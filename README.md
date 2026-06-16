# Pion Power (Hoymiles HAS) — Home Assistant integration

Unofficial Home Assistant integration for **Pion Power** home battery systems (built on the
**Hoymiles HAS-7.6LV-USG1** AC-coupled hybrid inverter and the Pion HEMS cloud). It gives you
local-network **monitoring and control** of your battery from Home Assistant using your existing
Pion Power app login — no installer account, no extra hardware, no manufacturer NDA.

> ⚠️ **Unofficial / use at your own risk.** This integration was built by reverse-engineering the
> Pion Power app's own cloud API. It is not affiliated with or endorsed by Pion Power or Hoymiles,
> and it could break if they change their API. Control commands change your live battery's behaviour
> — understand what each setting does before automating it.
>
> ⚠️ **AC-coupled solar caution.** If your PV is AC-coupled (microinverters), be careful with
> battery **charge** control — especially **grid-charge**. The HAS can respond by curtailing your
> solar output (sometimes to 0%) via its export management, and the curtailment can latch. Prefer
> normal TOU scheduling and avoid forcing grid-charge unless you understand this interaction.
> (Earlier `force_charge`/`force_discharge` services were removed in 0.5.0 for this reason.)
>
> ℹ️ **Single-inverter setups.** This integration is currently built and tested for a system with
> **one storage inverter** (one HAS). It reads that inverter's signals directly; on a multi-inverter
> site it would only surface the first inverter. Multi-inverter support (per-inverter sub-devices +
> aggregate) isn't implemented yet — if you have such a system, open an issue with your
> `GetDeviceList` / `GetRealDataByDeviceCode` responses and it can be added.

## Features

**Sensors**
- Battery State of Charge (%)
- Battery / PV / Grid / Load power (kW)
- Battery daily charge & discharge, PV daily energy (kWh)
- HEMS online status
- **TOU Schedule** — reads the **active TOU template** (the full, app-editable
  schedule via `GetTouTemplateDetail`). State is the number of periods; attributes
  hold the `periods`, a humanized `summary`, `template_name`, `reserved_soc`,
  `ems_mode`, and `tou_mode_active`. Note: the workmode's `TOUModeStraPeriods` is
  only a server-compiled subset (the grid-charge windows), so the sensor reads the
  template instead and falls back to the workmode list only if the template is
  unavailable.

**Controls** (number entities — read-modify-write on the inverter's work mode)
- Work Mode (raw `EmsMode`)
- Force Charge SOC, Force Discharge SOC
- Max Charge Power, Max Discharge Power
- TOU Reserved SOC, Self-Use SOC, Backup SOC, Economy SOC

Set the relevant parameters plus the matching **Work Mode** to, e.g., force-charge the battery
during cheap grid hours, then return to self-consumption.

**Schedule editor** (built-in entities — no custom dashboards or templates needed)

Each period of your **active** TOU template appears as a **TOU Period N** sub-device with native
entities — **Start**, **End** (time), **Mode** (select: Auto / Charge / Discharge), **Target SOC**,
**Run Power** (number), **Grid Charge**, **Sell to Grid** (switch). The number of period devices
tracks your schedule automatically.

Edits are staged locally; the HEMS device has three buttons:
- **Apply schedule** — write the staged schedule to the inverter (one write) and activate it.
- **Reload schedule from server** — discard staged edits.
- **Add TOU period** — append a new period (each period device also has a **Delete period** button).

The integration reads only the *active* template; to switch which template is active, use the Pion
app. Multi-group templates (separate weekday/weekend or seasonal rules) are shown in full by the
**TOU Schedule** sensor; the period entities edit the primary rule-group.

> **How a schedule actually executes.** The HAS runs the inverter **work mode** (`TOUModeStraPeriods`),
> not the template — writing the template alone does nothing. So Apply (and `set_tou_template`) write
> the template *and* push the **grid-charge windows** (periods with **Grid Charge** on) to the work
> mode, where they take effect within ~30–60 s. Discharge isn't an explicit window: outside the
> charge windows the inverter runs default self-consumption (covers load from solar/battery) down to
> the **reserve floor** (`TOU Reserved SOC`) — so that reserve is your discharge/"hold" lever.

**Writes are off by default.** Enable *Allow schedule writes* in the integration options
(Settings → Devices & Services → Pion Power → Configure) to allow Apply and the number/work-mode
controls to push to the inverter. Until then the integration is read-only.

**Services**
- `pion_power.set_tou_template` — write the full schedule (any shape: multiple seasonal date
  ranges, weekday/weekend groups, any number of periods). Pass `groups` (each with an optional date
  range, `weeks`, and `periods`). Used by automations; the per-period entities above are the
  point-and-click equivalent.
- `pion_power.set_tou_schedule` — coarse write of the workmode grid-charge windows (`periods` list).
  Both services require *Allow schedule writes*.

## Work modes & SOC parameters

The inverter runs in one of several **work modes**, selected by the raw `EmsMode` value
(the *Work Mode* number entity). Each mode has its own SOC threshold, and **only the parameter
belonging to the currently active mode takes effect** — changing, say, *Backup SOC* while the
inverter is in TOU mode does nothing until you also switch `EmsMode` to backup. (These mappings are
reverse-engineered; only `EmsMode 7` = Time-of-Use is confirmed. Map the other mode numbers by
switching modes in the Pion app and watching the *Work Mode* value.)

| Mode | What it does | Its SOC parameter |
|------|--------------|-------------------|
| **Time-of-Use** (`EmsMode 7`, confirmed) | Follows the TOU schedule/template (charge/discharge windows). The battery still discharges to cover load before importing, down to the reserve floor. | **TOU Reserved SOC** — the floor the battery is held to (your "keep N% in reserve" lever; the only one active in TOU mode). |
| **Self-Consumption** | Maximize use of own solar: cover load from solar/battery, bank surplus. | **Self-Use SOC** — floor the battery discharges to for self-use before holding the rest in reserve. |
| **Backup / UPS** | Keep the battery charged for blackout protection. | **Backup SOC** — minimum SOC reserved for an outage; the inverter won't discharge below it and tops it up from solar/grid. |
| **Economy** | Charge/discharge by the inverter's own peak/valley clock (`EconomyModeInfos`), an alternative to TOU. | **Economy SOC** — the floor during economy operation. |
| **Force charge / discharge** | One-shot push to a target SOC. | **Force Charge SOC** — charge *up to* this % then stop. **Force Discharge SOC** — discharge *down to* this % then stop. |

**Other work-mode controls:** *Max Charge Power* / *Max Discharge Power* (caps, %).

> ⚠️ The earlier `force_charge` / `force_discharge` **services** were removed in 0.5.0 (they could
> trigger solar curtailment on AC-coupled systems). The Force Charge/Discharge **SOC number
> entities** remain as raw work-mode fields but only matter if a force mode is engaged.

## Installation (via HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/jc22zhao/pion-power-ha`,
   category **Integration**.
2. Install **Pion Power (Hoymiles HAS)**, then restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Pion Power**.
4. Enter your Pion Power **email + password**, then pick your **station**. Entities appear under a
   *Pion Power HEMS* device.

Manual install: copy `custom_components/pion_power/` into your HA `config/custom_components/` and
restart.

> 💡 **Highly recommended: use a dedicated app user for Home Assistant.** The Pion cloud allows only
> one active session per user, so if Home Assistant logs in with *your* account it will keep kicking
> your phone out of the Pion app (and vice-versa). Instead, in the Pion Power app create a **separate
> user** and **add that user to your home/station**, then give Home Assistant *that* user's login.
> With its own session, the integration and your personal app login can both stay connected and read
> the data at the same time — no tug-of-war. (The integration also has a built-in coexistence
> fallback for the single-session case, but a dedicated user avoids the conflict entirely.)

**Changing your login later:** open the entry's ⋮ menu → **Reconfigure** to update the email/password
in place (entities and history are kept). If the server ever rejects the login (e.g. you changed the
password), Home Assistant prompts you to re-authenticate automatically.

## How it works / good to know

- Talks to `https://evcharger.pionpower.ca/hems/` with the same token-header auth the app uses
  (`token` + `companycode: PionPower`); the password is MD5-hashed, as the app does it. No request
  signing, so calls are simple JSON POSTs.
- **`cloud_polling`** — it needs internet and the Pion server; it is not a local-only integration.
  Default poll interval is 30 s (configurable in the integration options).
- **Asynchronous control:** a write is accepted immediately but the device confirms it after
  ~8 seconds; the entity updates on the next poll.
- **Mode-gated parameters:** only the parameters of the *active* `EmsMode` take effect — see
  [Work modes & SOC parameters](#work-modes--soc-parameters) above.
- Power units are labelled kW / kWh — verify against your app and adjust `const.py` if needed.
- **Data source:** live power/SOC come from the **inverter's own signals**
  (`GetRealDataByDeviceCode` — the app's "inverter" view), which are accurate. The
  station aggregate (`GetRealDataByStationCode`, the app's "energy station" view)
  can over-report PV, so it's only used as a fallback and for daily charge/discharge.

## Background

This integration is the result of a deep-dive into integrating a Hoymiles/Pion battery with Home
Assistant after the installer would only provide the limited Pion app. The local RS485/Modbus paths
on the inverter turned out to be one-way (the HAS only pushes a single value to the data logger),
and the storage Modbus protocol is dealer-NDA only — so the cloud API proved to be the practical
route to full monitoring and control. Sharing it so others in the same situation don't have to
repeat the work.

## License

MIT — see [LICENSE](LICENSE).
