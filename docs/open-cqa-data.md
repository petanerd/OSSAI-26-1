# OpenCQA 데이터 준비

Week 3은 설명형 차트 질의응답 데이터인
[OpenCQA](https://github.com/vis-nlp/OpenCQA)를 사용한다. 저장소에는 원본 이미지나 답을
복사해 넣지 않고, 사용할 30개 ID와 원본 revision만 기록한다.

후보 A와 B는 두 모델의 출력이 아니다. OpenCQA가 제공하는 `abstractive_answer`와
`extractive_answer`를 ID hash로 섞은 것이다. 기준 답은 `abstractive_answer`다. 두 답이
완전히 같은 사례는 제외하고, 차이의 크기가 한 split에만 몰리지 않도록 ID를 골랐다.

## 1. 원본 받기

프로젝트 밖에서 공식 저장소를 받는다.

```bash
git clone https://github.com/vis-nlp/OpenCQA.git ../OpenCQA
git -C ../OpenCQA checkout 28db0fd26a12fd376f6c30b7feb8a4db32313424
```

이 실습이 확인한 원본은 GPL-3.0이며, 선택한 ID와 revision은
`data/opencqa/week-03-selection.yaml`에 있다. 다른 revision을 쓰면 준비 명령이 중단된다.

## 2. 실습 자료 만들기

```bash
uv run --locked python scripts/prepare_opencqa.py --source-root ../OpenCQA
```

다음 파일은 `local-data/opencqa/`에 생기며 Git에 올라가지 않는다.

```text
images/                       선택한 차트 이미지 30개
week-03-pairs.jsonl           질문, 기준 답, 후보 A와 B
week-03-reviewer-1.csv        첫 번째 사람의 독립 평가표
week-03-reviewer-2.csv        두 번째 사람의 독립 평가표
```

`week-03-pairs.jsonl`에는 OpenCQA의 article, summary, OCR을 넣지 않는다. 작업 모델은 차트
이미지와 질문만 받아야 하며, 기준 답은 모델 출력 평가에만 사용한다.

기존 평가표가 있으면 준비 명령은 사람 라벨을 덮어쓰지 않는다. 현재 선택 ID와 기존 평가표
ID가 다르면 중단되므로, 이전 평가표를 별도 보관한 뒤 다시 준비한다.

## 3. 준비 확인

```bash
uv run --locked python scripts/inspect_judge_pair.py --number 1
```

출력된 `image_path`의 차트를 직접 열어 질문과 두 후보가 실제 그림의 수치에 맞는지 확인한다.
