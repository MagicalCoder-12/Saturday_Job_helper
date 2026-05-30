from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    text: str
    fallback_chain: list[str] = field(default_factory=list)


ProviderCall = Callable[[str], ProviderResult]


class LLMRouter:
    """Routes document generation across Groq -> Ollama cloud -> LM Studio."""

    def __init__(
        self,
        *,
        groq_call: ProviderCall,
        ollama_cloud_call: ProviderCall,
        lm_studio_call: ProviderCall,
        groq_document_limit: int = 1,
    ) -> None:
        self._groq_call = groq_call
        self._ollama_cloud_call = ollama_cloud_call
        self._lm_studio_call = lm_studio_call
        self._groq_document_limit = max(0, groq_document_limit)
        self._groq_documents_used = 0

    @property
    def groq_documents_used(self) -> int:
        return self._groq_documents_used

    def generate_document(self, prompt: str) -> ProviderResult:
        chain: list[str] = []
        providers: list[tuple[str, ProviderCall]] = []

        if self._groq_documents_used < self._groq_document_limit:
            providers.append(("groq", self._groq_call))
        providers.extend(
            [
                ("ollama_cloud", self._ollama_cloud_call),
                ("lm_studio", self._lm_studio_call),
            ]
        )

        last_error: Exception | None = None
        for provider_name, provider_call in providers:
            chain.append(provider_name)
            try:
                result = provider_call(prompt)
                if provider_name == "groq":
                    self._groq_documents_used += 1
                return ProviderResult(
                    provider=result.provider,
                    text=result.text,
                    fallback_chain=chain,
                )
            except Exception as exc:  # noqa: BLE001 - provider failures must fallback safely
                last_error = exc
                continue

        raise RuntimeError(f"all LLM providers failed: {last_error}")
