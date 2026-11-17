"""API + database tests with a fake AI. Skipped (not passed) unless every dependency is installed."""
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

HAVE = all(find_spec(m) for m in ("fastapi", "httpx", "pymupdf", "multipart", "sqlalchemy", "pydantic"))

if HAVE:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from app.api import analyses as analyses_api
    from app.core.config import Settings, get_settings
    from app.db.session import get_db, init_db, make_engine
    from app.main import app
    from app.services.ai_service import AIProviderError
    from tests.support import (CORRIGENDUM, DEMO, FIXTURES, MERIDIAN, FakeProvider, notice_provider)


def upload(path, name=None):
    return {"file": (name or path.name, path.read_bytes(), "application/pdf")}


@unittest.skipUnless(HAVE, "fastapi / httpx / pymupdf / sqlalchemy / pydantic not installed")
class AnalysisApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = make_engine(f"sqlite:///{Path(self.tmp.name, 't.db').as_posix()}")
        init_db(self.engine)
        factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        def db():
            s = factory()
            try:
                yield s
            finally:
                s.close()
        self.provider = notice_provider()
        app.dependency_overrides[get_db] = db
        app.dependency_overrides[get_settings] = lambda: Settings(ai_rate_limit_per_minute=100)
        app.dependency_overrides[analyses_api.get_ai_provider] = lambda: self.provider
        analyses_api.reset_limiter()
        self.client = TestClient(app, headers={"X-Workspace-Token": "a" * 64})

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.tmp.cleanup()

    def demo_mode(self):
        app.dependency_overrides[analyses_api.get_ai_provider] = lambda: None

    def test_analyses_are_private_to_workspace(self):
        self.demo_mode()
        created = self.client.post("/api/analyses", files=upload(DEMO))
        self.assertEqual(created.status_code, 201)
        analysis_id = created.json()["id"]
        other = {"X-Workspace-Token": "b" * 64}
        self.assertEqual(self.client.get("/api/analyses", headers=other).json(), [])
        for method, path in [("get", f"/api/analyses/{analysis_id}"),
                             ("delete", f"/api/analyses/{analysis_id}"),
                             ("post", f"/api/analyses/{analysis_id}/journey")]:
            self.assertEqual(getattr(self.client, method)(path, headers=other).status_code, 404)
        doc_id = created.json()["documents"][0]["id"]
        self.assertEqual(self.client.get(f"/api/analyses/{analysis_id}/documents/{doc_id}/pages/1", headers=other).status_code, 404)
        self.assertEqual(self.client.patch(f"/api/analyses/{analysis_id}", json={"title": "changed"}, headers=other).status_code, 404)
        self.assertEqual(self.client.post(f"/api/analyses/{analysis_id}/documents", files=upload(DEMO), headers=other).status_code, 404)
        self.assertEqual(self.client.get(f"/api/analyses/{analysis_id}").status_code, 200)

    def test_invalid_workspace_credential_is_rejected(self):
        self.assertEqual(self.client.get("/api/analyses", headers={"X-Workspace-Token": "bad"}).status_code, 401)

    def test_browser_preflight_accepts_workspace_header(self):
        response = self.client.options("/api/analyses", headers={
            "Origin": "https://lifepath-firstcommit-26.netlify.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-workspace-token",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://lifepath-firstcommit-26.netlify.app")

    # ---- creation
    def test_demo_mode_stores_text_and_shows_dates_without_ai(self):
        self.demo_mode()
        r = self.client.post("/api/analyses", files=upload(DEMO))
        self.assertEqual(r.status_code, 201)
        body = r.json()
        doc = body["documents"][0]
        self.assertEqual((doc["ai_status"], doc["page_count"], body["items"]), ("demo", 4, []))
        self.assertTrue(any(d["iso"] == "2027-04-01" and d["page"] == 4 for d in doc["dates"]))

    def test_failed_upload_leaves_no_empty_analysis(self):
        r = self.client.post("/api/analyses", files={"file": ("a.png", b"x", "image/png")})
        self.assertEqual(r.status_code, 415)
        r = self.client.post("/api/analyses", files=upload(FIXTURES / "corrupted.pdf"))
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (422, "corrupt"))
        self.assertEqual(self.client.get("/api/analyses").json(), [])

    def test_ai_failure_leaves_no_empty_analysis_and_maps_status(self):
        def boom(_u):
            raise AIProviderError("rate_limited", "quota", True)
        self.provider.respond = boom
        r = self.client.post("/api/analyses", files=upload(MERIDIAN))
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (429, "rate_limited"))
        self.assertEqual(self.client.get("/api/analyses").json(), [])

    def test_ai_timeout_maps_to_504_and_leaves_no_empty_analysis(self):
        def too_slow(_u):
            raise AIProviderError("timeout", "The AI service did not answer within 5 seconds.", True)
        self.provider.respond = too_slow
        r = self.client.post("/api/analyses", files=upload(MERIDIAN))
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (504, "timeout"))
        self.assertEqual(self.client.get("/api/analyses").json(), [])

    def test_scanned_pdf_skips_ai_and_says_so(self):
        r = self.client.post("/api/analyses", files=upload(FIXTURES / "scanned_notice.pdf"))
        doc = r.json()["documents"][0]
        self.assertEqual((r.status_code, doc["ai_status"], doc["extraction_status"]), (201, "skipped", "needs_ocr"))
        self.assertEqual(self.provider.calls, [])
        self.assertTrue(any("OCR" in w for w in doc["warnings"]))

    # ---- AI extraction + conflicts
    def test_ai_items_carry_source_evidence_and_header(self):
        body = self.client.post("/api/analyses", files=upload(MERIDIAN)).json()
        self.assertEqual(body["institution"], "Meridian State Technical University")
        reg = next(i for i in body["items"] if i["name"] == "Registration closes")
        self.assertEqual((reg["status"], reg["source_page"], reg["date_iso"]), ("verified", 3, "2027-06-05"))
        self.assertIn("5th June 2027", reg["supporting_quote"])
        self.assertTrue(reg["explanation"].startswith("AI reading"))
        self.assertEqual(body["not_found"][0]["topic"], "appeal process after Round 3")

    def test_corrigendum_creates_two_conflicts_showing_both_sources(self):
        first = self.client.post("/api/analyses", files=upload(MERIDIAN)).json()
        body = self.client.post(f"/api/analyses/{first['id']}/documents", files=upload(CORRIGENDUM)).json()
        keys = {c["key"] for c in body["conflicts"]}
        self.assertIn("deadline:registration_close", keys)
        self.assertEqual(body["counts"]["unresolved_conflicts"], 2)
        dl = next(c for c in body["conflicts"] if c["kind"] == "deadline")
        self.assertEqual({(s["document_name"], s["value"]) for s in dl["sides"]},
                         {(MERIDIAN.name, "2027-06-05"), (CORRIGENDUM.name, "2027-06-12")})
        reg = [i for i in body["items"] if i["name"] == "Registration closes"]
        self.assertTrue(all(i["status"] == "conflict" for i in reg))

    def test_resolving_requires_an_explicit_human_choice(self):
        first = self.client.post("/api/analyses", files=upload(MERIDIAN)).json()
        body = self.client.post(f"/api/analyses/{first['id']}/documents", files=upload(CORRIGENDUM)).json()
        c = next(c for c in body["conflicts"] if c["kind"] == "deadline")
        url = f"/api/analyses/{first['id']}/conflicts/resolve"
        self.assertEqual(self.client.post(url, json={"conflict_key": c["key"]}).status_code, 422)
        self.assertEqual(self.client.post(url, json={"conflict_key": c["key"], "chosen_item_id": "nope"}).status_code, 422)
        self.assertEqual(self.client.post(url, json={"conflict_key": "deadline:zzz", "note": "x"}).status_code, 404)
        chosen = c["sides"][1]["item_id"]
        done = self.client.post(url, json={"conflict_key": c["key"], "chosen_item_id": chosen}).json()
        self.assertEqual(done["counts"]["unresolved_conflicts"], 1)
        self.assertTrue(next(x for x in done["conflicts"] if x["key"] == c["key"])["resolved"])

    def test_duplicate_document_is_rejected_and_other_document_is_not(self):
        first = self.client.post("/api/analyses", files=upload(MERIDIAN)).json()
        again = self.client.post(f"/api/analyses/{first['id']}/documents", files=upload(MERIDIAN, "renamed.pdf"))
        self.assertEqual((again.status_code, again.json()["detail"]["code"]), (409, "duplicate_document"))
        other = self.client.post(f"/api/analyses/{first['id']}/documents", files=upload(CORRIGENDUM))
        self.assertEqual(len(other.json()["documents"]), 2)

    def test_analyses_are_independent(self):
        a = self.client.post("/api/analyses", files=upload(MERIDIAN), data={"title": "A"}).json()
        b = self.client.post("/api/analyses", files=upload(CORRIGENDUM), data={"title": "B"}).json()
        item_id = a["items"][0]["id"]
        self.client.patch(f"/api/analyses/{a['id']}/items/{item_id}", json={"review_state": "rejected"})
        self.assertTrue(all(i["review_state"] == "pending" for i in self.client.get(f"/api/analyses/{b['id']}").json()["items"]))
        self.assertEqual(len(self.client.get("/api/analyses").json()), 2)

    # ---- review and edit
    def test_editing_rules(self):
        a = self.client.post("/api/analyses", files=upload(MERIDIAN)).json()
        url = lambda i: f"/api/analyses/{a['id']}/items/{i['id']}"
        deadline = next(i for i in a["items"] if i["category"] == "deadline")
        doc = next(i for i in a["items"] if i["category"] == "document")
        elig = next(i for i in a["items"] if i["category"] == "eligibility")
        ok = self.client.patch(url(deadline), json={"date_iso": "2027-06-06"}).json()
        edited = next(i for i in ok["items"] if i["id"] == deadline["id"])
        self.assertEqual((edited["date_iso"], edited["date_status"], edited["review_state"], edited["user_edited"]),
                         ("2027-06-06", "user_confirmed", "edited", True))
        self.assertEqual(edited["supporting_quote"], deadline["supporting_quote"])    # evidence untouched
        self.assertEqual(self.client.patch(url(deadline), json={"date_iso": "2027-02-31"}).status_code, 422)
        self.assertEqual(self.client.patch(url(elig), json={"requirement_level": "mandatory"}).status_code, 422)
        self.assertEqual(self.client.patch(url(doc), json={"requirement_level": "mandatory"}).status_code, 200)
        self.assertEqual(self.client.patch(url(doc), json={"supporting_quote": "forged"}).status_code, 422)
        self.assertEqual(self.client.patch(url(doc), json={"name": ""}).status_code, 422)
        self.assertEqual(self.client.patch(f"/api/analyses/{a['id']}/items/missing", json={"review_state": "accepted"}).status_code, 404)

    def test_header_can_be_edited(self):
        a = self.client.post("/api/analyses", files=upload(MERIDIAN)).json()
        r = self.client.patch(f"/api/analyses/{a['id']}", json={"programme": "B.Tech CSE", "academic_year": "2027-28"})
        self.assertEqual((r.json()["programme"], r.json()["academic_year"]), ("B.Tech CSE", "2027-28"))

    # ---- pages, deletion, limits
    def test_page_text_and_deletion(self):
        a = self.client.post("/api/analyses", files=upload(MERIDIAN)).json()
        doc_id = a["documents"][0]["id"]
        page = self.client.get(f"/api/analyses/{a['id']}/documents/{doc_id}/pages/3").json()
        self.assertIn("5th June 2027", page["text"])
        self.assertEqual(self.client.get(f"/api/analyses/{a['id']}/documents/{doc_id}/pages/99").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/analyses/{a['id']}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/analyses/{a['id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/analyses/{a['id']}/documents/{doc_id}/pages/3").status_code, 404)
        with self.engine.connect() as conn:
            from sqlalchemy import text
            for table in ("source_documents", "document_pages", "extracted_items"):
                self.assertEqual(conn.execute(text(f"select count(*) from {table}")).scalar(), 0, table)

    def test_rate_limit_blocks_rapid_uploads(self):
        app.dependency_overrides[get_settings] = lambda: Settings(ai_rate_limit_per_minute=2)
        analyses_api.reset_limiter()
        self.demo_mode()
        codes = [self.client.post("/api/analyses", files=upload(DEMO)).status_code for _ in range(3)]
        self.assertEqual(codes, [201, 201, 429])

    def test_unknown_analysis_is_404(self):
        self.assertEqual(self.client.get("/api/analyses/nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()
