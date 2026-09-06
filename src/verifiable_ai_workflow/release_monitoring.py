"""주차별 실제 평가를 검증하고 작은 이력과 사람 결정으로 바꾼다."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

SHA40 = r"^[0-9a-f]{40}$"
SHA64 = r"^[0-9a-f]{64}$"
SOURCE_STATUSES = {"pass", "fail", "inconclusive"}
OBSERVED_STATUSES = {"complete", "partial", "blocked", "inconclusive", "not_run"}
AGENT_MUST_PASS = {
    "tool_contract",
    "authorization_safety",
    "idempotency_safety",
    "final_answer",
    "tool_budget",
    "workflow_lineage",
    "task_success",
}
NIGHTLY_SAMPLE_IDS = ["W5-06-idempotent-retry"]
WEEKLY_ROBUSTNESS_SAMPLE_ID = "884"
WEEKLY_ROBUSTNESS_FAMILY_ID = "opencqa-val-884"
WEEKLY_VARIANT_IDS = ["original", "rotate-2", "jpeg-60", "crop-left", "occlude-answer"]
WEEKLY_AGENT_IDS = [
    "W5-01-direct",
    "W5-02-calculator",
    "W5-03-lookup",
    "W5-04-ticket",
    "W5-05-pii-denial",
    "W5-06-idempotent-retry",
]
WEEKLY_HIGH_RISK_IDS = WEEKLY_AGENT_IDS[3:]
PROFILE_SAMPLE_IDS = {
    "nightly": NIGHTLY_SAMPLE_IDS,
    "weekly": [
        *(f"{WEEKLY_ROBUSTNESS_SAMPLE_ID}:{variant_id}" for variant_id in WEEKLY_VARIANT_IDS),
        *WEEKLY_AGENT_IDS,
    ],
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MonitoringRecord(StrictModel):
    timestamp: AwareDatetime
    profile: Literal["nightly", "weekly"]
    git_sha: str = Field(pattern=SHA40)
    requested_model: str = Field(min_length=1)
    expected_actual_model: str = Field(min_length=1)
    actual_model: str | None
    model_identity_matches: bool
    prompt_sha256: str = Field(pattern=SHA64)
    selected_prompt_sha256: str | None = Field(default=None, pattern=SHA64)
    agent_prompt_sha256: str | None = Field(default=None, pattern=SHA64)
    sample_ids: list[str]
    high_risk_sample_ids: list[str]
    component_statuses: dict[str, Literal["pass", "fail", "inconclusive"]] = Field(
        default_factory=dict
    )
    component_record_counts: dict[str, int] = Field(default_factory=dict)
    record_count: int = Field(ge=0)
    task_success: float | None = Field(default=None, ge=0, le=1)
    p95_latency_ms: float = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    error_count: int = Field(ge=0)
    automated_status: Literal["pass", "fail", "inconclusive"]

    @model_validator(mode="after")
    def matches_profile_contract(self) -> MonitoringRecord:
        if self.profile == "weekly" and (
            self.selected_prompt_sha256 is None or self.agent_prompt_sha256 is None
        ):
            raise ValueError("weekly 이력에는 이미지·agent prompt hash가 모두 필요합니다")
        expected_ids = PROFILE_SAMPLE_IDS[self.profile]
        expected_high_risk = (
            WEEKLY_HIGH_RISK_IDS if self.profile == "weekly" else NIGHTLY_SAMPLE_IDS
        )
        if self.sample_ids != expected_ids:
            raise ValueError(f"{self.profile} monitoring sample_id가 고정 계약과 다릅니다")
        if self.high_risk_sample_ids != expected_high_risk:
            raise ValueError(f"{self.profile} 고위험 sample_id가 고정 계약과 다릅니다")
        component_targets = {"robustness": 5, "agent": 6}
        if self.profile == "weekly":
            if (
                set(self.component_statuses) != set(component_targets)
                or set(self.component_record_counts) != set(component_targets)
            ):
                raise ValueError("weekly 이력에는 두 구성요소 상태와 건수가 모두 필요합니다")
            if any(
                count < 0 or count > component_targets[name]
                for name, count in self.component_record_counts.items()
            ) or sum(self.component_record_counts.values()) != self.record_count:
                raise ValueError("weekly 구성요소 건수가 고정 target 또는 전체 건수와 다릅니다")
        elif self.component_statuses or self.component_record_counts:
            raise ValueError("nightly 이력에는 weekly 구성요소 상태를 넣지 않습니다")
        if self.record_count > len(expected_ids):
            raise ValueError("monitoring record_count가 고정 target보다 큽니다")
        if self.automated_status == "inconclusive":
            if self.task_success is not None:
                raise ValueError("inconclusive 실행은 task_success를 품질 점수로 저장하지 않습니다")
        elif self.task_success is None:
            raise ValueError("pass/fail 실행에는 task_success가 필요합니다")
        if self.automated_status == "pass" and (
            self.record_count != len(expected_ids)
            or not self.model_identity_matches
            or self.actual_model != self.expected_actual_model
            or self.error_count != 0
            or self.task_success != 1
            or (
                self.profile == "weekly"
                and any(status != "pass" for status in self.component_statuses.values())
            )
        ):
            raise ValueError("pass monitoring 기록이 profile의 전체 통과 계약을 만족하지 않습니다")
        return self


class HumanAudit(StrictModel):
    completed_at: AwareDatetime
    reviewed_sample_ids: list[str] = Field(min_length=1)
    random_sample_ids: list[str] = Field(min_length=1)
    false_pass_sample_ids: list[str] = Field(default_factory=list)
    notes: str = Field(min_length=1)

    @field_validator("reviewed_sample_ids", "random_sample_ids", "false_pass_sample_ids")
    @classmethod
    def ids_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("감사 sample_id는 중복될 수 없습니다")
        return value


class HumanDecision(StrictModel):
    timestamp: AwareDatetime
    decision: Literal["SHIP", "HOLD", "ROLLBACK", "INVALID-RUN"]
    reviewer: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    monitoring_record_sha256: str = Field(pattern=SHA64)
    monitoring_timestamp: AwareDatetime
    profile: Literal["nightly", "weekly"]
    git_sha: str = Field(pattern=SHA40)
    requested_model: str = Field(min_length=1)
    actual_model: str | None
    prompt_sha256: str = Field(pattern=SHA64)
    selected_prompt_sha256: str | None = Field(default=None, pattern=SHA64)
    agent_prompt_sha256: str | None = Field(default=None, pattern=SHA64)
    sample_ids: list[str]
    high_risk_sample_ids: list[str]
    automated_status: Literal["pass", "fail", "inconclusive"]
    human_audit: HumanAudit | None = None
    rollback_git_sha: str | None = Field(default=None, pattern=SHA40)

    @model_validator(mode="after")
    def has_required_evidence(self) -> HumanDecision:
        if self.timestamp < self.monitoring_timestamp:
            raise ValueError("사람 결정 시각은 monitoring 기록보다 빠를 수 없습니다")
        if self.human_audit is not None:
            reviewed = set(self.human_audit.reviewed_sample_ids)
            if self.human_audit.completed_at < self.monitoring_timestamp:
                raise ValueError("사람 감사는 monitoring 실행 뒤에 완료해야 합니다")
            if self.human_audit.completed_at > self.timestamp:
                raise ValueError("사람 감사 완료 시각은 결정 시각보다 늦을 수 없습니다")
            if not reviewed <= set(self.sample_ids):
                raise ValueError("감사 대상은 monitoring sample_id 안에서 골라야 합니다")
            if not set(self.human_audit.random_sample_ids) <= reviewed:
                raise ValueError("무작위 감사 표본은 실제 검토 목록에 포함돼야 합니다")
            if not set(self.human_audit.random_sample_ids) - set(self.high_risk_sample_ids):
                raise ValueError("무작위 감사에는 고위험 의무 검토 밖의 표본이 필요합니다")
            if not set(self.human_audit.false_pass_sample_ids) <= reviewed:
                raise ValueError("false pass 사례는 실제 검토 목록에 포함돼야 합니다")
            if not set(self.high_risk_sample_ids) <= reviewed:
                raise ValueError("고위험 사례는 전부 사람이 검토해야 합니다")
        if self.decision == "SHIP" and (
            self.profile != "weekly"
            or self.automated_status != "pass"
            or self.sample_ids != PROFILE_SAMPLE_IDS["weekly"]
            or self.high_risk_sample_ids != WEEKLY_HIGH_RISK_IDS
            or self.human_audit is None
            or self.human_audit.false_pass_sample_ids
        ):
            raise ValueError("SHIP에는 weekly 자동 pass와 false pass 없는 구조화 감사가 필요합니다")
        if self.decision == "ROLLBACK":
            if not self.rollback_git_sha or self.rollback_git_sha == self.git_sha:
                raise ValueError("ROLLBACK에는 현재와 다른 Git SHA가 필요합니다")
        elif self.rollback_git_sha is not None:
            raise ValueError("rollback Git SHA는 ROLLBACK 결정에만 기록합니다")
        if self.decision == "INVALID-RUN" and self.automated_status != "inconclusive":
            raise ValueError("INVALID-RUN은 inconclusive 실행에만 사용합니다")
        return self


def _load_jsonl(path: str | Path) -> list[dict]:
    source = Path(path)
    if not source.is_file():
        return []
    return [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def _require_sha(value: object, *, length: int, name: str) -> str:
    pattern = SHA40 if length == 40 else SHA64
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError(f"{name}은 {length}자리 소문자 hex여야 합니다")
    return value


def require_bound_artifact(
    summary: dict,
    name: str,
    path: str | Path,
    *,
    required: bool,
) -> None:
    artifacts = summary.get("artifact_sha256")
    if not isinstance(artifacts, dict) or name not in artifacts:
        raise ValueError(f"summary에 {name} hash가 없습니다")
    source = Path(path)
    expected = artifacts[name]
    if expected is None:
        if required or source.exists():
            raise ValueError(f"{name}의 파일 유무와 summary hash가 다릅니다")
        return
    expected = _require_sha(expected, length=64, name=f"{name} hash")
    if not source.is_file():
        raise ValueError(f"hash에 기록된 {name} 파일이 없습니다")
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ValueError(f"{name} hash가 summary와 다릅니다")


def _require_source_summary(summary: dict, *, profile: str) -> tuple[str, str, bool]:
    if summary.get("profile") != profile:
        raise ValueError(f"source profile은 {profile}이어야 합니다")
    if summary.get("evidence_kind") != "live_quality":
        raise ValueError("weekly source는 live_quality여야 합니다")
    status = summary.get("status")
    observed_status = summary.get("observed_status")
    if status not in SOURCE_STATUSES or observed_status not in OBSERVED_STATUSES:
        raise ValueError("source status 또는 observed_status가 올바르지 않습니다")
    _require_sha(
        summary.get("git_sha") or summary.get("provenance", {}).get("git_sha"),
        length=40,
        name="git_sha",
    )
    requested_model = summary.get("requested_model")
    expected_model = summary.get("expected_actual_model")
    actual_models = summary.get("actual_models")
    if not isinstance(requested_model, str) or not requested_model:
        raise ValueError("source requested_model이 필요합니다")
    if not isinstance(expected_model, str) or not expected_model:
        raise ValueError("source expected_actual_model이 필요합니다")
    if not isinstance(actual_models, list) or any(
        not isinstance(item, str) or not item for item in actual_models
    ):
        raise ValueError("source actual_models는 문자열 목록이어야 합니다")
    identity_matches = (
        actual_models == [expected_model]
        and not summary.get("model_drift_count", 0)
        and not summary.get("provider_error_count", 0)
    )
    return status, observed_status, identity_matches


def _require_target_ids(summary: dict, expected: list[str]) -> int:
    target_ids = summary.get("target_sample_ids")
    completed_ids = summary.get("completed_sample_ids")
    if target_ids != expected or summary.get("target_count") != len(expected):
        raise ValueError("source target sample_id가 주차 계약과 다릅니다")
    if not isinstance(completed_ids, list) or len(completed_ids) != len(set(completed_ids)):
        raise ValueError("source completed sample_id가 없거나 중복됐습니다")
    if not set(completed_ids) <= set(expected):
        raise ValueError("source target 밖의 completed sample_id가 있습니다")
    record_count = int(summary.get("record_count", -1))
    if record_count != len(completed_ids):
        raise ValueError("source record_count와 completed sample_id 수가 다릅니다")
    return record_count


def _calls_match_summary(summary: dict, calls: list[dict], sample_ids: list[str]) -> bool:
    def nonnegative_number(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0

    successful = [call for call in calls if not call.get("error_type")]
    if len(successful) < len(sample_ids):
        return False
    for call in successful:
        if (
            call.get("requested_model") != summary["requested_model"]
            or call.get("expected_actual_model") != summary["expected_actual_model"]
            or call.get("actual_model") != summary["expected_actual_model"]
            or call.get("actual_model_matches_expected") is not True
            or call.get("provider_status") not in {"provider_response_received", "success"}
            or call.get("raw_response") is None
            or not isinstance(call.get("response_received_at"), str)
            or not call["response_received_at"]
            or not isinstance(call.get("sample_id"), str)
            or not call["sample_id"]
            or not nonnegative_number(call.get("latency_ms"))
            or type(call.get("input_tokens")) is not int
            or call["input_tokens"] < 0
            or type(call.get("output_tokens")) is not int
            or call["output_tokens"] < 0
            or not nonnegative_number(call.get("actual_cost_usd"))
        ):
            return False
    return (
        set(call["sample_id"] for call in successful) == set(sample_ids)
        and sorted({call["actual_model"] for call in successful}) == summary["actual_models"]
    )


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
    config_source = Path(config_path)
    if summary.get("release_config_sha256") != hashlib.sha256(
        config_source.read_bytes()
    ).hexdigest():
        raise ValueError("summary의 Week 6 release config hash가 현재 파일과 다릅니다")
    source_status, observed_status, identity_matches = _require_source_summary(
        summary, profile=profile
    )
    require_bound_artifact(summary, Path(calls_path).name, calls_path, required=True)
    provenance = summary.get("provenance", {})
    git_sha = _require_sha(
        summary.get("git_sha") or provenance.get("git_sha"), length=40, name="git_sha"
    )
    target_ids = summary.get("sample_ids") or summary.get("target_sample_ids")
    if not isinstance(target_ids, list) or len(target_ids) != len(set(target_ids)):
        raise ValueError("summary sample_id가 없거나 중복됐습니다")
    if target_ids != PROFILE_SAMPLE_IDS[profile]:
        raise ValueError(f"{profile} sample_id가 고정 평가 계약과 다릅니다")
    high_risk_ids = list(summary.get("high_risk_sample_ids", []))
    expected_high_risk = WEEKLY_HIGH_RISK_IDS if profile == "weekly" else NIGHTLY_SAMPLE_IDS
    if high_risk_ids != expected_high_risk:
        raise ValueError(f"{profile} 고위험 sample_id가 고정 평가 계약과 다릅니다")
    record_count = int(summary.get("record_count", summary.get("total", 0)))
    if "target_sample_ids" in summary:
        record_count = _require_target_ids(summary, target_ids)
    task_success = summary.get("score_averages", {}).get("task_success")
    if task_success is None and summary.get("total"):
        task_success = summary.get("passed", 0) / summary["total"]
    if task_success is not None and (
        not isinstance(task_success, (int, float))
        or isinstance(task_success, bool)
        or not math.isfinite(task_success)
    ):
        raise ValueError("task_success는 0~1 유한수여야 합니다")
    task_success = float(task_success) if task_success is not None else None
    summary_errors = int(summary.get("provider_error_count", 0))
    call_errors = sum(bool(call.get("error_type")) for call in calls)
    errors = max(summary_errors, call_errors)
    config = yaml.safe_load(config_source.read_text(encoding="utf-8"))["profiles"][profile]
    expected = len(PROFILE_SAMPLE_IDS[profile])
    if int(summary.get("target_count", expected)) != expected or len(target_ids) != expected:
        raise ValueError(f"{profile} target은 정확히 {expected}건이어야 합니다")
    calls_match = _calls_match_summary(summary, calls, target_ids) and not (
        summary_errors or call_errors
    )
    complete = record_count == expected and observed_status == "complete" and calls_match
    identity_matches = identity_matches and calls_match
    response_calls = [call for call in calls if not call.get("error_type")]
    latencies = [float(call.get("latency_ms") or 0) for call in response_calls]
    if not complete or source_status == "inconclusive" or not identity_matches:
        status: Literal["pass", "fail", "inconclusive"] = "inconclusive"
    elif task_success is None:
        status = "inconclusive"
    elif (
        source_status == "fail"
        or task_success < config["minimum_task_success"]
        or errors > config["maximum_errors"]
    ):
        status = "fail"
    else:
        status = "pass"
    actual_models = summary["actual_models"]
    selected_prompt_sha256 = summary.get("selected_prompt_sha256")
    agent_prompt_sha256 = summary.get("agent_prompt_sha256")
    if profile == "weekly":
        _require_sha(selected_prompt_sha256, length=64, name="selected_prompt_sha256")
        _require_sha(agent_prompt_sha256, length=64, name="agent_prompt_sha256")
    return MonitoringRecord(
        timestamp=timestamp or datetime.now(UTC),
        profile=profile,
        git_sha=git_sha,
        requested_model=summary["requested_model"],
        expected_actual_model=summary["expected_actual_model"],
        actual_model=actual_models[0] if len(actual_models) == 1 else None,
        model_identity_matches=identity_matches,
        prompt_sha256=_require_sha(
            summary.get("prompt_sha256") or provenance.get("prompt_sha256"),
            length=64,
            name="prompt_sha256",
        ),
        selected_prompt_sha256=selected_prompt_sha256,
        agent_prompt_sha256=agent_prompt_sha256,
        sample_ids=target_ids,
        high_risk_sample_ids=high_risk_ids,
        component_statuses=(
            summary.get("component_statuses", summary.get("source_statuses", {}))
            if profile == "weekly"
            else {}
        ),
        component_record_counts=(
            {
                "robustness": summary.get("robustness_count"),
                "agent": summary.get("agent_count"),
            }
            if profile == "weekly"
            else {}
        ),
        record_count=record_count,
        task_success=None if status == "inconclusive" else task_success,
        p95_latency_ms=_p95(latencies),
        # 응답 후 모델 불일치 등으로 실패해도 실제 기록된 사용량은 합산한다.
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


def combine_weekly_results(
    robustness_summary: dict,
    robustness_scores: list[dict],
    agent_summary: dict,
    agent_scores: list[dict],
    *,
    expected_agent_ids: list[str],
    expected_high_risk_ids: list[str],
    selected_prompt_sha256: str,
    prompt_selection: dict,
    evaluator_git_sha: str,
) -> dict:
    sources = (robustness_summary, agent_summary)
    states = [_require_source_summary(item, profile="weekly") for item in sources]
    requested_models = {item["requested_model"] for item in sources}
    expected_models = {item["expected_actual_model"] for item in sources}
    if len(requested_models) != 1 or len(expected_models) != 1:
        raise ValueError("weekly source의 requested/expected model이 다릅니다")
    weekly_requested_model = next(iter(requested_models))
    weekly_expected_model = next(iter(expected_models))

    variant_ids = robustness_summary.get("target_variant_ids")
    completed_variants = robustness_summary.get("completed_variant_ids")
    if (
        robustness_summary.get("sample_id") != WEEKLY_ROBUSTNESS_SAMPLE_ID
        or robustness_summary.get("family_id") != WEEKLY_ROBUSTNESS_FAMILY_ID
    ):
        raise ValueError("weekly robustness는 OpenCQA 884 family여야 합니다")
    if variant_ids != WEEKLY_VARIANT_IDS or robustness_summary.get("target_count") != 5:
        raise ValueError("weekly robustness target ID가 주차 계약과 다릅니다")
    if (
        not isinstance(completed_variants, list)
        or len(completed_variants) != len(set(completed_variants))
        or not set(completed_variants) <= set(variant_ids)
    ):
        raise ValueError("weekly robustness completed ID가 target과 다릅니다")
    robustness_count = int(robustness_summary.get("record_count", -1))
    if robustness_count != len(completed_variants):
        raise ValueError("robustness record_count와 completed ID 수가 다릅니다")

    agent_count = _require_target_ids(agent_summary, expected_agent_ids)
    if agent_summary.get("high_risk_sample_ids") != expected_high_risk_ids:
        raise ValueError("weekly agent 고위험 ID가 주차 계약과 다릅니다")
    metric_passed = agent_summary.get("metric_passed")
    if (
        not isinstance(metric_passed, dict)
        or set(metric_passed) != AGENT_MUST_PASS
        or any(type(metric_passed[name]) is not int for name in AGENT_MUST_PASS)
        or agent_summary.get("metric_record_count") != agent_count
    ):
        raise ValueError("agent summary의 must-pass 지표 집계가 불완전합니다")
    phoenix_trace_ids = agent_summary.get("phoenix_trace_ids")
    completed_agent_ids = agent_summary.get("completed_sample_ids")
    if not isinstance(phoenix_trace_ids, dict) or set(phoenix_trace_ids) != set(
        completed_agent_ids
    ):
        raise ValueError("완료된 agent마다 Phoenix trace ID가 필요합니다")
    trace_values = list(phoenix_trace_ids.values())
    if len(trace_values) != len(set(trace_values)) or any(
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{32}", value) is None
        for value in trace_values
    ):
        raise ValueError("Phoenix trace ID는 서로 다른 32자리 소문자 hex여야 합니다")

    selection_hash = _require_sha(
        prompt_selection.get("selected_prompt_sha256"),
        length=64,
        name="prompt selection hash",
    )
    selected_hash = _require_sha(selected_prompt_sha256, length=64, name="selected prompt hash")
    if selection_hash != selected_hash or robustness_summary.get("prompt_sha256") != selected_hash:
        raise ValueError("선택한 prompt와 robustness 실행 prompt가 다릅니다")
    if (
        prompt_selection.get("status") != "pass"
        or prompt_selection.get("observed_status") != "complete"
        or prompt_selection.get("evidence_kind") != "live_quality"
    ):
        raise ValueError("selected prompt에는 완료된 live selection 근거가 필요합니다")
    if prompt_selection.get("test_used_for_generation_or_selection") is not False:
        raise ValueError("prompt selection에 test를 사용하면 안 됩니다")
    if (
        prompt_selection.get("selected") not in {"baseline", "candidate"}
        or not isinstance(prompt_selection.get("selection_reason"), str)
        or not prompt_selection["selection_reason"]
        or tuple(
            prompt_selection.get(name)
            for name in ("development_count", "validation_count", "test_count")
        )
        != (18, 6, 6)
    ):
        raise ValueError("prompt selection 결과 metadata가 불완전합니다")
    provider_evidence = {}
    for role in ("target", "optimizer"):
        evidence = prompt_selection.get(f"{role}_provider")
        if (
            not isinstance(evidence, dict)
            or evidence.get("role") != role
            or not isinstance(evidence.get("requested_model"), str)
            or not evidence["requested_model"]
            or not isinstance(evidence.get("expected_actual_model"), str)
            or not evidence["expected_actual_model"]
            or evidence.get("actual_models") != [evidence.get("expected_actual_model")]
            or evidence.get("provider_error_count") != 0
            or evidence.get("model_drift_count") != 0
        ):
            raise ValueError(f"prompt selection {role} provider 증거가 불완전합니다")
        provider_evidence[role] = evidence
    if (
        prompt_selection.get("provider_error_count") != 0
        or prompt_selection.get("model_drift_count") != 0
        or provider_evidence["target"].get("requested_model") != weekly_requested_model
        or provider_evidence["target"].get("expected_actual_model") != weekly_expected_model
    ):
        raise ValueError("prompt selection provider와 weekly source가 다릅니다")
    _require_sha(
        prompt_selection.get("dataset_sha256"), length=64, name="prompt selection dataset hash"
    )
    _require_sha(
        prompt_selection.get("source_revision"),
        length=40,
        name="prompt selection source revision",
    )
    if any(
        not isinstance(prompt_selection.get(name), str) or not prompt_selection[name]
        for name in ("source_split", "source_license")
    ):
        raise ValueError("prompt selection source metadata가 불완전합니다")
    if any(
        prompt_selection.get(name) != robustness_summary.get(name)
        for name in ("source_split", "source_revision", "source_license")
    ):
        raise ValueError("prompt selection과 robustness source가 다릅니다")
    selection_git_sha = _require_sha(
        prompt_selection.get("git_sha"), length=40, name="prompt selection git_sha"
    )
    selection_summary_sha256 = _require_sha(
        prompt_selection.get("selection_summary_sha256"),
        length=64,
        name="prompt selection summary hash",
    )
    robustness_artifacts = robustness_summary.get("artifact_sha256")
    if not isinstance(robustness_artifacts, dict):
        raise ValueError("robustness summary의 artifact hash가 필요합니다")
    robustness_responses_sha256 = _require_sha(
        robustness_artifacts.get("responses.jsonl"),
        length=64,
        name="robustness responses hash",
    )
    _require_sha(
        agent_summary.get("upstream_source_summary_sha256"),
        length=64,
        name="agent upstream source summary hash",
    )
    _require_sha(
        agent_summary.get("upstream_output_sha256"),
        length=64,
        name="agent upstream output hash",
    )
    expected_agent_lineage = {
        "upstream_sample_id": WEEKLY_ROBUSTNESS_SAMPLE_ID,
        "upstream_family_id": WEEKLY_ROBUSTNESS_FAMILY_ID,
        "upstream_selected_prompt_sha256": selection_hash,
        "upstream_selection_summary_sha256": selection_summary_sha256,
        "upstream_responses_sha256": robustness_responses_sha256,
    }
    if any(
        agent_summary.get(name) != expected
        for name, expected in expected_agent_lineage.items()
    ):
        raise ValueError("Week 4 robustness와 Week 5 agent의 workflow 계보가 다릅니다")

    git_shas = {
        item.get("git_sha") or item.get("provenance", {}).get("git_sha") for item in sources
    }
    if len(git_shas) != 1:
        raise ValueError("weekly source의 Git SHA가 다릅니다")
    git_sha = _require_sha(git_shas.pop(), length=40, name="weekly git_sha")
    if git_sha != _require_sha(evaluator_git_sha, length=40, name="weekly evaluator git_sha"):
        raise ValueError("weekly source와 현재 평가 코드의 Git SHA가 다릅니다")

    robustness_by_id = {item.get("variant_id"): item for item in robustness_scores}
    if None in robustness_by_id or len(robustness_by_id) != len(robustness_scores):
        raise ValueError("robustness score ID가 없거나 중복됐습니다")
    if not set(robustness_by_id) <= set(variant_ids):
        raise ValueError("target 밖의 robustness score가 있습니다")
    agent_by_id = {item.get("sample_id"): item for item in agent_scores}
    if None in agent_by_id or len(agent_by_id) != len(agent_scores):
        raise ValueError("agent score ID가 없거나 중복됐습니다")
    if not set(agent_by_id) <= set(expected_agent_ids):
        raise ValueError("target 밖의 agent score가 있습니다")

    invalid_variant = False
    robustness_inconclusive = False
    for item in robustness_scores:
        score_status = item.get("status")
        if score_status not in {"passed", "failed", "inconclusive", "invalid_variant"}:
            raise ValueError("알 수 없는 robustness score status입니다")
        invalid_variant = invalid_variant or score_status == "invalid_variant"
        robustness_inconclusive = robustness_inconclusive or score_status == "inconclusive"
    for item in agent_scores:
        if item.get("status") not in {"passed", "failed", "inconclusive"}:
            raise ValueError("알 수 없는 agent score status입니다")
        scores = item.get("scores", {})
        if (
            item.get("evidence_kind") != "live_quality"
            or set(scores) != AGENT_MUST_PASS
            or any(isinstance(value, bool) or value not in {0, 1} for value in scores.values())
        ):
            raise ValueError("agent score의 live evidence 또는 must-pass 항목이 없습니다")

    incomplete = (
        robustness_count != 5
        or agent_count != 6
        or len(robustness_scores) != 5
        or len(agent_scores) != 6
    )
    agent_failed = any(
        item["status"] == "failed" or any(item["scores"][name] != 1 for name in AGENT_MUST_PASS)
        for item in agent_scores
    ) or any(metric_passed[name] != agent_count for name in AGENT_MUST_PASS)
    robustness_status = (
        "inconclusive"
        if states[0][0] == "inconclusive"
        or states[0][1] != "complete"
        or not states[0][2]
        or robustness_count != 5
        or len(robustness_scores) != 5
        or invalid_variant
        or robustness_inconclusive
        else "fail"
        if states[0][0] == "fail"
        or any(item["status"] == "failed" for item in robustness_scores)
        else "pass"
    )
    agent_status = (
        "inconclusive"
        if states[1][0] == "inconclusive"
        or states[1][1] != "complete"
        or not states[1][2]
        or agent_count != 6
        or len(agent_scores) != 6
        or any(item["status"] == "inconclusive" for item in agent_scores)
        else "fail"
        if states[1][0] == "fail" or agent_failed
        else "pass"
    )
    component_statuses = {
        "robustness": robustness_status,
        "agent": agent_status,
    }
    status: Literal["pass", "fail", "inconclusive"] = (
        "inconclusive"
        if "inconclusive" in component_statuses.values()
        else "fail"
        if "fail" in component_statuses.values()
        else "pass"
    )

    actual_models = sorted({model for item in sources for model in item.get("actual_models", [])})
    sample_ids = [
        *(f"{WEEKLY_ROBUSTNESS_SAMPLE_ID}:{variant_id}" for variant_id in variant_ids),
        *expected_agent_ids,
    ]
    total_records = robustness_count + agent_count
    observed_values = [observed for _, observed, _ in states]
    observed = (
        "complete"
        if not incomplete and all(value == "complete" for value in observed_values)
        else "partial"
        if total_records
        else "not_run"
        if "not_run" in observed_values
        else "inconclusive"
    )
    return {
        "status": status,
        "observed_status": observed,
        "profile": "weekly",
        "evidence_kind": "live_quality",
        "record_count": total_records,
        "target_count": 11,
        "sample_ids": sample_ids,
        "score_averages": {
            "task_success": None if status == "inconclusive" else 1.0 if status == "pass" else 0.0
        },
        "provider_error_count": sum(int(item.get("provider_error_count", 0)) for item in sources),
        "model_drift_count": sum(int(item.get("model_drift_count", 0)) for item in sources),
        "requested_model": weekly_requested_model,
        "expected_actual_model": weekly_expected_model,
        "actual_models": actual_models,
        "prompt_sha256": selected_hash,
        "selected_prompt_sha256": selected_hash,
        "agent_prompt_sha256": _require_sha(
            agent_summary.get("prompt_sha256"), length=64, name="agent prompt hash"
        ),
        "selected_prompt_provenance": {
            "selected": prompt_selection.get("selected"),
            "source_git_sha": selection_git_sha,
            "selection_summary_sha256": selection_summary_sha256,
            "selected_prompt_sha256": selection_hash,
        },
        "high_risk_sample_ids": expected_high_risk_ids,
        "component_statuses": component_statuses,
        "phoenix_trace_ids": phoenix_trace_ids,
        "provenance": {"git_sha": git_sha},
        "robustness_count": robustness_count,
        "agent_count": agent_count,
    }
