"""Contact-block parsing.

The contact block is parsed field-by-field (A15): a line containing an email,
phone, or URL is never mistaken for the candidate's name, and labeled fields
("LinkedIn: ...") win outright.
"""
import re

from app.common.headline import extract_headline
from app.parser.sections.common import (
    ACTION_RE,
    EMAIL_RE,
    GENERIC_URL_RE,
    GITHUB_URL_RE,
    LABELED_FIELD_RE,
    LINKEDIN_URL_RE,
    LOCATION_LINE_RE,
    PHONE_RE,
    ROLE_LINE_RE,
)


class ContactParser:
    def parse(self, text: str) -> dict:
        contact = {
            "name": "",
            # A4: the professional title ("FULL STACK DEVELOPER") printed under
            # the name. Kept so the exporter can show the candidate's own title
            # instead of substituting the job posting's.
            "title": "",
            "email": "",
            "phone": "",
            "linkedin": "",
            "github": "",
            "portfolio": "",
            "location": "",
        }
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue

            # A15: labeled lines win outright ("LinkedIn: linkedin.com/in/jane")
            labeled = LABELED_FIELD_RE.match(line)
            if labeled:
                key = labeled.group("key").lower()
                value = labeled.group("value").strip()
                if key == "linkedin":
                    contact["linkedin"] = self._normalize_handle("linkedin", value)
                elif key == "github":
                    contact["github"] = self._normalize_handle("github", value)
                elif key in ("portfolio", "website"):
                    m = GENERIC_URL_RE.search(value)
                    if m and "@" not in m.group(0):
                        contact["portfolio"] = m.group(0).rstrip(".,);")
                elif key == "email":
                    m = EMAIL_RE.search(value)
                    if m:
                        contact["email"] = m.group(0)
                elif key in ("phone", "mobile", "tel"):
                    contact["phone"] = value
                else:  # location / address
                    contact["location"] = value
                continue

            has_url = False
            li = LINKEDIN_URL_RE.search(line)
            if li and not contact["linkedin"]:
                contact["linkedin"] = li.group(0).rstrip("/")
                has_url = True
            gh = GITHUB_URL_RE.search(line)
            if gh and not contact["github"]:
                contact["github"] = gh.group(0).rstrip("/")
                has_url = True

            # A15: a portfolio is any URL that is NOT linkedin/github
            if not contact["portfolio"]:
                for m in GENERIC_URL_RE.finditer(line):
                    token = m.group(0)
                    if "@" in token:
                        continue
                    if LINKEDIN_URL_RE.search(token) or GITHUB_URL_RE.search(token):
                        continue
                    contact["portfolio"] = token.rstrip(".,);")
                    has_url = True
                    break

            if not contact["email"] and "@" in line:
                m = EMAIL_RE.search(line)
                if m:
                    contact["email"] = m.group(0)
                    has_url = True

            if not contact["phone"] and PHONE_RE.search(line):
                contact["phone"] = PHONE_RE.search(line).group().strip()

            looks_location = (
                "@" not in line
                and not has_url
                and len(line) < 60
                and len(line.split()) <= 6
                and LOCATION_LINE_RE.match(line)
                and not ACTION_RE.match(line)
            )
            if looks_location and not contact["location"]:
                contact["location"] = line

            # A15: a name line must not contain an email, phone, or URL
            is_name_candidate = (
                not contact["name"]
                and "@" not in line
                and not has_url
                and not PHONE_RE.search(line)
                and not looks_location
                and not ROLE_LINE_RE.search(line)
                and not re.search(r"\d{3,}", line)
                and len(line) < 60
            )
            if is_name_candidate:
                contact["name"] = line

        contact["title"] = extract_headline(text, contact["name"])
        return contact

    def _normalize_handle(self, kind: str, value: str) -> str:
        """Turn a labeled value into a canonical URL form."""
        value = value.strip().rstrip(".,;")
        if kind == "linkedin":
            if LINKEDIN_URL_RE.search(value):
                return LINKEDIN_URL_RE.search(value).group(0).rstrip("/")
            # bare username -> linkedin.com/in/<user>
            return f"linkedin.com/in/{value.strip('/')}"
        if kind == "github":
            if GITHUB_URL_RE.search(value):
                return GITHUB_URL_RE.search(value).group(0).rstrip("/")
            return f"github.com/{value.strip('/')}"
        return value
