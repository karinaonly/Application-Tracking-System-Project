"""Experience-section parsing.

Handles role/company headers, date lines, wrapped company names from
two-column PDFs, bullet continuations, and left-column label leakage.
"""
import re

from app.parser.sections.common import (
    ACTION_RE,
    BULLET_RE,
    clean_company,
    is_date_only,
    is_label,
    split_role_at_company,
    strip_date,
)


class ExperienceParser:
    def parse(self, text: str) -> list[dict]:
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
                    current["title"], extra = split_role_at_company(current["company"])
                    if extra:
                        current["company"] = extra

                # Scrub label leakage from every text field
                current["company"] = clean_company(current.get("company", ""))
                current["meta"] = clean_company(current.get("meta", ""))
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
                subtitle = clean_company(subtitle)
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
            if is_label(line):
                pending_label = line
                if current and not current.get("_label"):
                    current["_label"] = line
                continue

            # --- pure date line (left column) ---
            if is_date_only(line):
                # A15: "Title at Company" followed by its date line is one
                # entry — attach the date instead of flushing the title away.
                if (
                    current
                    and not current["dates"]
                    and not current["bullets"]
                    and (current["title"] or current["company"])
                ):
                    current["dates"] = line.strip()
                    continue
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

            is_bullet = bool(BULLET_RE.match(line))
            dates_in_line, rest = strip_date(line)
            rest = rest.strip()

            # --- header candidate ---
            looks_header = (
                not is_bullet
                and not ACTION_RE.match(line)
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
                        role, co = split_role_at_company(rest)
                        if not current["title"]:
                            current["title"] = role[:100]
                            if co and not current["company"]:
                                current["company"] = co
                        elif not current["company"]:
                            current["company"] = rest
                    continue

            # --- bullet ---
            if current and is_bullet:
                current["bullets"].append(BULLET_RE.sub("", line).strip())
                continue

            # --- meta / continuation ---
            if current and line:
                cleaned = BULLET_RE.sub("", line).strip()
                if is_label(cleaned):
                    current["_label"] = cleaned
                    continue

                # A15: a left-column label merged into the line by the PDF
                # extractor ("Internship Technology Solutions") is not content.
                cleaned = re.sub(
                    r"^(?:Internship|Capstone|Academic|Freelance|College|University|School)\s+",
                    "",
                    cleaned,
                    flags=re.I,
                )
                if not cleaned:
                    continue

                if not current["title"]:
                    role, co = split_role_at_company(cleaned)
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

                # A15: long company names wrap onto the next line in
                # two-column PDFs — merge a short non-meta line into the name.
                if (
                    not current["meta"]
                    and not current["bullets"]
                    and len(current["company"]) < 60
                    and not re.search(
                        r"\d|\b(?:full[- ]?time|part[- ]?time|contract|remote|hybrid|onsite|hour)\b",
                        cleaned,
                        re.I,
                    )
                    and not re.match(r"^[A-Z][\w.\s'-]*,\s*[A-Z]", cleaned)
                ):
                    current["company"] = f"{current['company']} {cleaned}"
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
