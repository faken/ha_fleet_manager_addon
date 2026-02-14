#!/bin/bash
# Fix HA Fleet Integration - Clear Python cache and reload

echo "🔄 Clearing Python cache for ha_fleet integration..."

cd /config/custom_components/ha_fleet

# Remove all Python cache files
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
find . -name "*.pyo" -delete 2>/dev/null

echo "✅ Cache cleared"

echo "📥 Pulling latest code from GitHub..."
git pull origin main

echo "✅ Code updated"

echo ""
echo "🔄 Now restart Home Assistant:"
echo "   Settings → System → Restart"
echo ""
echo "Or via CLI:"
echo "   ha core restart"
