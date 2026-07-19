"""OpenAI LLM client with VC-grade prompting."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from kulima.config import get_settings


class LLMClient:
    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.openai_model
        self.client = OpenAI(api_key=settings.openai_api_key)

    @retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3), reraise=True)
    def complete(self, system: str, user: str, temperature: float = 0.35) -> str:
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
