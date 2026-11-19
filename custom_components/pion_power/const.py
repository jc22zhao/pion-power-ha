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
    # Lifetime cumulative accumulators read straight from the CHINT "Home Energy"
    # meter via the device feed (monotonic, never reset). These are the accurate
    # source for the TOU utility meters -- unlike the GetHomeData daily stats
    # (StationUse/FromGrid/...), which are UTC-bucketed cloud aggregates that zero
    # out at 00:00 UTC (8pm local) and then read 0/offline for hours.
    {"key": "HomeConsumptionTotal", "signal": "10220010", "name": "Home Consumption Total", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "BatteryChargeTotal", "signal": "10200008", "name": "Battery Charge Total", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "BatteryDischargeTotal", "signal": "10200009", "name": "Battery Discharge Total", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
]

# Battery (BMS) readings from the same device feed. The BMS signals refresh less
# often than the power signals (every few minutes), and while the BMS is not
# reporting - e.g. for a few minutes after an inverter restart - every one of
# them reads 0. A cell can genuinely sit at 0 C (the pack is outdoors), but a
# cell voltage of 0 is never real, so a 0 V "high cell" marks the whole group
# as unavailable rather than recording fake zeros.
#
# The current limits are what the BMS currently allows the inverter to draw or
# push, and fall when the cells are cold - they show cold-weather derating
# directly. "Battery temperature (BMS)" (10200019) is deliberately absent: it
# reads 0 on this unit even when the cell readings are live.
BMS_VALID_SIGNAL = "10200031"  # highest cell voltage
BMS_SENSORS = [
    {"key": "CellTempHigh", "signal": "10200033", "name": "Battery Cell Temperature High", "unit": "°C", "device_class": "temperature", "state_class": "measurement", "precision": 0},
    {"key": "CellTempLow", "signal": "10200034", "name": "Battery Cell Temperature Low", "unit": "°C", "device_class": "temperature", "state_class": "measurement", "precision": 0},
    {"key": "CellVoltageHigh", "signal": "10200031", "name": "Battery Cell Voltage High", "unit": "V", "device_class": "voltage", "state_class": "measurement", "precision": 3},
    {"key": "CellVoltageLow", "signal": "10200032", "name": "Battery Cell Voltage Low", "unit": "V", "device_class": "voltage", "state_class": "measurement", "precision": 3},
    # Highest minus lowest cell, in mV. A balanced pack stays within a few mV;
    # a spread that widens near full charge is what makes the BMS stop short of 100%.
    {"key": "CellVoltageSpread", "signals": ("10200031", "10200032"), "scale": 1000, "name": "Battery Cell Voltage Spread", "unit": "mV", "device_class": "voltage", "state_class": "measurement", "precision": 0},
    {"key": "BmsChargeLimit", "signal": "10200014", "name": "BMS Charge Current Limit", "unit": "A", "device_class": "current", "state_class": "measurement", "precision": 0},
    {"key": "BmsDischargeLimit", "signal": "10200015", "name": "BMS Discharge Current Limit", "unit": "A", "device_class": "current", "state_class": "measurement", "precision": 0},
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
