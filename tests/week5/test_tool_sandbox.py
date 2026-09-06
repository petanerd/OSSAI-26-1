import pytest

from verifiable_ai_workflow.schemas.agent import (
    AuthorizationScope,
    CalculatorCall,
    CreateTicketCall,
    LookupCall,
)
from verifiable_ai_workflow.tools import (
    AfterCommitTimeout,
    AuthorizationDenied,
    IdempotencyConflict,
    ToolSandbox,
)


def test_calculator_uses_decimal() -> None:
    result = ToolSandbox(AuthorizationScope(), {}).execute(
        CalculatorCall(tool="calculator", expression="(0.1 + 0.2) * 10")
    )
    assert result == {"value": "3"}


def test_lookup_denies_personal_phone() -> None:
    sandbox = ToolSandbox(
        AuthorizationScope(
            allowed_record_ids={"staff-01"},
            allowed_lookup_fields={"office_phone"},
        ),
        {"staff-01": {"office_phone": "02", "personal_phone": "010"}},
    )
    with pytest.raises(AuthorizationDenied):
        sandbox.execute(
            LookupCall(
                tool="lookup",
                record_id="staff-01",
                fields=["personal_phone"],
            )
        )

    with pytest.raises(AuthorizationDenied):
        sandbox.execute(
            CreateTicketCall(
                tool="create_ticket",
                title="권한 없음",
                description="생성되면 안 됩니다.",
                idempotency_key="case-denied-ticket",
            )
        )
    assert sandbox.final_state["ticket_count"] == 0


def test_retry_same_ticket_does_not_duplicate_side_effect() -> None:
    sandbox = ToolSandbox(AuthorizationScope(can_create_ticket=True), {})
    call = CreateTicketCall(
        tool="create_ticket",
        title="검토",
        description="결과를 검토합니다.",
        idempotency_key="case-001-review",
    )
    with pytest.raises(AfterCommitTimeout):
        sandbox.execute(call, fail_after_commit=True)
    retry = sandbox.execute(call)

    assert retry["replayed"] is True
    assert sandbox.final_state["ticket_count"] == 1
    assert [item["ticket_count_after"] for item in sandbox.ledger] == [1, 1]

    with pytest.raises(IdempotencyConflict):
        sandbox.execute(
            call.model_copy(update={"description": "다른 내용입니다."})
        )
    assert sandbox.final_state["ticket_count"] == 1
    assert sandbox.ledger[-1]["error_type"] == "IdempotencyConflict"
