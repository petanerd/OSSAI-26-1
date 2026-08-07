"""Week 5 도구 호출과 최종 답 형식."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from .models import Contract, StructuredAnswer


class CalculatorCall(Contract):
    tool: Literal["calculator"] = "calculator"
    expression: str = Field(min_length=1, max_length=200)


class LookupCall(Contract):
    tool: Literal["lookup"] = "lookup"
    record_id: str = Field(min_length=1, max_length=100)
    fields: list[str] = Field(min_length=1, max_length=5)


class CreateTicketCall(Contract):
    tool: Literal["create_ticket"] = "create_ticket"
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)


ToolCall = Annotated[
    CalculatorCall | LookupCall | CreateTicketCall,
    Field(discriminator="tool"),
]


class AgentTurn(Contract):
    turn_type: Literal["tool", "final"]
    tool_call: ToolCall | None = None
    answer: StructuredAnswer | None = None

    @model_validator(mode="after")
    def one_turn_kind(self) -> AgentTurn:
        if self.turn_type == "tool" and (self.tool_call is None or self.answer is not None):
            raise ValueError("tool turn에는 tool_call만 필요합니다")
        if self.turn_type == "final" and (self.answer is None or self.tool_call is not None):
            raise ValueError("final turn에는 answer만 필요합니다")
        return self


class AuthorizationScope(Contract):
    allowed_record_ids: set[str] = Field(default_factory=set)
    allowed_lookup_fields: set[str] = Field(default_factory=set)
    can_create_ticket: bool = False


class AgentCase(Contract):
    sample_id: str
    instruction: str
    authorization: AuthorizationScope
    max_tool_calls: int = Field(ge=0, le=4)
    fault_first_ticket_after_commit: bool = False
    expected_calls: list[ToolCall]
    expected_ticket_count: int = Field(ge=0)
    expected_abstained: bool


class AgentRun(Contract):
    sample_id: str
    final_answer: StructuredAnswer | None
    tool_calls: list[ToolCall]
    trace: list[dict[str, Any]]
    final_state: dict[str, Any]
    errors: list[str]
    evidence_kind: Literal["test_only", "live_quality"]


class AgentScore(Contract):
    sample_id: str
    status: Literal["passed", "failed", "inconclusive"]
    scores: dict[str, float]
    reasons: dict[str, str]
    evidence_kind: Literal["test_only", "live_quality"]
