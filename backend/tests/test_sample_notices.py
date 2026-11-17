"""Tests that need PyMuPDF. Skipped (not passed) when it is not installed."""
import json
import re
import unittest
from importlib.util import find_spec
from pathlib import Path

HAVE_FITZ = find_spec("pymupdf") is not None
ROOT = Path(__file__).resolve().parents[2]
NOTICES = ROOT / "sample_notices"
FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_PAGES = {
    "01_demo_national_university_bsc_2027-28.pdf": 4,
    "02_meridian_state_technical_university_btech_2027-28.pdf": 6,
    "02b_meridian_state_technical_university_corrigendum_1.pdf": 1,
    "03_riverbend_central_college_ba_bcom_2027-28.pdf": 5,
}
norm = lambda s: re.sub(r"\s+", " ", s).strip()


def extract(path: Path):
    from app.services.pdf_extractor import extract_pdf
    return extract_pdf(path.read_bytes(), path.name, 300)


@unittest.skipUnless(HAVE_FITZ, "PyMuPDF (pymupdf) is not installed")
class SampleNoticeTests(unittest.TestCase):
    def test_every_sample_is_readable_with_preserved_page_numbers(self):
        for name, pages in EXPECTED_PAGES.items():
            with self.subTest(name):
                r = extract(NOTICES / name)
                self.assertEqual(r.analysis.status, "ok")
                self.assertEqual([p.number for p in r.pages], list(range(1, pages + 1)))

    def test_demo_journey_quotes_are_on_the_pages_they_cite(self):
        j = json.loads((ROOT / "backend/app/data/demo_journey.json").read_text(encoding="utf-8"))
        r = extract(NOTICES / j["sources"][0]["name"])
        texts = [norm(p.text) for p in r.pages]
        for key in ("eligibility", "documents", "warnings", "not_specified", "steps"):
            for item in j[key]:
                with self.subTest(item.get("id") or item["text"][:40]):
                    self.assertIn(norm(item["source_quote"]), texts[item["source_page"] - 1])

    def test_meridian_dates_found_with_pages_and_flags(self):
        from app.services.deadline_parser import find_dates_in_pages
        r = extract(NOTICES / "02_meridian_state_technical_university_btech_2027-28.pdf")
        dates = find_dates_in_pages([p.text for p in r.pages])
        by_raw = {(d.raw, d.page): d for d in dates}
        self.assertEqual(by_raw[("5th June 2027", 3)].iso, "2027-06-05")
        self.assertEqual(by_raw[("07/06/2027", 3)].status, "needs_review")
        self.assertTrue(any(d.raw == "9 June" and d.date is None for d in dates))

    def test_corrigendum_contains_the_conflicting_deadline(self):
        from app.services.deadline_parser import find_dates_in_pages
        r = extract(NOTICES / "02b_meridian_state_technical_university_corrigendum_1.pdf")
        isos = {d.iso for d in find_dates_in_pages([p.text for p in r.pages])}
        self.assertIn("2027-06-12", isos)

    def test_scanned_fixture_is_detected(self):
        r = extract(FIXTURES / "scanned_notice.pdf")
        self.assertEqual(r.analysis.status, "needs_ocr")
        self.assertEqual(r.analysis.scanned_pages, [1])

    def test_corrupted_fixture_raises_clear_error(self):
        from app.services.pdf_extractor import ExtractionError
        with self.assertRaises(ExtractionError) as ctx:
            extract(FIXTURES / "corrupted.pdf")
        self.assertEqual(ctx.exception.code, "corrupt")

    def test_page_limit_enforced(self):
        from app.services.pdf_extractor import ExtractionError, extract_pdf
        path = NOTICES / "02_meridian_state_technical_university_btech_2027-28.pdf"
        with self.assertRaises(ExtractionError) as ctx:
            extract_pdf(path.read_bytes(), path.name, 3)
        self.assertEqual(ctx.exception.code, "too_many_pages")


if __name__ == "__main__":
    unittest.main()
