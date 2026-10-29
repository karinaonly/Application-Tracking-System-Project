"""Projects-section parsing.

Projects share the experience shape (title / subtitle / dates / bullets) but
titles wrap differently and continuation lines are detected heuristically.
"""
import re

from app.parser.sections.common import (
    ACTION_RE,
    BULLET_RE,
    is_date_only,
    is_label,
    strip_date,
)


class ProjectsParser:
    def parse(self, text: str) -> list[dict]:
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

            if is_label(line):
                pending_label = line
                continue

            if is_date_only(line):
                # F4: a bare date line after a title line belongs to that
                # entry (mirrors the A15 education fix) — flushing here used
                # to split every "Title\nDates\n- bullet" project in two,
                # leaving the first entry dateless and bulletless.
                if (
                    current
                    and current.get("title")
                    and not current.get("dates")
                    and not current.get("bullets")
                    and not current.get("subtitle")
                ):
                    current["dates"] = line.strip()
                    continue
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

            is_bullet = bool(BULLET_RE.match(line))
            dates_in_line, rest = strip_date(line)
            rest = rest.strip()

            is_real_title = (
                not is_bullet
                and not ACTION_RE.match(line)
                and not is_continuation(line)
                and not is_label(line)
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
                current["bullets"].append(BULLET_RE.sub("", line).strip())
                continue

            if current and line:
                cleaned = BULLET_RE.sub("", line).strip()
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
