#!/usr/bin/env python3
"""Create a runnable copy of the current ATS Resume Fixer project.

Run from anywhere:
    python backend/setup_project.py --destination ./ats-resume-fixer-copy

The script copies the source files that are currently in this repository. It
does not copy local secrets, installed dependencies, databases, or uploads.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "__pycache__",
    "uploads",
}
EXCLUDED_FILES = {
    ".env",
    "ats_resume_fixer.db",
}


def should_copy(path: Path) -> bool:
    return not any(part in EXCLUDED_DIRECTORIES for part in path.parts) and path.name not in EXCLUDED_FILES


def copy_project(source_root: Path, destination: Path) -> int:
    copied = 0
    for source in source_root.rglob("*"):
        relative = source.relative_to(source_root)
        if not should_copy(relative):
            continue

        target = destination / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        print(f"  [+] Copied: {relative}")
        copied += 1

    (destination / "backend" / "uploads").mkdir(parents=True, exist_ok=True)
    (destination / "backend" / "uploads" / ".gitkeep").touch()
    return copied


def write_env_template(destination: Path) -> None:
    env_template = destination / "backend" / ".env.example"
    if env_template.exists():
        return

    env_template.write_text(
        """DATABASE_URL=sqlite:///./ats_resume_fixer.db
GROQ_API_KEY=your-groq-api-key-here
AI_PROVIDER=auto
AI_MODEL=gemini-2.0-flash
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
JWT_SECRET=change-this-for-local-use-only
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=43200
ENVIRONMENT=development
UPLOAD_DIR=./uploads
""",
        encoding="utf-8",
    )
    print("  [+] Created: backend/.env.example")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("ats-resume-fixer-copy"),
        help="Folder to create (default: ./ats-resume-fixer-copy)",
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    source_root = script_path.parent.parent
    destination = args.destination.expanduser().resolve()

    if destination == source_root:
        raise SystemExit("Destination must be different from the current project root.")

    print("\n" + "=" * 60)
    print("ATS RESUME FIXER - CURRENT PROJECT BOOTSTRAP")
    print("=" * 60)
    print(f"Source:      {source_root}")
    print(f"Destination: {destination}\n")

    destination.mkdir(parents=True, exist_ok=True)
    copied = copy_project(source_root, destination)
    write_env_template(destination)

    print("\nProject copy completed.")
    print(f"Files copied: {copied}")
    print("Next steps:")
    print("  1. Copy backend/.env.example to backend/.env and add your values.")
    print("  2. Install backend dependencies in backend/venv.")
    print("  3. Run: uvicorn app.main:app --reload --port 8000")
    print("  4. In frontend, install dependencies and run: npm run dev")


if __name__ == "__main__":
    main()
