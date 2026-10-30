from datetime import date

from .constants import MAX_AGE_DAYS


def validator(name: str, low: float, hi: float):
    """Reject implausible or stale values; each source applies this to its own data."""

    def validate(value: float, as_of: date) -> float:
        if not low <= value <= hi:
            raise ValueError(f"{name} out of range: {value}")
        if (date.today() - as_of).days > MAX_AGE_DAYS:
            raise ValueError(f"stale {name} date: {as_of}")
        return value

    return validate


def normalize_clp(raw: str) -> float:
    """Chilean number format: '41.242,32' -> 41242.32."""
    return float(raw.replace(".", "").replace(",", "."))
