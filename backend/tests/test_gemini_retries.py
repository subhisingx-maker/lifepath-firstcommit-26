import unittest

from app.services.ai_service import AIProviderError
from app.services.gemini_provider import GeminiProvider


def success():
    return {"candidates": [{"content": {"parts": [{"text": '{"items": [], "not_found": []}'}]},
                            "finishReason": "STOP"}]}


class GeminiRetryTests(unittest.TestCase):
    def provider(self, post, *, timeout=30, sleeps=None, clock=None):
        sleeps = sleeps if sleeps is not None else []
        return GeminiProvider("private-key", "test-model", timeout=timeout, post=post,
                              sleeper=sleeps.append, clock=clock or (lambda: 0.0),
                              jitter=lambda low, high: high)

    def test_503_retries_then_succeeds(self):
        calls = []
        def post(*_args):
            calls.append(1)
            return (503, {"error": {"message": "high demand"}}, {}) if len(calls) == 1 else (200, success())
        sleeps = []
        result = self.provider(post, sleeps=sleeps).generate_json("system", "user")
        self.assertIn('"items"', result)
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeps, [1.0])

    def test_transient_network_failure_retries(self):
        calls = []
        def post(*_args):
            calls.append(1)
            if len(calls) == 1:
                raise AIProviderError("network", "offline", True)
            return 200, success()
        self.provider(post, sleeps=[]).generate_json("system", "user")
        self.assertEqual(len(calls), 2)

    def test_429_respects_retry_after(self):
        calls = []
        def post(*_args):
            calls.append(1)
            return (429, {}, {"Retry-After": "3"}) if len(calls) == 1 else (200, success())
        sleeps = []
        self.provider(post, sleeps=sleeps).generate_json("system", "user")
        self.assertEqual(sleeps, [3.0])

    def test_exhausted_retries_preserve_status_and_safe_provider_detail(self):
        calls = []
        def post(*_args):
            calls.append(1)
            return 503, {"error": {"message": "high demand private-key"}}, {}
        sleeps = []
        with self.assertRaises(AIProviderError) as ctx:
            self.provider(post, sleeps=sleeps).generate_json("system", "user")
        self.assertEqual(len(calls), 3)
        self.assertEqual(ctx.exception.code, "service_error")
        self.assertEqual(ctx.exception.http_status, 503)
        self.assertIn("high demand", ctx.exception.message)
        self.assertNotIn("private-key", ctx.exception.message)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_permanent_error_is_not_retried(self):
        calls = []
        def post(*_args):
            calls.append(1)
            return 401, {"error": {"message": "bad key"}}, {}
        with self.assertRaises(AIProviderError) as ctx:
            self.provider(post).generate_json("system", "user")
        self.assertEqual(len(calls), 1)
        self.assertEqual(ctx.exception.code, "auth")

    def test_retry_cannot_sleep_past_overall_deadline(self):
        now = [0.0]
        sleeps = []
        def sleep(delay):
            sleeps.append(delay)
            now[0] += delay
        def post(*_args):
            return 503, {}, {"Retry-After": "8"}
        with self.assertRaises(AIProviderError) as ctx:
            GeminiProvider("k", "m", timeout=5, post=post, sleeper=sleep, clock=lambda: now[0],
                           jitter=lambda low, high: high).generate_json("s", "u")
        self.assertEqual(ctx.exception.http_status, 503)
        self.assertEqual(sleeps, [])

    def test_retry_after_http_date_is_parsed(self):
        # A fixed current time avoids wall-clock dependent tests.
        from unittest.mock import patch
        with patch("app.services.gemini_provider.datetime") as dt:
            from datetime import datetime, timezone
            dt.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
            dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            calls = []
            def post(*_args):
                calls.append(1)
                return (429, {}, {"Retry-After": "Thu, 01 Jan 2026 00:00:04 GMT"}) if len(calls) == 1 else (200, success())
            sleeps = []
            self.provider(post, sleeps=sleeps).generate_json("s", "u")
            self.assertEqual(sleeps, [4.0])


if __name__ == "__main__":
    unittest.main()
