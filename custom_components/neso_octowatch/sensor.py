"""Platform for sensor integration."""
from __future__ import annotations

from datetime import datetime
import zoneinfo
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
    SENSOR_STATUS,
    SENSOR_UTILIZATION,
    SENSOR_DELIVERY_DATE,
    SENSOR_TIME_WINDOW,
    SENSOR_PRICE,
    SENSOR_VOLUME,
    SENSOR_HIGHEST_ACCEPTED,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Neso Octowatch sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Initial refresh to get latest data
    await coordinator.async_refresh()

    entities = []
    for sensor_type in [
        SENSOR_STATUS,
        SENSOR_UTILIZATION,
        SENSOR_DELIVERY_DATE,
        SENSOR_TIME_WINDOW,
        SENSOR_PRICE,
        SENSOR_VOLUME,
        SENSOR_HIGHEST_ACCEPTED
    ]:
        entities.append(NesoOctowatchSensor(coordinator, sensor_type))

    async_add_entities(entities, True)

class NesoOctowatchSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Neso Octowatch Sensor."""

    def __init__(self, coordinator, sensor_type):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = SENSOR_NAMES[sensor_type]
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}"
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None

        # Set appropriate device class and units based on sensor type
        if sensor_type in [SENSOR_UTILIZATION, SENSOR_HIGHEST_ACCEPTED]:
            # Will be set dynamically based on value type
            pass
        elif sensor_type == SENSOR_DELIVERY_DATE:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif sensor_type == SENSOR_TIME_WINDOW:
            pass  # Text value, no special handling needed
        elif sensor_type == SENSOR_PRICE:
            self._attr_native_unit_of_measurement = "GBP/MWh"
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 2
        elif sensor_type == SENSOR_VOLUME:
            self._attr_native_unit_of_measurement = "MW"
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
        else:
            key = self._sensor_type
            if key in self.coordinator.data:
                sensor_data = self.coordinator.data[key]
                state_value = sensor_data.get("state")
                
                try:
                    if self._sensor_type == SENSOR_UTILIZATION:
                        # For utilization, only set percentage unit if it's a number
                        if isinstance(state_value, (int, float)) or (
                            isinstance(state_value, str) and 
                            state_value.replace('.', '', 1).isdigit()
                        ):
                            self._attr_native_value = float(state_value)
                            self._attr_native_unit_of_measurement = "%"
                            self._attr_state_class = SensorStateClass.MEASUREMENT
                        else:
                            self._attr_native_value = state_value
                            self._attr_native_unit_of_measurement = None
                            self._attr_state_class = None
                    elif self._sensor_type == SENSOR_DELIVERY_DATE:
                        if isinstance(state_value, str):
                            try:
                                # Try different date formats
                                try:
                                    # Try parsing with time
                                    dt = datetime.strptime(state_value, "%d %B %Y at %H:%M")
                                except ValueError:
                                    # Fallback to date-only format
                                    dt = datetime.strptime(state_value, "%Y-%m-%d")
                                dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                                self._attr_native_value = dt
                            except ValueError:
                                self._attr_native_value = None
                        else:
                            self._attr_native_value = state_value
                    else:
                        if self._sensor_type == SENSOR_HIGHEST_ACCEPTED:
                            # For highest accepted, only set monetary attributes if it's a number
                            if isinstance(state_value, (int, float)) or (
                                isinstance(state_value, str) and 
                                state_value.replace('.', '', 1).isdigit()
                            ):
                                self._attr_native_value = float(state_value)
                                self._attr_native_unit_of_measurement = "GBP/MWh"
                                self._attr_device_class = SensorDeviceClass.MONETARY
                                self._attr_state_class = SensorStateClass.MEASUREMENT
                                self._attr_suggested_display_precision = 2
                            else:
                                self._attr_native_value = state_value
                                self._attr_native_unit_of_measurement = None
                                self._attr_device_class = None
                                self._attr_state_class = None
                        else:
                            self._attr_native_value = state_value
                except (ValueError, TypeError):
                    self._attr_native_value = state_value
                
                self._attr_extra_state_attributes = sensor_data.get("attributes", {})
            else:
                self._attr_native_value = None
                self._attr_extra_state_attributes = {}
        
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._sensor_type in self.coordinator.data
        )