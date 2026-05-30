from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    external_id TEXT,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    remote_status TEXT,
    application_url TEXT NOT NULL,
    description TEXT NOT NULL,
    description_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'Discovered',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_scores (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    confidence_score INTEGER NOT NULL,
    explanation TEXT NOT NULL,
    rejection_reason TEXT,
    scoring_model TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    source_path TEXT,
    generated_docx_path TEXT,
    generated_pdf_path TEXT,
    diff_text TEXT,
    provider TEXT,
    model TEXT,
    telegram_diff_sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS approval_events (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    source TEXT NOT NULL,
    approved_by TEXT,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS application_attempts (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    attempt_type TEXT NOT NULL,
    status TEXT NOT NULL,
    confirmation_url TEXT,
    error_message TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);
"""


def init_db(db_path: Path | str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
