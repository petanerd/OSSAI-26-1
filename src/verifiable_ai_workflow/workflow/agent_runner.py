"""모델 turn과 결정적 도구 실행을 번갈아 처리한다."""

from __future__ import annotations

import json
from contextlib import nullcontext
from hashlib import sha256
from typing import Any, Protocol

from opentelemetry.trace import Status, StatusCode

from ..schemas.agent import AgentCase, AgentRun, AgentTurn, AgentUpstreamContext
from ..tools import ToolError, ToolSandbox, authorization_denial


class AgentExecutionError(RuntimeError):
    """완료로 집계하지 않을 실패 사례의 로컬 기록과 원래 오류를 보존한다."""

    def __init__(self, cause: Exception, partial_record: dict[str, Any]) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.partial_record = partial_record


class AgentProvider(Protocol):
    evidence_kind: str

    def generate(
        self,
        sample_id: str,
        messages: list[dict[str, Any]],
        *,
        response_schema,
    ) -> Any: ...


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _fingerprint(payload: Any) -> str:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(serialized.encode()).hexdigest()


def _set_json(span: Any | None, direction: str, payload: dict[str, Any]) -> None:
    if span is None:
        return
    span.set_attribute(f"{direction}.mime_type", "application/json")
    span.set_attribute(f"{direction}.value", _json_text(payload))


def _set_status(span: Any | None, status: StatusCode) -> None:
    if span is not None:
        span.set_status(Status(status))


def _set_attributes(span: Any | None, attributes: dict[str, Any]) -> None:
    if span is None:
        return
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


def _start_step(
    span: Any | None,
    input_summary: dict[str, Any],
    attributes: dict[str, Any],
) -> None:
    if span is None:
        return
    _set_attributes(span, {"course.status": "in_progress", **attributes})
    _set_json(span, "input", input_summary)
    span.add_event(
        "request.started",
        {
            "course.status": "in_progress",
            **{
                key: value
                for key, value in attributes.items()
                if key in {"course.turn_index", "course.request_sha256", "tool.name"}
            },
        },
    )


def _finish_step(
    span: Any | None,
    *,
    status: str,
    next_action: str,
    output_summary: dict[str, Any],
    attributes: dict[str, Any],
    result_event: str | None = None,
) -> None:
    if span is None:
        return
    _set_attributes(
        span,
        {
            "course.status": status,
            "course.next_action": next_action,
            **attributes,
        },
    )
    _set_json(span, "output", output_summary)
    if result_event is not None:
        span.add_event(
            result_event,
            {"course.status": status, **attributes},
        )
    span.add_event("follow_up.selected", {"course.next_action": next_action})
    _set_status(span, StatusCode.OK if status == "success" else StatusCode.ERROR)


def _provider_telemetry(provider: AgentProvider) -> dict[str, Any]:
    call = getattr(provider, "last_call", None)
    if not isinstance(call, dict):
        return {}
    return {
        key: call[key]
        for key in (
            "requested_model",
            "expected_actual_model",
            "actual_model",
            "actual_model_matches_expected",
            "response_id",
            "provider_status",
            "latency_ms",
            "input_tokens",
            "output_tokens",
            "actual_cost_usd",
            "retry_count",
            "request_number",
            "attempt_number",
        )
        if call.get(key) is not None
    }


def _apply_provider_telemetry(span: Any | None, telemetry: dict[str, Any]) -> None:
    if span is None:
        return
    attribute_names = {
        "requested_model": "course.requested_model",
        "expected_actual_model": "course.expected_actual_model",
        "actual_model": "course.actual_model",
        "actual_model_matches_expected": "course.actual_model_matches_expected",
        "response_id": "course.response_id",
        "provider_status": "course.provider_status",
        "latency_ms": "course.latency_ms",
        "actual_cost_usd": "course.actual_cost_usd",
        "retry_count": "course.retry_count",
        "request_number": "course.request_number",
        "attempt_number": "course.attempt_number",
    }
    for source, target in attribute_names.items():
        if source in telemetry:
            span.set_attribute(target, telemetry[source])
    model = telemetry.get("actual_model") or telemetry.get("requested_model")
    if model is not None:
        span.set_attribute("llm.model_name", model)
    if "input_tokens" in telemetry:
        span.set_attribute("llm.token_count.prompt", telemetry["input_tokens"])
    if "output_tokens" in telemetry:
        span.set_attribute("llm.token_count.completion", telemetry["output_tokens"])


def run_agent_case(
    case: AgentCase,
    provider: AgentProvider,
    *,
    upstream_context: AgentUpstreamContext,
    system_prompt: str,
    records: dict[str, dict[str, Any]],
    tracer: Any | None = None,
) -> AgentRun:
    if (
        provider.evidence_kind == "live_quality"
        and upstream_context.source_evidence_kind != "live_quality"
    ):
        raise ValueError("실제 agent 호출에는 실제 Week 4 upstream 근거가 필요합니다")
    if (
        case.source_sample_id != upstream_context.sample_id
        or case.family_id != upstream_context.family_id
    ):
        raise ValueError(
            f"Week 5 사례와 Week 4 입력 계보가 다릅니다: {case.sample_id}"
        )
    if tracer is None:
        return _run_agent_case(
            case,
            provider,
            upstream_context=upstream_context,
            system_prompt=system_prompt,
            records=records,
            tracer=None,
        )
    with tracer.start_as_current_span(
        "agent.run",
        attributes={
            "openinference.span.kind": "AGENT",
            "course.sample_id": case.sample_id,
            "course.source_sample_id": case.source_sample_id,
            "course.risk_level": case.risk_level,
            "course.evidence_kind": provider.evidence_kind,
        },
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        prompt_sha256 = sha256(system_prompt.encode()).hexdigest()
        instruction_sha256 = sha256(case.instruction.encode()).hexdigest()
        span.set_attribute("course.status", "in_progress")
        span.set_attribute("course.prompt_sha256", prompt_sha256)
        span.set_attribute("course.instruction_sha256", instruction_sha256)
        span.set_attribute("course.max_model_turns", case.max_tool_calls + 1)
        span.set_attribute("course.max_tool_calls", case.max_tool_calls)
        _set_json(
            span,
            "input",
            {
                "workflow": "week5_agent",
                "sample_id": case.sample_id,
                "source_sample_id": case.source_sample_id,
                "risk_level": case.risk_level,
                "evidence_kind": provider.evidence_kind,
                "request": "execute_case",
                "prompt_sha256": prompt_sha256,
                "instruction_sha256": instruction_sha256,
                "upstream_output_sha256": upstream_context.output_sha256,
                "max_model_turns": case.max_tool_calls + 1,
                "max_tool_calls": case.max_tool_calls,
                "authorization": {
                    "allowed_record_count": len(case.authorization.allowed_record_ids),
                    "allowed_lookup_field_count": len(
                        case.authorization.allowed_lookup_fields
                    ),
                    "can_create_ticket": case.authorization.can_create_ticket,
                },
            },
        )
        span.add_event(
            "workflow.started",
            {
                "course.sample_id": case.sample_id,
                "course.status": "in_progress",
            },
        )
        try:
            run = _run_agent_case(
                case,
                provider,
                upstream_context=upstream_context,
                system_prompt=system_prompt,
                records=records,
                tracer=tracer,
            )
        except Exception as exc:
            cause = exc.cause if isinstance(exc, AgentExecutionError) else exc
            if isinstance(exc, AgentExecutionError):
                exc.partial_record["phoenix_trace_id"] = (
                    f"{span.get_span_context().trace_id:032x}"
                )
            span.set_attribute("course.status", "provider_error")
            span.set_attribute("course.error_type", type(cause).__name__)
            span.set_attribute("course.next_action", "inspect_jsonl_and_hold")
            _set_json(
                span,
                "output",
                {
                    "status": "provider_error",
                    "error_type": type(cause).__name__,
                    "next_action": "inspect_jsonl_and_hold",
                },
            )
            span.add_event(
                "workflow.failed",
                {
                    "course.error_type": type(cause).__name__,
                    "course.next_action": "inspect_jsonl_and_hold",
                },
            )
            _set_status(span, StatusCode.ERROR)
            raise
        final_outcome = (
            "missing"
            if run.final_answer is None
            else "abstained"
            if run.final_answer.abstained
            else "answered"
        )
        next_action = "score_and_review" if not run.errors else "inspect_jsonl_and_hold"
        status = "complete" if not run.errors else "complete_with_errors"
        model_turn_count = sum(item.get("event") == "model_turn" for item in run.trace)
        span.set_attribute("course.status", status)
        span.set_attribute("course.tool_call_count", len(run.tool_calls))
        span.set_attribute("course.model_turn_count", model_turn_count)
        span.set_attribute("course.error_count", len(run.errors))
        span.set_attribute(
            "course.final_ticket_count", int(run.final_state.get("ticket_count", 0))
        )
        span.set_attribute("course.final_outcome", final_outcome)
        span.set_attribute("course.next_action", next_action)
        _set_json(
            span,
            "output",
            {
                "status": status,
                "model_turn_count": model_turn_count,
                "tool_call_count": len(run.tool_calls),
                "error_count": len(run.errors),
                "final_outcome": final_outcome,
                "final_ticket_count": int(run.final_state.get("ticket_count", 0)),
                "next_action": next_action,
            },
        )
        span.add_event(
            "workflow.completed",
            {
                "course.status": status,
                "course.next_action": next_action,
            },
        )
        _set_status(span, StatusCode.OK if not run.errors else StatusCode.ERROR)
        return run.model_copy(
            update={
                "phoenix_trace_id": f"{span.get_span_context().trace_id:032x}",
            }
        )


def _span(tracer: Any | None, name: str, attributes: dict[str, Any]):
    return (
        nullcontext()
        if tracer is None
        else tracer.start_as_current_span(
            name,
            attributes=attributes,
            record_exception=False,
            set_status_on_exception=False,
        )
    )


def _run_agent_case(
    case: AgentCase,
    provider: AgentProvider,
    *,
    upstream_context: AgentUpstreamContext,
    system_prompt: str,
    records: dict[str, dict[str, Any]],
    tracer: Any | None,
) -> AgentRun:
    sandbox = ToolSandbox(case.authorization, records)
    initial_state = sandbox.final_state
    execution_contract = {
        "source_sample_id": case.source_sample_id,
        "family_id": case.family_id,
        "risk_level": case.risk_level,
        "authorization": case.authorization.model_dump(mode="json"),
        "max_tool_calls": case.max_tool_calls,
        "fault_seed": case.fault_seed,
        "week_04_upstream_data": upstream_context.model_dump(mode="json"),
    }
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                case.instruction
                + "\n\n이번 실행 계약:\n"
                + json.dumps(execution_contract, ensure_ascii=False)
            ),
        },
    ]
    trace: list[dict[str, Any]] = []
    calls = []
    errors: list[str] = []
    final = None
    first_ticket = True
    for turn_index in range(case.max_tool_calls + 1):
        request_sha256 = _fingerprint(messages)
        request_summary = {
            "stage": "model_request",
            "sample_id": case.sample_id,
            "turn_index": turn_index,
            "provider": type(provider).__name__,
            "requested_model": getattr(provider, "model", None),
            "response_schema": AgentTurn.__name__,
            "message_count": len(messages),
            "previous_message_role": messages[-1]["role"],
            "tool_calls_used": len(calls),
            "tool_calls_remaining": case.max_tool_calls - len(calls),
            "request_sha256": request_sha256,
        }
        request_summary = {
            key: value for key, value in request_summary.items() if value is not None
        }
        with _span(
            tracer,
            "agent.model_turn",
            {
                "openinference.span.kind": "LLM",
                "course.sample_id": case.sample_id,
                "course.turn_index": turn_index,
            },
        ) as model_span:
            _start_step(
                model_span,
                request_summary,
                {
                    "course.turn_index": turn_index,
                    "course.provider": type(provider).__name__,
                    "course.request_sha256": request_sha256,
                    "course.message_count": len(messages),
                    "course.tool_calls_used": len(calls),
                    "course.tool_calls_remaining": case.max_tool_calls - len(calls),
                },
            )
            try:
                raw = provider.generate(case.sample_id, messages, response_schema=AgentTurn)
            except Exception as exc:
                telemetry = _provider_telemetry(provider)
                _apply_provider_telemetry(model_span, telemetry)
                _finish_step(
                    model_span,
                    status="provider_error",
                    next_action="stop_and_review",
                    output_summary={
                        "stage": "model_result",
                        "status": "provider_error",
                        "error_type": type(exc).__name__,
                        "provider": telemetry,
                        "next_action": "stop_and_review",
                    },
                    attributes={"course.error_type": type(exc).__name__},
                    result_event="request.failed",
                )
                raise AgentExecutionError(
                    exc,
                    {
                        "sample_id": case.sample_id,
                        "source_sample_id": case.source_sample_id,
                        "family_id": case.family_id,
                        "upstream_context": upstream_context.model_dump(mode="json"),
                        "risk_level": case.risk_level,
                        "authorization": case.authorization.model_dump(mode="json"),
                        "max_tool_calls": case.max_tool_calls,
                        "fault_seed": case.fault_seed,
                        "evidence_kind": (
                            "live_quality"
                            if provider.evidence_kind == "live_quality"
                            else "test_only"
                        ),
                        "observed_status": "partial",
                        "error_type": type(exc).__name__,
                        "final_answer": None,
                        "tool_calls": [call.model_dump(mode="json") for call in calls],
                        "trace": [
                            *trace,
                            {
                                "event": "model_request_failed",
                                "turn_index": turn_index,
                                "error_type": type(exc).__name__,
                            },
                        ],
                        "ledger": sandbox.ledger,
                        "initial_state": initial_state,
                        "final_state": sandbox.final_state,
                        "phoenix_trace_id": None,
                    },
                ) from exc
            telemetry = _provider_telemetry(provider)
            response_sha256 = _fingerprint(raw)
            _apply_provider_telemetry(model_span, telemetry)
            if model_span is not None:
                model_span.set_attribute("course.response_sha256", response_sha256)
                model_span.add_event(
                    "response.received",
                    {
                        "course.response_sha256": response_sha256,
                        "course.provider_status": telemetry.get(
                            "provider_status", "received"
                        ),
                    },
                )
            try:
                turn = raw if isinstance(raw, AgentTurn) else AgentTurn.model_validate_json(raw)
            except Exception as exc:
                _finish_step(
                    model_span,
                    status="invalid_output",
                    next_action="stop_and_review",
                    output_summary={
                        "stage": "model_result",
                        "status": "invalid_output",
                        "response_sha256": response_sha256,
                        "error_type": type(exc).__name__,
                        "provider": telemetry,
                        "next_action": "stop_and_review",
                    },
                    attributes={"course.error_type": type(exc).__name__},
                )
                trace.append(
                    {
                        "event": "model_output_invalid",
                        "raw_output": raw,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                errors.append("model_output_invalid")
                break
            next_action = (
                "execute_tool"
                if turn.turn_type == "tool"
                else "finish_with_abstention"
                if turn.answer is not None and turn.answer.abstained
                else "finish_agent"
            )
            tool_name = turn.tool_call.tool if turn.tool_call is not None else None
            answer_outcome = (
                "abstained"
                if turn.answer is not None and turn.answer.abstained
                else "answered"
                if turn.answer is not None
                else None
            )
            _finish_step(
                model_span,
                status="success",
                next_action=next_action,
                output_summary={
                    "stage": "model_result",
                    "status": "success",
                    "response_sha256": response_sha256,
                    "turn_type": turn.turn_type,
                    "tool_name": tool_name,
                    "answer_outcome": answer_outcome,
                    "provider": telemetry,
                    "next_action": next_action,
                },
                attributes={
                    "course.turn_type": turn.turn_type,
                    "tool.name": tool_name,
                },
            )
        trace.append({"event": "model_turn", "turn": turn.model_dump(mode="json")})
        if turn.turn_type == "final":
            final = turn.answer
            break
        call = turn.tool_call
        if call is None:
            errors.append("tool_call_missing")
            break
        if len(calls) >= case.max_tool_calls:
            calls.append(call)
            errors.append("tool_call_budget_exceeded")
            trace.append(
                {
                    "event": "tool_error",
                    "tool": call.tool,
                    "error": "ToolCallBudgetExceeded",
                }
            )
            break
        calls.append(call)
        fail_after_commit = bool(
            case.fault_seed is not None
            and call.tool == "create_ticket"
            and first_ticket
        )
        if call.tool == "create_ticket":
            first_ticket = False
        authorization_status = (
            "allowed"
            if authorization_denial(case.authorization, call) is None
            else "denied"
        )
        ticket_count_before = int(sandbox.final_state.get("ticket_count", 0))
        side_effect = call.tool == "create_ticket"
        tool_request = {
            "stage": "tool_request",
            "sample_id": case.sample_id,
            "turn_index": turn_index,
            "tool_name": call.tool,
            "authorization_status": authorization_status,
            "side_effect": side_effect,
            "idempotency_protected": side_effect,
            "requested_field_count": len(getattr(call, "fields", ())),
            "ticket_count_before": ticket_count_before,
            "next_action": "execute_tool",
        }
        with _span(
            tracer,
            "agent.tool",
            {
                "openinference.span.kind": "TOOL",
                "course.sample_id": case.sample_id,
                "course.turn_index": turn_index,
                "tool.name": call.tool,
            },
        ) as tool_span:
            _start_step(
                tool_span,
                tool_request,
                {
                    "tool.name": call.tool,
                    "course.authorization_status": authorization_status,
                    "course.side_effect": side_effect,
                    "course.idempotency_protected": side_effect,
                    "course.ticket_count_before": ticket_count_before,
                    "course.next_action": "execute_tool",
                },
            )
            try:
                result = sandbox.execute(call, fail_after_commit=fail_after_commit)
                ticket_count_after = int(sandbox.final_state.get("ticket_count", 0))
                returned_field_count = len(result.get("fields", {}))
                next_action = "return_result_to_model"
                state_changed = ticket_count_after != ticket_count_before
                _finish_step(
                    tool_span,
                    status="success",
                    next_action=next_action,
                    output_summary={
                        "stage": "tool_result",
                        "status": "success",
                        "tool_name": call.tool,
                        "replayed": bool(result.get("replayed")),
                        "returned_field_count": returned_field_count,
                        "ticket_count_before": ticket_count_before,
                        "ticket_count_after": ticket_count_after,
                        "state_changed": state_changed,
                        "next_action": next_action,
                    },
                    attributes={
                        "course.replayed": bool(result.get("replayed")),
                        "course.ticket_count_after": ticket_count_after,
                        "course.returned_field_count": returned_field_count,
                        "course.state_changed": state_changed,
                    },
                    result_event="result.received",
                )
                trace.append({"event": "tool_result", "tool": call.tool, "result": result})
                tool_content = {"status": "success", **result}
            except ToolError as exc:
                ticket_count_after = int(sandbox.final_state.get("ticket_count", 0))
                state_changed = ticket_count_after != ticket_count_before
                next_action = (
                    "verify_side_effect_then_return_error_to_model"
                    if state_changed
                    else "return_error_to_model"
                )
                _finish_step(
                    tool_span,
                    status="error",
                    next_action=next_action,
                    output_summary={
                        "stage": "tool_result",
                        "status": "error",
                        "tool_name": call.tool,
                        "error_type": type(exc).__name__,
                        "ticket_count_before": ticket_count_before,
                        "ticket_count_after": ticket_count_after,
                        "state_changed": state_changed,
                        "next_action": next_action,
                    },
                    attributes={
                        "course.error_type": type(exc).__name__,
                        "course.ticket_count_after": ticket_count_after,
                        "course.state_changed": state_changed,
                    },
                    result_event="result.failed",
                )
                trace.append(
                    {"event": "tool_error", "tool": call.tool, "error": type(exc).__name__}
                )
                tool_content = {"status": "error", "error": type(exc).__name__}
        messages.extend(
            [
                {"role": "assistant", "content": turn.model_dump_json()},
                {"role": "tool", "content": json.dumps(tool_content, ensure_ascii=False)},
            ]
        )
    if final is None and not errors:
        errors.append("final_answer_missing")
    evidence = "live_quality" if provider.evidence_kind == "live_quality" else "test_only"
    return AgentRun(
        sample_id=case.sample_id,
        source_sample_id=case.source_sample_id,
        family_id=case.family_id,
        upstream_context=upstream_context,
        risk_level=case.risk_level,
        authorization=case.authorization,
        max_tool_calls=case.max_tool_calls,
        fault_seed=case.fault_seed,
        final_answer=final,
        tool_calls=calls,
        trace=trace,
        ledger=sandbox.ledger,
        initial_state=initial_state,
        final_state=sandbox.final_state,
        errors=errors,
        evidence_kind=evidence,
    )
