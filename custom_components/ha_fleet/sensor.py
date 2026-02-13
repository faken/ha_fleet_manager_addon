"""HA Fleet Sensor Platform."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HA Fleet sensors."""
    _LOGGER.info("HA Fleet sensor platform loaded (no sensors configured)")
    
    # No sensors needed - metrics are collected and sent via __init__.py
    # This platform is kept for future diagnostic sensors if needed
    pass
