# Week 4 실습 — 자동으로 만든 지시문을 검증하고 이미지 변화에 대응하기

## 이번 주에 배우는 것

자동 지시문 최적화는 좋은 지시문을 확정하는 기능이 아니다. NVIDIA NIM Gemma가 차트 답을
만들고, Gemini가 그 답의 고정 점수와 이유를 읽어 지시문 후보를 만든다. 후보 생성에 쓰지 않은
검증 문제에서 기준 지시문과 비교한다. 이미지가 바뀌었을 때도 사람은 먼저 질문의 근거가
남았는지 확인해야 한다.

수업이 끝나면 다음 네 문장을 설명할 수 있어야 한다.

1. 개발 데이터와 검증 데이터를 나누지 않으면 좋아 보이는 후보를 공정하게 고를 수 없다.
2. 후보 점수가 기준선보다 높지 않으면 자동으로 만든 후보를 버리고 기준선을 유지한다.
3. 근거 보존과 근거 훼손은 기대하는 모델 행동이 서로 다르다.
4. API 오류와 유효한 모델 답의 품질 실패를 같은 실패로 세지 않는다.

이번 주의 전체 흐름은 다음과 같다.

```text
Week 3 OpenCQA 사례 30건
→ NIM Gemma가 development 18건의 차트 답 생성
→ Gemini가 답·기대 답·고정 점수로 지시문 후보 작성
→ validation 6건에서 기준선·후보 비교와 선택
→ test 6건은 후보 생성·선택에 사용하지 않음
→ 원본 차트와 이미지 변형 4개를 사람이 확인
→ 근거 보존에는 답 유지, 근거 훼손에는 안전한 답변 보류를 검사
```

## 1. 왜 데이터와 이미지 상태를 나누는가

### 두 모델의 역할

| 역할 | 모델 | 하는 일 |
| --- | --- | --- |
| 타깃 모델 | NIM Gemma | OpenCQA JPEG와 질문을 읽고 구조화 답 생성 |
| 최적화 검토 모델 | Gemini Flash Lite | 지시문·질문·기대 답·NIM 출력·고정 점수와 이유로 GEPA 진단·후보 작성 |

Gemini에는 OpenCQA 이미지와 사람의 변형 검토표를 보내지 않는다. Gemini가 지시문 후보를
만들었다고 그 후보가 정답이 되지는 않는다. 최종 선택은 별도 validation의 같은 고정 점수로
한다.

### 세 데이터 구분

Week 3에서 준비한 `local-data/opencqa/week-03-cases.jsonl` 30건을 그대로 사용한다.

| 데이터 구분 | 개수 | 이번 주의 역할 |
| --- | ---: | --- |
| development | 18 | DeepEval `PromptOptimizer`와 GEPA가 후보 지시문을 만드는 데 사용 |
| validation | 6 | 기준선과 후보 가운데 하나를 선택 |
| test | 6 | 후보 생성과 선택에 사용하지 않음 |

공개 test 답도 같은 파일에 들어 있다. 따라서 test를 보지 못했다고 주장하지 않는다.
`test_used_for_generation_or_selection=false`는 test 6건을 후보 생성과 선택 함수에 전달하지
않았다는 뜻이다. 이 작은 공개 test만으로 배포 성능도 주장하지 않는다.

### 두 이미지 상태

| 사람이 확인한 상태 | 쉬운 뜻 | 기대하는 모델 행동 |
| --- | --- | --- |
| `preserved` | 질문에 필요한 수치와 비교 대상이 보임 | 원본과 같은 핵심 답을 근거와 함께 반환 |
| `destroyed` | 필요한 근거가 잘리거나 가려짐 | 추정하지 않고 답변을 보류하며 근거를 비움 |

변형 이름만 보고 상태를 정하지 않는다. 사람이 실제 이미지를 본 결과가 변형의 의도와 다르면
그 변형은 `invalid_variant`다. 성공이나 실패에 넣지 않고 평가에서 제외한다.

## 2. 실습 준비

실행 프로젝트 저장소 최상위에서 준비한다.

```bash
uv sync --locked --dev

test -f local-data/opencqa/week-03-cases.jsonl
test -d local-data/opencqa/images
test -f prompts/week-04-baseline.md
test -f configs/nvidia-nim-gemma4.yaml
test -f configs/google-gemini-3.5-flash-lite-judge.yaml

uv run --locked pytest tests/week4
```

마지막 명령은 API를 호출하지 않는다. 데이터 분할, 지시문 선택, 이미지 hash, 사람 검토표와
채점 규칙을 확인하는 `test_only` 검사다.

개인 별칭과 기록 경로를 만든다.

```bash
STUDENT_ALIAS="course-alias"
WEEK4_STUDENT_DIR="local-data/week-04-students/$STUDENT_ALIAS"
WEEK4_REPORT_DIR="reports/week-04/students/$STUDENT_ALIAS"
mkdir -p "$WEEK4_STUDENT_DIR" "$WEEK4_REPORT_DIR"

test -e local-data/learning-progress.md || \
  cp ../../templates/learner-progress-template.md local-data/learning-progress.md
```

`course-alias`는 본인의 영문·숫자 별칭으로 바꾼다. 공백이나 `/`는 쓰지 않는다.

튜터가 현재 수업 release의 정확한 저장 결과 폴더 두 개를 알려 준다. 아래 `RELEASE_SHA`를
튜터가 알려 준 값으로 바꾼다.

```bash
OPTIMIZATION_DIR="local-data/week-04-full-runs/optimization-RELEASE_SHA"
ROBUSTNESS_DIR="local-data/week-04-full-runs/robustness-RELEASE_SHA"
```

과거 `week-03-pairs.jsonl`에서 만든 `optimization/` 결과는 현재 수업 정본이 아니다. 현재
`week-03-cases.jsonl` hash와 맞는 새 결과가 없으면 없는 값을 추정하지 말고 튜터에게 요청한다.

## 3. 저장된 지시문 선택 결과 읽기

PromptOptimizer 전체 실행은 여러 번의 실제 API 요청을 사용하므로 튜터가 같은 clean commit에서
수업 전에 한 번 준비한다. 학습자는 다음 다섯 파일을 순서대로 읽는다.

```bash
test -f "$OPTIMIZATION_DIR/candidate-prompt.md"
test -f "$OPTIMIZATION_DIR/selected-prompt.md"
test -f "$OPTIMIZATION_DIR/validation.jsonl"
test -f "$OPTIMIZATION_DIR/summary.json"
test -f "$OPTIMIZATION_DIR/calls.jsonl"
```

1. `candidate-prompt.md`: development 18건으로 만든 후보
2. `validation.jsonl`: validation 6건의 기준선·후보 출력과 고정 점수
3. `selected-prompt.md`: 실제로 선택된 기준선 또는 후보
4. `summary.json`: 데이터·모델·지시문·채점기 hash, 평균, 선택과 실행 상태
5. `calls.jsonl`: 실제 요청 모델·처리 모델, 원응답, token, 시간과 오류

먼저 실행이 현재 입력과 연결되는지 확인한다.

```bash
shasum -a 256 local-data/opencqa/week-03-cases.jsonl
rg -n '"(status|observed_status|git_sha|development_count|validation_count|test_count|test_used_for_generation_or_selection|baseline_mean|candidate_mean|selected|requested_model|expected_actual_model|provider_error_count|model_drift_count)"' \
  "$OPTIMIZATION_DIR/summary.json"
rg -n 'week-03-cases.jsonl' "$OPTIMIZATION_DIR/summary.json"
```

다음 조건을 모두 확인해야 평균을 비교한다.

- `observed_status=complete`
- development 18건, validation 6건, test 6건
- `test_used_for_generation_or_selection=false`
- `provider_error_count=0`, `model_drift_count=0`
- `target_provider`는 NIM Gemma, `optimizer_provider`는 Gemini Flash Lite
- `artifact_sha256.week-03-cases.jsonl`과 현재 파일의 SHA-256이 같음
- 요청 모델과 실제 처리 모델이 같음

그다음 validation 사례를 읽는다.

```bash
sed -n '1,4p' "$OPTIMIZATION_DIR/validation.jsonl"
diff -u prompts/week-04-baseline.md "$OPTIMIZATION_DIR/selected-prompt.md" || true
```

최적화 점수는 JSON 구조가 유효한 답에서 기준 답의 숫자 일치를 70%, 핵심 단어 겹침을 30%로
계산한 학습용 고정 점수다. 설명 품질 전체를 증명하지 않는다. 후보 평균이 기준선보다 높을 때만
후보를 선택한다. `status=pass`는 실행 조건과 파일이 완결됐다는 뜻이지 모든 답이 좋다는 뜻이
아니다.

다음 표를 `local-data/learning-progress.md`의 Week 4에 기록한다.

| 확인 항목 | 기록할 값 |
| --- | --- |
| 기준선 validation 평균 |  |
| 후보 validation 평균 |  |
| 실제 선택 | `baseline` 또는 `candidate` |
| 선택 이유 |  |
| 가장 낮은 validation 사례와 이유 |  |

## 4. 이미지 변형을 직접 보고 판정하기

튜터 저장 결과를 보기 전에 같은 첫 번째 사례의 변형을 개인 폴더에 만든다. 이 명령은 API를
호출하지 않는다.

```bash
STUDENT_VARIANT_DIR="$WEEK4_STUDENT_DIR/variants"
test ! -e "$STUDENT_VARIANT_DIR"

uv run --locked python scripts/generate_image_variants.py \
  --pair-number 1 \
  --output "$STUDENT_VARIANT_DIR"
```

`case.json`의 `original_image`와 다음 네 파일을 편집기에서 직접 연다.

- `rotate-2.png`: 원본을 2도 회전
- `jpeg-60.jpg`: JPEG 품질 60으로 압축
- `crop-left.png`: 왼쪽 40% 제거
- `occlude-answer.png`: 왼쪽 일부를 회색으로 가림

질문의 대상·기간·수치와 비교 대상을 먼저 찾는다. 그 근거가 남아 있으면 `preserved`, 찾을 수
없으면 `destroyed`를 개인 `variant-review.csv`의 `grounding_status`에 쓴다. 다른 열과 hash는
바꾸지 않는다.

```text
preserved 또는 destroyed만 입력
빈칸 금지
변형 이름이 아니라 실제 이미지로 판단
```

개인 변형은 판정 연습 자료다. 튜터의 실제 VLM 응답이 어느 이미지에서 만들어졌는지는 튜터
정본의 `variants.jsonl`, `variant-review.csv`와 `summary.json` hash로 따로 확인한다.

## 5. 저장된 이미지 견고성 결과 다시 계산하기

튜터가 준비한 정본은 같은 선택 지시문으로 원본 1개와 변형 4개를 실제 호출한 결과다.

```bash
test -f local-data/opencqa/week-04-variants/case.json
test -f local-data/opencqa/week-04-variants/variants.jsonl
test -f local-data/opencqa/week-04-variants/variant-review.csv
test -f "$ROBUSTNESS_DIR/responses.jsonl"
test -f "$ROBUSTNESS_DIR/calls.jsonl"
test -f "$ROBUSTNESS_DIR/summary.json"
test -f "$ROBUSTNESS_DIR/evaluation.json"
test -f "$ROBUSTNESS_DIR/evaluation-manifest.json"
```

API를 다시 호출하지 않고 같은 응답을 현재 채점기로 계산한다.

```bash
uv run --locked python scripts/evaluate_image_robustness.py \
  --responses "$ROBUSTNESS_DIR/responses.jsonl" \
  --output "$WEEK4_REPORT_DIR/evaluation.json"
```

다음 순서로 결과를 읽는다.

1. `summary.json`: 5개 응답 완결 여부, 실제 모델, 선택 지시문 hash와 오류
2. `responses.jsonl`: 원본·변형별 원응답과 구조화 답
3. 개인 `evaluation.json`: 원본과 변형 4개의 `passed / failed / invalid_variant`
4. 개인 `evaluation-manifest.json`: 응답·변형·검토표·채점기·출력 형식 hash

근거가 보존된 변형은 원본과 변형 모두 점수 0.8 이상이고, 근거가 있으며, 원본 답의 숫자를
유지해야 한다. 근거가 훼손된 변형은 원본이 통과하고 변형 답이 `abstained=true`, 빈 근거와
보류 이유를 가져야 한다. 두 상태를 하나의 정답 유지율로 합치지 않는다.

## 6. 강의자 대표 live 관찰

전체 PromptOptimizer는 수업 중 다시 실행하지 않는다. 외부 전송·모델·가격·quota와 상한이
승인된 경우에만 튜터가 884번 한 사례를 대표로 실행한다. 원본과 변형 4개를 각각 보내므로
사례는 한 건이지만 실제 VLM 요청은 최대 5회다. 전체 명령과 중단 기준은 Week 4 튜터
runbook에만 있다.

대표 실행이 끝나면 다음만 확인한다.

1. `record_count=5`, `target_count=5`인가?
2. `observed_status=complete`인가?
3. 실제 처리 모델이 요청 모델과 같은가?
4. API 오류와 구조화 답의 품질 실패를 구분했는가?
5. 저장 정본과 다른 답이 나왔다면 확률적 변동으로 기록했는가?

대표 실행은 한 development 사례의 반복 관찰이다. 새 지시문을 선택하거나 held-out 견고성을
주장하는 근거가 아니다. 승인이 없거나 provider가 중단되면 `not_run` 또는 `partial`로 남긴다.

## 7. 제출

다음 세 경로를 보존한다.

1. `$WEEK4_STUDENT_DIR/variants/variant-review.csv`: 직접 판정한 네 행
2. `$WEEK4_REPORT_DIR/evaluation.json`: 튜터 저장 응답을 현재 채점기로 계산한 결과
3. `local-data/learning-progress.md`: 데이터 분할, 선택 이유와 주장할 수 없는 범위

학습 기록에는 다음 문장을 본인의 결과에 맞게 완성한다.

```text
development 18건에서 만든 후보를 validation 6건에서 비교해 ______을 선택했다.
근거 보존 변형에는 ______을, 근거 훼손 변형에는 ______을 기대했다.
이 결과만으로 ______은 주장할 수 없다.
```

API key, `.env`, OpenCQA 원본과 튜터 정본은 제출하지 않는다.

## 완료 기준

- development·validation·공개 test의 역할을 설명했다.
- 현재 `week-03-cases.jsonl`과 저장 최적화 결과의 hash를 확인했다.
- validation 평균이 높지 않으면 기준선을 유지하는 코드를 확인했다.
- 원본과 변형 네 개를 직접 보고 근거 보존·훼손을 판정했다.
- 저장 VLM 응답 5개를 다시 채점하고 실패 이유를 한 사례에서 연결했다.
- `invalid_variant`, 품질 `fail`, provider 문제의 `inconclusive`를 구분했다.
- 대표 live 한 사례를 전체 견고성이나 배포 품질로 일반화하지 않았다.
