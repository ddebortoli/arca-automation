import logging
from decimal import Decimal

import httpx

from ..domain.datetime_utils import parse_mp_datetime
from ..domain.exceptions import MercadoPagoError
from ..domain.income import get_collector_id, is_income
from ..domain.models import MercadoPagoPayment

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.mercadopago.com"
_PAGE_SIZE = 100


class HttpMercadoPagoProvider:
    """Fetches income payments from the MercadoPago Payments API.

    Implements :class:`~src.domain.ports.MercadoPagoPort`.
    Income is determined solely by whether the authenticated user is the
    payment collector — not by ``operation_type`` or ``payment_method_id``.
    Handles pagination transparently — callers always receive the full list.
    """

    def __init__(self, access_token: str, my_user_id: int) -> None:
        self._headers = {
            "accept": "application/json",
            "authorization": f"Bearer {access_token}",
        }
        self._my_user_id = my_user_id

    def fetch_transfers(self, begin_date: str, end_date: str) -> list[MercadoPagoPayment]:
        """Return all income payments within *begin_date* / *end_date*.

        Args:
            begin_date: MP relative formula, e.g. ``"NOW-17DAYS"``.
            end_date:   MP relative formula, e.g. ``"NOW"``.

        Returns:
            Full list of income payments across all pages, ordered by date descending.

        Raises:
            MercadoPagoError: On non-200 HTTP responses.
        """
        payments: list[MercadoPagoPayment] = []
        offset = 0

        while True:
            batch = self._fetch_page(begin_date, end_date, offset)
            payments.extend(batch)
            if len(batch) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE

        logger.debug("Fetched %d income payment(s) from MercadoPago", len(payments))
        return payments

    def _fetch_page(
        self,
        begin_date: str,
        end_date: str,
        offset: int,
    ) -> list[MercadoPagoPayment]:
        params = {
            "sort": "date_created",
            "criteria": "desc",
            "limit": _PAGE_SIZE,
            "offset": offset,
            "range": "date_created",
            "begin_date": begin_date,
            "end_date": end_date,
        }

        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{_BASE_URL}/v1/payments/search",
                params=params,
                headers=self._headers,
            )

        if response.status_code != 200:
            raise MercadoPagoError(
                f"MercadoPago API error {response.status_code}: {response.text}"
            )

        results: list[dict] = response.json().get("results", [])
        return self._filter_income_payments(results)

    def _filter_income_payments(self, results: list[dict]) -> list[MercadoPagoPayment]:
        income_payments: list[MercadoPagoPayment] = []

        for raw in results:
            if get_collector_id(raw) is None:
                logger.warning(
                    "Payment %s has no collector_id nor collector.id — skipping",
                    raw.get("id"),
                )
                continue

            if not is_income(raw, self._my_user_id):
                continue

            income_payments.append(_parse_payment(raw))

        return income_payments


def _parse_payment(raw: dict) -> MercadoPagoPayment:
    return MercadoPagoPayment(
        id=raw["id"],
        date_created=parse_mp_datetime(raw["date_created"]),
        transaction_amount=Decimal(str(raw["transaction_amount"])),
        status=raw["status"],
    )
