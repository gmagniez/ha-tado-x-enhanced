"""API client for Tado X."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import ssl

from homeassistant.util.ssl import get_default_context

from .rolling_quota import RollingQuotaEstimate

from .const import (
    TADO_AUTH_URL,
    TADO_CLIENT_ID,
    TADO_EIQ_API_URL,
    TADO_HOPS_API_URL,
    TADO_MINDER_API_URL,
    TADO_MY_API_URL,
    TADO_TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)
_USE_ROOM_DEFAULT = object()

class TadoXAuthError(Exception):
    """Exception for authentication errors."""


class TadoXApiError(Exception):
    """Exception for API errors."""


class TadoXRateLimitError(TadoXApiError):
    """Exception for rate limit (429) errors."""

    def __init__(self, message: str, reset_time: datetime | None = None):
        """Initialize with optional reset time."""
        super().__init__(message)
        self.reset_time = reset_time


class TadoXApi:
    """Tado X API client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expiry: datetime | None = None,
        api_calls_today: int = 0,
        api_reset_time: datetime | None = None,
        api_last_reset: datetime | None = None,
        api_previous_used: int | None = None,
        api_previous_quota: int | None = None,
        has_auto_assist: bool = False,
        on_token_refresh: callable | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = token_expiry
        self._home_id: int | None = None
        self._has_auto_assist = has_auto_assist
        self._on_token_refresh = on_token_refresh
        self._token_lock = asyncio.Lock()
        self._get_room_control_defaults = None

        # The server's daily quota counter, not a fixed UTC clock, determines
        # the reset. The old fixed-time value is intentionally not migrated.
        self._api_calls_today = max(0, api_calls_today)
        self._api_last_reset = api_last_reset if (
            api_last_reset is not None and api_last_reset.tzinfo is not None
        ) else None
        self._api_call_reset_time = (
            self._api_last_reset + timedelta(hours=24)
            if self._api_last_reset is not None else None
        )
        self._api_previous_used = api_previous_used
        self._api_previous_quota = api_previous_quota
        self._api_last_observed_at: datetime | None = None
        self._api_quota_limit: int | None = None
        self._api_quota_remaining: int | None = None
        self._rolling_quota = RollingQuotaEstimate()

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Return the current refresh token."""
        return self._refresh_token

    @property
    def token_expiry(self) -> datetime | None:
        """Return the token expiry time."""
        return self._token_expiry

    @property
    def home_id(self) -> int | None:
        """Return the home ID."""
        return self._home_id

    @home_id.setter
    def home_id(self, value: int) -> None:
        """Set the home ID."""
        self._home_id = value

    @property
    def api_calls_today(self) -> int:
        """Return number of API calls made today."""
        return self._api_calls_today

    @property
    def api_reset_time(self) -> datetime | None:
        """Return when the API quota resets."""
        return self._api_call_reset_time

    @property
    def api_last_reset(self) -> datetime | None:
        """Most recently observed server quota rollover."""
        return self._api_last_reset

    @property
    def api_previous_used(self) -> int | None:
        return self._api_previous_used

    @property
    def api_previous_quota(self) -> int | None:
        return self._api_previous_quota

    @property
    def api_last_observed_at(self) -> datetime | None:
        return self._api_last_observed_at

    @property
    def has_auto_assist(self) -> bool:
        """Return whether user has Auto-Assist subscription."""
        return self._has_auto_assist

    @has_auto_assist.setter
    def has_auto_assist(self, value: bool) -> None:
        """Set whether user has Auto-Assist subscription."""
        self._has_auto_assist = value

    @property
    def api_quota_limit(self) -> int | None:
        """Return the API quota limit from headers (if available)."""
        return self._api_quota_limit

    @property
    def api_quota_remaining(self) -> int | None:
        """Return the API quota remaining from headers (if available)."""
        return self._api_quota_remaining

    @property
    def api_rolling_daily_usage(self) -> float | None:
        """Projected daily quota usage from the last 60 minutes of observations."""
        return self._rolling_quota.estimate(datetime.now(timezone.utc))

    def configure_quota_observation_interval(self, seconds: int) -> None:
        """Allow rolling observations to remain fresh at slower polling rates."""
        self._rolling_quota.set_main_poll_interval(seconds)

    def _observe_quota_usage(self, quota: int, remaining: int) -> None:
        """Learn the server's daily reset from a genuine quota-counter drop.

        Ignore counter changes caused by a different quota tier and small
        fluctuations. The observation time is an approximation bounded by
        consecutive requests, not an exact server-supplied reset timestamp.
        """
        if quota <= 0 or not 0 <= remaining <= quota:
            return
        now = datetime.now(timezone.utc)
        used = quota - remaining
        previous = self._api_previous_used
        previous_quota = self._api_previous_quota
        if previous is not None and previous_quota == quota:
            # A reset is a substantial drop to a low counter, not just a
            # decrement due to server-side corrections or stale responses.
            low = max(5, int(quota * 0.02))
            significant = max(10, int(quota * 0.05))
            if used <= low and previous - used >= significant:
                self._api_last_reset = now
                self._api_call_reset_time = now + timedelta(hours=24)
                _LOGGER.info(
                    "Observed Tado API quota reset (previous=%s, now=%s, quota=%s)",
                    previous, used, quota,
                )
        self._rolling_quota.observe(now, quota, used)
        self._api_previous_used = used
        self._api_previous_quota = quota
        self._api_last_observed_at = now

    def _parse_rate_limit_headers(self, headers: dict) -> None:
        """Parse rate limit information from Tado API response headers.

        Tado returns rate limit info in these headers:
        - ratelimit-policy: "perday";q=20000;w=86400 (q=quota limit, w=window in seconds)
        - ratelimit: "perday";r=17833 (r=remaining requests)
        """
        import re

        # Parse ratelimit-policy header for quota limit
        policy_header = headers.get("ratelimit-policy", "")
        if policy_header:
            # Extract q=NUMBER from the header
            quota_match = re.search(r"q=(\d+)", policy_header)
            if quota_match:
                self._api_quota_limit = int(quota_match.group(1))
                # Note: We no longer auto-detect Auto-Assist based on quota headers
                # The user's manual setting in options should be respected
                # API header values are used for display purposes only

        # Parse ratelimit header for remaining requests
        ratelimit_header = headers.get("ratelimit", "")
        if ratelimit_header:
            # Extract r=NUMBER from the header
            remaining_match = re.search(r"r=(\d+)", ratelimit_header)
            if remaining_match:
                self._api_quota_remaining = int(remaining_match.group(1))
                if self._api_quota_limit is not None:
                    self._observe_quota_usage(
                        self._api_quota_limit, self._api_quota_remaining
                    )

    async def start_device_auth(self) -> dict[str, Any]:
        """Start the device authorization flow.

        Returns a dict with device_code, user_code, verification_uri, etc.
        """
        _LOGGER.warning("Starting device authorization flow")
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)

        # Reuse Home Assistant's SSL context; do not load CA certificates on the event loop.
        ssl_context = get_default_context()

        # Create a dedicated session for auth to ensure timeout is respected
        connector = aiohttp.TCPConnector(force_close=True, ssl=ssl_context)
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
        ) as auth_session:
            try:
                _LOGGER.warning("Sending request to %s", TADO_AUTH_URL)
                async with auth_session.post(
                    TADO_AUTH_URL,
                    data={
                        "client_id": TADO_CLIENT_ID,
                        "scope": "offline_access",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    _LOGGER.warning("Device auth response status: %s", response.status)
                    if response.status != 200:
                        text = await response.text()
                        _LOGGER.error("Failed to start device auth: %s - %s", response.status, text)
                        raise TadoXAuthError(f"Failed to start device auth: {response.status}")
                    result = await response.json()
                    _LOGGER.debug("Device authorization request succeeded")
                    return result
            except asyncio.TimeoutError as err:
                _LOGGER.error("Timeout during device auth request (30s)")
                raise TadoXAuthError("Timeout during device auth request") from err
            except aiohttp.ClientError as err:
                _LOGGER.error("Network error during device auth: %s (type: %s)", err, type(err).__name__)
                raise TadoXAuthError(f"Network error: {err}") from err
            except ssl.SSLError as err:
                _LOGGER.error("SSL error during device auth: %s", err)
                raise TadoXAuthError(f"SSL error: {err}") from err
            except Exception as err:
                _LOGGER.error("Unexpected error during device auth: %s (type: %s)", err, type(err).__name__)
                raise TadoXAuthError(f"Unexpected error: {err}") from err

    async def poll_for_token(self, device_code: str, interval: int = 5, timeout: int = 300) -> bool:
        """Poll for the access token after user authorizes.

        Returns True if successful, False if timed out.
        """
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < timeout:
            try:
                async with self._session.post(
                    TADO_TOKEN_URL,
                    data={
                        "client_id": TADO_CLIENT_ID,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    data = await response.json()

                    if response.status == 200:
                        self._access_token = data["access_token"]
                        self._refresh_token = data.get("refresh_token")
                        expires_in = data.get("expires_in", 600)
                        self._token_expiry = datetime.now() + timedelta(seconds=expires_in)
                        return True

                    # Authorization pending, continue polling
                    if data.get("error") == "authorization_pending":
                        await asyncio.sleep(interval)
                        continue

                    # Other error
                    _LOGGER.error("Token error: %s", data)
                    raise TadoXAuthError(f"Token error: {data.get('error_description', data.get('error'))}")

            except aiohttp.ClientError as err:
                _LOGGER.error("Network error during token polling: %s", err)
                await asyncio.sleep(interval)

        return False

    async def refresh_access_token(self) -> bool:
        """Explicitly refresh credentials, serialised with automatic refreshes."""
        async with self._token_lock:
            return await self._refresh_access_token_locked(reason="explicit")

    async def _refresh_access_token_locked(self, reason: str) -> bool:
        """Rotate tokens. Caller must hold _token_lock."""
        if not self._refresh_token:
            raise TadoXAuthError("No refresh token available")

        try:
            async with self._session.post(
                TADO_TOKEN_URL,
                data={
                    "client_id": TADO_CLIENT_ID,
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if response.status != 200:
                    # Avoid logging OAuth response bodies, which may contain sensitive data.
                    if response.status in (408, 429) or response.status >= 500:
                        raise TadoXApiError(f"Token server temporarily unavailable: HTTP {response.status}")
                    if response.status in (400, 401):
                        try:
                            error_data = await response.json()
                        except (ValueError, aiohttp.ContentTypeError):
                            error_data = {}
                        error_code = error_data.get("error") if isinstance(error_data, dict) else None
                        if response.status == 401 or error_code in (
                            "invalid_grant", "invalid_client", "refresh_token_not_found"
                        ):
                            raise TadoXAuthError(f"Token refresh rejected: HTTP {response.status}")
                    raise TadoXApiError(f"Token refresh failed: HTTP {response.status}")

                data = await response.json()
                access_token = data.get("access_token")
                if not access_token:
                    raise TadoXApiError("Token server returned no access token")
                new_refresh_token = data.get("refresh_token", self._refresh_token)
                expires_in = data.get("expires_in", 600)
                # Update together before persisting the rotated credentials.
                self._access_token = access_token
                self._refresh_token = new_refresh_token
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in)
                if self._on_token_refresh:
                    self._on_token_refresh()
                _LOGGER.debug("Token refresh successful: home_id=%s, reason=%s, expires_in=%ss", self._home_id, reason, expires_in)
                return True
        except asyncio.TimeoutError as err:
            raise TadoXApiError("Timeout during token refresh") from err
        except aiohttp.ClientError as err:
            raise TadoXApiError(f"Network error during token refresh: {err}") from err

    def _token_is_stale(self) -> bool:
        """Refresh missing/unknown expiry or tokens expiring within 60 seconds."""
        return self._token_expiry is None or datetime.now() >= self._token_expiry - timedelta(seconds=60)

    async def _ensure_valid_token(self) -> None:
        """Ensure a usable access token, avoiding simultaneous rotations."""
        if self._access_token and not self._token_is_stale():
            return
        async with self._token_lock:
            if not self._access_token or self._token_is_stale():
                await self._refresh_access_token_locked(reason="expiry" if self._access_token else "missing_token")

    async def _refresh_after_401(self, rejected_token: str | None) -> None:
        """Refresh only if the token rejected by the server is still current."""
        async with self._token_lock:
            if self._access_token == rejected_token:
                await self._refresh_access_token_locked(reason="http_401")

    async def _request(
        self,
        method: str,
        url: str,
        json_data: dict | None = None,
    ) -> dict | list | None:
        """Make an authenticated API request."""
        await self._ensure_valid_token()

        # Track API call
        self._api_calls_today += 1

        sent_token = self._access_token
        headers = {
            "Authorization": f"Bearer {sent_token}",
            "Content-Type": "application/json",
        }

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                json=json_data,
            ) as response:
                # Parse rate limit headers from Tado API
                self._parse_rate_limit_headers(response.headers)

                if response.status == 401:
                    # Try to refresh token and retry
                    await self._refresh_after_401(sent_token)
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    async with self._session.request(
                        method,
                        url,
                        headers=headers,
                        json=json_data,
                    ) as retry_response:
                        self._parse_rate_limit_headers(retry_response.headers)
                        if retry_response.status == 429:
                            raise TadoXRateLimitError(
                                "API rate limit exceeded (429). Please wait for quota reset.",
                                reset_time=self._api_call_reset_time,
                            )
                        if retry_response.status not in (200, 204):
                            text = await retry_response.text()
                            raise TadoXApiError(f"API error: {retry_response.status} - {text}")
                        if retry_response.status == 204 or retry_response.content_length == 0:
                            return None
                        return await retry_response.json()

                if response.status == 429:
                    # Rate limited - raise specific exception with reset time
                    _LOGGER.warning(
                        "Rate limit exceeded (429). Quota remaining: %s, Reset time: %s",
                        self._api_quota_remaining,
                        self._api_call_reset_time,
                    )
                    raise TadoXRateLimitError(
                        "API rate limit exceeded (429). Please wait for quota reset.",
                        reset_time=self._api_call_reset_time,
                    )

                if response.status not in (200, 204):
                    text = await response.text()
                    raise TadoXApiError(f"API error: {response.status} - {text}")

                if response.content_length == 0 or response.status == 204:
                    return None
                return await response.json()

        except asyncio.TimeoutError as err:
            raise TadoXApiError("Timeout talking to the Tado API") from err
        except aiohttp.ClientError as err:
            raise TadoXApiError(f"Network error: {err}") from err

    # My Tado API endpoints (user info)
    async def get_me(self) -> dict[str, Any]:
        """Get user information including homes."""
        result = await self._request("GET", f"{TADO_MY_API_URL}/me")
        return result if isinstance(result, dict) else {}

    async def get_homes(self) -> list[dict[str, Any]]:
        """Get list of homes for the user."""
        me = await self.get_me()
        return me.get("homes", [])

    # Hops Tado API endpoints (Tado X specific)
    async def get_rooms(self) -> list[dict[str, Any]]:
        """Get all rooms with current state."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")
        result = await self._request("GET", f"{TADO_HOPS_API_URL}/homes/{self._home_id}/rooms")
        return result if isinstance(result, list) else []

    async def get_rooms_and_devices(self) -> dict[str, Any]:
        """Get all rooms with their devices."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")
        result = await self._request("GET", f"{TADO_HOPS_API_URL}/homes/{self._home_id}/roomsAndDevices")
        return result if isinstance(result, dict) else {}

    async def set_room_temperature(
        self,
        room_id: int,
        temperature: float,
        power: str = "ON",
        termination_type: str | None | object = _USE_ROOM_DEFAULT,
        duration_seconds: int | None | object = _USE_ROOM_DEFAULT,
    ) -> None:
        """Set the temperature for a room."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        # Obtain the configured defaults for this room.
        defaults = None
        if self._get_room_control_defaults is not None:
            defaults = self._get_room_control_defaults(room_id)

        # If the caller omitted termination_type, use the room default.
        if termination_type is _USE_ROOM_DEFAULT:
            termination_type = (
                defaults.termination_type
                if defaults is not None
                else "TIMER"
            )

        # If the caller omitted duration, use the room default.
        if duration_seconds is _USE_ROOM_DEFAULT:
            duration_seconds = (
                defaults.duration_minutes * 60
                if defaults is not None
                else 1800
            )

        data: dict[str, Any] = {
            "setting": {
                "power": power,
                "temperature": {"value": temperature},
            },
            "termination": {"type": termination_type},
        }

        if termination_type == "TIMER":
            data["termination"]["durationInSeconds"] = duration_seconds

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/rooms/{room_id}/manualControl",
            json_data=data,
        )

    async def set_room_off(
        self,
        room_id: int,
        termination_type: str = "TIMER",
        duration_seconds: int = 1800,
    ) -> None:
        """Turn off heating for a room (frost protection mode)."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        data: dict[str, Any] = {
            "setting": {
                "power": "OFF",
            },
            "termination": {"type": termination_type},
        }

        if termination_type == "TIMER":
            data["termination"]["durationInSeconds"] = duration_seconds

        _LOGGER.debug("Setting room %s to OFF with data: %s", room_id, data)

        result = await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/rooms/{room_id}/manualControl",
            json_data=data,
        )

        _LOGGER.debug("Set room OFF response: %s", result)

    async def resume_schedule(self, room_id: int) -> None:
        """Resume the schedule for a room (cancel manual control)."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "DELETE",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/rooms/{room_id}/manualControl",
        )

    async def set_boost_mode(self) -> None:
        """Activate boost mode for all rooms.

        Note: Tado X API only supports home-wide boost, not per-room boost.
        To boost a single room, use set_room_temperature with max temperature.
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/quickActions/boost",
        )

    async def resume_all_schedules(self) -> None:
        """Resume schedule for all rooms."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/quickActions/resumeSchedule",
        )

    async def set_open_window_detection(self, room_id: int, enabled: bool) -> None:
        """Enable or disable open window detection for a room."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        if enabled:
            await self._request(
                "POST",
                f"{TADO_HOPS_API_URL}/homes/{self._home_id}/rooms/{room_id}/openWindow",
            )
        else:
            await self._request(
                "DELETE",
                f"{TADO_HOPS_API_URL}/homes/{self._home_id}/rooms/{room_id}/openWindow",
            )

    # Presence/Geofencing endpoints (My Tado API)
    async def get_home_state(self) -> dict[str, Any]:
        """Get the current home presence state."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")
        result = await self._request("GET", f"{TADO_MY_API_URL}/homes/{self._home_id}/state")
        return result if isinstance(result, dict) else {}

    async def set_presence_home(self) -> None:
        """Set presence to HOME (override geofencing)."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "PUT",
            f"{TADO_MY_API_URL}/homes/{self._home_id}/presenceLock",
            json_data={"homePresence": "HOME"},
        )

    async def set_presence_away(self) -> None:
        """Set presence to AWAY (override geofencing)."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "PUT",
            f"{TADO_MY_API_URL}/homes/{self._home_id}/presenceLock",
            json_data={"homePresence": "AWAY"},
        )

    async def set_presence_auto(self) -> None:
        """Enable automatic geofencing (remove presence lock)."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "DELETE",
            f"{TADO_MY_API_URL}/homes/{self._home_id}/presenceLock",
        )

    # Device configuration endpoints
    async def set_temperature_offset(self, device_serial: str, offset: float) -> None:
        """Set the temperature offset for a device.

        Args:
            device_serial: Serial number of the device
            offset: Temperature offset in °C (typically -9.9 to +9.9)
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "PATCH",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/roomsAndDevices/devices/{device_serial}",
            json_data={"temperatureOffset": offset},
        )

    async def add_meter_reading(self, reading: int, date: str | None = None) -> None:
        """Add a meter reading to Tado Energy IQ.

        Args:
            reading: Integer meter reading value
            date: Date in YYYY-MM-DD format (defaults to today)
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        from datetime import date as date_module

        reading_date = date if date else date_module.today().isoformat()

        await self._request(
            "POST",
            f"{TADO_EIQ_API_URL}/homes/{self._home_id}/meterReadings",
            json_data={"date": reading_date, "reading": reading},
        )

    async def set_child_lock(self, device_serial: str, enabled: bool) -> None:
        """Enable or disable child lock on a device.

        Args:
            device_serial: Serial number of the device
            enabled: True to enable child lock, False to disable
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "PATCH",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/roomsAndDevices/devices/{device_serial}",
            json_data={"childLockEnabled": enabled},
        )

    async def set_room_manual_control_termination(
        self,
        room_id: int,
        termination_type: str,
        duration_seconds: int | None = None,
    ) -> None:
        """Set the Tado master manual-control termination setting for a room."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        valid_types = {"NEXT_TIME_BLOCK", "TIMER", "MANUAL"}

        if termination_type not in valid_types:
            raise ValueError(
                f"Invalid termination type: {termination_type}. "
                f"Expected one of {sorted(valid_types)}"
            )

        termination: dict[str, Any] = {
            "type": termination_type,
        }

        if termination_type == "TIMER":
            if duration_seconds is None:
                raise ValueError(
                    "duration_seconds is required when termination_type is TIMER"
                )
            termination["durationInSeconds"] = duration_seconds

        data = {
            "deviceManualControlTermination": termination,
        }

        _LOGGER.debug(
            "Setting room %s manual control termination: %s",
            room_id,
            data,
        )

        await self._request(
            "PATCH",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}"
            f"/roomsAndDevices/rooms/{room_id}",
            json_data=data,
        )


    # Quick Actions
    async def boost_all_heating(self) -> None:
        """Boost heating in all rooms."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/quickActions/boost",
        )

    async def disable_all_heating(self) -> None:
        """Turn off heating in all rooms."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/quickActions/allOff",
        )

    async def resume_all_schedules(self) -> None:
        """Resume smart schedule in all rooms."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/quickActions/resumeSchedule",
        )

    # Energy IQ Tariffs
    async def get_eiq_tariffs(self) -> list[dict]:
        """Get Energy IQ tariff history."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_EIQ_API_URL}/homes/{self._home_id}/tariffs",
        )
        return result if isinstance(result, list) else []

    async def set_eiq_tariff(
        self,
        tariff: float,
        unit: str = "m3",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        """Set Energy IQ tariff.

        Args:
            tariff: Price per unit (e.g., 0.85 for €0.85/m³)
            unit: Unit type - "m3" or "kWh"
            start_date: Start date (YYYY-MM-DD), defaults to today
            end_date: End date (YYYY-MM-DD), optional for ongoing tariff
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        from datetime import date as date_module

        tariff_in_cents = int(tariff * 100)
        payload: dict = {
            "tariffInCents": tariff_in_cents,
            "unit": unit,
            "startDate": start_date if start_date else date_module.today().isoformat(),
        }

        if end_date:
            payload["endDate"] = end_date

        await self._request(
            "POST",
            f"{TADO_EIQ_API_URL}/homes/{self._home_id}/tariffs",
            json_data=payload,
        )

    async def delete_eiq_tariff(self, tariff_id: str) -> None:
        """Delete an Energy IQ tariff.

        Args:
            tariff_id: ID of the tariff to delete
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "DELETE",
            f"{TADO_EIQ_API_URL}/homes/{self._home_id}/tariffs/{tariff_id}",
        )

    async def get_weather(self) -> dict[str, Any]:
        """Get weather data for the home.

        Returns weather information including outdoor temperature,
        solar intensity, and weather state.
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_MY_API_URL}/homes/{self._home_id}/weather",
        )
        return result if isinstance(result, dict) else {}

    # Mobile Devices endpoints
    async def get_mobile_devices(self) -> list[dict[str, Any]]:
        """Get all mobile devices registered for geofencing.

        Returns a list of mobile device dicts with location and geofencing info.
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")
        result = await self._request(
            "GET",
            f"{TADO_MY_API_URL}/homes/{self._home_id}/mobileDevices",
        )
        return result if isinstance(result, list) else []

    async def get_air_comfort(self) -> dict[str, Any]:
        """Get air comfort data for all rooms.

        Returns air freshness and comfort levels per room.
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/airComfort",
        )
        return result if isinstance(result, dict) else {}

    # Schedule endpoints (Tado X / Hops API, rooms)
    async def get_zone_schedule(self, room_id: int) -> dict[str, Any]:
        """Get the active smart schedule for a room.

        Returns the Tado X schedule: a dict with the room and a list of
        day blocks (dayType, start, end, setting).
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/rooms/{room_id}/schedule",
        )
        return result if isinstance(result, dict) else {}

    @staticmethod
    def _normalize_away_configuration(config: dict[str, Any], room_id: int) -> dict[str, Any]:
        """Validate Tado X room Away settings; strip response-only roomId."""
        if not isinstance(config, dict):
            raise TadoXApiError("Tado X Away configuration is not a JSON object")
        if "roomId" in config and str(config["roomId"]) != str(room_id):
            raise TadoXApiError(
                f"Tado X Away response roomId mismatch: expected {room_id}, "
                f"got {config['roomId']}"
            )
        mode = config.get("mode")
        if mode not in ("ON", "OFF"):
            raise TadoXApiError(f"Unexpected Tado X Away mode: {mode!r}")
        level = config.get("preheatingLevel")
        if not isinstance(level, str) or not level:
            raise TadoXApiError("Tado X Away preheatingLevel missing or invalid")
        temperature = config.get("awayTemperatureCelsius")
        if mode == "ON":
            if (isinstance(temperature, bool) or
                    not isinstance(temperature, (int, float)) or
                    not 0 < temperature < 50):
                raise TadoXApiError("Tado X Away ON requires a valid temperature")
        elif temperature is not None:
            raise TadoXApiError("Tado X Away OFF must have null temperature")
        return {
            "mode": mode,
            "awayTemperatureCelsius": temperature,
            "preheatingLevel": level,
        }

    async def get_zone_away_configuration(self, room_id: int) -> dict[str, Any]:
        """Read saved per-room Tado X Away configuration from Hops API."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")
        result = await self._request(
            "GET",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/away/rooms/{room_id}",
        )
        return self._normalize_away_configuration(result, room_id)

    async def set_zone_away_configuration(self, room_id: int, config: dict[str, Any]) -> None:
        """Write saved Away settings, preserving mode, temperature and preheating."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")
        payload = self._normalize_away_configuration(config, room_id)
        await self._request(
            "PUT",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/away/rooms/{room_id}",
            json_data=payload,
        )

    async def set_zone_schedule(
        self,
        room_id: int,
        day_type: str,
        day_schedule: list[dict[str, Any]],
    ) -> None:
        """Set the smart schedule blocks for a room.

        Args:
            room_id: Tado X room ID.
            day_type: One of MONDAY_TO_SUNDAY, MONDAY_TO_FRIDAY, SATURDAY, ...
            day_schedule: List of blocks. Each block is a dict with
                dayType, start, end, geolocationOverride and setting.
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/rooms/{room_id}/schedule",
            json_data={"dayType": day_type, "daySchedule": day_schedule},
        )

    # Historic data endpoints (My Tado API, zones)
    async def get_zone_day_report(self, zone_id: int, date_str: str) -> dict[str, Any]:
        """Get the historical day report for a zone (temperature, humidity, heating).

        Args:
            zone_id: Zone ID (for Tado X this equals the room ID).
            date_str: Date in YYYY-MM-DD format.

        Raises:
            TadoXApiError: on error, including 403 accessDenied for past days
                when the account has no Auto-Assist (Premium) subscription.
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_MY_API_URL}/homes/{self._home_id}/zones/{zone_id}/dayReport?date={date_str}",
        )
        return result if isinstance(result, dict) else {}

    # Holiday mode endpoints (Hops API, home settings — Auto-Assist skill)
    async def get_holiday_mode(self) -> dict[str, Any]:
        """Get the home's holiday mode settings.

        Returns the settings dict (enabled, active, startDate, endDate,
        roomSettings, hotWaterSettings) or {} when not configured.

        Raises:
            TadoXApiError: when unavailable (e.g. no Auto-Assist subscription).
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/holidayMode",
        )
        return result if isinstance(result, dict) else {}

    async def set_holiday_mode(
        self,
        enabled: bool,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        """Enable/disable holiday mode and optionally set its date range.

        Toggle-only PATCH sends only enabled; explicit date changes preserve
        existing room and hot-water settings. Dates are ISO-8601.
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        # Only send writable fields. Echoing a GET response back to PATCH can
        # include server-managed properties (such as active) and silently fail.
        # Retain existing dates when the caller supplies only one boundary.
        current = await self.get_holiday_mode()
        if not isinstance(current.get("roomSettings"), dict):
            raise TadoXApiError("Holiday settings incomplete; refusing unsafe update")

        date_update = start_date is not None or end_date is not None
        body: dict[str, Any] = {"enabled": enabled}
        if date_update:
            body["startDate"] = start_date if start_date is not None else current.get("startDate")
            body["endDate"] = end_date if end_date is not None else current.get("endDate")
            if not body["startDate"] or not body["endDate"]:
                raise TadoXApiError(
                    "Both holiday dates must be available to update the holiday period"
                )
            try:
                start = datetime.fromisoformat(body["startDate"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(body["endDate"].replace("Z", "+00:00"))
                if start.tzinfo is None or end.tzinfo is None or end <= start:
                    raise ValueError("invalid date range")
            except (TypeError, ValueError, AttributeError) as err:
                raise TadoXApiError("Holiday end must be after start; both dates must include a timezone") from err

        await self._request(
            "PATCH",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/holidayMode",
            json_data=body,
        )

        if date_update:
            # Tado can acknowledge a PATCH without applying the date change.
            # A read-back also ensures the minimal PATCH did not alter settings.
            actual = await self.get_holiday_mode()
            def same_instant(left: Any, right: Any) -> bool:
                try:
                    return datetime.fromisoformat(str(left).replace("Z", "+00:00")) == datetime.fromisoformat(str(right).replace("Z", "+00:00"))
                except ValueError:
                    return False

            if (
                actual.get("enabled") is not enabled
                or not same_instant(actual.get("startDate"), body["startDate"])
                or not same_instant(actual.get("endDate"), body["endDate"])
            ):
                raise TadoXApiError(
                    "Tado acknowledged the holiday update but did not retain the "
                    "requested enabled state and dates. Check the Tado app and "
                    "Home Assistant logs."
                )
            for field in ("roomSettings", "hotWaterSettings"):
                if field in current and actual.get(field) != current[field]:
                    raise TadoXApiError(
                        f"Tado changed {field} while updating holiday dates; "
                        "review the holiday settings in the Tado app"
                    )

    # Running Times endpoints (Minder API)
    async def get_running_times(self, from_date: str, to_date: str) -> dict[str, Any]:
        """Get running times data for heating statistics.

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format

        Returns:
            Running times data per zone including heating duration.
            Expected structure:
            {
                "runningTimes": [
                    {
                        "startTime": "2024-01-15T00:00:00Z",
                        "endTime": "2024-01-15T23:59:59Z",
                        "runningTimeInSeconds": 14400,
                        "zones": [
                            {
                                "id": 1,
                                "runningTimeInSeconds": 7200
                            }
                        ]
                    }
                ],
                "summary": {
                    "totalRunningTimeInSeconds": 14400
                }
            }
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_MINDER_API_URL}/homes/{self._home_id}/runningTimes?from={from_date}&to={to_date}",
        )
        return result if isinstance(result, dict) else {}

    async def get_hydronic_balancing(self) -> dict[str, Any]:
        """Read hydronic balancing configuration."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/hydronicBalancing",
        )
        return result if isinstance(result, dict) else {}

    async def set_hydronic_balancing(self, enabled: bool) -> None:
        """Update hydronic balancing; disabling may reset learned settings."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "PATCH",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/hydronicBalancing",
            json_data={"hydronicBalancingEnabled": enabled},
        )

    # Flow Temperature Optimization endpoints
    async def get_flow_temperature_optimization(self) -> dict[str, Any]:
        """Get flow temperature optimization settings.

        Returns:
            Flow temperature settings including:
            {
                "maxFlowTemperature": 38,
                "maxFlowTemperatureConstraints": {
                    "min": 20,
                    "max": 75
                },
                "openThermDeviceSerialNumber": "RU0000000000",
                "hasMultipleBoilerControlDevices": false,
                "autoAdaptation": {
                    "enabled": false,
                    "maxFlowTemperature": null
                }
            }
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/flowTemperatureOptimization",
        )
        return result if isinstance(result, dict) else {}

    async def set_max_flow_temperature(self, temperature: int) -> None:
        """Set the maximum flow temperature for the boiler.

        Args:
            temperature: Temperature in °C (typically 20-75, depends on constraints)
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "PATCH",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/flowTemperatureOptimization",
            json_data={"maxFlowTemperature": temperature},
        )

    async def set_flow_temp_auto_adaptation(self, enabled: bool) -> None:
        """Enable or disable auto-adaptation for flow temperature.

        Args:
            enabled: True to enable auto-adaptation, False to disable
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "PATCH",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/settings/flowTemperatureOptimization",
            json_data={"autoAdaptation": {"enabled": enabled}},
        )


    async def get_domestic_hot_water_state(self) -> dict[str, Any]:
        """Get the status of domestic hot water.

        Returns:
            Status information including:
            {
                "status": "OFF" | "SCHEDULE_OFF" |"SCHEDULE_ON" | "BOOST",
                "nextStateChange": "2026-02-14T16:00:00Z",
                "setpoint": null,
                "setpointConstraints": null
            }
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        result = await self._request(
            "GET",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/programmer/domesticHotWater/state",
        )
        return result if isinstance(result, dict) else {}

    async def set_domestic_hot_water_temperature(self, temperature: int) -> None:
        """Set the domestic hot water temperature using Hops manual control.

        OpenTherm installations can expose a temperature setpoint without
        supporting relay-based DHW boost and off actions.
        """
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/programmer/domesticHotWater/manualControl",
            json_data={"setpoint": temperature},
        )

    async def boost_domestic_hot_water(self) -> None:
        """Boost domestic hot water."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/programmer/domesticHotWater/boost",
            json_data={ "boost": "ON" },
        )

    async def disable_domestic_hot_water(self) -> None:
        """Turn off domestic hot water."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/programmer/domesticHotWater/boost",
            json_data={ "boost": "OFF" },
        )

    async def resume_domestic_hot_water_schedule(self) -> None:
        """Resume the schedule for domestic hot water."""
        if not self._home_id:
            raise TadoXApiError("Home ID not set")

        await self._request(
            "POST",
            f"{TADO_HOPS_API_URL}/homes/{self._home_id}/programmer/domesticHotWater/resumeSchedule",
        )


def summarize_day_report(report: dict[str, Any]) -> dict[str, Any]:
    """Reduce a raw dayReport to a compact temperature/humidity/heating summary.

    The dayReport returns two series shapes: ``dataPoints`` (timestamp + value,
    used for insideTemperature and humidity) and ``dataIntervals`` (from/to +
    value, used for callForHeat / settings / stripes). Both are flattened here.
    """

    def _series_values(series: dict[str, Any] | None, value_key: str | None) -> list[float]:
        out: list[float] = []
        for point in (series or {}).get("dataPoints") or []:
            value = point.get("value")
            if value_key and isinstance(value, dict):
                value = value.get(value_key)
            if isinstance(value, (int, float)):
                out.append(float(value))
        for interval in (series or {}).get("dataIntervals") or []:
            value = interval.get("value")
            if value_key and isinstance(value, dict):
                value = value.get(value_key)
            if isinstance(value, (int, float)):
                out.append(float(value))
        return out

    def _avg(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 1) if vals else None

    def _interval_hours(interval: dict[str, Any]) -> float:
        try:
            start = datetime.fromisoformat(interval["from"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(interval["to"].replace("Z", "+00:00"))
            return (end - start).total_seconds() / 3600.0
        except (KeyError, TypeError, ValueError):
            return 0.0

    measured = report.get("measuredData") or {}

    temps = _series_values(measured.get("insideTemperature"), "celsius")
    # dayReport humidity values are 0.0-1.0 fractions despite valueType "percentage"
    hums_pct = [round(h * 100, 1) for h in _series_values(measured.get("humidity"), None)]

    # Heating time: callForHeat marks actual boiler demand ("HEATING" vs "NONE");
    # fall back to the scheduled settings (power == "ON") when absent.
    heating_hours: float | None = None
    call_for_heat = (report.get("callForHeat") or {}).get("dataIntervals") or []
    if call_for_heat:
        heating_hours = round(
            sum(_interval_hours(iv) for iv in call_for_heat if iv.get("value") != "NONE"),
            1,
        )
    else:
        settings = (report.get("settings") or {}).get("dataIntervals") or []
        if settings:
            heating_hours = round(
                sum(
                    _interval_hours(iv)
                    for iv in settings
                    if (iv.get("value") or {}).get("power") == "ON"
                ),
                1,
            )

    return {
        "temperature_avg": _avg(temps),
        "temperature_min": round(min(temps), 1) if temps else None,
        "temperature_max": round(max(temps), 1) if temps else None,
        "humidity_avg": _avg(hums_pct),
        "heating_hours": heating_hours,
    }


if __name__ == "__main__":
    # Self-check against the live dayReport shape.
    _sample = {
        "measuredData": {
            "insideTemperature": {
                "dataPoints": [
                    {"timestamp": "2026-10-13T00:00:00Z", "value": {"celsius": 19.0}},
                    {"timestamp": "2026-10-13T00:15:00Z", "value": {"celsius": 21.0}},
                ]
            },
            "humidity": {
                "dataPoints": [
                    {"timestamp": "2026-10-13T00:00:00Z", "value": 0.60},
                    {"timestamp": "2026-10-13T00:15:00Z", "value": 0.728},
                ]
            },
        },
        "callForHeat": {
            "dataIntervals": [
                {"from": "2026-10-13T00:00:00Z", "to": "2026-10-13T01:00:00Z", "value": "HEATING"},
                {"from": "2026-10-13T01:00:00Z", "to": "2026-10-13T02:00:00Z", "value": "NONE"},
            ]
        },
    }
    _summary = summarize_day_report(_sample)
    assert _summary["temperature_avg"] == 20.0, _summary
    assert _summary["temperature_min"] == 19.0, _summary
    assert _summary["temperature_max"] == 21.0, _summary
    assert _summary["humidity_avg"] == 66.4, _summary
    assert _summary["heating_hours"] == 1.0, _summary
    # empty report returns all-None
    assert summarize_day_report({})["temperature_avg"] is None
    print("summarize_day_report OK:", _summary)
