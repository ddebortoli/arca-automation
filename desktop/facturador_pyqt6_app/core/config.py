"""Configuration persistence for the desktop app.

The UI stores settings in `~/.facturador/.env` and certificates in
`~/.facturador/certs/`.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values, set_key
from pydantic import BaseModel, Field

from core.paths import get_certs_dir, get_data_dir, get_env_file
from src.paths import get_default_sqlite_path

CONFIG_DIR = get_data_dir()
ENV_FILE = get_env_file()
CERTS_DIR = get_certs_dir()

CONFIG_EXPORT_SCHEMA_VERSION = 1
CONFIG_EXPORT_APP_NAME = "arca-automation"

_CONFIG_DEFAULTS: dict[str, str] = {
    "AFIP_CUIT": "",
    "MP_ACCESS_TOKEN": "",
    "MP_USER_ID": "",
    "APPROVAL_MODE": "auto",  # auto | telegram
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
    "AFIP_CERT_PATH": str(CERTS_DIR / "cert.crt"),
    "AFIP_KEY_PATH": str(CERTS_DIR / "private.key"),
    # WSFE (Factura C) defaults — consumed by backend via env vars.
    "AFIP_WSFE_PUNTO_DE_VENTA": "2",
    "AFIP_WSFE_TIPO_FACTURA": "11",
    "AFIP_WSFE_CONCEPTO": "2",
    "AFIP_WSFE_DOC_TIPO": "99",
    "AFIP_WSFE_DOC_NRO": "0",
    "AFIP_WSFE_CONDICION_IVA": "5",
    "AFIP_WSFE_INVOICE_TYPE_LABEL": "Factura C",
    "AFIP_WSFE_CONCEPT_LABEL": "Servicios",
    "AFIP_WSFE_RECEIVER_LABEL": "Consumidor Final",
    # Must be one of bootstrap accepted values: stdio | logfire | sentry.
    "OBSERVABILITY_BACKEND": "stdio",
    "LOGFIRE_TOKEN": "",
    # Database
    "DATABASE_BACKEND": "sqlite",  # sqlite | postgres
    "DATABASE_PATH": "",
    "DATABASE_URL": "",
    # UI-only preference (not consumed by the backend pipeline).
    "THEME": "light",
}


class ConfigExportBundle(BaseModel):
    """Serialized desktop configuration for export/import."""

    schema_version: int = CONFIG_EXPORT_SCHEMA_VERSION
    exported_at: str
    app: str = CONFIG_EXPORT_APP_NAME
    settings: dict[str, str]
    certificates: dict[str, str] = Field(default_factory=dict)


def ensure_dirs() -> None:
    """Create config/certs directories and ensure env file exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    ENV_FILE.touch(exist_ok=True)


def load_config() -> dict[str, str]:
    """Load `.env` content and provide defaults for required keys."""
    ensure_dirs()
    defaults = dict(_CONFIG_DEFAULTS)
    defaults["AFIP_CERT_PATH"] = str(CERTS_DIR / "cert.crt")
    defaults["AFIP_KEY_PATH"] = str(CERTS_DIR / "private.key")
    saved = dotenv_values(str(ENV_FILE))
    normalized_saved: dict[str, str] = {k: "" if v is None else str(v) for k, v in saved.items()}
    return {**defaults, **normalized_saved}


def save_config(data: dict[str, str]) -> None:
    """Persist key/value pairs into the `.env` file."""
    ensure_dirs()
    for key, value in data.items():
        set_key(str(ENV_FILE), key, value or "")


def merge_imported_settings(
    current: dict[str, str],
    imported: dict[str, str],
) -> dict[str, str]:
    """Replace settings, keeping current values when imported ones are empty."""
    merged = dict(current)
    for key, value in imported.items():
        if key not in _CONFIG_DEFAULTS and key not in current:
            continue
        if str(value).strip():
            merged[key] = str(value).strip()
    return merged


def export_config(*, include_certificates: bool = True) -> ConfigExportBundle:
    """Build an export bundle from the current desktop configuration."""
    cfg = load_config()
    settings = {key: cfg.get(key, default) for key, default in _CONFIG_DEFAULTS.items()}

    certificates: dict[str, str] = {}
    if include_certificates:
        cert_path = Path(cfg.get("AFIP_CERT_PATH", ""))
        key_path = Path(cfg.get("AFIP_KEY_PATH", ""))
        if cert_path.exists():
            certificates["cert_pem"] = cert_path.read_text(encoding="utf-8")
        if key_path.exists():
            certificates["key_pem"] = key_path.read_text(encoding="utf-8")

    return ConfigExportBundle(
        exported_at=datetime.now(timezone.utc).isoformat(),
        settings=settings,
        certificates=certificates,
    )


def export_config_json(*, include_certificates: bool = True) -> str:
    """Serialize the current configuration to JSON."""
    bundle = export_config(include_certificates=include_certificates)
    return bundle.model_dump_json(indent=2)


def import_config_bundle(bundle: ConfigExportBundle) -> dict[str, str]:
    """Import settings and optional certificates from an export bundle."""
    current = load_config()
    merged = merge_imported_settings(current, bundle.settings)
    save_config(merged)

    if bundle.certificates.get("cert_pem", "").strip():
        cert_dest = CERTS_DIR / "cert.crt"
        cert_dest.write_text(bundle.certificates["cert_pem"], encoding="utf-8")
        merged["AFIP_CERT_PATH"] = str(cert_dest)
        set_key(str(ENV_FILE), "AFIP_CERT_PATH", str(cert_dest))

    if bundle.certificates.get("key_pem", "").strip():
        key_dest = CERTS_DIR / "private.key"
        key_dest.write_text(bundle.certificates["key_pem"], encoding="utf-8")
        merged["AFIP_KEY_PATH"] = str(key_dest)
        set_key(str(ENV_FILE), "AFIP_KEY_PATH", str(key_dest))

    return merged


def import_config_json(raw_json: str) -> dict[str, str]:
    """Parse and import configuration from JSON."""
    bundle = ConfigExportBundle.model_validate_json(raw_json)
    if bundle.schema_version != CONFIG_EXPORT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported config schema version: {bundle.schema_version}")
    return import_config_bundle(bundle)


def cert_exists(path: str) -> bool:
    """Check if an uploaded certificate/key file exists."""
    return bool(path) and Path(path).exists()


def import_cert_file(src_path: str, dest_name: str) -> str:
    """Copy a local file into our certs directory."""
    ensure_dirs()
    dest = CERTS_DIR / dest_name
    shutil.copy2(src_path, dest)
    return str(dest)


def get_certs_status(config: dict[str, str]) -> dict[str, bool]:
    """Return whether key and cert exist for AFIP signing."""
    return {
        "key": cert_exists(config.get("AFIP_KEY_PATH", "")),
        "cert": cert_exists(config.get("AFIP_CERT_PATH", "")),
    }


def get_default_database_path() -> str:
    """Return the default SQLite database path as a string."""
    return str(get_default_sqlite_path())
