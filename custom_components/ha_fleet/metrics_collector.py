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
        """Collect entity statistics."""
        states = self.hass.states.async_all()
        
        total = len(states)
        
        # Sanity check: if entity count is suspiciously low, HA might still be loading
        # Log warning but still report the data (backend can decide what to do)
        if total < 1000:
            _LOGGER.warning(
                f"Entity count ({total}) is suspiciously low - "
                f"HA might still be loading integrations"
            )
        
        unavailable = len([s for s in states if s.state in ("unavailable", "unknown")])
        unavailable_percent = (unavailable / total * 100) if total > 0 else 0
        
        # Count by domain
        automations = len([s for s in states if s.domain == "automation"])
        
        # Count unique integrations (platforms)
        integrations = set()
        for state in states:
            if hasattr(state, 'attributes') and 'integration' in state.attributes:
                integrations.add(state.attributes['integration'])
        
        return {
            "total_entities": total,
            "unavailable_entities": unavailable,
            "unavailable_entities_percent": round(unavailable_percent, 2),
            "automation_count": automations,
            "integration_count": len(integrations),
        }
    
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
