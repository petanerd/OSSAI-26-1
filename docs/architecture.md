# 코드 구조

각 주차 문서에서는 필요한 `scripts/` 명령과 실행 주체를 구분한다. 아래 표에는 핵심 산출물을
만드는 주요 명령만 정리했다. 모든 명령은 `src/verifiable_ai_workflow/`의 공통 구현을 호출하며,
별도 평가 엔진은 두지 않는다.

## Week 1–6 주요 실행 파일

| 순서 | 실행 파일 | 하는 일 | 주요 결과 |
| ---: | --- | --- | --- |
| 1 | `prepare_documents.py` | PDF를 페이지 이미지로 준비 | 문서별 `manifest.json`, JPEG |
| 2 | `prepare_cases.py` | 사람이 편집하는 YAML을 실행용 JSONL로 변환 | `cases.jsonl` |
| 3 | `inspect_inputs.py` | 문서·질문·이미지 제한 검사 | `eda.json` |
| 4 | `inspect_deterministic_scoring_case.py` | 저장 응답 한 건의 채점 과정 확인 | 터미널 JSON |
| 5 | `preflight_nvidia.py` | 현재 설정 모델이 NVIDIA 목록에 있는지 확인 | 사용 가능 여부 |
| 6 | `run_nvidia_nim.py` | 튜터 baseline 또는 학습자 Week 2 prompt의 NIM 실제 호출·즉시 채점 | 원응답·점수·요약 |
| 7 | `evaluate_workflow.py` | 저장 응답 재실행과 고정 규칙·DeepEval 채점 | 원응답·사례별 점수·요약 |
| 8 | `evaluate_failures.py` | 의도적으로 깨진 네 응답 채점 | 실패 주입 결과 |
| 9 | `compare_gemma_prompts.py` | 같은 release Gemma baseline과 저장·개인 지시문 결과 비교 | 사례별 변화·계보 검사 |
| 10 | `compare_live_provider_routes.py` | Gemma와 Gemini 실제 비교 | 호출 경로별 결과·비교 |
| 11 | `rescore_provider_comparison.py` | 저장 원응답을 현재 채점기로 재계산 | 원본과 분리된 파생 비교 |
| 12 | `rehearse_provider_faults.py` | 저장된 API 장애 상황 확인 | 장애 상황 결과 |
| 13 | `prepare_opencqa.py` | OpenCQA 질문·사람 기대 답과 검토용 JPEG 30개 준비 | `week-03-cases.jsonl`, 이미지 |
| 14 | `run_open_cqa_candidates.py` | 같은 NIM Gemma에 baseline·improved prompt를 적용해 개인 후보 30쌍 생성 | 후보 호출·결과·요약, prompt snapshot |
| 15 | `inspect_judge_pair.py` | 개인 후보 한 쌍을 출처·기대 답 없이 확인하고 사람 사전 label 검증 | 터미널 출력 |
| 16 | `run_open_cqa_judge.py` | Gemini 3.5 Flash Lite로 개인 30쌍 또는 대표 1쌍을 두 trial·두 순서로 판단 | Judge 호출·60 trial·요약 |
| 17 | `compare_open_cqa_judge.py` | Judge 판단을 baseline·improved 출처, 잠근 사람 label과 연결하고 충돌 계산 | 승·무승부·review·순서·반복 비교 |
| 18 | `prepare_week_04_lab.py` | 4주차 입력·저장 결과를 확인하고 개인 폴더 준비 | 준비 상태와 개인 경로 |
| 19 | `inspect_week_04_prompt_results.py` | 바뀐 지시문·검증 점수·선택 이유를 쉬운 문장으로 표시 | 터미널 수업 설명 |
| 20 | `check_week_04_api_keys.py` | 두 API key가 있는지만 값 노출 없이 확인 | `present / missing` |
| 21 | `optimize_open_cqa_prompt.py` | 개발 문제의 실패 답으로 새 지시문을 만들고 검증 문제에서 처음 지시문과 비교 | 역할별 호출, 후보·선택 지시문, 검증 결과 |
| 22 | `generate_image_variants.py` | OpenCQA 첫 차트의 이미지 변형 생성 | 변형 이미지·사람 검토표 |
| 23 | `run_image_robustness.py` | 선택 지시문으로 원본 1개와 변형 4개 실행 | 구조화 답·호출 요약 |
| 24 | `evaluate_image_robustness.py` | 근거가 남았는지에 따라 이미지 답을 서로 다른 규칙으로 판정 | 이미지별 결과·검증 manifest |
| 25 | `inspect_agent_case.py` | Week 4 OpenCQA `884` 구조화 답을 받는 합성 agent 상황의 model 응답·도구·상태 확인 | 상류 답·실행 나무·결과의 터미널 JSON |
| 26 | `run_agent_cases.py` | 저장한 상류 답 1건과 model turn 11개로 여섯 합성 상황 실행; 필요하면 같은 단계를 로컬 Phoenix에 표시 | `test_only` 실행 나무·변경 기록·상태·일곱 지표 |
| 27 | `run_agent_live.py` | Week 4 선택·견고성·품질 파일의 identity·hash를 검증한 뒤 OpenCQA `884` 원본 답, 실제 NIM turn과 격리된 도구 연습장을 연결 | 상류 품질·agent 안전·모니터링 누적 상태, 응답 수신증·실행 나무·필수 Phoenix trace ID |
| 28 | `combine_weekly_results.py` | weekly의 이미지 품질·견고성 5건과 agent 6건을 누적 AND 판정으로 결합 | `combined/calls.jsonl`, `combined/summary.json` |
| 29 | `append_evaluation_history.py` | 현재 nightly 또는 weekly 요약을 검증해 append-only 이력에 추가 | `history.jsonl` |
| 30 | `record_release_decision.py` | 자동 상태와 사람 감사를 분리해 출시 결정을 기록 | 사람의 `SHIP / HOLD / ROLLBACK / INVALID-RUN` JSONL |
| 31 | `prepare_week6_inputs.py` | 공개 수업 저장소 Release에서 받은 입력 묶음의 SHA-256·17파일·안전한 경로 검사 후 추출 | checkout 안의 승인된 입력 |
| 32 | `export_phoenix_db.py` | 실행 중 Phoenix DB를 SQLite 백업 기능으로 복사하고 검사 | `phoenix/phoenix.db` |

`inspect_*.py`는 사람 판단 전에 후보의 prompt 출처·기대 답·Judge 결과를 숨긴다. 각 학습자는
Week 2 자기 prompt 40건과 Week 3 NIM 답 60개·Gemini Judge 30쌍을 실행한다. 강의자의 별도
시연은 Week 2 `r01` 한 건과 Week 3 대표 한 쌍이 최대다. Google 전송 범위는 2026-08-17에
승인됐지만, 실행 당일 현재 프로젝트의 Free Tier·model·quota·가격·데이터 이용 조건을 먼저
확인한다. 확인하지 못하면 `not_run`으로 남긴다. 실제 실행의 식별값·비용·오류는 결과 파일에
기록하고, 첫 개념 설명에서는 다루지 않는다.

Judge 설정은 공개 한도 15 RPM·입력 250,000 TPM·500 RPD보다 낮은 15 RPM·입력 75,000 TPM·
출력 7,500 TPM과 한 full run당 최대 240요청을 적용한다. 프로젝트의 하루 누적 요청은 추적하지
않으므로, 실행 전 당일 잔여 RPD가 240건 이상인지 확인한다. Free Tier token 단가는 0달러이며
비용 안전장치는 0.01달러다. 120~240회 요청의 pacing에는 약 8~16분이 걸리고 API 응답 시간이
더해진다. Free Tier로 보낸 자료가 제품 개선에 사용될 수 있다는 조건도 확인한다. 승인은 실행
성공 기록이 아니므로 새 결과의 완결 검사는 따로 통과해야 한다.

## Week 2–6 개인 결과 위치

| 주차 | 작성 입력 | 개인 실행 결과 | 비교·해석 |
| --- | --- | --- | --- |
| Week 2 | `local-data/week-02-students/<alias>/prompt.md` | `reports/week-02-gemma-baseline/runs/`의 고유 폴더 | `reports/week-02/students/<alias>/` 비교 JSON |
| Week 3 | `local-data/week-03-student-judges/<alias>/human-label.yaml` | `reports/week-03/student-full/<alias-시각>/candidates/`의 NIM 후보, `judge/`의 Gemini 판단·비교 | `local-data/week-03-student-judges/<alias>/interpretation.md` |
| Week 4 | `local-data/week-04-students/<alias>/variants/variant-review.csv` | `reports/week-04/student-full/<alias-시각>/optimization/`의 지시문 결과, `robustness/`의 이미지 응답·평가 | `local-data/learning-progress.md`의 실행 상태·지시문 선택 결과·실패 원인 |
| Week 5 | 별도 작성 입력 없음 | 잠근 Week 4 원본 품질, 저장 turn 6사례 회귀검사와 같은 clean commit의 실제 NIM 6사례·Phoenix 실행 | 세 구성의 누적 상태, trace 6개·JSONL 연결과 `local-data/week-05-students/<alias>/human-decision.md` |
| Week 6 | 학생의 공개 fork PR, 강사가 관리하는 수업 저장소의 승인된 Release 입력·Actions secret과 variables | 배정된 GitHub 표준 Ubuntu nightly·weekly의 실행 번호·JSONL·요약·Phoenix DB 사본 | Mac·Windows에서 결과 확인, `local-data/week-06-students/<alias>/human-decision.md` |

저장된 Week 2 개선·provider 결과는 설명 예시와 실패 fallback으로만 쓴다. 과거 OpenCQA
`abstractive_answer / extractive_answer` 후보·NIM Judge·Codex 합성 기준 결과는 legacy이며,
새 Week 3 입력이나 fallback이 아니다. 개인 실행이 `partial / not_run`이어도 완료로 바꾸지
않는다. 전체 명령은 [Week 2 실습](week-02-lab.md), [Week 3 실습](week-03-lab.md),
[Week 4 실습](week-04-lab.md), [Week 5 실습](week-05-lab.md),
[Week 6 실습](week-06-lab.md)에 둔다.

Week 5는 저장한 OpenCQA `884` 상류 답과 model turn 11개로 합성 6상황을 먼저
회귀검사한다. 이어 같은 clean commit에서 `--profile week5`로 6상황 전체를 실제
NIM과 로컬 Phoenix에서 실행하고, 서로 다른 trace ID 6개를 JSONL 결과와 연결한다.
전체 결과에 포함된 `W5-06`의 3 model·2 tool·1 ticket 흐름을 분석한다. Week 4 원본 품질,
Agent 안전과 모니터링 완결성을 AND로 판정한다.

## 내부 코드

```text
src/verifiable_ai_workflow/
├── config/          YAML 설정과 .env 읽기
├── schemas/         질문·모델 답·평가 결과의 출력 형식(schema)
├── preprocessing/   PDF 페이지 이미지 준비
├── data/            수업 데이터 읽기와 JSONL 생성
├── providers/       LiteLLM 실제 호출과 저장 응답 제공자(provider)
├── workflow/        질문·페이지 이미지·모델 호출 연결
├── evaluation/      고정 규칙 점수 계산과 DeepEval 저장
├── agent_lab.py     합성 사례·저장 turn·DeepEval·로컬 Phoenix 연결
├── open_cqa_candidates.py  Gemma 후보 생성·익명 배치·후보 세트 hash
├── prompt_optimization.py  개발·검증 분할, 점수 계산, 지시문 선택
├── image_robustness.py     이미지 변형, 사람 판정표, 결과 계산
├── release_monitoring.py   Week 6 결과 결합·이력·사람 결정 계약
├── week4_materials.py      튜터가 지정한 4주차 공통 저장 결과 경로 읽기
├── course_live.py          주차별 LiteLLM 예산·모델 설정 연결
├── judge_*.py      Gemini Judge 호출, 지표와 순서·반복 충돌 계산
├── tools/           계산기·권한 조회·중복 방지 티켓을 실행하는 격리된 도구 연습장
└── workflow/agent_runner.py  model 응답과 도구 실행 연결
```

문서·이미지 답변 작업 모델에는 질문·지시문(prompt)·페이지 JPEG를 보낸다.
OpenCQA 사람이 쓴 기대 답은 보내지 않는다. Judge 모델에는 질문·페이지 JPEG·기대 답·
익명 Gemma 후보 A/B와 고정 rubric을 보낸다.
PDF 추출 문장은 원본·라벨을 점검할 때만 쓰며, 모델 입력이나 채점에는 넣지 않는다.

Week 4에서 NIM Gemma에는 JPEG·질문·지시문을 보낸다. Gemini에는 JPEG와 사람의 이미지
검토표를 보내지 않는다. 대신 지시문·질문·기대 답·NIM 출력·고정 점수와 이유를 보낸다.
`calls.jsonl`에서는 NIM 호출을 `provider_role=target`, Gemini 호출을
`provider_role=optimizer`로 구분한다.

Gemini가 처음 지시문과 같은 문장을 제안하면, NIM을 다시 호출해 생긴 점수 차이를 개선으로
세지 않는다. 원본 답이 기준에 못 미치면 회전·압축 이미지의 답 유지 여부는
`inconclusive`로 둔다. 잘림·가림 이미지에서 안전하게 답변을 보류했는지는 별도로 판정한다.

Week 5의 업무 입력은 Week 4가 선택한 지시문으로 OpenCQA `884` 원본
이미지에 답한 `StructuredAnswer` 1건이다. `AgentUpstreamContext`가 이 답과
`sample_id=884`, `family_id=opencqa-val-884`, source revision·license, 선택 prompt·
선택 summary·source summary·responses·canonical output hash를 한 계약으로 묶는다.
여기에 잠근 `evaluation.json`과 `evaluation-manifest.json`을 로컬 입력으로 더해 원본
품질 상태, evaluation·responses SHA-256, source Git SHA와 schema SHA-256을 확인한다.
두 품질 파일 자체의 SHA-256도 실행 결과에 남긴다.
다만 Week 5의 마지막 답 형식은 도구 결과에 맞는 `AgentFinal`이다.

Week 4 선택 지시문의 **본문**은 Week 5 agent system prompt가 아니다.
OpenCQA 이미지에 답할 때만 Week 4 지시문을 쓰고, agent에는 별도
`prompts/week-05-agent.md`를 사용한다. Week 4 지시문 파일은 hash로 계보를
고정할 뿐이다. GEPA는 Week 4의 지시문 후보 생성·선택 방법이지 Week 5 판정기가
아니다. Week 5는 `tool_contract`, `authorization_safety`, `idempotency_safety`,
`final_answer`, `tool_budget`, `workflow_lineage`, `task_success` 일곱 지표를 Python
고정 규칙으로 계산한다. DeepEval은 그 지표와 이유를 저장한다.

조회 도구는 요청 인자뿐 아니라 변경 기록의 성공 여부·반환 record와 필드·빈 값 여부도
검사한다. 조회가 실패했는데 마지막 문장만 맞는 경우는 실패다. 마지막 답의 숫자·작업 번호는
완전한 값으로 확인하므로 `186`을 `86`으로, `TICKET-00010`을 `TICKET-0001`로 인정하지 않는다.
이 규칙은 답 전체의 의미나 `25%`와 `25%p`의 차이까지 판단하지 않는다. 사람 검토는 계속 필요하다.

여기서 견고성 `summary.json`의 `status=pass`와 agent의 `workflow_lineage` 통과는
응답 5건이 완결됐고 `original`을 `StructuredAnswer`로 읽어 같은 hash로 연결했다는
파일·구조 상태다. 별도 `evaluation.json`에서 `original` 품질은 점수 0.139,
`status=failed`다. Week 5의 일곱 지표는 주어진 입력을 받은 downstream agent의
계보·도구 안전·최종 상태를 판정한다. Week 5 전체 상태는
`상류 답 품질 ∧ agent 안전 ∧ monitoring 완결성`으로 누적 판정한다. 따라서 실제 agent가
6/6이고 Phoenix trace가 6개여도 현재 `original=0.139`, `failed`인 상류 품질 때문에
`status=fail`이며 사람의 결정은 `HOLD`다. 2026-08-31 live에서는 trace 6개가 완결됐지만
`W5-05`의 보류 이유가 요구 사실을 빠뜨려 agent도 5/6으로 실패했다. `workflow_lineage`와
source summary 통과만으로 상류 답 품질을 통과시킬 수 없다.

Week 5의 `AgentTurn`은 `turn_type`으로 구분한 Pydantic 판별 합집합이다. `tool`이면
`tool_call`이, `final`이면 중첩된 `AgentFinal`이 필수다. `AgentFinal`은 일반 답과 보류 답 모두
`answer`·`abstained`·`abstention_reason`을 명시하게 한다. 이 조건은 로컬 validator뿐 아니라
NIM에 전달하는 JSON Schema에도 나타나므로 `final + answer=null`을 허용하지 않는다.

각 사례는 권한 범위, 호출 상한과 고장 번호를 실행 결과에 남긴다. 격리된 도구 연습장은
시도마다 변경 기록(`ledger`)을 한 줄씩 덧붙이고, 실행 나무와 분리된 최종 상태도 저장한다.
개인정보 보류 사례는 보류 여부뿐 아니라 권한 밖 field를 이유로 밝혔는지도 검사한다.
사례 도중 모델 요청 실패는 `partial-runs.jsonl`에 도구 기록·최종 상태·오류·trace ID를 별도
저장하며 완료 건수와 채점에서 제외한다. Week 6 DB 백업의 자동 도착 검사는 완료된
`runs.jsonl`만 대상으로 하므로 실패 trace의 DB 도착 여부는 부분 기록의 ID로 직접 확인한다.

Week 5의 Phoenix 연동은 `agent_runner.py`의 실제 model·tool 실행 지점에 수동으로 둔
`AGENT`, `LLM`, `TOOL` 단계 세 종류다. 실제 실행은 로컬 Phoenix 연결을 필수로 한다.
각 단계는 안전한 JSON Input·Output, 실제 OTel Status, 요청·응답·후속조치 event를 남긴다.
LLM 단계는 실제 처리 모델·요청 번호·token·지연 시간을, TOOL 단계는 권한 상태·side effect·
재실행 여부를 함께 남긴다. Prompt, 원응답, 도구 인자와 개인정보는 넣지 않는다. JSONL이
평가 정본이며 Phoenix는 호출 흐름과 다음 조치를 찾는 화면이다.

실제 실행을 마치면 서버에서 해당 trace를 다시 읽는다. 사례별 AGENT 1개와 실행한 모든
LLM·TOOL 단계의 수, 부모 연결, 사례·실행 ID가 맞아야 저장 확인을 통과한다.
`phoenix_allocated_trace_count`는 로컬에서 발급한 ID 수이고 `phoenix_trace_count`는 이
저장 확인을 통과한 사례 수다. `phoenix_stored_trace_ids`에 그 ID를 남긴다. 전송 실패·조회
실패·단계 누락은 `trace_complete=false`, 모니터링 `inconclusive`이며 이력 작성 전에 반영된다.
ID 발급이나 전송 함수 종료만으로 저장 성공을 인정하지 않는다.
DB 백업은 `runs.jsonl`이 손상돼도 정상 사본을 보존한 뒤 오류로 종료한다. 보존과 평가 통과는 다르다.

### Week 5 데이터와 결과 파일

`data/agent/week-05-manifest.yaml`은 `week-05-agent-cases-v2` 합성 상황 6건·한
family·고정 회귀용이며 일반화가 허용되지 않는다고 선언한다. 고정 manifest의
`upstream_reference`는 OpenCQA `884`, `opencqa-val-884`, source revision·license만
유지한다. 실행별 선택·응답·출력 hash는 각 실제 실행의 `summary.json`에 남긴다.

`week-05-cases.yaml`은 사례 계약, `week-05-lookup.yaml`은 `opencqa-884`·`staff-01`
합성 record 2건이다. `data/recorded/week-05-upstream.json`은 OpenCQA `884`
원본 구조화 답과 hash 1건의 offline snapshot이고, `week-05-agent-turns.jsonl`은
6행·11 turn의 정본이다. 이 두 recorded 파일로 만든 결과는 `test_only`다. 실제 실행은
Week 4의 선택 summary·selected prompt·견고성 summary·responses와 잠근
`evaluation.json`·`evaluation-manifest.json`을 검증한 뒤 `original` 구조화 답을 사용한다.
두 품질 파일은 로컬 판정 입력이며 NVIDIA로 보내지 않는다.

실제 실행은 provider 응답을 잃지 않도록 두 단계로 기록한다.

| 파일 | 기록 시점과 의미 |
| --- | --- |
| `response-receipts.jsonl` | provider 응답 수신 즉시 원응답·model·usage를 먼저 보존 |
| `calls.jsonl` | usage·예산·actual model·attempt trace 확인 뒤의 정산 완료 또는 오류 상태 |
| `runs.jsonl` | 구조화 turn, tool trace, append-only ledger, initial/final state |
| `scores.jsonl` | 사례별 일곱 고정 지표와 이유 |
| `summary.json` | 상류 sample·family·계보 및 품질 파일 hash, 코드·설정·각 결과 파일 hash, 상류 품질·agent 안전·monitoring 완결 상태, 전체 `status`, `metric_passed`, 누적 예산 |

offline 실행은 실제 provider가 없으므로 앞의 두 provider JSONL을 만들지 않는다. 화면의
trace ID는 JSONL 정본을 대체하지 않으며 실제 실행에서는 누락되면 완료로 판정하지 않는다.
Week 5 완료 실행은 `profile=week5`, 사례 6건, model 요청·attempt 상한 11/11, 서로 다른
Phoenix trace 6개를 요구한다. 입력 220,000 token·출력 5,500 token·0.01달러·1,800초와
재시도 0회가 상한이다. 품질 파일이나 manifest hash, JSONL 또는 trace가 빠지면 전체 통과로
추론하지 않고 판정 불가 상태로 남긴다.

## 한 사례의 실제 흐름

```text
평가 사례
→ 문서의 페이지 JPEG 읽기
→ 지시문 + 질문 + 이미지 구성
→ LiteLLM을 통해 작업 모델 호출
→ 원응답 저장
→ Pydantic 출력 형식 검사
→ 고정 규칙 채점
→ DeepEval 결과 저장
```

Week 3에서는 이 흐름을 다음처럼 확장한다.

```text
같은 OpenCQA 입력
→ NIM Gemma baseline·improved 답 생성
→ 출처를 숨긴 A/B pair와 candidate-set SHA-256 저장
→ 사람 label과 파일 SHA-256 잠금
→ Gemini 3.5 Flash Lite에 이미지·질문·기대 답·A/B 전달
→ 두 trial의 A/B·B/A 결과와 baseline·improved 승패 계산
```

Week 5의 agent 사례는 다음 흐름을 따른다.

```text
Week 4 선택 summary·selected prompt·견고성 summary·responses hash 검증
→ 잠근 evaluation.json·evaluation-manifest.json과 quality 관련 hash 검증
→ OpenCQA 884 original StructuredAnswer와 canonical output hash를 AgentUpstreamContext로 결합
→ 별도 prompts/week-05-agent.md + 합성 후속 상황 + 권한·호출 상한·fault_seed
→ 저장 응답 또는 NIM이 AgentTurn 한 개 제안
→ 판별 JSON Schema와 Pydantic 검사
→ runner가 로컬 sandbox를 실행하고 결과를 다음 turn에 전달
→ 실행 나무·append-only ledger·최종 상태 저장
→ 계보·도구·권한·중복 방지·답·호출 상한을 AND로 판정
→ DeepEval에 같은 일곱 지표와 이유 저장
→ 상류 답 품질 ∧ agent 안전 ∧ monitoring 완결성으로 Week 5 전체 상태 판정
```

채점기의 필수 지표와 진단 지표는
[수업 도구·채점기·용어](terms-tools-and-scoring.md#고정-규칙-채점기와-평가지표)에 있다.

## Week 6까지 유지하는 공통 기능

다음 코드는 Week 1의 핵심 개념은 아니지만, 실제 호출 결과를 Week 6까지 비교하는 데 필요하므로
유지한다.

| 파일 | 기능 명세 | 사용하는 시점 |
| --- | --- | --- |
| `live_execution.py` | 요청·토큰·비용·시간 상한을 호출 전에 검사하고 중단 시 누적값을 보존한다. 같은 실행을 동시에 쓰지 않게 잠그고 JSON을 원자적으로 저장한다. | Week 1–6 실제 호출 |
| `model_identity.py` | 요청 모델과 API가 반환한 실제 처리 모델(actual model)이 같은지 확인한다. | Week 1–6 실제 호출 |
| `comparison.py` | 두 실행의 데이터·지시문·출력 형식·채점 조건이 같은지 확인하고 사례별 변화를 계산한다. | Week 2 비교 |
| `prompt_comparison.py` | 같은 모델에서 지시문만 다른 두 전체 실행을 비교한다. | Week 2 |
| `live_provider_comparison.py` | 서로 다른 두 API 제공자를 같은 입력과 상한으로 실행한다. | Week 2 |
| `open_cqa_candidates.py` | 같은 작업 모델의 baseline·improved 답을 만들고 출처를 가린 A/B와 candidate-set SHA-256으로 묶는다. | Week 3 |
| `judge_model.py` | Gemini 3.5 Flash Lite 실제 호출을 DeepEval Judge 인터페이스에 연결한다. | Week 3 |
| `judge_metrics.py` | 이미지·질문·기대 답·Gemma 후보를 과정의 고정 4단계 기준으로 비교한다. | Week 3 |
| `judge_comparison.py` | 잠근 사람 label·후보 출처·Judge 결과를 연결해 baseline·improved 승패와 순서·반복 충돌을 계산한다. | Week 3 |
| `course_live.py` | Week 4–6 실제 호출이 기존 LiteLLM 예산·모델 검사를 재사용하게 한다. | Week 4–6 |
| `prompt_optimization.py` | 개발 문제 18개로 지시문 후보를 만들고 검증 문제 6개로 처음·후보 지시문 중 하나를 고른다. 공개 test 6개는 이 과정에 쓰지 않는다. | Week 4 |
| `image_robustness.py` | 원본·변형 파일의 SHA-256과 사람 판정표를 확인하고 각 이미지의 결과를 계산한다. | Week 4 |
| `agent_lab.py`, `agent_runner.py` | Week 4 original `StructuredAnswer`와 Week 5 전용 prompt·상황을 결합한 뒤 agent 아래 model·tool 단계를 연결하고 실행 나무·변경 기록·최종 상태를 남긴다. | Week 5–6 |
| `release_monitoring.py` | Week 6의 이미지 5건·agent 6건 결과를 AND로 결합하고 현재 실행 이력과 사람 결정을 검증한다. | Week 6 |

이 기능들은 학습자가 직접 다시 구현하지 않는다. 해당 주차에서는 결과 파일을 보고 기능이
지켜졌는지만 확인한다.

## Week 6 자동 실행 경계

현재 브랜치에는 `.github/workflows/eval-nightly.yml`과 `eval-weekly.yml`이 구현돼 있다.
예약 실행을 별도로 켜면 nightly는 매일 03:00 KST에 `W5-06` 한 건을 최대 3 model turn으로
확인한다. Weekly는 매주 월요일 03:00 KST에 Week 4 선택 지시문으로 이미지 5건을 다시 답하고,
원본 답을 agent 6건에 넘겨 최대 11 model turn을 실행한다. 두 workflow 모두 수동
`workflow_dispatch`도 유지한다. 예약·수동 실행 모두 `main`,
`ENABLE_LIVE_EVALUATION=true`, `WEEK6_DATA_STORAGE_APPROVED=true`와 실행 직전 preflight를
요구한다. 수동 실행은 `confirm_live_evaluation=true`, 예약 실행은 별도의
`ENABLE_SCHEDULED_EVALUATION=true`가 필요하다. 공개 저장소라는 이유만으로 실행되지 않는다.

강사는 공개 수업 저장소 `petanerd/OSSAI-26-1`의 변수·NIM secret·Release를 관리한다.
학생의 공개 fork PR은 API 없이 검사하고, 실제 평가는 수업 저장소에서 배정한 실행으로 남긴다.
학생에게 쓰기 권한이 없으면 강사에게 요청해 수동 실행하고 학생 별칭·요청·실행 번호를 기록한다.
현재 승인 총량은 nightly·weekly 한 묶음의 생성 최대 19회·목록 GET 2회·관리용 비용 $0.03이다.
추가 실행이나 상한 확대는 정확한 합산 상한을 새로 승인받으며 자동 반복 승인으로 해석하지 않는다.

Weekly는 Week 5의 `상류 original 답 품질 ∧ agent 안전 ∧ monitoring 완결성`을
`상류 답 품질·견고성 5건 ∧ agent 안전 6건 ∧ monitoring 완결성`으로 다시 실행하고
확장한다. 세 구성은 평균내지 않는다. 하나라도 `fail`이면 전체가 `fail`이고, 누락이나
판정 불가는 `inconclusive`다. `workflow_lineage`와 source summary의 구조 통과만으로
상류 답 품질을 통과시킬 수 없다.

Weekly 결합기는 선택 지시문·선택 요약 artifact의 완료 상태, test 사용 상태, 출처와 provider
metadata, SHA-256과 입력 계보를 확인한다. `agent/summary.json`이
없으면 추측한 요약을 만들지 않고 결합을 실패시켜 이미 생긴 부분 결과를 보존한다. 이력은
현재 실행의 검증된 record만 append하며 직전 실행 대비 값이나 `latest_change`를 만들지 않는다.

2026-09-01의 nightly·weekly 결과는 Git에 포함되지 않은 강사 보존 기록이며 학생의 필수
입력이 아니다. API 없는 연습은 [Week 6 실습](week-06-lab.md)의 Git 고정 응답으로 진행한다.
각 학습자는 새 확인과 preflight 뒤 본인에게 배정된 nightly·weekly의 실제 결과를 분석한다.
저장 연습은 배정된 실제 실행을 대신하지 않으며 Week 5의 일회성 11회 승인은 반복 실행에
재사용하지 않는다. 2026-09-06 공개 저장 승인은 받았지만 이미지의 출처 고지와 묶음의
LICENSE·NOTICE 보완이 남아 있다. 입력 업로드와 이번 새 NIM 호출은 아직 하지 않았으며,
상세 조건은 [실제 API 실행 승인 범위](live-api-approval.md#week-6-반복-실행의-새-승인-범위와-현재-상태)를 따른다.

`answer_correct`는 기준 답 또는 명시한 `accepted_answers`와 정규화한 값이 완전히 일치할 때만
통과한다. `answer_similarity`와 `numeric_match`는 진단용으로만 저장한다.
