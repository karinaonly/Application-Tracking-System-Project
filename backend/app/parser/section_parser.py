import re
from app.common.constants import SECTION_PATTERNS


class SectionParser:
    # Left-column tags from the master resume layout — never real content
    LABEL_RE = re.compile(
        r"^(?:College|Senior\s*High(?:\s*School)?|University|Institute|"
        r"Internship|Capstone|Academic|Freelance|Part[- ]?Time|"
        r"Full[- ]?Time|Contract|Volunteer|Personal|Side\s*Project)$",
        re.I,
    )
    DATE_RE = re.compile(
        r"(?P<dates>"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?"
        r"(?:20|19)\d{2}"
        r"(?:\s*[-–—to]+\s*"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?"
        r"(?:(?:20|19)\d{2}|Present|Current))?"
        r")",
        re.I,
    )
    BULLET_RE = re.compile(r"^[•▪▸►◆○●\-–—*]\s+")
    ACTION_RE = re.compile(
        r"^(built|led|implemented|deployed|managed|collaborated|developed|"
        r"created|designed|optimized|automated|integrated|handled|wrote|"
        r"improved|participated|maintained|configured|architected)\b",
        re.I,
    )
    # "Backend Developer Intern at Synchores Information"
    ROLE_AT_CO_RE = re.compile(
        r"^(?P<title>.+?)\s+\bat\b\s+(?P<company>.+)$",
        re.I,
    )

    def parse(self, raw_text: str) -> dict:
        lines = raw_text.splitlines()
        sections: dict = {}
        current_sec = None
        current_body: list[str] = []
        sec_order: list[str] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                if current_sec:
                    current_body.append("")
                continue

            detected = self._detect_sec(line_str)

            # Skip REFERENCES entirely (ATS best practice)
            if detected == "references":
                if current_sec and current_body:
                    sections[current_sec] = {"raw": "\n".join(current_body).strip()}
                current_sec = None
                current_body = []
                continue

            if detected:
                if current_sec:
                    raw = "\n".join(current_body).strip()
                    raw = re.split(r"(?i)\n?\s*REFERENCES?\b.*", raw, maxsplit=1)[0].strip()
                    sections[current_sec] = {"raw": raw}
                current_sec = detected
                current_body = []
                sec_order.append(detected)
            else:
                if current_sec:
                    current_body.append(line_str)
                else:
                    if "contact" not in sections:
                        sections["contact"] = {"raw": ""}
                        sec_order.insert(0, "contact")
                    sections["contact"]["raw"] += line_str + "\n"

        if current_sec and current_body:
            raw = "\n".join(current_body).strip()
            raw = re.split(r"(?i)\n?\s*REFERENCES?\b.*", raw, maxsplit=1)[0].strip()
            sections[current_sec] = {"raw": raw}

        for key in list(sections.keys()):
            if key.startswith("_") or not isinstance(sections.get(key), dict):
                continue
            if "raw" in sections[key] and sections[key]["raw"]:
                sections[key]["raw"] = re.split(
                    r"(?i)\n?\s*REFERENCES?\b.*", sections[key]["raw"], maxsplit=1
                )[0].strip()

        sections["_section_order"] = sec_order
        sections["contact_parsed"] = self._parse_contact(
            sections.get("contact", {}).get("raw", "")
        )
        sections["experience_parsed"] = self._parse_experience(
            sections.get("experience", {}).get("raw", "")
        )
        sections["projects_parsed"] = self._parse_projects(
            sections.get("projects", {}).get("raw", "")
        )
        sections["education_parsed"] = self._parse_education(
            sections.get("education", {}).get("raw", "")
        )
        sections["skills_parsed"] = self._parse_skills(
            sections.get("skills", {}).get("raw", "")
        )
        return sections

    def _detect_sec(self, line: str) -> str | None:
        cleaned = re.sub(r"[:\-_=|#*•]+", "", line).strip()
        if len(cleaned.split()) > 6:
            return None
        for name, pat in SECTION_PATTERNS.items():
            if re.match(pat, cleaned):
                return name
        return None

    # ─────────────────────────────────────────────
    # shared helpers
    # ─────────────────────────────────────────────
    def _is_label(self, line: str) -> bool:
        return bool(self.LABEL_RE.match(line.strip()))

    def _is_date_only(self, line: str) -> bool:
        s = line.strip()
        m = self.DATE_RE.fullmatch(s) or self.DATE_RE.fullmatch(
            re.sub(r"[\s\|•\-–—]+$", "", s)
        )
        return m is not None

    def _strip_date(self, line: str) -> tuple[str, str]:
        """Return (dates, rest). dates='' if none."""
        m = self.DATE_RE.search(line)
        if not m:
            return "", line.strip(" |-–—")
        dates = m.group("dates").strip()
        rest = (line[: m.start()] + line[m.end() :]).strip(" |-–—")
        return dates, rest

    def _split_role_at_company(self, text: str) -> tuple[str, str]:
        m = self.ROLE_AT_CO_RE.match(text.strip())
        if m:
            return m.group("title").strip(), m.group("company").strip()
        return text.strip(), ""

    def _clean_company(self, text: str) -> str:
        """Remove left-column label words that leaked into company/meta strings."""
        if not text:
            return ""
        # Remove standalone label tokens anywhere in the string
        text = re.sub(
            r"\b(?:Internship|Capstone|Academic|College|Freelance|Volunteer)\b",
            "",
            text,
            flags=re.I,
        )
        # Collapse leftover separators
        text = re.sub(r"\s*[|]\s*", " | ", text)
        text = re.sub(r"\s*[—–\-]\s*", " — ", text)
        text = re.sub(r"(?:\s*\|\s*){2,}", " | ", text)
        text = re.sub(r"(?:\s*—\s*){2,}", " — ", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip(" |—–- \t")

    def _clean_degree(self, text: str) -> str:
        """Fix 'School, ABM Strand' and leading label leftovers."""
        if not text:
            return ""
        text = re.sub(
            r"^(?:College|Senior\s*High(?:\s*School)?|University|Institute|School)\s*,?\s*",
            "",
            text,
            flags=re.I,
        ).strip()
        # If we stripped too hard and left a leading comma
        text = text.lstrip(", ").strip()
        return text

    # ─────────────────────────────────────────────
    # CONTACT
    # ─────────────────────────────────────────────
    def _parse_contact(self, text: str) -> dict:
        contact = {
            "name": "",
            "email": "",
            "phone": "",
            "linkedin": "",
            "github": "",
            "portfolio": "",
            "location": "",
        }
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if lines:
            for line in lines[:3]:
                if "@" not in line and not re.search(r"\d{3,}", line) and len(line) < 60:
                    # skip if it looks like a role line
                    if not re.search(r"(developer|engineer|student|intern)", line, re.I):
                        contact["name"] = line
                        break
            if not contact["name"] and lines:
                contact["name"] = lines[0]

        email = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
        if email:
            contact["email"] = email.group()

        phone = re.search(
            r"(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4}",
            text,
        )
        if phone:
            contact["phone"] = phone.group().strip()

        li = re.search(
            r"(?:linkedin\.com/in/|linkedin:\s*)([a-zA-Z0-9\-_/]+)", text, re.I
        )
        if li:
            contact["linkedin"] = li.group(0).replace("linkedin:", "").strip()

        gh = re.search(r"(?:github\.com/|github:\s*)([a-zA-Z0-9\-]+)", text, re.I)
        if gh:
            contact["github"] = gh.group(0).replace("github:", "").strip()

        port = re.search(
            r"(https?://[^\s]+|(?:[\w\-]+\.)?(?:vercel\.app|netlify\.app|github\.io)/[^\s]*)",
            text,
            re.I,
        )
        if port:
            contact["portfolio"] = port.group(1).rstrip(".,);")

        loc = re.search(
            r"([A-Z][a-zA-Z\s]+(?:City)?,\s*[A-Z][a-zA-Z]+(?:\s+[A-Z]{2})?)",
            text,
        )
        if loc:
            contact["location"] = loc.group(1).strip()

        return contact

    # ─────────────────────────────────────────────
    # EXPERIENCE
    # ─────────────────────────────────────────────
    def _parse_experience(self, text: str) -> list[dict]:
        if not text or not text.strip():
            return []

        entries: list[dict] = []
        lines = [l.rstrip() for l in text.splitlines()]

        current: dict | None = None
        pending_label = ""
        i = 0

        def flush():
            nonlocal current, pending_label
            if current:
                if pending_label and not current.get("_label"):
                    current["_label"] = pending_label

                # title empty but company holds "Role at Co"?
                if not current["title"] and current["company"]:
                    current["title"], extra = self._split_role_at_company(current["company"])
                    if extra:
                        current["company"] = extra

                # Scrub label leakage from every text field
                current["company"] = self._clean_company(current.get("company", ""))
                current["meta"] = self._clean_company(current.get("meta", ""))
                current["location"] = (current.get("location") or "").strip()

                # If company is still empty but meta looks like a company name, swap
                if not current["company"] and current["meta"]:
                    if not re.search(r"(?i)\d\s*-?\s*hour|\bremote\b|\bonsite\b", current["meta"]):
                        current["company"] = current["meta"]
                        current["meta"] = ""

                # Build a single clean subtitle for the exporter
                bits = []
                if current.get("company"):
                    bits.append(current["company"])
                if current.get("meta"):
                    bits.append(current["meta"])
                if current.get("location"):
                    bits.append(current["location"])

                subtitle = " | ".join(bits)
                subtitle = self._clean_company(subtitle)
                current["subtitle"] = subtitle
                current["company"] = subtitle  # exporter reads company OR subtitle

                # Drop internal keys
                current.pop("_label", None)
                entries.append(current)

            current = None
            pending_label = ""

        while i < len(lines):
            raw = lines[i]
            line = raw.strip()
            i += 1
            if not line:
                continue
            if re.match(r"(?i)^references?\b", line):
                break

            # --- pure left-column label ---
            if self._is_label(line):
                pending_label = line
                if current and not current.get("_label"):
                    current["_label"] = line
                continue

            # --- pure date line (left column) ---
            if self._is_date_only(line):
                flush()
                current = {
                    "title": "",
                    "company": "",
                    "location": "",
                    "meta": "",
                    "dates": line.strip(),
                    "bullets": [],
                    "_label": pending_label,
                }
                pending_label = ""
                continue

            is_bullet = bool(self.BULLET_RE.match(line))
            dates_in_line, rest = self._strip_date(line)
            rest = rest.strip()

            # --- header candidate ---
            looks_header = (
                not is_bullet
                and not self.ACTION_RE.match(line)
                and len(line) < 120
                and (
                    dates_in_line
                    or current is None
                    or (
                        current is not None
                        and current.get("bullets")
                        and rest
                        and rest[0].isupper()
                        and not rest.endswith(".")
                        and len(rest) < 70
                    )
                )
            )

            if looks_header and (dates_in_line or current is None or current.get("bullets")):
                if current and current["title"] and not dates_in_line and not current.get("bullets"):
                    pass  # treat as meta below
                else:
                    if current and (current["title"] or current["bullets"]):
                        flush()
                    elif current and not current["title"] and not dates_in_line:
                        pass

                    if current is None:
                        current = {
                            "title": "",
                            "company": "",
                            "location": "",
                            "meta": "",
                            "dates": dates_in_line or "",
                            "bullets": [],
                            "_label": pending_label,
                        }
                        pending_label = ""
                    elif dates_in_line and not current["dates"]:
                        current["dates"] = dates_in_line

                    if rest:
                        role, co = self._split_role_at_company(rest)
                        if not current["title"]:
                            current["title"] = role[:100]
                            if co and not current["company"]:
                                current["company"] = co
                        elif not current["company"]:
                            current["company"] = rest
                    continue

            # --- bullet ---
            if current and is_bullet:
                current["bullets"].append(self.BULLET_RE.sub("", line).strip())
                continue

            # --- meta / continuation ---
            if current and line:
                cleaned = self.BULLET_RE.sub("", line).strip()
                if self._is_label(cleaned):
                    current["_label"] = cleaned
                    continue

                if not current["title"]:
                    role, co = self._split_role_at_company(cleaned)
                    current["title"] = role[:100]
                    if co:
                        current["company"] = co
                    continue

                if not current["company"]:
                    if "|" in cleaned:
                        parts = [p.strip() for p in cleaned.split("|")]
                        current["company"] = parts[0]
                        if len(parts) > 1:
                            current["location"] = parts[-1]
                    else:
                        current["company"] = cleaned
                    continue

                # extra meta
                if "|" in cleaned:
                    parts = [p.strip() for p in cleaned.split("|")]
                    current["meta"] = (
                        f"{current['meta']} — {parts[0]}".strip(" —")
                        if current["meta"]
                        else parts[0]
                    )
                    if len(parts) > 1:
                        current["location"] = parts[-1]
                elif re.search(r"(?i)(\d\s*-?\s*hour|\bremote\b|\bonsite\b|\bhybrid\b|\binternship\b)", cleaned):
                    current["meta"] = (
                        f"{current['meta']} — {cleaned}".strip(" —")
                        if current["meta"]
                        else cleaned
                    )
                elif current["bullets"]:
                    current["bullets"][-1] += " " + cleaned
                else:
                    current["company"] = f"{current['company']} — {cleaned}"
                continue

        flush()
        return entries

    # ─────────────────────────────────────────────
    # PROJECTS
    # ─────────────────────────────────────────────
    def _parse_projects(self, text: str) -> list[dict]:
        if not text or not text.strip():
            return []

        entries: list[dict] = []
        lines = [l.rstrip() for l in text.splitlines()]

        def is_continuation(s: str) -> bool:
            if not s:
                return True
            if s[0].islower():
                return True
            if s.endswith(".") and len(s) < 80:
                return True
            if re.match(
                r"^(and|or|with|using|to|for|which|that|ensuring|delivering|"
                r"automating|keeping|writing|wiring|process|collision|respond)\b",
                s,
                re.I,
            ):
                return True
            return False

        current: dict | None = None
        pending_label = ""
        i = 0

        def flush():
            nonlocal current, pending_label
            if current:
                entries.append(current)
            current = None
            pending_label = ""

        while i < len(lines):
            line = lines[i].strip()
            i += 1
            if not line:
                continue
            if re.match(r"(?i)^references?\b", line):
                break

            if self._is_label(line):
                pending_label = line
                continue

            if self._is_date_only(line):
                flush()
                current = {
                    "title": "",
                    "subtitle": "",
                    "dates": line.strip(),
                    "bullets": [],
                }
                if pending_label:
                    current["_tag"] = pending_label
                    pending_label = ""
                continue

            is_bullet = bool(self.BULLET_RE.match(line))
            dates_in_line, rest = self._strip_date(line)
            rest = rest.strip()

            is_real_title = (
                not is_bullet
                and not self.ACTION_RE.match(line)
                and not is_continuation(line)
                and not self._is_label(line)
                and (
                    dates_in_line
                    or (
                        current is not None
                        and current.get("bullets")
                        and len(line) < 70
                        and not line.endswith(".")
                        and line[0].isupper()
                    )
                    or current is None
                    or (current is not None and not current.get("title"))
                )
            )

            if is_real_title:
                if (
                    current
                    and current.get("title")
                    and not dates_in_line
                    and not current.get("bullets")
                    and not current.get("subtitle")
                    and len(line) < 80
                ):
                    tag = current.pop("_tag", "")
                    role = rest or line
                    current["subtitle"] = f"{tag} · {role}".strip(" ·") if tag else role
                    continue

                if current and current.get("title"):
                    flush()

                if current is None:
                    current = {
                        "title": "",
                        "subtitle": "",
                        "dates": dates_in_line or "",
                        "bullets": [],
                    }
                    if pending_label:
                        current["_tag"] = pending_label
                        pending_label = ""
                elif dates_in_line and not current["dates"]:
                    current["dates"] = dates_in_line

                title_text = rest or (line if not dates_in_line else "")
                if title_text and not current["title"]:
                    current["title"] = title_text[:100]
                continue

            if current and is_bullet:
                current["bullets"].append(self.BULLET_RE.sub("", line).strip())
                continue

            if current and line:
                cleaned = self.BULLET_RE.sub("", line).strip()
                if current["bullets"]:
                    current["bullets"][-1] += " " + cleaned
                elif not current["title"]:
                    current["title"] = cleaned[:100]
                elif not current["subtitle"]:
                    tag = current.pop("_tag", "")
                    current["subtitle"] = f"{tag} · {cleaned}".strip(" ·") if tag else cleaned
                else:
                    current["bullets"].append(cleaned)

        flush()
        for e in entries:
            e.pop("_tag", None)
        return entries

    # ─────────────────────────────────────────────
    # EDUCATION
    # ─────────────────────────────────────────────
    def _parse_education(self, text: str) -> list[dict]:
        if not text or not text.strip():
            return []

        entries: list[dict] = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        school_hint = re.compile(
            r"\b(University|College|Campus|Institute|School|Academy)\b", re.I
        )
        degree_hint = re.compile(
            r"\b(Bachelor|Master|Doctor|B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|"
            r"Ph\.?D\.?|Senior\s*High|Diploma|Certificate|Cum Laude|"
            r"Magna|Summa|Honor|Strand|GWA|GPA)\b",
            re.I,
        )

        current: dict | None = None

        def flush():
            nonlocal current
            if current:
                # If degree accidentally holds the school, swap
                if (
                    not current["school"]
                    and current["degree"]
                    and school_hint.search(current["degree"])
                    and not degree_hint.search(current["degree"])
                ):
                    current["school"] = current["degree"]
                    current["degree"] = ""

                # Scrub leftovers
                current["school"] = self._clean_degree(current.get("school", ""))
                current["degree"] = self._clean_degree(current.get("degree", ""))

                # Senior High special case
                if not current["degree"] and current.get("details"):
                    rebuilt = []
                    for d in current["details"]:
                        d2 = self._clean_degree(d)
                        if d2:
                            rebuilt.append(d2)
                    current["details"] = rebuilt

                entries.append(current)
            current = None

        for line in lines:
            if re.match(r"(?i)^references?\b", line):
                break
            if self._is_label(line):
                continue

            if self._is_date_only(line):
                flush()
                current = {
                    "dates": line.strip(),
                    "school": "",
                    "degree": "",
                    "details": [],
                }
                continue

            dates_in_line, rest = self._strip_date(line)
            rest = rest.strip()

            if dates_in_line and len(line) < 120:
                flush()
                current = {
                    "dates": dates_in_line,
                    "school": "",
                    "degree": "",
                    "details": [],
                }
                if rest:
                    if school_hint.search(rest) and not degree_hint.search(rest):
                        current["school"] = rest
                    elif degree_hint.search(rest) and not school_hint.search(rest):
                        current["degree"] = rest
                    else:
                        current["school"] = rest
                continue

            if current is None:
                current = {
                    "dates": "",
                    "school": "",
                    "degree": "",
                    "details": [],
                }

            # classify the line
            if re.match(r"(?i)^senior\s*high", line) or (
                degree_hint.search(line) and re.search(r"(?i)strand|honor|cum laude|gpa|gwa", line)
            ):
                if not current["degree"]:
                    current["degree"] = line
                    continue

            if not current["school"] and school_hint.search(line):
                current["school"] = line
            elif not current["degree"] and degree_hint.search(line):
                current["degree"] = line
            elif not current["school"] and len(line) < 80:
                current["school"] = line
            elif not current["degree"] and len(line) < 100:
                current["degree"] = line
            else:
                current["details"].append(line)

        flush()
        return entries

    # ─────────────────────────────────────────────
    # SKILLS
    # ─────────────────────────────────────────────
    def _parse_skills(self, text: str) -> list[str]:
        if not text:
            return []
        text = re.sub(r"[•▪▸►◆○●]", ",", text)
        parts = re.split(r"[\n;/|]", text)
        skills = []
        for p in parts:
            c = p.strip().strip("-").strip("*").strip()
            if c and 1 < len(c) < 60:
                skills.append(c)
        seen = set()
        out = []
        for s in skills:
            key = s.lower()
            if key not in seen:
                seen.add(key)
                out.append(s)
        return out