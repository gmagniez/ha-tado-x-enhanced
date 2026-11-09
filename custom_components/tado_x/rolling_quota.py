"""Bounded rolling projection from Tado's server-reported quota counter.

No extra API requests are made. This is an in-memory per-client estimate.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta

WINDOW = timedelta(minutes=60)
MIN_SPAN = timedelta(minutes=10)
SAMPLE_SPACING = timedelta(seconds=15)


class RollingQuotaEstimate:
    """Track observed consumption, isolating resets and quota changes."""

    def __init__(self) -> None:
        self._max_age = timedelta(minutes=2)
        self._samples: deque[tuple[datetime, int]] = deque()
        self._quota: int | None = None
        self._last_used: int | None = None

    def observe(self, when: datetime, quota: int, used: int) -> None:
        """Record valid server quota data without retaining every HTTP response."""
        if when.tzinfo is None or quota <= 0 or not 0 <= used <= quota:
            return
        if (self._quota != quota or
                (self._last_used is not None and used < self._last_used) or
                (self._samples and when < self._samples[-1][0])):
            # Includes daily reset and downward corrections: never span either.
            self._samples.clear()
        self._quota = quota
        self._last_used = used
        cutoff = when - WINDOW
        # Keep the last point just before the window boundary for interpolation.
        while len(self._samples) > 1 and self._samples[1][0] <= cutoff:
            self._samples.popleft()
        if self._samples and when - self._samples[-1][0] < SAMPLE_SPACING:
            # Refresh the most recent sample; bursts should count as usage.
            self._samples[-1] = (when, used)
        else:
            self._samples.append((when, used))

    def set_main_poll_interval(self, seconds: int) -> None:
        """Accept legitimate slower main polling without retaining stale data forever."""
        if seconds > 0:
            self._max_age = max(timedelta(minutes=2), timedelta(seconds=seconds * 1.5))

    def estimate(self, now: datetime) -> float | None:
        """Extrapolate recent consumption to 24h, as a quota percentage."""
        if self._quota is None or len(self._samples) < 2:
            return None
        # Avoid stale projections when quota readings have stopped arriving.
        if now - self._samples[-1][0] > self._max_age:
            return None
        cutoff = now - WINDOW
        points = list(self._samples)
        if points[0][0] < cutoff:
            # Linear interpolation between the two observations around cutoff.
            before, after = points[0], points[1]
            seconds = (after[0] - before[0]).total_seconds()
            if seconds <= 0:
                return None
            fraction = (cutoff - before[0]).total_seconds() / seconds
            first_used = before[1] + fraction * (after[1] - before[1])
            first_time = cutoff
        else:
            first_time, first_used = points[0]
        last_time, last_used = points[-1]
        span = (last_time - first_time).total_seconds()
        if span < MIN_SPAN.total_seconds() or last_used < first_used:
            return None
        return round((last_used - first_used) * 86400 / span / self._quota * 100, 1)
