#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Checking for old processes..."
"$SCRIPT_DIR/stop.sh"

echo "Checking darts cameras..."
if ! "$SCRIPT_DIR/scripts/check_cameras.sh"; then
    echo ""
    echo "⚠️  Camera check failed — not all 3 darts cameras are connected."
    if [ -t 0 ]; then
        read -r -p "Would you like to continue and start in Demo Mode? [y/N] " ans
        if [[ "$ans" =~ ^[Yy]$ ]]; then
            echo "Starting in Demo Mode..."
        else
            echo "Aborting startup."
            exit 1
        fi
    else
        echo "Non-interactive shell: continuing in Demo Mode..."
    fi
fi

echo "Starting Backend (FastAPI)..."
cd "$SCRIPT_DIR"
python3 src/server.py &
BACKEND_PID=$!

echo "Starting Frontend (Vite)..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "==========================================================="
echo "Darts Web App is running!"
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173 (Open this in your browser)"
echo "Press Ctrl+C to stop both."
echo "==========================================================="

cleanup() {
    echo "Stopping services..."
    "$SCRIPT_DIR/stop.sh"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Poll until either process exits (e.g. the in-app "Exit & stop server" button
# kills the backend), then tear down both so the frontend doesn't linger.
# (bash 3.2 on macOS has no `wait -n`, so poll with kill -0.)
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1
done
cleanup
