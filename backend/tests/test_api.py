"""API tests. Skipped (not passed) unless FastAPI, httpx and PyMuPDF are installed."""
import os
import unittest
from importlib.util import find_spec
from pathlib import Path

HAVE = all(find_spec(m) for m in ("fastapi", "httpx", "pymupdf", "multipart"))
NOTICE = Path(__file__).resolve().parents[2] / "sample_notices" / "01_demo_national_university_bsc_2027-28.pdf"


@unittest.skipUnless(HAVE, "fastapi / httpx / pymupdf / python-multipart not installed")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["GEMINI_API_KEY"] = ""       # force demo mode, whatever is in .env
        from fastapi.testclient import TestClient
        from app.main import app
        cls.client = TestClient(app)

    def test_health_reports_demo_mode_without_key(self):
        body = self.client.get("/api/health").json()
        self.assertEqual((body["ai_mode"], body["ai_configured"], body["ocr"]),
                         ("demo", False, "not_implemented"))
        self.assertNotIn("key", " ".join(body.keys()).replace("ai_configured", ""))

    def test_demo_journey_is_labelled_fictional(self):
        j = self.client.get("/api/demo/journey").json()
        self.assertTrue(j["fictional"])
        self.assertIn("NOT AN OFFICIAL", j["banner"])

    def test_upload_sample_pdf(self):
        r = self.client.post("/api/documents/extract",
                             files={"file": (NOTICE.name, NOTICE.read_bytes(), "application/pdf")})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual((body["status"], body["page_count"], body["ai"]["mode"]), ("ok", 4, "demo"))
        self.assertTrue(any(d["iso"] == "2027-04-01" and d["page"] == 4 for d in body["dates"]))

    def test_rejects_non_pdf_and_fake_pdf(self):
        r = self.client.post("/api/documents/extract", files={"file": ("a.png", b"x", "image/png")})
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (415, "unsupported_type"))
        r = self.client.post("/api/documents/extract", files={"file": ("a.pdf", b"hello", "application/pdf")})
        self.assertEqual(r.status_code, 415)

    def test_corrupt_pdf_gives_422(self):
        data = b"%PDF-1.7\n" + bytes(range(256)) * 20
        r = self.client.post("/api/documents/extract", files={"file": ("bad.pdf", data, "application/pdf")})
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (422, "corrupt"))


if __name__ == "__main__":
    unittest.main()
