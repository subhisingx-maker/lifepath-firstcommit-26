"""When the AI is too slow (or its answer is too big) for one request.

Real-world symptom this guards against: uploading a long notice returned HTTP 504 after several minutes,
because every large batch hit the time limit and the pipeline kept trying large batches.

Uses a fake AI and plain-text pages, so no PDF library is needed. Needs pydantic; skipped (not passed) without it.
"""
import json
import unittest
from importlib.util import find_spec

HAVE = find_spec("pydantic") is not None

if HAVE:
    from app.services.ai_service import AIProviderError
    from app.services.extraction_pipeline import run_pipeline
    from tests.support import FakeProvider

EMPTY_ANSWER = json.dumps({"items": [], "not_found": []})


def pages_of(count, size=500):
    """`count` text pages of about `size` characters."""
    return [(f"Admission rule {n}. " * 60)[:size] for n in range(count)]


def pages_in(user_prompt):
    return user_prompt.count("[[PAGE ")


def slow_when_more_than(limit, code="timeout"):
    """A fake AI that cannot cope with more than `limit` pages at once."""
    def respond(user):
        if pages_in(user) > limit:
            raise AIProviderError(code, "too slow", True)
        return EMPTY_ANSWER
    return respond


@unittest.skipUnless(HAVE, "pydantic not installed")
class SlowAiTests(unittest.TestCase):
    def test_timeout_on_a_big_batch_is_retried_as_two_halves(self):
        provider = FakeProvider(slow_when_more_than(4))
        result = run_pipeline(provider, pages_of(8), 100000)           # all 8 pages in one batch
        self.assertEqual(len(provider.calls), 3)                       # 8 pages (fails), then 4 + 4
        self.assertEqual(result.status, "ok")
        self.assertFalse(any("could not be analysed" in w for w in result.warnings))
        first_half, second_half = provider.calls[1][1], provider.calls[2][1]
        self.assertIn("[[PAGE 1]]", first_half)
        self.assertNotIn("[[PAGE 5]]", first_half)
        self.assertIn("[[PAGE 5]]", second_half)                       # page numbers stay correct

    def test_answer_cut_off_for_being_too_big_is_split_the_same_way(self):
        provider = FakeProvider(slow_when_more_than(4, code="truncated"))
        result = run_pipeline(provider, pages_of(8), 100000)
        self.assertEqual((len(provider.calls), result.status), (3, "ok"))

    def test_after_a_split_the_remaining_batches_are_smaller(self):
        provider = FakeProvider(slow_when_more_than(4))
        # 24 pages of 500 chars. Normally 8 pages per batch; once 8 proves too slow, 4 pages per batch.
        result = run_pipeline(provider, pages_of(24), 4000)
        self.assertEqual(result.status, "ok")
        sizes = [pages_in(u) for _, u in provider.calls]
        self.assertEqual(sizes, [8, 4, 4, 4, 4, 4, 4])                 # not 8, 4, 4, 8, 4, 4, 8, 4, 4
        self.assertEqual(len(provider.calls), 7)

    def test_gives_up_quickly_when_nothing_works(self):
        def always_slow(_u):
            raise AIProviderError("timeout", "too slow", True)
        provider = FakeProvider(always_slow)
        with self.assertRaises(AIProviderError) as ctx:
            run_pipeline(provider, pages_of(64), 4000)                 # 8 batches normally
        self.assertEqual(ctx.exception.code, "timeout")
        self.assertEqual(len(provider.calls), 3)                       # first batch + its two halves, then stop

    def test_repeated_timeouts_after_a_success_stop_early_and_say_so(self):
        state = {"n": 0}

        def respond(_u):
            state["n"] += 1
            if state["n"] == 1:
                return EMPTY_ANSWER
            raise AIProviderError("timeout", "too slow", True)
        provider = FakeProvider(respond)
        result = run_pipeline(provider, pages_of(6), 500)              # one page per batch
        self.assertEqual(len(provider.calls), 3)                       # ok, timeout, timeout -> stop
        self.assertEqual(result.status, "partial")
        self.assertTrue(any("Stopped early" in w and "Pages 4 onward" in w for w in result.warnings))

    def test_other_errors_are_not_split(self):
        def flaky(_u):
            raise AIProviderError("bad_response", "unavailable", True)
        provider = FakeProvider(flaky)
        with self.assertRaises(AIProviderError):
            run_pipeline(provider, pages_of(24), 4000)
        self.assertEqual(len(provider.calls), 3)                       # one call per batch, no halves

    def test_provider_outage_after_success_returns_partial_and_names_unanalysed_pages(self):
        state = {"calls": 0}
        def respond(_user):
            state["calls"] += 1
            if state["calls"] == 1:
                return EMPTY_ANSWER
            raise AIProviderError("service_error", "temporarily overloaded", True, http_status=503)
        provider = FakeProvider(respond)
        result = run_pipeline(provider, pages_of(4, size=700), 2000)
        self.assertEqual(result.status, "partial")
        self.assertTrue(any("temporarily overloaded" in warning for warning in result.warnings))
        self.assertTrue(any("Pages 3-4 could not be analysed" in warning for warning in result.warnings))
        self.assertEqual(len(provider.calls), 2)


if __name__ == "__main__":
    unittest.main()
