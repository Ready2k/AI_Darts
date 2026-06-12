#!/usr/bin/env bash
set -euo pipefail

kill_on_port() {
    local port=$1
    echo "Stopping process on port $port..."
    lsof -ti tcp:"$port" | xargs kill -9 2>/dev/null || true
}

kill_by_script() {
    local pattern=$1
    echo "Stopping $pattern..."
    pkill -9 -f "$pattern" 2>/dev/null || true
}

kill_on_port 8000   # FastAPI / uvicorn
kill_on_port 5173   # Vite dev server

kill_by_script "server.py"
kill_by_script "vite"

# Legacy scripts just in case
kill_by_script "detect.py"
kill_by_script "align.py"
kill_by_script "check_cameras.py"
kill_by_script "calibrate.py"
kill_by_script "menu.py"

echo "Done."
