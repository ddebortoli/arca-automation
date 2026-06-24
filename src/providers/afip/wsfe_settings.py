"""Shared WSFE (Facturación Electrónica) settings with ENV overrides.

Important: values must be read at *runtime*, because the backend loads `.env`
after module imports (via `load_dotenv()` / `ARC_ENV_FILE`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_PUNTO_DE_VENTA = 2
_DEFAULT_TIPO_FACTURA = 11  # Factura C
_DEFAULT_CONCEPTO = 2  # Servicios
_DEFAULT_DOC_TIPO = 99  # Consumidor Final
_DEFAULT_DOC_NRO = 0
_DEFAULT_CONDICION_IVA = 5  # Consumidor Final

_DEFAULT_INVOICE_TYPE_LABEL = "Factura C"
_DEFAULT_CONCEPT_LABEL = "Servicios"
_DEFAULT_RECEIVER_LABEL = "Consumidor Final"


@dataclass(frozen=True, slots=True)
class WsfeSettings:
    punto_de_venta: int
    tipo_factura: int
    concepto: int
    doc_tipo: int
    doc_nro: int
    condicion_iva: int
    invoice_type_label: str
    concept_label: str
    receiver_label: str


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _get_str_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def load_wsfe_settings() -> WsfeSettings:
    """Load WSFE settings from environment variables (with defaults)."""
    return WsfeSettings(
        punto_de_venta=_get_int_env("AFIP_WSFE_PUNTO_DE_VENTA", _DEFAULT_PUNTO_DE_VENTA),
        tipo_factura=_get_int_env("AFIP_WSFE_TIPO_FACTURA", _DEFAULT_TIPO_FACTURA),
        concepto=_get_int_env("AFIP_WSFE_CONCEPTO", _DEFAULT_CONCEPTO),
        doc_tipo=_get_int_env("AFIP_WSFE_DOC_TIPO", _DEFAULT_DOC_TIPO),
        doc_nro=_get_int_env("AFIP_WSFE_DOC_NRO", _DEFAULT_DOC_NRO),
        condicion_iva=_get_int_env("AFIP_WSFE_CONDICION_IVA", _DEFAULT_CONDICION_IVA),
        invoice_type_label=_get_str_env(
            "AFIP_WSFE_INVOICE_TYPE_LABEL",
            _DEFAULT_INVOICE_TYPE_LABEL,
        ),
        concept_label=_get_str_env("AFIP_WSFE_CONCEPT_LABEL", _DEFAULT_CONCEPT_LABEL),
        receiver_label=_get_str_env("AFIP_WSFE_RECEIVER_LABEL", _DEFAULT_RECEIVER_LABEL),
    )
