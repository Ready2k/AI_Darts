# DARTS.AI

A pro-grade vision system for automatically scoring darts.

DARTS.AI uses a **3-camera computer-vision pipeline** to detect exactly where each dart lands on a real dartboard, drives a full multi-mode game engine, and presents it through a **cinematic, broadcast-style React UI** — complete with AI opponents, walk-on cards, live stats, and audio commentary. Detection can run on our own CV engine or be sourced from an Autodarts board.

---

## Features

### 🎯 Multi-camera computer-vision detection
- **Three USB cameras** fused into a single **canonical board space** (a 500×500 board image where every camera's pixels are mapped through a homography), so scoring is perspective-correct.
- **Line-based tip localisation** — each camera's dart is fit to a shaft line, warped into board space, and the intersection of all cameras' lines is the true tip. Because a flight sits ~10 cm off the board plane, false "flight-end" points scatter and are rejected, while the real tip is pinpoint.
- **Multi-dart tracker** with layered anti-phantom gates: cross-camera consensus, scene-settle, contamination (arm-in-frame) rejection, and full-camera-agreement confirmation. Darts thrown in quick succession are each scored independently.
- **Automatic board-clear detection** — recognises when you pull the darts and resets for the next visit, even through arm motion.
- **Live corrections**: undo a misread (`U`), click the on-screen board to re-score the last dart, recapture the background (`R`), or set the bull reference (`B`).
- **Confidence badges** and a **missing-dart review modal** surface low-certainty reads for quick confirmation.

### 🕹️ Game modes
A shared engine powers six modes, each with its own scoreboard and cinematic theme:

| Mode | Description |
|---|---|
| **X01** | 301 / 501 / 701. Check-in *straight / double / master*, double-out, legs & sets, bust handling, 3-dart averages, and a checkout solver that suggests a throwable finish (e.g. `T20 T20 DBull`). |
| **Cricket** | Open and close 20→15 + bull, score on opponents' open numbers. |
| **Around the Clock** | Race through 1→20 (and bull) in order. |
| **Shanghai** | Hit single/double/treble of the round's number; a "Shanghai" wins instantly. |
| **Count Up** | Pure points race over a set number of rounds. |
| **Killer** | Claim a number via a pre-game **spin-the-wheel**, arm yourself (Standard = 3 marks on your number, Hard = your double), then knock out rivals' lives. |

### 🤖 AI opponents
Play any mode against the computer at three skill levels, modelled with realistic Gaussian throw spread:

| Level | Spread (σ) | Behaviour |
|---|---|---|
| **Beginner** | 45 mm | Frequent misses into neighbouring beds |
| **Semi Pro** | 15 mm | Consistent 20s, occasional trebles |
| **Pro** | 6 mm | Hits trebles regularly, not flawlessly |

The AI picks mode-appropriate targets (checkout solver for X01, close-then-score for Cricket, treble-the-round for Shanghai, arm-then-attack for Killer, …).

### 🎬 Cinematic broadcast mode
- **Walk-on cards** and flanking **caricature art** for every player.
- Themed, mode-specific **rules cards**, accent colours, emblems, and confetti palettes.
- Live **throw animations**, target highlighting on the board, dedicated Cricket & Killer lower-thirds.
- **Audio**: spoken score announcements (macOS `say`), event sound effects, and X01 "180!" / ton calls.
- Non-X01 modes launch straight into cinematic mode; a fully scripted demo final is available with no cameras needed.

### 📊 Stats & history
- Live **3-dart averages** chart, per-match history, and a cross-match **leaderboard** (wins, win-rate, average).

### 🔌 Pluggable detection source
- Switch between our **native CV engine** and an **Autodarts** local board manager via the `DETECTION_SOURCE` env var — the game engine, UI, and cinematic layer are identical either way.
- Board-manager status (connected / take-out in progress / stuck) is surfaced live in the UI.

### 🛠️ Calibration & alignment
- **Auto-detect** fits the board boundary as a perspective-aware ellipse and snaps the alignment mesh to it — you only rotate to line up the numbers.
- Manual 4-handle drag alignment and optional checkerboard intrinsic calibration are also supported.

---

## Getting started

### Prerequisites
- Python 3 with `opencv-python`, `numpy`, `fastapi`, `uvicorn`
- Node.js & npm (for the frontend)
- macOS (the `say` command is used for audio announcements)
- 3 USB cameras for live detection (or use the Autodarts source / mock)

### Run the web app

```bash
./start.sh
```

This checks the cameras, then starts the FastAPI backend and the Vite frontend:

- **Frontend UI**: `http://localhost:5173` ← open this
- **Backend API**: `http://localhost:8000`

Stop everything with `Ctrl+C` or `./stop.sh`.

#### Run manually (two terminals)

```bash
python3 src/server.py          # backend on :8000 (run from the repo root)
cd frontend && npm run dev     # frontend on :5173
```

#### Use an Autodarts board instead of the native CV engine

```bash
DETECTION_SOURCE=autodarts AUTODARTS_URL=ws://localhost:3180/api/events python3 src/server.py
```

To develop without any hardware, replay a scripted game on `:3180`:

```bash
python3 src/mock_autodarts.py
```

### Web UI tabs
**Live Track** (stream + live scoreboard + click-to-correct) · **Align** (auto-detect + drag handles) · **Cameras** (feed check) · **Stats** (averages + history) · **Settings** (game setup + detection source).

---

## Project structure

```
darts/
├── src/                # Application code (FastAPI backend, CV pipeline, game engine)
├── tests/              # Test suite (run from the repo root)
├── scripts/            # Standalone utilities (camera checks, checkerboard generator)
├── docs/               # Printable assets (checkerboard PDFs)
├── frontend/           # React 19 + Vite + Tailwind web UI
├── start.sh / stop.sh  # Launchers
└── *.json              # Runtime state (alignment, history, config)
```

Run everything from the repo root so state files resolve correctly. See [CLAUDE.md](CLAUDE.md) for a deep dive into the detection pipeline, scoring engine, and tuning constants.

## Architecture
- **Backend**: Python FastAPI server. Detection runs in a background thread that owns the cameras and the scoring state machine, streaming annotated MJPEG and pushing game state to the UI over a WebSocket. The game engine (X01 + alternative modes), checkout solver, AI, stats, and persistence all live here.
- **Frontend**: React 19 + Vite + Tailwind CSS single-page app, with a WebSocket-driven live scoreboard and the cinematic broadcast layer.

## Tests

```bash
python3 tests/test_game.py               # X01 engine + checkout + hit detail
python3 tests/test_games.py              # Cricket / ATC / Shanghai / Count Up / Killer + AI
python3 tests/test_autocal.py            # ellipse auto-calibration
python3 tests/test_consensus.py          # multi-dart cross-camera clustering
python3 tests/test_line_tips.py          # shaft-line tip localisation
python3 tests/test_autodarts_adapter.py  # Autodarts adapter parsing
python3 tests/test_replay_state.py       # state-machine replay (needs debug_recordings/)
python3 tests/test_board_clear.py        # board-clear detection (needs debug_recordings/)
```

## Logging
Each run mirrors stdout **and** stderr to a timestamped `logs/darts_<timestamp>.log` (with `darts.log` symlinked to the latest), pruned to the most recent 10 sessions — handy for troubleshooting a session after the fact.
