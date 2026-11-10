# Devices, Entities and Attributes

### Supported Devices

The device-model list below is illustrative, not a guarantee that every feature is available on every model. Some controls depend on the device and Tado API response.

| Model | Device |
| :--- | :--- |
| VA04 | Radiator Valve X |
| SU04 | Temperature Sensor X |
| TR04 | Wireless Receiver X |
| RU04 | Wired Smart Thermostat X |
| IB02 | Bridge X |

Available entities vary with hardware, account capabilities and configuration.

## Tado X Home

| Controls | Type | Description | Version |
| :--- | :--- | :--- | :---: |
| Boost All | Button | Apply a heating boost to all rooms for 30 minutes |  |
| Boost Hot Water | Button | Apply a heating boost to the hot water for 1 hour | 1.0.0 |
| Hot Water Mode | Selector | Off / Schedule / Boost | 1.0.0 |
| Presence Mode | Selector | Home / Away / Away (Geofencing) |  |
| Resume Hot Water Schedule | Button | Resume hot water schedule | 1.0.0 |
| Resume Schedules | Button | Resume heating schedules |  |
| Turn Off All | Button | Turn off heating to all rooms |  |
| Turn Off Hot Water | Button | Turn off hot water heating | 1.0.0 |


| Sensors | Description | Version |
| :--- | :--- | :---: |
| API calls today | The number of API calls made in the current 24-hour period. With an auto-assist subscription up to 20,000 calls can be made; without that only 100 calls are allowed. |  |
| API current usage | Shows the percentage of the current daily allowance that has been used. |  |
| API estimated daily usage | Estimates how the current usage rate will impact the daily allowance. Useful when configuring polling frequency and can exceed **100%**. It uses a rolling 60-minute window of server-reported quota observations (minimum 10 minutes before a provisional estimate is available). After restart, quota reset or quota-counter correction, it temporarily displays `Unknown` while collecting observations. | 1.0.0 |
| API theoretical daily usage | Immediate percentage projection of periodic API calls using the current main interval, supplementary multiplier, enabled features, independent schedule checking and room count. Attributes break down expected calls/day by category. Does not include unpredictable manual actions, retries or startup requests; not a guaranteed upper bound. | 1.2.0 |
| API quota limit | Depends on whether an auto-assist subscription is present. |  |
| API quota remaining | The number of API calls that remain within the daily allowance. |  |
| API reset time | The daily API allowance is reset each day. The time that this happens varies between different users. This sensor monitors the API calls remaining to determine when the reset time will be. Note that this sensor will read 'Unknown' for up to 24 hours after first being installed, while the integration is determining when the reset time is. | 1.0.0 |
| Hot water boost ends | If water heating is boosted, this sensor records when the boost period will end. It is Unknown if water heating is not boosted. | 1.0.0 |
| Hot water next schedule change | Records the time for the next scheduled water heating change. Available when Tado provides a next-change timestamp in `SCHEDULE_ON` or `SCHEDULE_OFF` state; otherwise Unknown (including Away modes, explicitly Off, or no forthcoming change) | 1.0.0 |
| Hot Water State | Records the status for hot water heating. This can be `OFF` / `AWAY_OFF` / `AWAY_ON` / `SCHEDULE_ON` / `SCHEDULE_OFF` / `BOOST`. Explicitly switching hot water off can produce `OFF` even while the home is Away; `AWAY_OFF` is a distinct API state. The Hot Water Mode selector maps `OFF` to Off and the Away schedule states to Schedule | 1.0.0 |
| Outdoor Temperature | The outdoor temperature as returned by Tado for your location |  |
| Solar Intensity | A percentage as returned by Tado for your location |  |
| Weather State | The weather description as returned by Tado for your location. Depends on weather being selected in the home configuration. |  |


#### API usage estimates

The 60-minute rolling estimate is based on observed consumption and can under- or overestimate when polling is infrequent; its freshness allowance follows the configured main polling interval. The theoretical estimate is immediate and based on periodic workload assumptions. Neither calculation requires additional API calls; neither is a guaranteed upper bound.

| Diagnostic | Description | Version |
| :--- | :--- | :---: |
| Tado Home ID | The internal Tado identifier for this home. | 1.0.0 |


## Tado X Room

| Controls | Type | Description | Version |
| :--- | :--- | :--- | :--- |
| ROOMNAME | Climate | Climate device associated with the room. Allows temperature control, HVAC modes (Heat/Off/Auto), Pre-set modes (schedule/Home/Away/auto) |  |
| Open Window | Switch | On if an open window is detected (only available with an auto-assist subscription). Can be set to Off to cancel the open window state if required. |  |


| Sensors | Type | Description | Version |
| :--- | :--- | :--- | :---: |
| Comfort Level | Sensor (text) | As returned by Tado |  |
| Heating | Binary sensor | Normal or Hot (when calling for heat) |  |
| Heating Power | Sensor (percentage) | The level of heat required, from 0% to 100% |  |
| Heating Time Today | Sensor (hours) | The number of hours today when calling for heat |  |
| Humidity | Sensor (percentage) | The humidity of the room |  |
| Humidity Level | Sensor (text) | As returned by Tado |  |
| Manual Control | Binary sensor | Off if the temperature is being set using the current schedule. On if the temperature is set to a custom value. |  |
| Next Schedule Change | Sensor (timestamp) | Date and time when the next schedule will start | 1.0.0 |
| Next Schedule Power | Sensor (text) | Scheduled `ON` or `OFF` state at the next change, when available | 1.0.0 |
| Next Schedule Temperature | Sensor (temperature) | Target temperature at the next scheduled change, when available | 1.0.0 |
| Temperature | Sensor | The current room temperature |  |
| Window Open | Binary sensor | On if an open window is detected (only available with an auto-assist subscription) |  |


| Configuration | Type | Description | Version |
| :--- | :--- | :--- | :---: |
| Refresh Schedule | Button | Click to refresh the heating schedule information. Schedules are refreshed periodically, but if the heating timing is altered from the Tado app, it is possible for the Home Assistant settings to be out of sync. Click this button to update the settings. | 1.0.0 |
| Restore schedule profile | Selector | Loads a saved heating schedule for the room. See Heating Schedules for a full description. | 1.0.0 |
| Save schedule profile | Selector | Saves the current room's heating schedule to one of the named locations. See Heating Schedules for a full description | 1.0.0 |
| Termination Type | Selector | For each room, the Tado app allows setting of how manual device control will alter the temperature. Allowed settings: `TIMER` - the new temperature lasts for Timer Duration; `MANUAL` - the new temperature is set indefinitely, until you resume schedule; `NEXT_TIME_BLOCK` - the new temperature is set until the next scheduled change | 1.0.0 |
| Timer Duration | Number | This sets the length of time associated with Termination Type of Timer. | 1.0.0 |

The Restore schedule profile selector also exposes match information as attributes:

| Restore schedule profile attributes | Values | Description | Version |
| :--- | :--- | :--- | :--- |
| `match_status` | Matched / Custom / Unknown | Whether the live Home/Away schedule matches a known profile, differs from all known profiles, or could not be determined | 1.0.0 |
| `matching_profiles` | List of names | All effective profiles matching the most recently read live Home/Away schedule | 1.0.0 |
| `last_applied_profile` | Name or null | Profile most recently applied through the integration | 1.0.0 |
| `saved_profiles` | List of names | Profiles saved specifically for this room (not all home defaults) | 1.0.0 |


### Room schedule profiles

The four named profiles are **Normal**, **Alternative**, **Eco** and **Not in use**. Each profile can store the room's full Home weekly schedule **and** Away configuration (including Away temperature and preheating where supported).

A room-specific profile takes precedence over its matching home-wide default on ordinary restore. To restore the home-wide template explicitly, use `tado_x.restore_schedule_profile_default` in **Developer Tools → Actions**. The default-profile selectors are not on the room device page. If no custom home default is saved, the integration has a predefined factory fallback. Custom home-wide profile classes can be created with `tado_x.create_schedule_profile`. Saving or resetting a default does **not** immediately alter active room schedules.

The integration initially captures the current room schedule as **Normal** if that room profile is missing. The **Custom** indication is based on the most recent comparison; when automatic checks are off, use **Refresh Schedule** to detect changes made outside Home Assistant.

## Tado X Devices

Applies to supported Tado X devices, including Radiator Valve X, Temperature Sensor X, Wireless Receiver X, Wired Smart Thermostat X and Bridge X

| Device info | Description | Version |
| :--- | :--- | :---: |
| Firmware | Shows the firmware version associated with the device |  |
| Serial number | Gives the serial number of the Tado X device | 1.0.0 |


## Tado Radiator Valve X

| Controls | Type | Description | Version |
| :--- | :--- | :--- | :--- |
| Child lock | Switch | Allows the child lock state to be read or set |  |


| Sensors | Description | Version |
| :--- | :--- | :--- |
| Battery | Normal if battery is charged |  |
| Battery Low | Normal if battery is charged |  |
| Connectivity | Connected if device is connected |  |
| Device Temperature | Temperature as recorded by the device |  |
| Temperature Offset | Temperature offset as applied by the device |  |


## Tado Temperature Sensor X

| Sensors | Type | Description | Version |
| :--- | :--- | :--- | :--- |
| Battery | Sensor | Normal if battery is charged |  |
| Battery Low | Binary sensor (battery) | Normal if battery is charged |  |
| Connectivity | Binary sensor (connectivity) | Connected if device is connected |  |
| Device Temperature | Sensor (temperature) | Temperature as recorded by the device |  |
| Temperature Offset | Sensor (temperature) | Temperature offset as applied by the device |  |


## Tado Bridge X

| Sensors | Type | Description | Version |
| :--- | :--- | :--- | :--- |
| Connectivity | Binary sensor (connectivity) | Connected if device is connected |  |


## Tado Wireless Receiver X (TR04)

| Sensors | Type | Description | Version |
| :--- | :--- | :--- | :--- |
| Connectivity | Binary sensor (connectivity) | Connected if device is connected |  |


---

# Climate attributes

In addition to standard climate properties (`hvac_modes`, `hvac_action`, `min_temp`, `max_temp`, `target_temp_step`, `current_temperature`, `temperature`) the climate entity associated with each room exposes the following additional attributes.

| Attribute | Values | Description | Version |
| :--- | :--- | :--- | :---: |
| `preset_modes` | schedule, home, away, auto | Standard climate entry |  |
| `current_humidity` | Percentage | The humidity reading |  |
| `heating_power` | 0-100 | The current heating power |  |
| `next_schedule_change` | date / time | When the next schedule change will occur | 1.0.0 |
| `next_schedule_temperature` |  | The temperature setting for the next schedule change | 1.0.0 |
| `manual_control_active` | true / false | false if the temperature control is being applied via a schedule |  |
| `manual_control_remaining_minutes` | Minutes or unavailable | Time remaining for a timed override, when available | 1.0.0 |
| `manual_control_type` | `MANUAL` / `TIMER` / `NEXT_TIME_BLOCK` | The type of manual control currently applied if `manual_control_active` is `true` |  |
| `open_window_detected` | true | `true` if a window open state is set |  |
| `open_window_ends_at` | date / time | Present if `open_window_detected` is `true` | 1.0.0 |
| `open_window_remaining_minutes` |  | Set if `open_window_detected` is `true` | 1.0.0 |



## Scope and compatibility

Room entity unique IDs and room actions are home-scoped; the same numeric room ID may occur in different Tado homes. The precise entity ID assigned by Home Assistant can vary for existing installations and user-renamed entities. Device and entity availability depends on the configured options, hardware, subscription and Tado API responses. For action parameters, see [ACTIONS.md](ACTIONS.md).


## Holiday Mode
The Tado X Home device provides a Holiday Mode switch, Holiday Status sensor (Off, Scheduled, Active, Ended), Holiday Start and Holiday End timestamp sensors, and Refresh Holiday Mode button. The switch enables any unexpired period without changing its dates; expired periods are replaced by seven days beginning immediately. Room and hot-water holiday settings are preserved. The status sensor includes stored settings as attributes. Holiday refresh runs at the configured schedule-check interval, independently of per-room profile polling, and at scheduled boundaries.

### Holiday date presentation

The existing **Holiday Start** and **Holiday End** entities remain timestamp sensors for automations. Home Assistant may display these as relative dates. The additional **Holiday Start (Local)** and **Holiday End (Local)** text sensors display an absolute local date and time, for example `01 Nov 2026, 07:00`. Timestamp sensors also provide a `local_datetime` attribute.

When Holiday Mode is active, the hot-water API may report `HOLIDAY_MODE_OFF`. **Hot Water State** retains this diagnostic API value; **Hot Water Mode** displays Off. Holiday switches and refreshes trigger an additional home coordinator refresh to update the hot-water entities.

### OpenTherm hot water setpoint and relay capabilities

On some European Tado X TR04 receivers connected using OpenTherm, the Hops API returns a configurable domestic hot water `setpoint` and `setpointConstraints` (for example 30–65 °C) with `state: MANUAL_ON`. A **Hot Water Temperature** number entity is then available, and its writes use `POST /programmer/domesticHotWater/manualControl` with a `setpoint` payload. The **Hot Water State** sensor supports `MANUAL_ON` / `MANUAL_OFF`.

If the same home reports `thermInterfaceType: OPENTHERM`, the relay-oriented DHW buttons (**Boost Hot Water**, **Turn Off Hot Water**, **Resume Hot Water Schedule**) and **Hot Water Mode** selector are **disabled by default for newly registered entities**. This avoids displaying likely unusable actions on a setpoint-capable OpenTherm home, while preserving already registered entities and explicit user choices. Users may enable controls manually if applicable.

This is a heuristic, not a universal declaration that OpenTherm installations cannot support DHW mode changes. A returned `No RELAY DHW device in home` error indicates the specific relay command is not supported by the installation. The account's `features` list (e.g. adaptiveHeating, hydronicBalancing) does not advertise relay capability.


### Hydronic balancing (switch; disabled by default)

**Hydronic Balancing** is a home-level switch created when the Hops `settings/hydronicBalancing` endpoint returns a boolean `hydronicBalancingEnabled`. It displays On/Off, and optionally exposes `panasonic_therm_interface` as an attribute. It is disabled by default to reduce accidental operation. Turning it off can reset Tado's learned balancing parameters; add a confirmation to the dashboard and be aware that direct service calls bypass that confirmation. The write uses PATCH on the same settings endpoint and invalidates the cached state for immediate refresh. The last successful state is cached and rechecked once every 24 hours; unsupported endpoints do not create an entity. The cost is about one API request per home per day, accounted for in the theoretical quota projection.
