"""Theoretical Tado API quota consumption from configured periodic work.

Pure calculation: does not issue requests. Costs are estimates, not a quota cap.
"""
from __future__ import annotations

from dataclasses import dataclass

SECONDS_PER_DAY = 86400


@dataclass(frozen=True)
class ApiProjection:
    """Expected periodic API calls per day, excluding user-triggered activity."""

    main: float
    supplementary: float
    schedule: float
    total: float
    percentage: float


def project_daily_api_usage(
    *, quota: int, main_interval: int, multiplier: int,
    weather: bool, air_comfort: bool, running_times: bool,
    flow_temp: bool, holiday_mode: bool, mobile_devices: bool,
    hot_water: bool, schedule_enabled: bool, schedule_interval: int,
    room_count: int,
) -> ApiProjection | None:
    """Estimate periodic calls from the active per-home configuration.

    Main: three mandatory requests, plus enabled mobile/DHW reads.
    Supplementary: one request per enabled feature per eligible poll.
    Schedule: approximately two reads per room per independent check.
    Fractions represent long-run daily averages, not exact daily boundaries.
    """
    if (quota <= 0 or main_interval <= 0 or multiplier <= 0
            or (schedule_enabled and schedule_interval <= 0) or room_count < 0):
        return None
    main = SECONDS_PER_DAY / main_interval * (3 + int(mobile_devices) + int(hot_water))
    supplementary_count = sum((weather, air_comfort, running_times, flow_temp, holiday_mode))
    supplementary = SECONDS_PER_DAY / (main_interval * multiplier) * supplementary_count
    schedule = (SECONDS_PER_DAY / schedule_interval * 2 * room_count
                if schedule_enabled else 0.0)
    total = main + supplementary + schedule
    return ApiProjection(main, supplementary, schedule, total, 100 * total / quota)
