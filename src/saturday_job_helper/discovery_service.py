from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import httpx

from saturday_job_helper.discovery import DiscoveredJob, GreenhouseAdapter, LeverAdapter
from saturday_job_helper.repository import JobRepository, UpsertResult


@dataclass(frozen=True)
class DiscoveryTarget:
    source: str
    company_slug: str
    company_name: str


@dataclass(frozen=True)
class DiscoveryResult:
    fetched: int
    inserted: int
    updated: int
    skipped: int = 0
    failed: int = 0
    errors: list[str] | None = None


FetchJson = Callable[[str], Any]


def default_fetch_json(url: str) -> Any:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


class JobDiscoveryService:
    def __init__(
        self,
        *,
        repository: JobRepository,
        fetch_json: FetchJson = default_fetch_json,
        enable_greenhouse: bool = True,
        enable_lever: bool = True,
    ) -> None:
        self.repository = repository
        self.fetch_json = fetch_json
        self.enable_greenhouse = enable_greenhouse
        self.enable_lever = enable_lever

    def discover(self, targets: list[DiscoveryTarget]) -> DiscoveryResult:
        discovered: list[DiscoveredJob] = []
        fetched = 0
        skipped = 0
        failed = 0
        errors: list[str] = []
        for target in targets:
            adapter = self._adapter_for_target(target)
            if adapter is None:
                skipped += 1
                continue
            try:
                payload = self.fetch_json(adapter.api_url)
                discovered.extend(adapter.parse_jobs(payload))
                fetched += 1
            except Exception as exc:  # noqa: BLE001 - discovery should continue across targets
                failed += 1
                errors.append(f"{target.source}:{target.company_slug}: {exc}")
                continue

        upsert = self.repository.upsert_jobs(discovered) if discovered else UpsertResult()
        return DiscoveryResult(
            fetched=fetched,
            inserted=upsert.inserted,
            updated=upsert.updated,
            skipped=skipped,
            failed=failed,
            errors=errors,
        )

    def _adapter_for_target(self, target: DiscoveryTarget) -> GreenhouseAdapter | LeverAdapter | None:
        source = target.source.lower().strip()
        if source == "greenhouse" and self.enable_greenhouse:
            return GreenhouseAdapter(
                company_slug=target.company_slug,
                company_name=target.company_name,
            )
        if source == "lever" and self.enable_lever:
            return LeverAdapter(
                company_slug=target.company_slug,
                company_name=target.company_name,
            )
        return None
