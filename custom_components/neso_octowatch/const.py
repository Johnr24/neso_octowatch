"""Constants for the Neso Octowatch integration."""
from homeassistant.const import Platform

DOMAIN = "neso_octowatch"
PLATFORMS = [Platform.SENSOR]

DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# Sensor types
SENSOR_UTILIZATION = "octopus_neso_utilization"
SENSOR_DELIVERY_DATE = "octopus_neso_delivery_date"
SENSOR_TIME_WINDOW = "octopus_neso_time_window"
SENSOR_PRICE = "octopus_neso_price"
SENSOR_VOLUME = "octopus_neso_volume"
SENSOR_HIGHEST_ACCEPTED = "octopus_neso_highest_accepted"

# Sensor names
SENSOR_NAMES = {
    SENSOR_UTILIZATION: "Octopus Neso Utilization",
    SENSOR_DELIVERY_DATE: "Octopus Neso Delivery Date",
    SENSOR_TIME_WINDOW: "Octopus Neso Time Window",
    SENSOR_PRICE: "Octopus Neso Price",
    SENSOR_VOLUME: "Octopus Neso Volume",
    SENSOR_HIGHEST_ACCEPTED: "Octopus Neso Highest Accepted"
}