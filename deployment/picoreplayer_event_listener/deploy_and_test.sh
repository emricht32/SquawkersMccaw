#!/bin/sh
# deploy_and_test.sh
# Deploy lmseventtrigger.json and test the full pipeline on piCorePlayer
#
# Usage: ./deploy_and_test.sh [user@]hostname

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 [user@]hostname"
    echo "Example: $0 tc@birdpi-main.local"
    exit 1
fi

TARGET_HOST="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying LMS Event Trigger Config to $TARGET_HOST ==="
echo ""

# Step 1: Copy lmseventtrigger.json to /etc/
echo "Step 1: Copying lmseventtrigger.json to /etc/..."
scp "$SCRIPT_DIR/lmseventtrigger.json" "$TARGET_HOST:/tmp/"
ssh "$TARGET_HOST" "sudo mv /tmp/lmseventtrigger.json /etc/lmseventtrigger.json && sudo chmod 644 /etc/lmseventtrigger.json"
echo "✓ Config deployed"
echo ""

# Step 2: Verify config exists and is readable
echo "Step 2: Verifying config..."
ssh "$TARGET_HOST" "ls -la /etc/lmseventtrigger.json"
echo ""

# Step 3: Validate JSON on remote
echo "Step 3: Validating JSON syntax on remote..."
ssh "$TARGET_HOST" "python3 -c 'import json; json.load(open(\"/etc/lmseventtrigger.json\"))' && echo '✓ JSON is valid' || echo '✗ JSON syntax error'"
echo ""

# Step 4: Check if event_listener.py exists at target path
echo "Step 4: Checking event_listener.py at target location..."
ssh "$TARGET_HOST" "ls -la /mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener/event_listener.py" || echo "⚠ event_listener.py not found - did you run setup script?"
echo ""

# Step 5: Restart LMS
echo "Step 5: Restarting Logitech Media Server..."
ssh "$TARGET_HOST" "sudo systemctl restart squeezeboxserver || sudo /etc/init.d/squeezeboxserver restart"
echo "Waiting 10 seconds for LMS to start..."
sleep 10
echo ""

# Step 6: Check LMS status
echo "Step 6: Checking LMS status..."
ssh "$TARGET_HOST" "systemctl status squeezeboxserver --no-pager || /etc/init.d/squeezeboxserver status" || true
echo ""

# Step 7: Test plugin commands
echo "Step 7: Testing LMS Event Trigger plugin..."
echo "  Enable:"
curl -s "http://${TARGET_HOST#*@}:9000/plugins/LMSeventTrigger/js.html?cmd=enable" && echo " ✓" || echo " ✗"
echo "  Reload config:"
curl -s "http://${TARGET_HOST#*@}:9000/plugins/LMSeventTrigger/js.html?cmd=reloadConfig" && echo " ✓" || echo " ✗"
echo ""

# Step 8: Manual test
echo "Step 8: Running manual test of event_listener.py..."
ssh "$TARGET_HOST" "cd /mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener && ./event_listener.py SONG_START test_song" || echo "(Expected to fail if config incomplete)"
echo ""

# Step 9: Check logs
echo "Step 9: Checking event listener log..."
ssh "$TARGET_HOST" "tail -20 /mnt/mmcblk0p2/tc/birdpi-logs/event_listener.log" || echo "No logs yet"
echo ""

echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Play a song on your LMS player"
echo "2. Watch logs: ssh $TARGET_HOST 'tail -f /mnt/mmcblk0p2/tc/birdpi-logs/event_listener.log'"
echo "3. Check LMS server logs: ssh $TARGET_HOST 'journalctl -u squeezeboxserver -f'"
