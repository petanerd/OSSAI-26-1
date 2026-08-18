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

## 3. 실제로 지시문이 어떻게 바뀌었는지 읽기

PromptOptimizer 전체 실행은 여러 번의 실제 API 요청을 사용하므로 튜터가 수업 전에 한 번
준비한다. 학습자는 명령부터 실행하지 말고 이번 정본의 결론을 먼저 읽는다.

| 질문 | 2026-08-18 정본의 답 |
| --- | --- |
| 무엇이 문제였나? | 짧은 값만 요구한 기준 지시문이 설명형 질문에도 답을 지나치게 줄였다. |
| Gemini가 무엇을 바꿨나? | 질문에 따라 서술형 문장과 세부 내용도 쓸 수 있게 한 문장을 완화했다. |
| 모든 문제가 좋아졌나? | 아니다. 6건 중 3건은 상승, 1건은 동일, 2건은 하락했다. |
| 무엇을 선택했나? | 평균이 더 높은 기준 지시문을 유지했다. |

실제 실행은 Git `2102ba6`에서 NIM 45회와 Gemini 4회를 사용했다. 오류와 실제 모델 불일치는
0건이었다. 아래 내용은 그 실행의 `candidate-prompt.md`, `validation.jsonl`, `summary.json`,
`calls.jsonl`을 그대로 줄여 설명한 것이다.

### 3-1. 기준 지시문에서 개선할 부분을 찾았다

기준 지시문의 핵심 문장은 다음과 같았다.

```text
`answer`에는 질문이 요구한 값과 단위만 간결하게 씁니다.
```

개발 데이터(development)에는 값 하나를 묻는 질문뿐 아니라 추세, 의견과 여러 집단의 차이를
묻는 질문도 있다. Gemini는 NIM 답의 낮은 점수와 이유를 읽고 다음처럼 진단했다.

```text
성공: JSON 구조, evidence와 답변 보류 형식은 대체로 지켜졌다.
문제: "값과 단위만 간결하게"라는 문장이 설명형 질문의 필요한 맥락까지 줄이게 했다.
제안: 질문이 설명을 요구하면 서술형 문장과 필요한 세부 내용도 허용한다.
```

이 내용은 `calls.jsonl`의 Gemini 원응답을 한국어로 줄인 것이다. Gemini는 이미지와
validation·test 사례를 보지 않았다. 진단이 그럴듯해도 아직 개선 증거는 아니다.

Gemini 호출 4회에는 `진단 → 새 지시문 제안`이 두 번 남아 있다. 두 번째 제안은 모든 수치와
세부 통계를 빠짐없이 쓰도록 더 강하게 요구했다. 저장된 최종 후보는 그보다 작은 첫 번째
변경을 사용했다. `calls.jsonl`만으로 내부 후보별 점수를 모두 재구성할 수는 없으므로,
학습자는 저장된 `candidate-prompt.md`부터 별도 validation에서 확인한다.

### 3-2. 실제 후보는 한 문장을 완화했다

기준과 저장 후보의 중요한 차이는 다음 두 줄이다.

```diff
- `answer`에는 질문이 요구한 값과 단위만 간결하게 씁니다.
+ `answer`에는 질문이 요구한 형태에 맞춰 간결한 값과 단위,
+ 또는 필요한 서술형 문장과 세부 내용을 작성합니다.
```

JSON 6개 field, 근거 인용, `confidence` 범위와 답변 보류 규칙은 바꾸지 않았다. 즉 이번
가설은 “설명형 질문에는 필요한 맥락을 허용하면 점수가 오른다”이다. 더 길게 쓰라는 지시가
항상 더 좋은 답을 만든다는 뜻은 아니다.

다음 명령으로 실제 전체 차이를 확인한다.

```bash
diff -u prompts/week-04-baseline.md "$OPTIMIZATION_DIR/candidate-prompt.md" || true
```

### 3-3. 검증 데이터 6건에서 좋아진 답과 새 실패가 함께 나왔다

후보 생성에 쓰지 않은 validation 6건의 실제 결과는 다음과 같다. 점수는 JSON 구조가 유효한
답에서 기준 답의 숫자 일치를 70%, 핵심 단어 겹침을 30%로 계산한다.
채점 이유의 `missing`은 기준 답에 있지만 모델 답에서 놓친 값이다. `extra`는 기준 답에 없는
추가 값이다.

| `sample_id` | 기준 | 후보 | 변화 | 실제로 읽을 점 |
| --- | ---: | ---: | ---: | --- |
| `171` | 0.1077 | 0.0000 | -0.1077 | 후보의 `confidence=1.95`가 허용 범위를 벗어남 |
| `699` | 0.6121 | 0.2681 | -0.3440 | 기준 답보다 G7 여섯 나라 수치를 더 넣어 extra 숫자가 늘어남 |
| `6447` | 0.0808 | 0.1164 | +0.0356 | 문장 맥락은 늘었지만 불필요한 값도 그대로 남음 |
| `2208` | 0.0000 | 0.0000 | 0.0000 | 후보가 답변 보류의 정해진 `answer`를 어김 |
| `4327` | 0.3650 | 0.3833 | +0.0183 | 추세 설명이 조금 더 구체적이 됨 |
| `5978` | 0.7004 | 0.8175 | +0.1171 | 질문의 `2050` 맥락을 답에 포함함 |
| **평균** | **0.3110** | **0.2642** | **-0.0468** | **후보를 버리고 기준 유지** |

평균만 보면 왜 바뀌었는지 알 수 없다. 아래 세 사례처럼 출력 문장을 함께 읽어야 한다.

#### 좋아진 사례 — `5978`

질문은 `Describe the projections of the California population in 2050.`이다.

```text
기준 answer:
The 2014 projection for the total population is 49.8 million,
and the 2007 projection is 59.5 million.

후보 answer:
The total population projections for California in 2050 are 49.8 million
according to the 2014 projection and 59.5 million according to the 2007 projection.
```

후보는 같은 수치를 쓰면서 `California in 2050`을 명시했다. 기준 답에서 빠졌던 질문의 맥락이
늘어 점수가 `0.7004 → 0.8175`로 올랐다. 이것은 변경 가설이 효과를 낸 사례다.

#### 새로 나빠진 사례 — `699`

질문은 `How is the income inequality among G7 countries?`이다.

```text
기준 answer:
The U.S. has the highest level of income inequality among G7 countries
with a Gini coefficient of 0.434.

후보 answer:
Among G7 countries, the U.S. has the highest level of income inequality
with a Gini coefficient of 0.434, followed by the UK (0.392), Italy (0.373),
Japan (0.363), Canada (0.352), Germany (0.351), and France (0.326).
```

후보는 기준 답이 강조한 최고·최저 비교보다 여섯 나라의 수치를 더 넣었다. 고정 채점기는
이 값을 extra 숫자로 계산했고 점수는 `0.6121 → 0.2681`로 떨어졌다. 이 결과는 현재 채점
규칙에서의 회귀다. 사람이 읽는 설명 품질까지 후보가 반드시 더 나쁘다는 뜻은 아니다.
**더 길고 자세한 답이 자동으로 더 좋은 답이 되는 것도 아니다.**

#### 출력 계약까지 깨진 사례 — `171`

후보 답에는 다음 값이 들어 있었다.

```json
{"confidence":1.95,"abstained":false}
```

`confidence`는 0 이상 1 이하라는 규칙을 지켜야 한다. 답 문장이 더 자연스러워도 구조 검사를
통과하지 못하면 이 사례의 점수는 0이다. 지시문에서 구조 규칙을 그대로 유지했더라도 모델의
새 응답은 다시 검사해야 한다. 이번에 바꾼 문장은 `answer` 규칙이므로 그 변경이
`confidence=1.95`를 직접 일으켰다고 단정하지 않는다. 다만 실제 후보 실행에서 생긴 회귀이므로
선택할 때는 그대로 포함한다.

### 3-4. 그래서 선택 지시문은 다시 기준선이 됐다

후보는 일부 설명형 질문을 고쳤지만 더 큰 회귀와 출력 형식 위반도 만들었다. 따라서
`summary.json`에는 다음 결론이 남았다.

```json
{
  "baseline_mean": 0.311,
  "candidate_mean": 0.26421666666666666,
  "candidate_changed": true,
  "selected": "baseline",
  "selection_reason": "validation_not_improved"
}
```

`selected-prompt.md`는 `candidate-prompt.md`가 아니라 기준 지시문과 같다. 자동 최적화의
유효한 결론은 항상 “새 지시문 채택”이 아니다. 이번 결론은 **가설은 일부 사례에서 맞았지만
전체 validation에서는 기준선을 이기지 못했다**이다.

후보가 기준선과 완전히 같으면 반복 응답의 점수 차이를 개선으로 보지 않는다. 이때는 후보를
다시 validation하지 않고 `candidate_identical`로 기준선을 유지한다.

### 3-5. 저장 파일에서 위 설명을 직접 확인한다

다음 다섯 파일은 “지시문 변화 → 실제 답 → 점수 → 선택”을 연결한다.

```bash
test -f "$OPTIMIZATION_DIR/candidate-prompt.md"
test -f "$OPTIMIZATION_DIR/selected-prompt.md"
test -f "$OPTIMIZATION_DIR/validation.jsonl"
test -f "$OPTIMIZATION_DIR/summary.json"
test -f "$OPTIMIZATION_DIR/calls.jsonl"
```

1. `candidate-prompt.md`: development 18건을 보고 만든 후보
2. `validation.jsonl`: validation 6건의 기준·후보 출력과 점수 이유
3. `selected-prompt.md`: 실제로 선택한 기준 지시문
4. `summary.json`: 평균, 선택 이유와 데이터·모델·채점기 hash
5. `calls.jsonl`: NIM 45회와 Gemini 4회의 원응답, token, 시간과 오류

먼저 실행이 현재 입력과 연결되는지 확인한다.

```bash
shasum -a 256 local-data/opencqa/week-03-cases.jsonl
rg -n '"(status|observed_status|git_sha|development_count|validation_count|test_count|test_used_for_generation_or_selection|baseline_mean|candidate_mean|candidate_changed|selected|selection_reason|requested_model|expected_actual_model|provider_error_count|model_drift_count)"' \
  "$OPTIMIZATION_DIR/summary.json"
rg -n 'week-03-cases.jsonl' "$OPTIMIZATION_DIR/summary.json"
```

다음 조건을 모두 확인해야 결과 예시를 현재 실행의 근거로 사용한다.

- `observed_status=complete`
- development 18건, validation 6건, test 6건
- `test_used_for_generation_or_selection=false`
- `candidate_changed=true`, `selection_reason=validation_not_improved`
- `provider_error_count=0`, `model_drift_count=0`
- `target_provider`는 NIM Gemma, `optimizer_provider`는 Gemini Flash Lite
- `artifact_sha256.week-03-cases.jsonl`과 현재 파일의 SHA-256이 같음
- 요청 모델과 실제 처리 모델이 같음

그다음 후보 차이, validation 12행과 최종 선택을 확인한다.

```bash
diff -u prompts/week-04-baseline.md "$OPTIMIZATION_DIR/candidate-prompt.md" || true
sed -n '1,12p' "$OPTIMIZATION_DIR/validation.jsonl"
diff -u prompts/week-04-baseline.md "$OPTIMIZATION_DIR/selected-prompt.md" || true
```

마지막 `diff`에 아무 내용도 나오지 않는 것이 이번 정본의 올바른 결과다. 선택 파일이 기준
지시문과 같다는 뜻이다. `status=pass`는 실행과 파일이 완결됐다는 뜻이지 후보가 채택됐거나
모든 답의 품질이 좋다는 뜻이 아니다.

이 수치는 수업 release가 바뀌면 다시 확인한다. 학생 개인 점수나 배포 성능으로 일반화하지
않는다. 다음 표를 `local-data/learning-progress.md`의 Week 4에 기록한다.

| 확인 항목 | 기록할 값 |
| --- | --- |
| 기준 지시문의 개선 가설 |  |
| 후보에서 실제로 바뀐 문장 |  |
| 점수가 오른 validation 사례와 이유 |  |
| 점수가 떨어진 validation 사례와 이유 |  |
| 기준선 validation 평균 |  |
| 후보 validation 평균 |  |
| 실제 선택과 선택 이유 |  |

### 3-6. 한 개선 사례와 한 회귀 사례를 끝까지 팔로업한다

먼저 위 예시의 원본 두 쌍을 찾는다.

```bash
rg -n '"sample_id": "5978"' \
  local-data/opencqa/week-03-cases.jsonl "$OPTIMIZATION_DIR/validation.jsonl"
rg -n '"sample_id": "699"' \
  local-data/opencqa/week-03-cases.jsonl "$OPTIMIZATION_DIR/validation.jsonl"
```

각 `sample_id`에는 질문·기준 답 한 행과 기준·후보 모델 출력 두 행이 연결된다. 원응답을
읽고 다음 표를 채운다. 점수만 옮기지 말고 모델의 `answer`에서 실제로 추가되거나 빠진 말을
적는다.

| 팔로업 항목 | 개선 사례 `5978` | 회귀 사례 `699` |
| --- | --- | --- |
| 질문이 요구한 것 |  |  |
| 기준 모델의 `answer` |  |  |
| 후보 모델의 `answer` |  |  |
| 후보에서 추가·삭제된 내용 |  |  |
| 기준 → 후보 점수 |  |  |
| 채점기의 이유 |  |  |
| 처음 세운 개선 가설과 맞는가 |  |  |

마지막으로 두 사례만 보고 후보를 채택하지 않는다. 위 표는 변화 원인을 이해하는 활동이고,
선택은 validation 6건 전체의 사전 규칙을 따른다.

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
3. 개인 `evaluation.json`: 원본과 변형 4개의
   `passed / failed / inconclusive / invalid_variant`
4. 개인 `evaluation-manifest.json`: 응답·변형·검토표·채점기·metric·schema hash

`source_git_sha`는 실제 응답을 만든 코드이고, `scorer_sha256`은 지금 다시 계산한 채점기다.
응답을 다시 호출하지 않고 채점 규칙만 고쳤다면 두 값을 함께 남겨 변경 범위를 구분한다.

근거가 보존된 변형은 원본과 변형 모두 점수 0.8 이상이고, 근거가 있으며, 원본 답의 숫자를
유지해야 한다. 원본 품질이 0.8 미만이면 변형 답이 같아도 정답 유지를 확인할 수 없어
`inconclusive`다. 근거가 훼손된 변형은 `abstained=true`, 빈 근거와 보류 이유를 가져야 한다.
두 상태를 하나의 정답 유지율로 합치지 않는다.

같은 날 NIM 실제 응답 5건은 모두 유효한 구조화 답이었고 provider 오류와 모델 불일치는
0건이었다. 원본이 필요 이상으로 주변 값을 나열해 점수 `0.139`로 실패했다. 회전·JPEG 답은
원본과 같았지만 원본 품질 때문에 `inconclusive`였고, 잘림·가림은 둘 다 안전하게 답변을
보류해 `passed`였다. 따라서 결과는 통과 2, 실패 1, 판정 불가 2, 변형 무효 0이다.

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
- 기준과 후보 지시문의 실제 변경 문장을 설명했다.
- 개선 사례와 회귀 사례에서 모델 답·점수·채점 이유를 같은 `sample_id`로 연결했다.
- 원본과 변형 네 개를 직접 보고 근거 보존·훼손을 판정했다.
- 저장 VLM 응답 5개를 다시 채점하고 실패 이유를 한 사례에서 연결했다.
- `invalid_variant`, 품질 `fail`, 원본 품질 부족·provider 문제의 `inconclusive`를 구분했다.
- 대표 live 한 사례를 전체 견고성이나 배포 품질로 일반화하지 않았다.
