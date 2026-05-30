import sqlite3
from pathlib import Path

from saturday_job_helper.alerting import (
    AlertPolicy,
    JobAlertService,
    TelegramNotifier,
    build_alert_message,
)
from saturday_job_helper.db import init_db
from saturday_job_helper.discovery import DiscoveredJob
from saturday_job_helper.repository import JobRepository
from saturday_job_helper.scoring import ScoreResult


def sample_job(*, hash_value: str = "hash-alert", title: str = "Junior ML Engineer") -> DiscoveredJob:
    return DiscoveredJob(
        source="greenhouse",
        external_id=hash_value,
        company="Acme AI",
        title=title,
        location="Remote - India",
        remote_status="remote",
        application_url=f"https://example.com/{hash_value}",
        description="Python, ML, RAG, APIs, junior friendly",
        description_hash=hash_value,
    )


def score(repo: JobRepository, job_id: int, *, score_value: int, confidence: int) -> None:
    repo.save_match_score(
        job_id=job_id,
        result=ScoreResult(
            match_score=score_value,
            confidence_score=confidence,
            explanation="Strong Ajith fit for Python ML and RAG projects",
            rejection_reason=None,
            recommended_action="alert",
        ),
        scoring_model="test-model",
    )


def test_repository_returns_alert_candidates_sorted_by_score(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)
    repo = JobRepository(db_path)
    repo.upsert_jobs(
        [
            sample_job(hash_value="low", title="Low Match"),
            sample_job(hash_value="high", title="High Match"),
        ]
    )
    jobs = repo.get_unscored_jobs(limit=10)
    low = next(job for job in jobs if job.description_hash == "low")
    high = next(job for job in jobs if job.description_hash == "high")
    score(repo, low.id, score_value=65, confidence=90)
    score(repo, high.id, score_value=91, confidence=80)

    candidates = repo.get_alert_candidates(min_score=70, min_confidence=50, limit=5)

    assert [candidate.job.title for candidate in candidates] == ["High Match"]
    assert candidates[0].score.score == 91
    assert candidates[0].score.confidence_score == 80


def test_build_alert_message_contains_approval_instructions():
    message = build_alert_message(
        job_title="Junior ML Engineer",
        company="Acme AI",
        location="Remote - India",
        score=91,
        confidence_score=80,
        explanation="Strong Python ML fit",
        application_url="https://example.com/job",
    )

    assert "Junior ML Engineer" in message
    assert "Score: 91" in message
    assert "Reply APPROVE" in message
    assert "https://example.com/job" in message


def test_job_alert_service_dry_run_does_not_send_and_keeps_status_scored(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)
    repo = JobRepository(db_path)
    repo.upsert_jobs([sample_job()])
    job = repo.get_unscored_jobs(limit=1)[0]
    score(repo, job.id, score_value=92, confidence=85)
    sent_messages = []

    service = JobAlertService(
        repository=repo,
        policy=AlertPolicy(min_score=70, min_confidence=50, max_alerts=20),
        send_alert=sent_messages.append,
    )

    summary = service.send_pending_alerts(dry_run=True)

    assert summary.eligible == 1
    assert summary.sent == 0
    assert summary.dry_run is True
    assert sent_messages == []
    with sqlite3.connect(db_path) as conn:
        status = conn.execute("select status from jobs where id = ?", (job.id,)).fetchone()[0]
    assert status == "Scored"


def test_job_alert_service_sends_and_marks_alerted(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)
    repo = JobRepository(db_path)
    repo.upsert_jobs([sample_job()])
    job = repo.get_unscored_jobs(limit=1)[0]
    score(repo, job.id, score_value=92, confidence=85)
    sent_messages = []

    service = JobAlertService(
        repository=repo,
        policy=AlertPolicy(min_score=70, min_confidence=50, max_alerts=20),
        send_alert=sent_messages.append,
    )

    summary = service.send_pending_alerts(dry_run=False)

    assert summary.eligible == 1
    assert summary.sent == 1
    assert len(sent_messages) == 1
    assert "Junior ML Engineer" in sent_messages[0]
    with sqlite3.connect(db_path) as conn:
        status = conn.execute("select status from jobs where id = ?", (job.id,)).fetchone()[0]
    assert status == "Alerted"


def test_telegram_notifier_posts_send_message_payload():
    calls = []

    def fake_post(url: str, payload: dict[str, str]) -> None:
        calls.append((url, payload))

    notifier = TelegramNotifier(
        bot_token="123:abc",
        chat_id="98765",
        post_json=fake_post,
    )

    notifier.send("hello Ajith")

    assert calls == [
        (
            "https://api.telegram.org/bot123:abc/sendMessage",
            {
                "chat_id": "98765",
                "text": "hello Ajith",
                "disable_web_page_preview": "false",
            },
        )
    ]
