# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Darts scoring system using 3 USB cameras (indices 0, 1, 2) and computer vision. Two UIs exist: a legacy OpenCV GUI and a web UI (FastAPI backend + React frontend).

## Commands

```bash
# Legacy OpenCV GUI (all-in-one launcher)
./start.sh               # OpenCV menu
./start.sh detect        # Dart detection + scoring
./start.sh align         # Camera mesh alignment
./start.sh cameras       # Live camera viewer
./start.sh calibrate     # Checkerboard intrinsic calibration
./start.sh calibrate-extrinsic
./stop.sh                # Kill all running instances

# Web UI (two terminals)
python3 server.py                        # FastAPI backend on :8000
cd frontend && npm run dev               # Vite dev server on :5173
cd frontend && npm run build
cd frontend && npm run lint

# Tests
python3 test_game.py                     # game engine + checkout + hit detail
python3 test_autocal.py                  # ellipse auto-calibration
```

Dependencies: `opencv-python`, `numpy`, `fastapi`, `uvicorn`. The `say` macOS command is used for audio score announcements.

## Architecture

### Coordinate system

Detection works in a **canonical board space**: a 500×500px image where the centre (250, 250) is the bullseye and radius 220px = the double-out ring (170mm). All homographies map camera pixels → this canonical space for scoring.

### Pipeline

1. **Calibration** (`calibrate.py`) — optional one-time step, saves `calibration.npz` (intrinsic + extrinsic camera parameters)
2. **Alignment** (`align.py`) — required before detection. User drags 4 diamond handles (top/right/bottom/left = Seg 20/6/3/11 outer doubles) to fit the board mesh on each camera. Saves homographies to `alignment.json`. Diamond layout (not a cross) prevents degenerate homographies where 3 points share the same canonical y. **Auto-detect** (`A` key / web button → `auto_calibrate.py`) fits the board boundary as an ellipse (perspective-aware) and snaps the handles to it; the user then only rotates to line up the numbers (ellipse fixes position/size/perspective but not rotation). `test_autocal.py` covers it.
3. **Detection** (`detect.py`) — background subtraction loop:
   - Cameras warm up (2s sleep + 60 drain frames per camera) before background capture to let auto-exposure/AWB settle
   - `capture_background()` averages 30 unique frames per camera. The board ROI mask comes from `roi_from_homography()` (inverse-warps a canonical disc of 1.2× the double ring through the alignment homography — deterministic); `detect_board_roi()` (HoughCircles) is only the fallback when no alignment exists
   - **Two background references per camera**: `backgrounds` (the empty board — drives the foreground-occupancy metric for the arrival gate and board-cleared detection) and `bg_detect` (the *last settled frame*, with already-scored darts absorbed into it — drives contour detection). After each scored dart, once the post-score cooldown passes and fg settles, the live frame is snapshotted into `bg_detect`, so the next dart is the only foreground object. This is the frame-subtraction approach used by opencv-steel-darts etc.; diffing everything against the empty board makes crossing shafts/flights merge contours and breaks cross-camera clustering
   - Per frame: `absdiff` vs `bg_detect` → threshold → morphology → contour filtering by area + aspect ratio
   - **Both** endpoints of each detected dart shaft are passed to `find_consensus_tip()` — since dart flights are ~10cm above the board, only the true tip (at board-plane z=0) will project to consistent canonical coords across cameras; the flight end will scatter
   - `find_consensus_tip()` clusters candidates across cameras; requires `MIN_CAMS_TO_TRIGGER` (default 2) cameras to agree
   - State machine: `watching` → `stabilising` (must stay stable for `STABLE_FRAMES=15` consecutive frames, with ≥`CONSENSUS_FRAMES_TO_SCORE` of those frames multi-camera-confirmed — not necessarily the final frame) → scores dart (fed into the live `X01Game`) → `watching`; when the visit ends (3 darts, bust, or a finished leg) enters `all_done` until the board is cleared, then announces the next player
   - Ghost dart guard: if `stabilising` lasts >2s without locking in, reverts to `watching`
   - Background healing: while the board is empty (`watching`/`all_done`), live grayscale frames are blended into the uint8 background reference (α=0.05, via `cv2.addWeighted`) to compensate for lighting drift
   - Runtime keys (web or legacy): `B` set bull reference · `U` undo last dart (misread correction) · `N` new game · `R` recapture background
   - Dart tips are kept as sub-pixel floats through the consensus/perspective math

### Scoring & game engine (`dartboard.py`, `game.py`, `checkout.py`)

- `dartboard.score_detail(x_mm, y_mm)` → a `Hit(points, label, ring, segment, multiplier)`; `ring` ∈ {INNER_BULL, OUTER_BULL, DOUBLE, TRIPLE, SINGLE, MISS}. `score_at()` still returns the `(points, label)` tuple for back-compat. `is_double(hit)` (DOUBLE or INNER_BULL) drives double-in/out.
- `game.X01Game` is the X01 engine: 301/501/701, double-in/out, 3-dart visits, bust (revert visit), multiple players, legs/sets, 3-dart averages, `undo()` (snapshot stack), and `to_dict()` for the web UI. Driven by `record_hit(hit, position)` where `position` is the optional board-mm coord. `correct_last(hit, position)` (undo + re-apply) powers **click-to-correct** misreads. Finished matches are appended to `match_history.json` via `history.save_match()` (detect loop saves on the over-edge).
- `checkout.suggest(score, darts_left, double_out)` returns a finishing path (e.g. `["T20","T20","DBull"]`) or `None`; preference-ordered so the first solution is throwable.
- `test_game.py` (`python3 test_game.py`) covers the engine, checkout solver, and hit detail.

### Web UI vs. legacy GUI

- **Legacy** (`menu.py`, direct script launches): OpenCV `imshow` windows, keyboard/mouse via `cv2.waitKey`
- **Web UI** (`server.py` + `frontend/`): FastAPI streams MJPEG via `StreamingResponse`; frontend `StreamViewer` renders the stream and POSTs mouse/keyboard events back to `/api/event/{detect|align}`. The backend stores events in `ALIGN_EVENTS` / `DETECT_EVENTS` lists that `stream_frames()` drains each loop iteration. Frontend is React 19 + Tailwind CSS v4 + Vite, with `recharts` for stats.
- **Game state** is pushed to the React scoreboard over a WebSocket (`/ws/game`) — no client polling. `server.GameHub` tracks clients; a single lifespan-managed watcher task diffs `current_state()` every 100 ms and broadcasts on change, so it catches both detect-thread scoring and REST mutations without cross-thread asyncio hazards. The frontend `useGame()` hook auto-reconnects.
- **Game control API** (REST): `POST /api/game/new` (`players[]`, `start_score`, `double_in`, `double_out`, `legs_to_win`, `sets_to_win`), `POST /api/game/undo`, `POST /api/game/correct` (`{x_mm, y_mm}` from a board click → re-scores the last dart), `GET /api/game` (fallback snapshot), `GET /api/history`. The shared `X01Game` lives at `detect.GAME` (guarded by `detect.GAME_LOCK`); `detect.game_state()` / `detect.new_game()` are the thread-safe accessors. The detection loop also paints a scoreboard strip into the MJPEG as a fallback.
- **Tabs**: Live Track (detect stream + live scoreboard + undo/new-game + interactive `DartBoard.jsx` for click-to-correct), Align (Auto-detect + drag handles + Confirm/Reset), Cameras (check feed), Stats (averages chart + table + match history), Settings (game setup).

### Persistent state files

| File | Contents |
|---|---|
| `alignment.json` | Per-camera homography matrices (cam → canonical) |
| `calibration.npz` | Intrinsic + extrinsic camera parameters |
| `bull_reference.json` | Per-camera bull pixel coords (set with `B` key during detection) |
| `board_config.json` | `rotation_deg` offset (legacy — currently unused; board orientation is encoded in the alignment homographies) |
| `match_history.json` | Completed matches (winner, players, legs/sets, averages) |
| `darts.log` | Session log (stdout tee'd here during detection) |

### Detection tuning constants (top of `detect.py`)

`DIFF_THRESH`, `MIN_DART_AREA`, `MAX_DART_AREA`, `CAM_MIN_ASPECT`, `STABLE_SECS`, `STABLE_FRAMES`, `CONSENSUS_FRAMES_TO_SCORE`, `CANONICAL_CLUSTER`, `CANONICAL_JUMP`, `MIN_CAMS_TO_TRIGGER` — adjust these for different lighting or camera positions.
