from datetime import timedelta
from unittest.mock import patch

from src.providers.afip.auth import AfipAuthProvider
from src.providers.afip.models import AfipCredentials


def _make_provider() -> AfipAuthProvider:
    return AfipAuthProvider(
        cert_path="cert.pem",
        key_path="key.pem",
        cuit=20424572951,
        renewal_buffer=timedelta(minutes=5),
    )


def _valid_credentials(provider: AfipAuthProvider) -> AfipCredentials:
    return AfipCredentials(
        token="token",
        sign="sign",
        expiration=provider._afip_now() + timedelta(hours=12),
    )


def test_get_credentials_caches_valid_token() -> None:
    provider = _make_provider()
    fresh = _valid_credentials(provider)

    with patch.object(provider, "_request_credentials", return_value=fresh) as request:
        first = provider.get_credentials()
        second = provider.get_credentials()

    assert first is second
    request.assert_called_once()


def test_get_credentials_renews_near_expiration() -> None:
    provider = _make_provider()
    expiring = AfipCredentials(
        token="old",
        sign="old",
        expiration=provider._afip_now() + timedelta(minutes=1),
    )
    renewed = _valid_credentials(provider)

    with patch.object(
        provider,
        "_request_credentials",
        side_effect=[expiring, renewed],
    ) as request:
        first = provider.get_credentials()
        second = provider.get_credentials()

    assert first.token == "old"
    assert second.token == "token"
    assert request.call_count == 2


def test_should_renew_respects_buffer() -> None:
    provider = _make_provider()
    credentials = AfipCredentials(
        token="token",
        sign="sign",
        expiration=provider._afip_now() + timedelta(minutes=4),
    )

    assert provider._should_renew(credentials) is True
