import ipaddress
import json
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

MAX_REDIRECTS = 5


def _walk_json_ld(data):
    """Yield every object in a JSON-LD document, including @graph entries."""
    if isinstance(data, list):
        for item in data:
            yield from _walk_json_ld(item)
    elif isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            yield from _walk_json_ld(graph)


def _job_posting_objects(soup):
    """Parse embedded schema.org JobPosting blocks (D4)."""
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk_json_ld(data):
            types = item.get("@type")
            types = types if isinstance(types, list) else [types]
            if any(str(t).lower() == "jobposting" for t in types):
                yield item


def _company_from_json_ld(soup) -> str:
    for item in _job_posting_objects(soup):
        org = item.get("hiringOrganization")
        if isinstance(org, dict):
            org = org.get("name")
        if isinstance(org, str) and org.strip():
            return org.strip()
    return ""


def _title_from_json_ld(soup) -> str:
    for item in _job_posting_objects(soup):
        title = item.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return ""



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
                # Many job boards (Indeed, LinkedIn) block automated fetches.
                # Fail loudly instead of returning an empty result that would
                # be saved as a junk row.
                raise ValueError(
                    f"Could not fetch the page (HTTP {resp.status_code}). "
                    "The site may block automated access -- please paste the job description manually instead."
                )

            soup = BeautifulSoup(resp.text, "html.parser")
            # D4: read the embedded JobPosting schema before stripping scripts.
            json_ld_title = _title_from_json_ld(soup)
            company = _company_from_json_ld(soup)
            # Grab the visible headline before removing header/nav wrappers:
            # many job pages put the <h1> inside <header>.
            title = soup.find("h1")
            title_text = (
                title.get_text().strip() if title else ""
            ) or json_ld_title or "Job Posting"

            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            body_text = soup.get_text(separator="\n").strip()
            lines = [line.strip() for line in body_text.splitlines() if line.strip()]
            text = "\n".join(lines[:200])
            if len(text) < 100:
                # 200 but no real content: bot-wall / cookie-wall page.
                raise ValueError(
                    "Could not extract job content from this page. "
                    "The site may require JavaScript or block automated access -- please paste the job description manually instead."
                )
            return {
                "title": title_text,
                # D4: empty when the page has no JobPosting schema -- the UI
                # shows "Company not provided" instead of a made-up name.
                "company": company,
                "text": text
            }

    raise ValueError(f"URL blocked by SSRF guard: too many redirects (>{MAX_REDIRECTS})")
