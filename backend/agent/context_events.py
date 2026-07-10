"""Interpret raw gap structure as narrative-worthy context events.

Only the most recent gap generates ReturnFromAbsence or CurrentlyAbsent — a
return from an absence 40 games ago is no longer context for current form. Older
gaps still emit ExtendedAbsence when long enough.
"""

from shared.schemas.context import (
    ContextEvent,
    ContextEventList,
    CurrentlyAbsent,
    ExtendedAbsence,
    ReturnFromAbsence,
)
from shared.schemas.gaps import GapEvent
from shared.schemas.stats import AggregatedStats

# Gap length at or above which we surface an ExtendedAbsence event.
_EXTENDED_ABSENCE_THRESHOLD = 5

_DATE_FORMAT = "%b %d"


def _format_date_range(start: str, end: str) -> str:
    return f"{start} - {end}"


def _extended_display(gap: GapEvent) -> str:
    start = gap.start_date.strftime(_DATE_FORMAT)
    end = gap.end_date.strftime(_DATE_FORMAT)
    return (
        f"Extended {gap.length}-game absence "
        f"({_format_date_range(start, end)})"
    )


def _return_display(gap: GapEvent) -> str:
    start = gap.start_date.strftime(_DATE_FORMAT)
    end = gap.end_date.strftime(_DATE_FORMAT)
    return (
        f"Returned from {gap.length}-game absence "
        f"({_format_date_range(start, end)})"
    )


def _currently_absent_display(gap: GapEvent) -> str:
    since = gap.start_date.strftime(_DATE_FORMAT)
    return f"Absent since {since} ({gap.length} games missed)"


def detect_context_events(
    gaps: list[GapEvent], stats: AggregatedStats
) -> ContextEventList:
    """Return context events derived from *gaps* interpreted against *stats*."""
    if stats.total_games == 0 or not gaps:
        return ContextEventList(events=[])

    sorted_gaps = sorted(gaps, key=lambda g: g.start_game_number)
    events: list[ContextEvent] = []

    for gap in sorted_gaps:
        if gap.length >= _EXTENDED_ABSENCE_THRESHOLD:
            events.append(
                ExtendedAbsence(
                    display=_extended_display(gap),
                    gap_length=gap.length,
                    start_date=gap.start_date,
                    end_date=gap.end_date,
                )
            )

    latest = sorted_gaps[-1]
    if latest.end_game_number == stats.total_games:
        events.append(
            CurrentlyAbsent(
                display=_currently_absent_display(latest),
                games_missed=latest.length,
                since_date=latest.start_date,
            )
        )
    else:
        events.append(
            ReturnFromAbsence(
                display=_return_display(latest),
                gap_length=latest.length,
                start_date=latest.start_date,
                end_date=latest.end_date,
            )
        )

    return ContextEventList(events=events)
