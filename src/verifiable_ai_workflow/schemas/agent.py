"""Week 5 도구 호출과 최종 답 형식."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal

from pydantic import Field, RootModel, field_serializer, model_validator

from .models import Contract, StructuredAnswer


def structured_answer_sha256(output: StructuredAnswer) -> str:
    canonical = json.dumps(
        output.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class CalculatorCall(Contract):
    tool: Literal["calculator"]
    expression: str = Field(min_length=1, max_length=200)


class LookupCall(Contract):
    tool: Literal["lookup"]
    record_id: str = Field(min_length=1, max_length=100)
    fields: list[str] = Field(min_length=1, max_length=5)


class CreateTicketCall(Contract):
    tool: Literal["create_ticket"]
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)


ToolCall = Annotated[
    CalculatorCall | LookupCall | CreateTicketCall,
    Field(discriminator="tool"),
]


class AgentFinal(Contract):
    answer: str = Field(min_length=1)
    abstained: bool
    abstention_reason: str | None

    @model_validator(mode="after")
    def answer_matches_abstention(self) -> AgentFinal:
        if self.abstained and (
            self.answer != "답변 보류" or not self.abstention_reason
        ):
            raise ValueError("답변 보류에는 정해진 answer와 이유가 필요합니다")
        if not self.abstained and (
            self.answer == "답변 보류" or self.abstention_reason is not None
        ):
            raise ValueError("일반 답변에는 답변 보류 값이나 이유를 넣지 않습니다")
        return self


class AgentToolTurn(Contract):
    turn_type: Literal["tool"]
    tool_call: ToolCall


class AgentFinalTurn(Contract):
    turn_type: Literal["final"]
    answer: AgentFinal


AgentTurnValue = Annotated[
    AgentToolTurn | AgentFinalTurn,
    Field(discriminator="turn_type"),
]


class AgentTurn(RootModel[AgentTurnValue]):
    """Provider JSON Schema에도 tool/final의 필수 필드 차이를 표현한다."""

    @property
    def turn_type(self) -> Literal["tool", "final"]:
        return self.root.turn_type

    @property
    def tool_call(self) -> ToolCall | None:
        return getattr(self.root, "tool_call", None)

    @property
    def answer(self) -> AgentFinal | None:
        return getattr(self.root, "answer", None)


class AuthorizationScope(Contract):
    allowed_record_ids: set[str] = Field(default_factory=set)
    allowed_lookup_fields: set[str] = Field(default_factory=set)
    can_create_ticket: bool = False

    @field_serializer("allowed_record_ids", "allowed_lookup_fields")
    def sorted_values(self, value: set[str]) -> list[str]:
        return sorted(value)


class AgentUpstreamContext(Contract):
    sample_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    source_license: str = Field(min_length=1)
    selected_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    responses_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output: StructuredAnswer
    source_evidence_kind: Literal["test_only", "live_quality"]
    source_status: Literal["pass", "fail", "inconclusive"]

    @model_validator(mode="after")
    def output_hash_matches(self) -> AgentUpstreamContext:
        if self.output_sha256 != structured_answer_sha256(self.output):
            raise ValueError("Week 4 구조화 답의 canonical SHA-256이 다릅니다")
        return self


class AgentCase(Contract):
    sample_id: str = Field(min_length=1)
    source_sample_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    risk_level: Literal["low", "medium", "high"]
    instruction: str = Field(min_length=1)
    authorization: AuthorizationScope
    max_tool_calls: int = Field(ge=0, le=4)
    fault_seed: int | None = Field(default=None, ge=0)
    expected_calls: list[ToolCall]
    expected_ticket_count: int = Field(ge=0)
    expected_abstained: bool
    expected_answer_contains: list[str] = Field(default_factory=list)
    expected_abstention_reason_contains: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def final_expectation_is_complete(self) -> AgentCase:
        if len(self.expected_calls) > self.max_tool_calls:
            raise ValueError("기대 도구 호출 수는 호출 상한 이하여야 합니다")
        ticket_calls = [
            call for call in self.expected_calls if isinstance(call, CreateTicketCall)
        ]
        for call in self.expected_calls:
            if isinstance(call, LookupCall) and (
                call.record_id not in self.authorization.allowed_record_ids
                or not set(call.fields) <= self.authorization.allowed_lookup_fields
            ):
                raise ValueError("기대 조회 호출은 권한 범위 안에 있어야 합니다")
            if isinstance(call, CreateTicketCall) and not self.authorization.can_create_ticket:
                raise ValueError("기대 ticket 호출에는 생성 권한이 필요합니다")
        if self.expected_ticket_count != len(
            {call.idempotency_key for call in ticket_calls}
        ):
            raise ValueError("기대 ticket 수는 고유 중복 방지 키 수와 같아야 합니다")
        if self.fault_seed is not None and (
            len(ticket_calls) != 2 or ticket_calls[0] != ticket_calls[1]
        ):
            raise ValueError("fault 사례는 같은 ticket 요청을 정확히 두 번 기대해야 합니다")
        if self.expected_abstained:
            if self.expected_answer_contains:
                raise ValueError("답변 보류 사례에는 최종 답 핵심값을 넣지 않습니다")
            if not self.expected_abstention_reason_contains:
                raise ValueError("답변 보류 사례에는 보류 이유 핵심값이 필요합니다")
        elif not self.expected_answer_contains or self.expected_abstention_reason_contains:
            raise ValueError("일반 답변에는 최종 답 핵심값만 필요합니다")
        return self


class AgentRun(Contract):
    sample_id: str
    source_sample_id: str
    family_id: str
    upstream_context: AgentUpstreamContext
    risk_level: Literal["low", "medium", "high"]
    authorization: AuthorizationScope
    max_tool_calls: int = Field(ge=0)
    fault_seed: int | None = Field(default=None, ge=0)
    final_answer: AgentFinal | None
    tool_calls: list[ToolCall]
    trace: list[dict[str, Any]]
    ledger: list[dict[str, Any]]
    initial_state: dict[str, Any]
    final_state: dict[str, Any]
    errors: list[str]
    evidence_kind: Literal["test_only", "live_quality"]
    phoenix_trace_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class AgentScore(Contract):
    sample_id: str
    status: Literal["passed", "failed", "inconclusive"]
    scores: dict[str, float]
    reasons: dict[str, str]
    evidence_kind: Literal["test_only", "live_quality"]
