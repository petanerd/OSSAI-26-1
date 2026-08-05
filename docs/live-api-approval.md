# Week 1~2 실제 API 실행 승인 범위

## 목적

실제 API 실습은 로컬 저장 응답이 아니라 모델 제공사의 서버로 입력을 보낸다. 이 문서는
Week 1~2에서 어떤 자료를 어느 서비스로 보내는지 보여 주고, 승인 범위 밖의 호출을 막기
위한 확인표다. 실행 상한의 기준 파일은
[`configs/live-egress.yaml`](../configs/live-egress.yaml)이다.

## 현재 결과

- 2026-08-01 Week 1 Gemma 4 전체 40건은 모두 응답했고 provider 오류와 actual model
  불일치는 0건이었다. 현재 이미지 전용 채점기로 같은 원응답을 계산하면 8/40건이
  통과한다.
- 2026-08-03 같은 Gemma 4에서 기준·개선 prompt를 각각 40건 실행했다. 현재 채점기로
  기준은 9/40, 개선 prompt는 품질 판정 가능한 39건 중 28건이 통과했다. 후보의 NVIDIA
  HTTP 500 한 건 때문에 자동 비교는 `inconclusive`다.
- 2026-08-05 공통 개선 prompt로 NVIDIA NIM Gemma와 Google AI Studio Gemini에
  AIHub 질문 40건씩 총 80회를 재실행했다. 두 route 모두 40/40 응답했고 API 제공사 오류,
  재시도와 actual model 불일치는 0건이었다.
- 전체 `task_success`는 Gemma 27/40, Gemini 35/40이다. 새 실패가 없어 상대 비교의 자동
  상태는 `pass`지만, 이는 출시 승인이 아니다. 두 route의 `aihub-report-r31` 답변 보류
  실패와 Gemini의 절대 실패 5건이 남아 `release_claim=false`, 사람 결정은 `HOLD`다.
- 실제 실행 결과는 로컬
  `reports/week-02-live/full-improved-20260805-rerun-01/summary.json`에 저장했다. API key
  값과 PDF 추출 문장은 결과 파일에 포함하지 않았다.

## 고정 provider와 model

| 용도 | 요청 model | 확인할 actual model | endpoint | key 환경 변수 |
| --- | --- | --- | --- | --- |
| Week 1·2 NIM | `nvidia_nim/google/gemma-4-31b-it` | `google/gemma-4-31b-it` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_NIM_API_KEY` |
| Week 2 Gemini | `gemini/gemini-3.5-flash-lite` | `gemini-3.5-flash-lite` | `https://generativelanguage.googleapis.com/v1beta` | `GEMINI_API_KEY` |

## 외부로 보내는 자료

| 주차 | 외부 서비스 | 보내는 자료 | 보내지 않는 자료 |
| --- | --- | --- | --- |
| 1 | NVIDIA NIM | AIHub PDF에서 만든 페이지 JPEG, 질문, prompt | PDF 추출 문장, 기대 정답, scorer 결과, key |
| 2 | NVIDIA NIM·Google AI Studio | 같은 페이지 JPEG·질문·공통 prompt | PDF 추출 문장, 기대 정답, 상대 route 응답, key |

AIHub 자료에는 `AIHub 이용정책 적용` 조건이 계속 적용된다. Gemini 무료 등급의 입력과
출력은 Google 제품 개선에 사용될 수 있으므로 이 조건을 확인한 뒤 승인해야 한다.

## 실행 전에 확인할 조건

1. 위 자료를 해당 외부 서비스로 보내도 되는가
2. model이 실행 당일 공식 catalog에 있는가
3. key·quota와 당일 RPM·RPD·TPM이 준비됐는가
4. 요청·입력 token·출력 token·재시도·비용·전체 시간 상한이 양수로 고정됐는가
5. Git 상태가 깨끗하고 새 출력 경로를 사용하는가

Probe는 full 전에 raw response, actual model, token, 비용과 오류를 확인하는 별도
실행이다. Probe 성공을 전체 품질 결과로 확대 해석하지 않는다.

| 실행 | probe 요청 / 비용 / 시간 | full 요청 / 비용 / 시간 |
| --- | --- | --- |
| Week 1 task | 1 / USD 0.01 / 120초 | 40 / USD 0.01 / 7,200초 |
| Week 1 prompt A/B | 2 / USD 0.02 / 240초 | 80 / USD 0.02 / 14,400초 |
| Week 2 두 provider | 2 / USD 0.01 / 240초 | 80 / USD 0.01 / 3,600초 |

## 실행 순서

```text
payload·목적지·상한 승인
→ clean Git와 고정 조건 hash 확인
→ model catalog·key·quota 확인
→ 가장 작은 probe
→ raw 응답·actual model·token·비용·오류 확인
→ 승인 상한 안에서 full 실행
→ deterministic scorer 적용
→ 사람의 SHIP·HOLD·ROLLBACK 결정
```

Provider 오류와 actual model 불일치는 오답 0점으로 바꾸지 않고 비교 불가로 보존한다.
Fixture와 replay 결과는 계속 `test_only`다.
