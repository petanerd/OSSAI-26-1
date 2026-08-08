"""한 평가 실행을 모니터링 history JSONL 한 줄로 추가한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verifiable_ai_workflow.release_monitoring import (
    append_jsonl,
    build_monitoring_record,
    latest_change,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("nightly", "weekly"), required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--calls", type=Path, required=True)
    parser.add_argument(
        "--history",
        type=Path,
        default=PROJECT_ROOT / "reports/evaluation-history.jsonl",
    )
    args = parser.parse_args()
    record = build_monitoring_record(
        profile=args.profile,
        summary_path=args.summary,
        calls_path=args.calls,
        config_path=PROJECT_ROOT / "configs/week-06.yaml",
    )
    append_jsonl(args.history, record)
    print(record.model_dump_json(indent=2))
    change = latest_change(args.history)
    if change is not None:
        print("직전 실행 대비: " + json.dumps(change, ensure_ascii=False))
    return 0 if record.automated_status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
