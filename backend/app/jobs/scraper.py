import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

MAX_REDIRECTS = 5


def is_safe_public_url(url: str) -> tuple[bool, str]:
    """E6 SSRF guard: only http(s), no credentials, and every resolved IP must be public.

    Returns (ok, reason). Reason is empty when ok.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "unparseable URL"
    if parsed.scheme not in ("http", "https"):
        return False, f"unsupported scheme: {parsed.scheme or '(none)'}"
    host = parsed.hostname
    if not host:
        return False, "missing host"
    if parsed.username or parsed.password:
        return False, "credentials in URL are not allowed"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, f"cannot resolve host: {host}"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False, f"unparseable resolved address: {info[4][0]}"
        # is_global rejects loopback, private, link-local (incl. 169.254.169.254),
        # multicast, and unspecified addresses.
        if not ip.is_global:
            return False, f"blocked non-public address: {ip}"
    return True, ""


async def scrape_job_url(url: str) -> dict:
    ok, reason = is_safe_public_url(url)
    if not ok:
        raise ValueError(f"URL blocked by SSRF guard: {reason}")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    # Redirects are followed manually so every hop passes the same guard.
    async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
        current_url = url
        for _ in range(MAX_REDIRECTS):
            ok, reason = is_safe_public_url(current_url)
            if not ok:
                raise ValueError(f"URL blocked by SSRF guard: {reason}")

            resp = await client.get(current_url, headers=headers)
            if resp.is_redirect:
                next_url = resp.next_url
                if next_url is None:
                    break
                current_url = str(next_url)
                continue
            if resp.status_code != 200:
                return {"title": "Scraped Job", "company": "", "text": ""}

            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            title = soup.find("h1")
            title_text = title.get_text().strip() if title else "Job Posting"
            body_text = soup.get_text(separator="\n").strip()
            lines = [line.strip() for line in body_text.splitlines() if line.strip()]
            return {
                "title": title_text,
                "company": "Extracted from web",
                "text": "\n".join(lines[:200])
            }

    raise ValueError(f"URL blocked by SSRF guard: too many redirects (>{MAX_REDIRECTS})")
