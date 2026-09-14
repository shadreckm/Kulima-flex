"""OpenAI LLM client with VC-grade prompting."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from kulima.config import get_settings


class LLMClient:
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.openai_model
        self._api_key = (api_key or settings.openai_api_key or "").strip()
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("Missing OpenAI credentials. Please pass an api_key or set the OPENAI_API_KEY environment variable.")
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def complete(self, system: str, user: str, temperature: float = 0.35) -> str:
        if not self._api_key:
            raise RuntimeError("Missing OpenAI credentials. Please pass an api_key or set the OPENAI_API_KEY environment variable.")
        return self._call_completion(system, user, temperature)

    @retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3), reraise=True)
    def _call_completion(self, system: str, user: str, temperature: float = 0.35) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    def complete_json(self, system: str, user: str, temperature: float = 0.2) -> dict[str, Any]:
        raw = self.complete(
            system=system + "\n\nRespond ONLY with valid JSON. No markdown fences.",
            user=user,
            temperature=temperature,
        )
        return parse_json_payload(raw)


def parse_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return {"data": data}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {"raw": raw, "parse_error": True}
