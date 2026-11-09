# Actions Reference

[README](../README.md) · [Schedules](SCHEDULES.md) · [Examples](EXAMPLES.md) · [Architecture](ARCHITECTURE.md)

Tado X Enhanced v1.2.0 registers **20 actions** under `tado_x`, available in **Developer Tools → Actions**. The following parameters were checked against the service schemas in `custom_components/tado_x/__init__.py` and descriptions in `services.yaml`.

**Targeting:** `entity_id` identifies a room climate entity and resolves its home. For home-level actions, `device_id` identifies the **Tado X Home** device; it may be omitted only when a single home is configured. `set_temperature_offset` requires the physical device's `device_id`. Profile names are free-text strings (up to 80 characters), validated against the names defined for the selected home.

| Action (`tado_x.` prefix) | Purpose | Inputs |
|---|---|---|
| `set_temperature_offset` | Physical-device temperature offset | `device_id` (required), `offset` (required; −9.9 to +9.9 °C) |
| `add_meter_reading` | Submit Energy IQ meter reading | `reading` (required nonnegative integer), `date` (optional YYYY-MM-DD), `device_id` (optional home device) |
| `set_eiq_tariff` | Set Energy IQ tariff | `tariff` (required nonnegative number), `unit` (`m3` or `kWh`), `start_date`, `end_date` (optional), `device_id` (optional home device) |
| `set_climate_timer` | Room temperature override | `entity_id` (required climate), `temperature` (5–30 °C; required for a change), `termination_type` (`TIMER`, `MANUAL`, `NEXT_TIME_BLOCK`; defaults to `TIMER`), `duration` (1–1440 minutes; required for `TIMER`) |
| `get_schedule` | Read room Home schedule | `entity_id` (required climate) |
| `set_schedule` | Write a complete selected Home day schedule | `entity_id`, `day_type`, `schedule` (all required; `schedule` is a JSON **string** of blocks) |
| `get_away_schedule` | Read room Away configuration | `entity_id` (required climate) |
| `set_away_schedule` | Write room Away configuration | `entity_id` and `mode` (`ON`/`OFF`) required; `away_temperature` (0.1–49.9 °C) and `preheating_level` (`OFF`/`ECO`/`BALANCE`/`COMFORT`) optional |
| `get_day_report` | Read room historical report | `entity_id` (required climate), `date` (optional) |
| `get_holiday_mode` | Read home holiday mode | `device_id` (optional home device) |
| `set_holiday_mode` | Set home holiday mode | `enabled` (required boolean), `start_date`, `end_date` (optional), `device_id` (optional home device) |
| `save_schedule_profile` | Save live room Home/Away schedule under an existing profile name | `entity_id`, `profile` (both required) |
| `restore_schedule_profile` | Apply saved room profile or home default fallback | `entity_id`, `profile` (both required) |
| `list_schedule_profiles` | Return profile names, saved/default state and current matching status | `entity_id` (required); returns response data |
| `save_schedule_profile_default` | Save live room Home/Away schedule as a home-wide default | `entity_id`, `profile` (both required) |
| `restore_schedule_profile_default` | Apply home-wide default to selected room | `entity_id`, `profile` (both required) |
| `create_schedule_profile` | Create a custom home-wide profile class | `profile` (required), `device_id` (optional home device) |
| `delete_schedule_profile` | Delete a custom home-wide profile class and its saved data | `profile` (required), `device_id` (optional home device); built-ins prohibited |
| `set_polling_options` | Change per-home polling settings without restarting | `device_id` (optional for single home); any subset of supported polling fields listed below |
| `reset_schedule_default` | Reset a built-in home-wide default to factory fallback | `profile` (required built-in name), `device_id` (optional home device) |

## Climate override example

```yaml
action: tado_x.set_climate_timer
data:
  entity_id: climate.living_room
  temperature: 21
  termination_type: TIMER
  duration: 60
```

For `MANUAL` and `NEXT_TIME_BLOCK`, omit `duration`. The entity ID is illustrative.

## Set schedule: input format

`day_type` must be one of the supported day/group options in the action selector. Each JSON block's `dayType` must match the selected value. The first block must begin at `00:00`, adjacent blocks must meet exactly, and the last must end at `24:00`. `ON` requires numeric `setting.temperature.value`. The action field `schedule` must be a **string containing JSON**, not a YAML array.

```yaml
action: tado_x.set_schedule
data:
  entity_id: climate.living_room
  day_type: MONDAY
  schedule: >-
    [{"dayType":"MONDAY","start":"00:00","end":"07:00","setting":{"power":"ON","temperature":{"value":18.0}}},
     {"dayType":"MONDAY","start":"07:00","end":"24:00","setting":{"power":"ON","temperature":{"value":21.0}}}]
```

## Profile scope and defaults

The built-in names are **Normal**, **Alternative**, **Eco** and **Not in use**. Additional names are created per home using `create_schedule_profile`. `save_schedule_profile` and `restore_schedule_profile` work with a room-specific saved profile (falling back to a home default on restore); `save_schedule_profile_default` and `restore_schedule_profile_default` explicitly manage/apply the **home-wide default**. `delete_schedule_profile` deletes a custom profile **across the selected home**, not merely a room's copy. `reset_schedule_default` resets only built-in home defaults.

`list_schedule_profiles` returns profile availability and matching status for the requested room. Its response keys include `profiles`, `home_defaults`, `current`, `status` and `matching_profiles`.

## API and testing notes

Read and write operations require Tado cloud access and are subject to API quotas. Some actions require hardware, subscription or account capabilities. Schedule restoration may involve multiple remote writes; it is not an atomic transaction. See [SCHEDULES.md](SCHEDULES.md) for workflows and [ARCHITECTURE.md](ARCHITECTURE.md) for validation and recovery behaviour.


### Holiday Mode and the home switch
`set_holiday_mode` offers local date/time pickers for optional start and end dates. YAML also accepts timezone-aware ISO-8601 timestamps. Both start and end times must be on a **30-minute boundary (HH:00 or HH:30)**. Supplying one date preserves the other existing boundary; date updates are checked against Tado after submission and raise an error if the dates are not retained. Explicit past start dates are accepted. The Holiday Mode switch provides automatic seven-day rescheduling only when the stored period has expired.

## Programmatic polling configuration

`tado_x.set_polling_options` accepts an optional Tado X Home `device_id` and any subset of polling options. The device is inferred when exactly one Tado X home is configured; with multiple homes, select the Tado X Home device. Unspecified options remain unchanged. All settings are validated before being saved and applied immediately, without a Home Assistant restart. Changes persist after restart.

```yaml
action: tado_x.set_polling_options
data:
  device_id: YOUR_TADO_X_HOME_DEVICE_ID
  scan_interval: 300
  supplementary_poll_multiplier: 10
  enable_schedule_polling: false
  enable_holiday_polling: true
```

The `device_id` line may be omitted for a single-home installation.

Supported optional fields: `scan_interval` (30–3600), `supplementary_poll_multiplier` (1, 2, 5, 10), `schedule_poll_interval` (900–86400), `enable_schedule_polling`, `enable_holiday_polling`, `enable_weather`, `enable_air_comfort`, `enable_running_times`, `enable_flow_temp`, `enable_mobile_devices` and `enable_hot_water`. All `enable_*` fields are booleans. A day/night automation should also run at Home Assistant startup to restore the appropriate current setting after a restart.
