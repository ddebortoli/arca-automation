from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class AfipCredentials:
    token: str
    sign: str
    expiration: datetime


class AfipAuthenticationError(Exception):
    pass