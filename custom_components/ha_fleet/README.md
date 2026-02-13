# HA Fleet Integration

Home Assistant custom integration for the HA Fleet monitoring system.

## Features

✅ **Automatic Log Access** - No manual YAML configuration needed!
- Service: `ha_fleet.get_logs` - On-demand log retrieval
- Sensor: `sensor.ha_fleet_log_tail` - Live log monitoring (updates every 5 min)

✅ **Zero Configuration** - Works out of the box after installation

✅ **Secure** - Only reads log files, no write access

## Installation

### Option 1: Manual Installation

1. **Copy to custom_components:**
   ```bash
   # On your Home Assistant machine:
   cd /config
   mkdir -p custom_components/ha_fleet
   
   # Copy these files:
   # - __init__.py
   # - sensor.py
   # - config_flow.py
   # - manifest.json
   # - services.yaml
   # - strings.json
   ```

2. **Restart Home Assistant**

3. **Add Integration:**
   - Go to Settings → Devices & Services
   - Click "Add Integration"
   - Search for "HA Fleet Agent"
   - Enter your Fleet Cloud URL and API Key

### Option 2: HACS (Coming Soon)

When published to HACS:
1. Open HACS
2. Search for "HA Fleet"
3. Install
4. Restart HA

## Usage

### Service: ha_fleet.get_logs

Call this service to retrieve logs on-demand:

```yaml
service: ha_fleet.get_logs
data:
  lines: 200  # Optional, default: 200
```

**Returns:**
```json
{
  "logs": "2024-02-12 20:00:00 INFO ...",
  "total_lines": 5000,
  "returned_lines": 200
}
```

### Sensor: sensor.ha_fleet_log_tail

The sensor automatically updates every 5 minutes and provides:
- **State:** Number of lines (e.g., "200 lines")
- **Attributes:**
  - `logs`: Full log text (last 200 lines)
  - `total_lines`: Total lines in log file
  - `returned_lines`: Lines returned
  - `log_file`: Path to log file

**Example Dashboard Card:**

```yaml
type: markdown
content: >
  ## HA Logs

  {{ state_attr('sensor.ha_fleet_log_tail', 'logs') }}
```

## Agent Integration

The Fleet Agent automatically detects and uses:
1. **Service** (preferred) - `ha_fleet.get_logs`
2. **Sensor** (fallback) - `sensor.ha_fleet_log_tail`

No manual configuration needed!

## Troubleshooting

### Logs show "error"

Check that `/config/home-assistant.log` exists and is readable.

### Service not found

1. Verify integration is installed in `custom_components/ha_fleet/`
2. Check HA logs for errors: `grep ha_fleet home-assistant.log`
3. Restart Home Assistant

### Sensor shows "unavailable"

Wait 5 minutes for first update, or restart Home Assistant.

## Development

To test locally:
```bash
# Copy to dev HA instance
cp -r agent/* /path/to/ha/custom_components/ha_fleet/

# Restart HA and check logs
tail -f /config/home-assistant.log | grep ha_fleet
```

## Security Note

This integration only **reads** the log file. It:
- ✅ Has read-only access to `/config/home-assistant.log`
- ✅ Does not modify any files
- ✅ Does not access the network
- ✅ Runs within Home Assistant's sandbox

## Support

- GitHub: https://github.com/your-org/ha-fleet-agent
- Issues: https://github.com/your-org/ha-fleet-agent/issues
- Docs: https://docs.hafleet.io
