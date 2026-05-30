from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import httpx


@dataclass(frozen=True)
class ProviderEndpoint:
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 120


ChatFunction = Callable[[ProviderEndpoint, str], str]


class OpenAICompatibleChatClient:
    def chat(self, endpoint: ProviderEndpoint, prompt: str) -> str:
        url = endpoint.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {endpoint.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": endpoint.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return strict JSON only. No markdown unless asked.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 900,
        }
        with httpx.Client(timeout=endpoint.timeout_seconds, follow_redirects=True) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"]["content"])


class ScoringProviderChain:
    def __init__(self, *, endpoints: list[ProviderEndpoint], chat: ChatFunction | None = None) -> None:
        self.endpoints = endpoints
        self.chat = chat or OpenAICompatibleChatClient().chat

    def score(self, prompt: str) -> tuple[str, str]:
        errors: list[str] = []
        for endpoint in self.endpoints:
            try:
                text = self.chat(endpoint, prompt)
                return text, f"{endpoint.provider}:{endpoint.model}"
            except Exception as exc:  # noqa: BLE001 - provider chain must fallback
                errors.append(f"{endpoint.provider}: {exc}")
                continue
        raise RuntimeError("all scoring providers failed: " + " | ".join(errors))
