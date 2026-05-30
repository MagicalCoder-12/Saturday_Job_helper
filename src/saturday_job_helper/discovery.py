from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiscoveredJob:
    source: str
    external_id: str
    company: str
    title: str
    location: str
    remote_status: str
    application_url: str
    description: str
    description_hash: str


def normalize_job_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def infer_remote_status(location: str, description: str = "") -> str:
    haystack = f"{location} {description}".lower()
    if "remote" in haystack or "work from home" in haystack or "wfh" in haystack:
        return "remote"
    if "hybrid" in haystack:
        return "hybrid"
    return "onsite"


def make_description_hash(source: str, company: str, title: str, application_url: str, description: str) -> str:
    normalized = "|".join(
        [
            source.lower().strip(),
            company.lower().strip(),
            title.lower().strip(),
            application_url.lower().strip(),
            normalize_job_text(description).lower(),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class GreenhouseAdapter:
    source = "greenhouse"

    def __init__(self, *, company_slug: str, company_name: str | None = None) -> None:
        self.company_slug = company_slug
        self.company_name = company_name or company_slug

    @property
    def api_url(self) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{self.company_slug}/jobs?content=true"

    def parse_jobs(self, payload: dict[str, Any]) -> list[DiscoveredJob]:
        jobs: list[DiscoveredJob] = []
        for item in payload.get("jobs", []):
            title = normalize_job_text(str(item.get("title") or ""))
            url = str(item.get("absolute_url") or "")
            location_value = item.get("location") or {}
            if isinstance(location_value, dict):
                location = normalize_job_text(str(location_value.get("name") or ""))
            else:
                location = normalize_job_text(str(location_value))
            description = normalize_job_text(str(item.get("content") or item.get("metadata") or ""))
            external_id = str(item.get("id") or url)
            jobs.append(
                DiscoveredJob(
                    source=self.source,
                    external_id=external_id,
                    company=self.company_name,
                    title=title,
                    location=location,
                    remote_status=infer_remote_status(location, description),
                    application_url=url,
                    description=description,
                    description_hash=make_description_hash(
                        self.source, self.company_name, title, url, description
                    ),
                )
            )
        return jobs


class LeverAdapter:
    source = "lever"

    def __init__(self, *, company_slug: str, company_name: str | None = None) -> None:
        self.company_slug = company_slug
        self.company_name = company_name or company_slug

    @property
    def api_url(self) -> str:
        return f"https://api.lever.co/v0/postings/{self.company_slug}?mode=json"

    def parse_jobs(self, payload: list[dict[str, Any]]) -> list[DiscoveredJob]:
        jobs: list[DiscoveredJob] = []
        for item in payload:
            title = normalize_job_text(str(item.get("text") or item.get("title") or ""))
            url = str(item.get("hostedUrl") or item.get("applyUrl") or "")
            categories = item.get("categories") or {}
            location = normalize_job_text(str(categories.get("location") or ""))
            description = normalize_job_text(
                str(item.get("descriptionPlain") or item.get("description") or "")
            )
            external_id = str(item.get("id") or url)
            jobs.append(
                DiscoveredJob(
                    source=self.source,
                    external_id=external_id,
                    company=self.company_name,
                    title=title,
                    location=location,
                    remote_status=infer_remote_status(location, description),
                    application_url=url,
                    description=description,
                    description_hash=make_description_hash(
                        self.source, self.company_name, title, url, description
                    ),
                )
            )
        return jobs
