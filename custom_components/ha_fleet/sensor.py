"""HA Fleet Sensor Platform."""
import logging
from datetime import timedelta
from pathlib import Path

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HA Fleet sensors."""
    _LOGGER.info("Setting up HA Fleet sensors")
    
    # Add log tail sensor
    async_add_entities([HAFleetLogSensor(hass)], True)


class HAFleetLogSensor(SensorEntity):
    """Sensor that reads HA logs."""
    
    _attr_name = "HA Fleet Log Tail"
    _attr_unique_id = "ha_fleet_log_tail"
    _attr_icon = "mdi:text-box-multiple"
    
    def __init__(self, hass: HomeAssistant):
        """Initialize the sensor."""
        self.hass = hass
        self._state = None
        self._attributes = {}
    
    @property
    def state(self):
        """Return the sensor state (first line of logs)."""
        return self._state
    
    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        return self._attributes
    
    def update(self):
        """Fetch new state data for the sensor."""
        log_file = self.hass.config.path("home-assistant.log")
        
        try:
            # Read log file
            with open(log_file, "r") as f:
                all_lines = f.readlines()
            
            # Get last 200 lines
            recent_logs = all_lines[-200:] if len(all_lines) > 200 else all_lines
            logs_text = ''.join(recent_logs)
            
            # Store in attributes (state has 255 char limit)
            self._attributes = {
                "logs": logs_text,
                "total_lines": len(all_lines),
                "returned_lines": len(recent_logs),
                "log_file": str(log_file)
            }
            
            # State shows summary
            if recent_logs:
                self._state = f"{len(recent_logs)} lines"
            else:
                self._state = "empty"
            
            _LOGGER.debug(f"Updated log sensor: {len(recent_logs)} lines")
            
        except FileNotFoundError:
            _LOGGER.error(f"Log file not found: {log_file}")
            self._state = "error"
            self._attributes = {"error": "Log file not found"}
            
        except Exception as e:
            _LOGGER.error(f"Error reading logs: {e}", exc_info=True)
            self._state = "error"
            self._attributes = {"error": str(e)}
