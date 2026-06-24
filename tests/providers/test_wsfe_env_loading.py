from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.domain.models import MercadoPagoPayment
from src.providers.afip.models import AfipCredentials
from src.providers.afip.wsfe_settings import load_wsfe_settings
from src.providers.afip.afip_electronic_billing import AfipElectronicBillingProvider
from src.bootstrap import load_runtime_config


def _dummy_auth(cuit: int) -> object:
    return SimpleNamespace(
        cuit=cuit,
        get_credentials=lambda: AfipCredentials(
            token="t", sign="s", expiration=datetime.now() + timedelta(hours=1)
        ),
    )


def test_wsfe_settings_env_overrides_are_used_in_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AFIP_WSFE_PUNTO_DE_VENTA", "7")
    monkeypatch.setenv("AFIP_WSFE_TIPO_FACTURA", "11")
    monkeypatch.setenv("AFIP_WSFE_CONCEPTO", "2")
    monkeypatch.setenv("AFIP_WSFE_DOC_TIPO", "99")
    monkeypatch.setenv("AFIP_WSFE_DOC_NRO", "0")
    monkeypatch.setenv("AFIP_WSFE_CONDICION_IVA", "5")
    monkeypatch.setenv("AFIP_WSFE_INVOICE_TYPE_LABEL", "Factura C")
    monkeypatch.setenv("AFIP_WSFE_CONCEPT_LABEL", "Servicios")
    monkeypatch.setenv("AFIP_WSFE_RECEIVER_LABEL", "Consumidor Final")

    wsfe = load_wsfe_settings()
    assert wsfe.punto_de_venta == 7

    with patch(
        "src.providers.afip.afip_electronic_billing.create_afip_client",
        return_value=SimpleNamespace(service=SimpleNamespace()),
    ):
        provider = AfipElectronicBillingProvider(auth=_dummy_auth(cuit=20424572951))  # type: ignore[arg-type]
        provider._next_invoice_number = lambda: 123  # type: ignore[method-assign]

        # Pydantic expects Decimal; create via string to avoid float quirks.
        payment = MercadoPagoPayment(
            id=42,
            date_created=datetime.now(),
            transaction_amount="100.0",  # type: ignore[arg-type]
            status="fetched",
        )

        preview = provider.build_invoice_preview(payment)
        assert preview.point_of_sale == 7
        assert preview.invoice_type == "Factura C"
        assert preview.concept == "Servicios"
        assert preview.receiver == "Consumidor Final"


def test_wsfe_settings_loaded_from_desktop_env_via_arc_env_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))

    from importlib import reload

    import desktop.facturador_pyqt6_app.core.config as desktop_config

    reload(desktop_config)

    env_path = desktop_config.ENV_FILE
    assert str(env_path).endswith(".facturador/.env")

    data = {
        "AFIP_CUIT": "20424572951",
        "AFIP_CERT_PATH": "/tmp/cert.crt",
        "AFIP_KEY_PATH": "/tmp/private.key",
        "MP_ACCESS_TOKEN": "mp_token",
        "MP_USER_ID": "1",
        "AFIP_WSFE_PUNTO_DE_VENTA": "9",
        "AFIP_WSFE_TIPO_FACTURA": "11",
        "AFIP_WSFE_CONCEPTO": "2",
        "AFIP_WSFE_DOC_TIPO": "99",
        "AFIP_WSFE_DOC_NRO": "0",
        "AFIP_WSFE_CONDICION_IVA": "5",
        "AFIP_WSFE_INVOICE_TYPE_LABEL": "Factura C",
        "AFIP_WSFE_CONCEPT_LABEL": "Servicios",
        "AFIP_WSFE_RECEIVER_LABEL": "Consumidor Final",
    }
    desktop_config.save_config(data)

    monkeypatch.setenv("ARC_ENV_FILE", str(env_path))
    load_runtime_config()

    wsfe = load_wsfe_settings()
    assert wsfe.punto_de_venta == 9
