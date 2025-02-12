"""Platform for sensor integration."""
from __future__ import annotations

from datetime import datetime
import zoneinfo
import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SENSOR_NAMES,
    SENSOR_UTILIZATION,
    SENSOR_DELIVERY_DATE,
    SENSOR_TIME_WINDOW,
    SENSOR_PRICE,
    SENSOR_VOLUME,
    SENSOR_HIGHEST_ACCEPTED,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    STATUS_UNKNOWN,
    VALID_STATUSES,
)

LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Octopus DFS Session Watch sensor entities."""   
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Log the setup process
    LOGGER.debug("Setting up sensors - waiting for initial data refresh")
    
    # Force an initial refresh to ensure we have data before creating entities
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for sensor_type in [
        SENSOR_UTILIZATION,
        SENSOR_DELIVERY_DATE,
        SENSOR_TIME_WINDOW,
        SENSOR_PRICE,
        SENSOR_VOLUME,
        SENSOR_HIGHEST_ACCEPTED
    ]:
        entities.append(DfsSessionWatchSensor(coordinator, sensor_type))

    async_add_entities(entities, True)

class DfsSessionWatchSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Octopus DFS Session Watch Sensor."""

    def __init__(self, coordinator, sensor_type):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = SENSOR_NAMES[sensor_type]
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}"
        self._attr_native_unit_of_measurement = None
        self._attr_state_class = None

        # Set appropriate device class and units based on sensor type
        if sensor_type == SENSOR_UTILIZATION:
            self._attr_has_entity_name = True
            self._attr_translation_key = "utilization"
            self._attr_entity_registry_enabled_default = True
            self._attr_device_class = None  # Text-based state
            self._attr_native_value = STATUS_UNKNOWN  # Set initial state
        elif sensor_type == SENSOR_DELIVERY_DATE:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif sensor_type == SENSOR_TIME_WINDOW:
            # Text value indicating DFS session period
            self._attr_has_entity_name = True
            self._attr_translation_key = "time_window"
            self._attr_entity_registry_enabled_default = True
            self._attr_state_class = None  # Text-based state, no measurement
        elif sensor_type == SENSOR_PRICE:
            self._attr_native_unit_of_measurement = "GBP/MWh"
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_state_class = SensorStateClass.TOTAL
            self._attr_suggested_display_precision = 2
        elif sensor_type == SENSOR_VOLUME:
            self._attr_native_unit_of_measurement = "MW"
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_suggested_display_precision = 1
        elif sensor_type == SENSOR_HIGHEST_ACCEPTED:
            self._attr_native_unit_of_measurement = "GBP/MWh"
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 2
            self._attr_has_entity_name = True
            self._attr_translation_key = "highest_accepted"
        
        if sensor_type == SENSOR_UTILIZATION:
            self._attr_options = VALID_STATUSES
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_state_class = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            self._attr_extra_state_attributes = {}
            self._attr_native_value = None
            return
        
        key = self._sensor_type
        if key not in self.coordinator.data:
            if (self._sensor_type == SENSOR_DELIVERY_DATE and 
                "octopus_dfs_session_highest_accepted" in self.coordinator.data):
                # Try to get delivery date from highest accepted attributes
                highest_accepted = self.coordinator.data["octopus_dfs_session_highest_accepted"]
                if "attributes" in highest_accepted:
                    delivery_date = highest_accepted["attributes"].get("delivery_date")
                    if delivery_date:
                        try:
                            self._attr_native_value = datetime.fromisoformat(
                                delivery_date.split('+')[0]
                            ).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                        except ValueError:
                            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        sensor_data = self.coordinator.data[key]
        state_value = sensor_data.get("state")
        
        # Set state based on sensor type
        if self._sensor_type == SENSOR_UTILIZATION:
            if isinstance(state_value, str) and state_value in VALID_STATUSES:
                self._attr_native_value = state_value
            else:
                self._attr_native_value = STATUS_UNKNOWN
            LOGGER.debug("Setting utilization state to: %s", self._attr_native_value)
        
        elif self._sensor_type == SENSOR_DELIVERY_DATE:
            if isinstance(state_value, str):
                try:
                    clean_value = state_value.split('+')[0].strip().split('.')[0].strip()
                    try:
                        # Try ISO format first
                        dt = datetime.fromisoformat(clean_value)
                    except ValueError:
                        try:
                            # Try basic date format
                            dt = datetime.strptime(clean_value, "%Y-%m-%d")
                        except ValueError:
                            # Try full date format
                            dt = datetime.strptime(clean_value, "%d %B %Y")
                    # Set time to midnight (00:00)
                    dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    self._attr_native_value = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                except ValueError:
                    self._attr_native_value = None
            else:  # Not a string value
                self._attr_native_value = state_value

        elif self._sensor_type == SENSOR_HIGHEST_ACCEPTED:
            try:
                LOGGER.debug("Raw highest accepted bid value received: %s", state_value)
                self._attr_native_value = float(state_value) if state_value is not None else None
                LOGGER.debug("Setting highest accepted bid value to: %s", self._attr_native_value)
            except (ValueError, TypeError):
                self._attr_native_value = state_value
        elif self._sensor_type == SENSOR_VOLUME:
            try:
                if isinstance(state_value, str) and ';' in state_value:
                    # Split the string and convert all values to floats
                    values = [float(v.strip()) for v in state_value.split(';')]
                    # Use the most recent (last) value
                    self._attr_native_value = values[-1]
                    # Store all values as an attribute for reference
                    self._attr_extra_state_attributes = {
                        **sensor_data.get("attributes", {}),
                        'all_volumes': values
                    }
                else:
                    self._attr_native_value = float(state_value) if state_value is not None else None
                LOGGER.debug("Setting volume value to: %s", self._attr_native_value)
            except (ValueError, TypeError) as e:
                LOGGER.error("Error processing volume value '%s': %s", state_value, str(e))
                self._attr_native_value = None
        else:
            if self._sensor_type == SENSOR_TIME_WINDOW:
                try:
                    if isinstance(state_value, str) and ';' in state_value:
                        # Split the string into time window values
                        values = [v.strip() for v in state_value.split(';')]
                        if values:
                            # Use the most recent (last) value
                            self._attr_native_value = values[-1]
                            # Store all values as an attribute for reference
                            self._attr_extra_state_attributes = {
                                **sensor_data.get("attributes", {}),
                                'all_time_windows': values
                            }
                        else:
                            self._attr_native_value = STATUS_UNKNOWN
                    else:
                        # If it's a single value, use it directly if it's a non-empty string
                        self._attr_native_value = state_value if isinstance(state_value, str) and state_value.strip() else STATUS_UNKNOWN
                except (ValueError, TypeError) as e:
                    LOGGER.error("Error processing time window value '%s': %s", state_value, str(e))
                    self._attr_native_value = STATUS_UNKNOWN
            else:
                self._attr_native_value = state_value
            
            self._attr_extra_state_attributes = sensor_data.get("attributes", {})
        
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._sensor_type in self.coordinator.data
        )