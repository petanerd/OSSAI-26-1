"""주차별 실제 실습이 같은 LiteLLM 안전 설정을 재사용한다."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .config.settings import LabSettings
from .live_execution import LiveBudget, LiveBudgetCaps
from .providers.litellm_provider import LiteLLMProvider


def build_course_provider(
    settings: LabSettings,
    caps: LiveBudgetCaps,
    *,
    on_response: Callable[[dict[str, Any]], None] | None = None,
    budget: LiveBudget | None = None,
) -> LiteLLMProvider:
    return LiteLLMProvider(
        model=settings.provider.model,
        expected_actual_model=settings.provider.expected_actual_model,
        api_key_env=settings.provider.api_key_env,
        api_base=settings.provider.api_base,
        structured_output="json_schema",
        max_requests=caps.max_requests,
        max_attempts=caps.max_attempts,
        requests_per_minute=settings.limits.requests_per_minute,
        max_retries=settings.limits.max_retries,
        retry_initial_seconds=settings.limits.retry_initial_seconds,
        max_cost_usd=caps.max_cost_usd,
        max_input_tokens=caps.max_input_tokens,
        max_output_tokens=caps.max_output_tokens,
        max_wall_seconds=caps.max_wall_seconds,
        request_input_token_ceiling=settings.limits.request_input_token_ceiling,
        request_output_token_ceiling=settings.limits.request_output_token_ceiling,
        request_timeout_seconds=settings.limits.request_timeout_seconds,
        input_cost_per_token_usd=settings.provider.input_cost_per_token_usd,
        output_cost_per_token_usd=settings.provider.output_cost_per_token_usd,
        temperature=settings.provider.temperature,
        top_p=settings.provider.top_p,
        seed=settings.provider.seed,
        thinking_mode=settings.provider.thinking_mode,
        thinking_parameter=settings.provider.thinking_parameter,
        max_images_per_prompt=settings.provider.max_images_per_prompt,
        budget=budget,
        on_response_received=on_response,
    )
