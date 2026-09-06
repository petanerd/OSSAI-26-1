"""자동 평가 뒤 사람의 SHIP·HOLD·ROLLBACK·INVALID-RUN 결정을 기록한다."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from verifiable_ai_workflow.release_monitoring import (
    HumanAudit,
    HumanDecision,
    MonitoringRecord,
    append_jsonl,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _require_rollback_ancestor(rollback_sha: str, current_sha: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", rollback_sha, current_sha],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit("rollback Git SHA는 현재 실행 commit의 이전 commit이어야 합니다")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitoring-record", type=Path, required=True)
    parser.add_argument(
        "--decision", choices=("SHIP", "HOLD", "ROLLBACK", "INVALID-RUN"), required=True
    )
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--human-audit", type=Path)
    parser.add_argument("--rollback-git-sha")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lines = args.monitoring_record.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise SystemExit("monitoring record가 비어 있습니다")
    record_line = lines[-1]
    record = MonitoringRecord.model_validate_json(record_line)
    if args.decision == "ROLLBACK" and args.rollback_git_sha:
        _require_rollback_ancestor(args.rollback_git_sha, record.git_sha)
    audit = (
        HumanAudit.model_validate_json(args.human_audit.read_text(encoding="utf-8"))
        if args.human_audit
        else None
    )
    decision = HumanDecision(
        timestamp=datetime.now(UTC),
        decision=args.decision,
        reviewer=args.reviewer,
        reason=args.reason,
        monitoring_record_sha256=hashlib.sha256(record_line.encode("utf-8")).hexdigest(),
        monitoring_timestamp=record.timestamp,
        profile=record.profile,
        git_sha=record.git_sha,
        requested_model=record.requested_model,
        actual_model=record.actual_model,
        prompt_sha256=record.prompt_sha256,
        selected_prompt_sha256=record.selected_prompt_sha256,
        agent_prompt_sha256=record.agent_prompt_sha256,
        sample_ids=record.sample_ids,
        high_risk_sample_ids=record.high_risk_sample_ids,
        automated_status=record.automated_status,
        human_audit=audit,
        rollback_git_sha=args.rollback_git_sha,
    )
    append_jsonl(args.output, decision)
    print(decision.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
