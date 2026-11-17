import tempfile
import unittest
from pathlib import Path

from app.core.config import load_settings
from app.services.ai_service import AINotConfiguredError, get_ai_status, require_ai


def write_env(text: str, encoding="utf-8") -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / ".env"
    p.write_bytes(text.encode(encoding))
    return p


class ConfigTests(unittest.TestCase):
    def test_no_env_file_means_demo_mode(self):
        s = load_settings(env_file=Path("/nonexistent/.env"), environ={})
        self.assertEqual(s.ai_mode, "demo")
        self.assertIsNone(s.gemini_api_key)
        self.assertEqual(s.gemini_model, "gemini-3.8-flash")

    def test_placeholder_key_is_not_a_real_key(self):
        s = load_settings(write_env("GEMINI_API_KEY=your_gemini_api_key_here\n"), {})
        self.assertEqual(s.ai_mode, "demo")

    def test_empty_key_is_demo(self):
        self.assertEqual(load_settings(write_env("GEMINI_API_KEY=\n"), {}).ai_mode, "demo")

    def test_real_key_in_file_switches_to_live(self):
        s = load_settings(write_env('GEMINI_API_KEY="abc123"\n'), {})
        self.assertEqual((s.ai_mode, s.gemini_api_key), ("live", "abc123"))

    def test_environment_variable_overrides_file(self):
        s = load_settings(write_env("GEMINI_API_KEY=from_file\n"), {"GEMINI_API_KEY": "from_env"})
        self.assertEqual(s.gemini_api_key, "from_env")

    def test_windows_notepad_bom_and_crlf(self):
        s = load_settings(write_env("\ufeffGEMINI_API_KEY=k1\r\nMAX_UPLOAD_MB=5\r\n"), {})
        self.assertEqual((s.gemini_api_key, s.max_upload_mb), ("k1", 5))

    def test_comments_and_inline_comments(self):
        s = load_settings(write_env("# comment\nMAX_PDF_PAGES=50 # pages\n"), {})
        self.assertEqual(s.max_pdf_pages, 50)

    def test_key_never_appears_in_repr(self):
        s = load_settings(write_env("GEMINI_API_KEY=SECRET-VALUE\n"), {})
        self.assertNotIn("SECRET-VALUE", repr(s))

    def test_bad_number_gives_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            load_settings(write_env("MAX_UPLOAD_MB=ten\n"), {})
        self.assertIn("MAX_UPLOAD_MB", str(ctx.exception))

    def test_cors_origins_parsed(self):
        s = load_settings(write_env("CORS_ORIGINS=http://a.test, http://b.test\n"), {})
        self.assertEqual(s.cors_origins, ("http://a.test", "http://b.test"))


class AIStatusTests(unittest.TestCase):
    def test_demo_status_is_honest(self):
        s = load_settings(Path("/nonexistent/.env"), {})
        st = get_ai_status(s)
        self.assertEqual((st.mode, st.configured), ("demo", False))
        self.assertIn("demo", st.message.lower())
        with self.assertRaises(AINotConfiguredError):
            require_ai(s)

    def test_live_status(self):
        s = load_settings(write_env("GEMINI_API_KEY=k\n"), {})
        self.assertTrue(get_ai_status(s).configured)
        require_ai(s)  # does not raise


if __name__ == "__main__":
    unittest.main()


class AiTimeoutSettingTests(unittest.TestCase):
    def test_default_leaves_room_for_slow_thinking_models(self):
        self.assertEqual(load_settings(env_file=Path("/nonexistent/.env"), environ={}).ai_timeout_seconds, 120)

    def test_can_be_raised_in_the_env_file(self):
        self.assertEqual(load_settings(write_env("AI_TIMEOUT_SECONDS=240\n"), {}).ai_timeout_seconds, 240)
