import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_local_env(path):
    """Load simple KEY=value entries without overriding the process environment."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_local_env(ROOT / ".env")

DB_PATH = Path(os.environ.get("TOUCHLINE_DB", ROOT / "data" / "touchline.db")).resolve()
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "4173"))
ADMIN_PATH = os.environ.get("TOUCHLINE_ADMIN_PATH", "").rstrip("/")
ADMIN_NAME = os.environ.get("TOUCHLINE_ADMIN_NAME", "Super Admin")
ADMIN_EMAIL = os.environ.get("TOUCHLINE_ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.environ.get("TOUCHLINE_ADMIN_PASSWORD", "")
SESSION_DAYS = int(os.environ.get("TOUCHLINE_SESSION_DAYS", "30"))
MAX_BODY_BYTES = int(os.environ.get("TOUCHLINE_MAX_BODY", "262144"))
PBKDF2_ITERATIONS = int(os.environ.get("TOUCHLINE_PBKDF2_ITERATIONS", "180000"))
CORS_ORIGINS = {
    origin.strip()
    for origin in os.environ.get(
        "TOUCHLINE_CORS_ORIGINS",
        "http://127.0.0.1:4173,http://localhost:4173,capacitor://localhost,http://localhost,https://localhost",
    ).split(",")
    if origin.strip()
}

LOGIN_FAIL_LIMIT_PER_EMAIL = int(os.environ.get("TOUCHLINE_LOGIN_FAILS_PER_EMAIL", "5"))
LOGIN_FAIL_LIMIT_PER_IP = int(os.environ.get("TOUCHLINE_LOGIN_FAILS_PER_IP", "20"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("TOUCHLINE_LOGIN_WINDOW", "300"))
REGISTER_LIMIT_PER_IP = int(os.environ.get("TOUCHLINE_REGISTER_PER_IP", "20"))
REGISTER_WINDOW_SECONDS = int(os.environ.get("TOUCHLINE_REGISTER_WINDOW", "3600"))
TRUST_PROXY = os.environ.get("TOUCHLINE_TRUST_PROXY", "0") in {"1", "true", "True"}
APP_BASE_URL = os.environ.get("TOUCHLINE_APP_BASE_URL", "http://127.0.0.1:4173").rstrip("/")
GOOGLE_CLIENT_ID = os.environ.get("TOUCHLINE_GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("TOUCHLINE_GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.environ.get("TOUCHLINE_GOOGLE_REDIRECT_URI", f"{APP_BASE_URL}/").strip()
TIMEZONE = os.environ.get("TOUCHLINE_TIMEZONE", "America/New_York")
SMTP_HOST = os.environ.get("TOUCHLINE_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("TOUCHLINE_SMTP_PORT", "587"))
SMTP_TIMEOUT = int(os.environ.get("TOUCHLINE_SMTP_TIMEOUT", "30"))
SMTP_USERNAME = os.environ.get("TOUCHLINE_SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("TOUCHLINE_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("TOUCHLINE_SMTP_FROM", SMTP_USERNAME or "no-reply@touchline.invalid")
SMTP_STARTTLS = os.environ.get("TOUCHLINE_SMTP_STARTTLS", "1") not in {"0", "false", "False"}
TWO_FACTOR_ENCRYPTION_KEY = os.environ.get("TOUCHLINE_2FA_ENCRYPTION_KEY", "")
AUTH_TOKEN_DAYS = int(os.environ.get("TOUCHLINE_AUTH_TOKEN_DAYS", "1"))
AUTH_EMAIL_LIMIT_PER_IP = int(os.environ.get("TOUCHLINE_AUTH_EMAIL_LIMIT_PER_IP", "10"))
AUTH_EMAIL_WINDOW_SECONDS = int(os.environ.get("TOUCHLINE_AUTH_EMAIL_WINDOW", "3600"))
