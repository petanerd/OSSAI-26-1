# 검증 가능한 AI 작업 흐름(Workflow) 설계·평가 과정

이 교육용 프로젝트에서는 공개 문서와 차트를 읽는 멀티모달 작업 흐름(workflow) 하나를 6주
동안 발전시킨다. 현재 브랜치에는 Week 1부터 Week 6까지의 실습이 담겨 있다.

- Week 1: PDF를 페이지 이미지로 만든다. VLM을 호출해 구조화된 답을 받고 고정 규칙으로 채점한다.
- Week 2: 동일 release baseline을 기준으로 각 학습자가 자기 prompt 40건을 실행·비교한다.
  저장된 개선·provider 결과는 설명 예시와 실패 fallback으로 쓰고, 강의자는 `r01` 한 건까지만
  별도로 시연한다.
- Week 3: 각 학습자가 같은 NIM Gemma에 기준·개선 지시문을 적용해 OpenCQA 실제 답 30개씩을
  만든다. 두 답을 익명 A/B 30쌍으로 묶고 배정된 1쌍의 사람 판단을 먼저 잠근 뒤, Gemini
  3.5 Flash Lite Judge를 두 번·양방향으로 실행한다.
- Week 4: Prompt 최적화를 배운다. NIM Gemma가 개발 문제에 답하면 Gemini가 낮은 점수의
  원인을 읽고 지시문을 고쳐 쓴다. 검증 문제 6개에서 처음·새 지시문을 비교한 뒤 이미지
  변형을 평가한다. 수업 중에는 개발 사례 2건의 생성 과정을 실제로 먼저 보여 주고, 그다음
  수업 전에 저장한 전체 결과를 열어 지시문 선택과 품질을 판단한다. 수업 후에는 각 학습자가
  개인 폴더에서 전체 최적화와 이미지 5건을 실행한다.
- Week 5: Week 4가 선택한 지시문으로 만든 OpenCQA `884` 구조화 답을
  실제 업무 데이터로 받는다. 과정이 만든 후속 업무 6건에서 모델의 도구 선택,
  권한, 중복 변경, 마지막 답·최종 상태와 입력 계보를 고정 규칙으로 함께 평가한다.
  저장 응답으로 6건을 회귀검사한 뒤 같은 clean commit에서 6건 전체를 실제 NIM으로
  최대 11 model turn 실행하고, Phoenix에서 각 호출의 안전한 요청·결과·다음 조치를 보며
  서로 다른 trace 6개를 JSONL과 연결한다.
  잠근 Week 4 원본 답 품질, agent 안전과 모니터링 완결성을 함께 누적 판정한다.
- Week 6: 공개 PR 결과를 읽고 본인 PR을 GitHub 제공 Ubuntu에서 검사한다(API 0회).
  이후 별도 준비·승인된 수업 코드에서 이미지 5건과 Agent 6건의 실제 답 평가를 자동으로
  실행하고, Phoenix와 결과 파일을 확인해 사람이 사용 여부를 결정한다.

처음 실습한다면 [Week 1 실습](docs/week-01-lab.md),
[Week 2 실습](docs/week-02-lab.md), [Week 3 실습](docs/week-03-lab.md),
[Week 4 실습](docs/week-04-lab.md), [Week 5 실습](docs/week-05-lab.md),
[Week 6 실습](docs/week-06-lab.md) 순서로 진행한다.
**공개 수업 자료의 범위는 이 저장소 안이다.** Week 5·6은 각각의 `docs/week-XX-lab.md`
하나에서 설명·실행·결과 해석·제출을 끝낸다. 필요한 코드·고정 응답·그림·양식도 이 저장소에
포함한다. 저장소 밖 교재·대본·진행표는 학생의 필수 자료가 아니다.
GitHub Actions 첫 실습과 관리자 설정은 Week 6 실습서에 통합했다.
개인 실행기나 별도 Linux 장비는 필요 없다.
Week 6 모델 API key는 강사가 공개 수업 저장소 `petanerd/OSSAI-26-1`의 Actions secret으로
관리한다. 학생은 공개 fork에서 PR을 제출하며, fork와 PR에 key를 넣지 않는다.
낯선 용어나 도구는 [수업 도구·채점기·용어](docs/terms-tools-and-scoring.md)에서 확인한다.
Week 5·6의 [사람의 사용 결정 양식](docs/templates/human-release-decision-template.md)도
이 저장소에 포함돼 있다. 실습서 안의 작성 절차를 따르며 별도 양식을 받을 필요가 없다.
강사 개인의 리허설 원본·작업 이력은 공개 수업 자료에 포함하지 않는다. 실습에 필요한
저장 예시의 설명과 배포 전 준비 상태는 각 주차 실습서에서 확인한다.

## 수업에서 먼저 보는 한 사례

Week 1–2는 전체 평균을 보기 전에 대표 사례 한 건을 다음 순서로 읽는다. Week 3는 Judge
결과를 보기 전에 차트·질문·후보 한 쌍만 읽고 사람 사전 label을 먼저 작성한다.

```text
페이지 이미지와 질문
→ 모델 원응답
→ 구조화된 답
→ 기대 답과 근거 페이지
→ 고정 규칙 채점 결과
```

| 주차 | 명령 | 확인할 내용 |
| --- | --- | --- |
| Week 1 | `uv run --locked python scripts/inspect_deterministic_scoring_case.py` | 한 답이 왜 통과하거나 실패하는지 |
| Week 2 | `uv run --locked python scripts/inspect_prompt_comparison_case.py` | 미리 준비한 같은 모델의 기준·후보 응답과 점수 차이 |
| Week 3 | `uv run --locked python scripts/inspect_judge_pair.py --candidates "$CANDIDATE_RESULTS" --number "$PAIR_NUMBER"` | 개인 후보 생성 뒤, 결과 공개 전에 사람이 판단할 차트·질문·후보 한 쌍 |
| Week 4 | `uv run --locked python scripts/generate_image_variants.py --pair-number 1` | 원본과, 질문에 필요한 수치가 남거나 사라진 변형 네 개 |
| Week 5 | `uv run --locked python scripts/inspect_agent_case.py --sample-id W5-06-idempotent-retry` | timeout 재시도, 변경 기록과 최종 ticket 수 |

위 명령들은 외부 API를 호출하지 않는다. Week 1–2의 Git 고정 응답은 코드 학습과 회귀검사용
`test_only`다. Week 3 명령은 [Week 3 실습](docs/week-03-lab.md)에서 만든 개인 후보 경로와 배정
번호를 사용한다. `--human-label`을 넘기면 작성한 사람 사전 label도 검증한다. 실제 API로 수집한
원본은 저장되어 있어도 `live_quality`다. 실행 조건과 완전성을 확인한 뒤에만 모델 품질을
판단한다.

## 6주 학습 경로

| 주차 | 배우는 내용 | 결과물 |
| --- | --- | --- |
| Week 1 | 이미지 입력, 구조화 출력, 고정 규칙 채점기(deterministic scorer) | 질문·답·근거 페이지를 검사하는 첫 작업 흐름 |
| Week 2 | 동일 release baseline과 자기 prompt 40건, 저장된 두 API 예시 비교 | 개인 원본·요약·baseline 비교, 경로 묶음·오류 구분 |
| Week 3 | NIM Gemma 기준·개선 실제 답과 Gemini Judge 30쌍 | 사람 사전 label, Judge trial 결과 60행의 위치·반복 충돌과 사용 한계 |
| Week 4 | 이미지 변형과 지시문 최적화 | 개인 전체 최적화·이미지 5건 실행의 원응답, 지시문 선택과 안전 비교 |
| Week 5 | OpenCQA `884` 품질, 합성 agent 6건의 안전, 실제 NIM과 Phoenix trace | 저장 6건 회귀 결과, 실제 6건의 trace·JSONL, 세 구성의 누적 상태와 사람 판단 |
| Week 6 | 본인 PR 코드 검사 → 별도 준비 후 이미지 5건·Agent 6건 실제 자동 평가 | 본인 PR 로그·실행 번호, 실제 11개 평가 결과와 사람의 최종 결정 |

Week 3–6에 필요한 실행 식별, 비용 상한, 오류 보존 기능은 공통 코드에 남아 있다. 각 주차의
실습 문서에서는 이 기능을 모두 설명하지 않고, 필요한 시점과 이유만 다룬다.

## 환경 준비

필요한 도구는 Python 3.12, `uv`, Git, 결과에서 필요한 줄을 찾는 `rg`(ripgrep)다. Docker는
사용하지 않는다.

```bash
uv python install 3.12
uv sync --locked --dev
uv run --locked python scripts/check_environment.py
```

`uv sync --locked --dev`는 `uv.lock`에 기록된 버전대로 실행 환경과 수업용 개발 도구를
설치한다. `--locked`는 잠금 파일을 임의로 바꾸지 않으며, `--dev`는 pytest와 Ruff도 함께
설치한다.

## 데이터 준비

Week 1은 AIHub `멀티모달 정보검색 데이터_Sample`의 보고서 PDF 1개와 보도자료 PDF
1개를 사용한다. 두 문서를 바탕으로 답을 찾는 질문 36건과 답이 없어 보류하는 질문 4건을
구성한다.

AIHub 원본과 라벨은 Git에 올리지 않는다. 내려받은 폴더를 다음 위치에 둔다.

```text
local-data/aihub/source/
├── 01.원천데이터/
└── 02.라벨링데이터/
```

전처리 결과는 `local-data/aihub/prepared/`, 실행 결과는 `reports/`에 생성되며 둘 다 Git에서
제외된다. 자세한 경로는 [AIHub 데이터 준비](docs/aihub-data.md)를 따른다.

Week 3 OpenCQA 원본도 Git에 넣지 않는다. [OpenCQA 데이터 준비](docs/open-cqa-data.md)를
따라 선택한 차트·질문·사람 작성 기준 답 30개를 `local-data/opencqa/`에 만든다. 사람 작성
`abstractive_answer`는 기대 답이며 후보가 아니다. 후보 A/B는 각 학습자가 같은 NIM Gemma에
기준·개선 지시문을 적용해 만든 실제 답이다.

Week 5의 실제 데이터 입력은 Week 4 GEPA 최적화가 선택한 지시문으로
OpenCQA `884` 원본 이미지에 답해 만든 `StructuredAnswer` 1건이다. Week 5는 이
답의 `sample_id=884`, `family_id=opencqa-val-884`, 선택 지시문·선택 요약·견고성
요약·응답 파일·구조화 답과 품질 평가 파일의 SHA-256을 함께 묶어 위조나 다른 입력의
혼입을 막는다. `evaluation.json`과 `evaluation-manifest.json`은 잠근 로컬 입력이며
NVIDIA로 보내지 않는다. 선택한 Week 4 지시문의 **본문**을 agent 지시문으로 쓰지는 않는다.
Agent의 역할·출력·도구 안전 규칙은 별도 파일 `prompts/week-05-agent.md`가 담당한다.

이 상류 답 1건에 `data/agent/week-05-cases.yaml`의 과정 제작 후속 업무 6건,
`data/agent/week-05-lookup.yaml`의 합성 조회 record 2건을 연결한다. 여섯 업무는 모두
같은 `source_sample_id=884`와 `family_id=opencqa-val-884`를 공유하는 고정 회귀
사례다. 별도 validation/test 분할이 없으므로 6/6을 일반적인 agent 품질이나
배포 모집단의 성능으로 확대 해석하지 않는다.

저장된 견고성 `summary.json`의 `status=pass`는 응답 5건을 수집하고 구조화 형식으로
읽었다는 뜻이다. 별도 `evaluation.json`에서 원본 답은 점수 0.139로 `failed`다.
Week 5의 `workflow_lineage`는 구조 검증을 통과한 답과 Agent 입력의 연결을 확인한다. 원본
답 품질은 `evaluation.json`, Agent 안전은 `scores.jsonl`, 모니터링 완결성은 JSONL과
Phoenix에서 확인한다. 세 구성이 모두 통과해야 전체 `status=pass`다.

Week 6 weekly 고정 회귀는 Week 5의 누적 계약을 `OpenCQA 이미지 5건 → agent 6건`으로
다시 실행하고 넓히는 한 흐름이다.
원본·변형 5건은 Week 4 선택 지시문을 쓰고, 그중 원본 `StructuredAnswer`를
`prompts/week-05-agent.md`를 쓰는 agent 6건의 입력으로 전달한다. 평가 항목은
11개이고 최대 NIM 호출은 이미지 5회와 agent model turn 11회를 합한 16회다.
Agent 여섯 건은 같은 원본 답 하나를 공유하므로 서로 독립인 통계 표본으로 세지 않는다.
전체 판정은 `상류 답 품질·견고성 5건 ∧ agent 안전 6건 ∧ monitoring 완결성`이다.
Week 4가 선택한 지시문과 선택 요약은 완료 상태, test 미사용, 출처와 provider metadata,
hash와 입력 계보를 확인하며 GEPA나 지시문 선택을 다시 실행하지 않는다.

공개 연결 연습용 `9da6a84`의 PR 성공 기록과 이번 Week 5·6 수업 코드판의 검사를 구분한다.
학생은 강사가 지정한 공개 수업판을 fork해 PR을 제출한다. 사용할 코드판과 입력 묶음의
배포를 모두 확인한 뒤 아래 실제 API 절차로 넘어간다.

이 브랜치의 세 workflow는 GitHub 표준 `ubuntu-24.04`에서 실행한다. 강사는 기존 공개 수업
저장소 `petanerd/OSSAI-26-1`에서 변수·NIM secret과 Release 입력을 관리한다. 학생은 배정된
nightly·weekly 실행을 확인한다. 수업 저장소에 쓰기 권한이 없으면 학생이 실행을 요청하고
강사가 수동 실행한 뒤, 학생 별칭·요청·실행 번호를 연결해 기록한다. workflow가 입력 해시를
검사하고 임시 Phoenix를 시작하며, JSONL·요약·DB 사본을 결과 파일로 7일 보관한다. 학생은
이를 자기 Mac·Windows에 내려받아 분석한다. 저장 예시는 배정된 실제 실행의 완료를 대신하지 않는다.

2026-09-06 공개 수업 저장소 사용과 이용조건 확인을 전제로 한 입력 17파일·수업 결과 보관,
코드상 실행 상한을 승인받았다. 다만 `crop-left`의 Pew 하단 고지 잘림,
`occlude-answer`의 Source 일부 가림, 입력 묶음의 LICENSE·NOTICE 부재를 보완해야 한다.
현재는 승인 조건 보완 대기이며 입력 업로드와 이번 새 NIM 호출은 아직 하지 않았다.
당장 승인된 총량은 nightly·weekly 한 묶음의 생성 최대 19회·목록 GET 2회·관리용 비용 $0.03이다.
더 여유 있게 실행해도 된다는 표현이나 학생 수를 근거로 이 정확한 상한을 늘리지 않는다.
현재 승인과 미완료 조건은 [실제 API 실행 승인 범위](docs/live-api-approval.md)에 기록한다.

예약 실행은 기본으로 꺼 둔다. 별도 `ENABLE_SCHEDULED_EVALUATION=true`를 설정하면 nightly는
매일 03:00 KST, weekly는 매주 월요일 03:00 KST에 실행할 수 있다. 공개 저장소의 표준
실행기 사용, 저장량·유료 기능 과금 차단과 NIM 잔여량을 먼저 확인한다. 필수 변수 6개와
준비 순서는 [Week 6 실습](docs/week-06-lab.md)을 따른다.
입력 검사는 [prepare_week6_inputs.py](scripts/prepare_week6_inputs.py), 실행 중인 DB의 안전한
사본 저장은 [export_phoenix_db.py](scripts/export_phoenix_db.py)가 담당한다.

Week 2 개인 prompt는 `local-data/week-02-students/<alias>/prompt.md`에 두고, 개인 원본·요약은
`reports/week-02-gemma-baseline/runs/`, baseline 비교는 `reports/week-02/students/<alias>/`에
저장한다. Week 3의 `human-label.yaml`·`interpretation.md`는
`local-data/week-03-student-judges/<alias>/`에 둔다. 개인 후보 생성의 호출·결과·요약·두
지시문 snapshot과 Gemini Judge 호출·결과·요약·비교는
`reports/week-03/student-full/<alias-시각>/candidates/`와 `judge/`에 나눠 보존한다. Week 4
개인 전체 실행 결과는 `reports/week-04/student-full/<alias-시각>/optimization/`과 `robustness/`에
나눠 보존한다. Week 5 개인 저장 응답과 실제 6건 결과는
`reports/week-05/students/<alias>/offline-<시각>/`과 `live-<시각>/`에 나눠 두고, 사람 판단은
`local-data/week-05-students/<alias>/human-decision.md`에 기록한다.
개인 전체 실제 실행 명령은 Week 2–6 각 학습자 실습서에 둔다.

모델에는 PDF 문장을 보내지 않는다. PDF를 페이지 JPEG로 바꿔 VLM이 이미지에서 직접 읽도록
한다. 전처리할 때는 원본·라벨 확인용 텍스트도 저장하지만, 모델 입력이나 채점에는 사용하지
않는다.

## 실제 API 모델

| 주차와 역할 | API 제공자 | 요청 모델 |
| --- | --- | --- |
| Week 1 기준 | NVIDIA NIM | `nvidia_nim/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| Week 2 기준·개선 | NVIDIA NIM | `nvidia_nim/google/gemma-4-31b-it` |
| Week 2 비교 후보 | Google AI Studio | `gemini/gemini-3.5-flash-lite` |
| Week 3 기준·개선 답 생성 | NVIDIA NIM | `nvidia_nim/google/gemma-4-31b-it` |
| Week 3 Judge | Google AI Studio | `gemini/gemini-3.5-flash-lite` |
| Week 4 최적화 타깃·견고성 | NVIDIA NIM | `nvidia_nim/google/gemma-4-31b-it` |
| Week 4 GEPA 검토 | Google AI Studio | `gemini/gemini-3.5-flash-lite` |
| Week 5 합성 agent 6건 | NVIDIA NIM | `nvidia_nim/google/gemma-4-31b-it` |
| Week 6 nightly·weekly | NVIDIA NIM | `nvidia_nim/google/gemma-4-31b-it` |

Gemini 3.5 Flash Lite는 현재 잠긴 LiteLLM adapter로 요청 모델·실제 처리 모델과 구조화 출력을
확인하므로 Week 2·3 Judge와 Week 4 지시문 검토에 쓴다. 2026-08-17에 OpenCQA JPEG·질문·
기대 답·Gemma 실제 출력을 Google로 보내는 범위를 승인했다. Week 4 검토에는 JPEG 대신
지시문·질문·기대 답·NIM 출력·고정 점수와 이유를 보낸다. Free Tier 자료가 제품 개선에
사용될 수 있다는 조건도 실행 전에 다시 확인한다.

승인 때 확인한 공개 한도는 15 RPM, 입력 250,000 TPM, 500 RPD다. 실제 실행은 현재 프로젝트의
할당량과 당일 잔여 RPD가 240건 이상인지 사전 점검한다. 코드는 15 RPM·입력 75,000 TPM·
출력 7,500 TPM과 한 full run당 최대 240요청을 적용한다. 하루 누적 요청은 추적하지 않으므로,
같은 프로젝트에서 여러 명이 실행하면 240N 요청이 500 RPD를 넘을 수 있다. Free Tier 입력·출력
단가는 0달러로 계산하되 비용 안전장치는 0.01달러로 둔다. 30쌍은 실제로 120~240회 요청하며
pacing에만 약 8~16분, 여기에 API 응답 시간이 더 걸린다. 전송 승인은 전체 실행 성공을 뜻하지
않는다. 새 결과가 완결 검사를 통과하기 전에는 `not_run` 또는 `partial`로 기록한다.

`.env`가 없을 때만 예시를 복사한다. 기존 파일이 있으면 그대로 보존하고 사용할 API 키만 편집한다.

```bash
test -e .env || cp .env.example .env
```

```dotenv
NVIDIA_NIM_API_KEY="Week-1~6-NIM을-호출할-때-입력"
GEMINI_API_KEY="Week-2-비교·Week-3-Judge·Week-4-GEPA-검토를-호출할-때-입력"
DEEPEVAL_DISABLE_DOTENV=1
DEEPEVAL_TELEMETRY_OPT_OUT=YES
```

`.env`는 Git에서 제외된다. 외부 전송 자료와 실행 상한은
[실제 API 실행 승인 범위](docs/live-api-approval.md), NIM 호출 방법은
[NVIDIA NIM 실행 안내](docs/nvidia-nim.md)를 확인한다.

## 학습 자료

- [GitHub Actions 실습 안내](docs/github-actions.md): Week 6 실습서로 통합한 이전 안내 주소
- [Week 1 실습](docs/week-01-lab.md): 환경 준비부터 한 사례·40건 실행과 고정 규칙 채점까지
- [Week 2 실습](docs/week-02-lab.md): 자기 prompt 40건과 동일 release baseline, 저장된 Gemma–Gemini 예시 비교
- [Week 3 실습](docs/week-03-lab.md): 개인 Gemma 실제 답 60개, 사람 사전 label과 Gemini Judge 30쌍
- [Week 4 실습](docs/week-04-lab.md): GEPA 지시문 최적화와 원본·변형 이미지 견고성 평가
- [Week 4 기록 양식](docs/templates/week-04-progress-template.md): 준비 스크립트가 복사하는 저장소 내 기록지
- [Week 5 실습](docs/week-05-lab.md): Week 4 OpenCQA `884` 답을 이은 합성 6사례의 계보·도구 권한·변경 기록·최종 상태 평가와 Phoenix 분석
- [Week 6 실습](docs/week-06-lab.md): nightly 1건과 weekly 이미지 5건→agent 6건의 자동 실행, 이력과 사람 출시 결정
- [수업 도구·채점기·용어](docs/terms-tools-and-scoring.md): 라이브러리, 지표, 실행 용어의 뜻
- [코드 구조](docs/architecture.md): 실행 파일과 내부 코드의 연결
- [AIHub 데이터 준비](docs/aihub-data.md): 원본 위치와 전처리 결과
- [OpenCQA 데이터 준비](docs/open-cqa-data.md): 공식 원본 revision과 로컬 30쌍 준비
- [NVIDIA NIM 실행 안내](docs/nvidia-nim.md): 사전 점검과 실제 호출 안전장치
- [실제 API 실행 승인 범위](docs/live-api-approval.md): 외부 전송 자료와 호출 상한
