"""Journey preview endpoint tests. Use a FAKE AI (never Gemini). Skipped unless all dependencies are installed."""
import json
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
    from tests.support import CORRIGENDUM, DEMO, MERIDIAN, FakeProvider, item, notice_provider


def upload(path):
    return {"file": (path.name, path.read_bytes(), "application/pdf")}


@unittest.skipUnless(HAVE, "fastapi / httpx / pymupdf / sqlalchemy / pydantic not installed")
class JourneyPreviewApiTests(unittest.TestCase):
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
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.tmp.cleanup()

    def make(self, path=None):
        return self.client.post("/api/analyses", files=upload(path or MERIDIAN)).json()

    def journey(self, analysis_id, body=None):
        return self.client.post(f"/api/analyses/{analysis_id}/journey", json=body) if body is not None \
            else self.client.post(f"/api/analyses/{analysis_id}/journey")

    def test_demo_mode_is_blocked_with_a_helpful_message_and_no_ai_is_used(self):
        app.dependency_overrides[analyses_api.get_ai_provider] = lambda: None
        a = self.make(DEMO)
        r = self.journey(a["id"])
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (409, "no_reviewed_items"))
        self.assertIn("/api/demo/journey", r.json()["detail"]["message"])

    def test_preview_from_reviewed_items(self):
        a = self.make()
        calls = len(self.provider.calls)
        r = self.journey(a["id"])
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["preview"])
        steps = {s["key"]: s for s in body["steps"]}
        self.assertEqual({"check_eligibility", "prepare_documents", "register"} <= set(steps), True)
        self.assertNotIn("check_merit_list", steps)                              # no merit-list item -> no such step
        reg = steps["register"]["deadlines"][0]
        self.assertEqual((reg["date_iso"], reg["source"]["page"], reg["source"]["evidence"]), ("2027-06-05", 3, "verified"))
        doc = steps["prepare_documents"]["documents"][0]
        self.assertEqual((doc["name"], doc["level"]), ("Income certificate", "conditional"))
        self.assertEqual(steps["suggested_confirm_official_notice"]["kind"], "suggested")
        self.assertEqual(len(self.provider.calls), calls)                        # preview made no AI call

    def test_preview_saves_nothing(self):
        a = self.make()
        before = self.client.get(f"/api/analyses/{a['id']}").json()
        self.journey(a["id"], {"outcome": "selected", "completed": ["check_eligibility"]})
        self.assertEqual(self.client.get(f"/api/analyses/{a['id']}").json(), before)

    def test_unresolved_conflicts_block_generation(self):
        a = self.make()
        both = self.client.post(f"/api/analyses/{a['id']}/documents", files=upload(CORRIGENDUM)).json()
        r = self.journey(a["id"])
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (409, "unresolved_conflicts"))
        keys = {d["key"] for d in r.json()["detail"]["details"]}
        self.assertEqual(keys, {c["key"] for c in both["conflicts"]})
        self.assertEqual(len(keys), 2)

    def test_after_resolving_the_chosen_side_is_used_and_the_other_is_reported_as_skipped(self):
        a = self.make()
        both = self.client.post(f"/api/analyses/{a['id']}/documents", files=upload(CORRIGENDUM)).json()
        for c in both["conflicts"]:
            newer = next(s for s in c["sides"] if s["document_name"] == CORRIGENDUM.name)
            self.client.post(f"/api/analyses/{a['id']}/conflicts/resolve",
                             json={"conflict_key": c["key"], "chosen_item_id": newer["item_id"]})
        r = self.journey(a["id"])
        self.assertEqual(r.status_code, 200)
        body = r.json()
        steps = {s["key"]: s for s in body["steps"]}
        self.assertEqual([d["date_iso"] for d in steps["register"]["deadlines"]], ["2027-06-12"])
        self.assertEqual([d["level"] for d in steps["prepare_documents"]["documents"]], ["not_required"])
        self.assertEqual(len(body["skipped_items"]), 2)

    def test_outcome_and_completed_are_validated_and_applied(self):
        a = self.make()
        self.assertEqual(self.journey(a["id"], {"outcome": "maybe"}).status_code, 422)
        self.assertEqual(self.journey(a["id"], {"surprise": 1}).status_code, 422)
        ok = self.journey(a["id"], {"completed": ["check_eligibility", "nope"]}).json()
        steps = {s["key"]: s for s in ok["steps"]}
        self.assertEqual(steps["check_eligibility"]["status"], "completed")
        self.assertTrue(any("unknown step 'nope'" in w for w in ok["warnings"]))

    def test_rejected_and_unverified_items_do_not_drive_steps(self):
        a = self.make()
        eligibility = next(i for i in a["items"] if i["category"] == "eligibility")
        self.client.patch(f"/api/analyses/{a['id']}/items/{eligibility['id']}", json={"review_state": "rejected"})
        body = self.journey(a["id"]).json()
        self.assertNotIn("check_eligibility", {s["key"] for s in body["steps"]})
        self.assertIn(eligibility["id"], {s["item_id"] for s in body["skipped_items"]})

    def test_only_unverified_items_cannot_make_a_journey(self):
        self.provider.respond = lambda _u: json.dumps({"items": [
            item("eligibility", "Invented rule", "Candidates must hold a PhD in astrophysics to apply here.", 1)]})
        a = self.make()
        self.assertEqual(a["items"][0]["status"], "unverified")
        r = self.journey(a["id"])
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (409, "insufficient_information"))

    def test_unknown_analysis_is_404(self):
        self.assertEqual(self.journey("nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()
