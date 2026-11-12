import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

from . import config


def utc_now():
    return datetime.now(timezone.utc)


def iso(value=None):
    return (value or utc_now()).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value):
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def hash_password(password, salt=None, iterations=None):
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    iterations = int(iterations or config.PBKDF2_ITERATIONS)
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        iterations,
    )
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt_bytes).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_text)
        expected = base64.b64decode(digest_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            salt,
            int(iterations),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, base64.binascii.Error):
        return False


def new_token():
    return secrets.token_urlsafe(32)


def hash_token(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def session_expiry():
    return iso(utc_now() + timedelta(days=config.SESSION_DAYS))


def new_id(prefix):
    return f"{prefix}-{secrets.token_hex(5)}"


def initials(name):
    parts = [part for part in str(name or "").split() if part]
    return "".join(part[0] for part in parts[:2]).upper()


def slugify(value):
    text = "".join(
        character.lower() if character.isalnum() else "-"
        for character in str(value or "").strip()
    )
    return "-".join(part for part in text.split("-") if part)[:48] or "user"


def encrypt_totp_secret(secret):
    if not config.TWO_FACTOR_ENCRYPTION_KEY:
        raise RuntimeError("TOUCHLINE_2FA_ENCRYPTION_KEY is required to enable two-factor authentication")
    key = config.TWO_FACTOR_ENCRYPTION_KEY.encode("ascii")
    return Fernet(key).encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_totp_secret(ciphertext):
    if not config.TWO_FACTOR_ENCRYPTION_KEY or not ciphertext:
        return None
    try:
        key = config.TWO_FACTOR_ENCRYPTION_KEY.encode("ascii")
        return Fernet(key).decrypt(ciphertext.encode("ascii")).decode("ascii")
    except (ValueError, InvalidToken, UnicodeError):
        return None


def new_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_step(at=None, period=30):
    instant = time.time() if at is None else at.timestamp()
    return int(instant // period)


def totp_code(secret, at=None, period=30, digits=6):
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
    counter = totp_step(at, period)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10**digits)).zfill(digits)


def matching_totp_step(secret, code, at=None, window=1):
    if not isinstance(code, str) or not code.isdigit() or len(code) != 6:
        return None
    current = totp_step(at)
    for step in range(current - window, current + window + 1):
        candidate_time = datetime.fromtimestamp(step * 30, timezone.utc)
        if hmac.compare_digest(totp_code(secret, candidate_time), code):
            return step
    return None


def totp_uri(secret, email):
    label = quote(f"Touchline:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer=Touchline&algorithm=SHA1&digits=6&period=30"
