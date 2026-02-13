"""HA Fleet Agent Integration - with Metrics Collection."""
import logging
import asyncio
import aiohttp
from datetime import datetime, timezone
import psutil

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ha_fleet"


async def async_setup(hass, config):
    """Set up the HA Fleet component."""
    _LOGGER.warning("🔵 HA Fleet integration loading...")
    
    # Get config
    conf = config.get(DOMAIN, {})
    api_url = conf.get("api_url")
    api_token = conf.get("api_token")
    
    if not api_url or not api_token:
        _LOGGER.error("❌ Missing api_url or api_token in configuration")
        return False
    
    # Get instance ID from HA
    try:
        from homeassistant.helpers import instance_id as instance_helper
        instance_id = await instance_helper.async_get(hass)
    except Exception as e:
        _LOGGER.error(f"Failed to get instance ID: {e}")
        instance_id = "unknown"
    
    _LOGGER.warning(f"🔧 HA Fleet configured: {api_url}, instance: {instance_id}")
    
    # Register get_logs service
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
    
    # Metrics collection task
    async def collect_and_send_metrics():
        """Collect system metrics and send to backend."""
        _LOGGER.info(f"🚀 HA Fleet metrics collection running (instance: {instance_id})")
        while True:
            try:
                # Collect metrics (non-blocking)
                psutil.cpu_percent(interval=0)  # First call to reset
                await asyncio.sleep(1)  # Wait 1 second (async)
                cpu_percent = psutil.cpu_percent(interval=0)  # Second call for accurate reading
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                boot_time = int(psutil.boot_time())  # System boot timestamp
                
                ha_version = hass.config.as_dict().get("version", "unknown")
                
                payload = {
                    "instance_id": instance_id,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    "metrics": {
                        "core_version": ha_version,
                        "cpu_usage_avg": round(cpu_percent, 2),
                        "ram_usage_percent": round(memory.percent, 2),
                        "ram_used_mb": round(memory.used / (1024 * 1024), 2),
                        "ram_total_mb": round(memory.total / (1024 * 1024), 2),
                        "disk_usage_percent": round(disk.percent, 2),
                        "disk_used_gb": round(disk.used / (1024 * 1024 * 1024), 2),
                        "disk_total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
                        "boot_time_seconds": boot_time
                    }
                }
                
                # Send to backend
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{api_url}/api/v1/metrics",
                        json=payload,
                        headers={"Authorization": f"Bearer {api_token}"},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            _LOGGER.info(f"✅ Metrics sent! CPU={cpu_percent}%, Health={result.get('health_score', 'N/A')}")
                        else:
                            text = await resp.text()
                            _LOGGER.warning(f"❌ Failed to send metrics: {resp.status} - {text}")
                
            except Exception as e:
                _LOGGER.error(f"Error collecting/sending metrics: {e}")
            
            # Wait 60 seconds
            await asyncio.sleep(60)
    
    # Start metrics collection in background (don't block setup)
    async def start_collection():
        """Start collection after a short delay."""
        _LOGGER.warning("⏰ HA Fleet waiting 10s before starting metrics...")
        await asyncio.sleep(10)  # Wait for HA to finish setup
        _LOGGER.warning("🚀 HA Fleet NOW starting metrics collection loop...")
        try:
            await collect_and_send_metrics()
        except Exception as e:
            _LOGGER.error(f"💥 Metrics collection crashed: {e}", exc_info=True)
    
    # Use async_create_task (newer HA method)
    hass.async_create_task(start_collection())
    _LOGGER.warning("✅ HA Fleet metrics collection task created!")
    
    return True
