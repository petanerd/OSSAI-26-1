# 실습 데이터 폴더

AIHub `멀티모달 정보검색 데이터_Sample`에서 받은 파일을 `aihub/source/`에 넣는다.

```text
local-data/aihub/
├── source/       다운로드한 AIHub 파일
├── prepared/     PNG, API용 JPEG, page text와 manifest
└── cases.jsonl   workflow가 읽는 질문 40건
```

`prepared/`와 `cases.jsonl`은 실습 명령을 실행하면 생성된다.

Week 2 개인 지시문은 다음 위치에 둔다.

```text
local-data/week-02-students/<과정-별칭>/prompt.md
```

`local-data/week-02-full-runs/gemma-baseline/`과 `gemma-improved/`는 저장 예시 A/B다.
튜터는 수업 release와 같은 clean commit에서 만든 baseline 40건을
`local-data/week-02-full-runs/gemma-release-baseline-<short-sha>/`에 별도로 배포한다.
각 학습자의 실제 40건 원본·요약은 `reports/week-02-gemma-baseline/runs/`에 저장되고,
baseline 비교 JSON은 `reports/week-02/students/<과정-별칭>/`에 생성된다. 전체 실행과 완결 검사는
[Week 2 실습](../docs/week-02-lab.md)을 따른다.

Week 3 OpenCQA 준비 명령은 차트·질문·사람 작성 기대 답을 만든다.

```text
local-data/opencqa/
├── images/                       API와 blind 비교용 차트 JPEG 30개
└── week-03-cases.jsonl           질문·abstractive 기대 답·출처·이미지 hash 30개
```

OpenCQA `abstractive_answer`는 기대 답이며 후보 A나 B가 아니다. 각 학습자는 같은 NIM Gemma에
기준·개선 지시문을 적용해 30개씩 실제 답을 만든다. 60개 답과 두 지시문 snapshot이 완결된
뒤에만 출처를 가린 A/B 30쌍을 만든다.

과거 `abstractive_answer / extractive_answer` 후보와 NIM Gemma Judge를 사용한 Codex 합성
기준과 `local-data/week-03-full-runs/judge-30/`은 legacy 자료다. 새 개인 실행의 입력·fallback·
완료 근거가 아니다.

개인 과제로 직접 작성하는 두 파일은 다음 폴더에 둔다.

```text
local-data/week-03-student-judges/<과정-별칭>/human-label.yaml
local-data/week-03-student-judges/<과정-별칭>/interpretation.md
```

`human-label.yaml`은 A/B의 기준·개선 출처와 Gemini Judge 결과를 보기 전에 작성한다.
`candidate_set_sha256`으로 개인 후보 세트에 묶은 뒤 파일 SHA-256을 동결한다.
과정에서는 `configs/week-03-judge-rubric.yaml`을 고정 평가 기준으로 사용하며, 개인 폴더에
복사하지 않는다. 사람 판단을 잠근 다음, 각 학습자가 자기 Google AI Studio 계정으로
Gemini 3.5 Flash Lite Judge 30쌍을 full 실행한다. 개인 후보 생성·판정·요약·비교는 다음 고유 폴더에
서로 구분해 보존한다.

```text
reports/week-03/student-full/<과정-별칭-시각>/
├── candidates/
│   ├── candidate-calls.jsonl, candidate-results.jsonl, candidate-summary.json
│   └── open-cqa-answer-baseline.md, open-cqa-answer-improved.md
└── judge/
    ├── judge-calls.jsonl, judge-results.jsonl, summary.json
    └── comparison.json
```

Gemini에는 OpenCQA JPEG·질문·기대 답과 Gemma 후보 A/B를 보내지만 개인 사람 label은 보내지
않는다. 개인 30쌍 Judge 명령에도 label을 넣지 않고, 실행 뒤 비교 명령에서 로컬 파일을
연결한다. 완결된 60행 Judge 결과에서
같은 pair를 찾아 사람 판단과 직접 비교한 뒤
`interpretation.md`에 task model 오류, Judge 오류, 순서·반복 충돌과 한계를 적는다. 전체 실행과
완결 검사는 [Week 3 실습](../docs/week-03-lab.md)을 따른다.

Google 전송 범위는 2026-08-17에 승인됐다. 공식 Free Tier 근거는 15 RPM·입력 250,000 TPM·
500 RPD이고, 수업 코드는 15 RPM·입력 75,000 TPM·출력 7,500 TPM과 한 full run당 최대
240요청을 적용한다. 프로젝트의 하루 누적 요청은 추적하지 않으므로 실행 전 당일 잔여 RPD가
240건 이상인지 확인한다. Free Tier token 단가는 0달러이며 비용 안전장치는 0.01달러다.
120~240회 요청은 pacing에만 약 8~16분이 걸리고 API 응답 시간이 더해진다.

실행 당일 현재 프로젝트의 실제 tier·model·quota·가격·데이터 이용 조건을 확인하지 못하면
Judge 상태를 `not_run`으로 둔다. Free Tier 자료가 제품 개선에 사용될 수 있다는 조건도 다시
확인한다. 전송 승인만으로 새 full 실행이 성공한 것은 아니며, legacy 저장 결과로 완료를 대신하지
않는다. 개인 사람 label 한 건만으로는 `human_calibrated`가 아니다. 두 사람·최소 30쌍으로 만든
별도 보정 자료와 같은 것으로 보지 않는다.

Week 5는 Week 4의 실제 OpenCQA 상류 답과 Git의 과정 제작 agent 자료를 함께 쓴다.
실제 상류 입력은 다음 파일에 있다.
이 파일들은 Git에 포함되지 않는다. 승인된 Release의 배포 상태·다운로드·해시 검사는
[Week 5 실습](../docs/week-05-lab.md) 2절 또는 [Week 6 실습](../docs/week-06-lab.md) 4절을
따른다. 공개 저장 응답 연습에는 아래 입력이 필요하지 않다.

```text
local-data/week-04-full-runs/
├── optimization-4b53815/
│   ├── summary.json           GEPA 선택 실행 상태와 selected prompt hash
│   └── selected-prompt.md     OpenCQA 884 답을 만들 때 사용한 지시문
└── robustness-4b53815/
    ├── summary.json           sample·family·source metadata와 응답 hash
    ├── responses.jsonl        original 1건과 변형 4건의 구조화 응답
    ├── evaluation.json        각 이미지 답의 잠근 품질 판정
    └── evaluation-manifest.json 품질 결과·응답·채점기 SHA-256
```

실제 Week 5 실행기는 앞의 여섯 파일을 읽는다. GEPA가 고른 prompt로 만든 OpenCQA `884`
`original` `StructuredAnswer` 1건을 agent의 실제 업무 데이터로 사용한다. 실제 명령은
`--upstream-evaluation local-data/week-04-full-runs/robustness-4b53815/evaluation.json`으로
품질 파일을 지정하며, 실행기는 같은 폴더의 `evaluation-manifest.json`과 evaluation·responses·
source Git·schema 계보를 확인한다. 두 품질 파일 자체의 SHA-256도 결과에 남긴다. 두 파일은
잠근 로컬 판정 입력이며 NVIDIA로 보내지 않는다.

과정 제작 agent 계약과 offline 자료의 Git 정본은 다음 다섯 파일이다.

```text
data/agent/week-05-manifest.yaml       과정 제작 합성 6건의 revision·용도·한계
data/agent/week-05-cases.yaml          저위험 2·중위험 1·고위험 3사례
data/agent/week-05-lookup.yaml         합성 record 2건
data/recorded/week-05-upstream.json    상류 구조화 답 1건의 offline fixture
data/recorded/week-05-agent-turns.jsonl  offline 회귀검사용 turn 11개
```

전체 수는 OpenCQA 상류 답 1건, agent 상황 6건, 합성 lookup record 2건, 저장 응답
6행·model turn 11개다. 여섯 상황은 모두 `source_sample_id=884`,
`family_id=opencqa-val-884`를 공유한다. 별도 validation/test 분할이 없고 일반화가
금지되어 있으므로 6/6을 서로 다른 표본 여섯 개나 배포 품질로 해석하지 않는다.

Week 4 selected prompt 본문은 OpenCQA 답을 만들 때만 쓴다. Week 5 agent system prompt는
별도 `prompts/week-05-agent.md`다. 고정 manifest `week-05-agent-cases-v2`에는 OpenCQA
source identity·revision·license를 둔다. 실제 실행의 `summary.json`에는 sample·family와
selected prompt·selection summary·source summary·responses·canonical output SHA-256을
일곱 `upstream_*` field로 기록한다.

GEPA는 Week 4 지시문 후보를 만든다. Week 5는 입력 계보·도구 계약·권한·중복 변경·마지막
답·호출 상한을 Python 고정 규칙의 일곱 지표로 판정한다.

견고성 `summary.json`의 `status=pass`는 응답 5건을 수집하고 원본을
`StructuredAnswer`로 읽었다는 파일·구조 상태다. 이 값은 upstream context에
`source_status=pass`로 옮긴다. 별도 `evaluation.json`에서 `original`은 점수 0.139,
`failed`다. `source_status`와 `workflow_lineage`는 입력 연결을, `evaluation.json`은 답 품질을
확인한다. Week 5 전체 상태는 `상류 답 품질 ∧ agent 안전 ∧ monitoring 완결성`으로 판정한다.

개인 offline 결과는 다음처럼 고유 폴더에 둔다.

```text
reports/week-05/students/<과정-별칭>/offline-<시각>/
├── runs.jsonl
├── scores.jsonl
└── deepeval/
```

저장 turn을 Phoenix로 시각화해도 결과 종류는 `test_only`다. 실제 provider를 호출하지 않으므로
`response-receipts.jsonl`과 `calls.jsonl`은 만들지 않는다. 실제 NIM 실행 폴더는 이와 별도로
다음 파일을 개인 고유 폴더에 보존한다.

```text
reports/week-05/students/<과정-별칭>/live-<시각>/
├── response-receipts.jsonl   응답 수신 즉시 남긴 원응답 수신증
├── calls.jsonl               token·예산·actual model 확인 뒤 정산 호출
├── runs.jsonl                model/tool 실행 나무·ledger·최종 상태
├── scores.jsonl              일곱 고정 지표와 이유
├── summary.json              계보·품질 hash·세 누적 상태·전체 status·metric_passed·예산
└── deepeval/                 같은 일곱 지표의 DeepEval 결과
```

모델 요청이 사례 도중 실패한 경우에만 `partial-runs.jsonl`도 남긴다. 이미 수행한 도구 호출과
최종 상태·오류·trace ID를 담으며 완료된 `runs.jsonl`·`scores.jsonl`과 분리한다.

이전 출력 형식과 AIHub 식별자를 쓴 Week 5 폴더는 현재 OpenCQA 계보와 Phoenix 완료
근거로 승격하지 않는다. 새 `--profile week5` 실행은 별도 승인과 새 출력 폴더를 사용한다.
완료 결과는 같은 clean commit의 합성 6사례, model 요청·attempt 상한 11/11, 서로 다른
Phoenix trace ID 6개와 JSONL을 포함해야 한다. ID 발급 수는 `phoenix_allocated_trace_count`,
서버에서 부모·모델·도구 단계까지 저장을 확인한 사례 수는 `phoenix_trace_count`다.
후자가 6이고 `trace_complete=true`여야 기록이 완결됐다. `W5-06`은 이 결과에서 3 model·2 tool·
1 ticket 흐름을 읽으며 추가 API 호출하지 않는다. 이 agent 실행이 6/6이어도 잠근 상류 품질
실패가 남아 있으므로 현재 Week 5 전체 결과와 사람 결정은 각각 `fail`, `HOLD`다.

`local-data/week-06-full-runs/`의 기존 AIHub nightly·validation 자료는 오래된 분기의 진단
자료다. 현재 브랜치의 OpenCQA Week 6 자동 실행은 새 폴더를 여기에 덧붙이지 않고 workflow별
`reports/week-06-nightly-<run-id>-<attempt>/`와
`reports/week-06-weekly-<run-id>-<attempt>/`에 저장한다. GitHub 표준 Ubuntu의 임시
Phoenix DB 사본과 함께 결과 파일로 7일 보관한다. `history.jsonl`은 실행별 한 줄이며
여러 실행을 자동 누적하지 않는다. 입력은 이용조건을 확인·보완한 뒤 공개 수업 저장소
`petanerd/OSSAI-26-1`의 Release에서 내려받으며, 학생은 결과를 개인 Mac·Windows에서 확인한다.
강사는 Release·Actions 변수·NIM secret을 관리하고, 학생은 공개 fork PR을 제출한다.
실제 평가는 수업 저장소에서 배정한다. 쓰기 권한이 없는 학생은 강사에게 수동 실행을 요청하고
자기 별칭·요청·실행 번호를 기록한다. fork와 PR에는 key나 개인 자료를 올리지 않는다.

2026-09-06 입력 17파일과 수업 결과의 공개 GitHub 보관은 이용조건 확인을 전제로 승인받았다.
다만 현재 묶음은 `crop-left`가 Pew 하단 고지를 잘랐고 `occlude-answer`가 Source 일부를
가렸으며 LICENSE·NOTICE도 없다. 이 조건 보완 전에는 업로드하지 않는다. 현재 입력 업로드와
이번 새 NIM 호출은 아직 하지 않았다. 기존 17파일·SHA-256 검사는 파일 목록과 무결성을 확인할
뿐, 이용조건 충족을 판단하지 않는다. 묶음을 바꾸면 해시를 다시 계산하고, 고지 파일을 묶음에
추가한다면 허용 파일 목록과 검사 코드도 맞춘다. 기존 묶음의 이름이나 해시만으로 배포 완료라고
하지 않는다.

Weekly는 Week 5의 `상류 original 답 품질 ∧ agent 안전 ∧ monitoring 완결성`을 이미지
품질·견고성 5건과 agent 6건으로 다시 실행하고 확장한다. 선택 지시문·선택 요약은 완료 상태,
test 미사용, 출처와 provider metadata, artifact hash와 입력 계보를 확인한다. `agent/summary.json`이 없으면
결합용 요약을 합성하지 않고 실패 상태와 앞 단계의 부분 파일을 보존한다. 이력에는 현재 실행
record만 추가하며 직전 실행
대비 값은 만들지 않는다.

2026-09-01 nightly·weekly의 로컬 결과는 Git에 포함되지 않은 강사 보존 기록이며 학생이
받아야 할 자료가 아니다. API 없는 연습은 [Week 6 실습](../docs/week-06-lab.md)의 Git 고정
응답으로 진행한다. 각 학습자는 수업 저장소에서 본인에게 배정된 새 nightly·weekly의
결과를 확인해야 하며 예시 폴더를 복사해 개인 `complete`나 `SHIP` 근거로 만들지 않는다.
현재 승인된 nightly·weekly 한 묶음은 생성 최대 19회·목록 GET 2회·관리용 비용 $0.03이며,
학생 수만큼 반복하는 권한이나 더 높은 상한을 자동으로 부여하지 않는다.

수업 전에 만든 실제 API 원본은 다음 위치에 둔다.

```text
local-data/week-01-full-runs/nemotron/
local-data/week-02-full-runs/gemma-baseline/
local-data/week-02-full-runs/gemma-improved/
local-data/week-02-full-runs/gemma-release-baseline-<short-sha>/
local-data/week-02-full-runs/provider-comparison/
local-data/week-03-full-runs/judge-30/   legacy Week 3 결과
reports/week-05/students/<과정-별칭>/live-*/   각 학습자의 승인된 Week 5 실제 결과
local-data/week-06-full-runs/   이전 분기의 진단 자료; 개인 Week 6 Actions 실행 근거가 아님
```

Week 5 사람 판단은 `local-data/week-05-students/<과정-별칭>/human-decision.md`에 둔다.

Week 2 저장 개선·provider 결과는 설명 예시와 분석 fallback으로 쓴다. Week 3 legacy 결과는
이전 계약을 설명할 때만 쓰며, 새 Gemma 후보·Gemini Judge의 입력이나 fallback이 아니다. 개인
40건·새 Week 3 실행 완료를 대신하지 않는다.

`local-data/`는 Git에서 제외된다. 위 목록은 저장 위치이지 다운로드 완료 목록이 아니다.
Week 4의 전체 입력과 Week 5·6의 최소 입력은 각 실습서에 적힌 같은 수업 저장소 Release의
배포 상태·권리·해시를 확인한 뒤에만 받는다. 미배포 자료나 강사 개인 결과 폴더를 요구하지 않는다.
학습자는 해당 주차 실습 문서의 파일 확인 명령이 통과한 범위만 수행하고, 입력이 없는 활동은
`not_run`으로 기록한다. 개인 작성 파일과 실행 결과는 학생이 직접 생성한다.
