# HA Fleet Agent Integration

**Version:** 0.2.0

Home Assistant custom integration that collects comprehensive system metrics and sends them to your HA Fleet Management backend.

## Features

### Metrics Collected

**Core:**
- Home Assistant version
- Instance UUID

**Performance:**
- CPU usage (%)
- RAM usage (%, MB used/total)
- Disk usage (%, GB used/total)  
- System uptime

**Entities:**
- Total entities
- Unavailable entities (count & %)
- Automation count
- Integration count

**Security:** ✨ NEW in 0.2.0
- SSL/TLS enabled status
- Certificate expiry (days remaining)
- Certificate issuer
- Self-signed certificate detection

**Database:** ✨ NEW in 0.2.0
- Total database size (MB)
- Recorder table size
- Last purge date

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "HA Fleet Agent" and install
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration**
5. Search for "HA Fleet Agent"
6. Enter your backend details:
   - **Cloud URL:** `http://your-backend:8100`
   - **API Key:** Your Fleet Management API token
   - **Instance Name:** Optional friendly name

### Manual Installation

1. Copy `custom_components/ha_fleet` to your HA config directory
2. Restart Home Assistant
3. Configure via UI (see above)

## Configuration

The integration requires:
- **Backend URL:** Where your HA Fleet Management backend is running
- **API Token:** Generated from the backend user management
- **Instance Name:** Optional friendly name for this instance

Example:
```yaml
# Configured via UI - no YAML needed
Cloud URL: http://192.168.1.100:8100
API Key: hafleet_xxxxxxxxxxxxx
Instance Name: Living Room Pi
```

## How It Works

1. **Every 5 minutes**, the integration:
   - Collects all system metrics
   - Bundles them into a JSON payload
   - Sends to your backend via HTTPS/HTTP

2. **The backend:**
   - Calculates health score (0-100)
   - Stores metrics history
   - Triggers alerts if needed
   - Displays in dashboard

3. **You see:**
   - Real-time health scores
   - 7-day metric trends
   - Alerts for issues
   - Security & database insights

## Metrics Interval

Default: **5 minutes**

You can't currently change this via UI, but you can modify `METRICS_INTERVAL` in `__init__.py` if needed.

## Troubleshooting

### No metrics appearing in dashboard

1. Check HA logs for errors: **Settings → System → Logs**
2. Look for `ha_fleet` entries
3. Verify backend is reachable: `curl http://your-backend:8100/health`
4. Check API token is valid

### SSL certificate not detected

- Ensure `external_url` is configured in HA configuration
- Must be HTTPS (not HTTP)
- Certificate must be accessible from HA instance

### Database size shows "Not available"

- Recorder integration must be enabled
- Database file must be accessible
- Check logs for permission errors

## Support

- **Issues:** https://github.com/faken/ha_fleet_manager_addon/issues
- **Backend:** https://github.com/faken/ha_monitor
- **Docs:** https://github.com/faken/ha_monitor#readme

## Changelog

### 0.2.0 (2026-02-13)
- ✨ Complete metrics collection rewrite
- ✨ Security metrics (SSL certificate validation)
- ✨ Database metrics (size, purge tracking)
- ✨ Performance metrics (CPU, RAM, Disk)
- ✨ Entity statistics (unavailable tracking)
- ✅ Automatic 5-minute sync to backend
- ✅ Config flow UI support
- 🐛 Fixed metrics not being sent issue

### 0.1.1
- Initial release with basic log collection
