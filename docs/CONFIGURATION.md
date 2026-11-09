# Configuration

Each Tado home is configured as a separate Home Assistant integration entry. Use **Add integration** or **Add entry**, depending on the Home Assistant interface, and select the appropriate Tado home during setup.

Each configured Tado home has its own options under **Settings → Devices & services → Tado X → Configure**.

| Setting | Purpose | Version |
| :--- | :--- | :---: |
| Auto-Assist subscription | Identifies the subscription tier for feature availability; does not overwrite an existing polling interval. |  |
| Main update interval | General integration polling, in seconds (configuration range: 30–3600). |  |
| Automatically check for schedule changes | Enable periodic Home/Away schedule comparisons. Defaults to on for Auto-Assist and off otherwise, unless explicitly set. | 1.0.0 |
| Schedule checking interval | Independent schedule checking interval: 900–86400 seconds (15 minutes–24 hours); default 3600 seconds. | 1.2.0 |
| Automatically check for Holiday Mode changes | Independent checkbox; enabled by default, including on existing installations. | 1.2.0 |
| Supplementary polling multiplier | 1×, 2×, 5× or 10× the main interval for Weather, Air Comfort, Heating Running Times, Flow Temperature and Holiday Mode; **5× by default**. | 1.2.0 |
| Weather | Enable weather data where available. |  |
| Mobile devices | Enable mobile presence/tracker data. |  |
| Air comfort | Enable air-comfort data. |  |
| Running times | Enable heating running-time data. |  |
| Flow temperature | Enable supported flow-temperature controls/data. |  |
| Hot water | Enable domestic hot-water functionality where supported. | 1.0.0 |


### API usage

Each main coordinator update makes **3 mandatory API requests per home** (rooms, rooms/devices and home state). Enabled Mobile Devices and Hot Water each add one request per main update. Weather, Air Comfort, Heating Running Times, Flow Temperature and Holiday Mode are **supplementary features**: each enabled feature adds approximately one request every `main_interval × supplementary_multiplier` seconds. Choose 1× (normal), 2×, 5× or 10×; the default is 5×. The configuration form groups the five supplementary features beneath this setting. Last successful values are retained between refreshes, with same-day handling for Heating Running Times. Holiday Mode initial/manual/action/boundary refreshes and flow-temperature action-triggered refreshes remain available regardless of multiplier.

Schedule profile checking remains independent, with its own enable checkbox and 900–86400 second interval (default 3600 seconds). Holiday Mode has its own enable checkbox but **does not use the schedule interval**.

Theoretical scheduled daily requests per home, excluding startup, manual actions, authentication, retries and other API activity, are approximately:

`(86400 / main_interval_seconds) × (3 + enabled_main_optional_features + enabled_supplementary_features / multiplier) + (86400 / schedule_check_interval_seconds) × (2 × room_count if schedule checking enabled)`.

For example, at a 30-second main interval with all seven optional data sources enabled (two main-frequency and five supplementary, including Holiday Mode, plus the three core calls), a 5× multiplier and 20 rooms checked hourly, the theoretical rate is **(2880 × (3 + 2 + 5/5)) + (24 × 40) = 18,240 calls/day per home**. This is close to a 20,000-call daily quota, and manual actions and retries add usage. The existing API usage sensors reflect server-reported consumption, not this theoretical rate.

**API usage for schedules:** A complete automatic schedule check uses approximately **two API calls per room** (one Home schedule and one Away settings read). For 10 rooms, automatic hourly checks would use approximately **480 requests per day** for this feature alone. Automatic checks can therefore be disabled if required; updates per room can still be done manually if required by using the **Refresh Schedule** button that is enabled for each room separately.



## Recommended starting settings and API quota

Tado limits API requests per home. Current reported allowances depend on Auto-Assist: **100 requests/day without Auto-Assist** and **20,000 requests/day with Auto-Assist**. The following are recommended starting settings, not guarantees that the quota will be sufficient:

- **Without Auto-Assist:** Main polling every 3600 seconds; disable optional polling features and automatic schedule checking. Even the three core API requests per main update account for approximately 72 requests/day, leaving limited headroom for other activity.
- **With Auto-Assist:** Main polling every 30 seconds, supplementary polling at 5× and schedule checking every 3600 seconds; enable the features you need. Larger homes and additional activity may require less frequent polling.

The Tado home device includes sensors for the server-reported API allowance and actual usage, a rolling 60-minute daily usage projection based on recent requests, and a theoretical daily usage projection based on current polling settings. The theoretical projection responds immediately to configuration changes but is not a guaranteed maximum. Keep actual usage below 100% to reduce the risk of API updates being blocked until the allowance resets.

The Auto-Assist checkbox identifies the subscription tier; it does **not** overwrite a manually configured polling interval.

## Polling and quotas

The main coordinator interval, supplementary multiplier and independent schedule checking interval are configured **per home**. Main polling supports 30–3,600 seconds; schedule checking supports 900–86,400 seconds and defaults to 3,600 seconds. Automatic schedule checking defaults to enabled with Auto-Assist and disabled without it, unless explicitly configured. Increasing an interval reduces polling frequency.

Schedule checking requires approximately two API reads per room per check. For 10 rooms checked hourly, that is about 480 requests/day, **in addition to** normal polling and other operations. For accounts with multiple homes, do not assume separate per-home quotas: inspect the server-reported API quota sensors. Schedule profiles and the room **Refresh Schedule** button can still be used with automatic schedule checking disabled.

## Multiple homes and compatibility

Each home has its own coordinator, configuration options and schedule-profile storage. Home-level actions require a **Tado X Home device** target when more than one home is configured; room actions resolve the home from the climate entity. The integration uses domain `tado_x` and cannot coexist with another integration using the same domain. See [README.md](../README.md) for the replacement-installation precautions.

## Troubleshooting

If a feature is unavailable, confirm that the corresponding optional dataset is enabled and supported by your Tado equipment/account. Check Home Assistant logs for authentication, rate-limit and API errors. Before sharing diagnostics, redact tokens, account details, addresses and other personal information. A successful YAML configuration check alone does not verify Tado cloud functionality.

For installations upgrading from a release without a supplementary multiplier setting, the default is **5×**. An explicitly saved 1×, 2×, 5× or 10× value is preserved. At a 30-second main interval, 5× refreshes enabled supplementary datasets approximately every 150 seconds; core polling is unaffected. This default limits API quota pressure from Holiday Mode joining supplementary polling.

### Rolling API usage projection

The **API estimated daily usage** sensor projects the recent request rate over a rolling 60-minute window against the server-reported daily quota. A provisional estimate appears after at least 10 minutes of valid observations, becoming representative of the current settings after approximately 60 minutes. The history is in memory only, and resets after a Home Assistant restart, quota rollover or quota-counter correction. The sensor does not make extra API requests. The current usage and remaining quota sensors continue to show actual reported consumption.

### Theoretical API usage projection

The **API theoretical daily usage** sensor estimates periodic requests/day immediately from each home's applied polling settings. Its attributes show main, supplementary and schedule-checking contributions and the quota used in the calculation. It assumes three mandatory main requests per cycle, one per enabled mobile-device/hot-water dataset per main cycle, one per enabled supplementary dataset per supplementary cycle, and approximately two schedule reads per room per schedule check. Actual consumption may differ due to failures, retries, unsupported features, user actions, restarts or other requests. It is not a hard upper bound. The 60-minute observed-rate estimate remains separate and is deliberately more variable for slow polling. Its freshness threshold now follows the configured main interval. No additional API requests are made.

### Configure dialogue wording and behaviour

The supplementary polling multiplier sets the time between enabled supplementary updates relative to the main interval. **Higher multipliers mean less frequent updates and fewer API requests**; for example, 30-second main polling with 5× means supplementary polling every 150 seconds. The multiplier description in the Configure dialogue deliberately does not restate the default value.

Flow Temperature uses one API request per scheduled supplementary update when enabled. Flow Temperature controls may initiate an additional immediate refresh; this behaviour is documented here rather than in the concise option description. Schedule checking is independently enabled and uses its own interval; changing the Auto-Assist checkbox does not automatically enable schedule checking or overwrite user-selected intervals.

The Configure dialogue recommends keeping actual API consumption below 100% of the allowance. The quota, rolling observed projection and theoretical configured-workload projection are available on the Tado home device.
