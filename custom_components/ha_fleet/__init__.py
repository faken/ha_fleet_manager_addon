"""HA Fleet Agent Integration."""
import logging
import asyncio
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .metrics_collector import MetricsCollector

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_fleet"
PLATFORMS = []  # No platforms needed - metrics sent directly

# Send metrics every 5 minutes
METRICS_INTERVAL = timedelta(minutes=5)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the HA Fleet component (legacy YAML config)."""
    _LOGGER.info("HA Fleet integration loading (legacy setup)...")
    
    # Register service for backwards compatibility
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Fleet from a config entry."""
    _LOGGER.info(f"Setting up HA Fleet integration: {entry.title}")
    
    # Store config
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "cloud_url": entry.data["cloud_url"],
        "api_key": entry.data["api_key"],
        "instance_name": entry.data.get("instance_name", "My Home"),
    }
    
    # Initialize metrics collector
    collector = MetricsCollector(hass)
    hass.data[DOMAIN][entry.entry_id]["collector"] = collector
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Start periodic metrics submission
    async def send_metrics(now=None):
        """Collect and send metrics to cloud."""
        try:
            await _send_metrics_to_cloud(hass, entry)
        except Exception as e:
            _LOGGER.error(f"Error sending metrics: {e}", exc_info=True)
    
    # Send immediately on startup
    hass.async_create_task(send_metrics())
    
    # Then send every 5 minutes
    hass.data[DOMAIN][entry.entry_id]["unsub"] = async_track_time_interval(
        hass, send_metrics, METRICS_INTERVAL
    )
    
    _LOGGER.info("HA Fleet metrics collection started (every 5min)")
    
    # Listen for config changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    _LOGGER.info(f"Reloading HA Fleet integration due to config change")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info(f"Unloading HA Fleet integration: {entry.title}")
    
    # Stop periodic updates
    if "unsub" in hass.data[DOMAIN][entry.entry_id]:
        hass.data[DOMAIN][entry.entry_id]["unsub"]()
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def _send_metrics_to_cloud(hass: HomeAssistant, entry: ConfigEntry):
    """Collect metrics and send to cloud backend."""
    config = hass.data[DOMAIN][entry.entry_id]
    collector = config["collector"]
    
    # Collect all metrics
    _LOGGER.debug("Collecting metrics...")
    metrics = await collector.collect_all()
    
    # Get instance ID (from HA's UUID)
    instance_id = hass.data.get("core.uuid")
    if not instance_id:
        _LOGGER.error("No instance UUID found - cannot send metrics")
        return
    
    # Prepare payload
    from datetime import datetime, timezone
    payload = {
        "instance_id": instance_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics
    }
    
    # Send to cloud
    cloud_url = config["cloud_url"].rstrip("/")
    api_key = config["api_key"]
    url = f"{cloud_url}/api/v1/metrics"
    
    _LOGGER.debug(f"Sending metrics to {url}")
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    health_score = data.get("health_score", "?")
                    _LOGGER.info(f"✅ Metrics sent successfully (Health: {health_score})")
                else:
                    error_text = await response.text()
                    _LOGGER.error(f"Failed to send metrics: {response.status} - {error_text}")
                    
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout sending metrics to cloud")
    except aiohttp.ClientError as e:
        _LOGGER.error(f"HTTP error sending metrics: {e}")
    except Exception as e:
        _LOGGER.error(f"Unexpected error sending metrics: {e}", exc_info=True)
