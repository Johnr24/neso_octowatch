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
        
        # Initialize with coordinator data if available
        if coordinator.data and sensor_type in coordinator.data:
            self._handle_initial_state(coordinator.data[sensor_type])

        # Set appropriate device class and units based on sensor type
        if sensor_type == SENSOR_UTILIZATION:
            self._attr_has_entity_name = True
            self._attr_translation_key = "utilization"
            self._attr_entity_registry_enabled_default = True
            self._attr_device_class = None  # Text-based state
            # Initial state will be set by _handle_initial_state if data available
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
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 2
            self._attr_has_entity_name = True
            self._attr_translation_key = "average_price"
        elif sensor_type == SENSOR_VOLUME:
            self._attr_native_unit_of_measurement = "MW"
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
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

    def _handle_initial_state(self, sensor_data: dict) -> None:
        """Handle the initial state setup for the sensor."""
        if not sensor_data:
            self._attr_native_value = None
            return

        state_value = sensor_data.get("state")
        
        # Process value based on sensor type
        if self._sensor_type == SENSOR_UTILIZATION:
            self._attr_native_value = state_value if state_value in VALID_STATUSES else STATUS_UNKNOWN
        
        elif self._sensor_type == SENSOR_DELIVERY_DATE:
            self._process_delivery_date(state_value)
        
        elif self._sensor_type == SENSOR_TIME_WINDOW:
            self._process_time_window(state_value, sensor_data.get("attributes", {}))
        
        elif self._sensor_type == SENSOR_VOLUME:
            self._process_volume(state_value, sensor_data.get("attributes", {}))
        
        elif self._sensor_type == SENSOR_PRICE:
            self._process_price(state_value, sensor_data.get("attributes", {}))
            
        elif self._sensor_type == SENSOR_HIGHEST_ACCEPTED:
            try:
                self._attr_native_value = float(state_value) if state_value is not None else None
            except (ValueError, TypeError):
                self._attr_native_value = None
        
        else:  # Default handling for other sensors
            self._attr_native_value = state_value
        
        self._attr_extra_state_attributes = sensor_data.get("attributes", {})

    def _process_delivery_date(self, state_value: str | None) -> None:
        """Process delivery date value."""
        if not isinstance(state_value, str):
            self._attr_native_value = None
            return
            
        try:
            clean_value = state_value.split('+')[0].strip().split('.')[0].strip()
            try:
                dt = datetime.fromisoformat(clean_value)
            except ValueError:
                try:
                    dt = datetime.strptime(clean_value, "%Y-%m-%d")
                except ValueError:
                    dt = datetime.strptime(clean_value, "%d %B %Y")
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            self._attr_native_value = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        except ValueError:
            self._attr_native_value = None

    def _process_time_window(self, state_value: str | None, attributes: dict) -> None:
        """Process time window value."""
        if isinstance(state_value, str) and ';' in state_value:
            values = [v.strip() for v in state_value.split(';')]
            if values:
                self._attr_native_value = values[-1]  # Use most recent
                self._attr_extra_state_attributes = {
                    **attributes,
                    'all_time_windows': values
                }
            else:
                self._attr_native_value = STATUS_UNKNOWN
        else:
            self._attr_native_value = state_value if isinstance(state_value, str) and state_value.strip() else STATUS_UNKNOWN

    def _process_price(self, state_value: str | None, attributes: dict) -> None:
        """Process price values and calculate average for the day."""
        if state_value == STATUS_UNKNOWN:
            self._attr_native_value = None
            return
            
        try:
            # Get all prices from all sessions
            all_prices = []
            
            if isinstance(state_value, str):
                if ';' in state_value:
                    # Multiple sessions - split and process each one
                    sessions = [s.strip() for s in state_value.split(';') if s.strip()]
                    for session in sessions:
                        if ',' in session:
                            # Multiple prices in this session
                            session_prices = [float(p.strip()) for p in session.split(',') if p.strip()]
                            all_prices.extend(session_prices)
                        else:
                            # Single price in this session
                            try:
                                price = float(session.strip())
                                all_prices.append(price)
                            except (ValueError, TypeError):
                                continue
                elif ',' in state_value:
                    # Single session with multiple prices
                    all_prices = [float(p.strip()) for p in state_value.split(',') if p.strip()]
                else:
                    # Single price
                    try:
                        all_prices = [float(state_value.strip())]
                    except (ValueError, TypeError):
                        pass
                        
            if all_prices:
                # Calculate average of all prices
                self._attr_native_value = sum(all_prices) / len(all_prices)
                self._attr_extra_state_attributes = {
                    **attributes,
                    'all_prices': all_prices,
                    'price_count': len(all_prices),
                    'min_price': min(all_prices),
                    'max_price': max(all_prices)
                }
            else:
                self._attr_native_value = None
        except (ValueError, TypeError):
            self._attr_native_value = None

    def _process_volume(self, state_value: str | None, attributes: dict) -> None:
        """Process volume value."""
        if state_value == STATUS_UNKNOWN:
            self._attr_native_value = None
            return
            
        try:
            if isinstance(state_value, str) and ';' in state_value:
                pairs = [pair.strip() for pair in state_value.split(';') if pair.strip()]
                values = []
                for pair in pairs:
                    if ',' in pair:
                        actual = pair.split(',')[0].strip()
                        values.append(float(actual))
                
                if values:
                    self._attr_native_value = values[-1]  # Use most recent
                    self._attr_extra_state_attributes = {
                        **attributes,
                        'all_volumes': values
                    }
                else:
                    self._attr_native_value = None
            elif state_value and str(state_value).strip():
                if ',' in str(state_value):
                    actual = str(state_value).split(',')[0].strip()
                    self._attr_native_value = float(actual)
                else:
                    self._attr_native_value = float(str(state_value).strip())
            else:
                self._attr_native_value = None
        except (ValueError, TypeError):
            self._attr_native_value = None

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
                        self._process_delivery_date(delivery_date)
            else:
                self._attr_extra_state_attributes = {}
                self._attr_native_value = None
            return

        # Use the same processing logic as initial state
        self._handle_initial_state(self.coordinator.data[key])
        
        # Log debug information for certain sensors
        if self._sensor_type == SENSOR_UTILIZATION:
            LOGGER.debug("Setting utilization state to: %s", self._attr_native_value)
        elif self._sensor_type == SENSOR_HIGHEST_ACCEPTED:
            LOGGER.debug("Setting highest accepted bid value to: %s", self._attr_native_value)
        elif self._sensor_type == SENSOR_VOLUME:
            LOGGER.debug("Setting volume value to: %s", self._attr_native_value)
        elif self._sensor_type == SENSOR_PRICE:
            LOGGER.debug("Setting daily average price to: %s", self._attr_native_value)
            if hasattr(self, '_attr_extra_state_attributes'):
                attrs = self._attr_extra_state_attributes
                if 'price_count' in attrs:
                    LOGGER.debug("Daily price range: %s - %s (average from %d prices)",
                                attrs.get('min_price'),
                                attrs.get('max_price'),
                                attrs['price_count'])
        
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._sensor_type in self.coordinator.data
        )