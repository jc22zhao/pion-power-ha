# Pion Power (Hoymiles HAS) — Home Assistant integration

Unofficial Home Assistant integration for **Pion Power** home battery systems (built on the
**Hoymiles HAS-7.6LV-USG1** AC-coupled hybrid inverter and the Pion HEMS cloud). It gives you
local-network **monitoring and control** of your battery from Home Assistant using your existing
Pion Power app login — no installer account, no extra hardware, no manufacturer NDA.

> ⚠️ **Unofficial / use at your own risk.** This integration was built by reverse-engineering the
> Pion Power app's own cloud API. It is not affiliated with or endorsed by Pion Power or Hoymiles,
> and it could break if they change their API. Control commands change your live battery's behaviour
> — understand what each setting does before automating it.

## Features

**Sensors**
- Battery State of Charge (%)
- Battery / PV / Grid / Load power (kW)
- Battery daily charge & discharge, PV daily energy (kWh)
- HEMS online status

**Controls** (number entities — read-modify-write on the inverter's work mode)
- Work Mode (raw `EmsMode`)
- Force Charge SOC, Force Discharge SOC
- Max Charge Power, Max Discharge Power
- TOU Reserved SOC, Self-Use SOC, Backup SOC, Economy SOC

Set the relevant parameters plus the matching **Work Mode** to, e.g., force-charge the battery
during cheap grid hours, then return to self-consumption.

## Installation (via HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/jc22zhao/pion-power-ha`,
   category **Integration**.
2. Install **Pion Power (Hoymiles HAS)**, then restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Pion Power**.
4. Enter your Pion Power **email + password**, then pick your **station**. Entities appear under a
   *Pion Power HEMS* device.

Manual install: copy `custom_components/pion_power/` into your HA `config/custom_components/` and
restart.

## How it works / good to know

- Talks to `https://evcharger.pionpower.ca/hems/` with the same token-header auth the app uses
  (`token` + `companycode: PionPower`); the password is MD5-hashed, as the app does it. No request
  signing, so calls are simple JSON POSTs.
- **`cloud_polling`** — it needs internet and the Pion server; it is not a local-only integration.
  Default poll interval is 30 s (configurable in the integration options).
- **Asynchronous control:** a write is accepted immediately but the device confirms it after
  ~8 seconds; the entity updates on the next poll.
- **Mode-gated parameters:** only the parameters of the *active* `EmsMode` take effect. (Observed:
  `EmsMode 7` = Time-of-Use.) Map the mode numbers by switching modes in the Pion app and watching
  the Work Mode value.
- Power units are labelled kW / kWh — verify against your app and adjust `const.py` if needed.

## Background

This integration is the result of a deep-dive into integrating a Hoymiles/Pion battery with Home
Assistant after the installer would only provide the limited Pion app. The local RS485/Modbus paths
on the inverter turned out to be one-way (the HAS only pushes a single value to the data logger),
and the storage Modbus protocol is dealer-NDA only — so the cloud API proved to be the practical
route to full monitoring and control. Sharing it so others in the same situation don't have to
repeat the work.

## License

MIT — see [LICENSE](LICENSE).
