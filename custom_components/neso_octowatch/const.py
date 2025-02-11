"""Constants for the Octopus DFS Session Watch integration."""
from homeassistant.const import Platform

DOMAIN = "neso_octowatch"
PLATFORMS = [Platform.SENSOR]

DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# Sensor types
SENSOR_UTILIZATION = "octopus_dfs_session_utilization"
SENSOR_DELIVERY_DATE = "octopus_dfs_session_delivery_date"
SENSOR_TIME_WINDOW = "octopus_dfs_session_time_window"
SENSOR_PRICE = "octopus_dfs_session_price"
SENSOR_VOLUME = "octopus_dfs_session_volume"
SENSOR_HIGHEST_ACCEPTED = "market_highest_accepted_bid"

# Sensor names
SENSOR_NAMES = {
    SENSOR_UTILIZATION: "Octopus DFS Session Utilization",
    SENSOR_DELIVERY_DATE: "Octopus DFS Session Delivery Date",
    SENSOR_TIME_WINDOW: "Octopus DFS Session Time Window",
    SENSOR_PRICE: "Octopus DFS Session Price",
    SENSOR_VOLUME: "Octopus DFS Session Volume",
    SENSOR_HIGHEST_ACCEPTED: "Market Highest Accepted Bid"
}