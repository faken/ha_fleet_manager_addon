"""HA Fleet Agent Integration."""
import logging
import asyncio
from datetime import timedelta, datetime, timezone

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

# Poll for commands every 20 seconds (faster than frontend 30s timeout)
COMMAND_POLL_INTERVAL = timedelta(seconds=20)


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
    _LOGGER.info(f"🚀 Setting up HA Fleet integration: {entry.title}")
    
    cloud_url = entry.data["cloud_url"]
    api_key = entry.data["api_key"]
    instance_name = entry.data.get("instance_name", "My Home")
    
    # Test connection on setup
    _LOGGER.info(f"🔍 Testing connection to Fleet backend at {cloud_url}")
    import aiohttp
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {"Authorization": f"Bearer {api_key}"}
            async with session.get(f"{cloud_url}/health", headers=headers) as resp:
                if resp.status == 200:
                    _LOGGER.info(f"✅ Fleet backend connection successful!")
                else:
                    _LOGGER.warning(f"⚠️ Fleet backend returned status {resp.status}")
    except Exception as e:
        _LOGGER.warning(f"⚠️ Fleet backend connection test failed: {e} - Will retry on next heartbeat")
    
    # Store config
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "cloud_url": cloud_url,
        "api_key": api_key,
        "instance_name": instance_name,
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
            # Only send if HA is fully running (all integrations loaded)
            if hass.state.value != "RUNNING":
                _LOGGER.debug(f"HA not fully running yet (state: {hass.state.value}), skipping metrics")
                return
            
            await _send_metrics_to_cloud(hass, entry)
        except Exception as e:
            _LOGGER.error(f"Error sending metrics: {e}", exc_info=True)
    
    # Don't send immediately - wait for first interval (HA needs time to load all integrations)
    # This prevents sending incomplete entity counts (e.g. 68 instead of 2184)
    _LOGGER.info("HA Fleet will send first metrics in 5 minutes (waiting for all integrations to load)")
    
    # Send every 5 minutes
    hass.data[DOMAIN][entry.entry_id]["unsub"] = async_track_time_interval(
        hass, send_metrics, METRICS_INTERVAL
    )
    
    _LOGGER.info("HA Fleet metrics collection started (every 5min)")
    
    # Start command polling (every 60 seconds)
    async def poll_commands(now=None):
        """Poll cloud for pending commands and execute them."""
        try:
            await _poll_and_execute_commands(hass, entry)
        except Exception as e:
            _LOGGER.error(f"Error polling commands: {e}", exc_info=True)
    
    hass.data[DOMAIN][entry.entry_id]["unsub_commands"] = async_track_time_interval(
        hass, poll_commands, COMMAND_POLL_INTERVAL
    )
    
    _LOGGER.info("HA Fleet command polling started (every 20s)")
    
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
    
    # Stop command polling
    if "unsub_commands" in hass.data[DOMAIN][entry.entry_id]:
        hass.data[DOMAIN][entry.entry_id]["unsub_commands"]()
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def _poll_and_execute_commands(hass: HomeAssistant, entry: ConfigEntry):
    """Poll cloud for pending commands and execute them."""
    import os
    from datetime import datetime, timezone
    
    config = hass.data[DOMAIN][entry.entry_id]
    cloud_url = config["cloud_url"].rstrip("/")
    api_key = config["api_key"]
    
    # Get instance ID
    instance_id = hass.data.get("core.uuid")
    if not instance_id:
        _LOGGER.warning("No instance UUID found - cannot poll commands")
        return
    
    # Fetch pending commands
    url = f"{cloud_url}/api/v1/commands?instance_id={instance_id}"
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.debug(f"Command poll returned {response.status}")
                    return
                
                data = await response.json()
                commands = data.get("commands", [])
                
                if not commands:
                    _LOGGER.debug("No pending commands")
                    return
                
                _LOGGER.info(f"📋 Found {len(commands)} pending command(s)")
                
                # Execute each command
                for cmd in commands:
                    command_id = cmd.get("id")
                    command_type = cmd.get("command_type")
                    params = cmd.get("params", {})
                    
                    _LOGGER.info(f"⚙️ Executing command #{command_id}: {command_type}")
                    
                    # Execute command
                    result = await _execute_command(hass, command_type, params)
                    
                    # Log result
                    if result.get("success"):
                        _LOGGER.info(f"✅ Command #{command_id} completed: {result.get('message', 'Success')}")
                    else:
                        _LOGGER.error(f"❌ Command #{command_id} failed: {result.get('message', 'Unknown error')}")
                    
                    # Report result back to cloud
                    await _report_command_result(
                        session, cloud_url, api_key, instance_id,
                        command_id, result
                    )
                    
    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout polling for commands")
    except aiohttp.ClientError as e:
        _LOGGER.warning(f"HTTP error polling commands: {e}")
    except Exception as e:
        _LOGGER.error(f"Unexpected error polling commands: {e}", exc_info=True)


async def _execute_command(hass: HomeAssistant, command_type: str, params: dict) -> dict:
    """Execute a command locally and return result."""
    import os
    
    try:
        if command_type == "trigger_backup":
            # Execute backup via Supervisor API
            return await _execute_backup(hass, params)
        
        elif command_type == "get_backup_info":
            # Get info about a specific backup
            return await _get_backup_info(hass, params)
        
        elif command_type == "get_logs":
            # Get Home Assistant logs
            return await _get_logs(hass, params)
        
        elif command_type == "restart_homeassistant":
            # Restart HA Core
            await hass.services.async_call("homeassistant", "restart")
            return {
                "success": True,
                "message": "Home Assistant restarting..."
            }
        
        elif command_type == "list_automations":
            # List all automations
            return await _list_automations(hass, params)
        
        elif command_type == "update_core":
            # Update HA Core
            return await _execute_update(hass, params)
        
        else:
            _LOGGER.warning(f"Unknown command type: {command_type}")
            return {
                "success": False,
                "message": f"Unknown command type: {command_type}"
            }
            
    except Exception as e:
        _LOGGER.error(f"Command execution failed: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Execution error: {str(e)}"
        }


async def _execute_backup(hass: HomeAssistant, params: dict) -> dict:
    """Execute backup via Supervisor API."""
    import os
    from datetime import datetime
    
    supervisor_token = os.getenv("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return {
            "success": False,
            "message": "Supervisor not available (not running on HA OS/Supervised)"
        }
    
    backup_name = params.get("name", f"Fleet backup {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    supervisor_url = "http://supervisor/backups/new/full"
    payload = {"name": backup_name}
    
    if "password" in params:
        payload["password"] = params["password"]
    
    try:
        timeout = aiohttp.ClientTimeout(total=600)  # 10 minutes for backup
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "Authorization": f"Bearer {supervisor_token}",
                "Content-Type": "application/json"
            }
            
            _LOGGER.info(f"Creating backup: {backup_name}")
            
            async with session.post(supervisor_url, json=payload, headers=headers) as resp:
                if resp.status in [200, 201]:
                    data = await resp.json()
                    backup_slug = data.get("data", {}).get("slug", "unknown")
                    
                    _LOGGER.info(f"✅ Backup created successfully: {backup_slug}")
                    
                    return {
                        "success": True,
                        "message": f"Backup created: {backup_name}",
                        "slug": backup_slug,
                        "name": backup_name
                    }
                else:
                    error_text = await resp.text()
                    _LOGGER.error(f"Backup failed with status {resp.status}: {error_text}")
                    
                    return {
                        "success": False,
                        "message": f"Supervisor API error: {resp.status}"
                    }
                    
    except asyncio.TimeoutError:
        _LOGGER.error("Backup creation timed out after 10 minutes")
        return {
            "success": False,
            "message": "Backup creation timed out"
        }
    except Exception as e:
        _LOGGER.error(f"Backup error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Backup error: {str(e)}"
        }


async def _get_backup_info(hass: HomeAssistant, params: dict) -> dict:
    """Get info about a specific backup via Supervisor API."""
    import os
    
    supervisor_token = os.getenv("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return {
            "success": False,
            "message": "Supervisor not available"
        }
    
    slug = params.get("slug")
    if not slug:
        return {
            "success": False,
            "message": "Missing backup slug parameter"
        }
    
    supervisor_url = f"http://supervisor/backups/{slug}/info"
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "Authorization": f"Bearer {supervisor_token}",
                "Content-Type": "application/json"
            }
            
            async with session.get(supervisor_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    backup_data = data.get("data", {})
                    
                    return {
                        "success": True,
                        "message": "Backup info retrieved",
                        "data": backup_data
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Backup not found: {resp.status}"
                    }
                    
    except Exception as e:
        _LOGGER.error(f"Error getting backup info: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


async def _get_logs(hass: HomeAssistant, params: dict) -> dict:
    """Get Home Assistant logs via Supervisor API."""
    import os
    
    supervisor_token = os.getenv("SUPERVISOR_TOKEN")
    if not supervisor_token:
        # Fallback: Try to read log file directly (non-Supervisor installs)
        return await _get_logs_from_file(hass, params)
    
    # Use Supervisor API to get logs
    lines = params.get("lines", 1000)
    supervisor_url = f"http://supervisor/core/logs"
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "Authorization": f"Bearer {supervisor_token}",
                "Content-Type": "application/json"
            }
            
            async with session.get(supervisor_url, headers=headers) as resp:
                if resp.status == 200:
                    logs_text = await resp.text()
                    
                    # Split into lines and get last N
                    all_lines = logs_text.split('\n')
                    recent_logs = all_lines[-lines:] if len(all_lines) > lines else all_lines
                    logs_result = '\n'.join(recent_logs)
                    
                    return {
                        "success": True,
                        "message": f"Retrieved {len(recent_logs)} log lines",
                        "logs": logs_result,
                        "total_lines": len(all_lines),
                        "returned_lines": len(recent_logs)
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Supervisor API returned {resp.status}"
                    }
                    
    except Exception as e:
        _LOGGER.error(f"Error getting logs from Supervisor: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


async def _get_logs_from_file(hass: HomeAssistant, params: dict) -> dict:
    """Get logs from file (fallback for non-Supervisor installs)."""
    import os
    
    lines = params.get("lines", 1000)
    
    # Try multiple possible log locations
    possible_paths = [
        "/config/home-assistant.log",
        hass.config.path("home-assistant.log"),
        "/var/log/homeassistant/home-assistant.log",
        os.path.expanduser("~/.homeassistant/home-assistant.log")
    ]
    
    log_file = None
    for path in possible_paths:
        if os.path.exists(path):
            log_file = path
            break
    
    if not log_file:
        return {
            "success": False,
            "message": "Log file not found. Use Supervisor API on HA OS/Supervised."
        }
    
    try:
        # Use executor to avoid blocking the event loop
        def read_logs():
            with open(log_file, "r") as f:
                return f.readlines()
        
        all_lines = await hass.async_add_executor_job(read_logs)
        
        recent_logs = all_lines[-lines:] if len(all_lines) > lines else all_lines
        logs_text = ''.join(recent_logs)
        
        return {
            "success": True,
            "message": f"Retrieved {len(recent_logs)} log lines",
            "logs": logs_text,
            "total_lines": len(all_lines),
            "returned_lines": len(recent_logs)
        }
    except Exception as e:
        _LOGGER.error(f"Error reading logs from file: {e}")
        return {
            "success": False,
            "message": f"Error reading logs: {str(e)}"
        }


async def _list_automations(hass: HomeAssistant, params: dict) -> dict:
    """List all automations."""
    try:
        automations = []
        
        # Get all automation entities
        for entity_id in hass.states.async_entity_ids("automation"):
            state = hass.states.get(entity_id)
            if state:
                automations.append({
                    "entity_id": entity_id,
                    "name": state.attributes.get("friendly_name", entity_id),
                    "state": state.state,
                    "last_triggered": str(state.attributes.get("last_triggered", "Never"))
                })
        
        return {
            "success": True,
            "message": f"Found {len(automations)} automations",
            "automations": automations,
            "count": len(automations)
        }
    except Exception as e:
        _LOGGER.error(f"Error listing automations: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


async def _execute_update(hass: HomeAssistant, params: dict) -> dict:
    """Execute Home Assistant Core update via Supervisor API."""
    import os
    
    supervisor_token = os.getenv("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return {
            "success": False,
            "message": "Supervisor not available (not running on HA OS/Supervised)"
        }
    
    target_version = params.get("target_version")  # None = latest
    backup_before = params.get("backup_before", True)
    
    # Step 1: Create backup if requested
    if backup_before:
        _LOGGER.info("Creating backup before update...")
        backup_result = await _execute_backup(hass, {
            "name": f"Pre-update backup {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        })
        
        if not backup_result.get("success"):
            return {
                "success": False,
                "message": f"Backup failed: {backup_result.get('message')}"
            }
        
        _LOGGER.info(f"Pre-update backup created: {backup_result.get('slug')}")
    
    # Step 2: Trigger update
    supervisor_url = "http://supervisor/core/update"
    
    payload = {}
    if target_version:
        payload["version"] = target_version
    
    try:
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes for update
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "Authorization": f"Bearer {supervisor_token}",
                "Content-Type": "application/json"
            }
            
            _LOGGER.info(f"Starting HA Core update to {target_version or 'latest'}...")
            
            async with session.post(supervisor_url, json=payload, headers=headers) as resp:
                if resp.status in [200, 201]:
                    _LOGGER.info("✅ Update initiated successfully")
                    
                    return {
                        "success": True,
                        "message": f"Update initiated to {target_version or 'latest'}",
                        "target_version": target_version,
                        "backup_created": backup_before
                    }
                else:
                    error_text = await resp.text()
                    _LOGGER.error(f"Update failed with status {resp.status}: {error_text}")
                    
                    return {
                        "success": False,
                        "message": f"Supervisor API error: {resp.status}"
                    }
                    
    except asyncio.TimeoutError:
        _LOGGER.error("Update initiation timed out")
        return {
            "success": False,
            "message": "Update initiation timed out"
        }
    except Exception as e:
        _LOGGER.error(f"Update error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Update error: {str(e)}"
        }


async def _report_command_result(
    session: aiohttp.ClientSession,
    cloud_url: str,
    api_key: str,
    instance_id: str,
    command_id: int,
    result: dict
):
    """Report command execution result back to cloud."""
    from datetime import datetime, timezone
    
    url = f"{cloud_url}/api/v1/commands/{command_id}/result"
    
    status = "success" if result.get("success") else "failed"
    
    payload = {
        "instance_id": instance_id,
        "status": status,
        "result": result if result.get("success") else None,
        "error": result.get("message") if not result.get("success") else None
    }
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 200:
                _LOGGER.info(f"📤 Command #{command_id} result reported to cloud: {status}")
            else:
                error_text = await resp.text()
                _LOGGER.error(f"❌ Failed to report command #{command_id} result: {resp.status} - {error_text}")
                
    except Exception as e:
        _LOGGER.error(f"Error reporting command result: {e}")


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
                    instance_id = data.get("instance_id", "unknown")
                    _LOGGER.info(
                        f"✅ Metrics sent successfully! "
                        f"Health Score: {health_score} | "
                        f"Instance: {instance_id[:8]}... | "
                        f"Entities: {payload['metrics'].get('total_entities', '?')} | "
                        f"Version: {payload['metrics'].get('core_version', '?')}"
                    )
                elif response.status == 401:
                    error_text = await response.text()
                    _LOGGER.error(
                        f"❌ Authentication failed! Invalid API token. "
                        f"Please reconfigure the integration with a valid token. "
                        f"Error: {error_text}"
                    )
                else:
                    error_text = await response.text()
                    _LOGGER.error(f"❌ Failed to send metrics: {response.status} - {error_text}")
                    
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout sending metrics to cloud")
    except aiohttp.ClientError as e:
        _LOGGER.error(f"HTTP error sending metrics: {e}")
    except Exception as e:
        _LOGGER.error(f"Unexpected error sending metrics: {e}", exc_info=True)
