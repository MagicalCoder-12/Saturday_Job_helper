from saturday_job_helper.llm_router import LLMRouter, ProviderResult


def test_router_uses_groq_for_first_document_then_ollama_for_next():
    calls = []

    def groq(prompt: str) -> ProviderResult:
        calls.append(("groq", prompt))
        return ProviderResult(provider="groq", text="groq-doc")

    def ollama(prompt: str) -> ProviderResult:
        calls.append(("ollama_cloud", prompt))
        return ProviderResult(provider="ollama_cloud", text="ollama-doc")

    router = LLMRouter(
        groq_call=groq,
        ollama_cloud_call=ollama,
        lm_studio_call=lambda prompt: ProviderResult(provider="lm_studio", text="local-doc"),
        groq_document_limit=1,
    )

    first = router.generate_document("first")
    second = router.generate_document("second")

    assert first.provider == "groq"
    assert second.provider == "ollama_cloud"
    assert [call[0] for call in calls] == ["groq", "ollama_cloud"]


def test_router_falls_back_to_lm_studio_when_groq_and_ollama_fail():
    def fail(_: str) -> ProviderResult:
        raise RuntimeError("provider down")

    router = LLMRouter(
        groq_call=fail,
        ollama_cloud_call=fail,
        lm_studio_call=lambda prompt: ProviderResult(provider="lm_studio", text=f"local:{prompt}"),
        groq_document_limit=1,
    )

    result = router.generate_document("resume")

    assert result.provider == "lm_studio"
    assert result.text == "local:resume"
    assert result.fallback_chain == ["groq", "ollama_cloud", "lm_studio"]
