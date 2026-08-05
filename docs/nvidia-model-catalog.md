# NVIDIA NIM 수업용 모델 카탈로그

확인일: 2026-08-04

아래 모델은 NVIDIA 공식 카탈로그에서 Free Endpoint가 활성화되어 있고, 수업 계정의
`/v1/models` 목록에도 있는 모델이다. `공식 언어 목록 미기재`는 모델 문서에서 지원
언어를 별도로 지정하지 않았다는 뜻이다.

## 멀티모달 모델

| 모델 | 개발사 | 규모 | Context | 입력 | 출력 | 공식 언어 정보 | 주요 활용 |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| [`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`](https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning) | NVIDIA | 33B/A3.1B | 262K | text·image·video·audio | text | 영어만 | PDF Q&A·OCR·표·차트·영상·음성 |
| [`nvidia/nemotron-nano-12b-v2-vl`](https://build.nvidia.com/nvidia/nemotron-nano-12b-v2-vl) | NVIDIA | 13B | 131K | text·image·video | text | 영어만 | 짧은 다중 이미지 Q&A·문서 이해 |
| [`meta/llama-3.2-11b-vision-instruct`](https://build.nvidia.com/meta/llama-3.2-11b-vision-instruct) | Meta | 11B | 131K | text·image | text | text-only 8개 언어, image+text 영어만 | 이미지 VQA·DocVQA |
| [`google/diffusiongemma-26b-a4b-it`](https://build.nvidia.com/google/diffusiongemma-26b-a4b-it) | Google | 25.2B/A3.8B | 262K | text·image·video | text | multilingual | 빠른 생성·PDF parsing·OCR·structured JSON |
| [`google/gemma-4-31b-it`](https://build.nvidia.com/google/gemma-4-31b-it) | Google | 33B | 262K | text·image·video | text | 즉시 지원 35개 이상, 사전학습 140개 이상 | 문서·이미지·영상 이해·coding·agent |
| [`minimaxai/minimax-m3`](https://build.nvidia.com/minimaxai/minimax-m3) | MiniMax | 427B | 1M | text·image·video | text | 공식 언어 목록 미기재 | 장문 멀티모달 추론·coding·tool calling |
| [`stepfun-ai/step-3.7-flash`](https://build.nvidia.com/stepfun-ai/step-3.7-flash) | StepFun | 약 200B/A11B | 262K | text·image | text | 공식 언어 목록 미기재 | 차트·GUI·coding·agent |
| [`meta/llama-3.2-90b-vision-instruct`](https://build.nvidia.com/meta/llama-3.2-90b-vision-instruct) | Meta | 89B | 131K | text·image | text | text-only 8개 언어, image+text 영어만 | 대형 VQA·DocVQA 비교 |
| [`moonshotai/kimi-k2.6`](https://build.nvidia.com/moonshotai/kimi-k2.6) | Moonshot AI | 1T | 262K | text·image·video | text | 공식 언어 목록 미기재 | 장기 agent·coding·이미지·영상 이해 |

Llama 3.2 Vision의 text-only 공식 언어는 영어, 독일어, 프랑스어, 이탈리아어,
포르투갈어, 힌디어, 스페인어, 태국어다. image+text의 공식 지원 언어는 영어다.
한국어 데이터 실습의 수업 기준 모델은 Gemma 4 31B IT다. Gemma 4 공식 카드는 35개가
넘는 언어의 즉시 지원과 140개가 넘는 언어의 사전학습을 구분해 명시한다.

### Kimi K2.6 Week 2 설정

`moonshotai/kimi-k2.6`은 NVIDIA Free Endpoint와 2026-08-04 수업 계정의
`/v1/models`에서 확인했다. JPEG·PNG 다중 이미지와 text 출력을 지원하지만 공식
한국어 지원 목록은 없다. 따라서 한국어 적합성은 모델 소개만으로 주장하지 않고 같은
AIHub 40건에서 직접 평가한다.

수업 설정은 `configs/nvidia-nim-kimi-k2.6.yaml`이다. 짧은 JSON만 필요한 과제라 Kimi의
Instant mode 권장값인 `temperature: 0.6`, `top_p: 0.95`, `thinking_mode: disabled`를
사용하고 NVIDIA 예제와 같이 `seed: 0`을 고정한다. Kimi 전용 prompt는 Gemma의
`/no_think` 지시만 제거하고 나머지 답변·근거·JSON 규칙을 유지한다. 이 route는 prompt와
sampling도 달라지므로 세 모델 표는 모델 하나만 바꾼 인과 비교가 아니라 실무 설정별
진단 결과로 해석한다.

같은 날 이 수업 계정의 실제 inference probe는 NVIDIA backend의 model function 404로
끝났다. key를 교체한 뒤 한 번 더 probe해도 같은 오류였다. 즉 `/v1/models`에 표시되는
것과 이 계정에서 호출 가능한 것은 같지 않았다. 성공 응답·actual model·usage가 없으므로
40건 full은 실행하지 않았으며, NVIDIA 계정의 Kimi endpoint 접근을 복구한 뒤 probe부터
다시 확인해야 한다.

### DiffusionGemma 26B A4B IT 대체 route

Kimi 대신 `google/diffusiongemma-26b-a4b-it`을 세 번째 route로 선택했다. 공식 모델 카드가
multilingual inference와 문서·PDF parsing, 다국어 OCR, 차트 이해, structured JSON을
명시해 이 실습 조건에 직접 맞는다. 한국어를 개별 지원 언어로 보장하는
자료는 아니므로 한국어 적합성은 실제 데이터 결과로만 판단한다.

수업 설정은 `configs/nvidia-nim-diffusiongemma.yaml`이다. NVIDIA hosted 예제의
`temperature: 1.0`, `top_p: 0.95`를 사용한다. 이번 과제는 reasoning 과정이 아닌 JSON
하나만 필요하므로 `chat_template_kwargs.enable_thinking: false`를 LiteLLM `extra_body`로
전달한다. Kimi용으로 만들었던 prompt에는 model 전용 token이 없어
`prompts/pdf-question-answer-json-only.md`로 이름을 바꾸고 두 route에서 함께 사용한다.

첫 probe에서는 9페이지 문서가 model의 prompt당 최대 이미지 8장 제한을 넘어 API가
응답 전에 거절했다. 페이지를 버리지 않고 8·9페이지를 위아래로 합친 한 이미지로 보내며,
원래 page label과 합성 이미지 byte 수·SHA-256을 결과 manifest에 남긴다. 이 입력 packing도
route 차이이므로 모델 단독 효과로 해석하지 않는다.

Packing 적용 probe는 JSON·정답·근거와 actual model을 모두 통과했다. Full 40건에서는
37건이 응답했고 17건이 `task_success`를 통과했으며, 마지막 보도자료 3건은 429로 품질
분모에서 제외했다. 합쳐진 page 8·9를 정답 근거로 쓰는 3건은 모두 실패해 packing 영향의
진단 신호가 남았지만, 별도 ablation 없이 packing만을 원인으로 단정하지 않는다.

## Text 모델

| 모델 | 개발사 | 규모 | Context | 입력 | 출력 | 공식 언어 정보 | 주요 활용 |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| [`openai/gpt-oss-20b`](https://build.nvidia.com/openai/gpt-oss-20b) | OpenAI | 21B/A3.6B | 131K | text | text | 공식 언어 목록 미기재 | 추론·수학·structured output·tool calling |
| [`deepseek-ai/deepseek-v4-flash`](https://build.nvidia.com/deepseek-ai/deepseek-v4-flash) | DeepSeek AI | 284B/A13B | 1M | text | text | 공식 언어 목록 미기재 | 빠른 coding·reasoning·agent |
| [`deepseek-ai/deepseek-v4-pro`](https://build.nvidia.com/deepseek-ai/deepseek-v4-pro) | DeepSeek AI | 1.6T/A49B | 1M | text | text | 공식 언어 목록 미기재 | 고난도 coding·reasoning·agent |
