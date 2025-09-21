"""Sync dashboard data files into docs/data/ for GitHub Pages.

Usage::

    source .venv/bin/activate  # optional if you want the virtualenv
    python scripts/sync_docs_data.py

Copies the JSON artifacts from ``data/`` into ``docs/data/`` while preserving
filenames. Creates ``docs/data`` if it does not exist. Prints a short summary
of the copied files so you can confirm the update before committing.
"""

from __future__ import annotations

import shutil
from pathlib import Path


SOURCE_DIR = Path("data")
TARGET_DIR = Path("docs/data")
FILES = [
    "content_plan.json",
    "post_queue.json",
    "voice_profile.json",
    "last_schedule.json",
]


def main() -> None:
    if not SOURCE_DIR.exists():
        raise SystemExit("data/ directory not found; run this from project root.")

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for filename in FILES:
        src = SOURCE_DIR / filename
        dst = TARGET_DIR / filename
        if not src.exists():
            print(f"[skip] {src} missing")
            continue
        shutil.copy2(src, dst)
        copied.append(filename)
        print(f"[sync] {src} -> {dst}")

    if not copied:
        raise SystemExit("No files copied. Ensure data/*.json exist.")

    print("\nDone. Remember to commit docs/data/* before pushing Pages updates.")


if __name__ == "__main__":
    main()
