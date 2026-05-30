from pathlib import Path

from saturday_job_helper.db import init_db
from saturday_job_helper.discovery_service import DiscoveryTarget, JobDiscoveryService
from saturday_job_helper.repository import JobRepository


def test_discovery_service_fetches_enabled_targets_and_stores_jobs(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)
    seen_urls = []

    def fetch_json(url: str):
        seen_urls.append(url)
        if "greenhouse" in url:
            return {
                "jobs": [
                    {
                        "id": 1,
                        "title": "AI Intern",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                        "location": {"name": "Remote"},
                        "content": "Python intern role",
                    }
                ]
            }
        return [
            {
                "id": "lever-1",
                "text": "ML Intern",
                "hostedUrl": "https://jobs.lever.co/beta/lever-1",
                "categories": {"location": "Hyderabad"},
                "descriptionPlain": "ML role",
            }
        ]

    service = JobDiscoveryService(repository=JobRepository(db_path), fetch_json=fetch_json)
    result = service.discover(
        [
            DiscoveryTarget(source="greenhouse", company_slug="acme", company_name="Acme AI"),
            DiscoveryTarget(source="lever", company_slug="beta", company_name="Beta ML"),
        ]
    )

    assert result.fetched == 2
    assert result.inserted == 2
    assert result.updated == 0
    assert len(seen_urls) == 2
    assert JobRepository(db_path).count_jobs() == 2


def test_discovery_service_skips_disabled_sources(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)

    service = JobDiscoveryService(
        repository=JobRepository(db_path),
        fetch_json=lambda _: {"jobs": []},
        enable_greenhouse=False,
        enable_lever=True,
    )
    result = service.discover(
        [DiscoveryTarget(source="greenhouse", company_slug="acme", company_name="Acme AI")]
    )

    assert result.fetched == 0
    assert result.inserted == 0
    assert result.failed == 0
    assert JobRepository(db_path).count_jobs() == 0


def test_discovery_service_records_failed_targets_without_crashing(tmp_path: Path):
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)

    def fetch_json(_: str):
        raise RuntimeError("404 board not found")

    service = JobDiscoveryService(repository=JobRepository(db_path), fetch_json=fetch_json)
    result = service.discover(
        [DiscoveryTarget(source="greenhouse", company_slug="missing", company_name="Missing Co")]
    )

    assert result.fetched == 0
    assert result.failed == 1
    assert "greenhouse:missing" in result.errors[0]
    assert JobRepository(db_path).count_jobs() == 0
