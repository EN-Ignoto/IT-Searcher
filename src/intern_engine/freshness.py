"""Expiry uses the employer's publish date, falling back to first discovery."""
from datetime import UTC, date, datetime, timedelta


def expired(posted_at: str | None, first_seen_at: str | None, days: int,
            *, now: datetime | None = None) -> bool:
    if not days:
        return False
    reference = now or datetime.now(UTC)
    for value in (posted_at, first_seen_at):
        try:
            day = date.fromisoformat((value or '')[:10])
        except (ValueError, TypeError):
            continue
        return day < reference.date() - timedelta(days=days)
    return False  # Newly discovered undated roles start their clock in the store.
