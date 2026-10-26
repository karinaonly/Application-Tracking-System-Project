import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.analyzer.ai_config import resolve_ai_config
from app.analyzer.ai_rewriter import AIRewriter
from app.auth.router import ai_status
from app.config.settings import Settings

VALID_OPENAI = "sk-" + "a" * 30
VALID_GROQ_UNDERSCORE = "gsk_" + "b" * 30
VALID_GROQ_HYPHEN = "gsk-" + "c" * 30
VALID_GEMINI = "AIza" + "d" * 30


def make_settings(api_key: str, provider: str = "auto") -> Settings:
    return Settings(groq_api_key=api_key, ai_provider=provider)


def make_session() -> MagicMock:
    session = MagicMock()
    session.exec.return_value.first.return_value = None
    return session


class ResolveAIConfigTests(unittest.TestCase):
    def test_table_driven_cases(self):
        cases = [
            {
                "name": "empty key",
                "key": "",
                "provider": "auto",
                "expected_provider": "auto",
                "configured": False,
                "reason": "missing",
            },
            {
                "name": "placeholder key",
                "key": "sk-placeholder",
                "provider": "auto",
                "expected_provider": "openai",
                "configured": False,
                "reason": "missing",
            },
            {
                "name": "short key",
                "key": "sk-short",
                "provider": "auto",
                "expected_provider": "openai",
                "configured": False,
                "reason": "invalid_format",
            },
            {
                "name": "key with internal whitespace",
                "key": "sk-" + "a" * 10 + " " + "b" * 10,
                "provider": "auto",
                "expected_provider": "openai",
                "configured": False,
                "reason": "invalid_format",
            },
            {
                "name": "explicit provider with odd prefix",
                "key": "totally-custom-key-1234567890",
                "provider": "groq",
                "expected_provider": "groq",
                "configured": True,
                "reason": "configured",
            },
            {
                "name": "auto with openai prefix",
                "key": VALID_OPENAI,
                "provider": "auto",
                "expected_provider": "openai",
                "configured": True,
                "reason": "configured",
            },
            {
                "name": "auto with groq underscore prefix",
                "key": VALID_GROQ_UNDERSCORE,
                "provider": "auto",
                "expected_provider": "groq",
                "configured": True,
                "reason": "configured",
            },
            {
                "name": "auto with groq hyphen prefix",
                "key": VALID_GROQ_HYPHEN,
                "provider": "auto",
                "expected_provider": "groq",
                "configured": True,
                "reason": "configured",
            },
            {
                "name": "auto with gemini prefix",
                "key": VALID_GEMINI,
                "provider": "auto",
                "expected_provider": "gemini",
                "configured": True,
                "reason": "configured",
            },
            {
                "name": "auto with unknown prefix",
                "key": "zzz_" + "e" * 30,
                "provider": "auto",
                "expected_provider": "auto",
                "configured": False,
                "reason": "invalid_format",
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                config = resolve_ai_config(make_settings(case["key"], case["provider"]))
                self.assertEqual(config.provider, case["expected_provider"])
                self.assertEqual(config.configured, case["configured"])
                self.assertEqual(config.reason, case["reason"])

    def test_key_is_stripped_before_validation(self):
        config = resolve_ai_config(make_settings(f"  {VALID_GROQ_UNDERSCORE}  ", "auto"))
        self.assertTrue(config.configured)
        self.assertEqual(config.api_key, VALID_GROQ_UNDERSCORE)

    def test_explicit_provider_does_not_require_prefix(self):
        settings = make_settings("not-a-known-prefix-but-long-enough", "openai")
        config = resolve_ai_config(settings)
        self.assertTrue(config.configured)
        self.assertEqual(config.provider, "openai")

    def test_groq_config_keeps_base_url(self):
        config = resolve_ai_config(make_settings(VALID_GROQ_UNDERSCORE, "auto"))
        settings = make_settings(VALID_GROQ_UNDERSCORE, "auto")
        self.assertEqual(config.base_url, settings.ai_base_url)

    def test_openai_config_uses_client_default_base_url(self):
        config = resolve_ai_config(make_settings(VALID_OPENAI, "auto"))
        self.assertEqual(config.base_url, "")

    def test_gemini_config_uses_gemini_base_url(self):
        settings = make_settings(VALID_GEMINI, "auto")
        config = resolve_ai_config(settings)
        self.assertEqual(config.base_url, settings.gemini_base_url)

    def test_client_uses_configured_timeout_and_no_sdk_retries(self):
        settings = make_settings(VALID_GROQ_UNDERSCORE, "auto")
        with patch("app.analyzer.ai_rewriter.get_settings", return_value=settings), \
                patch("app.analyzer.ai_rewriter.OpenAI") as openai_cls:
            AIRewriter()

        kwargs = openai_cls.call_args.kwargs
        self.assertEqual(kwargs["timeout"], settings.ai_timeout_seconds)
        self.assertEqual(kwargs["max_retries"], 0)


class StatusAgreementTests(unittest.TestCase):
    def _resolved_pair(self, settings):
        with patch("app.analyzer.ai_rewriter.get_settings", return_value=settings):
            rewriter = AIRewriter()
        with patch("app.auth.router.get_settings", return_value=settings):
            status = ai_status(user=SimpleNamespace(id="user-1"), session=make_session())
        return rewriter, status

    def test_status_and_rewriter_agree(self):
        settings_cases = [
            make_settings(VALID_GROQ_UNDERSCORE, "auto"),
            make_settings(VALID_OPENAI, "auto"),
            make_settings(VALID_GEMINI, "auto"),
            make_settings("", "auto"),
            make_settings("sk-short", "auto"),
            make_settings("not-a-known-prefix-but-long-enough", "groq"),
        ]

        for settings in settings_cases:
            with self.subTest(key_length=len(settings.groq_api_key), provider=settings.ai_provider):
                rewriter, status = self._resolved_pair(settings)
                try:
                    self.assertEqual(status["configured"], rewriter.client is not None)
                    self.assertEqual(status["provider"], rewriter.provider)
                    self.assertEqual(status["model"], rewriter.model)
                finally:
                    if rewriter.client is not None:
                        rewriter.client.close()

    def test_status_response_never_contains_the_key(self):
        settings = make_settings(VALID_GROQ_UNDERSCORE, "auto")
        _, status = self._resolved_pair(settings)

        self.assertNotIn("api_key", status)
        self.assertNotIn(VALID_GROQ_UNDERSCORE, json.dumps(status))
        self.assertNotIn(VALID_GROQ_UNDERSCORE, status.values())


if __name__ == "__main__":
    unittest.main()
