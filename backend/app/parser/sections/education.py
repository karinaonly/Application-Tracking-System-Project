"""Education-section parsing.

School/degree classification is anchored on hints rather than position, so
both school-first and degree-first layouts work, and left-column label
leakage is cleaned before classification.
"""
import re

from app.parser.sections.common import (
    clean_degree,
    is_date_only,
    is_label,
    strip_date,
)

SCHOOL_HINT_RE = re.compile(
    r"\b(University|College|Campus|Institute|School|Academy)\b", re.I
)
DEGREE_HINT_RE = re.compile(
    r"\b(Bachelor|Master|Doctor|B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|"
    r"Ph\.?D\.?|Senior\s*High|Diploma|Certificate|Cum Laude|"
    r"Magna|Summa|Honor|Strand|GWA|GPA)\b",
    re.I,
)


class EducationParser:
    def parse(self, text: str) -> list[dict]:
        if not text or not text.strip():
            return []

        entries: list[dict] = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        current: dict | None = None

        def flush():
            nonlocal current
            if current:
                # If degree accidentally holds the school, swap
                if (
                    not current["school"]
                    and current["degree"]
                    and SCHOOL_HINT_RE.search(current["degree"])
                    and not DEGREE_HINT_RE.search(current["degree"])
                ):
                    current["school"] = current["degree"]
                    current["degree"] = ""

                # Scrub leftovers
                current["school"] = clean_degree(current.get("school", ""))
                current["degree"] = clean_degree(current.get("degree", ""))

                # Senior High special case
                if not current["degree"] and current.get("details"):
                    rebuilt = []
                    for d in current["details"]:
                        d2 = clean_degree(d)
                        if d2:
                            rebuilt.append(d2)
                    current["details"] = rebuilt

                entries.append(current)
            current = None

        for line in lines:
            if re.match(r"(?i)^references?\b", line):
                break
            if is_label(line):
                continue

            # F4: "Expected 2026" / "Graduating 2026" is the graduation date of
            # the entry being built — not the start of a new one (it used to
            # become a bogus entry with school "Expected").
            grad = re.match(r"(?i)^(?:expected(?:\s+graduation)?|graduating)\s+((?:19|20)\d{2})", line)
            if grad:
                if current and not current["dates"]:
                    current["dates"] = f"Expected {grad.group(1)}"
                continue

            if is_date_only(line):
                # A15: a bare date line after header lines belongs to them
                # (degree-first layout) instead of starting a new entry.
                if (
                    current
                    and not current["dates"]
                    and not current["details"]
                    and (current["school"] or current["degree"])
                ):
                    current["dates"] = line.strip()
                    continue
                flush()
                current = {
                    "dates": line.strip(),
                    "school": "",
                    "degree": "",
                    "details": [],
                }
                continue

            dates_in_line, rest = strip_date(line)
            rest = rest.strip()

            if dates_in_line and len(line) < 120:
                # A15: a dateless school/degree header followed by the dated
                # detail line is ONE entry — carry the header into the new
                # entry instead of splitting them apart.
                carried = ""
                carried_field = ""
                drop_prev = False
                if (
                    current
                    and not current["dates"]
                    and not current["details"]
                    and bool(current["school"]) != bool(current["degree"])
                ):
                    if current["school"]:
                        carried, carried_field = current["school"], "school"
                    else:
                        carried, carried_field = current["degree"], "degree"
                    drop_prev = True

                if drop_prev:
                    current = None  # discard the header-only entry
                else:
                    flush()

                current = {
                    "dates": dates_in_line,
                    "school": "",
                    "degree": "",
                    "details": [],
                }
                if carried:
                    if carried_field == "school" and not current["school"]:
                        current["school"] = carried
                    elif carried_field == "degree" and not current["degree"]:
                        current["degree"] = carried
                if rest:
                    if SCHOOL_HINT_RE.search(rest) and not DEGREE_HINT_RE.search(rest):
                        current["school"] = rest
                    elif DEGREE_HINT_RE.search(rest) and not SCHOOL_HINT_RE.search(rest):
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

            # A15: a second school line means a new entry, not leftover details
            if SCHOOL_HINT_RE.search(line) and current["school"] and current["degree"]:
                flush()
                current = {
                    "dates": "",
                    "school": "",
                    "degree": "",
                    "details": [],
                }

            # F4: a left-column label glued to the degree line ("College
            # Bachelor of Science in Information Technology") hides the degree
            # behind a school hint — the word "College" made the whole line
            # classify as school, swapping school and degree. Strip the label
            # when the remainder is clearly the degree.
            label_m = re.match(
                r"(?i)^(?:College|Senior\s*High(?:\s*School)?|University|Institute|Internship|Capstone|Academic)\s+(.+)$",
                line,
            )
            if (
                label_m
                and DEGREE_HINT_RE.search(label_m.group(1))
                and not SCHOOL_HINT_RE.search(label_m.group(1))
            ):
                line = label_m.group(1)

            # classify the line
            if re.match(r"(?i)^senior\s*high", line) or (
                DEGREE_HINT_RE.search(line) and re.search(r"(?i)strand|honor|cum laude|gpa|gwa", line)
            ):
                if not current["degree"]:
                    current["degree"] = line
                    continue

            if not current["school"] and SCHOOL_HINT_RE.search(line):
                current["school"] = line
            elif not current["degree"] and DEGREE_HINT_RE.search(line):
                current["degree"] = line
            elif not current["school"] and len(line) < 80:
                current["school"] = line
            elif not current["degree"] and len(line) < 100:
                current["degree"] = line
            else:
                current["details"].append(line)

        flush()
        return entries
