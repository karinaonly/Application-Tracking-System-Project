"""Turn raw resume text into named sections.

The splitter only decides *where* sections begin and end. Interpreting each
section's content is the job of the sibling parser modules, which keeps this
state machine small enough to test directly.
"""
import re

from app.common.constants import SECTION_PATTERNS
from app.parser.sections.common import (
    INLINE_HEADER_RE,
    is_skipped_header,
    strip_references,
)


class SectionSplitter:
    def split(self, raw_text: str) -> tuple[dict, list[str]]:
        lines = raw_text.splitlines()
        sections: dict = {}
        current_sec = None
        current_body: list[str] = []
        sec_order: list[str] = []
        prev_blank = True
        skipping = False  # F4: set after a skipped header; orphan lines are dropped

        for line in lines:
            line_str = line.strip()
            if not line_str:
                if current_sec:
                    current_body.append("")
                prev_blank = True
                continue

            detected = self._detect_sec(line_str)
            inline_rest = ""
            if not detected:
                # A15: "Skills: Python, React" — the label is the header, the
                # remainder is the section's first body line. Only trust it
                # when it looks like a header, not like a labeled content line
                # inside a section (e.g. "Languages: JavaScript" under SKILLS):
                # the label must be ALL-CAPS, or the line must start a block.
                m = INLINE_HEADER_RE.match(line_str)
                if m:
                    label = m.group("label").strip()
                    cand = self._detect_sec(label)
                    if cand and cand != "contact" and (label.isupper() or prev_blank):
                        detected = cand
                        inline_rest = m.group("rest").strip()

            # Skip REFERENCES and involvement-type headers entirely (ATS best
            # practice; F4: org/activities content must not leak into other
            # sections). Lines that follow are dropped until the next real
            # header instead of polluting the contact block.
            if detected == "references" or is_skipped_header(line_str):
                if current_sec and current_body:
                    sections[current_sec] = {"raw": "\n".join(current_body).strip()}
                current_sec = None
                current_body = []
                skipping = True
                prev_blank = False
                continue

            if detected:
                skipping = False
                if current_sec:
                    raw = strip_references("\n".join(current_body).strip())
                    sections[current_sec] = {"raw": raw}
                current_sec = detected
                current_body = [inline_rest] if inline_rest else []
                sec_order.append(detected)
                prev_blank = False
            else:
                if current_sec:
                    current_body.append(line_str)
                elif skipping:
                    continue  # F4: orphan line after a skipped header — drop it
                else:
                    if "contact" not in sections:
                        sections["contact"] = {"raw": ""}
                        sec_order.insert(0, "contact")
                    sections["contact"]["raw"] += line_str + "\n"
                prev_blank = False

        if current_sec and current_body:
            raw = strip_references("\n".join(current_body).strip())
            sections[current_sec] = {"raw": raw}

        for key in list(sections.keys()):
            if key.startswith("_") or not isinstance(sections.get(key), dict):
                continue
            if "raw" in sections[key] and sections[key]["raw"]:
                sections[key]["raw"] = strip_references(sections[key]["raw"])

        return sections, sec_order

    def _detect_sec(self, line: str) -> str | None:
        cleaned = re.sub(r"[:\-_=|#*•]+", "", line).strip()
        if len(cleaned.split()) > 6:
            return None
        for name, pat in SECTION_PATTERNS.items():
            if re.match(pat, cleaned):
                return name
        return None
