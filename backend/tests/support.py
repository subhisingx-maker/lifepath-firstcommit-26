"""Shared helpers for tests that use the real sample PDFs and a fake AI provider."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTICES = ROOT / "sample_notices"
FIXTURES = Path(__file__).parent / "fixtures"
DEMO = NOTICES / "01_demo_national_university_bsc_2027-28.pdf"
MERIDIAN = NOTICES / "02_meridian_state_technical_university_btech_2027-28.pdf"
CORRIGENDUM = NOTICES / "02b_meridian_state_technical_university_corrigendum_1.pdf"


def item(category, name, quote, page, **extra):
    return {"category": category, "name": name, "explanation": f"AI reading of: {name}",
            "supporting_quote": quote, "source_page": page, **extra}


MERIDIAN_REPLY = {
    "institution": {"value": "Meridian State Technical University", "source_page": 1,
                    "supporting_quote": "Meridian State Technical University (MSTU)"},
    "programme": None, "academic_year": None,
    "items": [
        item("deadline", "Registration closes", "Application forms received after 5th June 2027 will not be accepted.",
             3, event_key="registration_close", date="2030-01-01"),   # a made-up "date" field must be ignored
        item("document", "Income certificate",
             "Income certificate is required only for candidates applying for the Fee Waiver Scheme.", 2,
             requirement_level="conditional", condition="Applying for the Fee Waiver Scheme"),
        item("eligibility", "Age limit", "The candidate must not be older than 24 years as on 1 October 2027.", 1),
    ],
    "not_found": ["appeal process after Round 3"],
}
CORRIGENDUM_REPLY = {
    "items": [
        item("deadline", "Registration closes", "The last date of registration is extended to 12th June 2027.", 1,
             event_key="registration_close"),
        item("document", "Income certificate", "Income certificate is no longer required for the Fee Waiver Scheme.",
             1, requirement_level="not_required"),
    ],
    "not_found": [],
}


class FakeProvider:
    """Stands in for Gemini. ``respond`` gets the user prompt and returns text (or raises)."""
    name = "fake"
    model = "fake-model"

    def __init__(self, respond):
        self.respond = respond
        self.calls = []

    def generate_json(self, system, user):
        self.calls.append((system, user))
        return self.respond(user)


def notice_provider():
    def respond(user):
        if "Corrigendum" in user:
            return json.dumps(CORRIGENDUM_REPLY)
        return json.dumps(MERIDIAN_REPLY)
    return FakeProvider(respond)
