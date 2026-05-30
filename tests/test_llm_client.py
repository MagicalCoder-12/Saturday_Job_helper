from saturday_job_helper.llm_client import ProviderEndpoint, ScoringProviderChain


def test_scoring_provider_chain_uses_groq_then_falls_back_to_ollama():
    calls = []

    def chat(endpoint: ProviderEndpoint, prompt: str) -> str:
        calls.append((endpoint.provider, prompt))
        if endpoint.provider == "groq":
            raise RuntimeError("rate limited")
        return '{"match_score": 80, "confidence_score": 70, "explanation": "ok", "rejection_reason": null, "recommended_action": "alert"}'

    chain = ScoringProviderChain(
        endpoints=[
            ProviderEndpoint("groq", "https://api.groq.com/openai/v1", "key", "groq-model"),
            ProviderEndpoint("ollama_cloud", "https://ollama.example/v1", "key", "ollama-model"),
        ],
        chat=chat,
    )

    text, model = chain.score("score this")

    assert "match_score" in text
    assert model == "ollama_cloud:ollama-model"
    assert [call[0] for call in calls] == ["groq", "ollama_cloud"]
