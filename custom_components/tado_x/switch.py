"""Switch platform for Tado X."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_TYPE_NAMES, DOMAIN
from .coordinator import TadoXDataUpdateCoordinator, TadoXDevice, TadoXRoom

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tado X switch entities."""
    coordinator: TadoXDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []

    # Add child lock switch for each device that supports it (valves and thermostats)
    for device in coordinator.data.devices.values():
        if device.device_type in ("VA04", "TR04"):  # Valve and Thermostat
            entities.append(TadoXChildLockSwitch(coordinator, device.serial_number))

    # Add open window switch for each room
    for room_id in coordinator.data.rooms:
        entities.append(TadoXOpenWindowSwitch(coordinator, room_id))

    # Add flow temperature auto-adaptation switch if available
    if coordinator.data and coordinator.data.has_flow_temp_control:
        entities.append(TadoXFlowTempAutoAdaptationSwitch(coordinator))

    if coordinator.data.adaptive_heating_enabled is not None:
        entities.append(TadoXAdaptiveHeatingSwitch(coordinator))

    # Hydronic balancing can reset its learned state when disabled.
    # Register controls on supported installations, initially disabled.
    if coordinator.data.hydronic_balancing_enabled is not None:
        entities.append(TadoXHydronicBalancingSwitch(coordinator))

    entities.append(TadoXHolidayModeSwitch(coordinator))
    async_add_entities(entities)


class TadoXAdaptiveHeatingSwitch(
    CoordinatorEntity[TadoXDataUpdateCoordinator], SwitchEntity
):
    """Control the per-home Adaptive Heating setting."""

    _attr_has_entity_name = True
    _attr_translation_key = "adaptive_heating"
    _attr_icon = "mdi:radiator"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: TadoXDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.home_id}_adaptive_heating"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, str(self.coordinator.home_id))},
            name=self.coordinator.home_name,
            manufacturer="Tado",
            model="Tado X Home",
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.adaptive_heating_enabled is not None
        )

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return data.adaptive_heating_enabled if data else None

    async def _set_enabled(self, enabled: bool) -> None:
        await self.coordinator.api.set_adaptive_heating(enabled)
        self.coordinator.invalidate_adaptive_heating()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_enabled(False)


class TadoXHydronicBalancingSwitch(
    CoordinatorEntity[TadoXDataUpdateCoordinator], SwitchEntity
):
    """Home-level hydronic balancing control.

    Turning the feature off can reset Tado's learned balancing data.
    Dashboard confirmation is recommended but cannot protect service calls.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "hydronic_balancing"
    _attr_icon = "mdi:pipe"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: TadoXDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.home_id}_hydronic_balancing"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, str(self.coordinator.home_id))},
            name=self.coordinator.home_name,
            manufacturer="Tado",
            model="Tado X Home",
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.hydronic_balancing_enabled is not None
        )

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return data.hydronic_balancing_enabled if data else None

    @property
    def extra_state_attributes(self) -> dict[str, bool] | None:
        data = self.coordinator.data
        if data and data.hydronic_balancing_panasonic_interface is not None:
            return {"panasonic_therm_interface": data.hydronic_balancing_panasonic_interface}
        return None

    async def _set_enabled(self, enabled: bool) -> None:
        await self.coordinator.api.set_hydronic_balancing(enabled)
        self.coordinator.invalidate_hydronic_balancing()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_enabled(False)


class TadoXChildLockSwitch(CoordinatorEntity[TadoXDataUpdateCoordinator], SwitchEntity):
    """Tado X child lock switch entity."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:lock-outline"

    def __init__(
        self,
        coordinator: TadoXDataUpdateCoordinator,
        serial_number: str,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_child_lock"
        self._attr_translation_key = "child_lock"

    @property
    def _device(self) -> TadoXDevice | None:
        """Get the device data."""
        return self.coordinator.data.devices.get(self._serial_number)

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return "Child Lock"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        device = self._device
        if not device:
            return DeviceInfo(
                identifiers={(DOMAIN, self._serial_number)},
            )


        via_device_identifier = (
            (DOMAIN, f"{self.coordinator.home_id}_{device.room_id}")
            if device.room_id
            else (DOMAIN, str(self.coordinator.home_id))
        )

        base_name = DEVICE_TYPE_NAMES.get(device.device_type, device.device_type)

        if device.room_id and device.room_name:
            same_type_in_room = sorted([
                d.serial_number for d in self.coordinator.data.devices.values()
                if d.room_id == device.room_id and d.device_type == device.device_type
            ])

            if len(same_type_in_room) > 1:
                device_number = same_type_in_room.index(self._serial_number) + 1
                device_name = f"{base_name} {device_number} - {device.room_name}"
            else:
                device_name = f"{base_name} - {device.room_name}"
        else:
            device_name = f"{base_name} ({self._serial_number[-4:]})"

        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=device_name,
            manufacturer="Tado",
            model=DEVICE_TYPE_NAMES.get(device.device_type, device.device_type),
            serial_number=device.serial_number,
            sw_version=device.firmware_version,
            via_device_id=self.coordinator.parent_device_ids[via_device_identifier],
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if child lock is enabled."""
        device = self._device
        if not device:
            return None
        return device.child_lock_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable child lock."""
        await self.coordinator.api.set_child_lock(self._serial_number, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable child lock."""
        await self.coordinator.api.set_child_lock(self._serial_number, False)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TadoXOpenWindowSwitch(CoordinatorEntity[TadoXDataUpdateCoordinator], SwitchEntity):
    """Tado X open window switch entity.

    When on: open window mode is active (heating reduced)
    Turn off: reset/dismiss open window detection
    Turn on: only works if open window was detected by the system
    """

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:window-open-variant"

    def __init__(
        self,
        coordinator: TadoXDataUpdateCoordinator,
        room_id: int,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_unique_id = f"{coordinator.home_id}_{room_id}_open_window"
        self._attr_translation_key = "open_window"

    @property
    def _room(self) -> TadoXRoom | None:
        """Get the room data."""
        return self.coordinator.data.rooms.get(self._room_id)

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return "Open Window"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        room = self._room
        room_name = room.name if room else f"Room {self._room_id}"

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.home_id}_{self._room_id}")},
            name=room_name,
            manufacturer="Tado",
            model="Tado X Room",
            via_device_id=self.coordinator.parent_device_ids[(DOMAIN, str(self.coordinator.home_id))],
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if open window mode is active."""
        room = self._room
        if not room:
            return None
        return room.open_window_detected

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate open window mode (only if system detected an open window)."""
        await self.coordinator.api.set_open_window_detection(self._room_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Reset/dismiss open window detection."""
        await self.coordinator.api.set_open_window_detection(self._room_id, False)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TadoXFlowTempAutoAdaptationSwitch(CoordinatorEntity[TadoXDataUpdateCoordinator], SwitchEntity):
    """Tado X flow temperature auto-adaptation switch.

    When enabled, Tado automatically adjusts the max flow temperature
    based on outdoor conditions to improve energy efficiency.
    """

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:auto-fix"
    _attr_translation_key = "flow_temp_auto_adaptation"

    def __init__(self, coordinator: TadoXDataUpdateCoordinator) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.home_id}_flow_temp_auto_adaptation"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the home."""
        home_name = self.coordinator.home_name or f"Tado Home {self.coordinator.home_id}"
        return DeviceInfo(
            identifiers={(DOMAIN, str(self.coordinator.home_id))},
            name=home_name,
            manufacturer="Tado",
            model="Tado X Home",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if auto-adaptation is enabled."""
        data = self.coordinator.data
        if not data or not data.has_flow_temp_control:
            return None
        return data.flow_temp_auto_adaptation

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        data = self.coordinator.data
        return data is not None and data.has_flow_temp_control

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable flow temperature auto-adaptation."""
        await self.coordinator.api.set_flow_temp_auto_adaptation(True)
        self.coordinator.invalidate_supplementary("flow_temp")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable flow temperature auto-adaptation."""
        await self.coordinator.api.set_flow_temp_auto_adaptation(False)
        self.coordinator.invalidate_supplementary("flow_temp")
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class TadoXHolidayModeSwitch(CoordinatorEntity[TadoXDataUpdateCoordinator], SwitchEntity):
    """Home-level holiday enable switch."""

    _attr_has_entity_name = True
    _attr_name = "Holiday Mode"
    _attr_translation_key = "holiday_mode"
    _attr_icon = "mdi:beach"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.home_id}_holiday_mode"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, str(self.coordinator.home_id))})

    @property
    def available(self) -> bool:
        return self.coordinator.holiday_mode_manager.data is not None

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.holiday_mode_manager.data
        return data.get("enabled") if data else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.holiday_mode_manager.set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.holiday_mode_manager.set_enabled(False)
