import logging
from datetime import datetime
from decimal import Decimal

from afip import Afip

from ..domain.exceptions import AfipInvoiceError
from ..domain.models import IssuedInvoice
from .afip.wsfe_settings import load_wsfe_settings

logger = logging.getLogger(__name__)


class AfipElectronicBillingProvider:
    """Issues Factura C invoices through the AFIP WSFE service.

    Implements :class:`~src.domain.ports.AfipPort`.
    Amount maps 1:1 to both ImpTotal and ImpNeto (no IVA, Monotributo).
    """

    def __init__(self, access_token: str, cuit: int, cert: str, key: str) -> None:
        client = Afip(
            {
                "access_token": access_token,
                "CUIT": cuit,
                "production": True,
                "cert": cert,
                "key": key,
            }
        )
        self._billing = client.ElectronicBilling

    def issue_invoice(self, amount: Decimal, date: datetime) -> IssuedInvoice:
        """Create a Factura C for *amount* ARS on the given *date*.

        Args:
            amount: Total amount in pesos (ImpTotal = ImpNeto = amount).
            date:   Service date; used for FchServDesde, FchServHasta, FchVtoPago.

        Returns:
            :class:`~src.domain.models.IssuedInvoice` with CAE and voucher number.

        Raises:
            AfipInvoiceError: If AFIP rejects or fails to process the request.
        """
        invoice_number = self._next_invoice_number()
        fecha = int(date.strftime("%Y%m%d"))
        amount_float = float(amount)

        wsfe = load_wsfe_settings()
        data = {
            "CantReg": 1,
            "PtoVta": wsfe.punto_de_venta,
            "CbteTipo": wsfe.tipo_factura,
            "Concepto": wsfe.concepto,
            "DocTipo": wsfe.doc_tipo,
            "DocNro": wsfe.doc_nro,
            "CbteDesde": invoice_number,
            "CbteHasta": invoice_number,
            "CbteFch": fecha,
            "FchServDesde": fecha,
            "FchServHasta": fecha,
            "FchVtoPago": fecha,
            "ImpTotal": amount_float,
            "ImpTotConc": 0,
            "ImpNeto": amount_float,
            "ImpOpEx": 0,
            "ImpIVA": 0,
            "ImpTrib": 0,
            "MonId": "PES",
            "MonCotiz": 1,
            "CondicionIVAReceptorId": wsfe.condicion_iva,
        }

        try:
            res = self._billing.createVoucher(data)
        except Exception as exc:
            raise AfipInvoiceError(f"AFIP rejected voucher for amount {amount}: {exc}") from exc

        logger.debug("AFIP voucher created: CAE=%s number=%d", res["CAE"], invoice_number)
        return IssuedInvoice(
            cae=res["CAE"],
            cae_expiry=res["CAEFchVto"],
            invoice_number=invoice_number,
        )

    def _next_invoice_number(self) -> int:
        wsfe = load_wsfe_settings()
        last = self._billing.getLastVoucher(wsfe.punto_de_venta, wsfe.tipo_factura)
        return last + 1
