from pathlib import Path

from saturday_job_helper.config import Settings, load_settings


def test_load_settings_reads_required_provider_chain(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "PROJECT_ROOT=/tmp/project",
                "DATA_DIR=/tmp/project/data",
                "DATABASE_URL=sqlite:////tmp/project/data/app.sqlite3",
                "CANDIDATE_PROFILE_PATH=/tmp/profile.md",
                "MASTER_RESUME_DOCX_PATH=/tmp/resume.docx",
                "MASTER_RESUME_EXTRACTED_MD_PATH=/tmp/resume.md",
                "OUTPUT_DOCUMENTS_DIR=/tmp/project/data/output/documents",
                "PRIMARY_LLM_PROVIDER=groq",
                "SECONDARY_LLM_PROVIDER=ollama_cloud",
                "FALLBACK_LLM_PROVIDER=lm_studio",
                "GROQ_API_KEY=gsk_test",
                "GROQ_SCORING_MODEL=groq-score",
                "GROQ_DOCUMENT_MODEL=groq-doc",
                "GROQ_MAX_DOCUMENT_TAILORINGS_PER_RUN=1",
                "OLLAMA_CLOUD_BASE_URL=https://ollama.example/v1",
                "OLLAMA_CLOUD_API_KEY=ollama-test",
                "OLLAMA_CLOUD_SCORING_MODEL=ollama-score",
                "OLLAMA_CLOUD_DOCUMENT_MODEL=ollama-doc",
                "LM_STUDIO_BASE_URL=http://localhost:1234/v1",
                "LM_STUDIO_FALLBACK_MODEL=google/gemma-4-e4b",
                "TELEGRAM_BOT_TOKEN=123:abc",
                "TELEGRAM_CHAT_ID=12345",
                "MAX_APPLICATIONS_PER_DAY=10",
                "MAX_ALERTS_PER_RUN=20",
                "REQUIRE_APPROVAL_BEFORE_APPLYING=true",
                "AUTO_APPLY_ENABLED=false",
            ]
        )
    )

    settings = load_settings(env_file)

    assert settings.primary_llm_provider == "groq"
    assert settings.secondary_llm_provider == "ollama_cloud"
    assert settings.fallback_llm_provider == "lm_studio"
    assert settings.groq_max_document_tailorings_per_run == 1
    assert settings.ollama_cloud_document_model == "ollama-doc"
    assert settings.require_approval_before_applying is True
    assert settings.auto_apply_enabled is False


def test_settings_rejects_auto_apply_without_approval():
    try:
        Settings(
            project_root=Path("/tmp/project"),
            data_dir=Path("/tmp/project/data"),
            database_url="sqlite:////tmp/project/data/app.sqlite3",
            candidate_profile_path=Path("/tmp/profile.md"),
            master_resume_docx_path=Path("/tmp/resume.docx"),
            master_resume_extracted_md_path=Path("/tmp/resume.md"),
            output_documents_dir=Path("/tmp/project/data/output/documents"),
            groq_api_key="gsk_test",
            groq_scoring_model="groq-score",
            groq_document_model="groq-doc",
            ollama_cloud_base_url="https://ollama.example/v1",
            ollama_cloud_api_key="ollama-test",
            ollama_cloud_scoring_model="ollama-score",
            ollama_cloud_document_model="ollama-doc",
            telegram_bot_token="123:abc",
            telegram_chat_id="12345",
            require_approval_before_applying=False,
            auto_apply_enabled=True,
        )
    except ValueError as exc:
        assert "AUTO_APPLY_ENABLED requires approval gate" in str(exc)
    else:
        raise AssertionError("unsafe settings should be rejected")
