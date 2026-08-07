# Week 3 실습 — LLM Judge를 사람 판단과 맞춰 보기

## 이번 주에 답할 질문

설명형 답변 두 개 중 더 나은 답을 LLM Judge가 고를 때, 그 선택을 언제 자동 평가에 사용할
수 있는가?

Week 1–2의 숫자·필드·근거 페이지는 Python 규칙으로 확정할 수 있었다. OpenCQA의 설명은
올바른 표현이 여러 개라 문자열 일치만으로 판정하기 어렵다. 이번 주에는 사람 두 명의 판단,
같은 Judge의 반복 판단, 후보 순서를 바꾼 판단을 직접 비교한다.

## 1. OpenCQA 30쌍 준비

[OpenCQA 데이터 준비](open-cqa-data.md)를 따라 다음 파일을 만든다.

```text
local-data/opencqa/week-03-pairs.jsonl
local-data/opencqa/week-03-reviewer-1.csv
local-data/opencqa/week-03-reviewer-2.csv
```

한 사례를 먼저 읽는다.

```bash
uv run --locked python scripts/inspect_judge_pair.py --number 1
```

차트, 질문, 후보 A, 후보 B, 비교 기준 답 순서로 확인한다. article·summary·OCR은 작업 모델
입력에 사용하지 않는다.

## 2. 사람 두 명이 서로 보지 않고 평가

두 검토자는 각자 파일 하나만 받는다. `label`에는 다음 셋 중 하나만 쓴다.

- `candidate_a`: A가 업무상 더 정확하고 완결됨
- `tie`: 차이가 업무상 의미 없음
- `candidate_b`: B가 업무상 더 정확하고 완결됨

두 파일을 모두 작성한 뒤 합친다.

```bash
uv run --locked python scripts/combine_human_labels.py
```

두 사람이 다르게 고른 행은 `local-data/opencqa/week-03-human-labels.csv`의 `adjudicated`가
빈칸으로 남는다. 두 사람이 근거를 다시 확인하고 최종 선택을 입력한다. 빈칸이 하나라도
남으면 보정 명령은 실패한다.

## 3. Judge가 맡지 않는 항목 확인

다음 항목은 여전히 고정 규칙으로 검사한다.

| 항목 | 검사 방법 |
| --- | --- |
| pair ID 누락·중복 | Python 검사 |
| 허용하지 않은 winner 문자열 | Pydantic 검사 |
| 두 번의 trial 누락 | Python 검사 |
| 설명의 정확성·완결성 비교 | 사람 기준표와 LLM Judge |

모델 기반 채점기가 JSON 오류나 누락된 실행을 점수로 덮게 하지 않는다.

## 4. 한 쌍으로 실제 Judge 경로 확인

현재 모델 제공 상태와 비용을 확인한 뒤 실행한다. 이 명령은 한 쌍을 두 번 평가하고, 각
반복에서 A/B와 B/A 순서를 모두 사용하므로 최대 4회 호출한다.

```bash
uv run --locked python scripts/run_open_cqa_judge.py \
  --live-judge \
  --pair-limit 1 \
  --max-requests 4 \
  --max-input-tokens 32000 \
  --max-output-tokens 4000 \
  --max-cost-usd 0.04 \
  --max-wall-seconds 600 \
  --catalog-verified-on "$(date +%F)" \
  --output reports/week-03/probe
```

확인할 파일은 세 개뿐이다.

- `judge-results.jsonl`: 반복별 `winner_ab`, `winner_ba`
- `judge-calls.jsonl`: 실제 모델, 원응답, token, 시간, 오류
- `summary.json`: 실행 범위와 예산 사용량

## 5. 수업용 5쌍에서 변동 확인

```bash
uv run --locked python scripts/run_open_cqa_judge.py \
  --live-judge \
  --pair-limit 5 \
  --max-requests 20 \
  --max-input-tokens 160000 \
  --max-output-tokens 20000 \
  --max-cost-usd 0.20 \
  --max-wall-seconds 1800 \
  --catalog-verified-on "$(date +%F)" \
  --output reports/week-03/classroom-5
```

5쌍 결과를 사람 라벨과 비교한다.

```bash
uv run --locked python scripts/calibrate_open_cqa_judge.py \
  --judge-results reports/week-03/classroom-5/judge-results.jsonl \
  --pair-limit 5 \
  --output reports/week-03/classroom-5/calibration.json
```

5쌍은 학습용 표본이므로 결과가 좋아도 `recommended_use=diagnostic`이다.

## 6. 결과 읽기

- `order_conflict=true`: A/B와 B/A의 선택이 달라 사람이 다시 본다.
- `repetition_conflict=true`: 같은 조건의 두 반복이 달라 사람이 다시 본다.
- `judge_human_agreement`: 충돌 없이 사람의 최종 선택과 같았던 비율이다.
- `human_human_weighted_kappa`: 두 사람의 최초 판단이 얼마나 일관됐는지 본다.

충돌을 다수결이나 평균으로 숨기지 않는다. 하나라도 충돌한 pair의 Judge 결과는 `review`다.

## 7. 30쌍 보정 기준

30쌍 전체 실제 실행 결과가 있을 때만 `--pair-limit` 없이 보정한다.

```bash
uv run --locked python scripts/calibrate_open_cqa_judge.py \
  --judge-results reports/week-03/full-30/judge-results.jsonl \
  --output reports/week-03/full-30/calibration.json
```

다음을 모두 만족해야만 `blocking` 후보가 된다.

- OpenCQA 30쌍 전체
- 사람–사람 가중 kappa 0.6 이상
- Judge–사람 일치율 0.8 이상
- 반복 충돌과 순서 충돌 0건
- 변경사항이 없는 Git commit에서 끝난 `live_quality` 실행

하나라도 만족하지 않으면 `diagnostic`으로만 사용한다. 자동 승인 여부는 이 수치만으로
결정하지 않고, 불일치 사례를 사람이 읽고 최종 판단한다.

## 완료 확인

```bash
uv run --locked pytest tests/week3
uv run --locked ruff check .
```

다음을 설명할 수 있으면 완료다.

1. 왜 설명형 답은 고정 규칙만으로 평가하기 어려운가?
2. 왜 같은 Judge를 두 번 실행하고 A/B 순서도 바꾸는가?
3. 왜 5쌍 결과가 좋아도 자동 차단 기준으로 쓰지 않는가?
