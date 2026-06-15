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

SERVICE_SET_TOU = "set_tou_schedule"

# Real-time sensors from GetRealDataByStationCode:
# (key, friendly name, unit, device_class, state_class)
SENSORS = [
    {"key": "EsSoc", "name": "Battery SOC", "unit": "%", "device_class": "battery", "state_class": "measurement"},
    {"key": "EsPower", "name": "Battery Power", "unit": "kW", "device_class": "power", "state_class": "measurement"},
    {"key": "PvPower", "name": "PV Power", "unit": "kW", "device_class": "power", "state_class": "measurement"},
    {"key": "GridPower", "name": "Grid Power", "unit": "kW", "device_class": "power", "state_class": "measurement"},
    {"key": "LoadPower", "name": "Load Power", "unit": "kW", "device_class": "power", "state_class": "measurement"},
    {"key": "EsDailyCharge", "name": "Battery Daily Charge", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "EsDailyDisCharge", "name": "Battery Daily Discharge", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "PvDailyElectricQuantity", "name": "PV Daily Energy", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
]

# Daily-energy sensors from GetHomeData (today's totals). Each value is obj["Value"].
HOME_SENSORS = [
    {"key": "FromGrid", "name": "Grid Import Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "ToGrid", "name": "Grid Export Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "StationUse", "name": "Home Consumption Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "FromSolar", "name": "Solar to Home Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    {"key": "FromBattery", "name": "Battery to Home Daily", "unit": "kWh", "device_class": "energy", "state_class": "total_increasing"},
]

# Writable work-mode fields (number entities). Read-modify-write on SetStationWorkMode.
# NOTE: parameters are mode-gated by EmsMode, and changes apply asynchronously (~8s).
CONTROLS = [
    {"field": "EmsMode", "name": "Work Mode (raw EmsMode)", "min": 1, "max": 8, "step": 1, "unit": None},
    {"field": "ForceChargeSOC", "name": "Force Charge SOC", "min": 0, "max": 100, "step": 1, "unit": "%"},
    {"field": "ForceDisargeSOC", "name": "Force Discharge SOC", "min": 0, "max": 100, "step": 1, "unit": "%"},
    {"field": "MaximumChargePower", "name": "Max Charge Power", "min": 0, "max": 100, "step": 1, "unit": "%"},
    {"field": "MaximumDischargePower", "name": "Max Discharge Power", "min": 0, "max": 100, "step": 1, "unit": "%"},
    {"field": "TOUModeReservedSoc", "name": "TOU Reserved SOC", "min": 0, "max": 100, "step": 1, "unit": "%"},
    {"field": "SelfUsedSOC", "name": "Self-Use SOC", "min": 0, "max": 100, "step": 1, "unit": "%"},
    {"field": "BackUpSOC", "name": "Backup SOC", "min": 0, "max": 100, "step": 1, "unit": "%"},
    {"field": "EconomicModeSOC", "name": "Economy SOC", "min": 0, "max": 100, "step": 1, "unit": "%"},
]
