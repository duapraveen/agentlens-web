"""Tests for the redaction boundary (synthetic examples only)."""

from agentlens.privacy.redact import redact


def test_redacts_ssn() -> None:
    assert redact("SSN is 123-45-6789 ok") == "SSN is [REDACTED:SSN] ok"


def test_redacts_phone() -> None:
    assert redact("call me at (555) 123-4567") == "call me at [REDACTED:PHONE]"
    assert redact("call 555-123-4567 now") == "call [REDACTED:PHONE] now"


def test_redacts_email() -> None:
    assert redact("mail pat.doe@example.com please") == "mail [REDACTED:EMAIL] please"


def test_redacts_date_of_birth_style_dates() -> None:
    assert redact("DOB 03/14/1985 noted") == "DOB [REDACTED:DATE] noted"
    assert redact("born 1985-03-14") == "born [REDACTED:DATE]"


def test_redacts_mrn() -> None:
    assert redact("MRN 84921 on file") == "[REDACTED:MRN] on file"
    assert redact("mrn: 84921") == "[REDACTED:MRN]"


def test_plain_text_passes_through() -> None:
    text = "I would like to book an appointment for next Tuesday."
    assert redact(text) == text
