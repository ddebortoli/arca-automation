import base64
import logging
import subprocess
import tempfile
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

    @property
    def cuit(self) -> int:
        return self._cuit

    def get_credentials(self) -> AfipCredentials:
        """Return cached WSAA credentials, renewing only when near expiration."""
        if self._cached is not None and not self._should_renew(self._cached):
            logger.debug("Reusing cached WSAA credentials (expires %s)", self._cached.expiration)
            return self._cached

        logger.info("Requesting new WSAA credentials")
        self._cached = self._request_credentials()
        return self._cached

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = create_afip_client(WSAA_WSDL)
        return self._client

    def _should_renew(self, credentials: AfipCredentials) -> bool:
        return self._afip_now() + self._renewal_buffer >= credentials.expiration

    def _request_credentials(self) -> AfipCredentials:
        tra_xml = self._build_tra()
        cms = self._sign_tra(tra_xml)

        try:
            login_response = self._get_client().service.loginCms(cms)
        except Exception as exc:
            raise AfipAuthenticationError(
                f"WSAA authentication failed: {exc}"
            ) from exc

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
                raise AfipAuthenticationError(
                    f"OpenSSL signing failed: {result.stderr}"
                )

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
            raise AfipAuthenticationError(
                f"Invalid WSAA response: {exc}"
            ) from exc
