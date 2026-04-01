from enum import Enum
from typing import Any, Optional, Dict


class AuthFailureReason(Enum):
    INVALID_CREDENTIALS = "Invalid credentials"

class AuthenticationError(Exception):
    def __init__(self, reason:AuthFailureReason, detail:str = None):
        self.reason = reason
        self.detail = detail
        super().__init__(self.detail)


class Principal:
    def __init__(self, client_ip:str):
        self.client_ip = client_ip


def authenticate(client_ip:str, request:Any, context:Optional[Dict[str, Any]]) -> Principal:
    try:
        return Principal(client_ip)
    except Exception as ex:
        raise AuthenticationError(AuthFailureReason.INVALID_CREDENTIALS, "Invalid credentials") from ex