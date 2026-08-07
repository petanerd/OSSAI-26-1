# Week 4 실습 — PromptOptimizer와 이미지 변형

## 이번 주에 답할 질문

지시문을 자동으로 바꿨을 때 실제로 나아졌는지, 그리고 입력 이미지가 조금 달라져도 같은
답을 내는지 어떻게 확인할 수 있는가?

이번 주에는 두 실험을 분리한다.

1. DeepEval `PromptOptimizer`와 `GEPA`가 development 18개로 후보 지시문을 만든다.
2. baseline과 후보를 validation 6개에서 비교한 뒤 하나를 고른다.
3. 선택한 지시문을 원본 차트와 이미지 변형 4개에 적용한다.

Prompt 최적화는 DeepEval `PromptOptimizer`와 GEPA 한 경로로 실행한다.

## 1. 데이터 분할 확인

Week 3에서 만든 `local-data/opencqa/week-03-pairs.jsonl` 30개를 그대로 사용한다.

| split | 개수 | 용도 |
| --- | ---: | --- |
| development | 18 | GEPA가 후보 지시문을 만드는 데 사용 |
| validation | 6 | baseline과 후보 중 하나를 선택 |
| test | 6 | 이번 실습에서는 열지 않음 |

`test_opened=false`를 결과에 남기는 이유는 후보 선택에 test 답을 사용하지 않았음을 분명히
하기 위해서다.

## 2. baseline 지시문과 평가 기준 읽기

다음 두 파일을 연다.

- `prompts/week-04-baseline.md`: GEPA가 수정할 시작 지시문
- `src/verifiable_ai_workflow/prompt_optimization.py`: 숫자와 핵심 token을 비교하는 고정 규칙

최적화 점수는 설명 품질 전체를 증명하지 않는다. JSON 구조를 지킨 답에서 기준 답의 숫자를
빠뜨리거나 추가했는지 70%, 핵심 token 겹침을 30%로 계산한다. 이 고정 점수는 후보 생성
방향을 일관되게 만드는 학습용 feedback이다. 최종 품질 판단은 사례를 직접 읽어야 한다.

코드 연결부터 API 없이 확인한다.

```bash
uv run --locked pytest tests/week4/test_prompt_optimization.py
```

## 3. PromptOptimizer 실행

실제 실행은 개발 데이터와 validation을 여러 번 호출하므로 수업 전에 예산과 provider quota를
확인한다. 아래 상한은 최대 80회, 요청당 입력 20,000 token과 출력 500 token을 예약한다.

```bash
uv run --locked python scripts/optimize_open_cqa_prompt.py \
  --live-optimize \
  --max-requests 80 \
  --max-input-tokens 1600000 \
  --max-output-tokens 40000 \
  --max-cost-usd 0.01 \
  --max-wall-seconds 7200 \
  --output reports/week-04/optimization
```

실행 뒤 다음 순서로 확인한다.

1. `candidate-prompt.md`: GEPA가 만든 후보
2. `validation.jsonl`: 6개에서 baseline과 후보의 출력·점수·이유
3. `summary.json`: 두 평균과 실제 선택
4. `calls.jsonl`: 실제 model, 원응답, token, 시간, 오류

후보 평균이 baseline보다 높지 않으면 `selected=baseline`이다. 자동 최적화가 실행됐다는
이유만으로 후보를 채택하지 않는다.

## 4. 차트 이미지 4가지로 바꾸기

OpenCQA 첫 번째 차트에서 변형을 만든다.

```bash
uv run --locked python scripts/generate_image_variants.py --pair-number 1
```

`local-data/opencqa/week-04-variants/`에서 원본과 다음 이미지를 직접 연다.

- `rotate-2.png`: 2도 회전
- `jpeg-60.jpg`: JPEG 품질 60
- `crop-right.png`: 오른쪽 40% 제거
- `occlude-center.png`: 가운데 50% 가림

변형 이름만 보고 근거가 남았다고 단정하지 않는다. 각 이미지를 보고
`variant-review.csv`의 `grounding_status`에 다음 중 하나를 쓴다.

- `preserved`: 질문에 필요한 수치와 비교 대상이 아직 보임
- `destroyed`: 필요한 근거가 잘리거나 가려짐

의도한 동작과 실제 근거 상태가 다르면 그 변형은 `invalid_variant`로 제외한다.

## 5. 원본과 변형을 같은 VLM으로 실행

사람 검토표를 모두 채운 뒤 5개 이미지를 같은 지시문으로 실행한다.

```bash
uv run --locked python scripts/run_image_robustness.py \
  --live \
  --max-requests 5 \
  --max-input-tokens 100000 \
  --max-output-tokens 2500 \
  --max-cost-usd 0.01 \
  --max-wall-seconds 900 \
  --output reports/week-04/robustness-live
```

최적화 후보를 선택했다면 다음 인자를 추가한다.

```text
--prompt reports/week-04/optimization/candidate-prompt.md
```

## 6. 견고성 결과 계산

```bash
uv run --locked python scripts/evaluate_image_robustness.py \
  --responses reports/week-04/robustness-live/responses.jsonl \
  --output reports/week-04/robustness-live/evaluation.json
```

근거가 보존된 변형은 원본 답의 숫자를 유지하고 답변을 보류하지 않아야 한다. 근거가
훼손된 변형은 추정하지 않고 답변을 보류하며 evidence를 비워야 한다. 두 상황을 같은
정답 유지율로 합치지 않는다.

## 완료 확인

```bash
uv run --locked pytest tests/week4
uv run --locked ruff check .
```

다음을 설명할 수 있으면 완료다.

1. 왜 development와 validation을 나누는가?
2. 왜 후보 평균이 낮으면 baseline을 유지하는가?
3. 왜 근거 보존 변형과 근거 훼손 변형의 통과 조건이 다른가?
