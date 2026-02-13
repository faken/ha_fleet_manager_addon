"""HA Fleet Agent Integration - Minimal Version."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_fleet"


async def async_setup(hass, config):
    """Set up the HA Fleet component."""
    _LOGGER.info("HA Fleet integration loading...")
    
    async def get_logs_service(call):
        """Service to get HA logs."""
        lines = call.data.get("lines", 200)
        log_file = hass.config.path("home-assistant.log")
        
        try:
            with open(log_file, "r") as f:
                all_lines = f.readlines()
            recent_logs = all_lines[-lines:] if len(all_lines) > lines else all_lines
            logs_text = ''.join(recent_logs)
            
            return {
                "logs": logs_text,
                "total_lines": len(all_lines),
                "returned_lines": len(recent_logs)
            }
        except Exception as e:
            _LOGGER.error(f"Error reading logs: {e}")
            return {"error": str(e), "logs": ""}
    
    hass.services.async_register(
        DOMAIN,
        "get_logs",
        get_logs_service,
        supports_response=True
    )
    
    _LOGGER.info("HA Fleet service 'get_logs' registered")
    
    return True
