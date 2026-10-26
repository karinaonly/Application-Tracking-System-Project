from dataclasses import dataclass

PLACEHOLDER_KEY = "sk-placeholder"
MIN_KEY_LENGTH = 20

PREFIX_PROVIDERS = (
    ("sk-", "openai"),
    ("gsk_", "groq"),
    ("gsk-", "groq"),
    ("AIza", "gemini"),
)


@dataclass(frozen=True)
class AIConfig:
    provider: str
    configured: bool
    reason: str
    api_key: str
    base_url: str
    model: str


def _resolve_provider(requested_provider: str, api_key: str) -> str:
    """Return the provider name to use. "auto" is kept when no prefix matches."""
    if requested_provider != "auto":
        return requested_provider
    for prefix, provider in PREFIX_PROVIDERS:
        if api_key.startswith(prefix):
            return provider
    return "auto"


def resolve_ai_config(settings) -> AIConfig:
    """Single source of truth for whether AI rewriting is configured.

    Validation is shape-based (length + no whitespace); the key prefix is only
    used to infer a provider when ``ai_provider`` is "auto".
    """
    api_key = (getattr(settings, "groq_api_key", "") or "").strip()
    requested_provider = (
        (getattr(settings, "ai_provider", "") or "").strip().lower() or "auto"
    )
    model = settings.ai_model
    provider = _resolve_provider(requested_provider, api_key)
    if provider == "groq":
        base_url = settings.ai_base_url
    elif provider == "gemini":
        base_url = settings.gemini_base_url
    else:
        base_url = ""

    if not api_key or api_key == PLACEHOLDER_KEY:
        reason = "missing"
    elif any(char.isspace() for char in api_key) or len(api_key) < MIN_KEY_LENGTH:
        reason = "invalid_format"
    elif requested_provider == "auto" and provider == "auto":
        reason = "invalid_format"
    else:
        reason = "configured"

    return AIConfig(
        provider=provider,
        configured=reason == "configured",
        reason=reason,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
