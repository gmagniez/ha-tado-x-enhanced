# Tado X Enhanced — Technical Architecture

**Documented version:** Tado X Enhanced `1.2.0`  
**Implementation source:** `custom_components/tado_x/` in this repository  
**Integration domain:** `tado_x`  
**Repository:** https://github.com/rleatherb/ha-tado-x-enhanced  
**Audience:** maintainers and contributors

> This document describes the source implementation. It does not constitute comprehensive live Home Assistant or Tado API validation. Behaviour depends on Tado hardware, subscription, account capabilities and API responses.

## 1. Design goals and invariants

Tado X Enhanced extends Exabird's original Home Assistant Tado X integration while retaining the domain `tado_x`. Its principal design requirements are:

- Support multiple configured Tado homes, including homes with identical room IDs.
- Preserve existing Home Assistant configuration entries, entity identities and established action names wherever possible.
- Scope API calls, device operations, room state, schedule profiles and options to the correct home.
- Preserve normal thermostat control, manual overrides, hot-water features, historical data, schedules and optional monitoring.
- Control cloud API consumption, especially when automatic schedule checking is enabled.
- Keep translated labels, action descriptions and implementation aligned.

The enhanced integration **replaces**, rather than runs alongside, another integration using the `tado_x` domain. A Home Assistant backup is recommended before replacement. Compatibility must be tested against existing installations; unchanged domain alone is not proof of a risk-free upgrade.

## 2. Package and module boundaries

All executable integration files reside in `custom_components/tado_x/`.

| Module | Responsibility |
|---|---|
| `manifest.json` | Integration metadata, dependencies, version and repository links |
| `const.py` | Domain, API hosts, feature flags, defaults, polling constants, platform names |
| `config_flow.py` | OAuth device authorisation, home selection, reauthentication and options |
| `__init__.py` | Entry setup/unload, coordinator wiring, schedule validation, global action registration and routing |
| `api.py` | HTTP requests, authentication/token refresh, API errors, rate-limit observations and Tado endpoints |
| `coordinator.py` | Per-home data refresh, typed room/device/home data models and optional feature retrieval |
| `schedule_profiles.py` | Home-scoped persistent profile manager, Home/Away snapshots, comparison, defaults, restore and polling |
| `climate.py` | Room thermostat, HVAC mode/action, presets, temperature and override behaviour |
| `sensor.py` | Home, room, device, weather and air-comfort sensors |
| `binary_sensor.py` | Room and physical-device binary sensors |
| `select.py` | Presence, hot-water mode, termination type and room profile controls |
| `number.py` | Flow-temperature and per-room timer-duration controls |
| `button.py` | Heating/hot-water actions and room schedule refresh |
| `switch.py` | Child lock, open-window detection and flow-temperature adaptation |
| `device_tracker.py` | Mobile-device geofencing entities |
| `services.yaml` | Home Assistant action fields and UI descriptions |
| `strings.json`, `translations/*.json` | Translation keys and English, German, French, Italian and Spanish strings |

The root-level `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, `hacs.json` and `docs/` belong to the **repository**, not inside `custom_components/tado_x/`.

## 3. Lifecycle and data flow

```text
Home Assistant config entry (one selected Tado home)
  └─ async_setup_entry (__init__.py)
      ├─ TadoXApi (api.py): auth, requests, quota observations
      ├─ TadoXDataUpdateCoordinator (coordinator.py)
      │   └─ TadoXData: rooms, devices, presence, optional datasets
      ├─ ProfileManager (schedule_profiles.py)
      │   ├─ home-specific persistent profile store
      │   └─ optional independent schedule comparison timer
      ├─ Home Assistant platforms (climate, sensors, selects, etc.)
      └─ domain-wide actions, with target resolution at call time
```

On entry setup, the integration obtains a Home Assistant `aiohttp` session, constructs a Tado API client from the entry's saved credentials, refreshes authentication, creates a coordinator for the selected home and performs an initial refresh. It then loads the home-specific schedule-profile store, captures the live **Normal** Home/Away profile for any room that lacks one, configures schedule polling, forwards the entry to the entity platforms and registers domain actions.

The coordinator is stored under `hass.data["tado_x"][entry.entry_id]`. Each entry has its own coordinator and API client. Entity platforms read coordinator data and publish entities to Home Assistant. Unloading an entry stops its profile polling and unloads its platforms; domain-level actions must continue to work for other configured entries.

### 3.1 Per-home data model

`coordinator.py` defines dataclasses including `TadoXData`, `TadoXRoom`, `TadoXDevice`, `TadoXRoomControlDefaults`, `TadoXWeather`, `TadoXMobileDevice` and `TadoXRoomAirComfort`.

`TadoXData` includes the home identity, rooms indexed by room ID, physical devices, presence, API quota observations, and optional weather, mobile, running-time, air-comfort, flow-temperature and domestic-hot-water data. The coordinator refreshes this snapshot, which is consumed by the platform entities. The profile manager separately fetches complete Home/Away schedules: these are **not** placed wholesale into climate entity attributes.

## 4. Authentication and Tado API

`api.py` uses the Tado OAuth device-authorisation flow and stores access/refresh token state through config-entry callbacks. The client refreshes credentials as required and exposes errors through `TadoXAuthError`, `TadoXApiError` and `TadoXRateLimitError`.

The code defines hosts for Tado login, Hops, `my.tado.com`, Energy IQ and Minder APIs in `const.py`. API methods cover home and room discovery, temperature control, presence, schedules, Away configuration, historical day reports, holiday mode, weather, air comfort, running times, flow-temperature optimisation, Energy IQ and domestic hot water.

The integration depends on **cloud APIs**, not local Matter control. Endpoint availability and response shapes are outside the project's control. Do not assume all features exist for every account or device. In particular, schedule and Away operations use the implemented Tado X API paths; do not substitute older Tado V3 zone endpoints without verifying compatibility.

### 4.1 API quota monitoring

The client observes quota/remaining values from server response headers. It tracks previous observations, detects a substantial fall in used calls as evidence of a reset and derives an **estimated** next reset time. Home Assistant exposes quota, remaining calls, current usage, observed rolling daily usage and theoretical daily usage sensors.

The observed estimated daily percentage is a rolling 60-minute projection from server quota-header observations, with a 10-minute minimum sampling period. The per-API-client history is bounded and held only in memory, is cleared on a counter decrease or quota change, and requires no extra API requests. It is not a Tado-issued forecast; it can be unavailable until enough observations have been collected, and can exceed 100%. A separate theoretical daily percentage is calculated from live coordinator options and schedule manager settings, using the number of discovered rooms and a per-feature periodic request model. The theoretical estimate updates on polling option changes without extra Tado API requests. The observed rolling estimate retains a fixed 60-minute window, but its stale-reading tolerance adapts to the main polling interval. The effective quota scope must not be assumed to be independent per home. The code includes nominal free and Auto-Assist limits of 100 and 20,000 calls/day respectively, but server-reported values should be preferred to assumptions.

## 5. Multi-home architecture and identity

The configuration flow lets an account holder select a Tado home and prevents duplicate entries for the same home. Each configured home is represented by its own entry and coordinator. The integration intentionally supports rooms with the same numeric ID in different homes.

**Critical rule:** never resolve a room from its numeric ID alone. Room-targeted actions first resolve the Home Assistant climate entity via the entity registry and its config-entry ID, then check that its home ID and room ID agree with the selected coordinator. Home-level actions resolve an explicitly supplied Tado home device when multiple homes are present; omission is only unambiguous for a single home.

Entity/device unique IDs and service routing must continue to include or resolve the home context. The current implementation derives the home and room from registered climate entity identity for room actions. When modifying these mechanisms, test two homes with overlapping room IDs.

## 6. Coordinator polling and optional datasets

The main coordinator polls current room, device and home state. Its default scan interval depends on the configured subscription tier, with a per-entry override supported by the options flow. Constants in `const.py` specify a nominal 45-minute free-tier default and 30-second Auto-Assist default; the user-configurable main interval is 30–3,600 seconds.

Optional feature flags control additional data retrieval and entity availability:

- Weather and solar information
- Mobile devices and geofencing
- Air comfort
- Heating running times
- Flow-temperature optimisation
- Domestic hot water

These are per-home options. Defaults are influenced by the configured Auto-Assist status. Enabling additional datasets may increase API consumption. Mobile Devices and Domestic Hot Water use the main coordinator interval. Weather, Air Comfort, Heating Running Times, Flow Temperature and Holiday Mode use a per-home supplementary multiplier (1×, 2×, 5× or 10× the main interval, default 5×). Supplementary datasets are cached between eligible checks. Holiday Mode retains a separate manager for manual reads and scheduled boundary callbacks, but no independent periodic timer. Flow Temperature actions invalidate the cache to read back the changed settings promptly. The `tado_x.set_polling_options` action and the options flow use the same live configuration update path; the action resolves an optional Tado X Home device, defaulting to the only configured home when unambiguous.

**Schedule polling is separate from main coordinator polling.** The profile manager checks Home and Away configurations at an independently configured interval: 900–86,400 seconds, default 3,600 seconds. Automatic schedule checking defaults on for Auto-Assist configurations and off otherwise, subject to saved options. A full comparison ordinarily requires approximately **two schedule API requests per room**. Manual schedule refresh and profile actions remain available when automatic checking is disabled.

## 7. Climate and room controls

`climate.py` exposes a thermostat per Tado room. The room model includes current and target temperature, humidity, heating demand, power, connection state, manual control and open-window information. The climate entity exposes standard Home Assistant climate functionality and, where available, attributes including:

- `heating_power`
- `manual_control_active`, `manual_control_type`, `manual_control_remaining_minutes`
- `next_schedule_change`, `next_schedule_temperature`
- `open_window_detected`, `open_window_ends_at`, `open_window_remaining_minutes`

`hvac_action` is implemented as a standard climate property; it is not an extra-state attribute. The separate **Next Schedule Power** sensor reports the upcoming ON/OFF state.

Manual temperature overrides support `TIMER`, `MANUAL` and `NEXT_TIME_BLOCK`. The `tado_x.set_climate_timer` action accepts an explicit temperature and a duration for timed overrides. Normal climate-card changes use the room's configured default termination behaviour, with the per-room termination-type select and timer-duration number providing control.

Other room/device controls include open-window detection, child lock, temperature offset, heating power, battery and connectivity indicators, and a room **Refresh Schedule** button.

## 8. Schedule representation and actions

A Home schedule is represented as blocks with `dayType`, `start`, `end` and `setting` (`power`, and temperature where ON). The code validates a replacement day's blocks to ensure:

1. Each block belongs to the selected day type.
2. The first block starts at `00:00`.
3. Adjacent blocks are contiguous, with no gaps or overlaps.
4. Each block has a valid positive duration and valid ON/OFF setting.
5. The final block ends at `24:00`.

The `set_schedule` action's **schedule** input is a JSON-encoded string containing an array of blocks; it is not an arbitrary YAML object. The integration supports named day types and grouping choices in the action schema. See [ACTIONS.md](ACTIONS.md) and [SCHEDULES.md](SCHEDULES.md) for the public interface.

Away configuration is stored separately from the weekly Home schedule and includes mode, Away temperature and preheating level. The integration provides explicit read/write Away actions. Changes to a live schedule do not automatically overwrite stored named profiles.

### 8.1 Registered actions

The source defines **19** `tado_x` actions:

| Area | Actions |
|---|---|
| Existing/extended controls | `set_temperature_offset`, `add_meter_reading`, `set_eiq_tariff`, `set_climate_timer` |
| Home/Away schedules | `get_schedule`, `set_schedule`, `get_away_schedule`, `set_away_schedule` |
| Historical/holiday data | `get_day_report`, `get_holiday_mode`, `set_holiday_mode` |
| Profiles | `save_schedule_profile`, `restore_schedule_profile`, `list_schedule_profiles`, `delete_schedule_profile`, `create_schedule_profile`, `save_schedule_profile_default`, `restore_schedule_profile_default`, `reset_schedule_default` |

Action schemas and response support are implemented in `__init__.py`; field descriptions live in `services.yaml`, with corresponding translation entries. The read-oriented actions return data where implemented. Do not rename established action identifiers or change their parameters without a deliberate compatibility decision.

## 9. Schedule-profile subsystem

`ProfileManager` in `schedule_profiles.py` maintains independent profile data **per home**. It separates **home-wide profile names** from **per-room saved schedules** and **home-wide default templates**.

### 9.1 Names and storage

Four built-in names always exist: **Normal**, **Alternative**, **Eco** and **Not in use**. Additional names can be created home-wide; they then become available in every room of that home. Creating a custom name initialises its home default from the effective **Normal** home default. Custom names are not automatically shared between homes.

Each saved room profile contains a snapshot of the full weekly Home schedule and its Away settings. A room-specific saved profile takes precedence; if none exists for that name, the manager uses the home-wide default. Home defaults may themselves be customised by saving a room's live schedule as that default. Resetting a default discards its customised version and reveals the factory fallback, without changing any active room schedule.

The manager uses Home Assistant's `Store` helper with **storage version 1** and the key:

```text
tado_x_schedule_profiles_<home_id>
```

The persisted structure contains `profiles`, `home_defaults`, `custom_names` and `last_applied`. Room IDs are keys **within** a home-specific store. Storage migration code from intermediate development builds was intentionally removed; do not introduce speculative migrations without an actual supported upgrade path.

### 9.2 Factory fallback schedules

The following schedules are implemented in `default_snapshot()` and apply only when a more specific saved profile/default is absent:

| Profile | Home schedule | Away settings |
|---|---|---|
| Normal | Every day: 00:00–07:30 18°C; 07:30–22:00 20°C; 22:00–24:00 18°C | ON, 17°C, BALANCE |
| Alternative | Weekdays: 00:00–06:30 18°C; 06:30–08:30 20°C; 08:30–16:30 18°C; 16:30–22:00 20°C; 22:00–24:00 18°C; weekends as Normal | ON, 17°C, BALANCE |
| Eco | Every day: 00:00–07:30 17°C; 07:30–22:00 18°C; 22:00–24:00 17°C | ON, 16°C, BALANCE |
| Not in use | Every day: 00:00–24:00 14°C | ON, 14°C, BALANCE |

Existing customised home defaults and saved room profiles take priority over these factory values.

### 9.3 First-run capture, matching and controls

During entry setup, rooms without a saved **Normal** profile have their current Tado Home/Away settings captured as Normal. A failed capture leaves the room unchanged for a later retry. This protects a user's existing app schedule before other profiles are applied.

The manager compares live snapshots against effective named profiles. It canonicalises Home blocks by day, boundaries, power and temperature and also compares Away settings. A matching profile is shown in the room's restore/save selectors; otherwise the state is **Custom**. A failed read is treated as unavailable rather than incorrectly reporting Custom. The last-applied profile helps choose between multiple matches.

The room device exposes **Restore schedule profile** and **Save schedule profile** selects, plus **Refresh Schedule**. The former **Restore default schedule profile** and **Save default schedule profile** device selectors are not exposed; their functions remain available through `tado_x.restore_schedule_profile_default` and `tado_x.save_schedule_profile_default` actions. Room selectors contain profile names only, not suffixed `… default` entries.

The profile actions use a free-text `profile` input, checked against the home-specific known names. Built-in names cannot be deleted. A custom profile name is created before it can be saved/restored, and deleting a custom name removes that class and its saved room/default data for the selected home.

### 9.4 Restore and failure handling

A restore validates the complete weekly Home schedule and Away configuration before writing. It compares the requested and current schedule and writes only changed days, followed by Away settings if needed. On write failure, it attempts a best-effort rollback of changed days and Away settings; rollback itself may fail and is reported. It then reads back the applied schedule and verifies the result. On success, it requests an immediate coordinator refresh so the room's schedule-change sensors update without waiting for the normal poll.

A restore is **not an atomic Tado-side transaction**. Failed writes, failed rollback or failed verification may leave the live schedule partially changed. This is a significant test case for maintainers.

## 10. Domestic hot water

Where supported and enabled, the coordinator retrieves domestic-hot-water state, boost expiry and next schedule-change data. `select.py` maps Tado's underlying states to user-facing **Schedule**, **Off** and **Boost** controls, including Away-related cases. Buttons can boost hot water, switch it off or resume its schedule. These functions depend on the home's actual hot-water equipment and the API response.

Keep the distinction between **Away with hot water still following its schedule** and **Away with hot water switched off**. Treating both as Off would regress a previously corrected behaviour.

## 11. Other supported capabilities

- **Historical day reports:** `get_day_report` retrieves room history and returns the original report together with a computed summary (`summarize_day_report()` in `api.py`).
- **Holiday mode:** read/write home-level holiday settings where the account supports them.
- **Energy IQ:** meter readings and tariff configuration.
- **Weather and air comfort:** optional home/room data and sensors.
- **Running times:** optional daily room heating duration.
- **Flow temperature:** optional maximum-flow-temperature number and auto-adaptation switch.
- **Presence and mobile devices:** home presence selection and optional mobile-device trackers, using Home Assistant's `in_zones` interface.
- **Physical-device diagnostics:** device serial information, battery/connectivity state, temperature and calibration.

For an exhaustive public-facing entity inventory, see [ENTITIES.md](ENTITIES.md).

## 12. Configuration, persistence and compatibility

`config_flow.py` uses device authorisation, home selection and reauthentication. Per-home options govern scan intervals, automatic schedule checks, schedule interval and optional datasets. The integration persists authentication and quota observations in config-entry data, and schedule profiles in Home Assistant's storage helper.

Maintain these compatibility invariants when modifying the code:

- Keep `tado_x` as the domain and `custom_components/tado_x` as the package path.
- Preserve existing unique IDs, entity IDs where possible, config-entry associations and home/device hierarchy.
- Do not key cross-home state by room ID alone.
- Keep actions domain-global but resolve the correct home **at invocation time**.
- Preserve Home and Away settings together when saving/restoring profiles.
- Avoid unnecessary API calls, especially for many-room installations.
- Keep service schemas, `services.yaml`, `strings.json` and translations consistent.
- Avoid unsupported migration logic or changing the persistent store format casually.

The original and enhanced integrations cannot be installed simultaneously because both own the same Home Assistant domain.

## 13. Verification and maintenance checklist

Before accepting a code change:

1. Compare against the **latest complete repository source or release tag**, not a reconstructed subset.
2. Inspect affected modules and their dependencies, including action schemas, entities and translation keys.
3. Run Python syntax checks and parse JSON/YAML; check ZIP integrity and repository layout.
4. Test startup, unload/reload, reauthentication and optional-feature combinations in Home Assistant where relevant.
5. Test single-home and two-home installations, including overlapping room IDs.
6. Verify existing entity unique IDs and action compatibility.
7. For schedule changes, test Home/Away reads, complete-day validation, defaults, custom profiles, persistence, manual refresh, polling, and failed-write recovery.
8. For hot water, test Schedule/Off/Boost and both Away states.
9. Observe actual API call usage and error handling under the applicable quota.
10. Update `CHANGELOG.md`, relevant `docs/` guides, action descriptions and translations; distinguish static checks from live testing.

## 14. Documentation map

- [README](../README.md) — introduction, installation and user-facing feature overview
- [CONFIGURATION.md](CONFIGURATION.md) — installation, settings and troubleshooting
- [SCHEDULES.md](SCHEDULES.md) — schedules and profile workflows
- [ACTIONS.md](ACTIONS.md) — Home Assistant action reference
- [ENTITIES.md](ENTITIES.md) — device/entity/attribute reference
- [EXAMPLES.md](EXAMPLES.md) — practical YAML examples
- [CONTRIBUTING.md](../CONTRIBUTING.md) — contributor guidance
- [CHANGELOG.md](../CHANGELOG.md) — release history

## 15. Provenance and validation scope

This document describes the implementation packaged with Tado X Enhanced `1.2.0`, including the integration modules, manifest, action definitions and schedule-profile handling. Source inspection and static validation are distinct from live integration tests. For release-specific changes and test scope, consult [CHANGELOG.md](../CHANGELOG.md).

Tado X Enhanced is an independently maintained MIT-licensed derivative of Exabird's original integration. Retain the original and subsequent copyright notices in the repository's [LICENSE](../LICENSE).

### 15.1 Holiday Mode state management

`holiday_mode.py` maintains a home-scoped Holiday Mode snapshot, polls independently of room schedule comparison, schedules callbacks at holiday start and end boundaries, and notifies home-level entities. Targeted refreshes follow Holiday Mode actions and button presses. The Holiday Mode status is derived from the enabled flag and the configured date interval.

The `tado_x.set_holiday_mode` action accepts optional start and end dates, converts supported Home Assistant local date/time and ISO-8601 input to UTC, and requires each supplied time to be on a 30-minute boundary. Enabling or disabling without date changes uses a minimal request. Date changes use a targeted update and server read-back verification so that an ignored update is reported as an error rather than silently treated as successful. See [ACTIONS.md](ACTIONS.md) for action syntax.

### 15.2 Holiday Mode and domestic hot water

Tado may leave hot water switched Off after Holiday Mode is cancelled, including when Holiday Mode was controlled through the Tado app. The integration reports the Tado API state rather than automatically changing the hot-water schedule. The [README](../README.md) describes an optional Home Assistant automation for restoring Schedule after Holiday Mode ends.
