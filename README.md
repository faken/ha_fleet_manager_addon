# HA Fleet Manager Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/faken/ha_fleet_manager_addon.svg)](https://github.com/faken/ha_fleet_manager_addon/releases)

Home Assistant integration for **HA Fleet Manager** - centralized monitoring and management for multiple Home Assistant instances.

## Features

- ✅ **Automatic metrics collection** (CPU, RAM, Disk, Uptime)
- ✅ **Real-time monitoring** (sends metrics every 60 seconds)
- ✅ **Health score tracking** (backend calculates health based on metrics)
- ✅ **Log retrieval service** (fetch HA logs via service call)
- ✅ **Zero configuration** (uses psutil, works on all platforms)
- ✅ **Lightweight** (runs in background, minimal overhead)

## Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/faken/ha_fleet_manager_addon`
6. Category: "Integration"
7. Click "Add"
8. Search for "HA Fleet Manager" and install
9. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/ha_fleet` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

Add to your `configuration.yaml`:

```yaml
ha_fleet:
  api_url: "http://YOUR_FLEET_BACKEND:8100"
  api_token: "YOUR_API_TOKEN"
```

**Where to get these values:**

- `api_url`: The URL of your HA Fleet Manager backend (e.g., `http://192.168.1.100:8100`)
- `api_token`: Your API token from the Fleet Manager Dashboard
  - Login to Fleet Manager Dashboard
  - Go to Settings → API Tokens
  - Generate a new token for this instance

**Example:**

```yaml
ha_fleet:
  api_url: "http://192.168.1.100:8100"
  api_token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

After adding the configuration, restart Home Assistant.

## What Gets Collected

The integration automatically collects and sends:

- **System Metrics:**
  - CPU usage (%)
  - RAM usage (% and MB)
  - Disk usage (% and GB)
  - System boot time (for uptime calculation)
  
- **Home Assistant Info:**
  - Core version
  - Instance ID (UUID)
  - Total entities count
  - Unavailable entities count & percentage
  - Automation count
  - Integration count
  - Unavailable entity details (for troubleshooting)

Metrics are sent every **60 seconds** to your Fleet Manager backend.

## Services

### `ha_fleet.get_logs`

Retrieve recent Home Assistant log entries.

**Parameters:**
- `lines` (optional): Number of lines to retrieve (default: 200, max: 1000)

**Example:**

```yaml
service: ha_fleet.get_logs
data:
  lines: 500
```

## Monitoring

After installation and configuration, your Home Assistant instance will appear in the Fleet Manager Dashboard within 1-2 minutes.

You can monitor:
- Real-time CPU, RAM, Disk usage
- System uptime
- Health score trends
- Alerts and notifications
- Compare multiple instances

## Troubleshooting

**Instance not showing in dashboard:**
- Check Home Assistant logs for errors: `Settings → System → Logs`
- Verify `api_url` and `api_token` are correct
- Ensure backend is reachable from HA (test with `curl http://YOUR_BACKEND:8100/health`)
- Check firewall rules

**Metrics not updating:**
- Check HA logs: Look for "HA Fleet" entries
- Verify psutil is installed: `pip list | grep psutil` (should be automatic)
- Restart Home Assistant

**Enable debug logging:**

```yaml
logger:
  default: info
  logs:
    custom_components.ha_fleet: debug
```

## Version History

### 1.0.0 (2026-02-13)
- Initial release
- Automatic metrics collection
- System uptime tracking
- Log retrieval service
- HACS support

## Support

- **Issues:** https://github.com/faken/ha_fleet_manager_addon/issues
- **Backend:** https://github.com/faken/ha_monitor
- **Documentation:** https://github.com/faken/ha_fleet_manager_addon/wiki

## License

MIT License - See LICENSE file for details

## Credits

Developed for HA Fleet Manager - Centralized Home Assistant monitoring.
