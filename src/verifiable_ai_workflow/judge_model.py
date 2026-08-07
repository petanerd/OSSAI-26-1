"""DeepEval Judge가 Week 1의 LiteLLM 예산 경로를 재사용하게 한다."""

from __future__ import annotations

import json
from typing import Any

from deepeval.models import DeepEvalBaseLLM
from pydantic import BaseModel

from .providers.litellm_provider import LiteLLMProvider


class CourseJudgeModel(DeepEvalBaseLLM):
    def __init__(self, provider: LiteLLMProvider) -> None:
        self.provider = provider
        self.call_id = "judge"
        self.call_records: list[dict[str, Any]] = []
        super().__init__(model=provider.model)

    def load_model(self) -> CourseJudgeModel:
        return self

    def get_model_name(self, *args, **kwargs) -> str:
        del args, kwargs
        return self.provider.model

    def supports_structured_outputs(self) -> bool:
        return True

    def supports_json_mode(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        schema: type[BaseModel] | None = None,
        **kwargs,
    ):
        del kwargs
        content = self.provider.generate(
            self.call_id,
            [{"role": "user", "content": prompt}],
            response_schema=schema,
        )
        self.call_records.append(dict(self.provider.last_call or {}))
        if schema is None:
            return content
        if isinstance(content, str):
            content = json.loads(content)
        return schema.model_validate(content)

    async def a_generate(
        self,
        prompt: str,
        schema: type[BaseModel] | None = None,
        **kwargs,
    ):
        return self.generate(prompt, schema=schema, **kwargs)
