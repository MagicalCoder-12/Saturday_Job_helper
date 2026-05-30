from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    environment: str = "development"
    log_level: str = "INFO"
    project_root: Path
    data_dir: Path
    database_url: str

    candidate_profile_path: Path
    master_resume_docx_path: Path
    master_resume_extracted_md_path: Path
    output_documents_dir: Path

    primary_llm_provider: str = "groq"
    secondary_llm_provider: str = "ollama_cloud"
    fallback_llm_provider: str = "lm_studio"

    groq_api_key: str
    groq_scoring_model: str
    groq_document_model: str
    groq_max_document_tailorings_per_run: int = Field(default=1, ge=0)
    groq_fallback_on_low_tokens: bool = True
    groq_fallback_on_error: bool = True

    ollama_cloud_enabled: bool = True
    ollama_cloud_base_url: str
    ollama_cloud_api_key: str
    ollama_cloud_scoring_model: str
    ollama_cloud_document_model: str
    ollama_cloud_timeout_seconds: int = Field(default=120, gt=0)
    ollama_cloud_max_retries: int = Field(default=2, ge=0)

    lm_studio_enabled: bool = True
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_api_key: str = "lm-studio"
    lm_studio_fallback_model: str = "google/gemma-4-e4b"
    lm_studio_fallback_on_ollama_error: bool = True

    allow_cloud_llm_for_documents: bool = True
    max_llm_tokens_per_job: int = Field(default=8000, gt=0)
    max_llm_cost_usd_per_run: float = Field(default=1.0, ge=0)

    telegram_bot_token: str
    telegram_chat_id: str
    telegram_restrict_to_chat: bool = True
    telegram_send_generated_pdfs: bool = True

    max_applications_per_day: int = Field(default=10, ge=0)
    max_alerts_per_run: int = Field(default=20, ge=0)
    require_approval_before_generating_documents: bool = True
    require_approval_before_applying: bool = True
    auto_apply_enabled: bool = False

    enable_greenhouse: bool = True
    enable_lever: bool = True
    enable_wellfound: bool = False
    enable_linkedin: bool = False

    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_sender_email: str = ""
    smtp_recipient_email: str = ""

    linkedin_username: str = ""
    linkedin_password: str = ""
    wellfound_username: str = ""
    wellfound_password: str = ""

    scheduler_enabled: bool = False
    scheduler_timezone: str = "Asia/Kolkata"
    job_discovery_cron: str = "0 */2 * * *"

    @field_validator(
        "groq_api_key",
        "groq_scoring_model",
        "groq_document_model",
        "ollama_cloud_base_url",
        "ollama_cloud_api_key",
        "ollama_cloud_scoring_model",
        "ollama_cloud_document_model",
        "telegram_bot_token",
        "telegram_chat_id",
    )
    @classmethod
    def required_string(cls, value: str) -> str:
        if not value:
            raise ValueError("required configuration value is blank")
        return value

    @model_validator(mode="after")
    def enforce_safety_gates(self) -> "Settings":
        if self.auto_apply_enabled and not self.require_approval_before_applying:
            raise ValueError("AUTO_APPLY_ENABLED requires approval gate")
        if self.primary_llm_provider != "groq":
            raise ValueError("primary provider must be groq for the approved workflow")
        if self.secondary_llm_provider != "ollama_cloud":
            raise ValueError("secondary provider must be ollama_cloud for the approved workflow")
        if self.fallback_llm_provider != "lm_studio":
            raise ValueError("fallback provider must be lm_studio for the approved workflow")
        return self


def _coerce_env_key(key: str) -> str:
    return key.lower()


def load_settings(env_file: Path | str = ".env") -> Settings:
    raw = dotenv_values(env_file)
    normalized: dict[str, Any] = {_coerce_env_key(k): v for k, v in raw.items() if v is not None}
    return Settings(**normalized)
