# Tado X Enhanced for Home Assistant

An independently maintained custom integration for controlling and monitoring **Tado X** systems in [Home Assistant](https://www.home-assistant.io/).

Tado X Enhanced builds on the original [Tado X integration by exabird](https://github.com/exabird/ha-tado-x) (version v1.8.11), adding multi-home support, Home and Away schedule management, reusable schedule profiles, domestic hot-water controls, richer room diagnostics and API quota forecasting.

> **Version:** 1.2.0. See [GitHub Releases](https://github.com/rleatherb/ha-tado-x-enhanced/releases) for available downloads. Some features depend on your Tado hardware, subscription and API responses. This is a cloud-based integration and is subject to Tado API limits. Code development and documentation assisted by AI.

**[Changelog](CHANGELOG.md)** · [Report an issue](https://github.com/rleatherb/ha-tado-x-enhanced/issues) · [Releases](https://github.com/rleatherb/ha-tado-x-enhanced/releases)

## Highlights

- **Multiple homes:** Configure more than one Tado home, with separate coordinators, home-scoped operations and profile storage. Rooms with the same numerical ID in different homes remain distinct.
- **Heating control:** Room thermostats, manual overrides, termination modes, open-window detection and home-wide heating quick actions. Ensures Home Assistant thermostat cards behave the same way as when temperature is changed on a Tado device.
- **Schedules:** Read and change Home schedules and Away settings; inspect next schedule changes, target temperatures and power states. Added `next_schedule_change`, `next_schedule_temperature`, and `next_schedule_power` sensors for each room.
- **Schedule profiles:** Save and restore **Normal**, **Alternative**, **Eco** and **Not in use** profiles per room, with separate home-wide defaults and factory fallbacks. As well as these four pre-defined schedule types, additional unlimited named profiles can also be added. A **Custom** state identifies schedules that do not match a saved profile.
- **Holiday mode:** Get and set Holiday mode (requires Tado Auto-Assist subscription)
- **Historic data:** Retrieve historic data for temperature, humidity and heating (requires Tado Auto-Assist subscription for days before today).
- **Hot water:** Where supported, view hot-water state, choose Schedule/Off/Boost and inspect boost or schedule-change timing.
- **Open window status:** Open window expiry and remaining time available via `open_window_detected`, `open_window_ends_at`, and `open_window_remaining_minutes `climate attributes.
- **API monitoring:** Track quota limit, remaining calls, current usage, rolling observed daily usage and theoretical daily usage. Learn the approximate reset time from server-reported quota observations rather than assuming a fixed clock time.
- **Additional data:** Heating running time, weather, air comfort, mobile presence and Energy IQ actions where supported and enabled.
- **Authentication reliability:** Serialised token renewal, improved recovery from temporary authentication-server failures, and per-home debug logging for successful refreshes.
- **Five languages:** English, German, French, Italian and Spanish.

## Installation through HACS

This repository is public and can be added to HACS as a custom repository. See [GitHub Releases](https://github.com/rleatherb/ha-tado-x-enhanced/releases) for the latest published version:

1. Install [HACS](https://www.hacs.xyz/) if it is not already installed.
2. In Home Assistant, open **HACS → Custom repositories**.
3. Add `https://github.com/rleatherb/ha-tado-x-enhanced` and select **Integration**.
4. Open the repository entry in HACS and select **Download**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**, search for **Tado X Enhanced**, and complete authentication and home selection.
7. Complete the **Configuration** settings as described below, to be consistent with your Auto-Assist subscription. Having this subscription is strongly recommended for optimum use, allowing a frequent Main update interval and allowing Schedule polling.

This is a **custom repository** installation; inclusion in the default HACS catalogue is not required. Exact HACS menu labels can vary by version.

### Replacing an existing Tado X installation

Tado X Enhanced uses the same Home Assistant integration domain, `tado_x`, as Exabird's original integration. **It is a replacement, not a second integration that can run alongside the original.** Preserving the domain is intended to retain existing configuration entries and entity identities, but migration from every older version has **not** been verified.

**Back up Home Assistant before switching.** Make a complete backup including configuration entries, `.storage` data and custom integrations. Record important entity IDs and the configured Tado homes, and ensure the backup can be restored.

Carry out the following HACS handover.

1. **Register the Enhanced repository.** In HACS, add `https://github.com/rleatherb/ha-tado-x-enhanced` as a custom **Integration** repository. Both repository entries may initially appear separately in HACS, although they use the same integration domain.
2. **Remove the original Exabird installation through HACS.** Open the original **Tado X** repository entry in HACS and select **Remove**. You will see a warning: *Integration is configured*. Select **IGNORE** to bypass this warning, then **REMOVE** on the subsequent confirmation. **Do not use NAVIGATE to delete the Home Assistant integration configuration, and do not remove the Tado X homes under Settings → Devices & services.** The HACS removal temporarily removes the old integration files; do not restart Home Assistant at this point.
3. **Download Tado X Enhanced.** Open its HACS repository entry and select **Download**. Confirm that the target directory is `/config/custom_components/tado_x` and that HACS reports **Pending restart**. Complete this download **before restarting Home Assistant**. If the download fails, do not restart until you have restored a working integration package or planned recovery from your backup.
4. **Restart Home Assistant once**, after the Enhanced files are in place.
5. **Verify the migration.** Check that the original Tado home entries load, existing climate and other entity IDs remain available, and no duplicate devices appear. Inspect Home Assistant logs. Verify any relevant hot-water and schedule controls before relying on them. For multiple homes, check both homes and room-specific routing.
6. **Confirm HACS ownership.** Ensure **Tado X Enhanced** is shown as installed in HACS and the original Exabird repository is no longer shown as installed.

**After migration:** All existing homes should be loaded, and all existing devices remain. The number of entities will be increased significantly as Enhanced entities become available. Check the configuration of your installed homes (see below) to ensure that the new schedule checking is consistent with your Auto-Assist subscription limits and you have enabled all the required features.

**Important:** Removing downloaded integration files through HACS is different from deleting a Home Assistant integration configuration entry, which can remove entities and integration-managed information. If replacement fails, restore your backup and report the problem with redacted logs.

## Detailed documentation

- [Configuration](docs/CONFIGURATION.md)
- [Schedules and schedule profiles](docs/SCHEDULES.md)
- [Actions reference](docs/ACTIONS.md)
- [Devices, entities and attributes](docs/ENTITIES.md)
- [Usage examples](docs/EXAMPLES.md)
- [Technical architecture](docs/ARCHITECTURE.md)

## Configuration

Each configured Tado home has its own options under **Settings → Devices & services → Tado X → Configure**.

| Setting | Purpose |
| :--- | :--- |
| Auto-Assist subscription | Sets subscription-related defaults and feature availability assumptions. |
| Main update interval | General integration polling, in seconds (configuration range: 30–3600). |
| Automatically check for schedule changes | Enable periodic Home/Away schedule comparisons. Defaults to on for Auto-Assist and off otherwise, unless explicitly set. |
| Schedule check interval | Independent schedule polling interval: 900–86400 seconds (15 minutes–24 hours); default 3600 seconds. |
| Supplementary polling multiplier | 1×, 2×, 5× or 10× main interval; higher values reduce supplementary API requests (default 5×). |
| Automatically check for Holiday Mode changes | Enable periodic Holiday Mode polling at the supplementary interval. |
| Weather | Enable weather data where available. |
| Mobile devices | Enable mobile presence/tracker data. |
| Air comfort | Enable air-comfort data. |
| Running times | Enable heating running-time data. |
| Flow temperature | Enable supported flow-temperature controls/data. |
| Hot water | Enable domestic hot-water functionality where supported. |

Polling settings can also be changed through `tado_x.set_polling_options`, without a restart. See [Configuration](docs/CONFIGURATION.md) for quota recommendations and the API usage sensors.

**API usage matters:** A complete automatic schedule check uses approximately **two API calls per room** (one Home schedule and one Away settings read). For 10 rooms, hourly checks would use approximately **480 requests per day** for this feature alone. Manual profile operations and the **Refresh Schedule** button remain available when automatic schedule checking is disabled.

### OpenTherm domestic hot water setpoint

Some Tado X installations with an OpenTherm-connected receiver (observed on the European TR04) expose a domestic hot water temperature setpoint without a separate DHW relay. When `programmer/domesticHotWater/state` returns both `setpoint` and `setpointConstraints`, the integration offers a **Hot Water Temperature** number entity with the API-provided limits. Setting it posts `{"setpoint": <temperature>}` to `programmer/domesticHotWater/manualControl` and refreshes the state.

When `roomsAndDevices.otherDevices` reports an `OPENTHERM` interface **and** the API exposes a DHW setpoint, relay-style **Boost Hot Water**, **Turn Off Hot Water**, **Resume Hot Water Schedule** and **Hot Water Mode** controls are disabled **by default for newly registered entities**. Existing entities and user choices are preserved. These actions may fail with `No RELAY DHW device in home` on installations without a DHW relay.

This is a conservative default, **not** a definitive hardware capability test: `thermInterfaceType: OPENTHERM` alone does not prove that relay actions are unavailable in every installation. Other OpenTherm mode APIs may exist, but have not been verified. The number setpoint is independent of these relay-style controls.

## Devices and entities

Available entities vary with hardware, account capabilities and configuration.

| Device type | Main entities and controls |
| :--- | :--- |
| **Tado X Home** | Home ID; presence sensors/select; API quota, calls, current usage, estimated daily usage and reset time; home-wide heating buttons; supported hot-water sensors, mode selector and buttons; flow-temperature controls. |
| **Tado X Room** | Climate thermostat; temperature, humidity, heating power and running time; next schedule change, temperature and power; open-window/heating/override status; termination settings; save/restore profile selectors; **Refresh Schedule** button. |
| **Physical Tado X device** | Battery, device temperature, temperature offset, connection state, low-battery status and child lock where supported. |
| **Weather / air comfort / mobile** | Optional weather, comfort and presence entities. |

### Room schedule profiles

The four named profiles are **Normal**, **Alternative**, **Eco** and **Not in use**. Each profile can store the room's full Home weekly schedule **and** Away configuration (including Away temperature and preheating where supported).

A room-specific saved profile takes precedence over the home-wide default when restored normally. To apply the home-wide default to a room explicitly, use `tado_x.restore_schedule_profile_default` in **Developer Tools → Actions**; to save the room's current schedule as the home-wide default, use `tado_x.save_schedule_profile_default`. The corresponding device-page default selectors were removed. Saving or resetting a default does **not** immediately change active room schedules.

The integration initially captures the current room schedule as **Normal** if that room profile is missing. The **Custom** indication is based on the latest comparison; when automatic checks are off, use **Refresh Schedule** to detect changes made outside Home Assistant. Additional profile names can be created separately for each home.

## Actions

The integration exposes **20 actions** under `tado_x` in **Developer Tools → Actions**:

| Category | Actions |
| :--- | :--- |
| Temperature and Energy IQ | `set_temperature_offset`, `add_meter_reading`, `set_eiq_tariff`, `set_climate_timer` |
| Home and Away schedules | `get_schedule`, `set_schedule`, `get_away_schedule`, `set_away_schedule` |
| Polling configuration | `set_polling_options` |
| History and holiday mode | `get_day_report`, `get_holiday_mode`, `set_holiday_mode` |
| Schedule profiles | `save_schedule_profile`, `restore_schedule_profile`, `list_schedule_profiles`, `create_schedule_profile`, `delete_schedule_profile`, `save_schedule_profile_default`, `restore_schedule_profile_default`, `reset_schedule_default` |

See the [complete actions reference](docs/ACTIONS.md) for parameters and home/room targeting.

Example — set a temperature for 60 minutes:

```yaml
action: tado_x.set_climate_timer
data:
  entity_id: climate.living_room
  temperature: 21
  termination_type: TIMER
  duration: 60
```

For `MANUAL` and `NEXT_TIME_BLOCK`, specify the desired temperature and omit `duration`. The `entity_id` above is an example and must match your installation.

When more than one Tado home is configured, home-level actions require selecting the appropriate **Tado X Home device**; room actions are routed through their room climate entity.

## Climate attributes and diagnostics

Room climate entities may expose `manual_control_active`, `manual_control_type`, `manual_control_remaining_minutes`, `heating_power`, `next_schedule_change`, `next_schedule_temperature`, `open_window_detected`, `open_window_ends_at` and `open_window_remaining_minutes`, where data is available. The next scheduled power state is available as a separate sensor. `hvac_action` is a standard Home Assistant climate property and depends on available heating-state data.

The Restore schedule profile selector also exposes match information such as `match_status`, `matching_profiles`, `last_applied_profile` and `saved_profiles`.

### API usage estimates

- **API current usage** reports the proportion of the daily quota consumed.
- **API reset time** is estimated from a substantial drop in server-reported calls used. It can remain `unknown` until a reset has been observed.
- **API estimated daily usage** projects the current API request rate from a rolling **60-minute** window, allowing polling changes to be assessed much sooner. It can exceed **100%**. It displays `unknown` until at least 10 minutes of valid observations have accumulated after startup, a quota reset or a quota-counter correction. A full hour gives the most representative estimate.

These calculations do not require additional API calls. They are estimates, not guarantees of Tado's future quota behaviour. Do not assume separate home sensors represent separate quota pools without verifying account-level reporting.

## Compatibility and limitations

- This is a **cloud-polling** integration; a working Tado account and internet connection are required.
- Some functionality requires compatible hardware, enabled options, or Tado Auto-Assist/API access.
- Tado's API is not controlled by this project and may change or impose request limits.
- Multiple homes are supported, but verify service targeting and quota reporting when configuring more than one home.
- The minimum supported Home Assistant release has **not yet been established by testing**. Do not infer compatibility solely from the manifest version.
- The original `1.0.0` release was validated on a separate Home Assistant test installation, including a HACS handover from the original Exabird integration. Version `1.1.0` passed regression testing, including Home Assistant 2026.11 climate compatibility checks. For `1.1.1`, the maintainer confirmed that the Holiday Mode date-update correction works against the live Tado API. For `1.1.2`, automatic token refresh and credential persistence were confirmed for both homes; live authentication failure recovery and a complete regression run have not been verified. For v1.2.0, the maintainer confirmed polling, options and action behaviour, API monitoring, and seven functional regression checks across the available homes. Flow Temperature was not available for live testing. Upgrade compatibility with every earlier installation and Home Assistant release has not been established.

## Releases and changes

See **[CHANGELOG.md](CHANGELOG.md)** and [CONTRIBUTING.md](CONTRIBUTING.md) for the initial feature set, compatibility notes and all future release changes. Versioning follows [Semantic Versioning](https://semver.org/).

## Issues and contributions

Please use [GitHub Issues](https://github.com/rleatherb/ha-tado-x-enhanced/issues) for reproducible bugs and feature requests. Include your Home Assistant version, integration version, relevant entity type and redacted debug logs. **Never post access tokens, refresh tokens or other account credentials.**

## Credits and licence

Tado X Enhanced is an **independently maintained derivative** of the original [ha-tado-x project by Exabird](https://github.com/exabird/ha-tado-x). The original integration and its contributors are acknowledged with thanks. This project is independently maintained and is not affiliated with or endorsed by Tado or the original maintainer.

This project is distributed under the **[MIT License](LICENSE)**. The licence file preserves the original copyright notice and identifies the subsequent enhancements:

- **Copyright (c) 2025 Exabird** — original integration.
- **Copyright (c) 2026 Robin Leatherbarrow** — subsequent modifications and enhancements.

The MIT licence permits use, modification and redistribution subject to retention of the required copyright and permission notices. See the complete [LICENSE](LICENSE) file for its terms and warranty disclaimer.

Project maintenance and GitHub code ownership: [@rleatherb](https://github.com/rleatherb).



### Holiday Mode

The Tado X Home device has Holiday Mode, Holiday Status, Holiday Start, Holiday End and Refresh Holiday Mode entities. An expired holiday switched on through Home Assistant is rescheduled to start immediately for seven days. Explicit dates in `tado_x.set_holiday_mode` remain unchanged. Holiday state refreshes independently at the configured schedule polling interval and at holiday boundaries.

### Holiday date display and hot-water states

The Home device now also provides **Holiday Start (Local)** and **Holiday End (Local)**, displaying absolute local dates and times. The original timestamp entities remain unchanged for automations. During active holidays, `HOLIDAY_MODE_OFF` is recognised as a hot-water state and shown as Off by the Hot Water Mode selector. Holiday changes refresh hot-water state promptly.

**Known Tado behaviour:** After cancelling Holiday Mode, Tado may leave domestic hot water Off instead of restoring Schedule, including when the holiday was controlled entirely in the Tado app. Tado X Enhanced reports the API state and does not automatically restore Schedule. If necessary, restore Schedule manually.

This appears to be a bug in the current Tado implementation that is found if you have water heating set to Scheduled, with Off when Away, and Holiday Mode is set while the status is Away. On ending Holiday Mode, the Hot Water status reverts to permanently Off rather than Scheduled.

The following automation example can be used to ensure that Hot Water Mode is always reset to Scheduled whenever Holiday Mode ends (replace `sensor.home_holiday_status` and `select.home_hot_water_mode` with the settings for your Tado home).

```yaml
alias: Restore hot water schedule mode when holiday mode ends
description: ''
triggers:
  - trigger: state
    entity_id:
      - sensor.home_holiday_status
    to:
      - ended
      - 'off'
    id: Holiday Status Ended
conditions: []
actions:
  - choose:
      - conditions:
          - condition: trigger
            id:
              - Holiday Status Ended
        sequence:
          - delay:
              hours: 0
              minutes: 1
              seconds: 0
              milliseconds: 0
          - action: select.select_option
            metadata: {}
            target:
              entity_id: select.home_hot_water_mode
            data:
              option: SCHEDULE
mode: queued
max: 10

```


### API usage projections

The existing **API estimated daily usage** sensor extrapolates observed consumption over the last 60 minutes (provisional after 10 minutes). For slow polling, this can miss infrequent requests or temporarily overstate their contribution. Its freshness tolerance follows the configured main polling interval. The new **API theoretical daily usage** sensor immediately projects the periodic request workload from current main/supplementary/schedule settings and room count, with a per-category calls/day breakdown in attributes. Neither sensor makes extra API calls. The theoretical model excludes unpredictable activity and is not a guaranteed upper bound.
