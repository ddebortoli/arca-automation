"""Income detection for MercadoPago payments.

Business rule: a payment is income when the current user is the collector
(the party that received the money).
"""


def get_collector_id(payment: dict) -> int | str | None:
    """Extract the collector identifier from a raw MercadoPago payment payload."""
    collector_id = payment.get("collector_id")
    if collector_id is not None:
        return collector_id

    collector = payment.get("collector") or {}
    return collector.get("id")


def is_income(payment: dict, my_user_id: int) -> bool:
    """Return True when *my_user_id* is the collector of *payment*.

    Args:
        payment: Raw payment dict from the MercadoPago Payments API.
        my_user_id: The authenticated MercadoPago user ID.

    Returns:
        True if the payment represents money received by the current user.
    """
    collector_id = get_collector_id(payment)
    if collector_id is None:
        return False

    return str(collector_id) == str(my_user_id)
