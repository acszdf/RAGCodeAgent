from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from .config import Settings


class LLMConfigurationError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class ChatModel(Protocol):
    model_name: str

    def complete_json(self, system_prompt: str, user_prompt: str) -> str: ...


@dataclass
class OpenAICompatibleChatModel:
    settings: Settings

    def __post_init__(self) -> None:
        if not self.settings.llm_api_key:
            raise LLMConfigurationError(
                "No API key configured. Set LLM_API_KEY in .env; "
                "OPENAI_API_KEY, DEEPSEEK_API_KEY, and ZHIPUAI_API_KEY are also supported."
            )
        self.model_name = self.settings.llm_model
        self._client = OpenAI(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            timeout=self.settings.llm_timeout_seconds,
        )

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.llm_temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise LLMResponseError("model returned an empty response")
        return content


def parse_json_response(raw: str) -> dict:
    candidate = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise LLMResponseError("model response does not contain a JSON object")
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"invalid JSON response: {exc}") from exc
    if not isinstance(value, dict):
        raise LLMResponseError("model response must be a JSON object")
    return value
