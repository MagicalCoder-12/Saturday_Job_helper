from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from saturday_job_helper.discovery import DiscoveredJob
from saturday_job_helper.models import JobStatus

if TYPE_CHECKING:
    from saturday_job_helper.scoring import ScoreResult


@dataclass(frozen=True)
class UpsertResult:
    inserted: int = 0
    updated: int = 0


@dataclass(frozen=True)
class StoredJob:
    id: int
    source: str
    external_id: str
    company: str
    title: str
    location: str
    remote_status: str
    application_url: str
    description: str
    description_hash: str
    status: str


@dataclass(frozen=True)
class StoredScore:
    id: int
    job_id: int
    score: int
    confidence_score: int
    explanation: str
    rejection_reason: str | None
    scoring_model: str


@dataclass(frozen=True)
class AlertCandidate:
    job: StoredJob
    score: StoredScore


class JobRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def upsert_jobs(self, jobs: list[DiscoveredJob]) -> UpsertResult:
        inserted = 0
        updated = 0
        with sqlite3.connect(self.db_path) as conn:
            for job in jobs:
                existing = conn.execute(
                    "select id from jobs where description_hash = ?",
                    (job.description_hash,),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        update jobs
                        set external_id = ?, source = ?, title = ?, company = ?, location = ?,
                            remote_status = ?, application_url = ?, description = ?,
                            updated_at = CURRENT_TIMESTAMP
                        where description_hash = ?
                        """,
                        (
                            job.external_id,
                            job.source,
                            job.title,
                            job.company,
                            job.location,
                            job.remote_status,
                            job.application_url,
                            job.description,
                            job.description_hash,
                        ),
                    )
                    updated += 1
                else:
                    conn.execute(
                        """
                        insert into jobs (
                            external_id, source, title, company, location, remote_status,
                            application_url, description, description_hash, status
                        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job.external_id,
                            job.source,
                            job.title,
                            job.company,
                            job.location,
                            job.remote_status,
                            job.application_url,
                            job.description,
                            job.description_hash,
                            JobStatus.DISCOVERED.value,
                        ),
                    )
                    inserted += 1
            conn.commit()
        return UpsertResult(inserted=inserted, updated=updated)

    def get_unscored_jobs(self, *, limit: int) -> list[StoredJob]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                select j.*
                from jobs j
                left join match_scores m on m.job_id = j.id
                where m.id is null
                order by j.id
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [self._stored_job_from_row(row) for row in rows]

    def save_match_score(
        self,
        *,
        job_id: int,
        result: "ScoreResult",
        scoring_model: str,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into match_scores (
                    job_id, score, confidence_score, explanation,
                    rejection_reason, scoring_model
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    result.match_score,
                    result.confidence_score,
                    result.explanation,
                    result.rejection_reason,
                    scoring_model,
                ),
            )
            conn.execute(
                "update jobs set status = ?, updated_at = CURRENT_TIMESTAMP where id = ?",
                (JobStatus.SCORED.value, job_id),
            )
            conn.commit()

    def get_alert_candidates(
        self,
        *,
        min_score: int,
        min_confidence: int,
        limit: int,
    ) -> list[AlertCandidate]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                select
                    j.id as job_id,
                    j.source,
                    j.external_id,
                    j.company,
                    j.title,
                    j.location,
                    j.remote_status,
                    j.application_url,
                    j.description,
                    j.description_hash,
                    j.status,
                    m.id as score_id,
                    m.score,
                    m.confidence_score,
                    m.explanation,
                    m.rejection_reason,
                    m.scoring_model
                from jobs j
                join match_scores m on m.job_id = j.id
                where j.status = ?
                  and m.score >= ?
                  and m.confidence_score >= ?
                order by m.score desc, m.confidence_score desc, j.id asc
                limit ?
                """,
                (JobStatus.SCORED.value, min_score, min_confidence, limit),
            ).fetchall()
        return [self._alert_candidate_from_row(row) for row in rows]

    def mark_job_alerted(self, job_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "update jobs set status = ?, updated_at = CURRENT_TIMESTAMP where id = ?",
                (JobStatus.ALERTED.value, job_id),
            )
            conn.commit()

    def count_jobs(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return int(conn.execute("select count(*) from jobs").fetchone()[0])

    @staticmethod
    def _stored_job_from_row(row: sqlite3.Row) -> StoredJob:
        return StoredJob(
            id=int(row["id"]),
            source=str(row["source"]),
            external_id=str(row["external_id"] or ""),
            company=str(row["company"]),
            title=str(row["title"]),
            location=str(row["location"] or ""),
            remote_status=str(row["remote_status"] or ""),
            application_url=str(row["application_url"]),
            description=str(row["description"]),
            description_hash=str(row["description_hash"]),
            status=str(row["status"]),
        )

    @staticmethod
    def _alert_candidate_from_row(row: sqlite3.Row) -> AlertCandidate:
        job = StoredJob(
            id=int(row["job_id"]),
            source=str(row["source"]),
            external_id=str(row["external_id"] or ""),
            company=str(row["company"]),
            title=str(row["title"]),
            location=str(row["location"] or ""),
            remote_status=str(row["remote_status"] or ""),
            application_url=str(row["application_url"]),
            description=str(row["description"]),
            description_hash=str(row["description_hash"]),
            status=str(row["status"]),
        )
        score = StoredScore(
            id=int(row["score_id"]),
            job_id=int(row["job_id"]),
            score=int(row["score"]),
            confidence_score=int(row["confidence_score"]),
            explanation=str(row["explanation"]),
            rejection_reason=row["rejection_reason"],
            scoring_model=str(row["scoring_model"] or ""),
        )
        return AlertCandidate(job=job, score=score)
