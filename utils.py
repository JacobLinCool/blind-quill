from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime


SEED_MAX_CHARS = 500
FRAGMENT_MAX_CHARS = 500
STORY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{6,32}$")

_DISALLOWED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsexual\s+content\s+involving\s+minors\b",
        r"\bminor\s+sexual\b",
        r"\bchild\s+sexual\b",
        r"\bhow\s+to\s+make\s+(a\s+)?bomb\b",
        r"\binstructions?\s+to\s+(kill|poison|stab|shoot)\b",
        r"\bprivate\s+(ssn|social\s+security|passport|credit\s+card)\b",
    )
]


class InputValidationError(ValueError):
    pass


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_story_id() -> str:
    return secrets.token_urlsafe(6)


def new_graft_id() -> str:
    return secrets.token_urlsafe(8)


def validate_story_id(story_id: str | None) -> str:
    if not isinstance(story_id, str):
        raise InputValidationError("Story ID is required.")
    value = story_id.strip()
    if not STORY_ID_PATTERN.fullmatch(value):
        raise InputValidationError("Story ID format is invalid.")
    return value


def validate_seed(seed: str) -> str:
    return _validate_text(seed, SEED_MAX_CHARS, "Seed")


def validate_fragment(fragment: str) -> str:
    return _validate_text(fragment, FRAGMENT_MAX_CHARS, "Fragment")


def _validate_text(value: str, max_chars: int, label: str) -> str:
    if not isinstance(value, str):
        raise InputValidationError(f"{label} is required.")
    text = value.strip()
    if not text:
        raise InputValidationError(f"{label} cannot be empty.")
    if len(text) > max_chars:
        raise InputValidationError(f"{label} must be {max_chars} characters or fewer.")
    for pattern in _DISALLOWED_PATTERNS:
        if pattern.search(text):
            raise InputValidationError(
                "This app keeps contributions PG-13. Please revise the text and try again."
            )
    return text


def require_open_for_graft(status: str, graft_count: int, max_grafts: int) -> None:
    if status != "open" or graft_count >= max_grafts:
        raise InputValidationError("This manuscript is sealed and cannot accept new grafts.")
