import json
import logging
import re

from openai import OpenAI
from app.analyzer.ai_config import resolve_ai_config
from app.analyzer.claim_guard import check_rewrite, describe_violations
from app.config.settings import get_settings

# Hard cap on how many bullets go into a single rewrite request. Keeps the prompt/response
# small and the latency predictable. Bullets beyond this are left untouched (source="skipped_batch_limit"),
# not silently dropped.
MAX_BULLETS_PER_CALL = 8
MAX_GUARD_RETRIES = 1
logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I | re.M)

# Hyphen-like glyphs some fonts cannot render (tofu boxes in DOCX viewers).
_BAD_DASH_RE = re.compile(r"[\u2010\u2011\u2012\u2015\u2212\uFE58\uFE63\u00AD\uFFFD]")

def _normalize_glyphs(text: str) -> str:
    """Replace unrenderable dash glyphs with ASCII hyphens."""
    return _BAD_DASH_RE.sub("-", text)


def _unchanged(bullet: str, source: str, error: str | None = None, status: str = "skipped") -> dict:
    out = {
        "ai_output": bullet,
        "moderate": bullet,
        "aggressive": bullet,
        "keywords_used": [],
        "has_placeholder": False,
        "source": source,
        "guard": {"status": status, "reasons": [], "retried": False, "rejected_variants": []},
    }
    if error:
        out["error"] = error
    return out


def _strip_fences(content: str) -> str:
    return _FENCE_RE.sub("", content.strip()).strip()


class AIRewriter:
    def __init__(self):
        settings = get_settings()
        config = resolve_ai_config(settings)

        self.provider = config.provider
        self.model = config.model
        self._api_key = config.api_key
        self.client = None
        if config.configured:
            client_options = {
                "api_key": config.api_key,
                "timeout": settings.ai_timeout_seconds,
                "max_retries": 0,
            }
            if config.base_url:
                client_options["base_url"] = config.base_url
            self.client = OpenAI(**client_options)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def rewrite_bullet(self, bullet: str, target_role: str = "",
                        matched_keywords: list[str] | None = None,
                        missing_keywords: list[str] | None = None) -> dict:
        """Single-bullet convenience wrapper around rewrite_bullets."""
        return self.rewrite_bullets(
            [bullet], target_role, matched_keywords, missing_keywords
        ).get(bullet, _unchanged(bullet, "fallback"))

    def rewrite_bullets(self, bullets: list[str], target_role: str = "",
                         matched_keywords: list[str] | None = None,
                         missing_keywords: list[str] | None = None) -> dict[str, dict]:
        """
        Rewrite multiple resume bullets in ONE API call.

        Returns: {original_bullet_text: {ai_output, moderate, aggressive, keywords_used,
                                           has_placeholder, source, [error]}}
        Duplicate bullet text collapses to one entry (dict is keyed by text, same as before).
        Order and exact original text are preserved for every input bullet.
        """
        unique = list(dict.fromkeys(b for b in bullets if b and b.strip()))
        if not unique:
            return {}

        if not self.client:
            return {b: _unchanged(b, "fallback") for b in unique}

        to_send, skipped = unique[:MAX_BULLETS_PER_CALL], unique[MAX_BULLETS_PER_CALL:]
        result: dict[str, dict] = {b: _unchanged(b, "skipped_batch_limit") for b in skipped}

        prompt = self._build_prompt(to_send, target_role, matched_keywords or [], missing_keywords or [])
        first_results, first_error = self._call_model(prompt, to_send)
        if first_error:
            for bullet in to_send:
                result[bullet] = _unchanged(bullet, "fallback", first_error, status="ai_error")
            return result

        attempts: dict[str, list[dict]] = {}
        retry_failed: dict[str, str] = {}
        retried: set[str] = set()
        for bullet in to_send:
            item = first_results[bullet]
            if item.get("error"):
                result[bullet] = _unchanged(bullet, "fallback", item["error"], status="ai_error")
            else:
                attempts[bullet] = [item]

        for _ in range(MAX_GUARD_RETRIES):
            retry_bullets = [
                bullet for bullet in to_send
                if bullet in attempts and bullet not in retry_failed
                and self._failed_variants(bullet, attempts[bullet][-1])
            ]
            if not retry_bullets:
                break
            retry_prompt = self._build_prompt(
                retry_bullets, target_role, matched_keywords or [], missing_keywords or []
            )
            retry_prompt += "\n\nRejected previous rewrites:\n"
            for index, bullet in enumerate(retry_bullets, 1):
                retry_prompt += (
                    f"Your previous rewrite of bullet {index} was rejected because it "
                    f"{describe_violations(self._all_violations(bullet, attempts[bullet][-1]))}. Rewrite it again using only facts, tools, "
                    "numbers and wording already present in the original.\n"
                )
            retried.update(retry_bullets)
            retried_results, retry_error = self._call_model(retry_prompt, retry_bullets)
            if retry_error:
                for bullet in retry_bullets:
                    retry_failed[bullet] = retry_error
                continue
            for bullet in retry_bullets:
                item = retried_results[bullet]
                if item.get("error"):
                    retry_failed[bullet] = item["error"]
                else:
                    attempts[bullet].append(item)

        for bullet in to_send:
            if bullet in result and result[bullet]["guard"]["status"] == "ai_error":
                continue
            result[bullet] = self._finalize(bullet, attempts[bullet], bullet in retried, retry_failed.get(bullet))

        return result

    def _call_model(self, prompt: str, bullets: list[str]) -> tuple[dict[str, dict], str | None]:
        try:
            kwargs = dict(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            if self.provider == "openai":
                kwargs["response_format"] = {"type": "json_object"}
            res = self.client.chat.completions.create(**kwargs)
            content = (res.choices[0].message.content or "").strip()
            parsed = self._parse_json_array(content, expected_len=len(bullets))
            return {bullet: self._to_result(bullet, item) for bullet, item in zip(bullets, parsed)}, None
        except Exception as e:
            error = self._safe_error(e)
            logger.warning(
                "AI rewrite request failed (%s/%s): %s", self.provider, self.model, error
            )
            return {}, error

    def _safe_error(self, exc: Exception) -> str:
        """Return an actionable error string with any API key redacted."""
        message = str(exc)
        api_key = getattr(self, "_api_key", "")
        if api_key:
            message = message.replace(api_key, "***")
        lowered = message.lower()
        if "model_not_found" in lowered or (
            "model" in lowered and "does not exist" in lowered
        ):
            return f"model not found: {self.model} (check AI_MODEL)"
        return message

    def _variant_violations(self, original: str, item: dict) -> dict[str, list[tuple[str, list[str]]]]:
        return {
            "moderate": check_rewrite(original, item.get("moderate", "")),
            "aggressive": check_rewrite(original, item.get("aggressive", "")),
        }

    def _failed_variants(self, original: str, item: dict) -> list[str]:
        return [variant for variant, violations in self._variant_violations(original, item).items() if violations]

    def _all_violations(self, original: str, item: dict) -> list[tuple[str, list[str]]]:
        return [violation for violations in self._variant_violations(original, item).values() for violation in violations]

    def _finalize(self, original: str, attempts: list[dict], retried: bool, retry_error: str | None) -> dict:
        final = dict(attempts[-1])
        rejected = []
        reasons = []
        for variant in ("moderate", "aggressive"):
            passed_text = None
            for item in reversed(attempts):
                if not check_rewrite(original, item.get(variant, "")):
                    passed_text = item.get(variant, original)
                    break
            if passed_text is None:
                rejected.append(variant)
                latest = self._variant_violations(original, attempts[-1])[variant]
                reasons.extend(code for code, _ in latest)
                final[variant] = original
                logger.info("Rewrite variant withheld for bullet %r: %s", original[:60], [code for code, _ in latest])
            else:
                final[variant] = passed_text

        reasons = list(dict.fromkeys(reasons))
        if retry_error:
            status = "retry_failed"
        elif not rejected:
            status = "retried_passed" if retried else "passed"
        elif len(rejected) == 2:
            status = "rejected"
        else:
            status = "partially_rejected"
        final["ai_output"] = final["moderate"]
        final["has_placeholder"] = False
        final["source"] = "guard_rejected" if len(rejected) == 2 else self.provider
        final["guard"] = {
            "status": status,
            "reasons": reasons,
            "retried": retried,
            "rejected_variants": rejected,
        }
        if retry_error:
            final["error"] = retry_error
        return final

    # ------------------------------------------------------------------ #
    # Prompt construction
    # ------------------------------------------------------------------ #
    def _system_prompt(self) -> str:
        return (
            "You are a resume editor. You rewrite resume bullet points so they are ATS-friendly and "
            "impact-focused, while staying strictly truthful to what the candidate actually wrote.\n\n"
            "HARD RULES (never break these):\n"
            "1. NEVER invent a number, percentage, dollar amount, team size, user count, or any other "
            "metric that is not already present in the ORIGINAL bullet.\n"
            "2. NEVER add a tool, technology, responsibility, or achievement that is not stated or "
            "clearly implied by the ORIGINAL bullet.\n"
            "3. If the original bullet has no metric, rewrite it qualitatively. NEVER add a placeholder, "
            "bracketed value, guessed number, or any other text for the candidate to fill in.\n"
            "4. You may rephrase the original content using wording closer to the provided target "
            "keywords ONLY if the bullet already reflects that skill or activity. Do not use a keyword "
            "that has nothing to do with what the bullet describes.\n"
            "5. Keep every existing real number, name, and tool exactly as given; do not remove or "
            "round them.\n"
            "6. Start each bullet with a strong past-tense action verb. One sentence. No emojis, no "
            "trailing period is fine either way, but keep ATS-safe punctuation (no bullets/asterisks).\n"
            "7. Match normal sentence-case English capitalization. Keywords you're given may be written "
            "Title Case (e.g. 'Communication', 'Teamwork') purely for display purposes -- when you use one "
            "mid-sentence, write it in lowercase like any other English word ('clear communication', "
            "'strong teamwork'). Only keep capitalization for genuine proper nouns: technology, language, "
            "tool, and product names (React, Docker, GraphQL, Python, etc.).\n\n"
            "8. Do not use words like automated, pipeline, robust, guaranteed, production-ready, scalable, "
            "seamless, streamlined, accelerated, standardized, or vague magnitude adverbs unless the ORIGINAL "
            "bullet already says so; do not make the lead verb imply more seniority than the original (a builder "
            "must not become an architect, and a helper must not become a lead).\n\n"
            "Respond with ONLY a JSON array, no prose before or after, no markdown code fences. "
            "The array must have exactly one object per input bullet, in the same order as given. "
            "Each object: "
            '{"moderate": string, "aggressive": string, "keywords_used": string[], "has_placeholder": boolean}. '
            '"moderate" makes conservative wording changes; "aggressive" is punchier but follows the same '
            "hard rules above (aggressive wording is NOT license to add unverified claims)."
        )

    def _build_prompt(self, bullets: list[str], target_role: str,
                       matched_keywords: list[str], missing_keywords: list[str]) -> str:
        lines = []
        if target_role:
            lines.append(f"Target role: {target_role}")
        if missing_keywords:
            lines.append(
                "Keywords the target job wants that are NOT yet in the resume (use ONLY where truthful, "
                "per rule 4 above): " + ", ".join(missing_keywords[:20])
            )
        if matched_keywords:
            lines.append(
                "Keywords the resume already has (safe to reinforce in wording): "
                + ", ".join(matched_keywords[:20])
            )
        lines.append("\nBullets to rewrite, in order:")
        for i, b in enumerate(bullets, 1):
            lines.append(f"{i}. {b}")
        return "\n".join(lines)

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.5,
        max_tokens: int = 900,
    ) -> tuple[str | None, str | None]:
        """Generate plain text (D8: cover letters) with the shared client.

        Returns ``(text, error)``. The error is already redacted of the API key.
        """
        if not self.client:
            return None, "AI provider is not configured"

        try:
            res = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = (res.choices[0].message.content or "").strip()
            if not content:
                return None, "empty response from model"
            return content, None
        except Exception as e:
            error = self._safe_error(e)
            logger.warning(
                "AI text generation failed (%s/%s): %s", self.provider, self.model, error
            )
            return None, error

    # ------------------------------------------------------------------ #
    # Response parsing
    # ------------------------------------------------------------------ #
    def _parse_json_array(self, content: str, expected_len: int) -> list[dict]:
        cleaned = _strip_fences(content)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Some models wrap the array in an object like {"results": [...]}
            match = re.search(r"\[.*\]", cleaned, re.S)
            if not match:
                raise ValueError(f"Model did not return valid JSON: {cleaned[:200]!r}")
            data = json.loads(match.group(0))

        if isinstance(data, dict):
            # tolerate {"results": [...]} / {"bullets": [...]} shapes
            for key in ("results", "bullets", "items", "data"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break

        if not isinstance(data, list):
            raise ValueError("Model response was valid JSON but not a list")

        # Pad/truncate defensively so a slightly-off count doesn't crash the request;
        # missing entries fall back to "no change" for that specific bullet.
        if len(data) < expected_len:
            data = data + [{}] * (expected_len - len(data))
        return data[:expected_len]

    def _to_result(self, original_bullet: str, item: object) -> dict:
        if not isinstance(item, dict):
            return _unchanged(original_bullet, "fallback", error="malformed item in model response")

        moderate = str(item.get("moderate") or "").strip()
        aggressive = str(item.get("aggressive") or "").strip()
        # Some models emit U+2011 non-breaking hyphens and similar glyphs that
        # render as tofu boxes (□) in the exported DOCX — normalize to ASCII.
        moderate = _normalize_glyphs(moderate)
        aggressive = _normalize_glyphs(aggressive)
        keywords_used = item.get("keywords_used") or []
        if not isinstance(keywords_used, list):
            keywords_used = []
        if not moderate:
            return _unchanged(original_bullet, "fallback", error="empty rewrite from model")

        return {
            "ai_output": moderate,       # kept for docx_exporter._apply_rewrites compatibility
            "moderate": moderate,
            "aggressive": aggressive or moderate,
            "keywords_used": [str(k) for k in keywords_used],
            "has_placeholder": False,
            "source": self.provider,
        }
