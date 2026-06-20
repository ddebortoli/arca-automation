import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.domain.exceptions import AfipValidationError
from src.providers.afip.afip_electronic_billing import AfipElectronicBillingProvider
from src.providers.afip.models import AfipCredentials


def test_validate_configuration_raises_on_errors(caplog: pytest.LogCaptureFixture) -> None:
    fake_auth = SimpleNamespace()
    fake_auth.cuit = 20424572951
    fake_auth.get_credentials = lambda: AfipCredentials(
        token="token",
        sign="sign",
        expiration=datetime.now(),
    )

    err_item = SimpleNamespace(Code=600, Msg="ValidacionDeToken: missing relation")
    errors = SimpleNamespace(Err=[err_item])
    result = SimpleNamespace(Errors=errors, Events=SimpleNamespace(Evt=[]))

    fake_service = SimpleNamespace(
        FECompUltimoAutorizado=lambda **_: result,
    )
    fake_client = SimpleNamespace(service=fake_service)

    with patch(
        "src.providers.afip.afip_electronic_billing.create_afip_client",
        return_value=fake_client,
    ):
        provider = AfipElectronicBillingProvider(auth=fake_auth)
        caplog.set_level(logging.ERROR)

        with pytest.raises(AfipValidationError):
            provider.validate_configuration()


def test_validate_configuration_logs_events_as_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_auth = SimpleNamespace()
    fake_auth.cuit = 20424572951
    fake_auth.get_credentials = lambda: AfipCredentials(
        token="token",
        sign="sign",
        expiration=datetime.now(),
    )

    evt_item = SimpleNamespace(
        Code=39,
        Msg="IMPORTANTE: ... WS version updated",
    )
    result = SimpleNamespace(
        Errors=SimpleNamespace(Err=[]),
        Events=SimpleNamespace(Evt=[evt_item]),
    )
    fake_service = SimpleNamespace(
        FECompUltimoAutorizado=lambda **_: result,
    )
    fake_client = SimpleNamespace(service=fake_service)

    with patch(
        "src.providers.afip.afip_electronic_billing.create_afip_client",
        return_value=fake_client,
    ):
        provider = AfipElectronicBillingProvider(auth=fake_auth)
        caplog.set_level(logging.WARNING)

        errors, events = provider.validate_configuration()
        assert errors == []
        assert events and "39" in events[0]
        assert any("AFIP validation event" in rec.message for rec in caplog.records)

