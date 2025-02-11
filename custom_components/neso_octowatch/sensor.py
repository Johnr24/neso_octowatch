"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SENSOR_NAMES,
    SENSOR_STATUS,
    SENSOR_UTILIZATION,
    SENSOR_HIGHEST_ACCEPTED,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Neso Octowatch sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for sensor_type in [SENSOR_STATUS, SENSOR_UTILIZATION, SENSOR_HIGHEST_ACCEPTED]:
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

        # Set appropriate device class and units based on sensor type
        if sensor_type == SENSOR_UTILIZATION:
            self._attr_native_unit_of_measurement = "%"
            self._attr_device_class = "power_factor"
        elif sensor_type == SENSOR_HIGHEST_ACCEPTED:
            self._attr_native_unit_of_measurement = "W"
            self._attr_device_class = "power"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
        else:
            sensor_data = self.coordinator.data.get(self._sensor_type, {})
            self._attr_native_value = sensor_data.get("state")
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