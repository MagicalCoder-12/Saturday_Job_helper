from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import typer

from saturday_job_helper.alerting import AlertPolicy, JobAlertService, TelegramNotifier
from saturday_job_helper.config import Settings, load_settings
from saturday_job_helper.db import init_db
from saturday_job_helper.discovery_service import DiscoveryTarget, JobDiscoveryService
from saturday_job_helper.llm_client import ProviderEndpoint, ScoringProviderChain
from saturday_job_helper.repository import JobRepository
from saturday_job_helper.scoring import JobScoringService

app = typer.Typer(help="Saturday Job Helper CLI")


def _db_path_from_url(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise typer.BadParameter("Only sqlite DATABASE_URL is implemented in Phase 1")
    return Path(parsed.path)


@app.command()
def check_config(env_file: Path = Path(".env")) -> None:
    """Validate configuration without printing secrets."""
    settings = load_settings(env_file)
    typer.echo("config: ok")
    typer.echo(
        "provider_chain: "
        f"{settings.primary_llm_provider} -> "
        f"{settings.secondary_llm_provider} -> "
        f"{settings.fallback_llm_provider}"
    )
    typer.echo(f"groq_document_tailoring_limit: {settings.groq_max_document_tailorings_per_run}")
    typer.echo(f"approval_required_before_apply: {settings.require_approval_before_applying}")
    typer.echo(f"auto_apply_enabled: {settings.auto_apply_enabled}")
    typer.echo(f"telegram_configured: {bool(settings.telegram_bot_token and settings.telegram_chat_id)}")
    typer.echo(f"max_alerts_per_run: {settings.max_alerts_per_run}")


@app.command()
def init_database(env_file: Path = Path(".env")) -> None:
    """Create the local SQLite schema."""
    settings = load_settings(env_file)
    db_path = _db_path_from_url(settings.database_url)
    init_db(db_path)
    typer.echo(f"database: initialized at {db_path}")


def _parse_target(value: str, source: str) -> DiscoveryTarget:
    if ":" in value:
        slug, company_name = value.split(":", 1)
    else:
        slug = value
        company_name = value
    slug = slug.strip()
    company_name = company_name.strip()
    if not slug or not company_name:
        raise typer.BadParameter("Target format must be slug or slug:Company Name")
    return DiscoveryTarget(source=source, company_slug=slug, company_name=company_name)


@app.command()
def discover(
    env_file: Path = Path(".env"),
    greenhouse: list[str] | None = typer.Option(
        None,
        help="Greenhouse board target as slug or slug:Company Name. Can be repeated.",
    ),
    lever: list[str] | None = typer.Option(
        None,
        help="Lever company target as slug or slug:Company Name. Can be repeated.",
    ),
) -> None:
    """Fetch Greenhouse/Lever jobs and store them in SQLite."""
    settings = load_settings(env_file)
    db_path = _db_path_from_url(settings.database_url)
    init_db(db_path)

    greenhouse_targets = greenhouse or []
    lever_targets = lever or []
    targets = [_parse_target(value, "greenhouse") for value in greenhouse_targets]
    targets.extend(_parse_target(value, "lever") for value in lever_targets)
    if not targets:
        raise typer.BadParameter("Provide at least one --greenhouse or --lever target")

    service = JobDiscoveryService(
        repository=JobRepository(db_path),
        enable_greenhouse=settings.enable_greenhouse,
        enable_lever=settings.enable_lever,
    )
    result = service.discover(targets)
    typer.echo(
        "discovery: "
        f"fetched={result.fetched} inserted={result.inserted} "
        f"updated={result.updated} skipped={result.skipped} failed={result.failed}"
    )
    if result.errors:
        for error in result.errors:
            typer.echo(f"discovery_error: {error}", err=True)


def _scoring_provider_chain(settings: Settings) -> ScoringProviderChain:
    endpoints = [
        ProviderEndpoint(
            provider="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key,
            model=settings.groq_scoring_model,
            timeout_seconds=120,
        ),
        ProviderEndpoint(
            provider="ollama_cloud",
            base_url=settings.ollama_cloud_base_url,
            api_key=settings.ollama_cloud_api_key,
            model=settings.ollama_cloud_scoring_model,
            timeout_seconds=settings.ollama_cloud_timeout_seconds,
        ),
        ProviderEndpoint(
            provider="lm_studio",
            base_url=settings.lm_studio_base_url,
            api_key=settings.lm_studio_api_key,
            model=settings.lm_studio_fallback_model,
            timeout_seconds=120,
        ),
    ]
    return ScoringProviderChain(endpoints=endpoints)


@app.command()
def score(env_file: Path = Path(".env"), limit: int = typer.Option(1, min=1, max=20)) -> None:
    """Score unscored jobs using Groq -> Ollama cloud -> LM Studio fallback."""
    settings = load_settings(env_file)
    db_path = _db_path_from_url(settings.database_url)
    init_db(db_path)
    candidate_profile = settings.candidate_profile_path.read_text(encoding="utf-8")
    provider_chain = _scoring_provider_chain(settings)
    service = JobScoringService(
        repository=JobRepository(db_path),
        candidate_profile=candidate_profile,
        score_with_llm=provider_chain.score,
    )
    summary = service.score_unscored_jobs(limit=limit)
    typer.echo(f"scoring: scored={summary.scored} failed={summary.failed}")
    if summary.errors:
        for error in summary.errors:
            typer.echo(f"scoring_error: {error}", err=True)


@app.command()
def send_alerts(
    env_file: Path = Path(".env"),
    min_score: int = typer.Option(70, min=0, max=100),
    min_confidence: int = typer.Option(50, min=0, max=100),
    dry_run: bool = typer.Option(True, help="Preview eligible alerts without sending Telegram messages."),
) -> None:
    """Send Telegram alerts for high-scoring jobs that still need approval."""
    settings = load_settings(env_file)
    db_path = _db_path_from_url(settings.database_url)
    init_db(db_path)
    policy = AlertPolicy(
        min_score=min_score,
        min_confidence=min_confidence,
        max_alerts=settings.max_alerts_per_run,
    )
    notifier = TelegramNotifier(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )
    service = JobAlertService(
        repository=JobRepository(db_path),
        policy=policy,
        send_alert=notifier.send,
    )
    summary = service.send_pending_alerts(dry_run=dry_run)
    typer.echo(
        "alerts: "
        f"eligible={summary.eligible} sent={summary.sent} "
        f"failed={summary.failed} dry_run={summary.dry_run}"
    )
    if summary.errors:
        for error in summary.errors:
            typer.echo(f"alert_error: {error}", err=True)


if __name__ == "__main__":
    app()
