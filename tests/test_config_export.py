"""Tests for desktop configuration export/import helpers."""

from core.config import ConfigExportBundle, merge_imported_settings


def test_merge_imported_settings_replaces_non_empty() -> None:
    current = {"AFIP_CUIT": "20111111111", "MP_ACCESS_TOKEN": "old-token"}
    imported = {"AFIP_CUIT": "20999999999", "MP_ACCESS_TOKEN": ""}

    merged = merge_imported_settings(current, imported)

    assert merged["AFIP_CUIT"] == "20999999999"
    assert merged["MP_ACCESS_TOKEN"] == "old-token"


def test_merge_imported_settings_ignores_unknown_keys() -> None:
    current = {"AFIP_CUIT": "20111111111"}
    imported = {"UNKNOWN_KEY": "value", "AFIP_CUIT": "20999999999"}

    merged = merge_imported_settings(current, imported)

    assert "UNKNOWN_KEY" not in merged
    assert merged["AFIP_CUIT"] == "20999999999"


def test_config_export_bundle_roundtrip() -> None:
    bundle = ConfigExportBundle(
        exported_at="2026-06-23T12:00:00+00:00",
        settings={"AFIP_CUIT": "20111111111"},
        certificates={"cert_pem": "CERT", "key_pem": "KEY"},
    )
    restored = ConfigExportBundle.model_validate_json(bundle.model_dump_json())
    assert restored.settings["AFIP_CUIT"] == "20111111111"
    assert restored.certificates["cert_pem"] == "CERT"
