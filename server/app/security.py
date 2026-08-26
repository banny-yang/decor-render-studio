import base64
import hashlib
import hmac
import os
import time

from .config import settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def _sign(payload: str) -> str:
    return hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_token(user_id: int) -> str:
    exp = int(time.time()) + settings.access_token_hours * 3600
    payload = f"{user_id}.{exp}"
    sig = _sign(payload)
    raw = f"{payload}.{sig}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def parse_token(token: str) -> int | None:
    """返回 user_id；无效或过期返回 None"""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        user_id, exp, sig = raw.rsplit(".", 2)
        payload = f"{user_id}.{exp}"
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        if int(exp) < time.time():
            return None
        return int(user_id)
    except Exception:
        return None
