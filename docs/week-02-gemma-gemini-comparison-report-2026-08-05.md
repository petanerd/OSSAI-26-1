# Week 2 Gemma–Gemini 비교 결과 보고서

## 재실행 결론

Week 2 문서를 처음부터 다시 따라가며 세 사례 probe 6회와 전체 비교 80회를 새 출력
폴더에서 실행했다. 전체 실행은 Git SHA
`e7f54dbe4f686568abb6ca3d70eca55f96bc7bb9`의 깨끗한 상태에서 진행했다.

- 전체 응답: `80/80`, API 제공사 오류·재시도·actual model 불일치 0건
- `task_success`: Gemma 27/40, Gemini 35/40
- 문제별 변화: 새 성공 8, 새 실패 0, 동일 32
- 자동 상태: `pass`
- 출시 주장 / 사람 결정: `release_claim=false` / `HOLD`

자동 `pass`는 같은 실행 안에서 후보에 새 실패가 없다는 상대 비교 결과다. Gemini의 절대
실패 5건과 두 route 공통의 `r31` 답변 보류 실패가 남아 출시 기준은 통과하지 못했다.
재실행 결과는
`reports/week-02-live/full-improved-20260805-rerun-01/summary.json`에 저장했다.

아래의 최초 실행 상세 기록은 당시 Git SHA와 비교 계약에 고정된 과거 증거다. 최초 실행과
재실행은 입력 manifest는 같지만 비교 계약 hash가 다르므로 latency 변화 등을 단일 모델
변화로 해석하지 않는다.

## 최초 실행 결론

Week 2의 평가체계 감사, 모델 변경 근거, Gemma prompt A/B 재평가, 공통 개선 prompt 연결,
오프라인 case-diff와 provider fault 검증을 완료했다. 세 사례 probe 뒤 별도 승인을 받아
같은 공통 prompt로 AIHub 40건을 NVIDIA NIM Gemma와 Google AI Studio Gemini에 각각
보냈다.

최초 실행 당시 상태는 다음과 같다.

- 오프라인 학습 활동: `완료`
- 개선 prompt 실제 연결: 두 provider 모두 `성공`
- 동일 3건 probe: `6/6 calls`, 3쌍 완료
- 전체 실제 비교: `80/80 calls`, 품질 판정 가능 40쌍
- 자동 상태: `fail`
- 사람 결정: `HOLD`

`HOLD`는 연결 실패가 아니다. provider 오류는 0건이고 Gemini의 성공률은 20.0%p
높았지만 새 실패 1건이 생겼고 두 route 모두 `r31`에서 답변 보류 기준을 어겼기 때문이다.

## 무엇을 개선했는가

### 1. 기존 평가체계에서 고친 점

| 발견한 문제 | 수정한 기준 |
| --- | --- |
| 긴 문장에 질문 연도까지 반복하면 숫자 오답으로 처리됨 | `answer`에는 값과 단위만 반환 |
| F1 하나가 전체 성공처럼 읽힘 | F1은 진단, 전체 성공은 구조·보류·정답·근거의 AND |
| provider timeout이 오답처럼 평균에 포함될 수 있음 | 품질 분모와 provider 오류 분리 |
| Markdown fence를 제거하면 구조 준수로 오해 | 내용은 진단하되 `json_object_only=0` 보존 |
| PDF 추출 문장이 VLM 판단에 섞일 수 있음 | 질문과 page JPEG만 model input으로 사용 |

현재 채점 profile은 `aihub-vqa-deterministic-v2`다. PDF 추출 문장은 모델 입력, 결정적
채점과 비교 조건에 포함하지 않는다.

### 2. Nemotron에서 Gemma로 바꾼 근거

Nemotron 3 Nano Omni 공식 카드는 이미지·OCR·document intelligence를 지원하지만 언어를
English only로 명시한다. Gemma 4 공식 카드는 multilingual OCR, document/PDF parsing,
35개 이상 언어의 즉시 지원과 140개 이상 언어의 사전학습을 명시한다.

따라서 한국어 AIHub 데이터에서 Gemma를 시험할 적합성 근거는 있었다. 그러나 과거 raw
response를 현재 scorer로 계산한 진단 점수는 다음과 같았다.

| 과거 응답 | `task_success` |
| --- | ---: |
| Nemotron | 16/40 |
| Gemma 최초 기준 | 8/40 |

두 실행은 완전한 통제 A/B가 아니므로 모델 우열을 주장하지 않는다. 확인된 사실은 “모델
카드만 보고 교체하면 품질이 자동으로 오르지 않는다”는 것이다.

최초 모델 교체 commit에서는 model ID, catalog 문서와 preflight 기대값만 바뀌었다.
기준 prompt와 호출·채점 코드는 바뀌지 않았다.

### 3. Gemma 실패가 수정 근거가 된 과정

| 실제 사례 | 실패 관점 | 반영한 변경 |
| --- | --- | --- |
| `r01`, `r04` | 질문의 연도와 정답 숫자를 함께 출력 | 짧은 값 규칙 |
| `r03` | 오답 JSON 뒤 수정 설명과 두 번째 JSON | JSON 하나 규칙 |
| `r06` | 중첩 배열과 깨진 JSON | 필드 고정, parser 엄격 유지 |
| `r22`, `r25` | 표의 인접 값 선택 | 행·열·단위 재확인 |
| `r31` | 답변 보류 대신 숫자 추측 | 보류 규칙과 새 실패 감사 |
| actual model prefix | transport prefix와 provider ID 혼동 | model identity 정규화 |

기준 prompt는 fence를 금지하면서 fenced JSON 예시를 제공했다. 개선 prompt는 fence 없는
한 줄 JSON 예시, 짧은 답, 표 확인과 근거 규칙을 사용한다.

Parser가 마지막 JSON만 추출하거나 scorer가 긴 문장에서 기대 숫자만 골라내도록 바꾸지는
않았다. 그러면 출력 형식 위반이 숨기 때문이다.

### 4. Gemma prompt A/B 현재 scorer 재평가

2026-08-03의 두 실제 run raw observation을 새 API 호출 없이 현재 scorer로 다시 계산했다.

- 기준 run: `week01-20260803T135626Z-0c8a3821`
- 개선 run: `week01-20260803T141015Z-9485bcce`
- model: 두 실행 모두 `google/gemma-4-31b-it`
- 비교 profile: `aihub-vqa-deterministic-v2`

| 확인 항목 | 기준 prompt | 개선 prompt |
| --- | ---: | ---: |
| target | 40 | 40 |
| 품질 판정 가능 | 40 | 39 |
| provider 오류 | 0 | 1 |
| `task_success` | 9/40, 22.5% | 28/39, 71.8% |
| `numeric_match` | 40.0% | 84.6% |
| `schema_validity` | 92.5% | 89.7% |
| `json_object_only` | 0.0% | 28.2% |

문제별 변화는 다음과 같다.

- `new_success`: 20
- `new_failure`: 1 (`aihub-report-r31`)
- `unchanged`: 18
- `not_comparable`: 1 (`aihub-report-r24`, HTTP 500)

Provider 오류는 품질 0점으로 넣지 않았다. 평균 개선 신호는 크지만 새 실패와 provider
오류가 있어 자동 상태는 `inconclusive`다.

재평가 명령은 다음 파일로 일반화했다.

- `scripts/compare_gemma_prompts.py`
- `src/verifiable_ai_workflow/prompt_comparison.py`

비교 결과에는 `score_source`, 현재 dataset·scorer hash, 품질 분모, provider 오류와
`not_comparable_ids`가 함께 남는다.

## 최초 실행의 실제 API 조건과 결과

### 세 사례 probe

Gemma 전용 `/no_think`를 Gemini에 보내지 않도록 공통 개선 prompt를 사용했다.

```text
prompts/pdf-question-answer-json-only.md
```

공통 실행 조건은 다음과 같다.

- Git SHA: `r01`은 `9c36bc24954f03b0a28bec4c1e8d0dbdbbf51be4`, `r03`과 `r31`은
  날짜 판정 수정 commit `bb3c6c211ec48fd7886c9c769bbf040c4d91c4cd`
- Git 상태: clean
- sample: `aihub-report-r01`, `aihub-report-r03`, `aihub-report-r31`
- 입력: 공통 prompt, 질문과 page JPEG 9장
- 제외: PDF 추출 문장, 기대 답, 상대 route 응답
- sample별·provider별 요청: 1회
- retry: 0회
- 전체 승인 상한: 요청 6회, USD 0.03, 명령별 240초
- run ID: `r01`은 `week02-20260804T142957Z-c81d5279da74`, `r03`은
  `week02-20260804T203814Z-fbf732c6413b`, `r31`은
  `week02-20260804T203835Z-4eaf4fa3c51a`

### 전체 40건 × 2 route

- 실행 시각: 2026-08-05 00:41:11~01:10:33 UTC
- Git SHA: `ca8997059ce3977c7b1a572b2d538a925d91cd5c`, clean
- run ID: `week02-20260805T004111Z-dbe6795d0a76`
- 입력: 보고서 JPEG 9장 또는 보도자료 JPEG 3장, 질문 40건, 공통 prompt
- 제외: PDF 추출 문장, 기대 답, 상대 route 응답, API key
- 고정값: prompt·schema·scorer·입력 manifest와 생성 상한
- 변경값: provider와 model route만 변경
- fallback·replay: 사용 안 함
- 승인 상한: 요청 80회, 입력 1,600,000 token, 출력 40,000 token, 재시도 0회,
  USD 0.01, 3,600초
- catalog 확인일: 2026-08-05

## 결과

### 세 사례 probe

| sample | route | 답 | `task_success` | 순수 JSON | latency | input/output token |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `r01` | Gemma | `71.6%` | 1 | 0 | 6,149ms | 3,125 / 84 |
| `r01` | Gemini | `71.6%` | 1 | 1 | 2,727ms | 10,507 / 78 |
| `r03` | Gemma | `2.6%` | 1 | 0 | 4,019ms | 3,121 / 71 |
| `r03` | Gemini | `2.6%` | 1 | 1 | 2,316ms | 10,503 / 63 |
| `r31` | Gemma | `106.0` | 0 | 0 | 4,937ms | 3,118 / 113 |
| `r31` | Gemini | `93.6` | 0 | 1 | 2,598ms | 10,500 / 76 |

두 route 모두 actual model 불일치, provider 오류, invalid output, 재시도와 예산 위반이
0건이었다. 세 사례에서 두 route의 `task_success`는 각각 2/3이다. Gemini는 순수 JSON을
3/3 반환했고 Gemma는 세 응답 모두 Markdown fence를 사용해 0/3이었다. 이 값은 출력 형식
진단이며, 그 자체로 전체 task 성공 여부나 provider 우열을 뜻하지 않는다.

Artifact에서 API secret 값과 PDF text field가 없음을 다시 검사했다. 환경 변수 이름은
어떤 secret을 사용했는지 설명하는 계보 정보로 남지만 key 값은 저장되지 않는다.

세 run의 입력 manifest, prompt와 `comparison_contract_sha256`는 동일하다. 자동 상태는
canonical 40건 중 3건만 평가했기 때문에 `inconclusive`다.

### 전체 40건 × 2 route

| 확인 항목 | NIM Gemma | AI Studio Gemini |
| --- | ---: | ---: |
| 요청·응답 | 40/40 | 40/40 |
| 품질 판정 가능 | 40/40 | 40/40 |
| `task_success` | 27/40, 67.5% | 35/40, 87.5% |
| 순수 JSON | 9/40 | 40/40 |
| schema 통과 | 36/40 | 40/40 |
| 근거 page F1 통과 | 34/40 | 37/40 |
| 평균 latency | 32,102ms | 2,840ms |
| 중앙 latency | 12,245ms | 2,412ms |
| p95 latency | 126,956ms | 3,000ms |
| input token | 111,513 | 367,337 |
| output token | 3,569 | 3,354 |
| provider 오류·재시도 | 0 / 0 | 0 / 0 |
| actual model 불일치 | 0 | 0 |
| 기록 비용 | USD 0 | USD 0 |

Gemini의 `task_success`는 20.0%p 높고 평균 latency는 약 29.3초 짧았다. 대신 input
token은 255,824개 더 사용했다. 문제별 변화는 `new_success=9`, `new_failure=1`,
`unchanged=30`이다. 비교 조건과 40쌍 coverage는 유효하지만 새 실패가 있어 자동 상태는
`fail`이다.

Gemma의 invalid output 4건은 API 오류가 아니라 JSON 구문 오류다. 그 밖에도 31/40
응답이 Markdown fence 또는 부가 텍스트를 포함했다. Gemini는 40건 모두 순수 JSON과
schema를 지켰다.

Full의 두 route는 같은 입력 manifest, prompt·schema·scorer hash와
`comparison_contract_sha256`를 기록했다. 입력 형식은 `page_images_only`이고 PDF 추출
문장 field와 API secret 값은 저장되지 않았다. Provider가 보고한 actual model은 Gemma와
Gemini 모두 40/40 기대값과 일치했다.

## 남은 실패와 원인

Gemini의 실패 5건은 성격이 다르다.

| 사례 | 관찰 | 분류 |
| --- | --- | --- |
| `r07` | 세 사례 중 `3D프린트` 대신 `스마트 코리아`를 선택 | 모델 정답 실패 |
| `r27` | `소폭 감소 전환 예상`, page 9를 반환 | 정답 허용 표현 점검 필요 |
| `r31` | 문서에 없는 2019년 1분기 값을 `93.6`으로 추측 | 답변 보류 실패 |
| `p01` | `24년 1월 11일~2월 22일, 43일간`을 반환 | 날짜 정규화 점검 필요 |
| `p07` | 기대 내용보다 넓은 답과 잘못된 page 2를 반환 | 새 실패, 사람 검토 필요 |

`p01`은 기대값 `2024-01-11~2024-02-22, 43일`과 뜻이 같지만 현재 숫자 추출 규칙이
한국어 날짜 표현을 같은 값으로 보지 않는다. `r27`도 기대 답을 포함하지만 현재 허용
기준을 넘지 못한다. 두 사례는 모델 개선과 scorer 개선을 구분해야 함을 보여 준다.

`r31`의 기대 동작은 질문이 요구한 연도·기간의 값을 이미지에서 확인할 수 없으면 답변을
보류하는 것이다. Full에서 Gemma는 깨진 JSON을, Gemini는 `93.6`을 반환했다. Gemini
응답은 구조와 숫자 형식은 유효하지만 `abstention_correct`, `answer_correct`,
`evidence_coverage`가 모두 0이다. 기대 답에 비교할 숫자가 없으므로
`numeric_match=1`은 정답이라는 뜻이 아니다.

현재 승인된 호출을 모두 사용했으므로 prompt나 scorer를 바꿔 추가 호출하지 않았다.
다음 실험에서는 보류 규칙과 날짜·짧은 의미 동등 표현의 허용 기준을 먼저 고정한 뒤,
새 hash로 저장 원응답을 재채점하고 필요할 때만 별도 승인을 받아 다시 호출한다.

## 오프라인 회귀검사

`scripts/evaluate_recorded_provider_routes.py`는 실제 개선 prompt 응답 3건을 기준 fixture에
덮어쓴 교육용 case-diff와 provider fault 6건을 만든다.

| 결과 | 건수 |
| --- | ---: |
| 새 성공 | 2 |
| 동일 | 38 |
| fault scenario | 6 |

이 40건 후보는 실제 candidate full이 아니다. `evidence_kind=test_only`이며 현재 provider
품질을 주장하지 않는다.

| fault | 처리 |
| --- | --- |
| 인증 실패 | provider 오류, 품질 분모 제외 |
| 429 뒤 성공 | 모든 시도 시간·비용 기록 |
| 반복 timeout | provider 오류, 품질 분모 제외 |
| actual model 미보고 | 응답 보존, 비교 중단 |
| actual model 불일치 | 응답 보존, 비교 중단 |
| fallback 성공 | availability로만 기록 |

## 기존 계획 점검

1. 과거 Week 2는 바로 provider 비교부터 시작했다. 평가 감사와 모델·prompt 변경 실험을
   앞에 추가했다.
2. 교육용 route B 응답을 실제 두-provider 결과처럼 읽을 여지가 있었다. 이름과 설명을
   `educational fixture`로 바꾸고 실제 prompt 응답 3건만 사용했다.
3. 오류가 있는 후보 full을 가리키는 `configs/week-01-gemma4.yaml`은 실제 recorded file이
   없어 실행할 수 없었다. 해당 설정과 잘못된 실행 안내를 제거했다.
4. Gemma 전용 prompt를 그대로 Gemini에 쓰면 공정 비교가 아니다. 모델 전용 제어문이 없는
   공통 개선 prompt로 바꿨다.
5. 원래 계획의 actual model, 동일 3건 probe, 40건씩의 전체 비교, latency·token·비용,
   fault, availability와 비교 조건 불일치 실습을 뒤쪽에 유지했다.
6. Kimi와 DiffusionGemma 탐색은 보조 route 연구다. 핵심 Week 2 완료 조건에서는 제외하고
   과거 artifact와 설정만 보존한다.

## 판정과 다음 조치

최초 실행은 `p07` 새 실패 때문에 `fail`이었다. 이후 별도 출력 폴더에서 같은 40건을
두 route에 다시 실행한 최신 결과는 새 성공 8건, 새 실패 0건으로 상대 비교가 `pass`다.
두 실행은 비교 계약 hash가 다르므로 점수나 latency를 하나의 실행처럼 합치지 않는다.

최신 재실행에서도 Gemini의 절대 실패 5건과 두 route 공통의 `r31` 답변 보류 실패가
남았다. 따라서 `release_claim=false`와 사람 결정 `HOLD`를 유지한다. 상대 비교의
`pass`는 Gemini를 채택하거나 배포한다는 뜻이 아니다. 보류 규칙과 고정 규칙 채점기의
날짜·의미 동등 표현 허용 기준을 먼저 검토해야 한다.

## 최신 재실행 검증 결과

- Ruff: 통과
- 전체 pytest: 통과
- 실제 동일 3건 두-provider probe: 요청 6/6 응답
- 두 provider `task_success`: 각각 2/3
- 실제 전체 두-provider 비교: 요청·응답 80/80
- 전체 `task_success`: Gemma 27/40, Gemini 35/40
- 문제별 변화: 새 성공 8, 새 실패 0, 동일 32
- 자동 상태 / 출시 주장 / 사람 결정: `pass` / `false` / `HOLD`
- Gemini 절대 실패: 5건 (`r07`, `r27`, `r31`, `p01`, `p07`)
- actual model mismatch: 0
- provider 오류: 0
- retry: 0
- API secret 값 저장: 0
- PDF 추출 문장 field 저장: 0
- `r31` 답변 보류 실패: 두 provider 모두 1건
- 실행 전 날짜 판정 오류: API 호출 전 발견, local calendar 기준으로 수정하고 회귀검사 통과

## 증거 파일

- 오프라인 요약: `reports/week-02/summary.json`
- 오프라인 case-diff: `reports/week-02/comparison.json`
- Provider fault: `reports/week-02/faults.json`
- 현재 scorer의 prompt A/B: `reports/week-02/gemma-prompt-comparison-current.json`
- 개선 prompt `r01` probe:
  `reports/week-02-live/probe-improved-r01-20260804-01/summary.json`
- 개선 prompt `r03` probe:
  `reports/week-02-live/probe-improved-r03-20260805-01/summary.json`
- 개선 prompt `r31` probe:
  `reports/week-02-live/probe-improved-r31-20260805-01/summary.json`
- 공통 개선 prompt 전체 40건 × 2 route:
  `reports/week-02-live/full-improved-20260805-01/summary.json`
- 재실행 `r01`, `r03`, `r31` probe:
  `reports/week-02-live/probe-improved-r01-20260805-rerun-01/summary.json`,
  `reports/week-02-live/probe-improved-r03-20260805-rerun-01/summary.json`,
  `reports/week-02-live/probe-improved-r31-20260805-rerun-01/summary.json`
- 재실행 전체 40건 × 2 route:
  `reports/week-02-live/full-improved-20260805-rerun-01/summary.json`

과거 기준-prompt full과 최초·재실행 공통 개선 prompt full은 서로 다른 실행으로 보존한다.
