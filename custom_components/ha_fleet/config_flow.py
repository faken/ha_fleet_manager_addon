"""Config flow for HA Fleet Agent integration."""
import logging
from typing import Any
import asyncio

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_fleet"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("cloud_url", default="http://localhost:8100"): cv.string,
        vol.Required("api_key"): cv.string,
        vol.Optional("instance_name"): cv.string,
    }
)


async def validate_connection(
    hass: HomeAssistant, cloud_url: str, api_key: str
) -> dict[str, Any]:
    """Validate the connection to the HA Fleet backend."""
    url = cloud_url.rstrip("/") + "/health"
    
    session = async_get_clientsession(hass)
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError(f"Backend returned status {response.status}")
            
            data = await response.json()
            if data.get("status") != "healthy":
                raise ValueError("Backend is not healthy")
            
            _LOGGER.info(f"Successfully connected to HA Fleet backend at {cloud_url}")
            return {"title": "HA Fleet Backend"}
            
    except asyncio.TimeoutError:
        _LOGGER.error(f"Timeout connecting to {cloud_url}")
        raise ValueError("Connection timeout")
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Connection error: {e}")
        raise ValueError(f"Cannot connect: {e}")
    except Exception as e:
        _LOGGER.error(f"Unexpected error: {e}")
        raise ValueError(f"Unknown error: {e}")


class HAFleetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Fleet Agent."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate connection to backend
                cloud_url = user_input["cloud_url"].rstrip("/")
                api_key = user_input["api_key"]
                
                # Test connection
                await validate_connection(self.hass, cloud_url, api_key)
                
                # Get instance name (default to HA's configured name)
                instance_name = user_input.get("instance_name")
                if not instance_name:
                    instance_name = self.hass.config.location_name or "Home Assistant"
                
                # Ensure only one instance
                await self.async_set_unique_id(self.hass.data.get("core.uuid"))
                self._abort_if_unique_id_configured()
                
                # Create entry
                return self.async_create_entry(
                    title=instance_name,
                    data={
                        "cloud_url": cloud_url,
                        "api_key": api_key,
                        "instance_name": instance_name,
                    },
                )
                
            except ValueError as e:
                _LOGGER.error(f"Validation error: {e}")
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error(f"Unexpected error during setup: {e}", exc_info=True)
                errors["base"] = "unknown"

        # Show form (initial or after error)
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "backend_url": "http://your-backend-server:8100",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return HAFleetOptionsFlowHandler(config_entry)


class HAFleetOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for HA Fleet Agent."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate new connection if URL or key changed
                cloud_url = user_input["cloud_url"].rstrip("/")
                api_key = user_input["api_key"]
                
                if (
                    cloud_url != self.config_entry.data["cloud_url"]
                    or api_key != self.config_entry.data["api_key"]
                ):
                    await validate_connection(self.hass, cloud_url, api_key)
                
                # Update config entry
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        "cloud_url": cloud_url,
                        "api_key": api_key,
                        "instance_name": user_input.get("instance_name", self.config_entry.data.get("instance_name")),
                    },
                )
                
                return self.async_create_entry(title="", data={})
                
            except ValueError as e:
                _LOGGER.error(f"Validation error: {e}")
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error(f"Unexpected error: {e}", exc_info=True)
                errors["base"] = "unknown"

        # Show form with current values
        options_schema = vol.Schema(
            {
                vol.Required(
                    "cloud_url",
                    default=self.config_entry.data.get("cloud_url", "http://localhost:8100"),
                ): cv.string,
                vol.Required(
                    "api_key",
                    default=self.config_entry.data.get("api_key", ""),
                ): cv.string,
                vol.Optional(
                    "instance_name",
                    default=self.config_entry.data.get("instance_name", ""),
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )
