# Week 6 실습 — 정기 평가와 사람의 출시 결정

## 이번 주에 답할 질문

모델 품질·응답 시간·사용량이 달라졌을 때 자동 검사는 어디까지 판단하고, 사람은 어떤
근거로 출시 여부를 결정해야 하는가?

이번 주에는 새 평가 엔진을 만들지 않는다. 앞 주차의 실행 결과를 한 줄짜리 이력으로
모으고, 자동 판정 뒤에 사람의 결정을 기록한다.

## 1. 세 자동 실행의 역할 구분

`.github/workflows/`의 세 파일을 연다.

| 파일 | 실행 시점 | 실제 API | 확인 범위 |
| --- | --- | --- | --- |
| `eval-pr.yml` | pull request | 사용하지 않음 | Ruff, pytest, 저장 turn agent 6건 |
| `eval-nightly.yml` | 매일 또는 수동 | 사용 | AIHub 앞 3건 빠른 확인 |
| `eval-weekly.yml` | 매주 또는 수동 | 사용 | AIHub validation 8건 + 이미지 5건 |

PR에서는 비밀키와 외부 호출 없이 코드 오류만 빠르게 찾는다. 실제 모델 품질은
`live_quality` 결과인 nightly와 weekly에서만 판단한다.

## 2. PR 검사 로컬 재현

```bash
uv sync --locked --dev
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python scripts/run_agent_cases.py --output reports/pr-agent
```

`reports/pr-agent/scores.jsonl`은 저장된 model turn으로 만든 `test_only` 결과다. 실패하면 코드를
고쳐야 하지만, 통과했다고 현재 외부 모델 품질이 좋다고 주장하지 않는다.

## 3. nightly 3건 실행 흐름 읽기

`eval-nightly.yml`에서 다음 순서를 찾는다.

1. NVIDIA 모델 목록에서 설정 모델이 현재 존재하는지 확인한다.
2. `run_nvidia_nim.py --limit 3`으로 앞 세 사례만 호출한다.
3. `summary.json`과 `provider-responses.jsonl`을 모니터링 한 줄로 바꾼다.
4. 이전 이력에 새 줄을 추가하고 실행 결과로 보관한다.

로컬에서 같은 실행을 할 때는 먼저 모델 목록을 확인한다.

```bash
uv run --locked python scripts/preflight_nvidia.py \
  --config configs/nvidia-nim-gemma4.yaml
```

그다음 호출 상한을 고정해 3건을 실행한다.

```bash
uv run --locked python scripts/run_nvidia_nim.py \
  --config configs/nvidia-nim-gemma4.yaml \
  --live --limit 3 \
  --max-requests 3 --max-input-tokens 60000 --max-output-tokens 1500 \
  --max-retries 0 --max-cost-usd 0.01 --max-wall-seconds 900 \
  --catalog-verified-on "$(date +%F)"
```

명령 끝의 `run directory:` 뒤 경로가 이번 결과 폴더다. 그 경로의 `summary.json`에서 성공률을,
`provider-responses.jsonl`에서 사례별 시간·token·오류를 확인한다.

## 4. 모니터링 이력 한 줄 만들기

위 명령이 출력한 실제 결과 폴더를 `RUN_DIR`에 그대로 넣는다.

```bash
RUN_DIR=reports/week-02-gemma-improved/runs/방금-출력된-폴더명

uv run --locked python scripts/append_evaluation_history.py \
  --profile nightly \
  --summary "$RUN_DIR/summary.json" \
  --calls "$RUN_DIR/provider-responses.jsonl" \
  --history reports/evaluation-history.jsonl
```

`reports/evaluation-history.jsonl`의 한 줄에는 다음 값만 남긴다.

- 실행 시각, Git SHA, 실제 모델, 지시문 hash
- 성공률, p95 응답 시간
- 입력·출력 token, 추정 비용, 오류 수
- 자동 판정 `pass`, `fail`, `inconclusive`

3건이 모두 끝나지 않았으면 품질 실패가 아니라 `inconclusive`다. 직전 줄이 있으면 성공률,
응답 시간, token, 비용과 오류의 변화도 터미널에 표시된다.

## 5. weekly 13건의 구성 확인

`eval-weekly.yml`은 다음 두 결과를 합친다.

- AIHub `validation` 8건: Week 1 고정 규칙의 `task_success`
- OpenCQA 원본 1개와 이미지 변형 4개: Week 4의 근거 보존·안전한 보류 규칙

`scripts/combine_weekly_results.py`는 정확히 8건과 5건이 아니거나 두 결과의 Git SHA가 다르면
합치지 않는다. 서로 다른 코드 상태의 결과를 평균 내지 않기 위해서다.

## 6. 자동 판정 뒤 사람 결정 기록

자동 `pass`는 출시 명령이 아니다. 고위험 사례를 사람이 확인한 뒤 다음 네 결정 중 하나를
기록한다.

| 결정 | 사용 조건 |
| --- | --- |
| `SHIP` | 자동 `pass`이고 사람 감사가 끝남 |
| `HOLD` | 더 확인하거나 수정해야 함 |
| `ROLLBACK` | 이전 Git SHA로 되돌려야 함 |
| `INVALID-RUN` | 실행이 불완전해 `inconclusive`임 |

예를 들어 사람이 nightly 결과를 확인한 뒤 출시한다면 다음과 같이 기록한다.

```bash
uv run --locked python scripts/record_release_decision.py \
  --monitoring-record reports/evaluation-history.jsonl \
  --decision SHIP \
  --reviewer learner-01 \
  --reason "세 사례의 원응답과 근거 페이지 확인 완료" \
  --human-audit-complete \
  --output reports/release-decisions.jsonl
```

`SHIP`에서 사람 감사 표시가 없거나, `ROLLBACK`에서 `--rollback-git-sha`가 없으면 명령이
실패한다.

## 7. GitHub 정기 실행 전에 필요한 값

저장소 설정에는 다음 값이 있어야 한다.

- secret `NVIDIA_NIM_API_KEY`
- variable `LIVE_TASK_ENABLED=true`
- variable `COURSE_DATA_ROOT`: self-hosted runner에 준비한 AIHub·OpenCQA 상위 경로
- variable `MONITORING_ROOT`: nightly·weekly JSONL 이력을 누적할 쓰기 가능한 경로
- `live-evaluation` environment의 실행 승인

실제 데이터가 로컬에 있으므로 nightly와 weekly는 `ai-eval` label이 붙은 self-hosted runner에서만
실행한다. 데이터 경로·승인·키 중 하나라도 없으면 실제 호출을 시작하지 않는다.

Week 3 Judge는 30쌍 사람 평가와 반복·순서 교환 보정이 실제로 끝난 뒤에만 정기 검사 후보가
된다. 현재 저장소에는 완료된 보정 결과가 없으므로 Judge CI를 만들지 않는다.

## 완료 확인

```bash
uv run --locked pytest tests/week6
uv run --locked ruff check .
```

다음을 설명할 수 있으면 완료다.

1. 왜 PR 통과를 현재 모델의 품질 증거로 쓸 수 없는가?
2. 왜 nightly 미완료와 품질 실패를 구분하는가?
3. 왜 자동 `pass`만으로 `SHIP`할 수 없는가?
