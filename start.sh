#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Checking for old processes..."
"$SCRIPT_DIR/stop.sh"

echo "Starting Backend (FastAPI)..."
cd "$SCRIPT_DIR"
python3 server.py &
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

wait $BACKEND_PID $FRONTEND_PID
