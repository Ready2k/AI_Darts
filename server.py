import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

import check_cameras
import align
import detect
import history
import leaderboard
import ai


def current_state():
    """Serialisable game state for the scoreboard, or a placeholder."""
    return detect.game_state() or {"running": False}


class GameHub:
    """Tracks connected scoreboard clients and pushes game-state updates."""

    def __init__(self):
        self.clients = set()

    async def register(self, ws):
        await ws.accept()
        self.clients.add(ws)
        await self._send(ws, json.dumps(current_state()))

    def unregister(self, ws):
        self.clients.discard(ws)

    async def _send(self, ws, msg):
        try:
            await ws.send_text(msg)
            return True
        except Exception:
            return False

    async def broadcast(self, msg):
        for ws in list(self.clients):
            if not await self._send(ws, msg):
                self.clients.discard(ws)


hub = GameHub()


async def _watch_game():
    """
    Single in-process broadcaster: diff the shared game state every 100 ms and
    push to all clients only when it changes. Covers every mutation source
    (the detect thread, and the REST control endpoints) without cross-thread
    asyncio hazards — clients never poll.
    """
    # Seed with the current state so we don't re-broadcast what `register`
    # already sends to a freshly connected client.
    last_state = current_state()
    last = json.dumps(last_state)
    game_was_over = last_state.get("over", False)
    while True:
        try:
            state = current_state()
            msg = json.dumps(state)
            if msg != last:
                last = msg
                await hub.broadcast(msg)
                
            # Handle saving match history if game just ended
            over_now = state.get("over", False)
            if over_now and not game_was_over:
                if detect.GAME:
                    print("Game is over, saving match history...")
                    history.save_match(detect.GAME)
                # Flush/close any debug recording so the video + telemetry are
                # finalised and ready to zip up.
                detect.dbg.stop()
            game_was_over = over_now
            
        except Exception as e:
            import traceback
            traceback.print_exc()
        await asyncio.sleep(0.1)


@asynccontextmanager
async def lifespan(app):
    watcher = asyncio.create_task(_watch_game())
    ai_task = asyncio.create_task(ai.ai_loop())
    try:
        yield
    finally:
        watcher.cancel()
        ai_task.cancel()
        # Finalise any in-progress debug recording so the video is playable.
        detect.dbg.stop()


app = FastAPI(lifespan=lifespan)

# Enable CORS for the local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALIGN_EVENTS = []
# Detect input events live on the detect module so the background detection
# worker (which the stream just observes) can drain them.
DETECT_EVENTS = detect.DETECT_EVENTS


async def _guarded_stream(gen, request: Request):
    """
    Wrap a synchronous MJPEG generator so it stops the moment the browser
    closes the connection. Without this, the sync generator keeps running in
    its thread even after Stop is clicked — cameras stay open and darts keep
    being scored into the game.
    """
    try:
        while True:
            if await request.is_disconnected():
                break
            frame = await run_in_threadpool(next, gen, None)
            if frame is None:
                break
            yield frame
    finally:
        gen.close()


@app.websocket("/ws/game")
async def ws_game(ws: WebSocket):
    """Live scoreboard feed — pushes game state on every change."""
    await hub.register(ws)
    try:
        while True:
            await ws.receive_text()   # no client messages expected; detects disconnect
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(ws)


# ── Game state / control API (drives the React scoreboard) ─────────────────────

@app.get("/api/game")
def get_game():
    """Current X01 game state, or {running: False} before a game exists."""
    return detect.game_state() or {"running": False}


@app.post("/api/game/new")
async def new_game(request: Request):
    """Start a new game. Body: players[], start_score, double_in, double_out, legs_to_win, sets_to_win."""
    cfg = await request.json()
    players_raw = cfg.get("players")
    players = []
    if players_raw:
        for p in players_raw:
            if isinstance(p, dict) and p.get("name") and p["name"].strip():
                p["name"] = p["name"].strip()
                players.append(p)
            elif isinstance(p, str) and p.strip():
                players.append(p.strip())
    
    if not players:
        players = None
    detect.new_game(
        players=players,
        start_score=cfg.get("start_score"),
        double_in=cfg.get("double_in"),
        double_out=cfg.get("double_out"),
        legs_to_win=cfg.get("legs_to_win"),
        sets_to_win=cfg.get("sets_to_win"),
        debug=bool(cfg.get("debug", False)),
    )
    return detect.game_state()


@app.post("/api/game/undo")
def undo_game():
    """Undo the last recorded dart (manual misread correction)."""
    with detect.GAME_LOCK:
        ok = detect.GAME.undo() if detect.GAME else False
    if ok:
        detect.dbg.event("undo", source="api")
    return {"ok": ok, "game": detect.game_state()}


@app.post("/api/game/end")
def end_game():
    """Abandon the current game (no winner recorded)."""
    with detect.GAME_LOCK:
        detect.GAME = None
    detect.STATUS["game_gen"] += 1
    detect.dbg.stop()
    return {"ok": True}


@app.get("/api/history")
def get_history():
    """Recently completed matches, most recent first."""
    return list(reversed(history.load_history(limit=20)))


@app.get("/api/leaderboard")
def get_leaderboard():
    """Returns the current leaderboard statistics."""
    return leaderboard.get_leaderboard()

@app.post("/api/game/correct")
async def correct_game(request: Request):
    """Relocate/re-score the last dart from a board click. Body: {x_mm, y_mm}."""
    import dartboard
    data = await request.json()
    hit = dartboard.score_detail(float(data["x_mm"]), float(data["y_mm"]))
    with detect.GAME_LOCK:
        ev = detect.GAME.correct_last(hit, (float(data["x_mm"]), float(data["y_mm"]))) if detect.GAME else None
    if ev is not None:
        detect.dbg.event("correct", label=hit.label, ring=hit.ring,
                         segment=hit.segment, x_mm=float(data["x_mm"]),
                         y_mm=float(data["y_mm"]))
    return {"ok": ev is not None, "label": hit.label, "game": detect.game_state()}

@app.post("/api/debug/simulate_hit")
async def simulate_hit(request: Request):
    """Simulates a hit on the dartboard for testing UI animations."""
    import dartboard
    data = await request.json()
    
    # Calculate a valid (x,y) for Treble 20 to drive the UI. T20 is at angle=0, radius=103
    # 0 angle is straight up, so x=0, y=103
    x_mm, y_mm = 0.0, 103.0 
    
    # Override if explicitly passed
    if "x_mm" in data and "y_mm" in data:
        x_mm = float(data["x_mm"])
        y_mm = float(data["y_mm"])

    hit = dartboard.score_detail(x_mm, y_mm)
    with detect.GAME_LOCK:
        if detect.GAME:
            detect.GAME.record_hit(hit, (x_mm, y_mm))
            
    return {"ok": True, "label": hit.label, "game": detect.game_state()}

@app.post("/api/event/detect")
async def detect_event(request: Request):
    data = await request.json()
    DETECT_EVENTS.append(data)
    return {"status": "ok"}

@app.get("/api/stream/detect")
async def stream_detect(request: Request):
    return StreamingResponse(
        _guarded_stream(detect.stream_frames(), request),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/api/event/align")
async def align_event(request: Request):
    data = await request.json()
    ALIGN_EVENTS.append(data)
    return {"status": "ok"}

@app.get("/api/stream/align")
async def stream_align(request: Request):
    ALIGN_EVENTS.clear()
    # Align needs exclusive camera access — release the detection worker first.
    await run_in_threadpool(detect.stop_detection)
    return StreamingResponse(
        _guarded_stream(align.stream_frames(ALIGN_EVENTS), request),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/api/stream/check")
async def stream_check(request: Request):
    # The Cameras viewer needs exclusive camera access too.
    await run_in_threadpool(detect.stop_detection)
    return StreamingResponse(
        _guarded_stream(check_cameras.stream_frames(), request),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/api/debug/snapshot")
async def debug_snapshot():
    """
    Save a debug bundle: last 300 log lines + live camera frames + alignment views.
    Writes to debug_snapshots/<timestamp>/ so you can share the folder for review.
    """
    import time as _time
    from pathlib import Path
    import json as _json
    import cv2 as _cv2
    import numpy as _np

    ts = _time.strftime("%Y%m%d_%H%M%S")
    out = Path("debug_snapshots") / ts
    out.mkdir(parents=True, exist_ok=True)

    # --- logs ---
    log_lines = []
    for log_path in ["darts.log", "/tmp/darts_backend.log"]:
        p = Path(log_path)
        if p.exists():
            lines = p.read_text(errors="replace").splitlines()
            log_lines.append(f"=== {log_path} (last 300 lines) ===")
            log_lines.extend(lines[-300:])
    (out / "logs.txt").write_text("\n".join(log_lines))

    # --- game state ---
    state = detect.game_state() or {"running": False}
    (out / "game_state.json").write_text(_json.dumps(state, indent=2))

    # --- camera frames + alignment views ---
    homographies = detect.load_alignment()
    saved_cams   = []
    frames_by_cam = {}

    for idx in detect.CAMERAS:
        cap = _cv2.VideoCapture(idx)
        if cap.isOpened():
            for _ in range(5):   # drain stale frames
                cap.read()
            ret, frame = cap.read()
            cap.release()
            if ret:
                _cv2.imwrite(str(out / f"cam{idx}_raw.jpg"), frame)
                frames_by_cam[idx] = frame
                saved_cams.append(idx)

                # Per-camera warped view (camera → canonical board space)
                H = homographies.get(idx)
                if H is not None:
                    warped = _cv2.warpPerspective(
                        frame, H,
                        (detect.CANONICAL_SIZE, detect.CANONICAL_SIZE)
                    )
                    _cv2.imwrite(str(out / f"cam{idx}_warped.jpg"), warped)

    # --- merged canonical board view (all cameras blended) ---
    if frames_by_cam and homographies:
        merged = detect.make_merged_view(frames_by_cam, homographies)
        _cv2.imwrite(str(out / "board_merged.jpg"), merged)

    summary = {
        "ts": ts,
        "cameras_saved": saved_cams,
        "alignment_loaded": bool(homographies),
        "log_lines": len(log_lines),
        "folder": str(out),
    }
    print(f"[snapshot] saved debug bundle → {out}")
    return summary


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
