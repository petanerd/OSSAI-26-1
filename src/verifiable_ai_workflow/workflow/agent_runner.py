"""모델 turn과 결정적 도구 실행을 번갈아 처리한다."""

from __future__ import annotations

import json
from typing import Any, Protocol

from ..schemas.agent import AgentCase, AgentRun, AgentTurn
from ..tools import ToolError, ToolSandbox


class AgentProvider(Protocol):
    evidence_kind: str

    def generate(
        self,
        sample_id: str,
        messages: list[dict[str, Any]],
        *,
        response_schema,
    ) -> Any: ...


def run_agent_case(
    case: AgentCase,
    provider: AgentProvider,
    *,
    system_prompt: str,
    records: dict[str, dict[str, Any]],
) -> AgentRun:
    sandbox = ToolSandbox(case.authorization, records)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": case.instruction},
    ]
    trace: list[dict[str, Any]] = []
    calls = []
    errors: list[str] = []
    final = None
    first_ticket = True
    for turn_index in range(case.max_tool_calls + 1):
        raw = provider.generate(case.sample_id, messages, response_schema=AgentTurn)
        turn = raw if isinstance(raw, AgentTurn) else AgentTurn.model_validate_json(raw)
        trace.append({"event": "model_turn", "turn": turn.model_dump(mode="json")})
        if turn.turn_type == "final":
            final = turn.answer
            break
        call = turn.tool_call
        if call is None:
            errors.append("tool_call_missing")
            break
        calls.append(call)
        fail_after_commit = bool(
            case.fault_first_ticket_after_commit
            and call.tool == "create_ticket"
            and first_ticket
        )
        if call.tool == "create_ticket":
            first_ticket = False
        try:
            result = sandbox.execute(call, fail_after_commit=fail_after_commit)
            trace.append({"event": "tool_result", "tool": call.tool, "result": result})
            tool_content = {"status": "success", **result}
        except ToolError as exc:
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
        if turn_index == case.max_tool_calls:
            errors.append("tool_call_budget_exceeded")
    if final is None and not errors:
        errors.append("final_answer_missing")
    evidence = "live_quality" if provider.evidence_kind == "live_quality" else "test_only"
    return AgentRun(
        sample_id=case.sample_id,
        final_answer=final,
        tool_calls=calls,
        trace=trace,
        final_state=sandbox.final_state,
        errors=errors,
        evidence_kind=evidence,
    )
