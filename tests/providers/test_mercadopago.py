import logging

import pytest

from src.providers.mercadopago import HttpMercadoPagoProvider

MY_USER_ID = 2963271786
OTHER_USER_ID = 178626783


def _raw_payment(
    payment_id: int,
    *,
    collector_id: int | None = None,
    collector_dot_id: int | None = None,
    operation_type: str = "money_transfer",
) -> dict:
    payment: dict = {
        "id": payment_id,
        "date_created": "2026-05-18T12:00:00.000-04:00",
        "transaction_amount": 1500.0,
        "status": "approved",
        "operation_type": operation_type,
    }
    if collector_id is not None:
        payment["collector_id"] = collector_id
    if collector_dot_id is not None:
        payment["collector"] = {"id": collector_dot_id}
    return payment


class TestHttpMercadoPagoProviderFilter:
    def test_keeps_only_payments_where_user_is_collector(self) -> None:
        provider = HttpMercadoPagoProvider(access_token="token", my_user_id=MY_USER_ID)
        results = [
            _raw_payment(1, collector_id=MY_USER_ID, operation_type="account_fund"),
            _raw_payment(2, collector_id=MY_USER_ID, operation_type="money_transfer"),
            _raw_payment(3, collector_dot_id=MY_USER_ID),
            _raw_payment(
                4,
                collector_dot_id=OTHER_USER_ID,
                operation_type="account_fund",
            ),
            _raw_payment(
                5,
                collector_dot_id=OTHER_USER_ID,
                operation_type="money_transfer",
            ),
        ]

        income = provider._filter_income_payments(results)

        assert [payment.id for payment in income] == [1, 2, 3]
        assert income[0].date_created.hour == 13
        assert str(income[0].date_created.tzinfo) == "America/Argentina/Buenos_Aires"

    def test_logs_warning_when_collector_is_missing(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        provider = HttpMercadoPagoProvider(access_token="token", my_user_id=MY_USER_ID)

        with caplog.at_level(logging.WARNING):
            income = provider._filter_income_payments([{"id": 999, "status": "approved"}])

        assert income == []
        assert "Payment 999 has no collector_id nor collector.id" in caplog.text
