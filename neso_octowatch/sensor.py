"""Platform for sensor integration."""
from homeassistant.const import (
    DEVICE_CLASS_POWER,
    POWER_WATT,
)
from homeassistant.helpers.entity import Entity

import json
import os
from pathlib import Path

# Add state file path for Home Assistant
STATES_PATH = Path("/data/neso_octowatch/states.json")

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    add_entities([NesoOctowatchSensor('Octopus Neso Status', 'octopus_neso_status'),
                  NesoOctowatchSensor('Octopus Neso Utilization', 'octopus_neso_utilization'),
                  NesoOctowatchSensor('Octopus Neso Highest Accepted', 'octopus_neso_highest_accepted')])

class NesoOctowatchSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, name, state_key):
        """Initialize the sensor."""
        self._name = name
        self._state_key = state_key
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            with open(STATES_PATH, 'r') as f:
                data = json.load(f)
                self._state = data[self._state_key]['state']
                self._attributes = data[self._state_key]['attributes']
        except Exception as e:
            self._state = "unavailable"
            self._attributes = {"error": str(e)}