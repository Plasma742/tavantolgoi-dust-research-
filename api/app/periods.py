"""Date-window validation. All periods are UTC and end-exclusive, like EE filterDate."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from .errors import InvalidPeriod

MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


@dataclass(frozen=True)
class Period:
    start: date
    end_exclusive: date

    @property
    def days(self) -> int:
        return (self.end_exclusive - self.start).days

    def as_dict(self) -> dict[str, str | int]:
        return {
            "start_utc": f"{self.start.isoformat()}T00:00:00Z",
            "end_exclusive_utc": f"{self.end_exclusive.isoformat()}T00:00:00Z",
            "days": self.days,
        }


def today_utc() -> date:
    return datetime.now(UTC).date()


def month_period(month: str) -> Period:
    match = MONTH_RE.match(month)
    if not match:
        raise InvalidPeriod(f"'{month}' is not a YYYY-MM month.")
    year, mon = int(match.group(1)), int(match.group(2))
    start = date(year, mon, 1)
    end = date(year + (mon == 12), 1 if mon == 12 else mon + 1, 1)
    return Period(start, end)


def validate_window(
    start: date, end_exclusive: date, *, max_days: int, earliest: date, today: date | None = None
) -> Period:
    today = today or today_utc()
    if end_exclusive <= start:
        raise InvalidPeriod("end_exclusive must be after start.")
    if start < earliest:
        raise InvalidPeriod(f"start is before the dataset's first available date ({earliest.isoformat()}).")
    if end_exclusive > today:
        raise InvalidPeriod(
            "The period has not ended yet (end_exclusive is after today, UTC). Partial periods are not summarised."
        )
    period = Period(start, end_exclusive)
    if period.days > max_days:
        raise InvalidPeriod(f"Period is {period.days} days; the limit is {max_days} days.")
    return period


def validate_month_range(
    start_month: str, end_month: str, *, max_months: int, earliest: date, today: date | None = None
) -> list[tuple[str, Period]]:
    first = month_period(start_month)
    last = month_period(end_month)
    if last.start < first.start:
        raise InvalidPeriod("end_month must not be before start_month.")
    today = today or today_utc()
    if last.end_exclusive > today:
        raise InvalidPeriod(f"{end_month} has not ended yet (UTC). Only complete months are summarised.")
    if first.end_exclusive <= earliest:
        raise InvalidPeriod(f"start_month is before the dataset's first available date ({earliest.isoformat()}).")
    months: list[tuple[str, Period]] = []
    year, mon = first.start.year, first.start.month
    while True:
        label = f"{year:04d}-{mon:02d}"
        months.append((label, month_period(label)))
        if label == end_month:
            break
        year, mon = (year + 1, 1) if mon == 12 else (year, mon + 1)
        if len(months) > max_months:
            raise InvalidPeriod(f"Requested more than {max_months} months; split the request.")
    if len(months) > max_months:
        raise InvalidPeriod(f"Requested {len(months)} months; the limit is {max_months}.")
    return months
