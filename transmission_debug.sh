#!/bin/bash

echo "=== Debugging Transmission Directly ==="

echo "1. Check Transmission web UI status:"
echo "Visit: http://localhost:9091 (user: transmission, pass: transmission)"

echo -e "\n2. Check Transmission logs:"
docker logs transmission --tail 20

echo -e "\n3. Test Transmission API directly:"
echo "Getting session info..."
curl -u transmission:transmission http://localhost:9091/transmission/rpc 2>/dev/null || echo "? Cannot connect"

echo -e "\n4. Get current torrents via API:"
# Get session ID first
SESSION_ID=$(curl -s -u transmission:transmission http://localhost:9091/transmission/rpc 2>/dev/null | grep -o 'X-Transmission-Session-Id: [^<]*' | cut -d' ' -f2)
echo "Session ID: $SESSION_ID"

if [ ! -z "$SESSION_ID" ]; then
    echo "Getting torrent list..."
    curl -s -u transmission:transmission \
         -H "X-Transmission-Session-Id: $SESSION_ID" \
         -H "Content-Type: application/json" \
         -d '{"method":"torrent-get","arguments":{"fields":["id","name","status","percentDone","downloadDir","rateDownload","rateUpload","error","errorString"]}}' \
         http://localhost:9091/transmission/rpc | jq '.' 2>/dev/null || echo "Raw response (no jq):"
fi

echo -e "\n5. Check if torrents are paused/stopped:"
echo "Visit Transmission web UI to see if torrents are paused"

echo -e "\n6. Check download directory permissions:"
echo "Host downloads directory:"
ls -la downloads/
echo -e "\nTransmission data directory:"
docker exec transmission ls -la /data/ 2>/dev/null || echo "? Cannot access transmission /data"

echo -e "\n7. Check Transmission settings:"
docker exec transmission cat /config/settings.json | grep -E "(download-dir|speed-limit|ratio-limit|idle-seeding)" 2>/dev/null || echo "? Cannot read settings"