from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    DISCOVERED = "Discovered"
    SCORED = "Scored"
    ALERTED = "Alerted"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    MANUAL_FALLBACK = "ManualFallback"
    APPLIED = "Applied"
    FAILED = "Failed"

    @property
    def allows_application(self) -> bool:
        return self is JobStatus.APPROVED
