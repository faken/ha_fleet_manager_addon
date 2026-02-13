"""Config flow for HA Fleet Agent integration."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_fleet"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("cloud_url", default="http://localhost:8100"): cv.string,
        vol.Required("api_key"): cv.string,
        vol.Optional("instance_name", default="My Home"): cv.string,
    }
)


class HAFleetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Fleet Agent."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the input (basic check)
            try:
                # TODO: Test connection to cloud
                cloud_url = user_input["cloud_url"]
                api_key = user_input["api_key"]
                
                # For now, just accept it
                return self.async_create_entry(
                    title=user_input.get("instance_name", "HA Fleet"),
                    data=user_input,
                )
                
            except Exception as e:
                _LOGGER.error(f"Error setting up HA Fleet: {e}")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
