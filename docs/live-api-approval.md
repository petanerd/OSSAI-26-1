# 실제 API 외부 전송 확인표

실제 API 실습은 문서 페이지·차트 이미지를 모델 제공사의 서버로 보낸다. 실행 전에는 사람이 아래 항목을
확인한다. 모델·접속 주소·가격 근거·키 이름은 아래 실제 설정 파일을 기준으로 삼으며, 실행 코드도
이 파일을 읽는다.

## Week 1–3 기준 파일

| 실습 | 실행 설정 |
| --- | --- |
| Week 1 Nemotron | `configs/nvidia-nim.yaml` |
| Week 2 Gemma 기준 지시문 | `configs/nvidia-nim-gemma4-baseline.yaml` |
| Week 2 Gemma 개선 지시문 | `configs/nvidia-nim-gemma4.yaml` |
| Week 2 NIM Gemma–AI Studio Gemini 경로 비교 | `configs/week-02-live.yaml` |
| Week 3 NIM Gemma 후보 생성 | `configs/week-03-candidates.yaml` |

요청·토큰·비용·시간·재시도 상한은 [Week 1 실습](week-01-lab.md),
[Week 2 실습](week-02-lab.md), [Week 3 실습](week-03-lab.md)의 실제 명령을 따른다. Week 1은 해당
학습자 문서의 계약대로 진행하고, Week 2는 저장 예시 분석과 학습자별 40건 full live를
함께 한다. 학생은 설정과 해당 주차 실습서의 학생 실행 명령을 대조하고, 다르면 호출하지 말고
강사에게 확인한다. 별도 승인 YAML을 실행 코드가 읽는다고 가정하지 않는다.

NVIDIA 설정은 `developer_program_free_endpoint`, 수업용 비용 계산값 0달러와 공식 상품 안내
URL을 기록한다. 이 값은 NVIDIA가 공개한 token 단가가 아니다. 실행 당일 개발 endpoint 이용
조건, 모델 목록과 계정 할당량을 다시 확인한다.

Google AI Studio 경로는 `free_tier`다. 공식 가격표상 무료 입력·출력은 0달러지만 요청이
제품 개선에 사용될 수 있다. 공개·합성·비식별 자료만 보내고 실행 당일 가격표와 계정의
무료 한도를 다시 확인한다.

### Week 2 역할과 합산 승인

Week 2의 실제 NIM 요청은 세 역할을 섞지 않는다.

| 역할 | 호출 범위 | 목적 |
| --- | --- | --- |
| 튜터 수업 전 baseline | 같은 release에서 40건 한 번 | 학습자 후보와 비교할 공통 기준 |
| 각 학습자 | 학생별 prompt로 40건 한 번 | 저장 baseline과 개인 후보의 prompt-only 비교 |
| 강의자 수업 시연 | `r01` 최대 1건 | 원응답·actual model·저장 형식 확인 |

같은 release에서 이미 완결된 baseline이 있으면 튜터는 40건을 다시 호출하지 않는다. 학습자
수가 `N`명이면 새 요청 상한은 baseline 준비가 필요할 때
`40 + 40×N + 1`, 재사용할 수 있을 때 `40×N + 1`이다. 강의자 시연이
승인되지 않으면 마지막 1건은 0건이다. 공유 credential을 쓸 때는 runner별 상한만 보지 말고
계정의 동시 요청·분당 요청·전체 할당량과 학습자별 0.01달러 상한의 합도 승인한다. 필요하면
학습자를 wave로 나눈다.

학습자 prompt는 `local-data/week-02-students/$STUDENT_ALIAS/prompt.md`, 비교 결과는
`reports/week-02/students/$STUDENT_ALIAS/` 아래에 둔다. 기존
`local-data/week-02-prompt.md`는 강의자 `r01` 시연 호환용이며 학습자 full
run에 공동으로 쓰지 않는다.

### 모델·가격 확인 날짜

실행 당일 설정의 공식 URL에서 billing basis와 이용 조건을 확인한다. provider에 공개 단가가
있으면 입력·출력 단가도 설정값과 비교한다. 값이 달라졌으면 설정을 고쳐 commit하고,
같다면 소스 파일은 바꾸지 않는다. 두 항목을 실제로 확인한 날짜만 live 명령에 넘긴다.

```bash
CATALOG_DATE=$(date +%F)
PRICING_DATE=$(date +%F)
```

모든 live 명령은 `--catalog-verified-on "$CATALOG_DATE"`와
`--pricing-verified-on "$PRICING_DATE"`를 모두 요구한다. Week 1–2 실행기는 7일 이내 확인만
받고, Week 3 후보·Judge 실행기는 실행 당일 날짜만 받는다.

## Week 1–2 전송 범위

| 보낸다 | 보내지 않는다 |
| --- | --- |
| AIHub PDF에서 만든 페이지 JPEG | PDF 추출 문장 |
| 한국어 질문 | 기대 정답과 채점 결과 |
| 구조화 답변용 지시문(prompt) | 다른 API 제공자의 응답 |
|  | API 키 |

VLM이 페이지 JPEG를 직접 읽는다. PDF 추출 문장은 모델 입력이나 채점에 넣지 않는다. AIHub
이용정책과 각 API 제공자의 데이터 이용 조건을 확인한 뒤 실행한다.

## Week 1–2 실행 전 확인

1. 실행할 설정 파일에서 API 제공자, 요청 모델, 실제 처리 예상 모델, 접속 주소와 키 환경
   변수 이름을 읽는다.
2. 사전 점검에서 요청 모델이 현재 목록에 있는지 확인한다.
3. 설정의 가격 근거 URL과 단가·billing basis, 계정 할당량을 당일 확인하고 두 확인
   날짜를 live 명령에 넘긴다.
4. `.env`에 필요한 키가 있고 Git과 화면 공유에 포함되지 않는지 확인한다.
5. 실습 명령에 요청·입력 token·출력 token·비용·시간·재시도 상한이 모두 있는지 확인한다.
6. 전체 실행은 `git status --short` 출력이 없을 때만 하고 probe는 새 결과 폴더를 쓴다.
7. Week 2 baseline의 `provenance.git_sha`가 학습자 release commit과 같고,
   비교기가 workflow·dataset·lockfile·schema·scorer hash를 확인할 수 있는지 검사한다.
8. 강의자 probe에서 원응답, 실제 처리 모델, 사용량과 오류를 확인한다. 학습자 full live는
   별도로 승인한 wave와 개인 상한에서만 시작한다.

Google AI Studio 경로의 `free_tier`와 0달러 계산은 해당 API key가 실제 무료 tier일 때만
맞는다. 실행 당일 계정 tier와 가격표의 데이터 이용 항목(`Used to improve our products`)을
확인한다. 제출 데이터의 제품 개선 이용이 허용되지 않거나 유료 tier라면 현재 0달러 설정으로
호출하지 않는다.

probe 일부가 성공해도 전체 품질이 좋다고 결론 내리지 않는다. Git에 포함된 고정·재생
응답은 시험 전용 증거(`test_only`)다. 대체 경로와 재실행을 끈 실제 API 원본은 저장되어
있어도 실제 품질 증거(`live_quality`)다.

Week 2 학습자 한 명의 full live 상한은 요청·attempt 40/40, 입력 800,000 token, 출력
20,000 token, 비용 안전장치 0.01달러, 7,200초, 재시도 0이다. `summary.json`의
`observed_status=complete`와 40개 원응답·결과가 있어야 실행이 완결된다. 품질 실패로
runner가 exit 1을 반환하더라도 이 완전성 조건을 만족할 수 있다. exit 2, 부분 실행, provider
오류나 provenance 불일치는 저장하되 비교 결론은 `inconclusive`로 둔다. 승인이
없으면 안전하게 0건을 호출하고, 개인 full live 완료는 승인된 보충 시간으로 미룬다.

## Week 3 두 단계 전송 명세

Week 3은 **NIM Gemma 답 생성**과 **Google AI Studio Gemini Judge**를 서로 다른 실제 실행으로
승인한다. 첫 단계 승인이 둘째 단계를 자동 승인하지 않는다. 각 학습자는 자기 계정과 자기
API key만 사용하며 key와 `.env`를 공유하거나 제출하지 않는다.

### 1. NIM Gemma 기준·개선 답 60개

| 항목 | 값 |
| --- | --- |
| API 제공자·모델 | NVIDIA NIM, `nvidia_nim/google/gemma-4-31b-it` |
| 키 환경 변수 | `NVIDIA_NIM_API_KEY` |
| 보낸다 | OpenCQA JPEG, 질문, 기준 또는 개선 지시문 |
| 보내지 않는다 | OpenCQA 기대 답, 다른 후보, 사람 label, Judge 결과, API key |
| 범위 | 같은 모델에서 기준 지시문 30개 + 개선 지시문 30개 |
| 상한 | 요청·attempt 60/60, 입력 1,200,000 token, 출력 30,000 token, 비용 안전장치 $0.01, 7,200초, 재시도 0 |
| 결과 | 후보 생성 호출·결과·요약, 기준·개선 지시문 snapshot |

60개 실제 답, 두 지시문 snapshot, requested/actual Gemma model과 입력 hash가 모두 맞아야
후보 생성을 `complete`로 판정한다. 그 뒤에만 기준·개선 출처를 가리고 개인 A/B 30쌍을 만든다.
후보 생성이 `partial` 또는 `not_run`이면 Gemini Judge를 시작하지 않는다.

### 2. Gemini 3.5 Flash Lite Judge 30쌍

| 항목 | 값 |
| --- | --- |
| API 제공자·모델 | Google AI Studio, `gemini/gemini-3.5-flash-lite` |
| 실행 설정 | `configs/google-gemini-3.5-flash-lite-judge.yaml` |
| 키 환경 변수 | `GEMINI_API_KEY` |
| 고정 평가 기준 | `configs/week-03-judge-rubric.yaml` |
| 보낸다 | OpenCQA JPEG, 질문, 사람 작성 기대 답(`abstractive_answer`), 익명 Gemma 후보 A와 B, 고정 Judge rubric |
| 보내지 않는다 | 개인 사람 label, 후보의 기준·개선 출처, article·summary·OCR, API key |
| 범위 | 30쌍 × 2 trial × A/B·B/A |
| 전체 hard cap | 실제 요청 120~240회, 요청·attempt 최대 240/240, 입력 1,200,000 token, 출력 120,000 token, 비용 안전장치 $0.01, 10,800초, 요청당 재시도 1회 |
| 코드 rate cap | 15 RPM, 요청당 입력 5,000 token·출력 500 token, 한 full run당 최대 240요청 |
| 결과 | Judge 호출·60행 trial 결과·요약, `comparison.json` |

개인 30쌍 Judge 명령은 사람 label을 받지 않는다. 실행이 완결된 뒤 비교 명령이 잠근 label을
로컬에서 연결하고 SHA-256이 그대로인지 확인한다. 사람 label은 Gemini 요청에 들어가지 않는다.

Gemini 3.5 Flash Lite는 현재 잠긴 LiteLLM adapter로 요청 모델·actual model·구조화 출력을
확인할 수 있어 Judge로 선택했다.

Google로 보내는 자료에는 OpenCQA JPEG·질문·기대 답뿐 아니라 NIM Gemma가 만든 실제 출력도
포함된다. 실행 당일 계정 tier, quota, 가격과 데이터 이용 조건을 확인하고 이 전송 범위를
명시적으로 승인해야 한다. Free Tier 입력·출력이 제품 개선에 사용될 수 있다는 조건을 허용할
수 없으면 호출하지 않는다.

OpenCQA JPEG·질문·기대 답·익명 Gemma 출력의 Google 전송은 2026-08-17에 승인됐다. 승인 당시
[공식 rate limit 안내](https://ai.google.dev/gemini-api/docs/rate-limits)에서 확인한 Free Tier
근거는 15 RPM, 입력 250,000 TPM, 500 RPD다. 이 수치는 모든 API key에 자동 적용되는 보장이
아니다. 실행 당일 Google AI Studio에서 현재 key가 속한 프로젝트의 tier와 실제 한도가 이보다
낮지 않은지, 당일 잔여 RPD가 240건 이상인지 확인한다. 확인하지 못했거나 값이 낮으면 요청
0건과 `not_run`으로 남긴다.

수업 코드는 15 RPM과 요청당 입력 5,000 token·출력 500 token을 함께 적용한다. 분당 잠재
상한은 입력 75,000 TPM·출력 7,500 TPM으로, 확인한 입력 250,000 TPM보다 낮다. 30쌍은 판정
형식에 따라 120~240회 요청한다. 코드는 한 full run의 240요청만 막고 프로젝트의 하루 누적
요청은 추적하지 않는다. pacing만 약 8~16분이고 API·네트워크 응답 시간이 더해진다. 10,800초는
예상 시간이 아니라 중단을 보장하는 hard cap이다.

[공식 가격표](https://ai.google.dev/gemini-api/docs/pricing)의 Free Tier 입력·출력 단가는
0달러로 설정한다. 0.01달러는 예상 청구액이 아니라 tier나 설정이 달라졌을 때 호출 전에 멈추는
코드 안전장치다. 전송 승인은 full 실행 성공을 뜻하지 않는다. 새 호출·결과·요약·비교가 완결
검사를 통과하기 전에는 `complete`로 표시하지 않는다.

학습자가 `N`명이면 반 전체 최대 상한은 NIM 요청 `60N`·입력
`1,200,000N`·출력 `30,000N` token·비용 `$0.01N`과, Gemini 요청
`240N`·입력 `1,200,000N`·출력 `120,000N` token·비용
안전장치 `$0.01N`을 분리해 승인한다. Gemini의 Free Tier token 단가로 계산한 명목
비용은 0달러다. provider별 분당 요청과 현재 프로젝트의 하루 한도를 함께 확인하고, 여러
학습자가 하나의 프로젝트를 쓰지 않도록 한다. 같은 프로젝트에서 N명이 실행하면 최대 240N
요청으로 500 RPD를 넘을 수 있다. 필요한 경우 학습자를 wave로 나눈다.

과거 `abstractive_answer / extractive_answer` 후보와 NIM Gemma Judge로 만든 Codex 합성 기준,
그 기준으로 계산한 수치와 저장 결과는 legacy다. 새 입력·provider·hash와 다르므로 새 학습자
실행의 fallback이나 완료 근거로 쓰지 않는다.

개인 완료에는 후보 생성과 Judge가 모두 `complete`여야 한다. 어느 단계든 `partial`이면 원본을
지우거나 같은 폴더에 이어 쓰지 않고, `not_run`이면 요청하지 않은 사유를 기록한다. 한 사람의
label과 Judge가 일치했다는 이유만으로 `human_calibrated`나 blocking 품질 증거라고 부르지 않는다.

## Week 4 외부 전송 명세

Week 4에서는 NIM Gemma가 차트에 답하고 Gemini Flash Lite가 지시문을 고쳐 쓴다. 아래 상한을
코드에 넣었다고 실행 승인이 끝난 것은 아니다. 실행 전에 사람이 NVIDIA와 Google로 보낼 자료,
모델, 가격, 남은 할당량과 Git 변경 사항이 없는지 확인한다.

| 실행·역할 | 보내는 자료 | 정확한 상한 |
| --- | --- | --- |
| PromptOptimizer의 NIM Gemma 타깃 호출 | OpenCQA JPEG·질문·타깃 지시문 | 요청·attempt 45/45, 입력 900,000 token, 출력 22,500 token, $0.01, 7,200초, 재시도 0 |
| PromptOptimizer의 Gemini 검토 호출 | 지시문·질문·사람 기대 답·NIM 출력·고정 점수와 이유 | 요청 4회, attempt 최대 8회, 입력 40,000 token, 출력 16,000 token, $0.01, 7,200초, 요청당 재시도 1회 |
| `scripts/run_image_robustness.py`의 NIM Gemma | OpenCQA 원본·변형 이미지, 질문, 선택 지시문 | 요청·attempt 5/5, 입력 100,000 token, 출력 2,500 token, $0.01, 900초, 재시도 0 |
| 수업 중 2건 시연의 NIM Gemma | 개발 사례 JPEG·질문·처음 지시문 | 요청·attempt 5/5, 입력 100,000 token, 출력 2,500 token, $0.01, 900초, 재시도 0 |
| 수업 중 2건 시연의 Gemini | 지시문·질문·사람 기대 답·NIM 출력·고정 점수와 이유 | 요청 2회, attempt 최대 4회, 입력 20,000 token, 출력 8,000 token, $0.01, 900초, 요청당 재시도 1회 |

세 실행 모두 `structured_output=json_schema`로 답의 필드와 자료형을 제한한다. NIM의 차트
답변은 요청당 출력 500 token, Gemini의 지시문 진단과 재작성은 2,000 token까지 허용한다.
NVIDIA와 Google의 사용량 상한과 `provider_role`은 따로 기록한다. Gemini에는 OpenCQA 이미지,
사람이 쓴 `variant-review.csv`, API key를 보내지 않는다. 원응답·실제 처리 모델·token·시간·
오류는 `calls.jsonl`과 `summary.json`에 남긴다.

앞의 첫 세 행에 적은 상한은 수업 전 전체 저장 기록과 수업 후 개인 전체 실행에 각각
적용한다. 학습자 수가 `N`이면 개인 실행의 전체 상한은 다음과 같다. NIM은 요청·attempt
`50N`회, 입력 `1,000,000N` token, 출력 `25,000N` token과 관리용 비용 `$0.02N`이 최대다.
Gemini는 요청 `4N`회·attempt `8N`회, 입력 `40,000N` token, 출력 `16,000N` token과
관리용 비용 `$0.01N`이 최대다. 개인 API key를 공유하지 않고 제공자별 quota가 부족하면 실행
일정을 나눈다.

마지막 두 행은 반 전체가 한 번 실행하는 개발 사례 2건짜리 시연 상한이다. 시연은 지시문 생성
과정만 보여 주며 검증 문제를 실행하거나 후보를 선택하지 않는다. 이미지 5건도 수업 중 다시
호출하지 않는다. 수업에서는 이 2건 시연을 먼저 끝낸 뒤 전체 저장 기록을 공개한다. 수업용
저장 결과와 시연은 개인 전체 실행 완료를 대신하지 않는다.

2026-08-19 실행 직전 NVIDIA 카탈로그에서 `google/gemma-4-31b-it` 제공을 확인했다.
AI Studio의 `ossai-26-1` 프로젝트에서 Gemini 3.5 Flash Lite의 최근 1일 최대 사용량은
1/15 RPM·2,230/250,000 TPM·12/500 RPD였다. Git `4b53815`의 실제 실행은 승인 상한 안에서
PromptOptimizer NIM 42회·Gemini 4회와 이미지 평가용 NIM 5회를 마쳤다. API 제공자 오류와
실제 모델 불일치는 0건이었고 기록 비용은 $0였다.
같은 날 Git `73948ed`의 수업 시연도 개발 사례 `884`·`43`에서 NIM 5회·Gemini 2회로
완결됐다. 오류·모델 불일치는 0건, 기록 비용은 $0였고 후보를 품질 선택에 쓰지 않았다.
이 기록이 다음 실행의 할당량이나 가격을 보장하지는 않으므로 실행 당일 다시 확인한다.

## Week 5 외부 전송 명세와 실행 기록

과거 합성 자료 11회 승인은 이전 AIHub 식별자 기반 실행에서 이미 사용됐다. 현재
`week-05-agent-cases-v2`는 별도 승인을 받아 2026-08-31 Git
`d25e5c362f3517259b5f9d09434869a852aa138e`에서 catalog 조회 1회와 아래 6사례 NIM 요청
11회를 실행했다. 이 승인은 모두 사용했으며 새 commit의 재실행 승인으로 재사용하지 않는다.

| 항목 | 내용 |
| --- | --- |
| script·config | `scripts/run_agent_live.py` · `configs/nvidia-nim-gemma4.yaml` |
| 제공자·모델 | NVIDIA NIM · `google/gemma-4-31b-it` |
| 접속·키 이름 | `https://integrate.api.nvidia.com/v1` · `NVIDIA_NIM_API_KEY` |
| 새 승인 뒤 task model에 보낼 자료 | 별도 `prompts/week-05-agent.md` 본문, 합성 상황·권한 범위·호출 상한·`personal_phone` field 이름, 허용된 합성 lookup·calculator·ticket 결과, Week 4 OpenCQA `884` 원본 `StructuredAnswer`, sample·family·source metadata, 선택 prompt·선택 summary·견고성 summary·responses·canonical output hash, 상류 파일·구조 상태 |
| 로컬 누적 판정 입력 | `--upstream-evaluation local-data/week-04-full-runs/robustness-4b53815/evaluation.json`; 같은 폴더의 `evaluation-manifest.json`과 관련 hash도 확인 |
| 보내지 않는 자료 | Week 4 선택 prompt 본문, `evaluation.json`, `evaluation-manifest.json`, OpenCQA JPEG·질문·사람 기대 답, AIHub 페이지·질문·정답·모델 응답, `personal_phone` 값, 실제 개인정보, API key, 로컬 경로 |
| Week 5 완료 상한 | `--profile week5`, 합성 6사례, model 요청·attempt 11/11, 입력 220,000 token, 출력 5,500 token, 0.01달러, 1,800초, 재시도 0 |
| 저장 결과 | `response-receipts.jsonl`, `calls.jsonl`, `runs.jsonl`, `scores.jsonl`, `summary.json`, `deepeval/` |

실제 결과 폴더는 `reports/week-05-live-20260831T123317Z-d25e5c3/`다. 요청·attempt 11/11,
입력 13,770 token, 출력 669 token, 기록 비용 0달러, provider 오류·모델 불일치 0건이었다.
여섯 사례와 서로 다른 Phoenix trace 6개가 완결돼 모니터링은 `pass`다. Agent는 5/6이며,
`W5-05`가 도구 없이 안전하게 보류했지만 사유에 `personal_phone`과 `권한`을 명시하지 않아
`final_answer`와 `task_success`가 실패했다. 상류 품질도 실패하므로 최종 상태는 `fail / HOLD`다.

`lookup`, `calculator`, `create_ticket`은 모두 로컬 sandbox에서 실행한다. 티켓 생성은 외부
시스템의 실제 상태 변경이 아니며 매 사례마다 초기화된다. task model에는 합성 tool 결과만
후속 context로 보낸다. `staff-01`과 전화번호 값은 합성이지만, `personal_phone` 값은 권한
검사에서 차단해 조회하거나 전송하지 않는다. Week 4 선택 prompt 파일은 hash 검증에만 쓰고
본문을 agent system prompt로 보내지 않는다. 실제 실행은 로컬 Phoenix 연결과 JSON Schema를
필수로 하며 공식
[NVIDIA NIM 지원 표](https://docs.nvidia.com/nim/vision-language-models/1.7.0/nim-container-variants.html)를
당일 확인한다. 새 commit·승인자·날짜와 새 상한이 기록되기 전에는 재실행하지 않는다.

실행기는 위 NVIDIA endpoint·키 환경 변수·요청 모델과 요청당 상한을 설정 파일에서 정확히
확인한다. 실행 전에 Week 4 선택 summary·selected prompt·견고성 summary·responses와 잠근
`evaluation.json`·`evaluation-manifest.json`이 모두 프로젝트 안의 실제 파일인지 확인한다.
OpenCQA `884`, `opencqa-val-884`, source revision·license, evaluation·responses SHA-256,
source Git SHA 또는 schema SHA-256이 하나라도 다르면 provider를 만들기 전에 멈춘다.
두 품질 파일 자체의 SHA-256도 결과에 남기며, 이 로컬 사전 검사와 누적 판정에만 쓰고
NVIDIA 요청에는 넣지 않는다.

고정 manifest `week-05-agent-cases-v2`에는 OpenCQA source identity·revision·license를 둔다.
실행별 `summary.json`에는 `upstream_sample_id`, `upstream_family_id`와 선택 prompt·선택 summary·
source summary·responses·canonical output 및 품질 artifact 계보의 SHA-256을 기록한다. 상류 답 1건에
합성 agent 상황 6건과 lookup record 2건을 연결한다. 저장 응답은 6행·model turn 11개다.
여섯 상황은 모두 같은 `opencqa-val-884` family를 공유하는 고정 회귀 사례이며 별도
validation/test 분할이나 일반화 주장은 없다.

Week 5 완료에는 같은 clean commit의 저장 응답 6사례 `test_only` 결과와 실제 NIM
6사례 결과가 모두 필요하다. 실제 결과에는 서로 다른 Phoenix trace ID 6개와 같은 사례를
연결하는 JSONL이 있어야 한다. `W5-06`의 3 model·2 tool·1 ticket은 이 전체 결과에서
분석하며 별도 요청을 만들지 않는다. 이 실행 증거에 잠근 Week 4 품질 artifact를 결합해
`상류 답 품질 ∧ agent 안전 ∧ monitoring 완결성`으로 Week 5 전체 상태를 판정한다.

실제 응답은 두 단계로 남긴다. `response-receipts.jsonl`은 provider 응답을 받은 즉시 원응답을
보존한다. `calls.jsonl`은 token·예산·actual model·attempt trace를 확인한 뒤 정산된 호출 상태를
보존한다. `summary.json`은 두 파일을 포함한 결과 hash, 일곱 지표별 통과 수 `metric_passed`와
채점 사례 수 `metric_record_count`를 기록한다. 응답 수신 뒤 telemetry나 예산 검사가 실패해도
첫 수신증을 지우지 않는다.

`data/recorded/week-05-upstream.json`과 저장 turn으로 만든 offline 결과는 `test_only`다.
또한 실제 견고성 `summary.json`의 `status=pass`와 이를 옮긴 upstream context의
`source_status=pass`는 5개 응답을 수집하고 원본을 `StructuredAnswer`로 읽을 수 있다는
파일·구조 상태다. 별도 `evaluation.json`에서 원본 답
품질은 점수 0.139, `failed`다. `workflow_lineage`는 같은 구조화 답을 연결했는지만 확인한다.
따라서 source summary나 `workflow_lineage` 통과는 품질 통과가 아니다. 실제 agent는 5/6이고
Phoenix trace 6개는 완결됐다. Agent 안전과 상류 품질이 모두 실패해 Week 5 전체
`status=fail`이며 사람의 결정은 `HOLD`다. Agent가 이후 6/6이 되더라도 잠긴 상류 품질
실패가 남으면 같은 결론이다. Week 5는 이 잠긴 품질 결과와 입력 SHA-256을 사용한다.

과거 `e297a67`의 11요청은 이전 출력 형식과 AIHub 식별자만 사용한 실패 진단이다. 현재
OpenCQA 결합, 판별 출력 형식과 Phoenix 완료 근거로 승격하지 않는다.

## Week 6 반복 실행의 새 승인 범위와 현재 상태

현재 브랜치에는 nightly·weekly workflow가 있다. 2026-09-01 로컬 E2E 결과는 Git에 포함되지
않은 강사 보존 기록이며 학생 실습의 필수 입력이 아니다. Nightly는
매일 03:00 KST, weekly는 매주 월요일 03:00 KST의 예약 정의와 수동
`workflow_dispatch`를 제공한다. 예약은 기본으로 꺼 둔다. 강사는 기존 공개 수업 저장소
`petanerd/OSSAI-26-1`에서 Actions 변수·NIM secret과 Release 입력을 관리한다. 학생은 공개
fork에서 PR을 제출하고, 실제 평가는 수업 저장소의 GitHub 표준 `ubuntu-24.04`에 배정한
실행으로 구분한다. 쓰기 권한이 없으면 학생이 실행을 요청하고 강사가 수동 실행한 뒤,
학생 별칭·요청·실행 번호를 함께 기록한다. 별도 비공개 저장소나 개인 실행기 등록은 필요 없다.
fork·PR에는 key를 넣지 않으며 PR 검사는 모델 API 0회다. 저장 예시와 Week 5의 일회성
승인은 새 실행 승인이 아니다. 실행 당일 사전 확인을 마치기 전에는
`ENABLE_LIVE_EVALUATION`을 켜지 않는다.

### 2026-09-06 새 승인 기록 — 조건 보완 대기

사용자는 기존 공개 수업 저장소의 사용, 이용조건 확인을 전제로 한 입력 17파일·수업 결과의
GitHub 보관, 코드상 실행 상한을 승인했다. 저장 승인을 다시 기다리는 상태가 아니라
승인에 붙은 조건을 보완하는 상태다. 당장 승인된 실행은 아래 nightly·weekly 한 묶음이며
**생성 최대 19회, 모델 목록 GET 2회, 관리용 비용 합계 $0.03**을 유지한다. 더 여유 있게
실행해도 된다는 표현을 정확한 상한 변경으로 해석하지 않으며 학생 수만큼 반복하는 승인도
아니다. 추가 실행은 남은 할당량을 확인하고 정확한 합산 상한을 새로 승인받는다.

현재 `crop-left` 변형은 Pew 하단 고지를 잘랐고 `occlude-answer`는 Source 일부를 가렸다.
입력 archive에는 LICENSE·NOTICE도 없다. 따라서 파일별 권리·고지·변형 이용조건을 확인하고
필요한 고지를 보완하기 전에는 공개 업로드나 이번 새 NIM 실행을 시작하지 않는다.
현재 입력 업로드와 이번 새 NIM 호출은 모두 아직 하지 않았다. 과거 실행 기록과 이 새 승인·
미실행 상태를 구분하며, 코드 검사 통과를 배포나 실제 API 완료로 바꾸지 않는다.

강사 보존 기록 두 개의 `git_sha=2d0ebeb...` commit 객체는 현재 저장소에 없다. 이 기록을
학생에게 내려받으라고 요구하거나 현재 코드와 같은 계보의 live 증거라고 소개하지 않는다.
학생의 API 없는 연습은 실습서의 Git 고정 응답을 쓰고, 현재 계보 확인은 배정된 새 Actions
결과가 있을 때 수행한다.

| 실행 | NVIDIA NIM에 보내는 자료 | 생성 요청·attempt 상한 | token·비용·시간 상한 |
| --- | --- | ---: | --- |
| nightly | Week 5 agent prompt, `W5-06` 합성 상황·권한·도구 결과, 저장된 OpenCQA `884` 원본 구조화 답과 계보 metadata·hash | 3/3 | 입력 60,000, 출력 1,500 token, $0.01, 360초, 재시도 0 |
| weekly 이미지 | OpenCQA 원본·변형 JPEG 5개, 질문, Week 4 선택 지시문 | 5/5 | 입력 100,000, 출력 2,500 token, $0.01, 900초, 재시도 0 |
| weekly agent | Week 5 agent prompt, 합성 상황·권한·허용된 도구 결과, weekly가 만든 원본 구조화 답과 계보 metadata·hash | 11/11 | 입력 220,000, 출력 5,500 token, $0.01, 1,800초, 재시도 0 |
| weekly 합계 | 앞의 두 weekly 단계 | 최대 16/16 | 입력 320,000, 출력 8,000 token, 관리용 비용 $0.02 |

Nightly와 weekly 모두 첫 생성 요청 전에 NVIDIA 모델 목록을 읽는 preflight GET 1회를
별도로 수행한다. 여기에는 이미지·질문·모델 답·합성 상황·도구 결과가 들어가지 않는다.
선택 요약, 선택 실행의 호출·검증 파일, 고정 규칙 품질 결과, 사람 결정, API key와 로컬
경로는 NVIDIA에 보내지 않는다. 선택 지시문 본문은 weekly 이미지 답변에만 보내며 agent
system prompt로 재사용하지 않는다. `personal_phone` 값과 실제 개인정보도 보내지 않는다.

Weekly는 Week 5의 `상류 original 답 품질 ∧ agent 안전 ∧ monitoring 완결성`을
`상류 답 품질·견고성 5건 ∧ agent 안전 6건 ∧ monitoring 완결성`으로 자동 재실행·확장한다.
선택 지시문과 선택 요약은 완료 상태, test 미사용, 출처와 provider metadata, artifact
hash와 입력 계보를 검증하며 GEPA나 선택 결정을 다시 실행하지 않는다. `agent/summary.json`이 없으면
합성 요약을 만들지 않고 결합을 실패로
보존한다. 이력은 현재 실행 record만 append하며 직전 실행 대비 값은 만들지 않는다.

두 workflow는 수업 저장소의 `main`, `ENABLE_LIVE_EVALUATION=true`,
`WEEK6_DATA_STORAGE_APPROVED=true`와 NVIDIA의 최신 preflight를 요구한다.
수동 실행은 `confirm_live_evaluation=true`, 예약 실행은 별도로
`ENABLE_SCHEDULED_EVALUATION=true`가 필요하다. 각 job이 `127.0.0.1:6006`에서
임시 Phoenix를 시작하고 준비를 확인한 다음 모델 API를 호출한다. 공개 저장소라는 사실만으로
승인 변수나 수동 확인을 우회할 수 없다.

GitHub 저장은 NVIDIA 전송과 별개 승인이다. 입력 묶음에는 OpenCQA 원본·변형 이미지,
질문·기대 답과 Week 4 지시문·저장 응답·평가 파일 17개가 들어간다. 강사는
[OpenCQA 해당 revision의 라이선스](https://github.com/vis-nlp/OpenCQA/blob/28db0fd26a12fd376f6c30b7feb8a4db32313424/LICENSE)와
[Pew 이용 조건](https://www.pewresearch.org/about/terms-and-conditions/)을 확인하고, 실제 파일의
권리·출처·저작권 고지와 변형의 고지 훼손 여부를 확인한다. 이번 저장 대상은 위에 적은
공개 수업 저장소이며, 2026-09-06 조건부 승인을 받았다. 공개된 원본이라는 이유만으로
수정 이미지의 재배포 조건까지 충족했다고 단정하지 않는다. 현재 고지 보완이 끝나지 않았으므로
`WEEK6_DATA_STORAGE_APPROVED=true`로 바꾸거나 입력 묶음을 업로드하지 않는다.

조건 보완과 배포 뒤 같은 공개 수업 저장소의 Release에서 `week56-inputs-a5eec33.tar.gz`를 내려받아
`WEEK6_INPUT_SHA256`과 정해진 파일 목록을 검사한다. 파일명의 `a5eec33`은 입력 묶음
버전이며 새 workflow 실행 코드의 SHA를 뜻하지 않는다. 실행 번호·코드 SHA·입력 해시는
`run-metadata.json`에 별도로 남긴다. 현재 추출기는 고정 17파일만 허용하므로 고지 파일을
묶음에 추가한다면 허용 파일 목록과 검사 코드도 맞춘다. 이미지 등 묶음의 내용이 바뀌면 해시를
다시 계산한다. 기존 입력의 해시를 새 묶음에 재사용하거나 해시 검사만으로 이용조건 충족을
대신하지 않는다.

JSONL·요약·해당 job의 Phoenix DB 사본은 Actions 결과 파일로 7일 보관한다. 저장 응답과
새 원응답도 공개 수업 저장소에 보관하는 승인 범위에 포함된다. 강사는 실제 업로드 전에
개인정보·비밀값·허용하지 않은 자료가 섞이지 않았는지 확인한다.
`.env`, API key, 원본 입력 묶음이나 과거 Phoenix DB 전체는 결과 파일로 올리지 않는다.
실행 이력은 각 결과 폴더의 `history.jsonl` 한 줄이며, 실행 간 자동 누적은 하지 않는다.
학생은 결과를 내려받아 [Week 6 실습](week-06-lab.md)의 Mac·Windows 절차로 연다.
