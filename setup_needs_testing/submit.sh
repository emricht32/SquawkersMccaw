#!/bin/bash

# this should be copied to /var/www/cgi-bin
echo "Content-type: text/html"
echo ""

read POST_STRING

SSID=$(echo "$POST_STRING" | sed -n 's/.*ssid=\([^&]*\).*/\1/p' | sed 's/%20/ /g')
PASS=$(echo "$POST_STRING" | sed -n 's/.*password=\([^&]*\).*/\1/p' | sed 's/%20/ /g')

SSID=$(printf "%b" "${SSID//%/\\x}")
PASS=$(printf "%b" "${PASS//%/\\x}")

echo "<html><body><h1>Connecting to $SSID...</h1>"

if [[ -n "$SSID" && -n "$PASS" ]]; then
    echo "<p>Attempting to connect using NetworkManager...</p>"

    # Try to connect using nmcli
    nmcli dev wifi connect "$SSID" password "$PASS" ifname wlan0

    if [[ $? -eq 0 ]]; then
        echo "<p>Connected! Rebooting in 5 seconds...</p></body></html>"
        nohup bash -c "sleep 5 && reboot" >/dev/null 2>&1 &
    else
        echo "<p>Failed to connect. Please check your SSID/password.</p></body></html>"
    fi
else
    echo "<p>Error: SSID or password missing.</p></body></html>"
fi
