import sqlite3
from pathlib import Path

from saturday_job_helper.db import init_db
from saturday_job_helper.discovery import GreenhouseAdapter, LeverAdapter, normalize_job_text
from saturday_job_helper.repository import JobRepository


def test_greenhouse_adapter_normalizes_board_jobs():
    payload = {
        "jobs": [
            {
                "id": 101,
                "title": "Junior AI Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
                "location": {"name": "Remote - India"},
                "content": "Python, LLM, RAG role",
                "updated_at": "2026-05-30T10:00:00Z",
            }
        ]
    }

    jobs = GreenhouseAdapter(company_slug="acme", company_name="Acme AI").parse_jobs(payload)

    assert len(jobs) == 1
    assert jobs[0].source == "greenhouse"
    assert jobs[0].external_id == "101"
    assert jobs[0].company == "Acme AI"
    assert jobs[0].title == "Junior AI Engineer"
    assert jobs[0].remote_status == "remote"
    assert jobs[0].application_url == "https://boards.greenhouse.io/acme/jobs/101"
    assert jobs[0].description_hash


def test_lever_adapter_normalizes_postings():
    payload = [
        {
            "id": "abc-123",
            "text": "Game AI Developer Intern",
            "hostedUrl": "https://jobs.lever.co/acme/abc-123",
            "categories": {"location": "Hyderabad / Remote", "team": "Engineering"},
            "descriptionPlain": "Unity, Python, gameplay AI",
            "createdAt": 1770000000000,
        }
    ]

    jobs = LeverAdapter(company_slug="acme", company_name="Acme Games").parse_jobs(payload)

    assert len(jobs) == 1
    assert jobs[0].source == "lever"
    assert jobs[0].external_id == "abc-123"
    assert jobs[0].company == "Acme Games"
    assert jobs[0].title == "Game AI Developer Intern"
    assert jobs[0].remote_status == "remote"
    assert "Unity" in jobs[0].description


def test_job_repository_upserts_by_description_hash(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)
    repo = JobRepository(db_path)
    job = GreenhouseAdapter(company_slug="acme", company_name="Acme AI").parse_jobs(
        {
            "jobs": [
                {
                    "id": 101,
                    "title": "Junior AI Engineer",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
                    "location": {"name": "Remote - India"},
                    "content": "Python, LLM, RAG role",
                }
            ]
        }
    )[0]

    first = repo.upsert_jobs([job])
    second = repo.upsert_jobs([job])

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("select count(*) from jobs").fetchone()[0]
        status = conn.execute("select status from jobs").fetchone()[0]

    assert first.inserted == 1
    assert first.updated == 0
    assert second.inserted == 0
    assert second.updated == 1
    assert count == 1
    assert status == "Discovered"


def test_normalize_job_text_removes_html_and_extra_whitespace():
    assert normalize_job_text("<p>Python&nbsp; role</p>\n\n<b>Remote</b>") == "Python role Remote"
