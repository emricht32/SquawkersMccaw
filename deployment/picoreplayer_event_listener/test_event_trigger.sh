#!/bin/sh
# test_event_trigger.sh
# Manual testing script for piCorePlayer LMS Event Trigger integration
#
# Usage: ./test_event_trigger.sh [local|remote]

set -e

MODE="${1:-local}"

echo "=== LMS Event Trigger Test Suite ==="
echo "Mode: $MODE"
echo ""

# -------------------------------------------------------------------
# Test 1: Validate JSON syntax
# -------------------------------------------------------------------
echo "Test 1: Validating lmseventtrigger.json syntax..."
if command -v python3 >/dev/null 2>&1; then
    python3 -c "import json; json.load(open('lmseventtrigger.json'))" && echo "✓ JSON is valid" || echo "✗ JSON syntax error"
elif command -v jq >/dev/null 2>&1; then
    jq empty lmseventtrigger.json && echo "✓ JSON is valid" || echo "✗ JSON syntax error"
else
    echo "⚠ Cannot validate JSON (no python3 or jq found)"
fi
echo ""

# -------------------------------------------------------------------
# Test 2: Check event_listener.py exists and is executable
# -------------------------------------------------------------------
echo "Test 2: Checking event_listener.py..."
if [ -f "event_listener.py" ]; then
    echo "✓ event_listener.py exists"
    if [ -x "event_listener.py" ]; then
        echo "✓ event_listener.py is executable"
    else
        echo "✗ event_listener.py is NOT executable (run: chmod +x event_listener.py)"
    fi
else
    echo "✗ event_listener.py not found"
fi
echo ""

# -------------------------------------------------------------------
# Test 3: Check bird.py exists
# -------------------------------------------------------------------
echo "Test 3: Checking bird.py..."
if [ -f "bird.py" ]; then
    echo "✓ bird.py exists"
else
    echo "✗ bird.py not found (run setup script to deploy)"
fi
echo ""

# -------------------------------------------------------------------
# Test 4: Manual invocation test
# -------------------------------------------------------------------
echo "Test 4: Testing event_listener.py invocation..."
if [ -f "event_listener.py" ] && [ -x "event_listener.py" ]; then
    echo "Running: ./event_listener.py SONG_START test_song"
    ./event_listener.py SONG_START test_song 2>&1 || echo "(Expected to fail if config/utils missing)"
else
    echo "⚠ Skipping (not executable)"
fi
echo ""

# -------------------------------------------------------------------
# Test 5: Check LMS Event Trigger plugin status (remote only)
# -------------------------------------------------------------------
if [ "$MODE" = "remote" ]; then
    echo "Test 5: Checking LMS Event Trigger plugin..."
    echo "Attempting to query LMS at birdpi-main:9000..."
    
    # Test enable
    echo "  Testing cmd=enable..."
    curl -s "http://birdpi-main:9000/plugins/LMSeventTrigger/js.html?cmd=enable" && echo "✓ Enable successful" || echo "✗ Enable failed"
    
    # Test reload
    echo "  Testing cmd=reloadConfig..."
    curl -s "http://birdpi-main:9000/plugins/LMSeventTrigger/js.html?cmd=reloadConfig" && echo "✓ Reload successful" || echo "✗ Reload failed"
    
    echo ""
fi

# -------------------------------------------------------------------
# Summary and recommendations
# -------------------------------------------------------------------
echo "=== Troubleshooting Checklist ==="
echo "On piCorePlayer device:"
echo "1. Verify /etc/lmseventtrigger.json exists and is readable by squeezeboxserver"
echo "   ls -la /etc/lmseventtrigger.json"
echo ""
echo "2. Verify event_listener.py path is correct and executable"
echo "   ls -la /mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener/event_listener.py"
echo ""
echo "3. Check LMS server logs for errors"
echo "   journalctl -u squeezeboxserver -f"
echo "   (or check /var/log/squeezeboxserver/server.log)"
echo ""
echo "4. Test manual execution"
echo "   cd /mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener"
echo "   ./event_listener.py SONG_START test_song"
echo ""
echo "5. Check event listener logs"
echo "   tail -f /mnt/mmcblk0p2/tc/birdpi-logs/event_listener.log"
echo ""
echo "6. Restart Logitech Media Server"
echo "   sudo systemctl restart squeezeboxserver"
echo ""
echo "7. Common reloadConfig failure causes:"
echo "   - JSON syntax errors (missing comma, trailing comma)"
echo "   - File permissions (config must be readable by LMS user)"
echo "   - Invalid event syntax in config"
echo "   - Plugin not fully enabled"
