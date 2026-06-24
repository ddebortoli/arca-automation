"""Filesystem paths for user data and runtime assets."""

from __future__ import annotations

from pathlib import Path

_DATA_DIR_NAME = ".facturador"


def get_data_dir() -> Path:
    """Return the per-user application data directory."""
    return Path.home() / _DATA_DIR_NAME


def get_env_file() -> Path:
    """Return the desktop-managed environment file path."""
    return get_data_dir() / ".env"


def get_certs_dir() -> Path:
    """Return the directory where AFIP certificates are stored."""
    return get_data_dir() / "certs"


def get_default_sqlite_path() -> Path:
    """Return the default SQLite database file path."""
    return get_data_dir() / "payments.db"


def resolve_sqlite_path(path_str: str | None) -> Path:
    """Resolve a SQLite path, falling back to the default user-data location."""
    if path_str and path_str.strip():
        return Path(path_str).expanduser()
    return get_default_sqlite_path()
