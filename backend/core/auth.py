import base64
import hashlib
import hmac
import re
from typing import Optional

from .config import CLIENT_ID, CLIENT_SECRET


def format_phone_to_e164(phone: str) -> str:
    """
    Format phone number to E.164 format (+1XXXXXXXXXX)
    Strips all non-digit characters and prepends +1 for US numbers
    """
    digits_only = re.sub(r"\D", "", phone)
    if digits_only.startswith("1") and len(digits_only) == 11:
        return f"+{digits_only}"
    elif len(digits_only) == 10:
        return f"+1{digits_only}"
    else:
        raise ValueError(
            f"Invalid phone number format. Expected 10 digits, got {len(digits_only)}"
        )


def validate_phone_e164(phone: str) -> bool:
    """
    Validate that phone is in correct E.164 format for US numbers
    Format: +1XXXXXXXXXX (exactly 12 characters)
    """
    return bool(re.match(r"^\+1\d{10}$", phone))


def calculate_secret_hash(username: str) -> Optional[str]:
    """Calculate SECRET_HASH for Cognito operations."""
    if not CLIENT_SECRET:
        return None

    message = username + CLIENT_ID
    secret_hash = base64.b64encode(
        hmac.new(CLIENT_SECRET.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()
    return secret_hash


