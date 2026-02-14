    async def _collect_performance(self) -> Dict[str, Any]:
        """Collect performance metrics (CPU, RAM, Disk) - same as HA System → Hardware."""
        metrics = {}
        
        # Try Supervisor API first (what HA shows in Settings → System → Hardware)
        if "hassio" in self.hass.config.components:
            try:
                # Get Core stats from Supervisor (shows HA container resources)
                supervisor_data = await self.hass.components.hassio.get_core_stats()
                
                if supervisor_data:
                    # CPU percent
                    cpu_percent = supervisor_data.get("cpu_percent", 0)
                    metrics["cpu_usage_avg"] = round(cpu_percent, 2)
                    
                    # Memory
                    memory_usage_mb = supervisor_data.get("memory_usage", 0) / (1024 * 1024)  # Bytes to MB
                    memory_limit_mb = supervisor_data.get("memory_limit", 0) / (1024 * 1024)
                    
                    if memory_limit_mb > 0:
                        memory_percent = (memory_usage_mb / memory_limit_mb) * 100
                        metrics["ram_usage_percent"] = round(memory_percent, 2)
                        metrics["ram_used_mb"] = round(memory_usage_mb, 2)
                        metrics["ram_total_mb"] = round(memory_limit_mb, 2)
                        _LOGGER.debug(f"Supervisor: {memory_percent:.1f}% of {memory_limit_mb:.0f}MB RAM")
                    
                    _LOGGER.debug(f"Using Supervisor API: CPU={cpu_percent}%, RAM={memory_percent:.1f}%")
                    
            except Exception as e:
                _LOGGER.warning(f"Supervisor API failed, falling back to psutil: {e}")
                metrics = {}  # Clear partial data
        
        # Fallback to psutil if Supervisor not available
        if not metrics:
            try:
                import psutil
                import asyncio
                from functools import partial
                
                _LOGGER.debug("Using psutil (Supervisor not available)")
                
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
                _LOGGER.error(f"Error collecting performance metrics with psutil: {e}")
        
        return metrics
