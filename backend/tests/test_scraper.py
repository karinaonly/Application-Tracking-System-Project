import asyncio
import unittest

from app.jobs.scraper import is_safe_public_url, scrape_job_url


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


if __name__ == "__main__":
    unittest.main()
