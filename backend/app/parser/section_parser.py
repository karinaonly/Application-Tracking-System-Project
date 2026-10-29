"""Resume section parser.

`SectionParser` is the stable entry point used by the resume service. It
delegates the actual work to the focused parsers in `app.parser.sections`:

- `SectionSplitter` — raw text -> named section blocks and their order
- `ContactParser` — name, title, email, phone, links, location
- `ExperienceParser` — roles, companies, dates, bullets
- `ProjectsParser` — project titles, subtitles, dates, bullets
- `EducationParser` — school, degree, dates, details
- `SkillsParser` — de-duplicated skill tokens

The underscore-prefixed methods below are kept for compatibility with existing
callers/tests; new code should use the section classes directly.
"""
from app.parser.sections import (
    ContactParser,
    EducationParser,
    ExperienceParser,
    ProjectsParser,
    SectionSplitter,
    SkillsParser,
)
from app.parser.sections.common import (
    clean_company,
    clean_degree,
    is_date_only,
    is_label,
    split_role_at_company,
    strip_date,
)


class SectionParser:
    def __init__(self):
        self._splitter = SectionSplitter()
        self._contact = ContactParser()
        self._experience = ExperienceParser()
        self._projects = ProjectsParser()
        self._education = EducationParser()
        self._skills = SkillsParser()

    def parse(self, raw_text: str) -> dict:
        sections, sec_order = self._splitter.split(raw_text)
        sections["_section_order"] = sec_order
        sections["contact_parsed"] = self._contact.parse(
            sections.get("contact", {}).get("raw", "")
        )
        sections["experience_parsed"] = self._experience.parse(
            sections.get("experience", {}).get("raw", "")
        )
        sections["projects_parsed"] = self._projects.parse(
            sections.get("projects", {}).get("raw", "")
        )
        sections["education_parsed"] = self._education.parse(
            sections.get("education", {}).get("raw", "")
        )
        sections["skills_parsed"] = self._skills.parse(
            sections.get("skills", {}).get("raw", "")
        )
        return sections

    # ── compatibility delegates ───────────────────────────────────────────
    def _parse_contact(self, text: str) -> dict:
        return self._contact.parse(text)

    def _parse_experience(self, text: str) -> list[dict]:
        return self._experience.parse(text)

    def _parse_projects(self, text: str) -> list[dict]:
        return self._projects.parse(text)

    def _parse_education(self, text: str) -> list[dict]:
        return self._education.parse(text)

    def _parse_skills(self, text: str) -> list[str]:
        return self._skills.parse(text)

    def _clean_company(self, text: str) -> str:
        return clean_company(text)

    def _clean_degree(self, text: str) -> str:
        return clean_degree(text)

    def _is_label(self, line: str) -> bool:
        return is_label(line)

    def _is_date_only(self, line: str) -> bool:
        return is_date_only(line)

    def _strip_date(self, line: str) -> tuple[str, str]:
        return strip_date(line)

    def _split_role_at_company(self, text: str) -> tuple[str, str]:
        return split_role_at_company(text)
