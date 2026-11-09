# Changelog

All notable changes to **Tado X Enhanced** will be documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The project is independently maintained and is derived from the original Tado X integration for Home Assistant. Version **1.0.0** is the first release under this project's own versioning scheme; earlier development revisions are not listed individually.

**[Readme](README.md)** · [Report an issue](https://github.com/rleatherb/ha-tado-x-enhanced/issues) · [Releases](https://github.com/rleatherb/ha-tado-x-enhanced/releases)

## [1.2.0] - 2026-11-09

### Added

- Per-home main, supplementary and schedule polling controls, including independently enabled Holiday Mode polling and 1×/2×/5×/10× supplementary intervals (5× default).
- `tado_x.set_polling_options` action for validated, persistent, immediately applied polling changes with multi-home device targeting.
- Theoretical daily API usage sensor, showing a per-category projection from applied settings and room count.

### Changed

- Existing API estimated daily usage sensor now uses a rolling 60-minute observed-rate projection (provisional after ten minutes), with freshness tolerance based on main polling frequency.
- Configure dialogue reorganised and clarified, including subscription-tier quota recommendations and supplementary multiplier explanations.
- Supplementary feature polling retains previously retrieved values between updates; Holiday Mode manual, action and boundary refreshes bypass periodic throttling.

### Validation and limitations

- Maintainer reported seven of seven functional regression checks passed on live Home Assistant installations, including climate, timers, hot water, schedules, history, multi-home isolation and Holiday Mode boundary refresh. Polling settings, persistence and API estimates were also checked live.
- Flow Temperature was not available on the test homes. Standalone automated and static tests do not establish compatibility with every Tado configuration or Home Assistant version. Theoretical API usage is a planning estimate, not a guaranteed upper bound.

## [1.1.2](https://github.com/rleatherb/ha-tado-x-enhanced/releases/tag/v1.1.2) - 2026-11-08

### Changed

- Serialise refresh-token rotation within each Tado home API client, including expiry and HTTP 401 recovery.
- Treat temporary token-server/network failures as recoverable rather than immediately requiring reauthentication.
- Avoid unnecessary refresh when a stored access token remains valid at setup.
- Use Home Assistant's shared SSL context for device authorisation and stop logging the device user code.
- Add debug-only home ID, refresh reason and token lifetime to successful refresh logs, plus home ID to token-persistence logs; never log credentials.

### Validation

- Standalone mocked tests and static validation passed. The maintainer confirmed live token refresh, token persistence and home-specific debug logging for both homes on 2026-11-07. Live authentication failure recovery and a complete Home Assistant regression run have not been verified.

### Contributors

- Incorporates and extends authentication improvements proposed by @cmatte in PRs #5, #6 and #7; consolidated in PR #9.

## [1.1.1](https://github.com/rleatherb/ha-tado-x-enhanced/releases/tag/v1.1.1) - 2026-11-06

### Fixed

- Restore local date/time selectors for `set_holiday_mode` while retaining ISO-8601 YAML support and explicitly document the required 30-minute time boundaries.
- Submit only writable Holiday Mode fields when updating dates instead of echoing the full GET response, and preserve an omitted start/end boundary.
- Verify date updates by reading back the Tado settings; raise a Home Assistant error if Tado does not retain the requested dates or changes room/hot-water settings.

### Validation

- Maintainer confirmed that date-bearing Holiday Mode changes now work against the live Tado API. Full regression testing on both homes has not been reported; package checks are static only.

## [1.1.0](https://github.com/rleatherb/ha-tado-x-enhanced/releases/tag/v1.1.0) - 2026-11-06

### Added

- Home-scoped Holiday Mode controls: switch, status, start/end sensors, local-date display, and manual refresh button.
- Independent holiday status refresh at the configured schedule polling interval and holiday start/end boundaries.
- Support for scheduling a new seven-day holiday when enabling an expired holiday period through Home Assistant; explicitly supplied dates are respected.

### Changed

- Holiday Mode enable/disable operations without date changes use a minimal `enabled` request; date updates preserve the existing holiday settings.
- Domestic hot-water state mapping recognises `HOLIDAY_MODE_OFF` and `HOLIDAY_MODE_ON` while preserving existing Schedule, Off, Boost, and Away handling.
- Removed temporary Holiday Mode and hot-water investigation diagnostics without adding extra polling or automatic hot-water writes.

### Fixed

- Updated climate entity interfaces for Home Assistant 2026.11 (`native_current_temperature`, `native_target_temperature`, and `_attr_native_temperature_unit`) to eliminate deprecation warnings without changing entity identities or temperature control behaviour.

### Known limitation

- Tado may leave domestic hot water `OFF` rather than restoring Schedule when Holiday Mode is cancelled, even if cancellation is performed entirely in the Tado app. The integration reports the state returned by Tado and does not automatically restore Schedule. Users may restore Schedule manually or use their own Home Assistant automation.

### Validation

- RC1 functionality was tested by the maintainer in Home Assistant across both configured homes, including schedules, profiles, climate timers, hot water, Holiday Mode, historical data, API monitoring, and climate compatibility. The version-only release package requires final installation verification.

## [1.0.0](https://github.com/rleatherb/ha-tado-x-enhanced/releases/tag/v1.0.0) - Initial Release

This integration is a development of the original [Tado X integration by exabird](https://github.com/exabird/ha-tado-x) (version 1.8.11). Changes from this are as below:

### Added

- Extended support for configuring multiple Tado homes in one Home Assistant installation, with home-scoped entities, operations, and schedule data.

- Home and Away schedule management through Home Assistant actions, including retrieving, updating, and refreshing room schedules.

  - This feature is an enhanced version of the implementation specified in the following pull request: [Feat/schedule and historic data by ilyesAj · Pull Request #90 · exabird/ha-tado-x](https://github.com/exabird/ha-tado-x/pull/90). Differences include implementing full multi-room compatibility, adding Away schedule information.

- Room-specific heating schedule profiles named **Normal**, **Alternative**, **Eco**, and **Not in use**, including saving, restoring, and detecting schedules that differ from a saved profile (displayed as **Custom** when no match is stored). The heating schedules include both the Home and Away settings, including the preheating configuration supported by the Tado API.

  - [Full  description of how heating schedule profiles are used.](docs/SCHEDULES.md)

  - On start-up, if a room has no saved **Normal** profile, the current heating schedule defined by the Tado app is automatically saved for future use. This means that the current heating schedule can easily be restored without needing to save this explicitly. This will, in general, only happen the first time that this integration is used.

  - Per-home default schedule profiles for each of these four named schedules. Selecting one of these for a room that has no specific version stored will use the default. The defaults for each home can also be set, allowing rooms access to customised but generic schedules when selecting one of these.

  - Home Assistant controls added to refresh schedules and manage schedule profiles.

- Added hot-water state handling, including Away modes, boost status, remaining boost time, and next scheduled change where available.

  - This feature is an enhanced version specified in the following pull request: [DHW Control by donalfenwick · Pull Request #53 · exabird/ha-tado-x](https://github.com/exabird/ha-tado-x/pull/53)

- Added retrieval of historic heating data from Tado

  - This feature is inspired by the implementation specified in the following pull request: [Feat/schedule and historic data by ilyesAj · Pull Request #90 · exabird/ha-tado-x](https://github.com/exabird/ha-tado-x/pull/90).

- Additional room information added, including upcoming schedule changes and temperatures, manual-control timing, and open-window expiry and remaining time where available.

- Additional API quota monitoring, including server-reported quota limits and remaining calls, current usage percentage, observed reset-time detection, and estimated daily usage percentage.

- Enhanced temperature setting

  - Changes to temperature via Home Assistant thermostat cards now work the same way as if the change is made on a Tado device, using the per-room settings shown in the Tado app to determine whether the temperature change is for a set time period, until the next schedule change, or lasts indefinitely.

  - The per-room settings for how manual control of temperature should be interpreted (indefinite, until next schedule change, for a defined period of time) are now available as a per-room Termination Type select entity and Timer Duration number entity.

- Support to read and set holiday mode

  - This feature is inspired by the implementation specified in the following pull request: [Feat/schedule and historic data by ilyesAj · Pull Request #90 · exabird/ha-tado-x](https://github.com/exabird/ha-tado-x/pull/90).

- Added display of serial number information for all Tado X devices

- Translations for English, German, French, Italian, and Spanish.

  - Please note that the non-English translations are machine coded.

### Changed

- Extended the original integration's controls, sensors, and service handling while retaining the Home Assistant integration domain `tado_x`.
- Improved multi-home action routing, including home-device selection for actions that need an explicit home target.
- Improved `set_climate_timer` implementation that includes  **TIMER**, **MANUAL**, and **NEXT_TIME_BLOCK** termination types.
  - This feature is inspired by the implementation specified in the following pull request: [Feature: Termination type configuration by xiic · Pull Request #54 · exabird/ha-tado-x](https://github.com/exabird/ha-tado-x/pull/54). It is enhanced to support multi-home installations
- Added configurable automatic schedule-change checks and a separate schedule polling interval (15 minutes to 24 hours; default one hour). Automatic checking defaults to enabled for Auto-Assist configurations and disabled otherwise, unless explicitly configured.
- Renamed the displayed **API usage** sensor to **API current usage** while retaining its existing entity identity.
- Replaced the fixed API reset-time assumption with an observed, account-response-based estimate. The reset-time and projected-usage sensors can remain `unknown` until sufficient observations are available.
- Updated the integration's translated service descriptions, labels, and options.

### Fixed

- Service registration and routing when more than one Tado home is configured. Routines that were incompatible with multi-home setups corrected (`set_climate_timer`, `set_temperature_offset`, `add_meter_reading`, `set_eiq_tariff`)
- Error messages warning about certain depreciated calls that would not be supported in future Home Assistant releases.

### Removed

- The previous fixed daily API reset-time assumption.

### Compatibility notes

- A HACS migration from Exabird's original integration to Enhanced was successfully tested in October 2026 on a two-home Home Assistant installation: 105 existing devices were retained, checked entity IDs were preserved, and the integration loaded without reported startup errors or warnings. The documented handover avoids deleting existing Home Assistant configuration entries. This is not a guarantee for every earlier version.

- The Home Assistant integration domain remains `tado_x`. This project **replaces** other installations using the same domain; it cannot run alongside the original integration in one Home Assistant instance.

- Back up Home Assistant before replacing an existing installation. Verify both home entries, entities, and stored schedule profiles after migration.

- Some functionality depends on the connected Tado devices, the account's subscription, and API responses. Cloud API quotas apply.

- API reset-time detection is observational rather than an exact server-announced reset timestamp. Estimated daily usage may exceed 100% and may initially be unavailable.

