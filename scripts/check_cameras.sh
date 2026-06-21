#!/usr/bin/env bash
# Verify the 3 USB darts cameras (Autodarts DIY Cam) are enumerated by macOS.
# Guides the user through reconnecting the hub/cameras and (last) an extension
# until all 3 are found. Exit 0 = all 3 present, exit 1 = gave up.

CAM_NAME="Autodarts DIY Cam"
NEED=3

count_cams() {
    system_profiler SPCameraDataType 2>/dev/null | grep -c "$CAM_NAME"
}

prompt() {
    # $1 = message. Waits for Enter (or 'q' to quit). Skips waiting if non-interactive.
    if [ -t 0 ]; then
        read -r -p "$1 [Enter to retest, q to quit] " ans
        [ "$ans" = "q" ] && return 1
    else
        echo "$1 (non-interactive: cannot prompt — aborting)"
        return 1
    fi
    return 0
}

echo "Checking for the $NEED darts cameras..."

# Step 0: initial check
n=$(count_cams)
if [ "$n" -eq "$NEED" ]; then
    echo "✅ All $NEED darts cameras detected."
    exit 0
fi
echo "⚠️  Found $n of $NEED darts cameras."

# Step 1: connect the hub / cameras directly (no extension)
echo ""
echo "Step 1 — Connect the camera hub (or cameras) DIRECTLY to the Mac, no extension cable."
while true; do
    prompt "Plug in the hub/cameras directly, then retest." || { echo "Aborted."; exit 1; }
    n=$(count_cams)
    if [ "$n" -eq "$NEED" ]; then
        echo "✅ All $NEED darts cameras detected (direct connection)."
        echo ""
        echo "Step 2 (optional) — If you need more reach, you can now try the extension."
        if prompt "Add the extension cable now if you want, then retest (or quit to keep direct)."; then
            n=$(count_cams)
            if [ "$n" -eq "$NEED" ]; then
                echo "✅ All $NEED cameras still detected through the extension. Good to go."
                exit 0
            fi
            echo "⚠️  Only $n of $NEED detected through the extension."
            echo "   The extension is marginal — use an ACTIVE/POWERED extension, or run without it."
            echo "   Remove the extension to continue with the working direct connection."
            while true; do
                prompt "Remove the extension and retest." || { echo "Aborted."; exit 1; }
                n=$(count_cams)
                if [ "$n" -eq "$NEED" ]; then
                    echo "✅ All $NEED cameras detected. Good to go."
                    exit 0
                fi
                echo "⚠️  Found $n of $NEED. Reseat the hub/cameras."
            done
        fi
        # User chose to keep direct connection
        exit 0
    fi
    echo "⚠️  Found $n of $NEED. Reseat the hub and each camera, check power, then retest."
done
