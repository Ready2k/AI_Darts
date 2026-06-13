#!/usr/bin/env bash
#
# reactivate_cameras.sh — recover USB-C (UVC) cameras that macOS has gotten
# stuck. It frees any app holding the cameras, kicks the macOS camera
# assistants (which macOS relaunches automatically, clearing stuck sessions),
# then re-enumerates.
#
#   IMPORTANT: a genuinely dead cable / port can't be fixed in software. If the
#   "after" list below still shows only the MacBook camera, the problem is
#   physical — try a different USB-C cable/port or re-seat the hub.
#
# Usage:  ./reactivate_cameras.sh
#
set -uo pipefail

DARTS_CAM_MATCH='Cam|UVC|VendorID_3141|Autodarts'

list_cameras() {
  system_profiler SPCameraDataType 2>/dev/null \
    | grep -E 'Camera:|Model ID:' \
    | sed 's/^/    /'
  local n
  n=$(system_profiler SPCameraDataType 2>/dev/null | grep -c 'Model ID:')
  echo "    → ${n} camera(s) seen by macOS"
}

echo "==================================================================="
echo " Reactivate USB-C cameras"
echo "==================================================================="

echo
echo "BEFORE:"
list_cameras

echo
echo "1) Releasing apps that hold the cameras…"
if pgrep -f "server.py" >/dev/null 2>&1; then
  pkill -f "server.py" && echo "   • stopped darts backend (server.py)"
else
  echo "   • darts backend not running"
fi

echo
echo "2) Resetting macOS camera assistants (you'll be asked for your password)."
echo "   macOS relaunches these automatically — this just clears stuck sessions."
for proc in UVCAssistant VDCAssistant; do
  if pgrep -x "$proc" >/dev/null 2>&1; then
    if sudo killall "$proc" 2>/dev/null; then
      echo "   • reset $proc"
    else
      echo "   • could not reset $proc (may be SIP-protected — that's OK)"
    fi
  else
    echo "   • $proc not running"
  fi
done

echo
echo "3) Waiting for cameras to re-enumerate…"
sleep 4

echo
echo "AFTER:"
list_cameras

echo
echo "-------------------------------------------------------------------"
darts_cams=$(system_profiler SPCameraDataType 2>/dev/null | grep -icE "$DARTS_CAM_MATCH")
if [ "$darts_cams" -gt 0 ]; then
  echo "✅ External camera(s) detected. Restart the darts backend:"
  echo "     python3 server.py"
else
  echo "⚠️  Still only the built-in camera. This is a hardware/cable issue —"
  echo "    no software can bring back a camera macOS can't see. Try:"
  echo "      • a different USB-C cable (cables fail far more often than ports)"
  echo "      • a different USB-C port"
  echo "      • re-seating / re-powering the USB hub the cameras run through"
  echo "      • System Settings ▸ Privacy & Security ▸ Camera (permissions)"
fi
echo "-------------------------------------------------------------------"
