import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from ...domain.exceptions import AfipInvoiceError, AfipValidationError
from ...domain.models import InvoicePreview, IssuedInvoice, MercadoPagoPayment
from .auth import AfipAuthProvider
from .wsfe_settings import load_wsfe_settings
from .transport import create_afip_client

logger = logging.getLogger(__name__)

WSFE_WSDL = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"


class AfipElectronicBillingProvider:
    """Issues Factura C invoices through the AFIP WSFE service.

    Implements :class:`~src.domain.ports.AfipPort`.
    """

    def __init__(self, auth: AfipAuthProvider) -> None:
        self._auth = auth
        self._client = create_afip_client(WSFE_WSDL)

    @staticmethod
    def _get_attr_or_key(obj: Any, key: str) -> Any | None:
        if obj is None:
            return None
        if hasattr(obj, key):
            return getattr(obj, key)
        if isinstance(obj, Mapping):
            return obj.get(key)
        return None

    @classmethod
    def _extract_errors_and_events(cls, result: Any) -> tuple[list[str], list[str]]:
        errors_obj = cls._get_attr_or_key(result, "Errors")
        events_obj = cls._get_attr_or_key(result, "Events")

        err_items = cls._get_attr_or_key(errors_obj, "Err")
        evt_items = cls._get_attr_or_key(events_obj, "Evt")

        def _normalize_items(value: Any) -> list[Any]:
            if not value:
                return []
            if isinstance(value, list):
                return value
            if isinstance(value, tuple):
                return list(value)
            if isinstance(value, Mapping):
                return [value]
            # Some zeep responses may return a single object (not a list).
            if hasattr(value, "Code") or hasattr(value, "Msg"):
                return [value]
            return [value]

        errors: list[str] = []
        for item in _normalize_items(err_items):
            code = cls._get_attr_or_key(item, "Code")
            msg = cls._get_attr_or_key(item, "Msg")
            if code is not None and msg is not None:
                errors.append(f"[{code}] {msg}")

        events: list[str] = []
        for item in _normalize_items(evt_items):
            code = cls._get_attr_or_key(item, "Code")
            msg = cls._get_attr_or_key(item, "Msg")
            if code is not None and msg is not None:
                events.append(f"[{code}] {msg}")

        return errors, events

    def validate_configuration(
        self,
        *,
        point_of_sale: int | None = None,
        invoice_type: int | None = None,
    ) -> tuple[list[str], list[str]]:
        """Validate AFIP WSFE configuration using a lightweight call.

        Calls `FECompUltimoAutorizado` and interprets:
        - `Errors.Err` as fatal configuration errors.
        - `Events.Evt` as warnings/events.
        """
        wsfe = load_wsfe_settings()
        po_vta = wsfe.punto_de_venta if point_of_sale is None else point_of_sale
        cbte_tipo = wsfe.tipo_factura if invoice_type is None else invoice_type

        result = self._client.service.FECompUltimoAutorizado(
            Auth=self._build_auth(),
            PtoVta=po_vta,
            CbteTipo=cbte_tipo,
        )

        errors, events = self._extract_errors_and_events(result)
        for err in errors:
            logger.error("AFIP validation error: %s", err)
        for evt in events:
            logger.warning("AFIP validation event: %s", evt)

        if errors:
            raise AfipValidationError("; ".join(errors))

        return errors, events

    def build_invoice_preview(self, payment: MercadoPagoPayment) -> InvoicePreview:
        """Return a preview of the voucher that would be issued for *payment*."""
        wsfe = load_wsfe_settings()
        return InvoicePreview(
            payment_id=payment.id,
            amount=payment.transaction_amount,
            service_date=payment.date_created,
            invoice_type=wsfe.invoice_type_label,
            point_of_sale=wsfe.punto_de_venta,
            next_invoice_number=self._next_invoice_number(),
            receiver=wsfe.receiver_label,
            concept=wsfe.concept_label,
        )

    def issue_invoice(
        self,
        amount: Decimal,
        date: datetime,
    ) -> IssuedInvoice:
        invoice_number = self._next_invoice_number()
        wsfe = load_wsfe_settings()
        fecha = date.strftime("%Y%m%d")
        auth = self._build_auth()

        request = {
            "FeCabReq": {
                "CantReg": 1,
                "PtoVta": wsfe.punto_de_venta,
                "CbteTipo": wsfe.tipo_factura,
            },
            "FeDetReq": {
                "FECAEDetRequest": [
                    {
                        "Concepto": wsfe.concepto,
                        "DocTipo": wsfe.doc_tipo,
                        "DocNro": wsfe.doc_nro,
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
                        "CondicionIVAReceptorId": wsfe.condicion_iva,
                    }
                ]
            },
        }

        try:
            response = self._client.service.FECAESolicitar(
                Auth=auth,
                FeCAEReq=request,
            )

            detail = response.FeDetResp.FECAEDetResponse[0]

            if detail.Resultado != "A":
                raise AfipInvoiceError(f"Voucher rejected: {detail.Observaciones}")

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
            raise AfipInvoiceError(f"AFIP rejected voucher: {exc}") from exc

    def _next_invoice_number(self) -> int:
        wsfe = load_wsfe_settings()
        result = self._client.service.FECompUltimoAutorizado(
            Auth=self._build_auth(),
            PtoVta=wsfe.punto_de_venta,
            CbteTipo=wsfe.tipo_factura,
        )
        errors, events = self._extract_errors_and_events(result)
        for evt in events:
            logger.warning("AFIP WSFE event: %s", evt)
        if errors:
            raise AfipInvoiceError(
                f"AFIP WSFE credential/service validation failed: {', '.join(errors)}"
            )
        cbte_nro = self._get_attr_or_key(result, "CbteNro")
        if cbte_nro is None:
            raise AfipInvoiceError("AFIP WSFE returned CbteNro as null")
        try:
            cbte_int = int(cbte_nro)
        except (TypeError, ValueError) as exc:
            raise AfipInvoiceError(f"AFIP WSFE returned invalid CbteNro: {cbte_nro}") from exc
        if cbte_int <= 0:
            raise AfipInvoiceError(f"AFIP WSFE returned unexpected CbteNro: {cbte_int}")
        return cbte_int + 1

    def _build_auth(self) -> dict[str, int | str]:
        credentials = self._auth.get_credentials()
        return {
            "Token": credentials.token,
            "Sign": credentials.sign,
            "Cuit": self._auth.cuit,
        }
