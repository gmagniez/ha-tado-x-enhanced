"""DataUpdateCoordinator for Tado X."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TadoXApi, TadoXApiError, TadoXAuthError, TadoXRateLimitError
from .const import (
    DEFAULT_TIMER_DURATION_MINUTES,
    DEFAULT_SUPPLEMENTARY_POLL_MULTIPLIER,
    DOMAIN,
    SCAN_INTERVAL_AUTO_ASSIST,
    SCAN_INTERVAL_FREE_TIER,
    TERMINATION_TIMER,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class TadoXDevice:
    """Representation of a Tado X device."""

    serial_number: str
    device_type: str
    firmware_version: str
    connection_state: str
    battery_state: str | None = None
    temperature_measured: float | None = None
    temperature_offset: float = 0.0
    mounting_state: str | None = None
    child_lock_enabled: bool = False
    room_id: int | None = None
    room_name: str | None = None


@dataclass
class TadoXRoom:
    """Representation of a Tado X room."""

    room_id: int
    name: str
    current_temperature: float | None = None
    target_temperature: float | None = None
    humidity: float | None = None
    heating_power: int = 0
    power: str = "OFF"
    connection_state: str = "DISCONNECTED"
    manual_control_active: bool = False
    manual_control_remaining_seconds: int | None = None
    manual_control_type: str | None = None
    boost_mode: bool = False
    open_window_detected: bool = False
    open_window_ends_at: str | None = None
    next_schedule_change: str | None = None
    next_schedule_temperature: float | None = None
    next_schedule_power: str | None = None
    devices: list[TadoXDevice] = field(default_factory=list)
    # Running times data (heating duration today)
    running_time_today_seconds: int = 0


@dataclass
class TadoXRoomControlDefaults:
    """Default control settings for a room."""

    termination_type: str = TERMINATION_TIMER
    duration_minutes: int = DEFAULT_TIMER_DURATION_MINUTES


@dataclass
class TadoXWeather:
    """Representation of Tado weather data."""

    outdoor_temperature: float | None = None
    solar_intensity: float | None = None
    weather_state: str | None = None


@dataclass
class TadoXMobileDevice:
    """Representation of a Tado mobile device for geofencing."""

    device_id: int
    name: str
    device_metadata: dict = field(default_factory=dict)
    location: str | None = None  # "HOME", "AWAY", or None if location not available
    at_home: bool = False
    geofencing_enabled: bool = False


@dataclass
class TadoXRoomAirComfort:
    """Air comfort data for a room."""

    room_id: int
    freshness: str | None = None  # FRESH, FAIR, STALE
    comfort_level: str | None = None  # Based on temperature/humidity


@dataclass
class TadoXData:
    """Data from Tado X API."""

    home_id: int
    home_name: str
    rooms: dict[int, TadoXRoom] = field(default_factory=dict)
    devices: dict[str, TadoXDevice] = field(default_factory=dict)
    other_devices: list[TadoXDevice] = field(default_factory=list)
    presence: str | None = None  # HOME, AWAY, or None if not locked
    presence_locked: bool = False  # Whether presence is manually set
    api_calls_today: int = 0
    api_reset_time: datetime | None = None
    api_last_reset: datetime | None = None
    api_last_observed_at: datetime | None = None
    has_auto_assist: bool = False
    # Real values from Tado API response headers
    api_quota_limit: int | None = None  # From ratelimit-policy header (q=)
    api_quota_remaining: int | None = None  # From ratelimit header (r=)
    api_rolling_daily_usage: float | None = None  # Recent 60-minute rate projection
    # Weather data
    weather: TadoXWeather | None = None
    # Mobile devices for geofencing
    mobile_devices: dict[int, TadoXMobileDevice] = field(default_factory=dict)
    # Running times data (raw response for additional processing if needed)
    running_times: dict[str, Any] = field(default_factory=dict)
    # Air comfort data per room
    air_comfort: dict[int, TadoXRoomAirComfort] = field(default_factory=dict)
    # Rate limit status
    rate_limited: bool = False
    rate_limit_reset: datetime | None = None
    # Flow temperature optimization
    max_flow_temperature: int | None = None
    flow_temp_min: int | None = None
    flow_temp_max: int | None = None
    flow_temp_auto_adaptation: bool = False
    flow_temp_auto_value: int | None = None
    has_flow_temp_control: bool = False
    # Domestic hot water state (e.g., OFF, SCHEDULE_ON, SCHEDULE_OFF, BOOST)
    dhw_state: str | None = None
    dhw_setpoint: float | None = None
    dhw_setpoint_min: float | None = None
    dhw_setpoint_max: float | None = None
    dhw_relay_actions_unverified: bool = False
    dhw_boost_ends: str | None = None
    dhw_next_schedule_change: str | None = None


class TadoXDataUpdateCoordinator(DataUpdateCoordinator[TadoXData]):
    """Class to manage fetching Tado X data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: TadoXApi,
        home_id: int,
        home_name: str,
        save_api_stats_callback: Callable[[], None] | None = None,
        scan_interval: int | None = None,
        enable_weather: bool = True,
        enable_mobile_devices: bool = True,
        enable_air_comfort: bool = True,
        enable_running_times: bool = True,
        enable_flow_temp: bool = True,
        enable_hot_water: bool = True,
        supplementary_poll_multiplier: int = DEFAULT_SUPPLEMENTARY_POLL_MULTIPLIER,
    ) -> None:
        """Initialize the coordinator."""
        # Determine scan interval based on subscription tier if not explicitly set
        if scan_interval is None:
            scan_interval = (
                SCAN_INTERVAL_AUTO_ASSIST if api.has_auto_assist
                else SCAN_INTERVAL_FREE_TIER
            )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.api._get_room_control_defaults = self.get_room_control_defaults
        self.parent_device_ids: dict[tuple[str, str], str] = {}
        self.home_id = home_id
        self.home_name = home_name
        self.api.home_id = home_id
        self._save_api_stats_callback = save_api_stats_callback
        self._scan_interval = scan_interval
        self.api.configure_quota_observation_interval(scan_interval)
        self.room_control_defaults: dict[int, TadoXRoomControlDefaults] = {}

        # Feature toggles for optional API calls
        self.enable_weather = enable_weather
        self.enable_mobile_devices = enable_mobile_devices
        self.enable_air_comfort = enable_air_comfort
        self.enable_running_times = enable_running_times
        self.enable_flow_temp = enable_flow_temp
        self.enable_hot_water = enable_hot_water
        self.supplementary_poll_multiplier = supplementary_poll_multiplier
        self._supplementary_last_success: dict[str, float] = {}
        self._supplementary_cache: dict[str, Any] = {}

        _LOGGER.info(
            "Tado X coordinator initialized with %d second update interval (%s tier)",
            scan_interval,
            "Auto-Assist" if api.has_auto_assist else "Free"
        )
        _LOGGER.info(
            "Optional features - Weather: %s, Mobile devices: %s, Air comfort: %s, Running times: %s, Flow temp: %s, Hot water: %s",
            enable_weather, enable_mobile_devices, enable_air_comfort, enable_running_times, enable_flow_temp, enable_hot_water
        )

    def update_scan_interval(self, new_interval: int) -> None:
        """Update the scan interval dynamically."""
        self._scan_interval = new_interval
        self.api.configure_quota_observation_interval(new_interval)
        self.update_interval = timedelta(seconds=new_interval)
        _LOGGER.info("Scan interval updated to %d seconds", new_interval)

    def get_api_calls_per_update(self) -> int:
        """Calculate the number of API calls per update based on enabled features."""
        # Base calls: get_rooms, get_rooms_and_devices, get_home_state
        calls = 3
        if self.enable_weather:
            calls += 1
        if self.enable_mobile_devices:
            calls += 1
        if self.enable_air_comfort:
            calls += 1
        if self.enable_running_times:
            calls += 1
        if self.enable_hot_water:
            calls += 1
        if self.enable_flow_temp:
            calls += 1
        holiday_manager = getattr(self, "holiday_mode_manager", None)
        if holiday_manager is not None and holiday_manager.poll_enabled:
            calls += 1
        return calls

    def should_refresh_supplementary(self, feature: str) -> bool:
        """Return whether a supplementary API dataset is due for refresh."""
        if self.supplementary_poll_multiplier == 1:
            return True
        from time import monotonic
        last = self._supplementary_last_success.get(feature)
        return last is None or monotonic() - last >= self._scan_interval * self.supplementary_poll_multiplier - min(1.0, self._scan_interval * 0.02)

    def mark_supplementary_success(self, feature: str, value: Any) -> None:
        """Cache successful data for reuse between reduced-frequency polls."""
        from time import monotonic
        self._supplementary_cache[feature] = value
        self._supplementary_last_success[feature] = monotonic()

    def update_supplementary_settings(self, multiplier: int) -> None:
        """Apply a new multiplier, resetting due timestamps when it changes."""
        if self.supplementary_poll_multiplier != multiplier:
            self._supplementary_last_success.clear()
        self.supplementary_poll_multiplier = multiplier

    def invalidate_supplementary(self, feature: str) -> None:
        """Ensure the next coordinator refresh fetches a changed setting."""
        self._supplementary_last_success.pop(feature, None)

    def get_room_control_defaults(self, room_id: int) -> TadoXRoomControlDefaults:
        """Return per-room control defaults, creating them if missing."""
        defaults = self.room_control_defaults.get(room_id)
        if defaults is None:
            defaults = TadoXRoomControlDefaults()
            self.room_control_defaults[room_id] = defaults
        return defaults

    def set_room_control_defaults(
        self,
        room_id: int,
        *,
        termination_type: str | None = None,
        duration_minutes: int | None = None,
    ) -> None:
        """Update per-room control defaults."""
        defaults = self.get_room_control_defaults(room_id)

        if termination_type is not None:
            defaults.termination_type = termination_type
        if duration_minutes is not None:
            defaults.duration_minutes = duration_minutes

    async def _async_update_data(self) -> TadoXData:
        """Fetch data from Tado X API."""
        try:
            # Get rooms with current state (required)
            rooms_data = await self.api.get_rooms()

            # Get rooms with devices (required)
            rooms_devices_data = await self.api.get_rooms_and_devices()

            home_state = await self.api.get_home_state()
            presence = home_state.get("presence")
            presence_locked = home_state.get("presenceLocked", False)

            # Get domestic hot water state (optional)
            dhw_state = None
            dhw_setpoint = None
            dhw_setpoint_min = None
            dhw_setpoint_max = None
            dhw_boost_ends = None
            dhw_next_schedule_change = None
            if self.enable_hot_water:
                dhw_state_response = await self.api.get_domestic_hot_water_state()
                dhw_state = dhw_state_response.get("state")
                dhw_setpoint = dhw_state_response.get("setpoint")
                constraints = dhw_state_response.get("setpointConstraints") or {}
                dhw_setpoint_min = constraints.get("min")
                dhw_setpoint_max = constraints.get("max")
                if dhw_state == "BOOST":
                    dhw_boost_ends = dhw_state_response.get("nextStateChange")
                elif dhw_state in ("SCHEDULE_ON", "SCHEDULE_OFF"):
                    dhw_next_schedule_change = dhw_state_response.get("nextStateChange")
            
            # Get weather data (optional)
            weather = None
            if self.enable_weather and not self.should_refresh_supplementary("weather"):
                weather = self._supplementary_cache.get("weather")
            elif self.enable_weather:
                _LOGGER.debug("Supplementary API request: weather (home_id=%s)", self.home_id)
                weather_data = await self.api.get_weather()
                outdoor_temp_data = weather_data.get("outsideTemperature") or {}
                solar_data = weather_data.get("solarIntensity") or {}
                weather_state_data = weather_data.get("weatherState") or {}

                weather = TadoXWeather(
                    outdoor_temperature=outdoor_temp_data.get("celsius"),
                    solar_intensity=solar_data.get("percentage"),
                    weather_state=weather_state_data.get("value"),
                )
                self.mark_supplementary_success("weather", weather)

            # Get mobile devices for geofencing (optional)
            mobile_devices_data = []
            if self.enable_mobile_devices:
                mobile_devices_data = await self.api.get_mobile_devices()

            # Process the data
            data = TadoXData(
                home_id=self.home_id,
                home_name=self.home_name,
                presence=presence,
                presence_locked=presence_locked,
                weather=weather,
                dhw_state=dhw_state,
                dhw_setpoint=dhw_setpoint,
                dhw_setpoint_min=dhw_setpoint_min,
                dhw_setpoint_max=dhw_setpoint_max,
                dhw_boost_ends=dhw_boost_ends,
                dhw_next_schedule_change=dhw_next_schedule_change,
            )

            # A setpoint-capable OpenTherm controller does not imply that
            # relay-only DHW actions are supported. Keep them opt-in.
            data.dhw_relay_actions_unverified = (
                data.dhw_setpoint is not None
                and any(
                    device.get("thermInterfaceType") == "OPENTHERM"
                    for device in (rooms_devices_data.get("otherDevices") or [])
                )
            )

            # Process rooms, devices and Tado manual-control defaults
            rooms_info = rooms_devices_data.get("rooms", [])
            room_devices_map: dict[int, list[dict]] = {}

            for room_info in rooms_info:
                room_id = room_info.get("roomId")
                if not room_id:
                    continue

                room_devices_map[room_id] = room_info.get("devices", [])

                # Read the Manual Control defaults configured in the Tado app.
                manual_control_default = (
                    room_info.get("deviceManualControlTermination") or {}
                )

                termination_type = manual_control_default.get("type")
                duration_seconds = manual_control_default.get("durationInSeconds")

                if termination_type is not None:
                    self.set_room_control_defaults(
                        room_id,
                        termination_type=termination_type,
                    )

                if duration_seconds is not None:
                    self.set_room_control_defaults(
                        room_id,
                        duration_minutes=int(duration_seconds / 60),
                    )
 
            # Process room states
            for room_data in rooms_data:
                room_id = room_data.get("id")
                if not room_id:
                    continue

                # Debug: log raw room data for power/setting analysis
                setting = room_data.get("setting") or {}
                _LOGGER.debug(
                    "Room %s (%s) - setting: %s, manualControl: %s",
                    room_id,
                    room_data.get("name"),
                    setting,
                    room_data.get("manualControlTermination"),
                )

                # Get sensor data (use 'or {}' to handle None values)
                sensor_data = room_data.get("sensorDataPoints") or {}
                inside_temp = sensor_data.get("insideTemperature") or {}
                humidity_data = sensor_data.get("humidity") or {}

                # Get setting (use 'or {}' to handle None values)
                setting = room_data.get("setting") or {}
                target_temp = setting.get("temperature") or {}

                # Get manual control info
                manual_control = room_data.get("manualControlTermination")
                manual_active = manual_control is not None
                manual_remaining = None
                manual_type = None
                if manual_control:
                    manual_remaining = manual_control.get("remainingTimeInSeconds")
                    manual_type = manual_control.get("type")

                # Get next schedule change (use 'or {}' to handle None values)
                next_change = room_data.get("nextScheduleChange") or {}
                next_change_time = next_change.get("start")
                next_change_setting = next_change.get("setting") or {}
                next_change_temp_obj = next_change_setting.get("temperature") or {}
                next_change_temp = next_change_temp_obj.get("value")
                next_change_power = next_change_setting.get("power")

                # Get heating power and connection (use 'or {}' to handle None values)
                heating_power_data = room_data.get("heatingPower") or {}
                connection_data = room_data.get("connection") or {}

                room = TadoXRoom(
                    room_id=room_id,
                    name=room_data.get("name", f"Room {room_id}"),
                    current_temperature=inside_temp.get("value"),
                    target_temperature=target_temp.get("value"),
                    humidity=humidity_data.get("percentage"),
                    heating_power=heating_power_data.get("percentage", 0),
                    power=setting.get("power", "OFF"),
                    connection_state=connection_data.get("state", "DISCONNECTED"),
                    manual_control_active=manual_active,
                    manual_control_remaining_seconds=manual_remaining,
                    manual_control_type=manual_type,
                    boost_mode=room_data.get("boostMode") is not None,
                    open_window_detected=room_data.get("openWindow") is not None,
                    open_window_ends_at=(room_data.get("openWindow") or {}).get("projectedExpiry"),
                    next_schedule_change=next_change_time,
                    next_schedule_temperature=next_change_temp,
                    next_schedule_power=next_change_power,
                )

                # Add devices for this room
                for device_data in room_devices_map.get(room_id, []):
                    device_connection = device_data.get("connection") or {}
                    device = TadoXDevice(
                        serial_number=device_data.get("serialNumber", ""),
                        device_type=device_data.get("type", ""),
                        firmware_version=device_data.get("firmwareVersion", ""),
                        connection_state=device_connection.get("state", "DISCONNECTED"),
                        battery_state=device_data.get("batteryState"),
                        temperature_measured=device_data.get("temperatureAsMeasured"),
                        temperature_offset=device_data.get("temperatureOffset", 0.0),
                        mounting_state=device_data.get("mountingState"),
                        child_lock_enabled=device_data.get("childLockEnabled", False),
                        room_id=room_id,
                        room_name=room.name,
                    )
                    room.devices.append(device)
                    data.devices[device.serial_number] = device

                data.rooms[room_id] = room

            # Process other devices (bridge, thermostat controller)
            # First, find the room with the most devices (for thermostat association)
            room_with_most_devices: int | None = None
            max_device_count = 0
            for room_id, room in data.rooms.items():
                device_count = len(room.devices)
                if device_count > max_device_count:
                    max_device_count = device_count
                    room_with_most_devices = room_id

            for device_data in rooms_devices_data.get("otherDevices") or []:
                other_device_connection = device_data.get("connection") or {}
                other_room_id = device_data.get("roomId")
                other_room_name = None
                device_type = device_data.get("type", "")

                # If device has a room association from API, use it
                if other_room_id and other_room_id in data.rooms:
                    other_room_name = data.rooms[other_room_id].name
                # For Wireless Receiver X (TR04) without room, associate with the room
                # that has the most devices (typically the main room it controls)
                elif device_type == "TR04" and room_with_most_devices:
                    other_room_id = room_with_most_devices
                    other_room_name = data.rooms[room_with_most_devices].name
                    _LOGGER.debug(
                        "Associating Wireless Receiver X %s with room %s (%s) - room has %d devices",
                        device_data.get("serialNumber"),
                        other_room_id,
                        other_room_name,
                        max_device_count,
                    )

                device = TadoXDevice(
                    serial_number=device_data.get("serialNumber", ""),
                    device_type=device_type,
                    firmware_version=device_data.get("firmwareVersion", ""),
                    connection_state=other_device_connection.get("state", "DISCONNECTED"),
                    room_id=other_room_id,
                    room_name=other_room_name,
                )

                # If device has a room, add it to the room's device list
                if other_room_id and other_room_id in data.rooms:
                    data.rooms[other_room_id].devices.append(device)

                data.other_devices.append(device)
                data.devices[device.serial_number] = device

            # Process mobile devices
            for mobile_data in mobile_devices_data:
                device_id = mobile_data.get("id")
                if not device_id:
                    continue

                # Get location info
                location_data = mobile_data.get("location") or {}
                settings_data = mobile_data.get("settings") or {}
                geo_tracking = settings_data.get("geoTrackingEnabled", False)

                # Determine if at home based on location
                at_home = location_data.get("atHome", False)
                location_state = "HOME" if at_home else "AWAY" if location_data else None

                mobile_device = TadoXMobileDevice(
                    device_id=device_id,
                    name=mobile_data.get("name", f"Mobile {device_id}"),
                    device_metadata=mobile_data.get("deviceMetadata", {}),
                    location=location_state,
                    at_home=at_home,
                    geofencing_enabled=geo_tracking,
                )
                data.mobile_devices[device_id] = mobile_device

            # Fetch running times (or reuse the latest same-day snapshot).
            if self.enable_running_times:
                today = date.today().isoformat()
                cached = self._supplementary_cache.get("running_times")
                if (self.should_refresh_supplementary("running_times")
                        or not cached or cached[0] != today):
                    try:
                        _LOGGER.debug("Supplementary API request: running_times (home_id=%s)", self.home_id)
                        running_times_data = await self.api.get_running_times(today, today)
                        self.mark_supplementary_success("running_times", (today, running_times_data))
                    except Exception as err:
                        _LOGGER.warning("Failed to fetch running times data: %s", err)
                        running_times_data = cached[1] if cached and cached[0] == today else {}
                else:
                    running_times_data = cached[1]
                data.running_times = running_times_data
                for rt_entry in running_times_data.get("runningTimes", []):
                    for zone_data in rt_entry.get("zones", []):
                        zone_id = zone_data.get("id")
                        if zone_id in data.rooms:
                            data.rooms[zone_id].running_time_today_seconds = zone_data.get("runningTimeInSeconds", 0)

            # Fetch air comfort, preserving the last successful snapshot.
            if self.enable_air_comfort:
                if self.should_refresh_supplementary("air_comfort"):
                    try:
                        _LOGGER.debug("Supplementary API request: air_comfort (home_id=%s)", self.home_id)
                        air_comfort_data = await self.api.get_air_comfort()
                        comfort = {}
                        for comfort_entry in air_comfort_data.get("comfort", []):
                            room_id = comfort_entry.get("roomId")
                            if room_id:
                                comfort[room_id] = TadoXRoomAirComfort(
                                    room_id=room_id,
                                    freshness=comfort_entry.get("humidityLevel"),
                                    comfort_level=comfort_entry.get("temperatureLevel"),
                                )
                        self.mark_supplementary_success("air_comfort", comfort)
                    except Exception as err:
                        _LOGGER.warning("Failed to fetch air comfort data: %s", err)
                data.air_comfort = dict(self._supplementary_cache.get("air_comfort", {}))

            # Flow-temperature configuration is cached between supplementary polls.
            if self.enable_flow_temp:
                flow_data = self._supplementary_cache.get("flow_temp")
                if self.should_refresh_supplementary("flow_temp"):
                    try:
                        _LOGGER.debug("Supplementary API request: flow_temp (home_id=%s)", self.home_id)
                        flow_data = await self.api.get_flow_temperature_optimization()
                        self.mark_supplementary_success("flow_temp", flow_data)
                    except Exception as err:
                        _LOGGER.debug("Flow temperature optimization not available: %s", err)
                if flow_data:
                    data.has_flow_temp_control = True
                    data.max_flow_temperature = flow_data.get("maxFlowTemperature")
                    constraints = flow_data.get("maxFlowTemperatureConstraints") or {}
                    data.flow_temp_min = constraints.get("min")
                    data.flow_temp_max = constraints.get("max")
                    auto_adapt = flow_data.get("autoAdaptation") or {}
                    data.flow_temp_auto_adaptation = auto_adapt.get("enabled", False)
                    data.flow_temp_auto_value = auto_adapt.get("maxFlowTemperature")

            # Holiday Mode uses the same supplementary cadence but remains a
            # separate manager for manual refreshes and boundary callbacks.
            holiday_manager = getattr(self, "holiday_mode_manager", None)
            if holiday_manager is not None and holiday_manager.poll_enabled:
                if self.should_refresh_supplementary("holiday_mode"):
                    try:
                        _LOGGER.debug("Supplementary API request: holiday_mode (home_id=%s)", self.home_id)
                        await holiday_manager.refresh(notify=False, source="periodic")
                        self.mark_supplementary_success("holiday_mode", holiday_manager.data)
                    except Exception as err:
                        _LOGGER.warning("Holiday Mode periodic refresh failed for home %s: %s", self.home_id, err)

            # Populate API stats (prefer real values from headers when available)
            data.api_calls_today = self.api.api_calls_today
            data.api_reset_time = self.api.api_reset_time
            data.api_last_reset = self.api.api_last_reset
            data.api_last_observed_at = self.api.api_last_observed_at
            data.has_auto_assist = self.api.has_auto_assist
            data.api_quota_limit = self.api.api_quota_limit
            data.api_quota_remaining = self.api.api_quota_remaining
            data.api_rolling_daily_usage = self.api.api_rolling_daily_usage

            # Save API stats for persistence
            if self._save_api_stats_callback:
                self._save_api_stats_callback()

            return data

        except TadoXRateLimitError as err:
            # Handle rate limit gracefully - return previous data with rate_limited flag
            _LOGGER.warning(
                "Rate limit hit. Suspending API calls until %s. Using cached data.",
                err.reset_time,
            )
            if self.data:
                # Return previous data with rate_limited flag set
                self.data.rate_limited = True
                self.data.rate_limit_reset = err.reset_time
                return self.data
            # No previous data - create minimal data with rate limited status
            return TadoXData(
                home_id=self.home_id,
                home_name=self.home_name,
                rate_limited=True,
                rate_limit_reset=err.reset_time,
            )
        except TadoXAuthError as err:
            # Trigger reauthentication flow instead of just failing
            # This will prompt the user to re-authenticate via the UI
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}. Please re-authenticate."
            ) from err
        except TadoXApiError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching Tado X data")
            raise UpdateFailed(f"Unexpected error: {err}") from err
