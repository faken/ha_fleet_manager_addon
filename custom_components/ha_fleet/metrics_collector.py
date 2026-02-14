"""Metrics collector for HA Fleet Integration."""
import logging
import ssl
import socket
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)


class MetricsCollector:
    """Collects all metrics from Home Assistant instance."""
    
    def __init__(self, hass):
        """Initialize metrics collector."""
        self.hass = hass
    
    async def collect_all(self) -> Dict[str, Any]:
        """Collect all metrics and return as dict."""
        metrics = {}
        
        # Core metrics
        try:
            metrics.update(self._collect_core())
        except Exception as e:
            _LOGGER.warning(f"Failed to collect core metrics: {e}")
        
        # Performance metrics
        try:
            metrics.update(await self._collect_performance())
        except Exception as e:
            _LOGGER.warning(f"Failed to collect performance metrics: {e}")
        
        # Entity metrics
        try:
            metrics.update(self._collect_entities())
        except Exception as e:
            _LOGGER.warning(f"Failed to collect entity metrics: {e}")
        
        # Security metrics
        try:
            metrics.update(await self._collect_security())
        except Exception as e:
            _LOGGER.warning(f"Failed to collect security metrics: {e}")
        
        # Database metrics
        try:
            metrics.update(await self._collect_database())
        except Exception as e:
            _LOGGER.warning(f"Failed to collect database metrics: {e}")
        
        # Backup metrics
        try:
            metrics.update(await self._collect_backups())
        except Exception as e:
            _LOGGER.warning(f"Failed to collect backup metrics: {e}")
        
        return metrics
    
    def _collect_core(self) -> Dict[str, Any]:
        """Collect core version information and system information."""
        from homeassistant.const import __version__ as ha_version
        import platform
        import os
        
        metrics = {
            "core_version": ha_version,
            "config_dir": self.hass.config.config_dir,
        }
        
        # Collect system/hardware information
        try:
            # Platform information
            metrics["system_platform"] = platform.system()  # Linux, Darwin, Windows
            metrics["system_machine"] = platform.machine()  # x86_64, aarch64, armv7l, etc.
            metrics["system_processor"] = platform.processor() or platform.machine()
            
            # Try to get more detailed CPU info from /proc/cpuinfo (Linux only)
            if platform.system() == "Linux":
                try:
                    with open("/proc/cpuinfo", "r") as f:
                        cpuinfo = f.read()
                        
                    # Extract model name
                    for line in cpuinfo.split("\n"):
                        if "model name" in line.lower():
                            cpu_model = line.split(":")[1].strip()
                            metrics["cpu_model"] = cpu_model
                            break
                        elif "hardware" in line.lower():  # ARM devices
                            hardware = line.split(":")[1].strip()
                            metrics["cpu_model"] = hardware
                            break
                except:
                    pass  # Fallback to platform.processor()
            
            # If no cpu_model found, use processor or machine
            if "cpu_model" not in metrics:
                metrics["cpu_model"] = metrics["system_processor"] or metrics["system_machine"]
            
            # Python version
            metrics["python_version"] = platform.python_version()
            
        except Exception as e:
            _LOGGER.warning(f"Failed to collect system information: {e}")
        
        return metrics
    
    async def _collect_performance(self) -> Dict[str, Any]:
        """Collect performance metrics (CPU, RAM, Disk)."""
        metrics = {}
        
        try:
            import psutil
            import asyncio
            from functools import partial
            
            # CPU
            loop = asyncio.get_event_loop()
            cpu_percent = await loop.run_in_executor(
                None, partial(psutil.cpu_percent, interval=1)
            )
            metrics["cpu_usage_avg"] = round(cpu_percent, 2)
            
            # RAM
            memory = psutil.virtual_memory()
            metrics["ram_usage_percent"] = round(memory.percent, 2)
            metrics["ram_used_mb"] = round(memory.used / (1024 * 1024), 2)
            metrics["ram_total_mb"] = round(memory.total / (1024 * 1024), 2)
            
            # Disk
            disk = psutil.disk_usage(self.hass.config.config_dir)
            metrics["disk_usage_percent"] = round(disk.percent, 2)
            metrics["disk_used_gb"] = round(disk.used / (1024 ** 3), 2)
            metrics["disk_total_gb"] = round(disk.total / (1024 ** 3), 2)
            
            # Boot time (Unix timestamp when system booted)
            boot_time = psutil.boot_time()
            # Send absolute boot timestamp, not duration
            metrics["boot_time_seconds"] = int(boot_time)
            
        except ImportError:
            _LOGGER.warning("psutil not available - performance metrics disabled")
        except Exception as e:
            _LOGGER.error(f"Error collecting performance metrics: {e}")
        
        return metrics
    
    def _collect_entities(self) -> Dict[str, Any]:
        """Collect entity statistics and unavailable entity details."""
        from homeassistant.helpers import entity_registry as er
        
        states = self.hass.states.async_all()
        
        total = len(states)
        
        # Sanity check: if entity count is suspiciously low, HA might still be loading
        # Log warning but still report the data (backend can decide what to do)
        if total < 1000:
            _LOGGER.warning(
                f"Entity count ({total}) is suspiciously low - "
                f"HA might still be loading integrations"
            )
        
        unavailable_states = [s for s in states if s.state in ("unavailable", "unknown")]
        unavailable = len(unavailable_states)
        unavailable_percent = (unavailable / total * 100) if total > 0 else 0
        
        # Get entity registry to lookup platforms
        entity_registry = er.async_get(self.hass)
        
        # Collect detailed information about unavailable entities
        unavailable_details = []
        for state in unavailable_states:
            # Get integration/platform from entity registry (most reliable)
            platform = "unknown"
            
            # Try entity registry first (most accurate)
            entity_entry = entity_registry.async_get(state.entity_id)
            if entity_entry and entity_entry.platform:
                platform = entity_entry.platform
            # Fallback to attributes
            elif hasattr(state, 'attributes'):
                if 'integration' in state.attributes:
                    platform = state.attributes['integration']
                elif 'platform' in state.attributes:
                    platform = state.attributes['platform']
            
            # Get friendly name
            friendly_name = state.attributes.get('friendly_name', state.entity_id) if hasattr(state, 'attributes') else state.entity_id
            
            # Calculate how long entity has been unavailable
            duration_seconds = 0
            if state.last_changed:
                try:
                    now = datetime.now(timezone.utc)
                    # Ensure last_changed is timezone-aware
                    if state.last_changed.tzinfo is None:
                        last_changed = state.last_changed.replace(tzinfo=timezone.utc)
                    else:
                        last_changed = state.last_changed
                    
                    duration = now - last_changed
                    duration_seconds = int(duration.total_seconds())
                except Exception as e:
                    _LOGGER.debug(f"Failed to calculate duration for {state.entity_id}: {e}")
            
            unavailable_details.append({
                "entity_id": state.entity_id,
                "friendly_name": friendly_name,
                "domain": state.domain,
                "platform": platform,
                "state": state.state,
                "last_changed": state.last_changed.isoformat() if state.last_changed else None,
                "duration_seconds": duration_seconds
            })
        
        # Count by domain
        automations = len([s for s in states if s.domain == "automation"])
        
        # Count unique integrations (platforms)
        integrations = set()
        for state in states:
            if hasattr(state, 'attributes') and 'integration' in state.attributes:
                integrations.add(state.attributes['integration'])
        
        metrics = {
            "total_entities": total,
            "unavailable_entities": unavailable,
            "unavailable_entities_percent": round(unavailable_percent, 2),
            "automation_count": automations,
            "integration_count": len(integrations),
        }
        
        # Store unavailable_details separately (will be added to payload root by __init__.py)
        if unavailable_details:
            metrics["_unavailable_entity_details"] = unavailable_details
            _LOGGER.info(f"Collected {len(unavailable_details)} unavailable entity details")
        
        return metrics
    
    async def _collect_security(self) -> Dict[str, Any]:
        """Collect security metrics (SSL certificate info)."""
        metrics = {
            "ssl_enabled": False,
            "ssl_cert_expiry_days": None,
            "ssl_issuer": None,
            "ssl_self_signed": None,
        }
        
        # Get external URL
        external_url = self.hass.config.external_url
        if not external_url:
            return metrics
        
        parsed = urlparse(str(external_url))
        if parsed.scheme != "https":
            return metrics
        
        metrics["ssl_enabled"] = True
        
        # Check SSL certificate
        hostname = parsed.hostname
        port = parsed.port or 443
        
        try:
            # Create SSL context that allows self-signed
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Connect and get certificate
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
            
            # Parse issuer
            issuer = dict(x[0] for x in cert.get("issuer", []))
            issuer_cn = issuer.get("commonName", "Unknown")
            issuer_o = issuer.get("organizationName", "")
            metrics["ssl_issuer"] = f"{issuer_o} ({issuer_cn})" if issuer_o else issuer_cn
            
            # Parse subject (for self-signed check)
            subject = dict(x[0] for x in cert.get("subject", []))
            subject_cn = subject.get("commonName", "")
            
            # Check if self-signed
            metrics["ssl_self_signed"] = (issuer_cn == subject_cn)
            
            # Parse expiry
            expiry_str = cert.get("notAfter")
            if expiry_str:
                expiry_date = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                days_until_expiry = (expiry_date - datetime.now()).days
                metrics["ssl_cert_expiry_days"] = days_until_expiry
            
        except Exception as e:
            _LOGGER.debug(f"Failed to check SSL certificate: {e}")
        
        return metrics
    
    async def _collect_database(self) -> Dict[str, Any]:
        """Collect database metrics (size, purge status)."""
        metrics = {
            "db_size_mb": None,
            "recorder_size_mb": None,
            "db_growth_rate": None,
            "last_purge_date": None,
        }
        
        # Check if Recorder is enabled
        if "recorder" not in self.hass.config.components:
            return metrics
        
        # Get database file path
        db_path = self._get_db_path()
        if not db_path or not os.path.exists(db_path):
            return metrics
        
        try:
            # Get total file size
            size_bytes = os.path.getsize(db_path)
            size_mb = size_bytes / (1024 * 1024)
            metrics["db_size_mb"] = round(size_mb, 2)
            metrics["recorder_size_mb"] = round(size_mb, 2)  # Assume all is recorder
            
        except Exception as e:
            _LOGGER.warning(f"Failed to get database size: {e}")
        
        # Try to get last purge info from recorder
        try:
            recorder = self.hass.data.get("recorder")
            if recorder and hasattr(recorder, "last_purge_time"):
                last_purge = recorder.last_purge_time
                if last_purge:
                    metrics["last_purge_date"] = last_purge.isoformat()
        except Exception as e:
            _LOGGER.debug(f"Could not get last purge date: {e}")
        
        return metrics
    
    def _get_db_path(self) -> Optional[str]:
        """Get database file path."""
        try:
            recorder = self.hass.data.get("recorder")
            if recorder and hasattr(recorder, "db_url"):
                db_url = recorder.db_url
                
                # Parse SQLite URL
                if db_url and db_url.startswith("sqlite:///"):
                    db_path = db_url[10:]  # Remove sqlite:///
                    if not db_path.startswith("/"):
                        db_path = "/" + db_path
                    return db_path
        except Exception as e:
            _LOGGER.debug(f"Could not parse DB URL: {e}")
        
        # Fallback: default location
        config_dir = self.hass.config.config_dir
        default_db = os.path.join(config_dir, "home-assistant_v2.db")
        if os.path.exists(default_db):
            return default_db
        
        return None
    
    async def _collect_backups(self) -> Dict[str, Any]:
        """Collect backup information from Supervisor API."""
        import aiohttp
        
        metrics = {
            "backup_count": 0,
            "last_backup_date": None,
            "last_backup_age_days": None,
            "last_backup_age_hours": None,
            "total_backup_size_mb": 0,
            "oldest_backup_date": None,
        }
        
        # Check if Supervisor token is available
        supervisor_token = os.getenv("SUPERVISOR_TOKEN")
        if not supervisor_token:
            _LOGGER.debug("Supervisor token not available - skipping backup metrics")
            return metrics
        
        supervisor_url = "http://supervisor/backups"
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    "Authorization": f"Bearer {supervisor_token}",
                    "Content-Type": "application/json"
                }
                
                async with session.get(supervisor_url, headers=headers) as resp:
                    if resp.status != 200:
                        _LOGGER.debug(f"Supervisor backups endpoint returned {resp.status}")
                        return metrics
                    
                    data = await resp.json()
                    backups = data.get("data", {}).get("backups", [])
                    
                    if not backups:
                        _LOGGER.debug("No backups found")
                        return metrics
                    
                    # Count backups
                    metrics["backup_count"] = len(backups)
                    
                    # Sort by date (newest first)
                    sorted_backups = sorted(
                        backups,
                        key=lambda b: b.get("date", ""),
                        reverse=True
                    )
                    
                    # Get last backup info
                    if sorted_backups:
                        last_backup = sorted_backups[0]
                        last_date_str = last_backup.get("date")
                        
                        if last_date_str:
                            try:
                                # Parse ISO timestamp
                                last_date = datetime.fromisoformat(last_date_str.replace("Z", "+00:00"))
                                metrics["last_backup_date"] = last_date.isoformat()
                                
                                # Calculate age in hours and days
                                now = datetime.now(timezone.utc)
                                age_delta = now - last_date
                                metrics["last_backup_age_hours"] = round(age_delta.total_seconds() / 3600, 1)
                                metrics["last_backup_age_days"] = round(age_delta.total_seconds() / 86400, 1)
                                
                            except Exception as e:
                                _LOGGER.debug(f"Failed to parse backup date {last_date_str}: {e}")
                    
                    # Get oldest backup
                    if sorted_backups:
                        oldest_backup = sorted_backups[-1]
                        oldest_date_str = oldest_backup.get("date")
                        
                        if oldest_date_str:
                            try:
                                oldest_date = datetime.fromisoformat(oldest_date_str.replace("Z", "+00:00"))
                                metrics["oldest_backup_date"] = oldest_date.isoformat()
                            except Exception as e:
                                _LOGGER.debug(f"Failed to parse oldest backup date: {e}")
                    
                    # Calculate total size
                    total_size_bytes = sum(b.get("size", 0) for b in backups)
                    metrics["total_backup_size_mb"] = round(total_size_bytes / (1024 * 1024), 1)
                    
                    _LOGGER.debug(
                        f"Collected backup metrics: {metrics['backup_count']} backups, "
                        f"last: {metrics['last_backup_age_hours']}h ago, "
                        f"total size: {metrics['total_backup_size_mb']} MB"
                    )
                    
        except aiohttp.ClientError as e:
            _LOGGER.debug(f"Failed to fetch backups from Supervisor: {e}")
        except Exception as e:
            _LOGGER.warning(f"Unexpected error collecting backup metrics: {e}", exc_info=True)
        
        return metrics
