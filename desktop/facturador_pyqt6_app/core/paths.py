"""Path helpers for the desktop app (dev and frozen bundles)."""

from __future__ import annotations

import sys
from pathlib import Path

from src.paths import get_certs_dir, get_data_dir, get_default_sqlite_path, get_env_file


def get_bundle_root() -> Path:
    """Return the directory containing bundled read-only assets."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[3]


def get_docs_dir() -> Path:
    """Return the directory containing bundled PDF guides."""
    return get_bundle_root() / "docs"


__all__ = [
    "get_bundle_root",
    "get_certs_dir",
    "get_data_dir",
    "get_default_sqlite_path",
    "get_docs_dir",
    "get_env_file",
]
