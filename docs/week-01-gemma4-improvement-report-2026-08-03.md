# Week 1 Gemma 4 개선 결과 보고서

> 역사적 결과: 아래 수치는 당시 PDF text 기반 scorer로 만든 실행 기록이다. 현재
> `aihub-vqa-deterministic-v2`와 metric 구성이 다르므로 새 결과와 직접 비교하지 않는다.
> raw response와 실행 계보는 보존하고, 재사용할 때는 현재 scorer로 다시 채점한다.

## 결론

2026-08-03에 같은 Gemma 4 모델과 같은 40개 질문으로 기존 prompt와 개선 prompt를
실제 NVIDIA NIM에서 비교했다. 필수 기준 통과율은 20.0%에서 67.5%로 올랐다. 모델이
근거를 못 찾은 것이 주원인이 아니라, 긴 설명 문장과 불안정한 JSON이 짧은 정답·출력
형식 채점 기준과 맞지 않았던 것이 주원인이었다.

후보 실행에서 NVIDIA HTTP 500이 1건 발생했고 새 실패도 1건 생겼다. 따라서 개선 신호는
크지만 자동 판정은 `inconclusive`이며, 이 결과만으로 후보 prompt를 채택하지 않는다.

## 무엇을 개선했는가

### 1. 정답을 짧게 쓰도록 했다

기존 prompt의 `질문에 대한 짧은 답`이라는 표현을 다음처럼 구체화했다.

- 숫자 질문: 질문의 연도·분기·항목을 반복하지 않고 값과 단위만 작성
- 날짜 질문: 날짜만 작성
- 기관·품목 질문: 기관명·품목명만 작성
- 여러 항목 질문: 요청된 개수만 쉼표로 구분

예를 들어 `2017년 증가율은 2.2%입니다` 대신 `2.2%`만 반환하게 했다. 그 결과
`answer_correct`는 22.5%에서 70.0%로, `numeric_match`는 40.0%에서 82.5%로 올랐다.

### 2. 표·차트의 인접 값 혼동을 줄이도록 했다

답하기 전에 대상·연도·기간·단위를 구분하고, 표와 차트에서 행과 열의 교차값을 확인한 뒤
같은 페이지에서 다시 확인하도록 지시했다. `aihub-report-r14`, `r25` 등은 새로 통과했다.
다만 `r15`, `r16`, `r22`에는 인접 값 또는 항목을 잘못 고른 문제가 남았다.

### 3. 근거 인용 규칙을 명확히 했다

근거에는 답을 직접 포함하는 연속된 원문만 복사하고, 말줄임표·요약·바꿔쓰기·질문 문장을
넣지 않도록 했다. 답을 직접 포함한 인용의 평균 점수인 `quote_answer_support`는
41.25%에서 80.0%로 올랐다.

### 4. JSON 예시에서 Markdown fence를 없앴다

기존 prompt는 “fence를 쓰지 말라”고 지시하면서 반환 예시는 fenced JSON으로 보여 주는
모순이 있었다. 후보 prompt는 한 줄 JSON object 예시만 사용하고 첫 글자 `{`, 마지막 글자
`}`를 다시 명시했다. 순수 JSON 응답 비율은 0.0%에서 27.5%로 올랐다.

이 부분은 아직 충분하지 않다. 후보에서도 깨진 JSON 3건과 허용하지 않은
`tool_tool_requests` 필드 1건이 나와 schema 통과율은 오히려 92.5%에서 87.5%로
낮아졌다.

### 5. 기준 결과를 덮어쓰지 않는 비교 경로를 추가했다

- 기준 prompt: [`prompts/pdf-question-answer.md`](../prompts/pdf-question-answer.md)
- 후보 prompt: [`prompts/pdf-question-answer-gemma4.md`](../prompts/pdf-question-answer-gemma4.md)
- 기준 설정: [`configs/nvidia-nim.yaml`](../configs/nvidia-nim.yaml)
- 후보 설정: [`configs/nvidia-nim-gemma4.yaml`](../configs/nvidia-nim-gemma4.yaml)

후보 응답과 결과를 별도 경로에 저장해 기존 기준 결과를 덮어쓰지 않게 했다. live runner는
위 두 NVIDIA 설정만 허용하므로 다른 임의 설정으로 승인 범위를 넓힐 수 없다.

### 6. prompt 외 변경을 잡는 비교 도구를 추가했다

[`scripts/compare_gemma_prompts.py`](../scripts/compare_gemma_prompts.py)는 두 full run의
모델, 40개 sample, 입력 manifest, Git SHA, lockfile, schema, scorer, workflow와 실행
상한이 같은지 확인한다. `--rescore-current`를 사용하면 raw observation을 현재 채점기로
다시 계산한다. 그 뒤 전체 지표 변화와 새 통과·새 실패·비교 불가 사례를 같은
`sample_id`끼리 비교한다.

비교 조건이 다르거나 provider 오류가 있으면 점수가 높아도 `pass`로 만들지 않고
`inconclusive`로 남긴다. Provider 오류는 품질 0점이 아니라 `not_comparable`이다.

## 실제 API 실행 조건

| 항목 | 값 |
| --- | --- |
| provider | NVIDIA hosted NIM |
| 요청 모델 | `nvidia_nim/google/gemma-4-31b-it` |
| 확인된 실제 모델 | `google/gemma-4-31b-it` |
| 데이터 | 같은 AIHub 질문·JPEG 40건 |
| 호출 속도 | 최대 20 RPM, 순차 호출 |
| 재시도 | 0회 |
| fallback·replay | 사용하지 않음 |
| 실행 범위 | 기준·후보 probe 각 1건, full 각 40건, 합계 82회 |
| 비용 상한 | 합계 USD 0.04 |
| 기록 비용 | USD 0 |

사용자의 작업 중 변경을 건드리지 않기 위해 동일 작업 상태를 임시 clean clone에 복제해
실행했다. 두 full run의 실행용 Git SHA는
`30edb46d24ee4ebc557efeb398d185e860264328`로 같다. 이 SHA는 사용자 branch에 만든
commit이 아니며, prompt·schema·scorer·workflow hash는 각 실행 결과에 별도로 남아 있다.

## 결과

| 지표 | 기준 | 후보 | 변화 |
| --- | ---: | ---: | ---: |
| `task_success` | 20.00% | 67.50% | +47.50%p |
| `answer_correct` | 22.50% | 70.00% | +47.50%p |
| `numeric_match` | 40.00% | 82.50% | +42.50%p |
| `json_object_only` | 0.00% | 27.50% | +27.50%p |
| `schema_validity` | 92.50% | 87.50% | -5.00%p |
| `evidence_page_f1` | 90.83% | 87.50% | -3.33%p |
| `quote_grounding` | 79.96% | 80.70% | +0.74%p |

- 기준: 8건 통과, 32건 실패
- 후보: 27건 통과, 12건 실패, 1건 판단 보류
- 사례 변화: 새 통과 20건, 새 실패 1건, 변화 없음 19건
- 기준 사용량: 입력 101,113 token, 출력 6,099 token, 약 813.2초
- 후보 사용량: 입력 108,590 token, 출력 3,400 token, 약 686.2초
- model drift: 0건

후보의 출력 token은 기준보다 44.3% 줄었다. 이는 답을 값 중심으로 짧게 쓰도록 한 변경과
일치한다.

## 남은 실패와 원인

1. `aihub-report-r24`: NVIDIA inference connection HTTP 500이다. 모델 품질 실패가 아니라
   provider 가용성 문제이며 재시도하지 않기로 한 실행 조건에 따라 판단 보류로 기록했다.
2. `aihub-report-r31`: 답변 보류가 필요한 사례에서 `106.0`을 답했고 JSON도 깨졌다. 기준은
   통과했지만 후보는 실패한 유일한 새 회귀다.
3. `aihub-report-r17`, `r31`, `aihub-press-p08`: JSON 구문 오류다.
4. `aihub-press-p06`: 허용하지 않은 `tool_tool_requests` 필드를 반환했다.
5. `aihub-report-r22` 등: 표의 인접 값을 선택하거나 질문이 요구한 항목을 정확히 구분하지
   못했다.
6. `aihub-report-r28`: 정답과 근거 페이지는 맞았지만 근거 문구 점수가 필수 기준에 조금
   못 미쳤다.

## 판정과 다음 조치

자동 상태는 `inconclusive`다. 후보 실행에 provider 오류가 있어 prompt만의 효과라고
공식 판정할 수 없고, 새 실패 1건도 남아 있기 때문이다.

다음 실험에서는 다른 조건을 바꾸지 않고 아래 두 항목만 prompt에 보강한다.

1. 답변 보류 조건을 먼저 확인하고, 보류 사례에서는 숫자를 추측하지 않기
2. JSON field 이름을 고정하고 닫는 괄호·대괄호를 최종 확인하기

이미지 해상도, schema와 채점기는 이번 결과와 원인을 섞지 않기 위해 다음 실험에서도
그대로 둔다.

## 증거 파일

- 기준 full summary: `reports/week-01-nvidia/runs/week01-20260803T135626Z-0c8a3821/summary.json`
- 후보 full summary: `reports/week-01-nvidia-gemma4/runs/week01-20260803T141015Z-9485bcce/summary.json`
- 사례별 prompt 비교: `reports/week-02/gemma-prompt-comparison-current.json`
- [실행 승인과 누적 사용량](live-api-approval.md)
- [Week 1 실행·재현 절차](week-01-lab.md#gemma-4-prompt-후보를-따로-평가하기)

`reports/`는 Git에서 제외되는 로컬 live evidence다. 새 checkout에는 자동으로 따라가지
않으므로 공유할 때는 이 보고서와 함께 해당 run directory를 별도로 보존해야 한다.
