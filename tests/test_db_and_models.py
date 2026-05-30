import sqlite3
from pathlib import Path

from saturday_job_helper.db import init_db
from saturday_job_helper.models import JobStatus


def test_init_db_creates_approval_gated_schema(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"

    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
            )
        }
        jobs_columns = {row[1] for row in conn.execute("pragma table_info(jobs)")}
        approvals_columns = {row[1] for row in conn.execute("pragma table_info(approval_events)")}

    assert {"jobs", "match_scores", "documents", "approval_events", "application_attempts"} <= tables
    assert {"status", "application_url", "description_hash"} <= jobs_columns
    assert {"job_id", "action", "source", "created_at"} <= approvals_columns


def test_job_status_requires_approved_before_application_ready():
    assert JobStatus.APPROVED.allows_application is True
    assert JobStatus.DISCOVERED.allows_application is False
    assert JobStatus.REJECTED.allows_application is False
