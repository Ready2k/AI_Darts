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
python3 test_game.py                     # X01 engine + checkout + hit detail + check-in
python3 test_games.py                    # Cricket / ATC / Shanghai / Count Up / Killer + AI + master-in
python3 test_autocal.py                  # ellipse auto-calibration
python3 test_consensus.py                # multi-dart cross-camera tip clustering
python3 test_line_tips.py                # shaft-line intersection tip localisation
python3 test_autodarts_adapter.py        # Autodarts adapter notation + event parsing
python3 test_replay_state.py             # state-machine replay harness
python3 test_board_clear.py              # board-clear detection logic
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
   - Contour detection diffs against the **empty board** (`backgrounds`, lighting-healed while empty; `bg_detect` tracks it). All darts on the board are visible at once; flight-end/contamination phantoms are filtered by the downstream gates (tightness + full-camera-agreement + consecutive-consensus), **not** by absorbing scored darts into the reference — absorbing created detection *blind spots* around already-scored darts, so a nearby dart was seen by too few cameras and got missed.
   - Per frame: `absdiff` vs `bg_detect` → threshold → morphology → contour filtering by area + aspect ratio
   - **Both** endpoints of each detected dart shaft are projected to canonical space — since dart flights are ~10cm above the board, only the true tip (at board-plane z=0) projects to consistent canonical coords across cameras; the flight end scatters
   - `find_consensus_tips()` (plural) clusters all cameras' endpoints into **one cluster per physical dart** (each cluster holds ≤1 tip per camera; flight ends fall out as singletons) and returns each cluster's **spread** (max member distance from the centre). A real tip is *tight* (all cameras' rays meet at the board plane ≈ alignment error); the tracker rejects clusters whose spread is too loose as flight-end/noise coincidences — without this, a single dart's flight ends could coincidentally form extra loose multi-camera clusters and score as phantoms (one dart → three). The spread limit is **camera-count dependent**: full 3-camera clusters get `CLUSTER_TIGHT_3CAM` (looser — alignment error grows toward the board edges, and real edge darts still earn full agreement), 2-camera clusters must be within the tighter `CLUSTER_TIGHT` (a loose 2-camera match is the phantom signature). `find_consensus_tip()` (singular) is the legacy one-cluster version, now unused by the loop
   - **Multi-target tracker** (replaces the old `watching → stabilising` state machine): each frame, every cluster that is *new* (not within `CANONICAL_MATCH` of an already-scored dart) **and seen by ≥`MIN_CAMS_TO_TRIGGER` cameras** is matched to a `pending` candidate (a lone single-camera blip never starts one); a pending is scored once it has persisted `CONFIRM_FRAMES` frames with a **consecutive** run of ≥`CONFIRM_CONSENSUS_FRAMES` multi-camera frames (`consensus` is a streak that resets to 0 on any 1-camera / unseen frame — a cumulative count let a persistent edge artifact that was only *occasionally* multi-camera crawl to a score after sitting ~100 frames). One dart is committed per frame, re-checking turn-over before the next, so darts thrown in quick succession are each scored independently. The visit ends (3 darts, bust, or finished leg) → `all_done` until the board clears.
   - **Camera-agreement requirement**: a dart is only committed if (a) it reached **full agreement** (≥`CONFIRM_MIN_CAMS` cameras, capped at the number present) at some point — rules out 2-camera flight phantoms — **and** (b) it still has **multi-camera support on the confirming frame** (`cur_cams ≥ MIN_CAMS_TO_TRIGGER`). A real static dart is seen by every camera every frame; a flight-end phantom's agreement only *flickers* and ends up confirming on a lone single-camera frame (telltale `spread: 0.0` in the `scored` telemetry). The current-support check kills that while staying lenient enough not to drop a real dart one camera briefly lost. (Pendings are still *tracked* from 2 cameras; they just can't score.)
   - **Anti-phantom scene-settle gate**: a dart is only *committed* while the scene is **settled** (frame-to-frame `max_fg` change < `FG_SETTLE_DELTA` for `FG_STABLE_FRAMES` frames — i.e. the dart has landed and the arm/motion is gone). A transient blob from an incoming dart or arm wash spikes fg and so can't confirm mid-motion. Plus the `recent_arrival` (fg-rose) gate and the in-board scoring check.
   - **Contamination gate**: the scene-settle test alone is fooled by an arm held momentarily still (high fg, low frame-to-frame delta → "settled"). A real settled board shows only a few blobs per camera (≈ one per dart); a hand/arm reaching in shatters into many contours. So a dart is **also** only committed while **no camera shows more than `MAX_SCORE_CONTOURS` blobs** (`scene_clean`, logged as `clean` in the `fg` telemetry). The pending persists across the contamination and scores once the arm clears, so a real dart is delayed, never lost. (This is what was missing when a phantom `Double 14` scored at the moment one camera saw 24 contours from the throwing arm.)
   - **Confirmation tie-break**: when several pendings are ready in one frame, the most *trustworthy* is committed first — sorted by **tightest spread, then most cameras, then persistence** — *not* by longest-lived (`seen`). A lingering edge artifact accumulates a high `seen` while a freshly-landed real dart has a low one, so the old `-seen` sort let the stale phantom win.
   - Pendings unseen for `PENDING_GRACE_FRAMES` frames are forgotten (flicker / arm motion)
   - **Board-clear** (`all_done` → next visit): on the first *settled* `all_done` frame the darts-in fg level is measured (`fg_darts_in`); the board is judged clear once `max_fg` drops below `max(EMPTY_FG, fg_darts_in × CLEAR_FRACTION)`. Comparing to the darts-in level (not a running peak) means the arm briefly spiking fg high while *pulling* the darts can't be mistaken for "cleared."
   - Background healing: while the board is empty (`watching`/`all_done`), live grayscale frames are blended into the uint8 background reference (α=0.05, via `cv2.addWeighted`) to compensate for lighting drift
   - Runtime keys (web or legacy): `B` set bull reference · `U` undo last dart (misread correction) · `N` new game · `R` recapture background
   - Dart tips are kept as sub-pixel floats through the consensus/perspective math

### Scoring & game engine (`dartboard.py`, `game.py`, `checkout.py`)

- `dartboard.score_detail(x_mm, y_mm)` → a `Hit(points, label, ring, segment, multiplier)`; `ring` ∈ {INNER_BULL, OUTER_BULL, DOUBLE, TRIPLE, SINGLE, MISS}. `score_at()` still returns the `(points, label)` tuple for back-compat. `is_double(hit)` (DOUBLE or INNER_BULL) drives double-in/out.
- `game.X01Game` is the X01 engine: 301/501/701, 3-dart visits, bust (revert visit), multiple players, legs/sets, 3-dart averages, `undo()` (snapshot stack), and `to_dict()` for the web UI. Check-in is set via `check_in` ∈ {`straight`, `double`, `master`} (`master` opens on a double **or** treble; `is_master()`/`is_triple()` live in `dartboard.py`); the legacy `double_in=True` flag still maps to `check_in="double"`. `double_out` controls the finish. Driven by `record_hit(hit, position)` where `position` is the optional board-mm coord. `correct_last(hit, position)` (undo + re-apply) powers **click-to-correct** misreads. Finished matches are appended to `match_history.json` via `history.save_match()` (detect loop saves on the over-edge).
- **Alternative game modes** (`games.py`): `CricketGame`, `AroundTheClockGame`, `ShanghaiGame`, `CountUpGame`, `KillerGame` all subclass `BaseGame`, which shares the X01-compatible interface (`record_hit`, `to_dict`, `undo`, `enter_review`/`confirm_review`, `.player`, `.over`, `.winner`, `.checkout_hint()`→None). `games.create_game(mode, players, rounds=…, lives=…, legs_to_win=…)` is the factory; it returns `None` for X01 modes so the caller falls back to `X01Game`. Killer arming is configurable via `arm_mode` ∈ {`marks` (Standard — 3 marks on your own number), `double` (Hard — your own double)}, surfaced in `to_dict()` as `arm_mode` and selected in the setup UI as Standard/Hard. Players pick their numbers via a pre-game spin-the-wheel in the cinematic (`KillerSpin.jsx`, the `spin` phase after the rules card); the chosen numbers are POSTed to `/api/game/killer/numbers` → `KillerGame.assign_numbers()`. `to_dict()` carries `mode`, `mode_label`, and per-player `state` (cricket marks, ATC target, Killer number/lives/killer/out/arm, …) so the same scoreboard + cinematic UI render every mode. `BaseGame._visit_should_end()` lets Killer end a visit early on self-elimination; `KillerGame._advance_player` skips eliminated players. Covered by `test_games.py`.
- **AI opponents across modes** (`ai.py`): `decide_target_label(game)` switches on `game.mode` to pick a sensible throw (Cricket: close own numbers high-first then score on opponents' open; ATC: current target; Shanghai: treble the round number; Count Up: T20; Killer: arm on own double, then treble the strongest alive foe; X01: checkout solver). `decide_target()` maps the label to ideal mm coords, then `execute_ai_throw` adds per-level Gaussian spread.
- `checkout.suggest(score, darts_left, double_out)` returns a finishing path (e.g. `["T20","T20","DBull"]`) or `None`; preference-ordered so the first solution is throwable.
- `test_game.py` (`python3 test_game.py`) covers the engine, checkout solver, and hit detail.

### Web UI vs. legacy GUI

- **Legacy** (`menu.py`, direct script launches): OpenCV `imshow` windows, keyboard/mouse via `cv2.waitKey`
- **Web UI** (`server.py` + `frontend/`): FastAPI streams MJPEG via `StreamingResponse`; frontend `StreamViewer` renders the stream and POSTs mouse/keyboard events back to `/api/event/{detect|align}`. The backend stores events in `ALIGN_EVENTS` / `detect.DETECT_EVENTS` lists that the detection worker drains each loop iteration. Frontend is React 19 + Tailwind CSS v4 + Vite, with `recharts` for stats.
- **Detection runs in a background thread, decoupled from the stream.** `detect._run_detection()` owns the cameras + scoring state machine and publishes the latest annotated JPEG to `detect._latest_jpeg`; `detect.stream_frames()` is a thin generator that calls `start_detection()` and just serves that frame. Closing/remounting the Live Track tab only detaches a viewer — detection keeps running, so darts still score while you're on another tab and the background is **captured once** (no re-capture/poisoning on remount). Cameras are exclusive and shared with the Align/Cameras tabs, so `/api/stream/{align,check}` call `detect.stop_detection()` to take the hardware; detection restarts when Live Track is reopened. `stop_detection()` also runs on FastAPI lifespan shutdown.
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

### Autodarts adapter (pluggable detection engine)

`autodarts_adapter.py` skins the **Autodarts local board manager** (`:3180` WebSocket) as the detection engine, feeding each dart event into `detect.GAME` so the frontend and cinematic UI work unchanged. The `DETECTION_SOURCE` env var switches between `native` (our CV) and `autodarts`. The WS message schema (`/api/events`) was captured live from board manager v1.0.7; `_parse_message()` is the only place that knows the wire format — everything downstream uses `notation_to_hit()` which is unit-tested in `test_autodarts_adapter.py`.

The adapter publishes board-manager status (`connected`, last `event`, `awaiting_takeout`, and a `ts` that only advances when the state changes) into `detect.STATUS["autodarts"]`, which rides along on the game-state WS (`detect.game_state()` adds it) and is also in `GET /api/config`. The cinematic top bar renders it (`AutodartsStatus` in `CinematicGame.jsx`): a stuck board (e.g. stuck mid-takeout) shows the non-progressing state and, after ~12s, a red "Stuck? … · Ns" so a silent hang is visible.

To develop without a real board: `mock_autodarts.py` replays a scripted 501 game on `:3180` using the exact captured schema.

```bash
python3 mock_autodarts.py
DETECTION_SOURCE=autodarts AUTODARTS_URL=ws://localhost:3180/api/events python3 server.py
```

### Line-based tip localisation (`line_tips.py`)

Replaces dual-endpoint clustering. Each camera's dart contour is fit to a **shaft line**; the line is warped into canonical board space via the alignment homography. Because a homography maps lines to lines and maps the on-board tip pixel correctly (the flight end is ~10 cm off-plane and warps differently per camera), the **intersection of the warped shaft lines from all cameras is the true tip** — no endpoint ambiguity, no flight-end phantoms. Unit-tested in `test_line_tips.py`.

### Replay rigs (`replay.py`, `replay_state.py`)

`replay_state.py` — the authoritative offline test harness. Feeds a `debug_recorder.py` recording through the **same** `detect.step_tracker` function the live loop calls, so the full scoring state machine (pending/confirm/bust/board-clear) can be reproduced and diagnosed without cameras. Frame rate caveat: recorder throttles to ~15 fps vs live ~30 fps, so per-frame counters advance at half rate.

`replay.py` — geometry-only replay: re-runs `detect_all_darts` + `find_tips_by_lines` on recorded frames to validate tip positions without the state machine.

```bash
python3 replay_state.py <recording_dir>   # full state-machine replay
python3 replay.py <recording_dir>         # geometry/tip validation only
```

### Cinematic game mode (`frontend/src/cinematic/`)

Broadcast-style overlay for live 2-player games driven entirely by WebSocket game state. Key files:
- `CinematicGame.jsx` — live game driver; maps `useGame()` state to the broadcast `pl` player shape, manages walk-on card sequencing and throw animations
- `CinematicDemo.jsx` — canned scripted final (no live WS needed) for demos
- `broadcastParts.jsx` — shared presentational components: `WalkOnCard`, `SideChar` (caricature flanking panels), lower-third score `Panel`, `BroadcastBoard`
- `audio.js` — sound effects keyed by game event
- `modeThemes.js` — per-mode visual identity (accent colour, emblem, themed rules-card entrance, win-shot call, confetti palette). `CinematicGame` is mode-aware: walk-on for every player → a click-to-continue `RulesCard` (themed, mode-specific how-to-play) → match. The board highlights the active player's targets (`BroadcastBoard` `targets`/`targetColor`); Cricket and Killer get dedicated lower-third scoreboards (`CricketScoreboard`, `KillerScoreboard`). Win/elimination moments use themed big-calls + confetti; the X01-only 180/ton calls are suppressed in other modes (and the spoken visit-total in `App.jsx` is X01-only).

Player avatars are configured in `frontend/src/config/avatars.js`; caricature SVG art lives in `frontend/src/art/`.

### AI player simulation (`ai.py`)

`simulate_throw(label, level)` adds Gaussian spread (σ configurable per `LEVEL_SPREAD` dict) to an ideal target coordinate and returns a `Hit`. Used to simulate AI opponents in cinematic demo mode. Three levels: `Beginner` (σ=45 mm), `Semi Pro` (σ=15 mm), `Pro` (σ=6 mm).

### Detection tuning constants (top of `detect.py`)

`DIFF_THRESH`, `MIN_DART_AREA`, `MAX_DART_AREA`, `CAM_MIN_ASPECT`, `MIN_CAMS_TO_TRIGGER`, `CANONICAL_CLUSTER` (loose association radius), `CLUSTER_TIGHT` (confirmed clusters must agree within this — raise if real darts are dropped as "loose", lower if phantoms slip through), `CANONICAL_JUMP`, `CANONICAL_MATCH` — and the multi-dart tracker constants `CONFIRM_FRAMES` (frames a new dart must persist before scoring, ~0.25s), `CONFIRM_CONSENSUS_FRAMES` (of those, how many need ≥`MIN_CAMS_TO_TRIGGER` cameras), `PENDING_GRACE_FRAMES`, `FG_SETTLE_DELTA` + `FG_STABLE_FRAMES` (scene-settle anti-phantom gate), `MAX_SCORE_CONTOURS` (contamination gate — max blobs any camera may show while a score is committed; raise if real grouped darts are being held back, lower if arm-motion phantoms still slip through), `EMPTY_FG` + `CLEAR_FRACTION` (board-clear). Lower `CONFIRM_FRAMES` for faster scoring at the cost of more flicker sensitivity; raise `FG_STABLE_FRAMES` / lower `FG_SETTLE_DELTA` if motion phantoms still slip through. (`STABLE_FRAMES`, `CONSENSUS_FRAMES_TO_SCORE`, `POST_SCORE_SETTLE_SECS`, `FG_SETTLE_ALPHA` are legacy/unused after the multi-dart rewrite.)
