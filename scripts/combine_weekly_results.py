"""weekly validation 8건과 이미지 challenge 5건을 한 summary로 합친다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verifiable_ai_workflow.release_monitoring import combine_weekly_results


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-summary", type=Path, required=True)
    parser.add_argument("--validation-calls", type=Path, required=True)
    parser.add_argument("--robustness-summary", type=Path, required=True)
    parser.add_argument("--robustness-calls", type=Path, required=True)
    parser.add_argument("--robustness-scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = combine_weekly_results(
        _load(args.validation_summary),
        _load(args.robustness_summary),
        _load(args.robustness_scores),
    )
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (args.output / "calls.jsonl").open("w", encoding="utf-8") as target:
        for source in (args.validation_calls, args.robustness_calls):
            target.write(source.read_text(encoding="utf-8"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
