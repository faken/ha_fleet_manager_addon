#!/bin/bash
# Install HA Fleet Integration to Home Assistant

set -e

echo "🚀 HA Fleet Integration Installer"
echo "=================================="
echo ""

# Detect HA config path
if [ -d "/config" ]; then
    HA_CONFIG="/config"
elif [ -d "$HOME/.homeassistant" ]; then
    HA_CONFIG="$HOME/.homeassistant"
elif [ -n "$1" ]; then
    HA_CONFIG="$1"
else
    echo "❌ Error: Cannot find Home Assistant config directory"
    echo ""
    echo "Usage: $0 [/path/to/ha/config]"
    echo ""
    echo "Examples:"
    echo "  $0 /config              # HA OS"
    echo "  $0 ~/.homeassistant     # HA Core"
    echo ""
    exit 1
fi

echo "📂 HA Config: $HA_CONFIG"
echo ""

# Create custom_components directory
CUSTOM_DIR="$HA_CONFIG/custom_components/ha_fleet"
echo "📦 Creating $CUSTOM_DIR..."
mkdir -p "$CUSTOM_DIR"

# Copy files
echo "📋 Copying integration files..."
cp __init__.py "$CUSTOM_DIR/"
cp sensor.py "$CUSTOM_DIR/"
cp config_flow.py "$CUSTOM_DIR/"
cp manifest.json "$CUSTOM_DIR/"
cp services.yaml "$CUSTOM_DIR/"
cp strings.json "$CUSTOM_DIR/"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Restart Home Assistant"
echo "2. Go to Settings → Devices & Services"
echo "3. Click 'Add Integration'"
echo "4. Search for 'HA Fleet Agent'"
echo "5. Enter your Fleet Cloud URL and API Key"
echo ""
echo "The integration will provide:"
echo "  - Service: ha_fleet.get_logs"
echo "  - Sensor: sensor.ha_fleet_log_tail"
echo ""
echo "No manual YAML configuration needed! 🎉"
