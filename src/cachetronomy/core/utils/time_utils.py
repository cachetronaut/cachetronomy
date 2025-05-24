from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)