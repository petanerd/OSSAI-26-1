# Week 2 실행형 실습

## 목표

평가체계를 고치고 이미지를 읽는 두 모델(VLM)을 같은 조건에서 비교한다.

실습을 마치면 다음을 할 수 있다.

- 기존 점수표에 답하기 어려운 질문을 먼저 찾아 평가 기준을 고친다.
- 모델 카드의 적합성 근거와 실제 데이터의 품질 결과를 구분한다.
- Gemma 실패를 prompt, 출력 구조, 시각 추론, API 실행 문제로 나눈다.
- 같은 모델에서 prompt만 바꾼 전후 결과를 문제별로 비교한다.
- Google AI Studio key를 안전하게 연결하고 Gemini를 제한 실행한다.
- 품질 실패, API 제공사(provider) 오류와 비교 불가를 서로 다른 결과로 기록한다.

## 이 문서에서 쓰는 이름

| 쉬운 이름 | 코드에서 쓰는 이름 | 뜻 |
| --- | --- | --- |
| 입력 지시문 | prompt | 모델에 질문과 함께 보내는 규칙 |
| 답변 형식 | schema | JSON field와 값이 지켜야 할 구조 |
| 채점 코드 | scorer | 모델 답을 정해진 규칙으로 검사하는 코드 |
| 고정 규칙 채점기 | deterministic scorer | 같은 저장 답·기대 답·규칙이면 같은 점수를 계산하는 코드 |
| 모델 기반 채점기—결과가 달라질 수 있음 | `(model-based scorer, stochastic scorer)` | 별도 LLM이 의미를 판단하며 반복 평가 결과가 달라질 수 있는 채점기 |
| 채점 규칙 묶음 | profile | 한 실행에서 함께 적용하는 채점 기준과 버전 |
| API 제공사 | provider | 모델 API를 제공하는 회사 또는 서비스 |
| 고정 호출 경로 | route | provider, model과 endpoint를 묶은 비교 단위 |
| 원본 응답 | raw response | API가 반환한 내용을 가공하기 전에 저장한 값 |
| 저장 예제 | fixture | API를 다시 부르지 않고 코드 동작을 확인하는 고정 응답 |
| 실제 처리 모델 | actual model | provider가 요청을 실제로 처리했다고 보고한 model ID |
| 실행 증거 파일 | artifact | 입력·응답·점수·시간·token을 함께 남긴 결과 파일 |
| 자동 판정 기준 | gate | 통과·실패·판단 보류를 기계적으로 나누는 조건 |
| 입력 목록 지문 | input manifest hash | 입력 파일과 질문이 같은지 확인하는 SHA-256 값 |
| 비교 조건 지문 | comparison contract hash | prompt·schema·scorer 등 비교 조건이 같은지 확인하는 SHA-256 값 |

이후 표와 명령에서는 코드와 결과 파일에 맞춰 오른쪽 영어 이름을 사용한다.

## 오늘의 실험


| 실험 | 고정 | 변경 | 말할 수 있는 것 |
| --- | --- | --- | --- |
| 모델 전환 진단 | AIHub 질문과 현재 채점 규칙 | Nemotron → Gemma | 다음 모델을 시험할 근거와 추가 문제 |
| Gemma prompt A/B | Gemma, 이미지, 질문, schema, scorer | prompt만 변경 | prompt 변경 전후의 문제별 변화 |
| provider 비교 | 이미지, 질문, 개선 prompt, schema, scorer | NIM Gemma → AI Studio Gemini | 두 고정 route의 품질·시간·token 차이 |

모델 전환의 과거 실행은 Git SHA와 입력 manifest가 완전히 같지 않으므로 통제된 A/B가
아니다. 모델 카드와 진단 점수만으로 “Gemma가 더 좋다”고 결론 내리지 않는다.

## 준비

Week 2 내용이 `main`에 병합된 실습 저장소에서 진행한다. 준비한 AIHub PDF와
40개 질문을 사용한다.

```bash
uv sync --locked --dev
```

처음 환경을 만들었거나 `uv.lock`이 바뀐 경우에만 다시 실행한다. 현재 `uv`는 개발 의존성
그룹을 기본으로 포함하므로 `--dev`를 덧붙이지 않는다.

두 실제 VLM에는 PDF 추출 문장을 보내지 않는다. 질문과 같은 page JPEG만 전달하며 OCR과
시각적 판단은 VLM이 수행한다. PDF text layer는 사람이 라벨을 점검하는 보조 자료일 뿐
모델 입력, 결정적 채점과 비교 조건에 포함하지 않는다.

## 1. 기존 평가체계부터 질문하기

### 먼저 답할 질문

다음 질문마다 현재 답과 수정할 답을 직접 적는다.

1. 의미가 맞는 긴 문장이면 `answer` 작성 기준을 통과한 것인가?
2. 질문의 연도를 답에 반복하면 숫자 정답으로 인정할 것인가?
3. Markdown fence를 제거해 파싱할 수 있으면 구조를 지킨 것으로 볼 것인가?
4. 근거 페이지가 맞고 답이 틀리면 전체 성공인가?
5. API timeout을 모델 오답 0점으로 넣을 것인가?
6. token F1 하나로 숫자, 날짜, 기관명과 근거를 모두 판정할 수 있는가?
7. PDF 추출 문장을 모델이나 scorer에 주면 VLM의 OCR을 평가했다고 할 수 있는가?

### 이번 실습의 수정된 답

- `answer`는 업무 요구사항에 맞는 짧은 값이어야 한다. 숫자 질문에는 질문의 연도를 반복하지
  않는다.
- parser는 fence를 제거해 내용을 진단할 수 있지만 `json_object_only=0`을 보존한다.
- provider 오류는 품질 분모에서 제외하고 별도 오류율로 기록한다.
- F1은 원인을 찾는 진단 점수다. 전체 성공을 단독 결정하지 않는다.
- VLM 입력과 채점에는 PDF 추출 문장을 사용하지 않는다.

### 이번 실습에서 쓰는 채점기

현재 AIHub 질문에는 짧은 기대 답, 답변 보류 여부와 근거 페이지가 있다. 따라서 외부
Judge 없이 `aihub-vqa-deterministic-v2` 고정 규칙 채점기를 사용한다. 같은 질문에 VLM이
다른 답을 만드는 현상과, 저장한 같은 답을 scorer가 다르게 평가하는 현상을 구분한다.

- task model의 `temperature=0`: 답 생성의 변화를 줄이는 조건
- 고정 규칙 채점기(deterministic scorer): 저장된 같은 답을 같은 규칙으로 다시 계산하면
  같은 점수
- 모델 기반 채점기(model-based scorer, stochastic scorer): 별도 LLM이 설명 의미를
  판단하므로 사람 보정과 반복 확인이 필요

DeepEval은 여기서 실행 결과를 모아 보여 주는 도구다. 현재 지표는 Python 코드가 먼저
계산하며 `judge_status=not_requested`다. 전체 지표의 역할과 수식은
[Week 1의 채점기와 수식 설명](week-01-lab.md#채점기-두-종류-고정-규칙과-모델-기반)을
참고한다.

현재 전체 성공은 다음 네 조건의 AND다.

```text
schema_validity
AND abstention_correct
AND answer_correct
AND evidence_coverage
```

| 전체 성공 구성 | 확인하는 것 |
| --- | --- |
| `schema_validity` | 정해진 JSON 구조와 필드 조건을 지켰는가 |
| `abstention_correct` | 답변과 답변 보류 중 올바르게 선택했는가 |
| `answer_correct` | 질문 종류별 정답 허용 규칙을 통과했는가 |
| `evidence_coverage` | 일반 답변에 기대 근거 페이지가 있는가 |

현재 채점 규칙 묶음(profile)은 `aihub-vqa-deterministic-v2`다. 다음 점수는 원인
분석용이며 단독 자동 판정 기준(gate)이 아니다.

| 진단 점수 | 용도 |
| --- | --- |
| `numeric_match` | 답에 포함된 숫자 목록 비교 |
| `answer_anls` | OCR 오차를 포함한 편집거리 유사도 |
| `answer_token_f1` | 여러 단어 답의 token 겹침 |
| `evidence_page_f1` | 예측 근거 페이지와 기대 페이지의 겹침 |
| `quote_answer_support` | 모델 답과 모델 인용문의 자체 일관성 |

`quote_answer_support`는 이미지에 실제로 그 문구가 있다는 증명이 아니다. 기대 답, 근거와
전체 성공은 결정적 규칙으로 판정하며 설명 품질은 이 데이터에서 Judge로 넘기지 않는다.

## 2. Nemotron에서 Gemma로 바꾼 이유를 검증하기

기존 모델은 NVIDIA Nemotron 3 Nano Omni였다. 공식 모델 카드는 image·OCR·document
intelligence를 지원하지만 언어 지원을 English only로 명시한다.

- [NVIDIA Nemotron 3 Nano Omni 공식 모델 카드](https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning/modelcard)
- [Google Gemma 4 공식 모델 카드](https://ai.google.dev/gemma/docs/core/model_card_4)

Gemma 4 카드는 multilingual OCR, document/PDF parsing과 35개 이상 언어의 즉시 지원을
명시한다. 따라서 한국어 질문·문서에 Gemma를 **시험할 이유**는 충분하다. 하지만 모델
카드는 이 AIHub 40건에서 더 높은 점수를 보장하지 않는다.

과거 raw response를 현재 결정적 채점기로 다시 계산한 진단 결과는 다음과 같다.

| 모델 전환 진단 | `task_success` | 해석 |
| --- | ---: | --- |
| Nemotron 과거 응답 | 16/40 | 한국어 비지원 카드와 달리 일부 문제는 통과 |
| Gemma 최초 기준 응답 | 8/40 | 모델 교체만으로 성공률이 오르지 않음 |

두 실행의 비교 조건이 완전히 같다는 증거가 없으므로 16과 8은 모델 우열의 인과 증거가
아니다. 결론은 다음 두 줄이다.

1. 언어 지원은 후보를 고르는 사전 조건이다.
2. 후보를 채택하려면 실제 데이터와 고정된 평가 조건에서 다시 측정해야 한다.

Gemma로 모델을 바꾼 commit에서는 모델 ID, catalog 안내와 preflight 기대값만 바뀌었다. prompt와
모델 호출·채점 코드는 그대로였다. 따라서 다음 Gemma 기준 결과에서 새로 드러난 실패를
먼저 관찰할 수 있다.

## 3. Gemma 기준 결과에서 수정 근거 찾기

API를 다시 호출하지 않고 고정한 Gemma 응답 40건을 현재 코드로 평가한다.

```bash
uv run --locked python scripts/run_workflow.py --config configs/week-01.yaml
uv run --locked python scripts/evaluate_workflow.py --config configs/week-01.yaml
```

기준 응답의 `task_success`는 8/40이다. 다음 사례를 raw response부터 확인한다.

| 사례 | 관찰 | 관점 | 수정할 곳 |
| --- | --- | --- | --- |
| `r01`, `r04` | 정답 외에 질문의 연도 반복 | answer 작성 기준 | prompt의 짧은 답 규칙 |
| `r03` | 첫 오답 뒤 설명과 두 번째 JSON | 출력 구조 | prompt의 JSON 하나 규칙 |
| `r06` | 중첩 배열·닫히지 않은 JSON | schema | prompt 필드 고정, parser는 엄격 유지 |
| `r22`, `r25` | 표의 인접 값 선택 | 시각 추론 | 행·열 교차값 재확인 지시 |
| 보류 사례 | 문서의 다른 숫자를 추측 | abstention | 찾을 수 없을 때만 정해진 보류값 사용 |
| actual model | LiteLLM prefix가 붙어 보고됨 | 실행 계보 | model ID 정규화 코드 |

여기서 parser가 마지막 JSON만 몰래 뽑거나 긴 답에서 기대 숫자만 골라내도록 바꾸지 않는다.
그렇게 하면 형식 위반이 통과로 숨는다. 출력 형식은 prompt에서 분명히 하고, scorer는 위반을
계속 보여 준다.

### 실제로 바뀐 prompt

```bash
diff -u prompts/pdf-question-answer.md prompts/pdf-question-answer-gemma4.md || true
```

개선 prompt는 다음을 추가했다.

- 숫자·날짜·기관명은 값만 반환
- 표·차트에서 대상, 행, 열과 단위를 재확인
- 근거는 답을 포함한 연속 원문 한 구절
- 첫 글자 `{`, 마지막 글자 `}`인 JSON 하나만 반환
- fenced JSON 예시 제거

기준 prompt는 “code fence를 쓰지 말라”고 하면서 fenced JSON 예시를 보여 주는 모순이
있다. 기준 파일은 전후 비교를 위해 보존하고, 개선 파일을 별도 후보로 둔다.

### 실제로 바뀐 코드

| 파일 | 변경 이유 |
| --- | --- |
| `src/verifiable_ai_workflow/model_identity.py` | LiteLLM의 전송용 접두어와 provider model ID를 구분 |
| `src/verifiable_ai_workflow/prompt_comparison.py` | prompt 외 통제값과 문제별 변화를 확인 |
| `scripts/compare_gemma_prompts.py` | raw observation을 현재 scorer로 재평가 |

비교 코드는 provider 오류를 오답 0점으로 넣지 않는다. `not_comparable`로 보내고
`quality_eligible_count`와 `provider_error_count`를 따로 출력한다.

## 4. 같은 Gemma에서 prompt 전후 비교하기

### 대표 한 건

```bash
uv run --locked python scripts/inspect_prompt_comparison_case.py
```

`aihub-report-r01`에서 다음을 확인한다.

| 항목 | 기준 prompt | 개선 prompt |
| --- | --- | --- |
| 모델 | Gemma 4 31B IT | 동일 |
| 실제 답 | 연도와 설명을 포함한 문장 | `71.6%` |
| `numeric_match` | 0 | 1 |
| `task_success` | 0 | 1 |

두 응답은 실제 Gemma 실행에서 고정한 raw response다. 이 명령은 저장 응답을 다시 채점하므로
`evidence_kind=test_only`이며 API를 호출하지 않는다.

### 전체 실제 A/B raw observation 재평가

보존된 두 live run 폴더가 있을 때 실행한다.

```bash
uv run --locked python scripts/compare_gemma_prompts.py \
  --baseline-run reports/week-01-nvidia/runs/<BASELINE_RUN_ID> \
  --candidate-run reports/week-01-nvidia-gemma4/runs/<CANDIDATE_RUN_ID> \
  --rescore-current \
  --output reports/week-02/gemma-prompt-comparison-current.json
```

2026-08-03에 저장한 실제 원본 응답(raw observation)을 현재 profile로 다시 계산한 결과는
다음과 같다.

| 확인 항목 | 기준 prompt | 개선 prompt |
| --- | ---: | ---: |
| target | 40 | 40 |
| 품질 판정 가능 | 40 | 39 |
| provider 오류 | 0 | 1 |
| `task_success` | 9/40, 22.5% | 28/39, 71.8% |
| `numeric_match` | 40.0% | 84.6% |
| `schema_validity` | 92.5% | 89.7% |

문제별 변화는 `new_success=20`, `new_failure=1`, `unchanged=18`,
`not_comparable=1`이다.

- 새 실패 `aihub-report-r31`: 답변 보류 대신 숫자를 추측하고 JSON도 깨졌다.
- 비교 불가 `aihub-report-r24`: NVIDIA HTTP 500으로 답을 받지 못했다.

평균은 크게 올랐지만 provider 오류와 새 실패가 있으므로 자동 상태는 `inconclusive`다.
“prompt가 좋아 보인다”와 “자동 채택할 수 있다”는 다른 결론이다.

보존 live run이 없는 환경에서는 다음으로 case-diff와 fault 계산만 연습한다.

```bash
uv run --locked python scripts/evaluate_recorded_provider_routes.py
```

이 결과는 개선 prompt 실제 응답 3건을 기준 fixture에 덮어쓴 교육용 40건이다. 실제
candidate full이 아니며 현재 API 경로 품질을 주장하지 않는다. 기대 변화는 새 성공 2건,
동일 38건이다.

## 5. 두 provider가 공유할 최종 prompt 확정하기

Gemma 전용 후보는 `/no_think`를 포함한다. 이를 Gemini에도 보내면 prompt와 provider가
동시에 달라져 공정 비교가 아니다. 따라서 모델별 제어문을 뺀 다음 파일을 공통으로 쓴다.

```text
prompts/pdf-question-answer-json-only.md
```

`configs/week-02-live.yaml`의 두 route는 같은 질문, page JPEG, 공통 prompt, schema,
scorer와 생성 상한을 사용한다. 달라지는 것은 provider와 model route뿐이다.

`comparison_contract_sha256`가 다르면 결과를 직접 비교하지 않고 자동 `inconclusive`로
남긴다.

## 6. Gemini API key 발급과 연결

1. [Google AI Studio의 API key 안내](https://ai.google.dev/gemini-api/docs/api-key)를 연다.
2. 실습에 사용할 Google Cloud project에서 Gemini API에 제한된 key를 만든다.
3. key를 Markdown, terminal 출력, Git과 결과 JSON에 붙여 넣지 않는다.
4. Git에서 제외된 `.env`에 다음 환경 변수 이름으로 저장한다.

```dotenv
NVIDIA_NIM_API_KEY="..."
GEMINI_API_KEY="..."
```

코드는 `GEMINI_API_KEY` 값 자체를 artifact에 쓰지 않는다. NVIDIA와 Gemini key가 같거나
한쪽이 없으면 network 시작 전에 실패한다.

실행 전에 다음을 확인한다.

- Git 작업공간이 깨끗한 commit인가
- 두 model이 실행 당일 공식 catalog에 있는가
- 가격 확인일이 7일 이내인가
- key·quota와 AIHub page JPEG 외부 전송이 승인됐는가
- 새 출력 경로를 사용하는가

## 7. 같은 진단 3건을 두 provider에 보내기

먼저 다음 세 사례만 probe한다.

| `sample_id` | 고른 이유 |
| --- | --- |
| `aihub-report-r01` | 긴 답에 질문 연도를 반복했던 사례 |
| `aihub-report-r03` | JSON 두 개와 수정 설명을 냈던 사례 |
| `aihub-report-r31` | 답변 보류 대신 숫자를 추측했던 회귀 사례 |

각 명령은 NVIDIA 1회와 Gemini 1회, 합계 2회만 요청한다. 세 명령의 최악 상한은 요청 6회,
재시도 0회, 승인 비용 상한 합계 USD 0.03, 명령별 240초다.

```bash
uv run --locked python scripts/compare_live_provider_routes.py \
  --live --probe-sample-id aihub-report-r01 \
  --max-requests 2 --max-input-tokens 40000 --max-output-tokens 1000 \
  --max-retries 0 --max-cost-usd 0.01 --max-wall-seconds 240 \
  --catalog-verified-on <YYYY-MM-DD> \
  --output reports/week-02-live/probe-improved-r01-<RUN_ID>

uv run --locked python scripts/compare_live_provider_routes.py \
  --live --probe-sample-id aihub-report-r03 \
  --max-requests 2 --max-input-tokens 40000 --max-output-tokens 1000 \
  --max-retries 0 --max-cost-usd 0.01 --max-wall-seconds 240 \
  --catalog-verified-on <YYYY-MM-DD> \
  --output reports/week-02-live/probe-improved-r03-<RUN_ID>

uv run --locked python scripts/compare_live_provider_routes.py \
  --live --probe-sample-id aihub-report-r31 \
  --max-requests 2 --max-input-tokens 40000 --max-output-tokens 1000 \
  --max-retries 0 --max-cost-usd 0.01 --max-wall-seconds 240 \
  --catalog-verified-on <YYYY-MM-DD> \
  --output reports/week-02-live/probe-improved-r31-<RUN_ID>
```

각 결과에서 다음을 확인한다.

- requested model과 actual model이 일치하는가
- raw response와 구조화 답변이 저장됐는가
- latency와 input/output token이 기록됐는가
- `task_success` 실패가 어느 구성 점수 때문인가
- provider 오류가 품질 0점으로 바뀌지 않았는가

probe가 모두 성공해도 평가 범위가 3/40뿐이므로 전체 품질 우열은 `inconclusive`다. probe의
원본 응답, 실제 처리 모델, token과 오류를 확인한 뒤 다음 명령으로 전체 40건 × 2 route를
실행한다. 과거 full은 기준 prompt를 썼기 때문에 새 공통 개선 prompt의 full 결과로
재사용하지 않는다.

```bash
uv run --locked python scripts/compare_live_provider_routes.py \
  --live \
  --max-requests 80 --max-input-tokens 1600000 --max-output-tokens 40000 \
  --max-retries 0 --max-cost-usd 0.01 --max-wall-seconds 3600 \
  --catalog-verified-on <YYYY-MM-DD> \
  --output reports/week-02-live/full-improved-<RUN_ID>
```

전체 결과가 `fail`이면 명령 종료 코드는 1, 비교할 수 없으면 2다. 둘 다 실행 오류라는 뜻은
아니다. 출력 폴더의 `summary.json`에서 `automated_status`, API 제공사 오류와 실제 처리
모델 불일치 원인을 확인한다.

### 2026-08-05 기준 실행 결과

아래 표는 날짜와 Git SHA를 고정한 과거 실제 실행 기록이다. `reports/`는 Git에서 제외되므로
새로 받은 저장소에는 원본 실행 폴더가 없을 수 있다. 현재 실행의 증거로 재사용하지 말고,
이번에 만든 고유 출력 폴더의 `summary.json`과 원본 응답을 확인한다.

| sample | Gemma | Gemini | 확인한 문제 |
| --- | --- | --- | --- |
| `r01` | 성공, fenced JSON | 성공, 순수 JSON | 두 route 모두 `71.6%` |
| `r03` | 성공, fenced JSON | 성공, 순수 JSON | 두 route 모두 `2.6%` |
| `r31` | 실패, `106.0` 추측 | 실패, `93.6` 추측 | 요청한 연도·기간이 없는데 보류하지 않음 |

요청 6회는 모두 응답했고 provider 오류, 재시도와 actual model 불일치는 0건이었다. 두
route 모두 `task_success=2/3`이므로 이 표로 우열을 정하지 않는다. `r31`처럼 기대 답에
숫자가 없는 답변 보류 사례에서는 `numeric_match=1`이어도 정답이 아니다. 보류·정답·근거
점수를 함께 확인한다. 세부 기록은
[`Week 2 Gemma–Gemini 비교 결과 보고서`](week-02-gemma-gemini-comparison-report-2026-08-05.md)에
있다.

### 2026-08-05 전체 40건 × 2 route 재실행 결과

위 명령을 새 출력 폴더에서 다시 실행했다. 두 route 모두 40/40 응답했고 API 제공사 오류,
재시도와 actual model 불일치는 0건이었다. 실행 코드는 Git SHA
`e7f54dbe4f686568abb6ca3d70eca55f96bc7bb9`의 깨끗한 상태였다.

| 확인 항목 | NIM Gemma | AI Studio Gemini |
| --- | ---: | ---: |
| 품질 판정 가능 | 40/40 | 40/40 |
| `task_success` | 27/40, 67.5% | 35/40, 87.5% |
| 순수 JSON | 8/40 | 40/40 |
| schema 통과 | 38/40 | 40/40 |
| 평균 latency | 16,714ms | 2,487ms |
| input/output token | 111,513 / 3,530 | 367,337 / 3,459 |

문제별 변화는 `new_success=8`, `new_failure=0`, `unchanged=32`다. 평균 성공률은
Gemini가 20.0%p 높았다. 새 실패가 없으므로 상대 비교의 자동 상태는 `pass`다. 그러나
이 판정은 출시 승인이 아니다. Gemini의 절대 실패는 `r07`, `r27`, `r31`, `p01`, `p07`
다섯 건이고, 두 route 모두 `r31`에서 답변을 보류하지 못했다. 따라서
`release_claim=false`, 사람 결정은 `HOLD`다.

이번 실행 결과는 로컬
`reports/week-02-live/full-improved-20260805-rerun-01/summary.json`에 있다. 앞선 실행과
입력 manifest는 같지만 비교 계약 hash가 다르므로 두 실행의 latency 차이를 모델 변화로
해석하지 않는다. Gemini 호출 중 응답 생성 조절값(sampling 인자)의 사용 중단 예정 경고도
확인했다. 이번 비교 조건은 바꾸지 않았으며, 다음 실행 전 LiteLLM과 Gemini 지원 상태를
다시 확인한다.

실패 5건을 그대로 오답 다섯 건으로만 읽지 않는다.

- `r07`, `p07`: 답이나 근거를 잘못 고른 모델 실패다.
- `r31`: 문서에 없는 기간의 숫자를 추측한 답변 보류 실패다.
- `p01`: 한국어 날짜 표현이 기대값과 뜻은 같지만 현재 숫자 비교 규칙을 통과하지 못했다.
- `r27`: `소폭 감소 전환 예상`이 기대 답 `소폭 감소`를 포함하지만 현재 정답 허용 기준을
  통과하지 못했다.

마지막 두 건은 고정 규칙 채점 코드(deterministic scorer)의 엄격함을 보여 준다. 이번 실행
뒤 scorer를 바꿔 결과를 덮어쓰지 않았다. 같은 저장 원응답을 다시 넣으면 현재 규칙은 같은
실패를 낸다. 이는 재현 가능하다는 뜻이지 규칙이 의미상 완벽하다는 뜻은 아니다. 다음 평가
기준 변경 후보로 기록하고, 변경한다면 같은 저장 원응답을 새 scorer hash로 다시 계산해
기존 결과와 분리한다.

## 8. 원래 Week 2 계획에서 빠뜨리지 않을 것

### 모델 이름 세 가지

| 이름 | 뜻 |
| --- | --- |
| logical model | 실험에서 route를 부르는 이름 |
| requested model | API 요청에 넣은 model ID |
| actual model | provider가 실제 처리했다고 보고한 model ID |

actual model이 없거나 기대값과 다르면 답은 보존하지만 비교는 `inconclusive`다.

### API 오류 6건

`scripts/evaluate_recorded_provider_routes.py`가 `reports/week-02/faults.json`을 만든다.

| 상황 | 최종 처리 | 품질 비교 |
| --- | --- | --- |
| 인증 실패 | `provider_error`, 재시도 없음 | 제외 |
| 429 뒤 성공 | 모든 시도 시간·비용 기록 | 포함 |
| 반복 timeout | `provider_error` | 제외 |
| actual model 미보고 | 응답 보존 | 비교 중단 |
| actual model 불일치 | 응답 보존 | 비교 중단 |
| fallback 성공 | `availability` | 고정 route 품질에서 제외 |

```text
benchmark    = fallback을 끄고 고정 route의 품질을 평가
availability = retry와 fallback을 포함해 복구와 추가 비용을 평가
```

### 비교 조건이 다른 반례

prompt, schema, scorer, temperature나 최대 출력 token이 다르면 provider만 바꾼 비교가
아니다. `comparison_contract_sha256`가 다른 결과를 억지로 평균 내지 않고
`inconclusive`로 보낸다.

여기서 `temperature`는 task model의 답 생성 조건이다. scorer의 결정성은 저장 응답,
기대 답, scorer 코드와 profile이 같은지로 확인한다.

### 평균 외에 확인할 값

- `new_success`, `new_failure`, `unchanged`, `not_comparable`
- 품질 판정 가능 분모와 provider 오류 수
- actual model mismatch
- latency, input/output token, 비용과 retry
- 자동 상태와 사람의 `SHIP / HOLD / ROLLBACK / INVALID-RUN`

## 결과 정리

| 항목 | 결과 |
| --- | --- |
| 기존 평가체계에서 고친 질문 |  |
| 고정 규칙 채점과 모델 기반 채점의 차이 |  |
| Nemotron → Gemma 변경 근거 |  |
| Gemma 기준 실패 유형 2개 |  |
| prompt 또는 코드 변경 근거 |  |
| prompt A/B 새 성공 / 새 실패 / 비교 불가 |  |
| 두 provider probe 성공 수 / 6 |  |
| 두 provider full 성공 수 / 80 |  |
| actual model 불일치 수 |  |
| provider 오류 수 |  |
| latency·token 차이 |  |
| 자동 상태와 이유 |  |
| 사람 결정과 추가 증거 |  |

## 완료 확인

```bash
uv run --locked pytest tests/week2
uv run --locked ruff check .
```

다음을 모두 만족하면 Week 2 실습을 완료한 것이다.

- PDF 추출 문장을 VLM 입력이나 scorer에 사용하지 않았다.
- task model의 답 생성 변동과 scorer의 평가 변동을 구분했다.
- 현재 지표의 역할과 `task_success` 계산식을 설명할 수 있다.
- 모델 카드의 적합성과 실제 품질 결과를 구분했다.
- 모델 교체와 prompt 변경의 효과를 한 표에서 섞지 않았다.
- 실제 Gemma prompt 전후 응답을 현재 scorer로 비교했다.
- provider 오류를 오답으로 계산하지 않았다.
- 같은 공통 prompt로 두 provider의 동일 3건을 probe했다.
- 요청·비용 상한을 확인한 full 실행에서는 같은 공통 prompt로 두 provider의 40건씩을
  비교했다.
- benchmark와 availability를 분리했다.
- prompt 또는 runtime 조건 불일치를 `inconclusive`로 처리했다.
- 3건 probe와 전체 40건씩의 결과를 구분했다.

실제 API 전송을 승인받지 않은 경우에는 오프라인 활동만 완료한 것이다. 이 저장소의 기준
재실행은 실제 두 provider 40건씩의 응답까지 수집했고 상대 비교는 `pass`였다. 그러나
`release_claim=false`이고 답변 보류 실패가 남아 있으므로 모델 채택이나 배포 근거로 쓰지
않는다.
