import re
from datetime import date, datetime, timedelta, timezone

from .errors import ApiError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}\Z")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\Z")


def require_object(value):
    if not isinstance(value, dict):
        raise ApiError(400, "invalid_body", "Request body must be a JSON object.")
    return value


def text(data, key, *, required=True, minimum=1, maximum=500, default=None, label=None):
    value = data.get(key, default)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ApiError(400, "missing_field", f"{label or key} is required.", {key: "required"})
        return default
    if not isinstance(value, str):
        raise ApiError(400, "invalid_field", f"{label or key} must be text.", {key: "type"})
    value = value.strip()
    if len(value) < minimum:
        raise ApiError(400, "invalid_field", f"{label or key} is too short.", {key: "length"})
    if len(value) > maximum:
        raise ApiError(400, "invalid_field", f"{label or key} is too long.", {key: "length"})
    return value


def integer(data, key, *, required=True, minimum=None, maximum=None, default=None, label=None):
    value = data.get(key, default)
    if value is None:
        if required:
            raise ApiError(400, "missing_field", f"{label or key} is required.", {key: "required"})
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(400, "invalid_field", f"{label or key} must be a number.", {key: "type"})
    value = int(value)
    if minimum is not None and value < minimum:
        raise ApiError(400, "invalid_field", f"{label or key} must be at least {minimum}.", {key: "range"})
    if maximum is not None and value > maximum:
        raise ApiError(400, "invalid_field", f"{label or key} must be at most {maximum}.", {key: "range"})
    return value


def number(data, key, *, required=True, minimum=None, maximum=None, default=None, label=None):
    value = data.get(key, default)
    if value is None:
        if required:
            raise ApiError(400, "missing_field", f"{label or key} is required.", {key: "required"})
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(400, "invalid_field", f"{label or key} must be a number.", {key: "type"})
    value = float(value)
    if value != value:
        raise ApiError(400, "invalid_field", f"{label or key} must be a valid number.", {key: "type"})
    if minimum is not None and value < minimum:
        raise ApiError(400, "invalid_field", f"{label or key} must be at least {minimum}.", {key: "range"})
    if maximum is not None and value > maximum:
        raise ApiError(400, "invalid_field", f"{label or key} must be at most {maximum}.", {key: "range"})
    return value


def choice(data, key, options, *, required=True, default=None, label=None):
    value = data.get(key, default)
    if value is None:
        if required:
            raise ApiError(400, "missing_field", f"{label or key} is required.", {key: "required"})
        return default
    if not isinstance(value, str) or value not in options:
        raise ApiError(
            400,
            "invalid_field",
            f"{label or key} must be one of: {', '.join(sorted(options))}.",
            {key: "enum"},
        )
    return value


def boolean(data, key, *, default=False, label=None):
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise ApiError(400, "invalid_field", f"{label or key} must be a boolean.", {key: "type"})


def email(data, key="email"):
    value = text(data, key, required=True, minimum=3, maximum=180, label="Email").lower()
    if not EMAIL_RE.match(value):
        raise ApiError(400, "invalid_field", "Enter a valid email address.", {key: "format"})
    return value


def password(data, key="password"):
    value = data.get(key)
    if not isinstance(value, str) or len(value) < 8:
        raise ApiError(400, "invalid_field", "Password must be at least 8 characters.", {key: "length"})
    if len(value) > 128:
        raise ApiError(400, "invalid_field", "Password is too long.", {key: "length"})
    return value


def text_list(data, key, *, minimum=1, maximum=8, item_maximum=160):
    value = data.get(key)
    if not isinstance(value, list):
        raise ApiError(400, "invalid_field", f"{key} must be a list.", {key: "type"})
    if len(value) < minimum or len(value) > maximum:
        raise ApiError(400, "invalid_field", f"{key} must contain {minimum}-{maximum} items.", {key: "length"})
    output = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ApiError(400, "invalid_field", f"Every item in {key} must be text.", {key: "type"})
        item = item.strip()
        if len(item) > item_maximum:
            raise ApiError(400, "invalid_field", f"An item in {key} is too long.", {key: "length"})
        output.append(item)
    return output


def valid_id(value, key="id"):
    if not isinstance(value, str) or not ID_RE.match(value):
        raise ApiError(400, "invalid_id", f"Invalid {key}.")
    return value


def iso_date(data, key, *, required=False, default=None, label=None, minimum_age=None, maximum_age=None):
    """Validate a YYYY-MM-DD calendar date that is not in the future."""
    value = data.get(key, default)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ApiError(400, "missing_field", f"{label or key} is required.", {key: "required"})
        return default
    if not isinstance(value, str) or not DATE_RE.match(value.strip()):
        raise ApiError(400, "invalid_field", f"{label or key} must be a date like 2011-04-26.", {key: "format"})
    value = value.strip()
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ApiError(400, "invalid_field", f"{label or key} is not a real calendar date.", {key: "format"})
    today = date.today()
    if parsed > today:
        raise ApiError(400, "invalid_field", f"{label or key} cannot be in the future.", {key: "range"})
    age = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
    if minimum_age is not None and age < minimum_age:
        raise ApiError(400, "invalid_field", f"{label or key} gives an age under {minimum_age}.", {key: "range"})
    if maximum_age is not None and age > maximum_age:
        raise ApiError(400, "invalid_field", f"{label or key} gives an age over {maximum_age}.", {key: "range"})
    return value


CALENDAR_MAX_DAYS = 93


def _date_value(query, key, default):
    raw = (query.get(key) or [None])[0]
    if raw is None or raw == "":
        return default
    if not isinstance(raw, str) or not DATE_RE.match(raw):
        raise ApiError(400, "invalid_field", f"{key} must be a date like 2026-11-07.", {key: "format"})
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        raise ApiError(400, "invalid_field", f"{key} is not a real calendar date.", {key: "format"})


def calendar_range(query):
    """Inclusive UTC date range for the calendar. Defaults to the current month."""
    today = datetime.now(timezone.utc).date()
    first_of_month = today.replace(day=1)
    next_month = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    start = _date_value(query, "from", first_of_month.isoformat())
    end = _date_value(query, "to", (next_month - timedelta(days=1)).isoformat())
    if end < start:
        raise ApiError(400, "invalid_range", "The end date must be on or after the start date.", {"to": "range"})
    if (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 > CALENDAR_MAX_DAYS:
        raise ApiError(400, "range_too_large", f"The calendar can show at most {CALENDAR_MAX_DAYS} days at once.", {"to": "range"})
    return start, end
