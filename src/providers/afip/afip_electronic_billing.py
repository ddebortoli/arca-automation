import logging
from datetime import datetime
from decimal import Decimal

from ...domain.exceptions import AfipInvoiceError
from ...domain.models import InvoicePreview, IssuedInvoice, MercadoPagoPayment
from .auth import AfipAuthProvider
from .transport import create_afip_client

logger = logging.getLogger(__name__)

_PUNTO_DE_VENTA = 2
_TIPO_FACTURA = 11  # Factura C
_INVOICE_TYPE_LABEL = "Factura C"
_CONCEPTO = 2       # Servicios
_CONCEPT_LABEL = "Servicios"
_DOC_TIPO = 99      # Consumidor Final
_DOC_NRO = 0
_RECEIVER_LABEL = "Consumidor Final"
_CONDICION_IVA = 5

WSFE_WSDL = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"


class AfipElectronicBillingProvider:
    """Issues Factura C invoices through the AFIP WSFE service.

    Implements :class:`~src.domain.ports.AfipPort`.
    """

    def __init__(self, auth: AfipAuthProvider) -> None:
        self._auth = auth
        self._client = create_afip_client(WSFE_WSDL)

    def build_invoice_preview(self, payment: MercadoPagoPayment) -> InvoicePreview:
        """Return a preview of the voucher that would be issued for *payment*."""
        return InvoicePreview(
            payment_id=payment.id,
            amount=payment.transaction_amount,
            service_date=payment.date_created,
            invoice_type=_INVOICE_TYPE_LABEL,
            point_of_sale=_PUNTO_DE_VENTA,
            next_invoice_number=self._next_invoice_number(),
            receiver=_RECEIVER_LABEL,
            concept=_CONCEPT_LABEL,
        )

    def issue_invoice(
        self,
        amount: Decimal,
        date: datetime,
    ) -> IssuedInvoice:
        invoice_number = self._next_invoice_number()
        fecha = date.strftime("%Y%m%d")
        auth = self._build_auth()

        request = {
            "FeCabReq": {
                "CantReg": 1,
                "PtoVta": _PUNTO_DE_VENTA,
                "CbteTipo": _TIPO_FACTURA,
            },
            "FeDetReq": {
                "FECAEDetRequest": [{
                    "Concepto": _CONCEPTO,
                    "DocTipo": _DOC_TIPO,
                    "DocNro": _DOC_NRO,
                    "CbteDesde": invoice_number,
                    "CbteHasta": invoice_number,
                    "CbteFch": fecha,
                    "ImpTotal": float(amount),
                    "ImpTotConc": 0,
                    "ImpNeto": float(amount),
                    "ImpOpEx": 0,
                    "ImpTrib": 0,
                    "ImpIVA": 0,
                    "MonId": "PES",
                    "MonCotiz": 1,
                    "FchServDesde": fecha,
                    "FchServHasta": fecha,
                    "FchVtoPago": fecha,
                    "CondicionIVAReceptorId": _CONDICION_IVA,
                }]
            },
        }

        try:
            response = self._client.service.FECAESolicitar(
                Auth=auth,
                FeCAEReq=request,
            )

            detail = response.FeDetResp.FECAEDetResponse[0]

            if detail.Resultado != "A":
                raise AfipInvoiceError(
                    f"Voucher rejected: {detail.Observaciones}"
                )

            logger.debug(
                "AFIP voucher created: CAE=%s number=%d",
                detail.CAE,
                invoice_number,
            )
            return IssuedInvoice(
                cae=detail.CAE,
                cae_expiry=detail.CAEFchVto,
                invoice_number=invoice_number,
            )

        except AfipInvoiceError:
            raise
        except Exception as exc:
            raise AfipInvoiceError(
                f"AFIP rejected voucher: {exc}"
            ) from exc

    def _next_invoice_number(self) -> int:
        result = self._client.service.FECompUltimoAutorizado(
            Auth=self._build_auth(),
            PtoVta=_PUNTO_DE_VENTA,
            CbteTipo=_TIPO_FACTURA,
        )
        return result.CbteNro + 1

    def _build_auth(self) -> dict[str, int | str]:
        credentials = self._auth.get_credentials()
        return {
            "Token": credentials.token,
            "Sign": credentials.sign,
            "Cuit": self._auth.cuit,
        }
