"""Shared, validated live polling settings for the options UI and HA action."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ENABLE_HOLIDAY_POLLING, CONF_ENABLE_SCHEDULE_POLLING,
    CONF_SCHEDULE_POLL_INTERVAL, CONF_SCAN_INTERVAL,
    CONF_SUPPLEMENTARY_POLL_MULTIPLIER, SUPPLEMENTARY_POLL_MULTIPLIERS,
    CONF_ENABLE_WEATHER, CONF_ENABLE_AIR_COMFORT, CONF_ENABLE_RUNNING_TIMES,
    CONF_ENABLE_FLOW_TEMP, CONF_ENABLE_MOBILE_DEVICES, CONF_ENABLE_HOT_WATER,
    CONF_HAS_AUTO_ASSIST, FEATURE_ENTITY_MAP, DOMAIN,
)

BOOL_KEYS = (
    CONF_ENABLE_SCHEDULE_POLLING, CONF_ENABLE_HOLIDAY_POLLING,
    CONF_ENABLE_WEATHER, CONF_ENABLE_AIR_COMFORT, CONF_ENABLE_RUNNING_TIMES,
    CONF_ENABLE_FLOW_TEMP, CONF_ENABLE_MOBILE_DEVICES, CONF_ENABLE_HOT_WATER,
)
POLLING_KEYS = (CONF_SCAN_INTERVAL, CONF_SCHEDULE_POLL_INTERVAL,
                CONF_SUPPLEMENTARY_POLL_MULTIPLIER, *BOOL_KEYS)


def validate_polling_changes(changes: dict) -> dict:
    """Reject invalid settings before any stored or live state is modified."""
    invalid = set(changes) - set(POLLING_KEYS)
    if invalid:
        raise HomeAssistantError(f"Unsupported polling options: {', '.join(sorted(invalid))}")
    for key, value in changes.items():
        if key in BOOL_KEYS:
            if not isinstance(value, bool):
                raise HomeAssistantError(f"{key} must be true or false")
        elif type(value) is not int:
            raise HomeAssistantError(f"{key} must be an integer")
        elif key == CONF_SCAN_INTERVAL and not 30 <= value <= 3600:
            raise HomeAssistantError("scan_interval must be 30–3600 seconds")
        elif key == CONF_SCHEDULE_POLL_INTERVAL and not 900 <= value <= 86400:
            raise HomeAssistantError("schedule_poll_interval must be 900–86400 seconds")
        elif key == CONF_SUPPLEMENTARY_POLL_MULTIPLIER and value not in SUPPLEMENTARY_POLL_MULTIPLIERS:
            raise HomeAssistantError("supplementary_poll_multiplier must be 1, 2, 5 or 10")
    return changes


async def apply_polling_changes(hass, entry, coordinator, changes: dict) -> None:
    """Persist and apply a complete validated patch, without needless API calls."""
    validate_polling_changes(changes)
    changed = {key: value for key, value in changes.items() if entry.data.get(key) != value}
    if not changed:
        return
    hass.config_entries.async_update_entry(entry, data={**entry.data, **changed})
    if coordinator is None:
        return
    if CONF_SCAN_INTERVAL in changed:
        coordinator.update_scan_interval(changed[CONF_SCAN_INTERVAL])
    if CONF_SUPPLEMENTARY_POLL_MULTIPLIER in changed:
        coordinator.update_supplementary_settings(changed[CONF_SUPPLEMENTARY_POLL_MULTIPLIER])
    if CONF_ENABLE_SCHEDULE_POLLING in changed or CONF_SCHEDULE_POLL_INTERVAL in changed:
        manager = getattr(coordinator, "schedule_profile_manager", None)
        if manager:
            manager.configure_polling(entry.data.get(CONF_ENABLE_SCHEDULE_POLLING, entry.data.get(CONF_HAS_AUTO_ASSIST, False)),
                                      entry.data.get(CONF_SCHEDULE_POLL_INTERVAL, 3600))
    if CONF_ENABLE_HOLIDAY_POLLING in changed:
        manager = getattr(coordinator, "holiday_mode_manager", None)
        if manager:
            manager.configure_polling(changed[CONF_ENABLE_HOLIDAY_POLLING])
    for key in (CONF_ENABLE_WEATHER, CONF_ENABLE_AIR_COMFORT, CONF_ENABLE_RUNNING_TIMES,
                CONF_ENABLE_FLOW_TEMP, CONF_ENABLE_MOBILE_DEVICES, CONF_ENABLE_HOT_WATER):
        if key in changed:
            setattr(coordinator, key, changed[key])
            if changed[key]:
                coordinator.invalidate_supplementary({
                    CONF_ENABLE_WEATHER: "weather", CONF_ENABLE_AIR_COMFORT: "air_comfort",
                    CONF_ENABLE_RUNNING_TIMES: "running_times", CONF_ENABLE_FLOW_TEMP: "flow_temp",
                }.get(key, key))
            else:
                feature = {CONF_ENABLE_WEATHER: "weather", CONF_ENABLE_AIR_COMFORT: "air_comfort",
                           CONF_ENABLE_RUNNING_TIMES: "running_times", CONF_ENABLE_FLOW_TEMP: "flow_temp"}.get(key)
                if feature:
                    coordinator._supplementary_cache.pop(feature, None)
                    coordinator.invalidate_supplementary(feature)
    if any(key in changed for key in (CONF_ENABLE_WEATHER, CONF_ENABLE_AIR_COMFORT, CONF_ENABLE_RUNNING_TIMES,
                                      CONF_ENABLE_FLOW_TEMP, CONF_ENABLE_MOBILE_DEVICES, CONF_ENABLE_HOT_WATER)):
        registry = er.async_get(hass)
        for feature_flag, entity_keys in FEATURE_ENTITY_MAP.items():
            for entity_id, entity in list(registry.entities.items()):
                if (entity.platform != DOMAIN or entity.domain not in ("sensor", "button", "select")
                        or entity.config_entry_id != entry.entry_id
                        or entity.disabled_by not in (None, er.RegistryEntryDisabler.INTEGRATION)
                        or not entity.unique_id):
                    continue
                if any(entity.unique_id.endswith(f"_{suffix}") for suffix in entity_keys):
                    desired = None if getattr(coordinator, feature_flag, False) else er.RegistryEntryDisabler.INTEGRATION
                    if entity.disabled_by != desired:
                        registry.async_update_entity(entity_id, disabled_by=desired)

    # Publish the new theoretical estimate immediately, without an API refresh.
    coordinator.async_update_listeners()
