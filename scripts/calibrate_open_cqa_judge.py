"""OpenCQA 사람 라벨과 반복 Judge 결과를 비교한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from verifiable_ai_workflow.judge_calibration import (
    calibrate,
    load_human_labels,
    load_judge_trials,
    load_pairs,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pairs",
        type=Path,
        default=PROJECT_ROOT / "local-data/opencqa/week-03-pairs.jsonl",
    )
    parser.add_argument(
        "--human-labels",
        type=Path,
        default=PROJECT_ROOT / "local-data/opencqa/week-03-human-labels.csv",
    )
    parser.add_argument("--judge-results", type=Path, required=True)
    parser.add_argument("--pair-limit", type=int)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports/week-03/calibration.json",
    )
    args = parser.parse_args()
    pairs = load_pairs(args.pairs)
    labels = load_human_labels(args.human_labels)
    trials = load_judge_trials(args.judge_results)
    if args.pair_limit is not None:
        if not 1 <= args.pair_limit <= len(pairs):
            raise SystemExit(f"--pair-limit는 1부터 {len(pairs)}까지입니다")
        pairs = pairs[: args.pair_limit]
        selected = {pair.pair_id for pair in pairs}
        labels = [label for label in labels if label.pair_id in selected]
        trials = [trial for trial in trials if trial.pair_id in selected]

    run_summary_path = args.judge_results.with_name("summary.json")
    run_summary = (
        json.loads(run_summary_path.read_text(encoding="utf-8"))
        if run_summary_path.is_file()
        else {}
    )
    pairs_sha256 = hashlib.sha256(args.pairs.read_bytes()).hexdigest()
    live_quality = bool(
        len(pairs) == 30
        and run_summary.get("status") == "completed"
        and run_summary.get("evidence_kind") == "live_quality"
        and run_summary.get("pair_count") == 30
        and run_summary.get("git_dirty") is False
        and run_summary.get("pairs_sha256") == pairs_sha256
    )
    summary = calibrate(
        pairs,
        labels,
        trials,
        live_quality=live_quality,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    print(
        f"30쌍={summary.pair_count}, 사람 일치도={summary.human_human_weighted_kappa:.3f}, "
        f"Judge 일치율={summary.judge_human_agreement:.3f}, 사용={summary.recommended_use}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
