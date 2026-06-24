import base64
import json
import logging
import os
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

from zeep import Client

from ...domain.datetime_utils import ART
from .models import AfipAuthenticationError, AfipCredentials
from .transport import create_afip_client

logger = logging.getLogger(__name__)

WSAA_WSDL = "https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL"
SERVICE = "wsfe"
_DEFAULT_RENEWAL_BUFFER = timedelta(minutes=5)


class AfipAuthProvider:
    """Handles WSAA authentication and returns token/sign credentials for AFIP services."""

    def __init__(
        self,
        cert_path: str,
        key_path: str,
        cuit: int,
        renewal_buffer: timedelta = _DEFAULT_RENEWAL_BUFFER,
    ) -> None:
        self._cert_path = Path(cert_path)
        self._key_path = Path(key_path)
        self._cuit = cuit
        self._renewal_buffer = renewal_buffer
        self._client: Client | None = None
        self._cached: AfipCredentials | None = None
        # WSAA may reject concurrent renewals for the same CEE/service combination.
        # This lock avoids races inside a single process.
        self._renew_lock = threading.Lock()
        self._cache_path = self._resolve_cache_path()

    @property
    def cuit(self) -> int:
        return self._cuit

    def _resolve_cache_path(self) -> Path:
        """Return path for persisted WSAA credentials cache."""
        override = os.getenv("AFIP_WSAA_CACHE_PATH")
        if override:
            return Path(override).expanduser()

        cache_dir = Path(os.getenv("AFIP_WSAA_CACHE_DIR", "~/.cache/arca-automation")).expanduser()
        return cache_dir / f"wsaa_{self._cuit}_{SERVICE}.json"

    def get_credentials(self) -> AfipCredentials:
        """Return cached WSAA credentials, renewing only when near expiration."""
        cached = self._cached
        if cached is None:
            cached_from_disk = self._load_cached_credentials_from_disk()
            if cached_from_disk is not None:
                self._cached = cached_from_disk
                cached = cached_from_disk

        if cached is not None and not self._should_renew(cached):
            logger.debug("Reusing cached WSAA credentials (expires %s)", cached.expiration)
            return cached

        with self._renew_lock:
            cached = self._cached
            if cached is not None and not self._should_renew(cached):
                logger.debug("Reusing cached WSAA credentials (expires %s)", cached.expiration)
                return cached

            logger.info("Requesting new WSAA credentials")
            try:
                self._cached = self._request_credentials()
            except AfipAuthenticationError as exc:
                # If another thread/process refreshed the TA between checks, WSAA can respond
                # with "already has a valid TA" (even though we requested a renewal).
                if self._cached is not None and self._is_wsaa_ta_already_valid(exc):
                    logger.warning(
                        "WSAA rejected renewed TA, reusing cached credentials instead: %s",
                        exc,
                    )
                    return self._cached
                if self._is_wsaa_ta_already_valid(exc):
                    cached_from_disk = self._load_cached_credentials_from_disk()
                    if cached_from_disk is not None and not self._should_renew(cached_from_disk):
                        self._cached = cached_from_disk
                        return cached_from_disk
                raise

            credentials = self._cached
            if credentials is not None:
                self._save_cached_credentials_to_disk(credentials)
            return credentials

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = create_afip_client(WSAA_WSDL)
        return self._client

    def _should_renew(self, credentials: AfipCredentials) -> bool:
        return self._afip_now() + self._renewal_buffer >= credentials.expiration

    @staticmethod
    def _is_wsaa_ta_already_valid(exc: AfipAuthenticationError) -> bool:
        """Best-effort check for WSAA 'TA already valid' rejection messages."""
        msg = str(exc).lower()
        return ("ya posee" in msg and "ta" in msg and "val" in msg) or (
            "already" in msg and "valid" in msg and "ta" in msg
        )

    def _load_cached_credentials_from_disk(self) -> AfipCredentials | None:
        """Load WSAA credentials from disk cache if available."""
        try:
            raw = self._cache_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return AfipCredentials(
                token=str(data["token"]),
                sign=str(data["sign"]),
                expiration=self._parse_afip_datetime(str(data["expiration"])),
            )
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            return None

    def _save_cached_credentials_to_disk(self, credentials: AfipCredentials) -> None:
        """Persist WSAA credentials to disk for cross-process reuse."""
        try:
            cache_dir = self._cache_path.parent
            cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "token": credentials.token,
                "sign": credentials.sign,
                "expiration": credentials.expiration.isoformat(),
            }
            tmp_path = self._cache_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload), encoding="utf-8")
            tmp_path.replace(self._cache_path)
        except OSError as exc:
            logger.warning("Failed to write WSAA credential cache: %s", exc)

    def _request_credentials(self) -> AfipCredentials:
        tra_xml = self._build_tra()
        cms = self._sign_tra(tra_xml)

        try:
            login_response = self._get_client().service.loginCms(cms)
        except Exception as exc:
            raise AfipAuthenticationError(f"WSAA authentication failed: {exc}") from exc

        return self._parse_response(login_response)

    def _afip_now(self) -> datetime:
        """Return current time in Argentina (naive), as WSAA expects."""
        return datetime.now(ART).replace(tzinfo=None)

    def _parse_afip_datetime(self, value: str) -> datetime:
        """Parse a WSAA timestamp into naive ART."""
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            return dt.astimezone(ART).replace(tzinfo=None)
        return dt

    def _build_tra(self) -> str:
        now = self._afip_now()
        unique_id = int(datetime.now(ART).timestamp())

        generation_time = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
        expiration_time = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
    <header>
        <uniqueId>{unique_id}</uniqueId>
        <generationTime>{generation_time}</generationTime>
        <expirationTime>{expiration_time}</expirationTime>
    </header>
    <service>{SERVICE}</service>
</loginTicketRequest>
"""

    def _sign_tra(self, tra_xml: str) -> str:
        """Uses OpenSSL to generate a CMS-signed message."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".xml",
            delete=False,
        ) as tra_file:
            tra_file.write(tra_xml)
            tra_path = tra_file.name

        cms_path = f"{tra_path}.cms"

        try:
            command = [
                "openssl",
                "smime",
                "-sign",
                "-signer",
                str(self._cert_path),
                "-inkey",
                str(self._key_path),
                "-outform",
                "DER",
                "-nodetach",
                "-binary",
                "-in",
                tra_path,
                "-out",
                cms_path,
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise AfipAuthenticationError(f"OpenSSL signing failed: {result.stderr}")

            return base64.b64encode(Path(cms_path).read_bytes()).decode()
        finally:
            Path(tra_path).unlink(missing_ok=True)
            Path(cms_path).unlink(missing_ok=True)

    def _parse_response(self, login_response: str) -> AfipCredentials:
        try:
            root = ElementTree.fromstring(login_response)

            token = root.find(".//token").text
            sign = root.find(".//sign").text
            expiration = root.find(".//expirationTime").text

            return AfipCredentials(
                token=token,
                sign=sign,
                expiration=self._parse_afip_datetime(expiration),
            )

        except Exception as exc:
            raise AfipAuthenticationError(f"Invalid WSAA response: {exc}") from exc
