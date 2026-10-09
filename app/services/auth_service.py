from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time


PBKDF2_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_session_token(user_id: int, secret_key: str, lifetime_seconds: int = 28_800) -> str:
    payload = {"user_id": user_id, "expires": int(time.time()) + lifetime_seconds}
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(secret_key.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}"


def read_session_token(token: str, secret_key: str) -> int | None:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(secret_key.encode(), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(supplied_signature)):
            return None
        payload = json.loads(_b64decode(encoded))
        if int(payload["expires"]) < int(time.time()):
            return None
        return int(payload["user_id"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None

