"""Configuration persistence for the desktop app.

The UI stores settings in `~/.facturador/.env` and certificates in
`~/.facturador/certs/`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from dotenv import dotenv_values, set_key


CONFIG_DIR = Path.home() / ".facturador"
ENV_FILE = CONFIG_DIR / ".env"
CERTS_DIR = CONFIG_DIR / "certs"


def ensure_dirs() -> None:
    """Create config/certs directories and ensure env file exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    ENV_FILE.touch(exist_ok=True)


def load_config() -> dict[str, str]:
    """Load `.env` content and provide defaults for required keys."""
    ensure_dirs()
    defaults: dict[str, str] = {
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
        # UI-only preference (not consumed by the backend pipeline).
        "THEME": "light",
    }
    saved = dotenv_values(str(ENV_FILE))
    normalized_saved: dict[str, str] = {
        k: "" if v is None else str(v) for k, v in saved.items()
    }
    return {**defaults, **normalized_saved}


def save_config(data: dict[str, str]) -> None:
    """Persist key/value pairs into the `.env` file."""
    ensure_dirs()
    for key, value in data.items():
        set_key(str(ENV_FILE), key, value or "")


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

