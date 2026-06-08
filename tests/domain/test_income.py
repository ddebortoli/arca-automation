import pytest

from src.domain.income import get_collector_id, is_income

MY_USER_ID = 2963271786
OTHER_USER_ID = 178626783


class TestGetCollectorId:
    def test_returns_collector_id_when_present(self) -> None:
        payment = {"collector_id": MY_USER_ID}

        assert get_collector_id(payment) == MY_USER_ID

    def test_returns_collector_dot_id_when_collector_id_missing(self) -> None:
        payment = {"collector": {"id": MY_USER_ID}}

        assert get_collector_id(payment) == MY_USER_ID

    def test_prefers_collector_id_over_collector_dot_id(self) -> None:
        payment = {
            "collector_id": MY_USER_ID,
            "collector": {"id": OTHER_USER_ID},
        }

        assert get_collector_id(payment) == MY_USER_ID

    def test_returns_none_when_collector_missing(self) -> None:
        assert get_collector_id({}) is None
        assert get_collector_id({"collector": {}}) is None


class TestIsIncome:
    @pytest.mark.parametrize(
        "payment",
        [
            {"collector_id": MY_USER_ID, "operation_type": "account_fund"},
            {"collector_id": MY_USER_ID, "operation_type": "money_transfer"},
            {"collector": {"id": MY_USER_ID}, "operation_type": "money_transfer"},
            {"collector_id": str(MY_USER_ID)},
        ],
    )
    def test_returns_true_when_user_is_collector(self, payment: dict) -> None:
        assert is_income(payment, MY_USER_ID) is True

    def test_returns_false_when_user_is_payer_not_collector(self) -> None:
        payment = {
            "payer_id": MY_USER_ID,
            "collector": {"id": OTHER_USER_ID},
            "operation_type": "money_transfer",
        }

        assert is_income(payment, MY_USER_ID) is False

    def test_returns_false_when_collector_is_missing(self) -> None:
        assert is_income({"id": 123}, MY_USER_ID) is False

    def test_does_not_use_operation_type_as_income_signal(self) -> None:
        payment = {
            "collector": {"id": OTHER_USER_ID},
            "operation_type": "account_fund",
        }

        assert is_income(payment, MY_USER_ID) is False

    def test_does_not_use_payment_method_id_as_income_signal(self) -> None:
        payment = {
            "collector": {"id": OTHER_USER_ID},
            "payment_method_id": "cvu",
        }

        assert is_income(payment, MY_USER_ID) is False
