# Week 4 실습 — 자동으로 만든 지시문을 검증하고 이미지 변화에 대응하기

## 이번 주에 배우는 것

이번 주에는 NIM Gemma가 처음 지시문으로 만든 답을 Gemini가 살펴본다. Gemini는 점수가 낮은
답을 보고 지시문을 고쳐 쓴다. NIM Gemma가 처음 지시문과 바뀐 지시문으로 같은 검증 문제에
다시 답하면 두 점수를 비교한다. 실제 실행에서는 바뀐 지시문의 평균이 더 낮아서 처음
지시문을 그대로 사용했다. 그다음 차트를 회전·압축·잘림·가림으로 바꾸고, 필요한 수치가
이미지에 남아 있는지 사람이 먼저 확인한다.

수업이 끝나면 다음 네 문장을 설명할 수 있어야 한다.

1. 지시문을 고치는 데 쓴 문제와 지시문을 고르는 문제를 왜 나누는지 설명한다.
2. 처음과 변경 후의 전체 `system` 메시지를 보고 실제로 바뀐 문장을 찾는다.
3. 같은 문제에서 NIM 답과 점수가 어떻게 달라졌는지 설명한다.
4. 필요한 수치가 남은 이미지에는 같은 답을, 수치가 사라진 이미지에는 답변 보류를 기대한다.

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

마지막 명령은 API를 호출하지 않는다. 문제 30개가 18·6·6개로 나뉘었는지, 지시문 선택
규칙이 맞는지, 이미지의 SHA-256과 사람 검토표가 연결되는지 확인한다.

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

튜터가 이번 수업에서 사용할 Git SHA와 저장 결과 폴더 두 개를 알려 준다. 아래
`RELEASE_SHA`를 튜터가 알려 준 짧은 Git SHA로 바꾼다.

```bash
OPTIMIZATION_DIR="local-data/week-04-full-runs/optimization-RELEASE_SHA"
ROBUSTNESS_DIR="local-data/week-04-full-runs/robustness-RELEASE_SHA"
```

과거 `week-03-pairs.jsonl`로 만든 `optimization/` 폴더는 이번 수업에서 쓰지 않는다. 현재
`week-03-cases.jsonl`과 같은 입력으로 만든 결과 폴더가 없으면 튜터에게 요청한다.

## 3. 실제로 지시문이 어떻게 바뀌었는지 읽기

이 절에서 **기준 지시문**은 처음 사용한 지시문이다. 저장 파일에서는 `baseline`이라고 쓴다.
**후보 지시문**은 Gemini의 제안을 반영한 새 지시문이다. 저장 파일에서는 `candidate`라고 쓴다.

2026-08-18에 실제로 실행한 순서는 다음과 같다.

1. NIM Gemma가 처음 지시문으로 개발 문제에 답했다.
2. Gemini가 점수가 낮은 답과 그 이유를 읽고 지시문 수정을 제안했다.
3. NIM Gemma가 바뀐 지시문으로 검증 문제 6개에 다시 답했다.
4. 같은 6개 문제에서 처음 지시문과 바뀐 지시문의 점수를 비교했다.
5. 바뀐 지시문의 평균이 더 낮아서 처음 지시문으로 돌아갔다.

이 실행에서는 NIM을 45회, Gemini를 4회 호출했다. API 호출 오류는 없었다. 요청한 모델과
실제로 응답한 모델도 같았다. 검증 문제 6개 중 3개는 점수가 올랐고, 1개는 같았으며,
2개는 떨어졌다.

### 3-1. Gemini는 왜 지시문을 바꾸자고 했을까

처음 지시문에는 다음 문장이 있었다.

```text
`answer`에는 질문이 요구한 값과 단위만 간결하게 씁니다.
```

이 문장은 “몇 퍼센트인가?”처럼 짧은 값을 묻는 질문에는 잘 맞는다. 하지만 개발 문제에는
“어떻게 변했는가?”, “두 집단은 어떻게 다른가?”처럼 문장으로 설명해야 하는 질문도 있었다.
Gemini는 처음 지시문, NIM의 실제 답, 사람이 작성한 기준 답, 점수와 감점 이유를 읽었다.
그 뒤 다음과 같은 뜻의 제안을 만들었다.

```text
잘된 점: NIM은 정해 둔 JSON 모양과 근거 작성 규칙을 대체로 지켰다.
고칠 점: "값과 단위만" 쓰게 하면 설명이 필요한 질문에서도 답이 너무 짧아진다.
바꿀 점: 질문이 설명을 요구하면 짧은 문장과 필요한 세부 내용도 쓰게 한다.
```

위 내용은 `calls.jsonl`에 저장된 Gemini 답을 쉬운 한국어로 줄인 것이다. Gemini는 차트
이미지를 보지 않았다. 후보를 고르는 데 사용할 검증 문제 6개와 마지막 확인용 test 문제
6개도 보지 않았다.

여기서 전체 내용으로 보여 주는 `system` 메시지는 NIM Gemma가 받은 메시지다. 현재
`calls.jsonl`에는 Gemini가 받은 전체 요청 문장이 아니라 Gemini의 전체 응답만 저장돼 있다.
따라서 저장되지 않은 Gemini 요청 문장을 실제 내용처럼 만들어 보여 주지 않는다.

Gemini는 `문제 설명 → 새 지시문 작성`을 두 번 수행했다. 두 번째에는 차트의 모든 수치와
세부 통계를 넣자는 더 긴 지시문도 제안했다. 최종 `candidate-prompt.md`에는 첫 번째 제안처럼
작게 바꾼 문장이 저장됐다. 현재 저장 파일에는 두 제안의 점수를 나란히 보여 주는 표가 없다.
따라서 왜 두 번째 제안이 빠졌는지는 추측하지 않는다.

### 3-2. NIM Gemma가 받은 전체 메시지를 본다

지시문 파일은 설명용 메모가 아니다. 코드가 파일 내용을 읽어 NIM Gemma의 `system` 메시지로
보낸다. `{question}` 자리에는 현재 문제의 질문이 들어간다. 그다음 `user` 메시지로 같은 질문과
차트 이미지를 보낸다.

아래는 문제 `5978`을 처음 지시문으로 실행했을 때의 전체 `system` 메시지다. 영어 질문은
“2050년 캘리포니아 인구 전망을 설명하라”는 뜻이다.

```text
/no_think

차트 이미지에서 아래 질문의 답을 찾고, JSON 하나만 반환하세요.

질문: Describe the projections of the California population in 2050.

이미지에서 확인한 내용만 사용하세요. 답을 찾는 과정은 출력하지 않습니다.

`answer`에는 질문이 요구한 값과 단위만 간결하게 씁니다. `evidence`의 `quote`에는
답을 직접 확인할 수 있는 차트의 연속된 글자와 수치를 그대로 씁니다. 차트 이미지는
1페이지로 보고 `evidence_id`는 `chart`, `page_number`는 `1`을 사용합니다.

출력 규칙:

- 첫 글자는 `{`, 마지막 글자는 `}`입니다.
- Markdown code fence, 설명, 두 번째 JSON을 출력하지 않습니다.
- 아래 6개 field를 모두 한 번씩 넣습니다.
- `confidence`는 0 이상 1 이하 숫자입니다.
- `tool_requests`는 항상 빈 목록입니다.

답을 확인할 수 있을 때의 JSON 모양은 다음과 같습니다. 예시 값은 복사할 정답이 아닙니다.

{"answer":"값과 단위","evidence":[{"evidence_id":"chart","quote":"답을 포함한 차트 글자와 수치","page_number":1}],"confidence":0.9,"abstained":false,"abstention_reason":null,"tool_requests":[]}

이미지에서 답을 확인할 수 없을 때는 추정하지 말고 아래 모양으로 답변을 보류합니다.

{"answer":"답변 보류","evidence":[],"confidence":0.0,"abstained":true,"abstention_reason":"이미지에서 답을 확인할 수 없음","tool_requests":[]}
```

Gemini의 제안을 반영한 뒤에는 다음 전체 `system` 메시지를 보냈다.

```text
/no_think

차트 이미지에서 아래 질문의 답을 찾고, JSON 하나만 반환하세요.

질문: Describe the projections of the California population in 2050.

이미지에서 확인한 내용만 사용하세요. 답을 찾는 과정은 출력하지 않습니다.

`answer`에는 질문이 요구한 형태에 맞춰 간결한 값과 단위, 또는 필요한 서술형 문장과 세부 내용을 작성합니다. `evidence`의 `quote`에는 답을 직접 확인할 수 있는 차트의 연속된 글자와 수치를 그대로 씁니다. 차트 이미지는 1페이지로 보고 `evidence_id`는 `chart`, `page_number`는 `1`을 사용합니다.

출력 규칙:

- 첫 글자는 `{`, 마지막 글자는 `}`입니다.
- Markdown code fence, 설명, 두 번째 JSON을 출력하지 않습니다.
- 아래 6개 field를 모두 한 번씩 넣습니다.
- `confidence`는 0 이상 1 이하 숫자입니다.
- `tool_requests`는 항상 빈 목록입니다.

답을 확인할 수 있을 때의 JSON 모양은 다음과 같습니다. 예시 값은 복사할 정답이 아닙니다.

{"answer":"값과 단위 또는 서술형 답변","evidence":[{"evidence_id":"chart","quote":"답을 포함한 차트 글자와 수치","page_number":1}],"confidence":0.9,"abstained":false,"abstention_reason":null,"tool_requests":[]}

이미지에서 답을 확인할 수 없을 때는 추정하지 말고 아래 모양으로 답변을 보류합니다.

{"answer":"답변 보류","evidence":[],"confidence":0.0,"abstained":true,"abstention_reason":"이미지에서 답을 확인할 수 없음","tool_requests":[]}
```

두 실행에서 `user` 메시지는 같다. 실제 코드에서는 이미지 파일을 base64 데이터로 바꿔
전송한다. 아래에서는 긴 이미지 데이터를 파일 경로로 줄여 표시했다.

```text
role: user

text:
Describe the projections of the California population in 2050.

image:
local-data/opencqa/images/5978.jpg
```

API 요청에는 Pydantic의 `StructuredAnswer`에서 만든 JSON Schema도 함께 들어간다. 이것은
프롬프트 문장이 아니라 API가 응답 모양을 제한하는 별도 설정이다.

전체 메시지를 놓고 보면 바뀐 곳은 두 군데다.

1. `answer`에 값만 쓰게 하던 문장을, 질문에 필요하면 설명도 쓰게 바꿨다.
2. 정상 답 예시의 `answer`를 `값과 단위`에서 `값과 단위 또는 서술형 답변`으로 바꿨다.

그 밖의 질문, 이미지 사용 규칙, 근거 작성법, JSON 6개 항목, `confidence` 범위와 답변 보류
규칙은 그대로다. 우리가 예상한 결과는 다음과 같다.

```text
설명이 필요한 질문에서는 빠졌던 대상·시점·비교 내용이 답에 추가될 것이다.
```

이 예상이 맞는지는 Gemini의 설명만 보고 정하지 않는다. NIM이 새 지시문으로 만든 답을
처음 답과 직접 비교한다. 저장 파일의 전체 차이는 다음 명령으로 다시 확인한다.

```bash
diff -u prompts/week-04-baseline.md "$OPTIMIZATION_DIR/candidate-prompt.md" || true
```

### 3-3. 검증 문제 6개의 실제 점수를 비교한다

아래 6개 문제는 Gemini가 지시문을 고칠 때 사용하지 않았다. 프로그램은 NIM의 답이 정해 둔
JSON 모양인지 먼저 확인한다. JSON이 맞으면 기준 답과 숫자가 얼마나 같은지 70%, 주요 단어가
얼마나 같은지 30% 비율로 점수를 계산한다. `missing`은 NIM이 빠뜨린 값이고, `extra`는
기준 답에는 없는데 NIM이 추가한 값이다.

| 문제 번호 | 처음 지시문 | 바뀐 지시문 | 점수 변화 | 모델 답에서 실제로 일어난 일 |
| --- | ---: | ---: | ---: | --- |
| `171` | 0.1077 | 0.0000 | -0.1077 | `confidence`에 허용 범위 밖의 값 `1.95`를 씀 |
| `699` | 0.6121 | 0.2681 | -0.3440 | G7 여섯 나라의 수치를 추가해 `extra` 값이 늘어남 |
| `6447` | 0.0808 | 0.1164 | +0.0356 | 문장은 자연스러워졌지만 필요하지 않은 값도 남음 |
| `2208` | 0.0000 | 0.0000 | 0.0000 | 답을 보류하면서 정해 둔 `answer` 문구를 쓰지 않음 |
| `4327` | 0.3650 | 0.3833 | +0.0183 | 전화 설문 응답률이 어떻게 변했는지 조금 더 자세히 씀 |
| `5978` | 0.7004 | 0.8175 | +0.1171 | 답에 `California in 2050`을 추가함 |
| **평균** | **0.3110** | **0.2642** | **-0.0468** | **처음 지시문의 평균이 더 높음** |

점수만 보면 왜 좋아지거나 나빠졌는지 알 수 없다. 아래에서 NIM이 실제로 쓴 답을 읽는다.

#### 좋아진 사례 — `5978`

질문은 `Describe the projections of the California population in 2050.`이다. 한국어로는
“2050년 캘리포니아 인구 전망을 설명하라”는 뜻이다.

```text
처음 지시문의 answer:
The 2014 projection for the total population is 49.8 million,
and the 2007 projection is 59.5 million.

바뀐 지시문의 answer:
The total population projections for California in 2050 are 49.8 million
according to the 2014 projection and 59.5 million according to the 2007 projection.
```

바뀐 지시문으로 만든 답에는 처음 답에 없던 `California in 2050`이 들어갔다. 두 답의
49.8 million과 59.5 million은 같다. 질문이 요구한 장소와 시점을 추가했기 때문에 점수가
`0.7004 → 0.8175`로 올랐다. 이 문제에서는 예상한 변화가 실제로 나타났다.

#### 처음보다 점수가 떨어진 사례 — `699`

질문은 `How is the income inequality among G7 countries?`이다. 한국어로는 “G7 국가의
소득 불평등은 어떠한가?”라는 뜻이다.

```text
처음 지시문의 answer:
The U.S. has the highest level of income inequality among G7 countries
with a Gini coefficient of 0.434.

바뀐 지시문의 answer:
Among G7 countries, the U.S. has the highest level of income inequality
with a Gini coefficient of 0.434, followed by the UK (0.392), Italy (0.373),
Japan (0.363), Canada (0.352), Germany (0.351), and France (0.326).
```

바뀐 지시문으로 만든 답은 모든 나라의 수치를 길게 나열했다. 프로그램은 기준 답에 없는
수치들을 `extra`로 세었고 점수는 `0.6121 → 0.2681`로 떨어졌다. 이것은 이 수업의 채점
방법으로 계산한 결과다. 사람이 읽었을 때도 무조건 더 나쁜 답이라는 뜻은 아니다. 다만
**답이 길고 자세하다는 이유만으로 더 좋은 답이라고 선택할 수도 없다.**

#### 미리 정한 JSON 규칙을 어긴 사례 — `171`

바뀐 지시문으로 실행했을 때 다음 값이 나왔다.

```json
{"confidence":1.95,"abstained":false}
```

`confidence`에는 0부터 1 사이의 숫자만 쓸 수 있다. `1.95`는 이 범위를 벗어나므로 프로그램이
답을 거부했고 점수는 0이 됐다. 이번에 바꾼 문장은 `answer` 작성 방법이다. 따라서 그 문장
때문에 `1.95`가 나왔다고 단정하지 않는다. 원인이 무엇이든 실제 실행에서 나온 실패이므로
후보 점수에서 빼거나 고쳐 쓰지 않는다.

### 3-4. 왜 처음 지시문을 그대로 사용했을까

수업을 시작하기 전에 “검증 문제 6개의 평균이 더 높은 지시문을 사용한다”라고 정했다.
처음 지시문의 평균은 `0.3110`, 바뀐 지시문의 평균은 `0.2642`다. 따라서 처음 지시문을
선택했다. `summary.json`에도 같은 결과가 저장돼 있다.

```json
{
  "baseline_mean": 0.311,
  "candidate_mean": 0.26421666666666666,
  "candidate_changed": true,
  "selected": "baseline",
  "selection_reason": "validation_not_improved"
}
```

`selected-prompt.md`를 열면 처음 지시문과 같은 내용이 나온다. 자동 지시문 최적화를 했다고
항상 새 지시문을 사용해야 하는 것은 아니다. 이번 실행에서 알게 된 내용은 다음 한 문장이다.

```text
설명을 허용하자 일부 답은 좋아졌지만, 6개 전체 평균은 낮아져 처음 지시문을 유지했다.
```

Gemini가 만든 문장이 처음 지시문과 글자까지 완전히 같을 수도 있다. 이때는 새 지시문이
생긴 것이 아니므로 NIM을 다시 호출하지 않는다. 저장 결과에는 `candidate_identical`이라고
쓴다.

### 3-5. 어느 파일에서 무엇을 확인할까

다음 다섯 파일을 순서대로 연다.

```bash
test -f "$OPTIMIZATION_DIR/candidate-prompt.md"
test -f "$OPTIMIZATION_DIR/selected-prompt.md"
test -f "$OPTIMIZATION_DIR/validation.jsonl"
test -f "$OPTIMIZATION_DIR/summary.json"
test -f "$OPTIMIZATION_DIR/calls.jsonl"
```

1. `candidate-prompt.md`: Gemini의 제안을 반영해 바뀐 지시문
2. `validation.jsonl`: 문제 6개의 처음 답·바뀐 답·점수와 감점 이유
3. `selected-prompt.md`: 최종적으로 사용할 처음 지시문
4. `summary.json`: 두 평균과 처음 지시문을 선택한 이유
5. `calls.jsonl`: NIM 45회와 Gemini 4회의 실제 응답, 사용 token, 걸린 시간과 오류

먼저 저장 결과가 이번 수업 파일로 만든 것인지 확인한다. SHA-256은 파일 내용으로 만든
고유한 문자열이다. 입력 파일이 바뀌면 이 문자열도 바뀐다.

```bash
shasum -a 256 local-data/opencqa/week-03-cases.jsonl
rg -n '"(status|observed_status|git_sha|development_count|validation_count|test_count|test_used_for_generation_or_selection|baseline_mean|candidate_mean|candidate_changed|selected|selection_reason|requested_model|expected_actual_model|provider_error_count|model_drift_count)"' \
  "$OPTIMIZATION_DIR/summary.json"
rg -n 'week-03-cases.jsonl' "$OPTIMIZATION_DIR/summary.json"
```

화면에 나온 영문 필드는 다음 뜻이다.

- `observed_status=complete`: 예정한 호출이 끝났고 필요한 파일이 모두 생겼다.
- development 18, validation 6, test 6: 30개 문제를 세 묶음으로 나눴다.
- `test_used_for_generation_or_selection=false`: 마지막 6개 문제는 지시문을 만들거나 고를 때
  사용하지 않았다.
- `candidate_changed=true`: 처음 지시문과 다른 후보가 만들어졌다.
- `selection_reason=validation_not_improved`: 후보 평균이 오르지 않아 처음 지시문을 골랐다.
- `provider_error_count=0`: API 호출 실패가 없었다.
- `model_drift_count=0`: 요청한 모델과 실제 응답한 모델이 달랐던 경우가 없었다.
- `artifact_sha256.week-03-cases.jsonl`: 실행에 사용한 입력 파일의 SHA-256이다. 현재 파일의
  SHA-256과 같아야 한다.

그다음 바뀐 문장, 문제별 모델 답 12개와 최종 지시문을 확인한다.

```bash
diff -u prompts/week-04-baseline.md "$OPTIMIZATION_DIR/candidate-prompt.md" || true
sed -n '1,12p' "$OPTIMIZATION_DIR/validation.jsonl"
diff -u prompts/week-04-baseline.md "$OPTIMIZATION_DIR/selected-prompt.md" || true
```

마지막 `diff`에 아무 내용도 나오지 않아야 한다. `selected-prompt.md`와 처음 지시문이 같다는
뜻이다. `status=pass`는 실행이 끝나고 파일이 모두 생겼다는 뜻이다. 바뀐 지시문이 선택됐거나
모델 답이 모두 좋다는 뜻은 아니다.

이 숫자는 2026-08-18에 저장한 실행의 예시다. 수업 코드나 입력 파일이 바뀌면 현재
`summary.json`의 숫자를 사용한다. 다음 표를 `local-data/learning-progress.md`의 Week 4에
기록한다.

| 확인 항목 | 기록할 값 |
| --- | --- |
| 처음 지시문에서 고치려고 한 문제 |  |
| 후보에서 실제로 바뀐 문장 |  |
| 점수가 오른 검증 문제와 이유 |  |
| 점수가 떨어진 검증 문제와 이유 |  |
| 처음 지시문의 평균 |  |
| 바뀐 지시문의 평균 |  |
| 실제 선택과 선택 이유 |  |

### 3-6. 지시문을 바꾸자 모델 답이 어떻게 달라졌는지 따라가 본다

점수가 오른 `5978`과 점수가 떨어진 `699`를 찾는다.

```bash
rg -n '"sample_id": "5978"' \
  local-data/opencqa/week-03-cases.jsonl "$OPTIMIZATION_DIR/validation.jsonl"
rg -n '"sample_id": "699"' \
  local-data/opencqa/week-03-cases.jsonl "$OPTIMIZATION_DIR/validation.jsonl"
```

각 문제에는 질문과 사람이 쓴 기준 답 한 줄이 있다. `validation.jsonl`에는 처음 지시문으로
만든 NIM 답과 바뀐 지시문으로 만든 NIM 답이 한 줄씩 있다. 세 줄을 같은 `sample_id`로
연결한 뒤 아래 표를 채운다.

| 확인할 내용 | 점수가 오른 `5978` | 점수가 떨어진 `699` |
| --- | --- | --- |
| 질문이 요구한 것 |  |  |
| 처음 지시문으로 만든 `answer` |  |  |
| 바뀐 지시문으로 만든 `answer` |  |  |
| 새 답에서 추가되거나 빠진 말 |  |  |
| 처음 점수 → 바뀐 점수 |  |  |
| 프로그램이 알려 준 감점 이유 |  |  |
| 처음 예상한 변화가 나타났는가 |  |  |

이 두 문제는 답이 왜 달라졌는지 배우기 위한 예시다. 두 문제만 보고 지시문을 고르지 않는다.
최종 선택에는 검증 문제 6개 전체의 평균을 사용한다.

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
없으면 `destroyed`를 개인 `variant-review.csv`의 `grounding_status`에 쓴다. 다른 열과
SHA-256은 바꾸지 않는다.

```text
preserved 또는 destroyed만 입력
빈칸 금지
변형 이름이 아니라 실제 이미지로 판단
```

개인 변형은 이미지를 보고 판단하는 연습 자료다. 튜터가 저장한 NIM 답이 어느 이미지에서
나왔는지는 실행 결과 폴더의 `variants.jsonl`, `variant-review.csv`, `summary.json`에 적힌
SHA-256으로 확인한다.

## 5. 저장된 이미지 견고성 결과 다시 계산하기

튜터가 수업 전에 저장한 결과는 같은 지시문으로 원본 이미지 1개와 바꾼 이미지 4개를 NIM에
실제로 보낸 결과다.

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

1. `summary.json`: 응답 5개가 모두 있는지, 어떤 모델과 지시문을 썼는지, 오류가 있었는지
2. `responses.jsonl`: 원본·변형별 원응답과 구조화 답
3. 개인 `evaluation.json`: 원본과 변형 4개의
   `passed / failed / inconclusive / invalid_variant`
4. 개인 `evaluation-manifest.json`: 응답·이미지·검토표·채점 규칙·출력 형식의 SHA-256

`source_git_sha`는 저장된 NIM 답을 만들 때 사용한 코드 버전이다. `scorer_sha256`은 그 답을
지금 채점한 Python 파일의 SHA-256이다. NIM을 다시 호출하지 않고 채점 규칙만 고쳤다면 두
값이 다를 수 있다.

근거가 보존된 변형은 원본과 변형 모두 점수 0.8 이상이고, 근거가 있으며, 원본 답의 숫자를
유지해야 한다. 원본 품질이 0.8 미만이면 변형 답이 같아도 정답 유지를 확인할 수 없어
`inconclusive`다. 근거가 훼손된 변형은 `abstained=true`, 빈 근거와 보류 이유를 가져야 한다.
두 상태를 하나의 정답 유지율로 합치지 않는다.

같은 날 NIM 실제 응답 5건은 모두 정해 둔 JSON 모양을 지켰다. API 호출 오류도 없었고 요청한
모델과 다른 모델이 응답한 경우도 없었다. 원본 답은 필요 이상으로 주변 값을 나열해 점수
`0.139`로 실패했다. 회전·JPEG 답은 원본과 같았지만 원본 품질 때문에 `inconclusive`였고,
잘림·가림은 둘 다 안전하게 답변을
보류해 `passed`였다. 따라서 결과는 통과 2, 실패 1, 판정 불가 2, 변형 무효 0이다.

## 6. 수업 중 NIM 한 문제를 실제로 호출해 보기

전체 PromptOptimizer는 수업 중 다시 실행하지 않는다. OpenCQA 이미지를 외부 API로 보내도
되는지, 사용할 모델과 가격이 맞는지, 남은 요청 수가 충분한지 확인한 경우에만 튜터가 884번
문제를 실행한다. 원본과 변형 4개를 각각 보내므로 문제는 한 개지만 NIM 요청은 최대 5회다.
전체 명령과 중단 조건은 Week 4 튜터 runbook에만 있다.

대표 실행이 끝나면 다음만 확인한다.

1. `record_count=5`, `target_count=5`인가?
2. `observed_status=complete`인가?
3. 실제 처리 모델이 요청 모델과 같은가?
4. API 오류와 구조화 답의 품질 실패를 구분했는가?
5. 수업 전에 저장한 답과 다르다면 “같은 조건에서도 답이 달라짐”이라고 기록했는가?

이 실행은 개발 문제 한 개를 다시 관찰하는 활동이다. 이 한 문제의 결과로 새 지시문을
고르거나 다른 이미지에서도 잘 작동한다고 말하지 않는다. 실행 승인이 없거나 API 서비스가
중단되면 `not_run` 또는 `partial`로 기록한다.

## 7. 제출

다음 세 경로를 보존한다.

1. `$WEEK4_STUDENT_DIR/variants/variant-review.csv`: 직접 판정한 네 행
2. `$WEEK4_REPORT_DIR/evaluation.json`: 튜터 저장 응답을 현재 채점기로 계산한 결과
3. `local-data/learning-progress.md`: 데이터 분할, 선택 이유와 주장할 수 없는 범위

학습 기록에는 다음 문장을 본인의 결과에 맞게 완성한다.

```text
개발 문제 18개를 참고해 바꾼 지시문을 검증 문제 6개에서 비교한 결과 ______을 선택했다.
질문에 필요한 수치가 남은 이미지에는 ______을 기대했다.
질문에 필요한 수치가 사라진 이미지에는 ______을 기대했다.
이 한 번의 수업 결과만으로 다른 문제나 실제 서비스의 ______은 말할 수 없다.
```

API key, `.env`, OpenCQA 원본과 튜터가 저장한 실제 실행 폴더는 제출하지 않는다.

## 완료 기준

- development·validation·공개 test의 역할을 설명했다.
- 현재 `week-03-cases.jsonl`과 저장 최적화 결과의 SHA-256이 같은 입력을 가리키는지 확인했다.
- validation 평균이 높지 않으면 기준선을 유지하는 코드를 확인했다.
- 기준과 후보 지시문의 실제 변경 문장을 설명했다.
- 점수가 오른 사례와 떨어진 사례에서 모델 답·점수·감점 이유를 같은 `sample_id`로 연결했다.
- 원본과 변형 네 개를 직접 보고 근거 보존·훼손을 판정했다.
- 저장 VLM 응답 5개를 다시 채점하고 실패 이유를 한 사례에서 연결했다.
- 잘못 만든 이미지(`invalid_variant`), 모델 답 실패(`fail`), 원본 답 또는 API 문제로 판단할
  수 없는 경우(`inconclusive`)를 구분했다.
- 수업 중 실제 호출 한 사례의 결과를 다른 문제나 실제 서비스에서도 같을 것이라고 말하지 않았다.
