# DARTS.AI

A Pro Vision System for automatically scoring darts. 

This project uses a 3-camera computer-vision system to detect darts on a dartboard, complete with full X01 game logic, checkout suggestions, live stats, and a cinematic React-based UI.

## Features

- **Multi-Camera Computer Vision**: Uses USB cameras to automatically detect where a dart lands on the board.
- **X01 Game Logic**: Tracks game state for 301, 501, 701 with double-in, double-out and legs/sets options.
- **Player Stats**: Tracks live 3-dart averages and match history.
- **Web UI**: Modern, glass-morphism dashboard built with React and Vite, featuring live streams of the cameras for easy alignment and tracking.

## Getting Started

### Prerequisites
- Python 3
- Node.js & npm

### Running Locally

Use the included shell script to start both the Python backend and Vite frontend:

```bash
./start.sh
```

- Backend API: `http://localhost:8000`
- Frontend UI: `http://localhost:5173`

To stop the services, you can press `Ctrl+C` or use `./stop.sh`.

## Architecture
- **Backend**: Python-based FastAPI server managing the game engine and OpenCV image processing.
- **Frontend**: React and Vite single-page application.
