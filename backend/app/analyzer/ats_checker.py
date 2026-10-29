import re


_CONTACT_LINE_RE = re.compile(r"@|(?:https?://|www\.)|(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)", re.I)
_NON_I_PRONOUN_RE = re.compile(r"\b(?:me|my|mine|myself)\b", re.I)
_I_PRONOUN_RE = re.compile(r"\bI(?:'m|'ve|'ll|'d)\b|(?<![A-Za-z0-9_])I(?=\s+[a-z][a-z'-]*\b)")
_SAFE_FILENAME_RE = re.compile(r"[A-Za-z0-9._-]+")


class ATSCompatibilityChecker:
    def _pronoun_matches(self, raw_text: str, sections: dict) -> tuple[int, list[str]]:
        contact_raw = sections.get("contact", {}).get("raw", "")
        contact_lines = {line.strip() for line in contact_raw.splitlines() if line.strip()}
        count = 0
        examples = []

        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped in contact_lines or _CONTACT_LINE_RE.search(stripped):
                continue
            hits = _NON_I_PRONOUN_RE.findall(stripped)
            hits.extend(_I_PRONOUN_RE.findall(stripped))
            if hits:
                count += len(hits)
                if len(examples) < 3:
                    examples.append(stripped[:80])

        return count, examples

    def check(self, raw_text: str, sections: dict, metadata: dict, filename: str = "") -> dict:
        issues = []
        passed = []

        # Tables check
        if metadata.get("has_tables"):
            issues.append({"category": "critical", "issue": "Tables detected", "fix": "Remove all tables. Use simple standard text alignment."})
        else:
            passed.append("No ATS-breaking tables detected")

        # Headers check
        if metadata.get("has_headers") or metadata.get("has_footers"):
            issues.append({"category": "critical", "issue": "Content in header/footer", "fix": "Move all contact details into the main body."})
        else:
            passed.append("Document headers/footers clean")

        # Contact check
        c = sections.get("contact_parsed", {})
        missing = [k for k in ["email", "phone", "name"] if not c.get(k)]
        if missing:
            issues.append({"category": "critical", "issue": f"Missing contact fields: {', '.join(missing)}", "fix": f"Add {', '.join(missing)} at the top."})
        else:
            passed.append("Essential contact info present")

        # Standard Sections check
        order = set(sections.get("_section_order", []))
        for req in ["experience", "education", "skills"]:
            if req not in order:
                issues.append({"category": "warning", "issue": f"Missing section: '{req.title()}'", "fix": f"Include a standard '{req.title()}' section."})
            else:
                passed.append(f"'{req.title()}' section detected")

        # B9: layout checks that used to be DOCX-only or absent.
        image_count = metadata.get("image_count") or (1 if metadata.get("has_images") else 0)
        if image_count:
            issues.append({
                "category": "warning",
                "issue": f"Images/icons detected ({image_count})",
                "fix": "Keep contact details, skills, and dates as real text — ATS cannot read text inside images.",
            })
        else:
            passed.append("No images/icons detected")

        if metadata.get("has_multi_column"):
            issues.append({
                "category": "critical",
                "issue": "Multi-column layout detected",
                "fix": "Use a single-column layout so ATS reads sections in the intended order.",
            })
        else:
            passed.append("Single-column layout")

        if metadata.get("has_icon_font"):
            issues.append({
                "category": "warning",
                "issue": "Icon font detected",
                "fix": "Replace icon fonts with plain text labels (email, phone, location).",
            })
        elif (metadata.get("font_count") or 0) > 2:
            issues.append({
                "category": "warning",
                "issue": f"Multiple fonts detected ({metadata['font_count']})",
                "fix": "Use one or two standard fonts such as Calibri or Arial.",
            })
        else:
            passed.append("Standard font usage")

        # B9: dates are how ATS and recruiters judge tenure.
        experience = sections.get("experience_parsed", []) or []
        undated = [entry for entry in experience if not str(entry.get("dates") or "").strip()]
        if undated:
            noun = "entry" if len(undated) == 1 else "entries"
            issues.append({
                "category": "warning",
                "issue": f"{len(undated)} experience {noun} missing dates",
                "fix": "Add start/end dates (e.g. Jan 2024 – Present) to every role.",
            })
        elif experience:
            passed.append("Experience dates present")

        # B9: file naming. Only checked when the caller supplies the name.
        if filename:
            if _SAFE_FILENAME_RE.fullmatch(filename):
                passed.append("ATS-friendly file name")
            else:
                issues.append({
                    "category": "warning",
                    "issue": "File name uses spaces or special characters",
                    "fix": "Rename with letters, numbers, hyphens or underscores (e.g. jane-doe-resume.pdf).",
                })

        # Pronouns
        pronouns, pronoun_examples = self._pronoun_matches(raw_text, sections)
        if pronouns > 2:
            issues.append({"category": "warning", "issue": f"Personal pronouns detected ({pronouns}x)", "fix": "Remove first-person pronouns (I, me, my).", "examples": pronoun_examples})

        # Score deduction
        crit = sum(1 for i in issues if i["category"] == "critical")
        warn = sum(1 for i in issues if i["category"] == "warning")
        score = max(0, 100 - (crit * 20 + warn * 10))

        return {"score": score, "issues": issues, "passed": passed}
