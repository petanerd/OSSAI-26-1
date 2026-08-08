"""자동 평가 뒤 사람의 SHIP·HOLD·ROLLBACK·INVALID-RUN 결정을 기록한다."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from verifiable_ai_workflow.release_monitoring import HumanDecision, append_jsonl


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitoring-record", type=Path, required=True)
    parser.add_argument(
        "--decision", choices=("SHIP", "HOLD", "ROLLBACK", "INVALID-RUN"), required=True
    )
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--human-audit-complete", action="store_true")
    parser.add_argument("--rollback-git-sha")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lines = args.monitoring_record.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise SystemExit("monitoring record가 비어 있습니다")
    record = json.loads(lines[-1])
    decision = HumanDecision(
        timestamp=datetime.now(UTC),
        decision=args.decision,
        reviewer=args.reviewer,
        reason=args.reason,
        automated_status=record["automated_status"],
        human_audit_complete=args.human_audit_complete,
        rollback_git_sha=args.rollback_git_sha,
    )
    append_jsonl(args.output, decision)
    print(decision.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
