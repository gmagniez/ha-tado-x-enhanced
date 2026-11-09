> **Release preparation (9 November 2026):** DEV-004 is the functional baseline for the proposed v1.2.0 release candidate. Historical notes below describe interim development decisions and are not necessarily the final defaults. Latest published version remains v1.1.2 until release approval.

# Tado X Enhanced — Development Status

**Repository:** https://github.com/rleatherb/ha-tado-x-enhanced  
**Integration domain:** `tado_x`  
**Current release:** `v1.1.2` (8 November 2026)  
**DEV-003 integration:** PR #9, commit `1ad377480c674e718f413d29bdc6416d63ae7f78`  
**Status:** DEV-003 incorporated in v1.1.2; future work is tracked against the current accepted source.  
**Updated:** 8 November 2026

## Current development position

Version `v1.1.2` includes DEV-003 authentication reliability improvements alongside the previously released Holiday Mode functionality. The DEV-002 Holiday Mode hotfix followed DEV-001's introduction of home-level Holiday Mode controls, status/date sensors, manual refresh, boundary handling, local date presentation and holiday hot-water state mapping. The hotfix restored local date/time selectors and corrected date-bearing requests by sending only writable settings, preserving an omitted boundary and verifying dates through a server read-back.

The maintainer confirmed that date-bearing Holiday Mode changes work against the live Tado API. This is not evidence of a complete `v1.1.1` regression run on both homes. The existing schedules, timers, historical data, API monitoring and multi-home behaviour are intended to remain unchanged; relevant live regression tests should be performed for future functional changes.

Holiday Mode cancellation can leave domestic hot water `OFF` rather than returning to Schedule, including when cancelled through the Tado app. This appears to be Tado-side behaviour, but its cause has not been conclusively established. The integration reports the API state and does not automatically restore Schedule. The README documents an optional Home Assistant automation to restore it.

Temporary DEV-002 diagnostic logging was removed. Toggle-only Holiday Mode changes retain a minimal `enabled` request; date-bearing changes use filtered writable fields and read-back verification. Holiday Mode polling cadence was not changed. A potential duplicate settings read remains an optional future API-quota review item, not an implemented optimisation.

## Next-cycle verification priorities

1. Establish future changes against the latest accepted `develop` baseline and complete source package.
2. Verify both configured homes, entity identities, device associations and existing automations when changes could affect them.
3. Regression-test schedule profiles, extended climate timer, hot-water selection, Holiday Mode, historical data, API monitoring and setup/unload as appropriate to the change.
4. Check translations, Home Assistant action selectors and labels after user-facing changes.
5. Measure or assess additional Tado API calls before introducing new polling or verification requests.

These are ongoing development verification priorities, not claims that all scenarios were tested for `v1.1.2`.

## Development rules

1. Preserve the integration domain `tado_x`, existing config entries, entity identities, action interfaces and supported behaviour unless a change is explicitly agreed.
2. Keep all state and operations scoped to the correct Tado home, including where room IDs overlap.
3. Preserve schedule profiles, Home/Away settings, climate timers, hot water, historical data and API monitoring.
4. Avoid unnecessary Tado API calls; consider both main and schedule polling and account quotas.
5. Discuss architectural implications before implementation. Make minimal, focused changes.
6. Update `services.yaml`, `strings.json`, relevant `translations/*.json`, documentation and `CHANGELOG.md` when behaviour changes.
7. Validate Python syntax, JSON/YAML parsing, package layout, ZIP integrity and internal consistency. Record live Home Assistant/Tado API tests separately; static validation is not runtime verification.
8. Do not bump the version or publish a release without explicit approval.

## Working procedure

1. Start from the latest complete integration source and check its relationship to the `develop` branch.
2. Investigate an issue, agree the design and record decisions in this file.
3. Implement minimal changes and produce complete replacement files or an updated complete development ZIP.
4. Perform and report static validation, then install and test in Home Assistant as appropriate.
5. Record test results, unresolved problems and any follow-up corrections.
6. Commit accepted changes to `develop`, with descriptive commit messages.
7. Replace the Project's development ZIP and update this file and relevant individual documentation Sources to match the accepted baseline.
8. When release scope and testing are agreed, prepare release notes, agree a semantic version, merge to `main`, tag and publish. Do not do this automatically.

## Previous investigations

DEV-001 introduced Holiday Mode entities and state management in `v1.1.0`; DEV-002 corrected date updates in `v1.1.1`. The Stage C–G diagnostic builds and associated Home Assistant logs are historical evidence rather than release-facing changelog entries. The `CHANGELOG.md` records published changes and their stated validation scope.

## DEV-003 — Authentication reliability (v1.1.2)

A consolidated implementation based on community PRs #5 (rotating refresh-token race), #6 (Home Assistant SSL context and authorisation-code logging) and #7 (transient refresh failures). Contributions by @cmatte are acknowledged in PR #9 and the v1.1.2 changelog. DEV-003 was incorporated into v1.1.2 following PR #9.

- `api.py`: per-client refresh lock covers explicit, expiry-triggered and HTTP-401-triggered refreshes; a 401 retries once using the current token, avoiding duplicate rotations. Refresh errors distinguish known rejected credentials from transient network/server conditions. The existing token persistence callback remains in place. Device authorisation uses Home Assistant's SSL context and no longer logs the user code.
- `__init__.py`: setup refreshes only when the access token is missing or close to expiry; initial coordinator update still checks connectivity. Transient refresh errors become `ConfigEntryNotReady` rather than reauthentication requests.
- No config-entry, entity-ID, unique-ID, integration-domain, schedule, hot-water, Holiday Mode or action-interface changes. Per-home API instances and credentials remain independent. Same-account multi-home refresh-token behaviour remains unverified.
- Logging enhancement: debug-only success entries identify `home_id`, refresh `reason` (`expiry`, `missing_token`, `http_401`, or `explicit`) and `expires_in`; token persistence logs identify `home_id`. No credentials or device codes are logged. The home ID is assigned before startup refresh.
- Maintainer confirmed live token refresh and persistence for both homes with the enhanced logging build on 2026-11-07: home_id=2243481 at 22:53:37 UTC and home_id=1985739 at 22:54:08 UTC, both reason=expiry and expires_in=599s. Normal operation was also reported. Live error-path recovery, revoked-token handling and same-account multi-home behaviour remain unverified.
- `tests/test_dev003.py`: standalone mocked tests; no Home Assistant or live Tado API exercised. Run `python tests/test_dev003.py` from the package root.

Validation scope: standalone mocked tests covered concurrent refresh and HTTP 401 recovery. The maintainer confirmed routine live refresh and persistence for both homes. Live revoked-token handling, transient failure recovery, reauthentication, and same-account multi-home behaviour were not verified. These are known limits of the evidence, not claims of successful live testing.

Community contribution: DEV-003 draws on PR #5 (serialised refresh), PR #6 (SSL context and authorisation-code logging) and PR #7 (transient refresh failures), submitted by @cmatte. This work is acknowledged in PR #9 and the changelog; the consolidated implementation contains additional changes and should not be described as a direct merge of those PRs.

## v1.1.2 release record

Version 1.1.2 contains DEV-003 authentication reliability improvements. The release retains the existing integration domain, configuration-entry model, entities, actions, schedule profiles, climate timers, hot-water controls, Holiday Mode, historical data and API monitoring.

Validation evidence includes static checks, standalone mocked authentication tests and the maintainer's successful live refresh/persistence observations for both independently authenticated homes. A complete Home Assistant regression run and live authentication-failure injection were not reported. Future maintenance should verify those scenarios when practical without exposing credentials or generating unnecessary API traffic.

## DEV-004 — API polling and configuration (unreleased development build)

- DEV-004.1: Schedule and Holiday Mode polling share the existing check interval, with independent enable/disable checkboxes. Holiday polling defaults to enabled for existing entries and supports live interval reconfiguration. Initial read, manual refresh, boundary events and action-triggered refresh are preserved.
- DEV-004.2: Correct the coordinator per-update API accounting to include optional flow-temperature requests.
- DEV-004.3: Explain three mandatory main-update requests, per-feature costs and theoretical scheduled daily usage; distinguish these from server-reported API usage. Detailed investigation of the historical predicted/observed discrepancy is deferred.
- DEV-004.4: Optional reduced supplementary polling for weather, air comfort and running times, approximately every five main intervals. Off by default. Retain cached values between updates; discard running-time values from prior dates. Debug-only coordinator logs mark each actual supplementary API request (weather, air comfort, running times) with its home ID for live polling-cadence verification, without adding API calls.

No release version change, GitHub commit or live Home Assistant/Tado API testing is implied by this development record.

### DEV-004 Check 3 — polling diagnostics (unreleased)

- Debug-only schedule and Holiday Mode polling configuration messages show enabled state, interval and home ID, including on live options changes.
- Separate scheduled callbacks log `Schedule polling started` and `Holiday Mode polling started` only for periodic checks. Initial/manual schedule comparisons, Holiday Mode manual refreshes and Holiday Mode boundary-triggered refreshes do not emit these periodic markers.
- No additional API requests or entity/configuration interface changes. These markers report the start of a check, not successful API completion.
- Live verification of all four checkbox combinations remains pending.

### DEV-004 consolidated design update (unreleased)

- The supplementary reduction checkbox is replaced with a per-home selector of 1×, 2×, 5× or 10× (default 1×). No migration code is introduced for unpublished DEV-004 builds.
- Supplementary features: Weather, Air Comfort, Heating Running Times, Flow Temperature and Holiday Mode. Mobile Devices and Hot Water remain on the main cadence; schedule checking remains independent. Holiday Mode no longer has a periodic timer separate from the coordinator.
- Flow-temperature control actions invalidate the cached dataset before requesting a coordinator refresh. Holiday Mode initial/manual/boundary refreshes remain independent of periodic checks.
- DEV-004.5: `tado_x.set_polling_options` action, using the standard optional Home device selector, with partial updates, shared live options logic, persistence and validation.
- Earlier Check 3 Holiday Mode cadence results apply to the superseded shared-interval design and must be repeated for the new coordinator-driven polling.
- No actual Home Assistant runtime testing of this consolidated design is claimed.

### DEV-004 options UI correction (unpublished)

- Main polling, Supplementary polling and Schedule checking are now native Home Assistant sections on one options page.
- Supplementary multiplier is an explicit 1×/2×/5×/10× dropdown with 1× preselected for entries without a stored multiplier; existing selected values are retained.
- Section form submissions are flattened before applying the existing shared polling configuration logic; stored entry keys and action parameters remain unchanged. No migration code is included.
- Home Assistant frontend rendering and live persistence require user verification; static validation does not constitute a live HA test.

- DEV-004 action UI correction: `set_polling_options` now shares the existing home-device resolution convention, requiring a Tado X Home device only for multi-home installations; the unpublished numeric `home_id` argument was removed.

### DEV-004 Check 7 diagnostic logging (unpublished)

Added source-labelled debug logs around Holiday Mode API reads (initial, periodic, button, action and boundary), including success and failure. The manual refresh button continues to bypass the supplementary polling cadence. No polling frequency, action interface or API request count is intentionally changed. This is static validation only; repeat Check 7A in Home Assistant.

### DEV-004 default supplementary multiplier decision (unpublished)

- Adopt **5×** as the supplementary polling default for new installations and upgrades from published releases without this option. At 30-second main polling, supplementary datasets are normally checked approximately every 150 seconds.
- Preserve an explicitly stored multiplier, including 1×. No migration is required: absent values resolve to 5× in runtime and options, and the options form saves 5× when submitted.
- Keep earlier DEV-004 notes describing the original 1× development default as historical context; the final intended default is now 5×.
- This change does not affect the main polling interval, schedule checking interval, or immediate Holiday Mode reads. Home Assistant live testing of the new default remains pending.

### DEV-004 Check 8C and regression review (unpublished)

- Maintainer confirmed in Home Assistant that the 5× default is described in options and that existing explicit multipliers (1× for home 2243481 and 5× for home 1985739) were preserved after installing the default-5× build and restarting.
- API monitoring source review: current usage uses the server-reported quota/remaining headers when available; estimated daily usage extrapolates observed consumption since the quota reset to a 24-hour rate. Neither sensor directly computes a forecast from the configured supplementary multiplier.
- Corrected the source-level `tests/test_dev004.py` translation assertion to inspect the new three-section options schema. This fixes an obsolete test assumption, not a runtime issue. Standalone DEV-003, DEV-004, DEV-004.5 and default-5× checks pass. No new Home Assistant test is implied.

### DEV-004 — Rolling API usage estimate (unpublished)

- Replaced since-quota-reset daily extrapolation with a rolling 60-minute projection, based on existing API rate-limit response headers. No extra requests.
- A minimum 10-minute observation period provides a provisional estimate; full-window stabilization takes 60 minutes. History is per API client/home, bounded, in memory only, and cleared on quota changes or counter decreases.
- Existing API estimated daily usage sensor identity retained; current usage and remaining quota sensors unchanged. Live HA testing pending.

### DEV-004 — complementary theoretical API usage projection (unpublished)

Added the **API theoretical daily usage** sensor, preserving existing API sensor identities. The new home-scoped diagnostic projects the current periodic API workload immediately from the applied coordinator settings, supplementary multiplier, enabled features, independent schedule interval and discovered room count. Attributes separate main, supplementary and schedule contributions. The existing 60-minute observed estimate is unchanged except that its freshness tolerance now follows slower main polling. Live option changes notify sensors without issuing a Tado API refresh. No migration or new API requests. Requires Home Assistant verification; theoretical model excludes manual actions, retries, startup and API-specific variation.

### DEV-004 — Configuration wording refinement (9 November 2026)

Updated the Configure dialogue introduction to recommend quota-conscious starting settings for both subscription tiers, clarified that Auto-Assist does not automatically change a configured polling interval, standardised “API request” terminology, and shortened Weather, Air Comfort and Heating Running Times descriptions. Updated all five shipped translations and `docs/CONFIGURATION.md`. No polling logic or entity identities changed.

### DEV-004 — Final Configure dialogue wording (9 November 2026)

- Corrected quota warning Markdown so the full phrase “Keep actual usage below 100%” is bold. Home Assistant frontend rendering still requires visual verification.
- Clarified that larger supplementary multipliers reduce polling frequency and API requests; removed the multiplier default from the Configure description without changing the actual 5× default.
- Simplified Flow Temperature description and removed upgrade/default wording from schedule checking description.
- Aligned `strings.json` and the five shipped translation files with the agreed options text. No functional code, entity identities, polling behaviour or API request counts changed.
