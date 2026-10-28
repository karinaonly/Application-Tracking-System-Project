import asyncio
import unittest
from unittest.mock import patch

from app.jobs.scraper import is_safe_public_url, scrape_job_url


class _FakeResponse:
    def __init__(self, status_code=200, text="", is_redirect=False, next_url=None):
        self.status_code = status_code
        self.text = text
        self.is_redirect = is_redirect
        self.next_url = next_url


class _FakeClient:
    """Stands in for httpx.AsyncClient; returns queued responses in order."""

    def __init__(self, responses):
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None):
        return self._responses.pop(0)


class SafeUrlGuardTests(unittest.TestCase):
    def test_blocked_urls(self):
        cases = [
            ("ftp://example.com/job", "scheme"),
            ("javascript:alert(1)", "scheme"),
            ("not a url", "scheme"),
            ("http:///path-only", "missing host"),
            ("http://user:pass@example.com/job", "credentials"),
            ("http://localhost:8000/job", "non-public"),
            ("http://127.0.0.1:8000/job", "non-public"),
            ("http://10.0.0.5/job", "non-public"),
            ("http://192.168.1.10/job", "non-public"),
            ("http://172.16.0.9/job", "non-public"),
            ("http://169.254.169.254/latest/meta-data/", "non-public"),
            ("http://0.0.0.0/", "non-public"),
            ("http://[::1]:8000/job", "non-public"),
        ]
        for url, expected_reason in cases:
            with self.subTest(url=url):
                ok, reason = is_safe_public_url(url)
                self.assertFalse(ok)
                self.assertIn(expected_reason, reason)

    def test_public_ip_literal_is_allowed(self):
        ok, reason = is_safe_public_url("https://8.8.8.8/job")
        self.assertTrue(ok, reason)

    def test_scrape_rejects_loopback_target(self):
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(scrape_job_url("http://127.0.0.1:8000/jobs"))
        self.assertIn("SSRF guard", str(ctx.exception))


class ScrapeFailureTests(unittest.TestCase):
    """Failed scrapes must raise, not return empty results that get saved as junk rows."""

    URL = "https://8.8.8.8/job"  # public IP literal: passes the SSRF guard without DNS

    def _run_with(self, responses):
        with patch("app.jobs.scraper.httpx.AsyncClient", lambda **kw: _FakeClient(responses)):
            return asyncio.run(scrape_job_url(self.URL))

    def test_non_200_raises_instead_of_returning_empty(self):
        with self.assertRaises(ValueError) as ctx:
            self._run_with([_FakeResponse(status_code=403)])
        self.assertIn("Could not fetch the page", str(ctx.exception))
        self.assertIn("paste the job description manually", str(ctx.exception))

    def test_bot_wall_page_with_200_but_no_content_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._run_with([_FakeResponse(status_code=200, text="Enable JavaScript and cookies to continue")])
        self.assertIn("Could not extract job content", str(ctx.exception))

    def test_successful_scrape_returns_text(self):
        html = ("<html><head><script>var x=1;</script></head><body><h1>Backend Developer</h1>"
                "<p>We are looking for a developer with strong Python experience.</p>"
                "<p>Requirements: Python, Docker, PostgreSQL and REST API design. "
                "Candidates should have experience building web services at scale.</p></body></html>")
        out = self._run_with([_FakeResponse(status_code=200, text=html)])
        self.assertEqual(out["title"], "Backend Developer")
        self.assertIn("Python", out["text"])

    def test_redirect_without_next_url_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._run_with([_FakeResponse(status_code=301, is_redirect=True, next_url=None)])
        self.assertIn("redirect", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
