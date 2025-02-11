"""Constants for the Neso Octowatch integration."""
from homeassistant.const import Platform

DOMAIN = "neso_octowatch"
PLATFORMS = [Platform.SENSOR]

DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# Sensor types
SENSOR_STATUS = "octopus_neso_status"
SENSOR_UTILIZATION = "octopus_neso_utilization"
SENSOR_HIGHEST_ACCEPTED = "octopus_neso_highest_accepted"

# Sensor names
SENSOR_NAMES = {
    SENSOR_STATUS: "Octopus Neso Status",
    SENSOR_UTILIZATION: "Octopus Neso Utilization",
    SENSOR_HIGHEST_ACCEPTED: "Octopus Neso Highest Accepted"
}