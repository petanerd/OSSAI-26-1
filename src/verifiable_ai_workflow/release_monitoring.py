"""평가 요약을 작은 시계열 한 줄과 사람 결정으로 바꾼다."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MonitoringRecord(StrictModel):
    timestamp: datetime
    profile: Literal["nightly", "weekly"]
    git_sha: str
    model: str
    prompt_sha256: str
    record_count: int = Field(ge=0)
    task_success: float = Field(ge=0, le=1)
    p95_latency_ms: float = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    error_count: int = Field(ge=0)
    automated_status: Literal["pass", "fail", "inconclusive"]


class HumanDecision(StrictModel):
    timestamp: datetime
    decision: Literal["SHIP", "HOLD", "ROLLBACK", "INVALID-RUN"]
    reviewer: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    automated_status: Literal["pass", "fail", "inconclusive"]
    human_audit_complete: bool
    rollback_git_sha: str | None = None

    @model_validator(mode="after")
    def decision_has_required_evidence(self) -> HumanDecision:
        if self.decision == "SHIP" and (
            self.automated_status != "pass" or not self.human_audit_complete
        ):
            raise ValueError("SHIP에는 자동 pass와 완료된 사람 감사가 모두 필요합니다")
        if self.decision == "ROLLBACK" and not self.rollback_git_sha:
            raise ValueError("ROLLBACK에는 되돌릴 Git SHA가 필요합니다")
        if self.decision == "INVALID-RUN" and self.automated_status != "inconclusive":
            raise ValueError("INVALID-RUN은 inconclusive 실행에만 사용합니다")
        return self


def _load_jsonl(path: str | Path) -> list[dict]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def build_monitoring_record(
    *,
    profile: Literal["nightly", "weekly"],
    summary_path: str | Path,
    calls_path: str | Path,
    config_path: str | Path,
    timestamp: datetime | None = None,
) -> MonitoringRecord:
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    calls = _load_jsonl(calls_path)
    provenance = summary.get("provenance", {})
    record_count = int(summary.get("record_count", summary.get("total", 0)))
    task_success = summary.get("score_averages", {}).get("task_success")
    if task_success is None and summary.get("total"):
        task_success = summary.get("passed", 0) / summary["total"]
    task_success = float(task_success or 0.0)
    errors = max(
        int(summary.get("provider_error_count", 0)),
        sum(bool(call.get("error_type")) for call in calls),
    )
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))["profiles"][profile]
    complete = record_count == config["expected_records"]
    if not complete:
        status: Literal["pass", "fail", "inconclusive"] = "inconclusive"
    elif (
        task_success < config["minimum_task_success"]
        or errors > config["maximum_errors"]
        or _p95([float(call.get("latency_ms") or 0) for call in calls])
        > config["maximum_p95_latency_ms"]
    ):
        status = "fail"
    else:
        status = "pass"
    actual_models = summary.get("actual_models") or []
    model = (
        actual_models[0]
        if len(actual_models) == 1
        else summary.get("model") or summary.get("requested_model") or "unknown"
    )
    return MonitoringRecord(
        timestamp=timestamp or datetime.now(UTC),
        profile=profile,
        git_sha=summary.get("git_sha") or provenance.get("git_sha") or "unknown",
        model=model,
        prompt_sha256=summary.get("prompt_sha256") or provenance.get("prompt_sha256") or "unknown",
        record_count=record_count,
        task_success=task_success,
        p95_latency_ms=_p95([float(call.get("latency_ms") or 0) for call in calls]),
        input_tokens=sum(int(call.get("input_tokens") or 0) for call in calls),
        output_tokens=sum(int(call.get("output_tokens") or 0) for call in calls),
        cost_usd=sum(float(call.get("actual_cost_usd") or 0) for call in calls),
        error_count=errors,
        automated_status=status,
    )


def append_jsonl(path: str | Path, value: BaseModel) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(value.model_dump_json() + "\n")


def latest_change(path: str | Path) -> dict[str, float] | None:
    records = [MonitoringRecord.model_validate(item) for item in _load_jsonl(path)]
    if len(records) < 2:
        return None
    before, after = records[-2], records[-1]
    return {
        "task_success": after.task_success - before.task_success,
        "p95_latency_ms": after.p95_latency_ms - before.p95_latency_ms,
        "input_tokens": float(after.input_tokens - before.input_tokens),
        "output_tokens": float(after.output_tokens - before.output_tokens),
        "cost_usd": after.cost_usd - before.cost_usd,
        "error_count": float(after.error_count - before.error_count),
    }


def combine_weekly_results(
    validation_summary: dict,
    robustness_summary: dict,
    robustness_scores: list[dict],
) -> dict:
    if validation_summary.get("record_count") != 8:
        raise ValueError("weekly validation 결과는 8건이어야 합니다")
    if robustness_summary.get("record_count") != 5 or len(robustness_scores) != 5:
        raise ValueError("weekly challenge 결과는 원본과 변형을 합쳐 5건이어야 합니다")
    validation_git = validation_summary.get("provenance", {}).get("git_sha")
    if validation_git != robustness_summary.get("git_sha"):
        raise ValueError("validation과 challenge의 Git SHA가 다릅니다")
    validation_success = validation_summary["score_averages"]["task_success"]
    robustness_success = sum(item["status"] == "passed" for item in robustness_scores) / 5
    return {
        "status": "complete",
        "record_count": 13,
        "score_averages": {
            "task_success": (validation_success * 8 + robustness_success * 5) / 13
        },
        "provider_error_count": validation_summary.get("provider_error_count", 0),
        "requested_model": validation_summary.get("requested_model"),
        "actual_models": validation_summary.get("actual_models", []),
        "provenance": validation_summary.get("provenance", {}),
        "validation_count": 8,
        "challenge_count": 5,
    }
