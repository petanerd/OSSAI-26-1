"""OpenCQA 한 쌍을 사람이 읽는 순서대로 출력한다."""

from __future__ import annotations

import argparse
from pathlib import Path

from verifiable_ai_workflow.judge_calibration import load_pairs

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--number", type=int, default=1)
    args = parser.parse_args()
    pairs = load_pairs(PROJECT_ROOT / "local-data/opencqa/week-03-pairs.jsonl")
    if not 1 <= args.number <= len(pairs):
        raise SystemExit(f"--number는 1부터 {len(pairs)}까지입니다")
    pair = pairs[args.number - 1]
    print(f"[차트] {pair.image_path}")
    print(f"[질문] {pair.question}")
    print(f"[후보 A] {pair.candidate_a}")
    print(f"[후보 B] {pair.candidate_b}")
    print(f"[비교 기준 답] {pair.reference_answer}")
    print("[사람 판단] candidate_a / tie / candidate_b 중 하나를 고릅니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
