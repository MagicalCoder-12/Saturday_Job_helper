from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import httpx

from saturday_job_helper.repository import JobRepository


@dataclass(frozen=True)
class AlertPolicy:
    min_score: int = 70
    min_confidence: int = 50
    max_alerts: int = 20


@dataclass(frozen=True)
class AlertSummary:
    eligible: int
    sent: int
    failed: int
    dry_run: bool
    errors: list[str]


SendAlert = Callable[[str], None]
PostJson = Callable[[str, dict[str, str]], None]


def build_alert_message(
    *,
    job_title: str,
    company: str,
    location: str,
    score: int,
    confidence_score: int,
    explanation: str,
    application_url: str,
) -> str:
    return "\n".join(
        [
            "🚦 Saturday Job Match Alert",
            "",
            f"Role: {job_title}",
            f"Company: {company}",
            f"Location: {location or 'Not specified'}",
            f"Score: {score}/100",
            f"Confidence: {confidence_score}/100",
            "",
            f"Why: {explanation}",
            "",
            f"Apply URL: {application_url}",
            "",
            "Reply APPROVE <job_id> to generate tailored documents later, or REJECT <job_id> to skip.",
        ]
    )


class TelegramNotifier:
    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        post_json: PostJson | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds
        self.post_json = post_json or self._post_json

    def send(self, message: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.post_json(
            url,
            {
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": "false",
            },
        )

    def _post_json(self, url: str, payload: dict[str, str]) -> None:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()


class JobAlertService:
    def __init__(
        self,
        *,
        repository: JobRepository,
        policy: AlertPolicy,
        send_alert: SendAlert,
    ) -> None:
        self.repository = repository
        self.policy = policy
        self.send_alert = send_alert

    def send_pending_alerts(self, *, dry_run: bool) -> AlertSummary:
        candidates = self.repository.get_alert_candidates(
            min_score=self.policy.min_score,
            min_confidence=self.policy.min_confidence,
            limit=self.policy.max_alerts,
        )
        sent = 0
        failed = 0
        errors: list[str] = []
        for candidate in candidates:
            message = build_alert_message(
                job_title=candidate.job.title,
                company=candidate.job.company,
                location=candidate.job.location,
                score=candidate.score.score,
                confidence_score=candidate.score.confidence_score,
                explanation=candidate.score.explanation,
                application_url=candidate.job.application_url,
            )
            if dry_run:
                continue
            try:
                self.send_alert(message)
                self.repository.mark_job_alerted(candidate.job.id)
                sent += 1
            except Exception as exc:  # noqa: BLE001 - continue alerting remaining candidates
                failed += 1
                errors.append(f"job_id={candidate.job.id}: {exc}")
        return AlertSummary(
            eligible=len(candidates),
            sent=sent,
            failed=failed,
            dry_run=dry_run,
            errors=errors,
        )
