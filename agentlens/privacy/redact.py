"""Redaction boundary for transcript text bound to external APIs.

All data in this repo is synthetic, but the architecture must be
HIPAA-plausible (constitution V.2): every code path that sends transcript
text to an external API calls redact() first. Pattern order matters —
more specific patterns (SSN, MRN) run before generic ones (phone, date).
"""

import re

_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED:SSN]", "SSN"),
    (re.compile(r"\bmrn\s*:?\s*\d+\b", re.IGNORECASE), "[REDACTED:MRN]", "MRN"),
    (re.compile(r"\(\d{3}\)\s*\d{3}-\d{4}"), "[REDACTED:PHONE]", "PHONE"),
    (re.compile(r"\b\d{3}-\d{3}-\d{4}\b"), "[REDACTED:PHONE]", "PHONE"),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED:EMAIL]",
        "EMAIL",
    ),
    (re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"), "[REDACTED:DATE]", "DATE"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[REDACTED:DATE]", "DATE"),
]


def redact(text: str) -> str:
    """Replace PHI-shaped substrings (SSN, MRN, phone, email, dates) with placeholders."""
    for pattern, replacement, _ in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def phi_matches(text: str) -> list[str]:
    """Type names of PHI-shaped patterns present in text (e.g. ["SSN", "DATE"]), deduplicated."""
    found: list[str] = []
    for pattern, _, type_name in _PATTERNS:
        if type_name not in found and pattern.search(text):
            found.append(type_name)
    return found
