"""Constants for the Pion Power (Hoymiles HAS) integration."""

DOMAIN = "pion_power"
BASE_URL = "https://evcharger.pionpower.ca/hems/"
COMPANY_CODE = "PionPower"

DEFAULT_SCAN_INTERVAL = 30
# When the mobile app takes the single-session account, HA waits this long
# before reclaiming it (configurable in the integration options).
DEFAULT_RETRY_INTERVAL = 300

CONF_EMAIL = "email"
CONF_STATION_CODE = "station_code"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_RETRY_INTERVAL = "retry_interval"
# Schedule writes re-push the TOU schedule to the inverter (a live control
# action). Off by default so a fresh install is read-only until the owner opts
# in via the integration options.
CONF_ALLOW_WRITE = "allow_schedule_write"
DEFAULT_ALLOW_WRITE = False

SERVICE_SET_TOU = "set_tou_schedule"
SERVICE_SET_TOU_TEMPLATE = "set_tou_template"

# Real-time sensors. Live power/SOC are read from the HAS inverter's own signals
# (GetRealDataByDeviceCode, the app's accurate "inverter" view) via "signal";
# the station aggregate (GetRealDataByStationCode, "key") over-reports PV, so it
# is only a fallback. Daily charge/discharge have no device signal -> station key.
# (key, signal id, friendly name, unit, device_class, state_class)
SENSORS = [
    {"key": "EsSoc", "signal": "10200006", "name": "Battery SOC", "unit": "%", "device_class": "battery", "state_class": "measurement"},
    {"key": "EsPower", "signal": "10200003", "name": "Battery Power", "unit": "kW", "device_class": "power", "state_class": "measurement"},
    {"key": "PvPower", "signal": "10210000", "name": "PV Power", "unit": "kW", "device_class": "power", "state_class": "measurement"},
    {"key": "GridPower", "signal": "10230000", "name": "Grid Power", "unit": "kW", "device_class": "power", "state_class": "measurement"},
    {"key": "LoadPower", "signal": "10220000", "name": "Load Power", "unit": "kW", "device_class": "power", "state_class": "measurement"},
    {"key": "EsDailyCharge", "name": "Battery Daily Charge", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "EsDailyDisCharge", "name": "Battery Daily Discharge", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "PvDailyElectricQuantity", "signal": "10210002", "name": "PV Daily Energy", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
]

# Daily-energy sensors from GetHomeData (today's totals). Each value is obj["Value"].
HOME_SENSORS = [
    {"key": "FromGrid", "name": "Grid Import Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "ToGrid", "name": "Grid Export Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "StationUse", "name": "Home Consumption Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "FromSolar", "name": "Solar to Home Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "FromBattery", "name": "Battery to Home Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
]

# The only work-mode number we expose: the reserve floor (discharge floor /
# "hold" lever). The other work-mode SOC/power fields are mode-gated and unused
# in this charge-window + reserve-floor model, so they are not surfaced.
CONTROLS = [
    {"field": "TOUModeReservedSoc", "name": "Reserve Floor SOC", "min": 0, "max": 100, "step": 1, "unit": "%"},
]

# Inverter caps the work-mode TOU schedule at this many charge windows (verified:
# writing more returns success but only 2 persist).
MAX_CHARGE_WINDOWS = 2

# Debounce (seconds) for coalescing rapid entity edits into one work-mode write.
WRITE_DEBOUNCE = 3
