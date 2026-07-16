from __future__ import annotations

from typing import Any


SESSION_ACTIVE = "Active"
SESSION_SUBMITTED = "Submitted"
SESSION_ENDED = "Ended"
SESSION_REVIEWED = "Reviewed"
SESSION_LEGACY_COMPLETED = "Completed"

SESSION_TERMINAL_STATUSES = frozenset(
    {
        SESSION_SUBMITTED,
        SESSION_ENDED,
        SESSION_REVIEWED,
        SESSION_LEGACY_COMPLETED,
    }
)

_CANONICAL_STATUSES = {
    status.casefold(): status
    for status in {SESSION_ACTIVE, *SESSION_TERMINAL_STATUSES}
}


def normalize_session_status(value: Any) -> str:
    status = str(value or "").strip()
    return _CANONICAL_STATUSES.get(status.casefold(), status)


def is_active_session(value: Any) -> bool:
    return normalize_session_status(value) == SESSION_ACTIVE


def is_terminal_session(value: Any) -> bool:
    return normalize_session_status(value) in SESSION_TERMINAL_STATUSES


def is_reviewable_session(value: Any) -> bool:
    return is_terminal_session(value)
