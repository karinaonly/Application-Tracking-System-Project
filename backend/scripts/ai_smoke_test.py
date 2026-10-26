"""Live AI smoke test (not part of the unit suite).

Run from backend/:

    python scripts/ai_smoke_test.py

Makes exactly one real rewrite request. Exit code 0 means the configured
provider produced a real rewrite; 1 means the code fell back locally.
The API key is never printed in full.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analyzer.ai_config import resolve_ai_config
from app.analyzer.ai_rewriter import AIRewriter
from app.config.settings import get_settings

BULLET = "Worked on backend features using Python"


def _mask(key: str) -> str:
    if len(key) <= 4:
        return "***"
    return key[:4] + "..."


def main() -> int:
    settings = get_settings()
    config = resolve_ai_config(settings)

    print(f"provider: {config.provider}")
    print(f"model: {config.model}")
    print(f"reason: {config.reason}")
    print(f"api_key: {_mask(config.api_key)}")

    result = AIRewriter().rewrite_bullets([BULLET]).get(BULLET)
    if result is None:
        print("result: missing from rewrite output")
        return 1

    print(f"source: {result.get('source')}")
    print(f"guard status: {(result.get('guard') or {}).get('status')}")
    print(f"moderate: {result.get('moderate')}")

    return 1 if result.get("source") == "fallback" else 0


if __name__ == "__main__":
    sys.exit(main())
