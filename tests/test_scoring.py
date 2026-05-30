import sqlite3
from pathlib import Path

from saturday_job_helper.db import init_db
from saturday_job_helper.discovery import DiscoveredJob
from saturday_job_helper.repository import JobRepository
from saturday_job_helper.scoring import (
    JobScoringService,
    ScoreResult,
    build_scoring_prompt,
    parse_score_response,
)


def sample_job() -> DiscoveredJob:
    return DiscoveredJob(
        source="greenhouse",
        external_id="job-1",
        company="Acme AI",
        title="Junior AI Engineer",
        location="Remote - India",
        remote_status="remote",
        application_url="https://example.com/job-1",
        description="Python, machine learning, RAG, TensorFlow, APIs, internship friendly",
        description_hash="hash-1",
    )


def test_build_scoring_prompt_contains_profile_and_job_details():
    prompt = build_scoring_prompt(
        candidate_profile="Ajith: Python, ML, TensorFlow, Unity, RAG projects",
        job=sample_job(),
    )

    assert "Return strict JSON only" in prompt
    assert "Junior AI Engineer" in prompt
    assert "Ajith" in prompt
    assert "match_score" in prompt
    assert "recommended_action" in prompt


def test_parse_score_response_accepts_json_object_inside_markdown_fence():
    result = parse_score_response(
        """```json
        {
          "match_score": 86,
          "confidence_score": 78,
          "explanation": "Strong Python and RAG match",
          "rejection_reason": null,
          "recommended_action": "alert"
        }
        ```"""
    )

    assert result.match_score == 86
    assert result.confidence_score == 78
    assert result.recommended_action == "alert"
    assert result.rejection_reason is None


def test_parse_score_response_clamps_scores_and_rejects_bad_actions():
    result = parse_score_response(
        '{"match_score": 140, "confidence_score": -5, "explanation": "ok", '
        '"rejection_reason": "", "recommended_action": "unknown"}'
    )

    assert result.match_score == 100
    assert result.confidence_score == 0
    assert result.recommended_action == "manual_review"


def test_repository_returns_unscored_jobs_and_saves_latest_score(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)
    repo = JobRepository(db_path)
    repo.upsert_jobs([sample_job()])

    jobs = repo.get_unscored_jobs(limit=5)
    repo.save_match_score(
        job_id=jobs[0].id,
        result=ScoreResult(
            match_score=88,
            confidence_score=80,
            explanation="Strong ML project match",
            rejection_reason=None,
            recommended_action="alert",
        ),
        scoring_model="test-model",
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "select score, confidence_score, explanation, scoring_model from match_scores"
        ).fetchone()
        status = conn.execute("select status from jobs").fetchone()[0]

    assert len(jobs) == 1
    assert jobs[0].title == "Junior AI Engineer"
    assert row == (88, 80, "Strong ML project match", "test-model")
    assert status == "Scored"


def test_scoring_service_scores_jobs_and_persists_results(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)
    repo = JobRepository(db_path)
    repo.upsert_jobs([sample_job()])
    calls = []

    def fake_llm(prompt: str) -> tuple[str, str]:
        calls.append(prompt)
        return (
            '{"match_score": 91, "confidence_score": 82, '
            '"explanation": "Great Ajith ML match", '
            '"rejection_reason": null, "recommended_action": "alert"}',
            "groq:test-score",
        )

    service = JobScoringService(
        repository=repo,
        candidate_profile="Ajith profile with Python ML RAG projects",
        score_with_llm=fake_llm,
    )
    summary = service.score_unscored_jobs(limit=2)

    assert summary.scored == 1
    assert summary.failed == 0
    assert calls and "Ajith profile" in calls[0]
    assert repo.get_unscored_jobs(limit=5) == []
