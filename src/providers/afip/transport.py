import ssl

import requests
from requests.adapters import HTTPAdapter
from zeep import Client
from zeep.transports import Transport


class _AfipHttpAdapter(HTTPAdapter):
    """Lowers OpenSSL security level for AFIP's legacy DH parameters."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def create_afip_client(wsdl: str) -> Client:
    """Build a zeep client configured for AFIP's HTTPS endpoints."""
    session = requests.Session()
    session.mount("https://", _AfipHttpAdapter())
    return Client(wsdl, transport=Transport(session=session))
