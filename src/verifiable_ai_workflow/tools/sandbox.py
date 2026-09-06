"""계산기·조회·티켓을 외부 시스템 없이 실행하는 작은 sandbox."""

from __future__ import annotations

import ast
from decimal import Decimal, InvalidOperation
from typing import Any

from ..schemas.agent import (
    AuthorizationScope,
    CalculatorCall,
    CreateTicketCall,
    LookupCall,
    ToolCall,
)


class ToolError(RuntimeError):
    pass


class AuthorizationDenied(ToolError):
    pass


class IdempotencyConflict(ToolError):
    pass


class AfterCommitTimeout(ToolError):
    pass


def authorization_denial(
    authorization: AuthorizationScope,
    call: ToolCall,
) -> str | None:
    if isinstance(call, LookupCall):
        if call.record_id not in authorization.allowed_record_ids:
            return "조회할 수 없는 record입니다"
        denied = set(call.fields) - authorization.allowed_lookup_fields
        if denied:
            return f"조회할 수 없는 field입니다: {sorted(denied)}"
    if isinstance(call, CreateTicketCall) and not authorization.can_create_ticket:
        return "ticket 생성 권한이 없습니다"
    return None


class ToolSandbox:
    def __init__(
        self,
        authorization: AuthorizationScope,
        records: dict[str, dict[str, Any]],
    ) -> None:
        self.authorization = authorization
        self.records = records
        self.tickets: dict[str, dict[str, str]] = {}
        self.idempotency: dict[str, tuple[dict[str, str], str]] = {}
        self.ledger: list[dict[str, Any]] = []

    @property
    def final_state(self) -> dict[str, Any]:
        return {"ticket_count": len(self.tickets), "tickets": dict(self.tickets)}

    def execute(self, call: ToolCall, *, fail_after_commit: bool = False) -> dict[str, Any]:
        entry = {
            "sequence": len(self.ledger) + 1,
            "call": call.model_dump(mode="json"),
        }
        try:
            denial = authorization_denial(self.authorization, call)
            if denial is not None:
                raise AuthorizationDenied(denial)
            if isinstance(call, CalculatorCall):
                result = {"value": self._calculate(call.expression)}
            elif isinstance(call, LookupCall):
                result = self._lookup(call)
            elif isinstance(call, CreateTicketCall):
                result = self._create_ticket(call, fail_after_commit=fail_after_commit)
            else:
                raise ToolError(f"지원하지 않는 도구입니다: {type(call).__name__}")
        except ToolError as exc:
            entry.update(status="error", error_type=type(exc).__name__)
            raise
        else:
            entry.update(status="success", result=result)
            return result
        finally:
            entry["ticket_count_after"] = len(self.tickets)
            self.ledger.append(entry)

    def _calculate(self, expression: str) -> str:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ToolError("계산식을 읽을 수 없습니다") from exc
        if sum(1 for _ in ast.walk(tree)) > 40:
            raise ToolError("계산식이 너무 복잡합니다")

        def evaluate(node: ast.AST) -> Decimal:
            if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
                return Decimal(str(node.value))
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = evaluate(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp) and isinstance(
                node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
            ):
                left, right = evaluate(node.left), evaluate(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                return left / right
            raise ToolError("계산기는 숫자와 +, -, *, /, 괄호만 허용합니다")

        try:
            value = evaluate(tree.body)
        except (InvalidOperation, ArithmeticError) as exc:
            raise ToolError("계산할 수 없는 수식입니다") from exc
        rendered = format(value, "f")
        return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered

    def _lookup(self, call: LookupCall) -> dict[str, Any]:
        record = self.records.get(call.record_id)
        if record is None or any(field not in record for field in call.fields):
            raise ToolError("record 또는 field가 없습니다")
        return {
            "record_id": call.record_id,
            "fields": {field: record[field] for field in call.fields},
        }

    def _create_ticket(
        self,
        call: CreateTicketCall,
        *,
        fail_after_commit: bool,
    ) -> dict[str, Any]:
        payload = {"title": call.title, "description": call.description}
        existing = self.idempotency.get(call.idempotency_key)
        if existing is not None:
            old_payload, ticket_id = existing
            if old_payload != payload:
                raise IdempotencyConflict("같은 idempotency key의 내용이 다릅니다")
            return {"ticket": self.tickets[ticket_id], "replayed": True}
        ticket_id = f"TICKET-{len(self.tickets) + 1:04d}"
        ticket = {"ticket_id": ticket_id, **payload, "status": "open"}
        self.tickets[ticket_id] = ticket
        self.idempotency[call.idempotency_key] = (payload, ticket_id)
        if fail_after_commit:
            raise AfterCommitTimeout("ticket은 생성됐지만 응답 전에 timeout이 발생했습니다")
        return {"ticket": ticket, "replayed": False}
