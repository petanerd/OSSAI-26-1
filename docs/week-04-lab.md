# Week 4 실습 — 실패를 보고 지시문을 고친 뒤 다른 문제로 확인하기

## 이번 주에 배우는 것

Week 4는 모델의 실패 이유를 이용해 지시문(prompt)을 고치고, 별도 문제에서 실제 점수를
비교해 최종 지시문을 선택하는 주차다. 선택한 지시문은 원본과 변형 이미지 5개에도 적용한다.

```text
개발 문제 18개
→ NIM Gemma가 답 생성
→ Python이 점수와 실패 이유 계산
→ Gemini GEPA가 새 지시문 제안
→ 검증 문제 6개로 처음·새 지시문 비교
→ 점수가 높은 지시문 선택
→ 원본·변형 이미지 5개에서 답 유지와 답변 보류 확인
```

수업이 끝나면 다음을 설명할 수 있어야 한다.

1. NIM Gemma, Python 채점기와 Gemini GEPA가 각각 하는 일
2. 개발 문제와 검증 문제를 나누는 이유
3. 새 지시문의 문장과 모델 답이 어떻게 달라졌는지
4. 검증 문제 6개의 평균으로 최종 지시문을 고르는 방법
5. 이미지에 근거가 남았을 때와 사라졌을 때 기대하는 행동

## 사용하는 데이터와 역할

OpenCQA 30개를 다음처럼 사용한다.

| 구분 | 개수 | 이번 주 역할 |
| --- | ---: | --- |
| 개발(`development`) | 18 | 실패를 찾고 새 지시문을 만듦 |
| 검증(`validation`) | 6 | 처음 지시문과 새 지시문 중 하나를 선택 |
| 공개 test | 6 | 이후 최종 확인용으로 보존 |

지시문을 만드는 자료와 선택하는 자료를 나누면, 새 문장이 처음 본 개발 문제에만 맞는지
다른 검증 문제에서도 도움이 되는지 확인할 수 있다.

### 모델과 코드의 역할

| 역할 | 담당 | 입력과 결과 |
| --- | --- | --- |
| 답 생성 | NIM Gemma | 차트·질문·지시문을 읽고 `StructuredAnswer` 생성 |
| 고정 채점 | Python | 기준 답과 모델 답의 숫자·핵심 단어를 비교해 점수와 이유 생성 |
| 지시문 제안 | Gemini GEPA | 지시문·질문·기대 답·모델 답·점수·이유를 읽고 새 지시문 제안 |

Python 점수는 다음 식을 사용한다.

```text
0.7 × 숫자 F1 + 0.3 × 핵심 단어 F1
```

개별 문제는 0.8 이상이면 통과다. 최종 지시문은 검증 문제 6개의 평균이 더 높은 쪽으로
선택한다.

### 이미지 변화 두 가지

| 사람이 확인한 상태 | 쉬운 뜻 | 기대 행동 |
| --- | --- | --- |
| `preserved` | 질문에 필요한 수치와 비교 대상이 보임 | 원본과 같은 핵심 답과 근거 제시 |
| `destroyed` | 필요한 근거가 잘리거나 가려짐 | 답변 보류와 보류 이유 제시 |

## 1. 실습 준비

모든 명령은 이 저장소 최상위에서 실행한다. Python 3.12·Git·`uv`를 준비한다.
코드·설정·기록 양식은 Git에 있지만 OpenCQA 이미지와 수업 전 실제 응답은 Git에 없다.
먼저 아래 두 준비를 구분한다. 없는 자료를 다른 개인 폴더에 연결하거나 예시 결과로 채우지 않는다.

**1) OpenCQA 30개 준비.** 이미 같은 수업판의 `local-data/opencqa/`가 있다면 덮어쓰지 않고
다음 준비 검사에서 확인한다. 없는 새 수업 clone에서만 아래 명령을 실행한다. 공식 원본은
저장소 안의 Git 제외 폴더에 받는다. 내려받기 전에 강사와 원본·차트 이용 조건을 확인한다.
이 단계에는 모델 API 호출이 없다.

```bash
uv sync --locked --dev
(
  test ! -e local-data/opencqa && test ! -e local-data/opencqa-source || {
    printf '기존 입력 폴더가 있습니다. 삭제하거나 덮어쓰지 말고 준비 상태를 확인하세요.\n' >&2
    exit 1
  }
  mkdir -p local-data
  git clone https://github.com/vis-nlp/OpenCQA.git local-data/opencqa-source || exit 1
  git -C local-data/opencqa-source switch --detach 28db0fd26a12fd376f6c30b7feb8a4db32313424 || exit 1
  uv run --locked python scripts/prepare_opencqa.py --source-root local-data/opencqa-source
)
```

**2) 수업용 전체 저장 결과 받기.** 강사는 이용 조건·공개 저장 범위를 확인한 자료만
[이 저장소 Releases](https://github.com/petanerd/OSSAI-26-1/releases)로 공급하고 태그·파일명·
SHA-256·추출 위치를 안내한다. 학생은 그 해시를 확인한 뒤 기존 입력과 충돌하지 않게 다음
위치에 둔다. 현재 Week 4 전체 묶음의 공개 배포는 확인되지 않았으므로, 준비 완료 공지와
입력을 받기 전에는 아래 준비 명령과 저장 결과 분석을 `not_run`으로 남긴다.
Week 5·6용 17파일 묶음은 아래 전체 자료의 대체물이 아니며 그 저장 승인을 확대해 쓰지 않는다.

| 저장소 안의 위치 | 필요한 내용 |
| --- | --- |
| `local-data/opencqa/week-04-variants/` | `case.json`, `variants.jsonl`, `variant-review.csv`, 검토한 변형 이미지 4개 |
| `local-data/week-04-full-runs/optimization-4b53815/` | `candidate-prompt.md`, `selected-prompt.md`, `validation.jsonl`, `summary.json`, `calls.jsonl` |
| `local-data/week-04-full-runs/robustness-4b53815/` | `calls.jsonl`, `responses.jsonl`, `summary.json`, `evaluation.json`, `evaluation-manifest.json` |

이 경로는 `configs/week-04.yaml`과 준비 스크립트가 읽는다. 누락·해시 불일치를 지우려고
설정이나 원응답을 고치지 않는다. 입력을 모두 받은 뒤 `minsu`를 본인 별칭으로 바꿔 실행한다.

```bash
uv run --locked python scripts/prepare_week_04_lab.py --alias minsu
```

이 명령은 다음을 확인하고 개인 폴더를 준비한다.

- OpenCQA 30개와 이미지
- 개발 18개·검증 6개·공개 test 6개 분할
- 수업용 지시문 최적화 결과와 이미지 응답 5개
- 입력, 이미지, 지시문, 채점기의 SHA-256

Git SHA는 결과를 만든 코드 버전, SHA-256은 입력과 결과 파일의 내용 지문이다. 준비 화면에서
`4주차 실습 준비 완료`와 사용할 폴더를 확인한다. 기록지는 저장소의
[Week 4 기록 양식](templates/week-04-progress-template.md)을 `local-data/learning-progress.md`로
복사하며 기존 기록은 보존한다. 과거 저장 결과의 SHA를 본인 실제 실행의 SHA로 적지 않는다.

## 2. 개발 사례 2건으로 GEPA 과정 보기

외부 전송 범위, NVIDIA·Google 모델, 가격과 사용 한도를 확인한 뒤 다음 명령을 실행한다.

```bash
uv run --locked python scripts/optimize_open_cqa_prompt.py \
  --live-optimize \
  --demo-samples 2 \
  --max-requests 5 \
  --max-input-tokens 100000 \
  --max-output-tokens 2500 \
  --max-cost-usd 0.01 \
  --max-wall-seconds 900 \
  --catalog-verified-on "$(date +%F)" \
  --pricing-verified-on "$(date +%F)" \
  --optimizer-max-requests 2 \
  --optimizer-max-attempts 4 \
  --optimizer-max-input-tokens 20000 \
  --optimizer-max-output-tokens 8000 \
  --optimizer-max-cost-usd 0.01 \
  --optimizer-max-wall-seconds 900 \
  --optimizer-catalog-verified-on "$(date +%F)" \
  --optimizer-pricing-verified-on "$(date +%F)"
```

화면과 결과 폴더에서 다음 순서를 찾는다.

1. NIM Gemma가 처음 지시문으로 답을 만든다.
2. Python이 점수와 감점 이유를 붙인다.
3. Gemini가 새 지시문을 제안한다.
4. NIM Gemma가 새 지시문으로 다시 답한다.
5. `candidate_changed`에서 실제 문장 변화 여부를 확인한다.

이 실행은 후보 생성 과정을 보여 주는 `classroom_demo`다. 최종 선택은 다음 절의 개발 18개와
검증 6개 전체 결과에서 한다.

## 3. 전체 저장 결과에서 최종 지시문 선택 확인

튜터가 수업 전에 같은 release에서 만든 전체 결과를 연다.

```bash
uv run --locked python scripts/inspect_week_04_prompt_results.py
```

다음 항목을 순서대로 기록한다.

| 확인 항목 | 기록할 값 |
| --- | --- |
| 처음 지시문에서 발견한 실패 |  |
| 후보에서 바뀐 문장 |  |
| 점수가 오른 검증 문제와 이유 |  |
| 점수가 떨어진 검증 문제와 이유 |  |
| 처음 지시문 평균 |  |
| 후보 지시문 평균 |  |
| 최종 선택과 선택 이유 |  |

결과 파일의 역할은 다음과 같다.

| 파일 | 확인 내용 |
| --- | --- |
| `candidate-prompt.md` | Gemini가 제안한 지시문 |
| `validation.jsonl` | 검증 6개의 처음·후보 답, 점수와 이유 |
| `selected-prompt.md` | 검증 평균으로 선택한 지시문 |
| `summary.json` | 두 평균, 선택 이유, 모델, 실행·계보 상태 |
| `calls.jsonl` | 실제 요청, token, 시간과 오류 |

`validation.jsonl`에서 점수가 가장 오른 사례와 가장 떨어진 사례를 찾아 같은 `sample_id`의
질문, 기준 답, 처음 답, 후보 답과 감점 이유를 연결한다. 두 대표 사례로 변화 원인을 설명하고,
최종 선택은 검증 6개의 평균으로 확인한다.

## 4. 이미지 변형을 보고 상태 판정

`minsu`를 본인 별칭으로 바꿔 개인 이미지 변형을 만든다.

```bash
uv run --locked python scripts/generate_image_variants.py --student-alias minsu
```

`case.json`의 원본과 다음 네 파일을 연다.

- `rotate-2.png`: 원본을 2도 회전
- `jpeg-60.jpg`: JPEG 품질 60으로 압축
- `crop-left.png`: 왼쪽 40% 제거
- `occlude-answer.png`: 왼쪽 일부를 회색으로 가림

질문의 대상·기간·수치·비교 대상을 먼저 찾는다. 근거가 보이면 `preserved`, 근거가 사라졌으면
`destroyed`를 `variant-review.csv`의 `grounding_status`에 쓴다. 네 변형을 모두 직접 확인한다.

## 5. 저장된 이미지 답 다시 평가

다음 명령은 수업 전에 실제 NIM으로 만든 원본 1개와 변형 4개의 답을 현재 채점기로 평가한다.

```bash
uv run --locked python scripts/evaluate_image_robustness.py --student-alias minsu
```

다음 파일을 순서대로 읽는다.

| 파일 | 확인 내용 |
| --- | --- |
| `summary.json` | 응답 5개, 모델, 지시문과 실행 상태 |
| `responses.jsonl` | 원본·변형별 원응답과 구조화 답 |
| `evaluation.json` | `passed / failed / inconclusive / invalid_variant` |
| `evaluation-manifest.json` | 응답·이미지·검토표·채점기·schema SHA-256 |

`preserved`는 원본과 변형 점수 0.8 이상, 근거와 원본 핵심 숫자 유지를 확인한다.
`destroyed`는 `abstained=true`, 빈 근거와 보류 이유를 확인한다. 원본 답의 품질이 0.8
미만이면 `preserved` 변형의 정답 유지 판정은 `inconclusive`로 기록한다.

## 6. 개인 전체 API 실행

같은 release에서 본인의 API 키로 개발 18개·검증 6개 전체 최적화와 이미지 5개를 실행한다.

### 6-1. 실행 전 확인

다음 항목을 확인한다.

1. `git status --porcelain` 출력이 비어 있다.
2. OpenCQA 30개와 개인 이미지 변형 5개가 있다.
3. `variant-review.csv` 네 행을 판정했다.
4. NVIDIA와 Google의 전송 자료, 모델, 가격, 사용 한도와 데이터 이용 조건을 승인했다.
5. API key는 본인의 `.env` 안에서만 사용한다.

```bash
git status --porcelain
uv run --locked python scripts/check_week_04_api_keys.py
uv run --locked python scripts/preflight_nvidia.py \
  --config configs/nvidia-nim-gemma4.yaml
```

개인 한 명의 전체 상한은 다음과 같다.

| 역할 | 요청·attempt 상한 | token 상한 | 비용·시간 상한 |
| --- | --- | --- | --- |
| NIM 답 생성과 이미지 5개 | 50/50회 | 입력 1,000,000·출력 25,000 | $0.02·2시간 15분 |
| Gemini 지시문 제안 | 4/8회 | 입력 40,000·출력 16,000 | $0.01·2시간 |

준비 상태는 `complete / partial / not_run`으로 기록하고 필요한 보완 날짜를 정한다.

### 6-2. 개발 18개·검증 6개 전체 최적화

```bash
STUDENT_ALIAS=minsu
RUN_ID=$(date +%Y%m%d-%H%M%S)
STUDENT_RUN_DIR="reports/week-04/student-full/${STUDENT_ALIAS}-${RUN_ID}"
OPTIMIZATION_RUN_DIR="$STUDENT_RUN_DIR/optimization"
ROBUSTNESS_RUN_DIR="$STUDENT_RUN_DIR/robustness"
VARIANTS_DIR="local-data/week-04-students/$STUDENT_ALIAS/variants"
NIM_CATALOG_DATE=$(date +%F)
NIM_PRICING_DATE=$(date +%F)
GEMINI_MODEL_DATE=$(date +%F)
GEMINI_PRICING_DATE=$(date +%F)

uv run --locked python scripts/optimize_open_cqa_prompt.py \
  --live-optimize \
  --max-requests 45 \
  --max-input-tokens 900000 \
  --max-output-tokens 22500 \
  --max-cost-usd 0.01 \
  --max-wall-seconds 7200 \
  --catalog-verified-on "$NIM_CATALOG_DATE" \
  --pricing-verified-on "$NIM_PRICING_DATE" \
  --optimizer-max-requests 4 \
  --optimizer-max-attempts 8 \
  --optimizer-max-input-tokens 40000 \
  --optimizer-max-output-tokens 16000 \
  --optimizer-max-cost-usd 0.01 \
  --optimizer-max-wall-seconds 7200 \
  --optimizer-catalog-verified-on "$GEMINI_MODEL_DATE" \
  --optimizer-pricing-verified-on "$GEMINI_PRICING_DATE" \
  --output "$OPTIMIZATION_RUN_DIR"
```

중단된 폴더는 `partial` 증거로 보존하고 새 `RUN_ID`로 재실행한다. 결과를 읽는다.

```bash
uv run --locked python scripts/inspect_week_04_prompt_results.py \
  --optimization-dir "$OPTIMIZATION_RUN_DIR"
```

`optimization/summary.json`에서 `run_mode=full_evaluation`, `observed_status=complete`, 18/6/6
분할, 실제 처리 모델, 오류 수, `candidate_changed`, `selected`와 `selection_reason`을 확인한다.

### 6-3. 선택 지시문으로 이미지 5개 실행

```bash
uv run --locked python scripts/run_image_robustness.py \
  --live \
  --prompt "$OPTIMIZATION_RUN_DIR/selected-prompt.md" \
  --variants-dir "$VARIANTS_DIR" \
  --max-requests 5 \
  --max-input-tokens 100000 \
  --max-output-tokens 2500 \
  --max-cost-usd 0.01 \
  --max-wall-seconds 900 \
  --catalog-verified-on "$NIM_CATALOG_DATE" \
  --pricing-verified-on "$NIM_PRICING_DATE" \
  --output "$ROBUSTNESS_RUN_DIR"

uv run --locked python scripts/evaluate_image_robustness.py \
  --variants "$VARIANTS_DIR/variants.jsonl" \
  --reviews "$VARIANTS_DIR/variant-review.csv" \
  --case "$VARIANTS_DIR/case.json" \
  --responses "$ROBUSTNESS_RUN_DIR/responses.jsonl" \
  --output "$ROBUSTNESS_RUN_DIR/evaluation.json"
```

`robustness/summary.json`에서 `observed_status=complete`, `record_count=target_count=5`, 실제
처리 모델과 오류 수를 확인한다. 두 실행의 다음 계보도 비교한다.

- 같은 `git_sha`
- `selected_prompt_sha256`와 `prompt_sha256` 일치
- 같은 `artifact_sha256.week-03-cases.jsonl`

## 제출과 완료 기준

다음 결과를 보존한다.

1. `variant-review.csv`: 직접 판정한 네 이미지 상태
2. 수업용 `evaluation.json`: 저장 이미지 답의 재평가 결과
3. `local-data/learning-progress.md`: 지시문 변화, 검증 평균, 최종 선택과 해석 범위
4. `reports/week-04/student-full/`: 개인 전체 실행의 원응답·요약·평가

완료한 학습자는 다음을 확인한다.

- 개발 18개와 검증 6개의 역할을 설명했다.
- NIM Gemma, Python 채점기와 Gemini GEPA의 역할을 구분했다.
- 실제로 바뀐 지시문 문장과 점수가 오른·떨어진 검증 사례를 연결했다.
- 검증 6개 평균으로 선택한 지시문과 선택 이유를 기록했다.
- 이미지 변형 4개를 직접 보고 `preserved / destroyed`를 판정했다.
- 저장 이미지 답 5개의 상태와 실패 이유를 확인했다.
- 개인 전체 최적화와 이미지 5개 실행의 `complete / partial / not_run` 상태를 기록했다.
- `complete` 실행의 결과 파일과 세 계보 항목이 일치함을 확인했다.
