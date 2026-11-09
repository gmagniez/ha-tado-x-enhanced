"""Home-scoped holiday state, refresh scheduling and safe activation."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


class HolidayModeManager:
    """Maintain a single holiday snapshot per Tado home."""

    def __init__(self, hass, coordinator, enabled: bool = True) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.poll_enabled = enabled
        self.data: dict[str, Any] | None = None
        self._unsub_events = []
        self._lock = asyncio.Lock()

    @property
    def status(self) -> str | None:
        data = self.data
        if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool):
            return None
        if not data["enabled"]:
            return "off"
        now = dt_util.utcnow()
        start, end = parse_time(data.get("startDate")), parse_time(data.get("endDate"))
        if start is None or end is None or end <= start:
            return None
        if start > now:
            return "scheduled"
        if end <= now:
            return "ended"
        # The API active flag can lag a scheduled transition; the known
        # date interval determines the effective status between refreshes.
        return "active"

    async def start(self) -> None:
        try:
            await self.refresh(source="initial")
        except Exception as err:  # Holiday API may not be available on every account.
            _LOGGER.warning("Holiday mode initial read failed for home %s: %s", self.coordinator.home_id, err)
        self.configure_polling(self.poll_enabled)

    def configure_polling(self, enabled: bool) -> None:
        """Enable/disable coordinator-driven checks, preserving boundary events."""
        if self.poll_enabled != enabled:
            self.coordinator.invalidate_supplementary("holiday_mode")
        self.poll_enabled = enabled
        _LOGGER.debug(
            "Holiday Mode polling configured: enabled=%s, multiplier=%s, home_id=%s",
            enabled, self.coordinator.supplementary_poll_multiplier, self.coordinator.home_id,
        )

    async def _periodic(self, now) -> None:
        try:
            await self.refresh(source="boundary")
        except Exception as err:
            _LOGGER.warning("Holiday mode refresh failed for home %s: %s", self.coordinator.home_id, err)

    async def refresh(self, *, notify: bool = True, source: str = "manual") -> None:
        """Fetch Holiday Mode directly; source identifies why the read occurred."""
        async with self._lock:
            _LOGGER.debug(
                "Holiday Mode API request: source=%s (home_id=%s)",
                source, self.coordinator.home_id,
            )
            try:
                data = await self.coordinator.api.get_holiday_mode()
            except Exception:
                _LOGGER.exception(
                    "Holiday Mode API request failed: source=%s (home_id=%s)",
                    source, self.coordinator.home_id,
                )
                raise
            if not isinstance(data, dict) or "enabled" not in data:
                raise ValueError("Holiday mode API response is incomplete")
            self.data = data
            self._schedule_events()
            if notify:
                self.coordinator.async_update_listeners()
            self.coordinator.mark_supplementary_success("holiday_mode", self.data)
            _LOGGER.debug(
                "Holiday Mode API request succeeded: source=%s (home_id=%s)",
                source, self.coordinator.home_id,
            )

    def _schedule_events(self) -> None:
        for unsubscribe in self._unsub_events:
            unsubscribe()
        self._unsub_events.clear()
        if not self.data or not self.data.get("enabled"):
            return
        now = dt_util.utcnow()
        for field in ("startDate", "endDate"):
            when = parse_time(self.data.get(field))
            if when and when > now:
                self._unsub_events.append(async_track_point_in_utc_time(self.hass, self._at_boundary, when))

    async def _at_boundary(self, now) -> None:
        # Notify entities promptly, even if the confirming API request fails.
        self.coordinator.async_update_listeners()
        await self._periodic(now)
        await self.coordinator.async_request_refresh()

    async def set_enabled(self, enabled: bool) -> None:
        # Always obtain the latest settings before a read-modify-write.
        current = await self.coordinator.api.get_holiday_mode()
        if not isinstance(current, dict) or not isinstance(current.get("roomSettings"), dict):
            raise ValueError("Cannot safely modify holiday mode without its existing room settings")
        start = end = None
        if enabled:
            stored_start = parse_time(current.get("startDate"))
            stored_end = parse_time(current.get("endDate"))
            now = dt_util.utcnow()
            if not stored_start or not stored_end or stored_end <= now or stored_end <= stored_start:
                # Tado accepts only full half-hour boundaries. Round down in UTC
                # to make the new holiday active immediately.
                start_dt = now.replace(
                    minute=(now.minute // 30) * 30, second=0, microsecond=0
                )
                end_dt = start_dt + timedelta(days=7)
                start = start_dt.isoformat(timespec="seconds").replace("+00:00", "Z")
                end = end_dt.isoformat(timespec="seconds").replace("+00:00", "Z")
        await self.coordinator.api.set_holiday_mode(enabled, start, end)
        await self.refresh(source="action")
        await self.coordinator.async_request_refresh()

    def stop(self) -> None:
        for unsubscribe in self._unsub_events:
            unsubscribe()
        self._unsub_events.clear()
