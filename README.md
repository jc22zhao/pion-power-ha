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
- Lifetime cumulative energy accumulators read straight from the meter — home
  consumption, battery charge & discharge totals (kWh). Monotonic and never
  reset, so they make ideal sources for `utility_meter` (TOU breakdowns, etc.)
- HEMS online status
- **TOU Schedule** — a read-only summary of the active schedule (the work-mode
  charge windows + reserve), with the periods in its attributes.

**Controls**
- **Reserve Floor SOC** (number) — the battery's discharge floor (`TOUModeReservedSoc`): the
  inverter covers load from the battery down to this level, then leaves the rest. Raising it
  "holds" the battery (e.g. to save it for peak); it's also the blackout-reserve lever. This is the
  one work-mode SOC the integration exposes — the others (Self-Use / Backup / Economy / Force
  charge-discharge) are mode-gated and unused in the charge-window model, so they aren't surfaced.

**Schedule editor** — charge windows as sub-devices (no dashboards/templates needed)

The HAS executes the **work mode** (`TOUModeStraPeriods`), so the editor reads and writes there
directly. The schedule is just **charge windows** + the reserve floor; discharge is automatic
(default self-consumption down to the reserve floor), so there's no discharge "period" to manage.

- Each charge window is a **Charge Window N** sub-device with **Start**, **End** (time), **Target
  SOC** (number), and **Grid Charge** (switch). Each also has a **Delete window** button.
- The HEMS device has an **Add charge window** button. The inverter supports **at most 2 charge
  windows** (writing more silently drops the extras), so Add is disabled once two exist.
- Edits **auto-apply** — change an entity and it's written to the inverter after a short debounce
  (rapid edits coalesce into one `SetStationWorkMode`). No Apply button; changes take effect in
  ~30–60 s, and the entities re-sync to the cloud on each poll.

> **One source of truth.** The editor and the `set_tou_schedule` service both read/write the work
> mode, so **manual edits and an autoscheduler automation stay in sync** — the entities reflect
> whatever was last written (by you or an automation), and an in-progress manual edit is held until
> the debounced write flushes. ⚠️ Don't activate a TOU **template** in the Pion app while using the
> HA editor/automations — doing so re-compiles onto the work mode (and drops grid-charge); HA's
> work-mode control is the single source of truth.

**Writes are off by default.** Enable *Allow schedule writes* in the integration options
(Settings → Devices & Services → Pion Power → Configure). Until then the integration is read-only
(edits won't be written).

**Services / automations**
- `pion_power.set_tou_schedule` — write the charge windows atomically (`periods` list, each with
  `StartTime`, `EndTime`, `ChargeOrDis` 1=charge, `SOC`, `RunPower`, `GridChargeEn`), plus optional
  `reserved_soc`. **Recommended for autoschedulers** (one atomic write of the whole schedule).
- Autoschedulers can equally just **set the Charge Window entities** — the debounce coalesces those
  into a single safe write. Either way, requires *Allow schedule writes*.
- `pion_power.set_tou_template` — legacy template writer; the HAS doesn't execute templates, so
  prefer `set_tou_schedule`.

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

> This table is background on the inverter's modes. In practice the integration runs the inverter in
> **Time-of-Use** mode and exposes only the **Reserve Floor SOC**; the other mode SOC parameters
> (Self-Use / Backup / Economy / Force charge-discharge) and the raw Work Mode / Max Power fields are
> **no longer surfaced as entities** (they're unused in the charge-window + reserve-floor model).
> The `force_charge` / `force_discharge` services were removed in 0.5.0 (solar-curtailment risk).

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
