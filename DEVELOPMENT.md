# Tado X Enhanced — Development Status

**Repository:** https://github.com/rleatherb/ha-tado-x-enhanced  
**Integration domain:** `tado_x`  
**Latest published release:** `v1.1.1` (6 November 2026)  
**Development baseline:** `v1.1.1`; `main` and `develop` synchronized following release, as reported by the maintainer  
**Status:** Release complete; next development cycle open. No subsequent functional changes recorded.  
**Updated:** 6 November 2026

## Current development position

Version `v1.1.1` is the published baseline for further work. The DEV-002 Holiday Mode hotfix followed DEV-001's introduction of home-level Holiday Mode controls, status/date sensors, manual refresh, boundary handling, local date presentation and holiday hot-water state mapping. The hotfix restored local date/time selectors and corrected date-bearing requests by sending only writable settings, preserving an omitted boundary and verifying dates through a server read-back.

The maintainer confirmed that date-bearing Holiday Mode changes work against the live Tado API. This is not evidence of a complete `v1.1.1` regression run on both homes. The existing schedules, timers, historical data, API monitoring and multi-home behaviour are intended to remain unchanged; relevant live regression tests should be performed for future functional changes.

Holiday Mode cancellation can leave domestic hot water `OFF` rather than returning to Schedule, including when cancelled through the Tado app. This appears to be Tado-side behaviour, but its cause has not been conclusively established. The integration reports the API state and does not automatically restore Schedule. The README documents an optional Home Assistant automation to restore it.

Temporary DEV-002 diagnostic logging was removed. Toggle-only Holiday Mode changes retain a minimal `enabled` request; date-bearing changes use filtered writable fields and read-back verification. Holiday Mode polling cadence was not changed. A potential duplicate settings read remains an optional future API-quota review item, not an implemented optimisation.

## Next-cycle verification priorities

1. Establish the next change against the published `v1.1.1` tag and the latest complete development package.
2. Verify both configured homes, entity identities, device associations and existing automations when changes could affect them.
3. Regression-test schedule profiles, extended climate timer, hot-water selection, Holiday Mode, historical data, API monitoring and setup/unload as appropriate to the change.
4. Check translations, Home Assistant action selectors and labels after user-facing changes.
5. Measure or assess additional Tado API calls before introducing new polling or verification requests.

These are future development checks, **not** outstanding conditions for the already published `v1.1.1` release.

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

## DEV-003 — Authentication reliability (unreleased development build)

A consolidated implementation based on community PRs #5 (rotating refresh-token race), #6 (Home Assistant SSL context and authorisation-code logging) and #7 (transient refresh failures). Contributor attribution should be retained when the changes are committed. This is not yet an accepted or published release.

- `api.py`: per-client refresh lock covers explicit, expiry-triggered and HTTP-401-triggered refreshes; a 401 retries once using the current token, avoiding duplicate rotations. Refresh errors distinguish known rejected credentials from transient network/server conditions. The existing token persistence callback remains in place. Device authorisation uses Home Assistant's SSL context and no longer logs the user code.
- `__init__.py`: setup refreshes only when the access token is missing or close to expiry; initial coordinator update still checks connectivity. Transient refresh errors become `ConfigEntryNotReady` rather than reauthentication requests.
- No config-entry, entity-ID, unique-ID, integration-domain, schedule, hot-water, Holiday Mode or action-interface changes. Per-home API instances and credentials remain independent. Same-account multi-home refresh-token behaviour remains unverified.
- Logging enhancement: debug-only success entries identify `home_id`, refresh `reason` (`expiry`, `missing_token`, `http_401`, or `explicit`) and `expires_in`; token persistence logs identify `home_id`. No credentials or device codes are logged. The home ID is assigned before startup refresh.
- Maintainer confirmed live token refresh and persistence for both homes with the enhanced logging build on 2026-11-07: home_id=2243481 at 22:53:37 UTC and home_id=1985739 at 22:54:08 UTC, both reason=expiry and expires_in=599s. Normal operation was also reported. Live error-path recovery, revoked-token handling and same-account multi-home behaviour remain unverified.
- `tests/test_dev003.py`: standalone mocked tests; no Home Assistant or live Tado API exercised. Run `python tests/test_dev003.py` from the package root.

Before release: retain the successful two-home live refresh evidence; complete targeted Home Assistant regression checks as practical, including restart after token rotation and normal entities/actions. Mocked tests cover concurrent refresh and 401 recovery, but live revoked-token handling, transient failure recovery, reauthentication and same-account multi-home behaviour remain unverified. Review contributor PR disposition before merging. No version bump or release approval is implied.

Community contribution: DEV-003 draws on PR #5 (serialised refresh), PR #6 (SSL context and authorisation-code logging) and PR #7 (transient refresh failures), submitted by @cmatte. Acknowledge this work in the integration commit/PR description; the consolidated implementation contains additional changes and should not be described as a direct merge of those PRs.
