from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from saturday_job_helper.repository import JobRepository, StoredJob


@dataclass(frozen=True)
class ScoreResult:
    match_score: int
    confidence_score: int
    explanation: str
    rejection_reason: str | None
    recommended_action: str


@dataclass(frozen=True)
class ScoringSummary:
    scored: int
    failed: int
    errors: list[str]


ScoreWithLLM = Callable[[str], tuple[str, str]]


def build_scoring_prompt(*, candidate_profile: str, job: StoredJob) -> str:
    return f"""
You are scoring whether this job fits Ajith's candidate profile.
Return strict JSON only with these keys:
- match_score: integer 0-100
- confidence_score: integer 0-100
- explanation: short practical explanation
- rejection_reason: null or short reason
- recommended_action: one of alert, reject, manual_review

Scoring guidance:
- Prefer AI/ML, data science, Python, RAG, LLM, game AI, Unity/Godot/Pygame, backend API roles.
- Prefer remote, Hyderabad, India, internships, junior roles, entry-level roles.
- Penalize senior-only roles, unrelated sales-only roles, impossible location constraints.

Candidate profile:
{candidate_profile[:6000]}

Job:
Title: {job.title}
Company: {job.company}
Location: {job.location}
Remote status: {job.remote_status}
Source: {job.source}
URL: {job.application_url}
Description:
{job.description[:6000]}
""".strip()


def _extract_json_object(text: str) -> str:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object")
    return cleaned[start : end + 1]


def _clamp_score(value: object) -> int:
    try:
        score = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def parse_score_response(text: str) -> ScoreResult:
    payload = json.loads(_extract_json_object(text))
    action = str(payload.get("recommended_action") or "manual_review").strip().lower()
    if action not in {"alert", "reject", "manual_review"}:
        action = "manual_review"
    rejection_reason = payload.get("rejection_reason")
    if rejection_reason == "":
        rejection_reason = None
    return ScoreResult(
        match_score=_clamp_score(payload.get("match_score")),
        confidence_score=_clamp_score(payload.get("confidence_score")),
        explanation=str(payload.get("explanation") or "No explanation provided").strip(),
        rejection_reason=rejection_reason,
        recommended_action=action,
    )


class JobScoringService:
    def __init__(
        self,
        *,
        repository: JobRepository,
        candidate_profile: str,
        score_with_llm: ScoreWithLLM,
    ) -> None:
        self.repository = repository
        self.candidate_profile = candidate_profile
        self.score_with_llm = score_with_llm

    def score_unscored_jobs(self, *, limit: int) -> ScoringSummary:
        scored = 0
        failed = 0
        errors: list[str] = []
        for job in self.repository.get_unscored_jobs(limit=limit):
            prompt = build_scoring_prompt(candidate_profile=self.candidate_profile, job=job)
            try:
                response_text, scoring_model = self.score_with_llm(prompt)
                score = parse_score_response(response_text)
                self.repository.save_match_score(
                    job_id=job.id,
                    result=score,
                    scoring_model=scoring_model,
                )
                scored += 1
            except Exception as exc:  # noqa: BLE001 - continue scoring remaining jobs
                failed += 1
                errors.append(f"job_id={job.id}: {exc}")
        return ScoringSummary(scored=scored, failed=failed, errors=errors)
