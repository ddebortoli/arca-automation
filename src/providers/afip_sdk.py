import logging
from datetime import datetime
from decimal import Decimal

from afip import Afip

from ..domain.exceptions import AfipInvoiceError
from ..domain.models import IssuedInvoice

logger = logging.getLogger(__name__)

_PUNTO_DE_VENTA = 2
_TIPO_FACTURA = 11      # Factura C
_CONCEPTO = 2           # Servicios
_TIPO_DOCUMENTO = 99    # Consumidor Final
_NUMERO_DOCUMENTO = 0
_CONDICION_IVA = 5      # Consumidor Final


class AfipElectronicBillingProvider:
    """Issues Factura C invoices through the AFIP WSFE service.

    Implements :class:`~src.domain.ports.AfipPort`.
    Amount maps 1:1 to both ImpTotal and ImpNeto (no IVA, Monotributo).
    """

    def __init__(self, access_token: str, cuit: int, cert: str, key: str) -> None:
        client = Afip({
            "access_token": access_token,
            "CUIT": cuit,
            "production": True,
            "cert": cert,
            "key": key,
        })
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

        data = {
            "CantReg": 1,
            "PtoVta": _PUNTO_DE_VENTA,
            "CbteTipo": _TIPO_FACTURA,
            "Concepto": _CONCEPTO,
            "DocTipo": _TIPO_DOCUMENTO,
            "DocNro": _NUMERO_DOCUMENTO,
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
            "CondicionIVAReceptorId": _CONDICION_IVA,
        }

        try:
            res = self._billing.createVoucher(data)
        except Exception as exc:
            raise AfipInvoiceError(
                f"AFIP rejected voucher for amount {amount}: {exc}"
            ) from exc

        logger.debug("AFIP voucher created: CAE=%s number=%d", res["CAE"], invoice_number)
        return IssuedInvoice(
            cae=res["CAE"],
            cae_expiry=res["CAEFchVto"],
            invoice_number=invoice_number,
        )

    def _next_invoice_number(self) -> int:
        last = self._billing.getLastVoucher(_PUNTO_DE_VENTA, _TIPO_FACTURA)
        return last + 1
