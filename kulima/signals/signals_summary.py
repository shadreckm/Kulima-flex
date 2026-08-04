"""Helper functions for summarising SIGNALS collections (Phase 5B).

These utilities operate purely on the Signal domain model and can be
used by any UI or orchestrator layer.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from kulima.signals.models import Signal, SignalLevel, SignalCategory


def count_signals_by_level(signals: Iterable[Signal]) -> dict[SignalLevel, int]:
    """Return a mapping from SignalLevel → count.

    Levels with zero occurrences are omitted from the result.
    """

    counter: Counter[SignalLevel] = Counter()
    for s in signals:
        counter[s.level] += 1
    return dict(counter)


def count_signals_by_category(signals: Iterable[Signal]) -> dict[SignalCategory, int]:
    """Return a mapping from SignalCategory → count.

    Categories with zero occurrences are omitted from the result.
    """

    counter: Counter[SignalCategory] = Counter()
    for s in signals:
        counter[s.category] += 1
    return dict(counter)


_LEVEL_PRIORITY: dict[SignalLevel, int] = {
    SignalLevel.CRITICAL: 0,
    SignalLevel.HIGH: 1,
    SignalLevel.MEDIUM: 2,
    SignalLevel.LOW: 3,
}


def highest_priority_signals(
    signals: Iterable[Signal],
    *,
    limit: int | None = 5,
) -> list[Signal]:
    """Return the highest-priority signals from the collection.

    Ordering rules:
    - Primary: SignalLevel (CRITICAL → HIGH → MEDIUM → LOW)
    - Secondary: confidence (descending)
    - Tertiary: title (ascending, to keep ordering stable)
    """

    def _sort_key(s: Signal) -> tuple[int, float, str]:
        level_rank = _LEVEL_PRIORITY.get(s.level, 99)
        # Negative confidence so higher confidence comes first.
        return (level_rank, -s.confidence, s.title or "")

    ordered = sorted(list(signals), key=_sort_key)
    if limit is not None and limit >= 0:
        return ordered[:limit]
    return ordered
