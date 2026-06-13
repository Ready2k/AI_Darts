#!/usr/bin/env python3
"""
Dart detection — background subtraction across 3 cameras.

Startup: captures an empty-board reference frame for each camera.
Runtime: diffs each frame against reference, finds dart contours,
         tracks up to 3 darts per turn with score announcement.
"""

import sys
import math
import time
import threading
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

import dartboard
import game
import history

CAMERAS = [0, 1, 2]
LABELS  = {0: "Darts Cam 0", 1: "Darts Cam 1", 2: "Darts Cam 2"}

TILE_W, TILE_H = 640, 480

# ── Shared game state (read by server.py for the web scoreboard) ───────────────
GAME      = None
GAME_LOCK = threading.Lock()
GAME_CONFIG = {
    "players":     ["Player 1"],
    "start_score": 501,
    "double_in":   False,
    "double_out":  True,
    "legs_to_win": 3,
    "sets_to_win": 1,
}


def new_game(**overrides):
    """(Re)start the X01 game. Thread-safe — called from the web API or 'N' key."""
    global GAME
    for k, v in overrides.items():
        if v is not None and k in GAME_CONFIG:
            GAME_CONFIG[k] = v
    with GAME_LOCK:
        GAME = game.X01Game(
            GAME_CONFIG["players"],
            start_score=GAME_CONFIG["start_score"],
            double_in=GAME_CONFIG["double_in"],
            double_out=GAME_CONFIG["double_out"],
            legs_to_win=GAME_CONFIG["legs_to_win"],
            sets_to_win=GAME_CONFIG["sets_to_win"],
        )
    STATUS["game_gen"] += 1
    return GAME


# Live detection phase, surfaced to the web UI so it can prompt "remove darts".
# game_gen is bumped every time a new game is started via the API so the detect
# loop can notice the game was replaced and flush its per-turn local state.
STATUS = {"phase": "idle", "awaiting_clear": False, "game_gen": 0}


def game_state():
    """Serialisable snapshot for the web UI (safe to call from another thread)."""
    with GAME_LOCK:
        d = GAME.to_dict() if GAME else None
    if d is not None:
        d["detect_phase"] = STATUS["phase"]
        d["awaiting_clear"] = STATUS["awaiting_clear"]
    return d

# Canonical merged board view (must match align.py)
CANONICAL_SIZE   = 500
CANONICAL_CENTRE = CANONICAL_SIZE // 2   # 250 px
CANONICAL_RADIUS = 220                   # px for DOUBLE_OUT ring

# Stability: dart must be detected for this long before scoring
STABLE_SECS = 1.0
# After all 3 scored: board must be clear this long before next turn starts
ABSENT_SECS = 1.5
# Candidate tip may disappear this long (seconds) before we give up on it
CANDIDATE_GRACE = 0.5

# Detection tuning
DIFF_THRESH   = 25    # pixel intensity change to count as foreground
MIN_DART_AREA = 120   # minimum contour area
MAX_DART_AREA = 8000  # maximum (ignore hand/arm blobs)

# Per-camera minimum aspect ratio. A dart seen near end-on produces a squat
# blob; too high a floor silently removes that camera from the consensus vote.
CAM_MIN_ASPECT = {0: 1.6, 1: 1.6, 2: 1.6}

# Min px between two DIFFERENT scored darts in canonical space (12px ≈ 9mm).
# Scored darts are absorbed into the per-dart detection background shortly
# after scoring, so they can no longer re-appear as foreground at all — this
# is only a safety net for the brief window before that refresh. Keeping it
# small matters: tight grouping (three darts at T20) lands new darts well
# within 23mm of the previous one, and a large radius rejects them as dupes.
CANONICAL_MATCH = 12
# Max px between two cameras' views of the SAME dart — alignment won't be perfect
CANONICAL_CLUSTER = 55
# Reset the stable timer only if the smoothed position jumps this far
CANONICAL_JUMP  = 120
# Minimum cameras that must agree to trigger stabilising.
MIN_CAMS_TO_TRIGGER = 2

STABLE_FRAMES = 15     # consecutive stable frames before scoring (~0.5s)

# During stabilising, the candidate must be confirmed by >= MIN_CAMS_TO_TRIGGER
# cameras in at least this many frames (not necessarily the final one). A real
# dart racks these up quickly; an arm passing through yields only a couple.
# Requiring multi-cam agreement on the *exact* scoring frame instead (the old
# rule) dropped real darts whenever one camera flickered at the wrong moment.
CONSENSUS_FRAMES_TO_SCORE = 5

# A turn ends when 3 darts are in. We only start the next turn once the board is
# physically cleared — judged by TOTAL foreground (fg) dropping below this, which
# is a far more stable signal than per-camera tip detection (one camera losing
# sight of the darts must NOT look like "board cleared"). Darts-in-board fg runs a
# few thousand; an empty board is a few hundred. Tune from the [all_done] fg log.
EMPTY_FG = 1500

# Phantom guard: a real dart makes the foreground RISE (a new object lands);
# static reflections/lighting don't. We track a slow "quiet" baseline of the
# foreground and only allow a new dart to be scored shortly after fg rises clearly
# above that baseline. This is relative (scale-independent), so it won't block
# real darts the way an absolute motion threshold did. Tune FG_RISE_DELTA from the
# "[fg]" log lines (it should be below a single dart's fg jump, above noise).
FG_RISE_DELTA  = 400    # fg increase over baseline that counts as "a dart arrived"
ARRIVAL_WINDOW = 6.0    # seconds after an arrival within which a dart may score
FG_QUIET_ALPHA = 0.05   # EMA rate of the quiet-board baseline
# After scoring a dart, we immediately jump fg_quiet to the dart-in-board level and
# then let it settle with a fast EMA for POST_SCORE_SETTLE_SECS.  This closes the
# arrival gate so dart 1 cannot re-trigger stabilising while it is still in the board;
# the NEXT real dart must produce a genuine new rise above the new (dart-in-board)
# baseline before it can be scored.
POST_SCORE_SETTLE_SECS = 1.2  # seconds of fast settling after each dart scores
FG_SETTLE_ALPHA        = 0.3  # fast EMA alpha during post-score cooldown



# ── Camera reader (threaded) ───────────────────────────────────────────────────

class CameraReader:
    def __init__(self, index):
        self.index = index
        self.cap   = cv2.VideoCapture(index)
        self._frame  = None
        self._lock   = threading.Lock()
        self._stop   = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        try:
            self.cap.release()
        except Exception:
            pass

    def _reopen(self):
        # A camera can be momentarily busy when a superseded detection session
        # hasn't released it yet (USB devices allow a single owner). Re-acquire
        # until it opens so the reader self-heals instead of going dead — which
        # would otherwise stall capture_background's warmup drain forever.
        try:
            self.cap.release()
        except Exception:
            pass
        self.cap = cv2.VideoCapture(self.index)

    def _run(self):
        fails = 0
        while not self._stop.is_set():
            if not self.cap.isOpened():
                self._reopen()
                if not self.cap.isOpened():
                    if self._stop.wait(0.3):
                        break
                    continue
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self._frame = frame
                fails = 0
            else:
                # Device dropped or never really opened — try to reacquire.
                fails += 1
                if fails >= 30:
                    self._reopen()
                    fails = 0
                    if self._stop.wait(0.3):
                        break

    def get_frame(self):
        with self._lock:
            return self._frame.copy() if self._frame is not None else None


# ── Audio ──────────────────────────────────────────────────────────────────────

def say(text):
    threading.Thread(
        target=lambda: subprocess.run(["say", text]),
        daemon=True,
    ).start()


# ── Board ROI & background ─────────────────────────────────────────────────────

def detect_board_roi(gray):
    """Find the dartboard circle. Returns (mask, (cx, cy), radius_px)."""
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    h, w = gray.shape
    min_r = int(min(h, w) * 0.25)
    max_r = int(min(h, w) * 0.65)
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2,
        minDist=min(h, w) // 2,
        param1=80, param2=40,
        minRadius=min_r, maxRadius=max_r,
    )
    mask = np.zeros_like(gray)
    if circles is not None:
        cx, cy, r = np.round(circles[0][0]).astype(int)
        cv2.circle(mask, (cx, cy), int(r * 1.15), 255, -1)
        print(f"    Board circle found: centre ({cx},{cy}) radius {r}px")
        return mask, (int(cx), int(cy)), int(r)
    else:
        mask[:] = 255
        print("    Board circle not found - using full frame")
        return mask, (w // 2, h // 2), min(h, w) // 2


def roi_from_homography(H, shape):
    """
    Camera-space board mask built by inverse-warping a canonical disc through
    the alignment homography. Deterministic — unlike HoughCircles, which can
    lock onto the wrong circle and mask out most of the board for a camera,
    silently removing it from the cross-camera consensus.

    The disc radius (1.2 × double-out ring) matches the scoring clamp limit so
    tips that alignment drift projects slightly outside the doubles still pass.
    """
    h, w = shape
    pad = 60   # canvas margin so the disc isn't clipped at the canonical edges
    r = int(CANONICAL_RADIUS * 1.2)
    src = np.zeros((CANONICAL_SIZE + 2 * pad, CANONICAL_SIZE + 2 * pad), np.uint8)
    cv2.circle(src, (CANONICAL_CENTRE + pad, CANONICAL_CENTRE + pad), r, 255, -1)
    T = np.array([[1, 0, pad], [0, 1, pad], [0, 0, 1]], dtype=np.float64)
    return cv2.warpPerspective(src, T @ H, (w, h),
                               flags=cv2.WARP_INVERSE_MAP | cv2.INTER_NEAREST)


def capture_background(readers, n_frames=20, warmup_frames=30, homographies=None,
                       per_cam_timeout=10.0):
    print("Capturing background - keep board empty...")
    backgrounds = {}
    rois        = {}
    board_info  = {}
    homographies = homographies or {}
    for reader in readers:
        # Drain warmup_frames to let auto-exposure/AWB settle before accumulating.
        # Bounded by per_cam_timeout so a camera that never delivers frames (e.g.
        # unplugged, or wedged) can't hang startup forever.
        drained = 0
        last_frame = None
        deadline = time.time() + per_cam_timeout
        while drained < warmup_frames and time.time() < deadline:
            frame = reader.get_frame()
            if frame is None:
                time.sleep(0.005)
                continue
            if frame is not last_frame:
                drained += 1
                last_frame = frame

        accum = None
        count = 0
        last_frame = None
        deadline = time.time() + per_cam_timeout
        while count < n_frames and time.time() < deadline:
            frame = reader.get_frame()
            if frame is None or frame is last_frame:
                time.sleep(0.005)
                continue
            last_frame = frame
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            accum = gray if accum is None else accum + gray
            count += 1

        if accum is None or count == 0:
            label = LABELS.get(reader.index, f"Camera {reader.index}")
            print(f"  {label}: no frames within {per_cam_timeout:.0f}s — skipping this camera")
            continue
        bg = (accum / count).astype(np.uint8)
        H = homographies.get(reader.index)
        if H is not None:
            mask = roi_from_homography(H, bg.shape)
            c = cv2.perspectiveTransform(
                np.array([[[CANONICAL_CENTRE, CANONICAL_CENTRE]]], np.float32),
                np.linalg.inv(H)).reshape(2)
            center, radius = (int(c[0]), int(c[1])), 0
            print(f"    Board ROI from alignment: centre ({center[0]},{center[1]})")
        else:
            mask, center, radius = detect_board_roi(bg)
        backgrounds[reader.index] = bg
        rois[reader.index]        = mask
        board_info[reader.index]  = {"center": center, "radius": radius}
        label = LABELS.get(reader.index, f"Camera {reader.index}")
        print(f"  {label}: background captured")
    print("Background ready.\n")
    return backgrounds, rois, board_info


# ── Dart detection ─────────────────────────────────────────────────────────────

def detect_all_darts(frame, background, roi=None, min_aspect=1.8,
                     empty_background=None):
    """Returns (list of (p1, p2, contour), foreground_pixel_count).

    `background` is the *detection* reference: the last settled frame, with all
    previously scored darts absorbed into it, so the only foreground is the
    newest dart (frame-subtraction, as used by opencv-steel-darts and friends).
    Diffing against the original empty board instead leaves every dart of the
    visit in the diff — crossing shafts/flights merge contours and produce
    endpoints that never cluster across cameras.

    `empty_background` (the original empty-board reference) drives the
    foreground count: a stable board-occupancy metric used for the arrival
    gate and board-cleared detection, which must keep seeing the scored darts.
    Falls back to `background` when not given."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(gray, background)
    _, mask = cv2.threshold(diff, DIFF_THRESH, 255, cv2.THRESH_BINARY)
    if roi is not None:
        mask = cv2.bitwise_and(mask, roi)
    if empty_background is None:
        fg_area = int(cv2.countNonZero(mask))
    else:
        ediff = cv2.absdiff(gray, empty_background)
        _, emask = cv2.threshold(ediff, DIFF_THRESH, 255, cv2.THRESH_BINARY)
        if roi is not None:
            emask = cv2.bitwise_and(emask, roi)
        fg_area = int(cv2.countNonZero(emask))

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    for c in contours:
        area = cv2.contourArea(c)
        if not (MIN_DART_AREA < area < MAX_DART_AREA):
            continue
        rect = cv2.minAreaRect(c)
        w, h = rect[1]
        if min(w, h) == 0:
            continue
        aspect = max(w, h) / min(w, h)
        if aspect < min_aspect:
            continue
        vx, vy, x0, y0 = cv2.fitLine(c, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
        pts = c.reshape(-1, 2).astype(np.float32)
        t_vals = (pts[:, 0] - x0) * vx + (pts[:, 1] - y0) * vy
        t_min, t_max = t_vals.min(), t_vals.max()
        # Keep sub-pixel float endpoints — the perspective transform and
        # cross-camera consensus are more accurate without truncation.
        p1 = (float(x0 + t_min * vx), float(y0 + t_min * vy))
        p2 = (float(x0 + t_max * vx), float(y0 + t_max * vy))
        results.append((p1, p2, c))
    return results, fg_area


# (pick_tip function removed - we now let mathematical consensus find the tip)


_last_disagree_log = 0.0   # throttle "cameras disagree" messages

def find_consensus_tip(all_tips_by_cam, homographies, scored_canonical):
    """
    Collect canonical tips from ALL cameras and cluster them.
    Returns (avg_canonical, set_of_agreeing_cam_indices) for the strongest
    cluster, or (None, set()) if no new dart detected.

    The cluster position is a *view-weighted* average: each camera's tip is
    weighted by its shaft length squared, so the camera with the clearest
    (most side-on) view of the point dominates and a near-end-on camera — whose
    tip estimate can be off by a wedge — barely contributes. A single-camera
    detection still counts; consensus just raises confidence.
    """
    global _last_disagree_log
    candidates = []   # (canonical_pt, cam_idx, weight)
    for cam_idx, tips in all_tips_by_cam.items():
        if cam_idx not in homographies:
            continue
        for tip, weight in tips:
            c = to_canonical(tip, cam_idx, homographies)
            if c and canonical_is_new(c, scored_canonical):
                candidates.append((c, cam_idx, weight))

    if not candidates:
        return None, set()

    # Find the cluster with the most agreeing cameras
    best_cluster = []   # list of (canonical_pt, weight)
    best_cams    = set()
    for i, (ci, cam_i, wi) in enumerate(candidates):
        seen_cams = {cam_i}
        cluster   = [(ci, wi)]
        for j, (cj, cam_j, wj) in enumerate(candidates):
            if i != j and cam_j not in seen_cams:
                if math.hypot(ci[0] - cj[0], ci[1] - cj[1]) < CANONICAL_CLUSTER:
                    cluster.append((cj, wj))
                    seen_cams.add(cam_j)
        if len(cluster) > len(best_cluster):
            best_cluster = cluster
            best_cams    = seen_cams

    if not best_cluster:
        return None, set()

    # Log when multiple cameras see something but can't agree (throttled to 1/sec)
    all_cams = {cam for _, cam, _ in candidates}
    if len(best_cluster) < MIN_CAMS_TO_TRIGGER and len(all_cams) >= MIN_CAMS_TO_TRIGGER:
        now = time.monotonic()
        if now - _last_disagree_log > 1.0:
            _last_disagree_log = now
            for c, cam, _ in candidates:
                print(f"    [disagree] cam{cam}: ({c[0]:.0f},{c[1]:.0f})")

    # View-weighted average (weight = shaft length²) — favours the clearest view.
    wsum = sum(w * w for _, w in best_cluster) or 1.0
    avg_c = (
        sum(p[0] * w * w for p, w in best_cluster) / wsum,
        sum(p[1] * w * w for p, w in best_cluster) / wsum,
    )
    return avg_c, best_cams



# ── Overlay drawing ────────────────────────────────────────────────────────────

def draw_tile(frame, background, roi, cam_idx, scored_tips=None, is_candidate_cam=False,
              empty_background=None):
    """
    Draw camera tile with all detected darts highlighted.
    scored_tips:     list of (x,y) for darts already scored this turn (orange).
    is_candidate_cam: highlight this tile as the current candidate camera (red border).
    Returns (tile_image, list_of_detected_tips_in_original_px, foreground_area).
    """
    min_aspect = CAM_MIN_ASPECT.get(cam_idx, 1.6)
    darts, fg_area = detect_all_darts(frame, background, roi, min_aspect=min_aspect,
                                      empty_background=empty_background)
    tile  = cv2.resize(frame, (TILE_W, TILE_H))
    sx    = TILE_W / frame.shape[1]
    sy    = TILE_H / frame.shape[0]

    all_tips = []
    for p1, p2, contour in darts:
        # Pass BOTH ends of the dart line to the consensus algorithm!
        # Since the flight sits ~10cm above the board, the perspective warp will
        # project it to radically different canonical coordinates for each camera.
        # Only the true tips (at z=0) will cluster together across all cameras!
        # Tag each endpoint with the shaft length (image px): a camera viewing the
        # dart side-on sees a long shaft and localises the tip well; one viewing it
        # end-on sees a short blob — so length is a view-quality weight.
        shaft_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        all_tips.append((p1, shaft_len))
        all_tips.append((p2, shaft_len))

        scaled = (contour * [sx, sy]).astype(np.int32)
        cv2.drawContours(tile, [scaled], -1, (0, 200, 200), 2)
        lp1 = (int(p1[0] * sx), int(p1[1] * sy))
        lp2 = (int(p2[0] * sx), int(p2[1] * sy))
        cv2.line(tile, lp1, lp2, (0, 180, 255), 1)
        cv2.drawMarker(tile, lp1, (0, 180, 255), cv2.MARKER_CROSS, 16, 2)
        cv2.drawMarker(tile, lp2, (0, 180, 255), cv2.MARKER_CROSS, 16, 2)

    # Scored dart positions shown in orange
    if scored_tips:
        for st in scored_tips:
            tp = (int(st[0] * sx), int(st[1] * sy))
            cv2.circle(tile, tp, 12, (0, 140, 255), 2)
            cv2.drawMarker(tile, tp, (0, 140, 255), cv2.MARKER_DIAMOND, 16, 2)

    # Red border on tiles contributing to the current candidate
    if is_candidate_cam:
        cv2.rectangle(tile, (2, 2), (TILE_W - 2, TILE_H - 2), (0, 0, 255), 3)

    label  = LABELS.get(cam_idx, f"Camera {cam_idx}")
    n      = len(all_tips)
    status = f"{n} dart{'s' if n != 1 else ''}" if n else "watching..."
    s_col  = (0, 255, 0) if n else (160, 160, 160)

    ov = tile.copy()
    cv2.rectangle(ov, (0, 0), (TILE_W, 36), (0, 0, 0), -1)
    cv2.addWeighted(ov, 0.55, tile, 0.45, 0, tile)
    cv2.putText(tile, label,  (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6,  (0, 255, 0), 2)
    cv2.putText(tile, status, (8, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.45, s_col,       1)

    return tile, all_tips, fg_area


# ── Canonical coordinate helpers ──────────────────────────────────────────────

def to_canonical(tip_px, cam_idx, homographies):
    """Project a camera-pixel tip to canonical board coords. Returns (cx,cy) or None."""
    H = homographies.get(cam_idx)
    if H is None:
        return None
    pt  = np.array([[list(tip_px)]], dtype=np.float32)
    dst = cv2.perspectiveTransform(pt, H).reshape(2)
    return (float(dst[0]), float(dst[1]))


def canonical_is_new(c_tip, scored_canonical):
    """True if this canonical position is not near any already-scored dart."""
    return all(
        math.hypot(c_tip[0] - s[0], c_tip[1] - s[1]) > CANONICAL_MATCH
        for s in scored_canonical
    )


def canonical_to_mm(c_tip):
    """Canonical (board-space pixel) → board mm (origin = bull, y-up toward 20)."""
    scale = CANONICAL_RADIUS / dartboard.DOUBLE_OUT
    return ((c_tip[0] - CANONICAL_CENTRE) / scale,
            (CANONICAL_CENTRE - c_tip[1]) / scale)


def score_canonical(c_tip, debug=False):
    """Score directly from canonical (board-space) pixel coords. Returns a Hit."""
    x_mm, y_mm = canonical_to_mm(c_tip)
    hit = dartboard.score_detail(x_mm, y_mm)
    if debug:
        r_mm  = math.sqrt(x_mm**2 + y_mm**2)
        angle = math.degrees(math.atan2(x_mm, y_mm)) % 360
        print(f"    canonical=({c_tip[0]:.0f},{c_tip[1]:.0f})  "
              f"mm=({x_mm:+.1f},{y_mm:+.1f})  r={r_mm:.1f}mm  "
              f"angle={angle:.1f}  -> ({hit.points}, '{hit.label}')")
    return hit


# ── Alignment / merged board view ─────────────────────────────────────────────

def load_alignment():
    """Load homographies from alignment.json. Returns dict {cam_idx: np.array}."""
    p = Path("alignment.json")
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return {int(k): np.array(v, dtype=np.float64) for k, v in data.items()}


def _board_diagram():
    """Draw a faint dartboard schematic on a black image."""
    img   = np.zeros((CANONICAL_SIZE, CANONICAL_SIZE, 3), dtype=np.uint8)
    c     = CANONICAL_CENTRE
    scale = CANONICAL_RADIUS / dartboard.DOUBLE_OUT

    for r_mm, col in [
        (dartboard.DOUBLE_OUT,  (50,  50, 120)),
        (dartboard.DOUBLE_IN,   (30,  30,  80)),
        (dartboard.TREBLE_OUT,  (50,  50, 120)),
        (dartboard.TREBLE_IN,   (30,  30,  80)),
        (dartboard.BULLS_R,     (0,  100, 100)),
        (dartboard.BULL_R,      (0,  100, 100)),
    ]:
        cv2.circle(img, (c, c), max(1, int(r_mm * scale)), col, 1)

    for i in range(20):
        a  = math.radians(i * 18 - 9)   # segment boundaries, matching score_at
        ro = int(dartboard.DOUBLE_OUT * scale)
        cv2.line(img, (c, c),
                 (int(c + ro * math.sin(a)), int(c - ro * math.cos(a))),
                 (40, 40, 40), 1)

    for i, seg in enumerate(dartboard.SEGMENTS):
        a  = math.radians(i * 18)   # segment centres
        r  = int(dartboard.DOUBLE_IN * scale * 0.82)
        lx = int(c + r * math.sin(a))
        ly = int(c - r * math.cos(a))
        cv2.putText(img, str(seg), (lx - 8, ly + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (100, 100, 100), 1)
    return img


_DIAGRAM = None  # built once on first use


def make_merged_view(frames_by_cam, homographies,
                     scored_canonical=None, candidate_canonical=None):
    """
    Warp each camera frame to the canonical board view, blend, overlay grid.
    scored_canonical:   list of (cx,cy) in canonical space — shown as orange diamonds
    candidate_canonical: (cx,cy) in canonical space — shown as red crosshair
    """
    global _DIAGRAM
    if _DIAGRAM is None:
        _DIAGRAM = _board_diagram()

    accum   = np.zeros((CANONICAL_SIZE, CANONICAL_SIZE, 3), dtype=np.float32)
    weights = np.zeros((CANONICAL_SIZE, CANONICAL_SIZE, 1), dtype=np.float32)

    for cam_idx, frame in frames_by_cam.items():
        H = homographies.get(cam_idx)
        if H is None or frame is None:
            continue
        warped = cv2.warpPerspective(frame, H, (CANONICAL_SIZE, CANONICAL_SIZE))
        mask   = (warped.sum(axis=2, keepdims=True) > 20).astype(np.float32)
        accum  += warped.astype(np.float32) * mask
        weights += mask

    merged = (accum / np.maximum(weights, 1)).astype(np.uint8)
    merged = cv2.addWeighted(merged, 1.0, _DIAGRAM, 0.6, 0)

    if scored_canonical:
        for cx, cy in scored_canonical:
            px, py = int(cx), int(cy)
            if 0 <= px < CANONICAL_SIZE and 0 <= py < CANONICAL_SIZE:
                cv2.circle(merged, (px, py), 10, (0, 140, 255), 2)
                cv2.drawMarker(merged, (px, py), (0, 140, 255),
                               cv2.MARKER_DIAMOND, 16, 2)

    if candidate_canonical is not None:
        px, py = int(candidate_canonical[0]), int(candidate_canonical[1])
        if 0 <= px < CANONICAL_SIZE and 0 <= py < CANONICAL_SIZE:
            cv2.drawMarker(merged, (px, py), (0, 0, 255), cv2.MARKER_CROSS, 24, 3)
            cv2.circle(merged, (px, py), 12, (0, 0, 255), 2)

    return merged


# ── Main loop ──────────────────────────────────────────────────────────────────

def draw_score_bar(width, gm, dart_state, confidence):
    """Render the live X01 scoreboard strip drawn under the camera grid."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    if gm is None:
        bar = np.zeros((48, width, 3), dtype=np.uint8)
        cv2.putText(bar, "No game running", (12, 30), font, 0.6, (160, 160, 160), 1)
        return bar

    with GAME_LOCK:
        st = gm.to_dict()

    players = st["players"]
    bar_h   = 64 + len(players) * 24
    bar     = np.zeros((bar_h, width, 3), dtype=np.uint8)

    # Per-player rows
    for i, p in enumerate(players):
        active = (i == st["current"]) and not st["over"]
        col    = (0, 255, 120) if active else (170, 170, 170)
        y      = 24 + i * 24
        prefix = ">" if active else " "
        cv2.putText(bar, f"{prefix} {p['name']}", (12, y), font, 0.6, col, 2 if active else 1)
        cv2.putText(bar, f"{p['score']:>3}", (220, y), font, 0.7, col, 2 if active else 1)
        cv2.putText(bar, f"L{p['legs']} S{p['sets']}  {p['avg']:.0f} avg",
                    (290, y), font, 0.45, col, 1)

    y = 30 + len(players) * 24
    # This visit
    visit = "  ".join(f"{d['label']}" for d in st["turn"]) or "-"
    cv2.putText(bar, f"Visit: {visit} ({st['turn_points']})", (12, y), font, 0.5,
                (0, 220, 255), 1)
    # Checkout suggestion
    if st["checkout"]:
        co = " ".join(st["checkout"])
        cv2.putText(bar, f"Checkout: {co}", (max(360, width // 2), y), font, 0.5,
                    (0, 255, 180), 2)

    y += 24
    state_col = {"watching": (120, 120, 120), "stabilising": (0, 200, 255),
                 "all_done": (0, 255, 0)}.get(dart_state, (120, 120, 120))
    conf = f"  conf x{confidence}" if confidence else ""
    cv2.putText(bar, f"{dart_state}{conf}", (12, y), font, 0.45, state_col, 1)
    cv2.putText(bar, "B:bull  U:undo  N:new game  R:bg", (max(360, width // 2), y),
                font, 0.4, (90, 90, 90), 1)
    if st["over"]:
        cv2.putText(bar, st["message"], (12, y), font, 0.6, (0, 255, 120), 2)
    return bar


def _setup_logging():
    """Mirror all stdout to darts.log (appended each run)."""
    import sys as _sys
    log_path = Path("darts.log")

    class _Tee:
        def __init__(self, *streams):
            self._s = streams
        def write(self, data):
            for s in self._s:
                try:
                    s.write(data)
                except Exception:
                    pass
        def flush(self):
            for s in self._s:
                try:
                    s.flush()
                except Exception:
                    pass

    f = open(log_path, "a")
    import time as _t
    f.write(f"\n{'='*60}\n{_t.strftime('%Y-%m-%d %H:%M:%S')} — session start\n")
    _sys.stdout = _Tee(_sys.__stdout__, f)


_detect_session = 0   # bumped on every new detection stream; only the latest runs
_cameras_free = threading.Event()   # set while no session is holding the cameras
_cameras_free.set()


def stream_frames(event_queue):
    # Single-active guard: opening the stream again (StrictMode remount, rapid
    # Start/Stop, a stray client) must not leave two loops scoring the same dart.
    # The newest session wins; any older loop sees the bump and exits, releasing
    # its cameras.
    global _detect_session
    _detect_session += 1
    my_session = _detect_session
    print(f"Starting dart detection stream (session {my_session})...")

    # Wait for any previous session to fully release the USB cameras before we
    # open them. Opening a still-busy device yields a reader that never produces
    # frames, which used to stall background capture forever ("not finding
    # cameras"). The previous holder sets _cameras_free in its finally block.
    if not _cameras_free.wait(timeout=8):
        print(f"Session {my_session}: timed out waiting for previous camera release — opening anyway.")
    if my_session != _detect_session:
        print(f"Session {my_session} superseded before opening cameras — exiting.")
        return
    _cameras_free.clear()

    readers = [CameraReader(i).start() for i in CAMERAS]
    time.sleep(2.0)

    # Yield "keep board empty" frames during the ~9-second capture window so the
    # browser shows a live signal and the user knows NOT to throw yet.
    for _ci, reader in enumerate(readers):
        for _fi in range(8):   # ~0.25s of frames per camera while it warms up
            msg_img = np.zeros((TILE_H * 2, TILE_W * 3, 3), dtype=np.uint8)
            label = f"Capturing background — camera {_ci + 1} of {len(readers)}..."
            cv2.putText(msg_img, "KEEP BOARD EMPTY", (60, TILE_H - 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 220, 255), 3)
            cv2.putText(msg_img, label, (60, TILE_H),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 180, 180), 2)
            ret, buf = cv2.imencode('.jpg', msg_img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            if ret:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + buf.tobytes() + b'\r\n')
            time.sleep(0.12)

    homographies = load_alignment()
    if homographies:
        print(f"Alignment loaded for cameras: {sorted(homographies.keys())} — board view enabled")
    else:
        print("No alignment.json found — run './start.sh align' to enable merged board view")

    backgrounds, rois, board_info = capture_background(readers, homographies=homographies)
    # Drop any camera that produced no background (skipped on timeout) so the
    # detection loop below — which indexes backgrounds[reader.index] — only ever
    # sees cameras that are actually delivering frames.
    dead = [r for r in readers if r.index not in backgrounds]
    for r in dead:
        r.stop()
    readers = [r for r in readers if r.index in backgrounds]
    if not readers:
        print("No cameras delivered frames — aborting detection stream.")
        _cameras_free.set()
        return
    # Per-dart detection references: start equal to the empty board, then have
    # each scored dart absorbed into them so the next dart is the only diff.
    bg_detect = {i: b.copy() for i, b in backgrounds.items()}
    bg_refresh_pending = False

    # After capture, check if something is already in the board (dart thrown too
    # early). High fg means the background includes the dart — warn visually.
    _post_fg = []
    for reader in readers:
        f = reader.get_frame()
        if f is not None:
            g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(g, backgrounds[reader.index])
            _, m = cv2.threshold(diff, DIFF_THRESH, 255, cv2.THRESH_BINARY)
            _post_fg.append(int(cv2.countNonZero(m)))
    if _post_fg and max(_post_fg) > 500:
        print(f"WARNING: board may not have been empty during capture "
              f"(post-capture fg={max(_post_fg)}). Press R to recapture.")
        for _ in range(20):   # show warning for ~2s
            warn_img = np.zeros((TILE_H * 2, TILE_W * 3, 3), dtype=np.uint8)
            cv2.putText(warn_img, "BOARD NOT EMPTY DURING CAPTURE!", (40, TILE_H - 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 60, 255), 3)
            cv2.putText(warn_img, "Press R to recapture background", (40, TILE_H + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 180, 255), 2)
            ret, buf = cv2.imencode('.jpg', warn_img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            if ret:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + buf.tobytes() + b'\r\n')
            time.sleep(0.1)

    bull_path = Path("bull_reference.json")

    bull_ref = {}
    if bull_path.exists():
        bull_ref = {int(k): tuple(v) for k, v in json.loads(bull_path.read_text()).items()}
        print(f"Loaded bull reference for cameras: {list(bull_ref.keys())}")

    if GAME is None:
        new_game()
    # players may be plain names or per-player config dicts ({"name", "is_ai", ...})
    _names = [p["name"] if isinstance(p, dict) else str(p) for p in GAME_CONFIG['players']]
    print(f"Game ready: {GAME_CONFIG['start_score']} "
          f"({'double-out' if GAME_CONFIG['double_out'] else 'straight-out'}) "
          f"— players: {', '.join(_names)}")

    dart_state                = "watching"
    scored_canonical          = []
    candidate_canonical       = None
    candidate_n_cams          = 0
    candidate_max_n_cams      = 0
    candidate_absent_since    = None
    last_seen                 = 0.0
    empty_frames              = 0
    game_was_over             = False
    turn_points               = 0
    last_alldone_log          = 0.0
    fg_quiet                  = None    # slow baseline of the foreground level
    last_arrival              = 0.0     # when fg last arose (a dart landed)
    last_fg_log               = 0.0
    post_score_cooldown_until = 0.0     # end of fast-settle window after each score
    fg_all_done_peak          = 0       # peak fg seen during current all_done phase
    known_game_gen            = STATUS["game_gen"]   # detect API-triggered game changes

    try:
        while True:
            if my_session != _detect_session:
                print(f"Detection session {my_session} superseded — exiting.")
                break

            # If the game was replaced or ended via the API, flush all per-turn
            # state so we start clean rather than carrying stale dart positions.
            if STATUS["game_gen"] != known_game_gen:
                known_game_gen         = STATUS["game_gen"]
                scored_canonical       = []
                candidate_canonical    = None
                candidate_n_cams       = 0
                candidate_max_n_cams   = 0
                candidate_absent_since = None
                dart_state                = "watching"
                turn_points               = 0
                fg_quiet                  = None   # will re-seed from max_fg this iteration
                last_arrival              = 0.0
                post_score_cooldown_until = 0.0
                fg_all_done_peak          = 0
                bg_detect = {i: b.copy() for i, b in backgrounds.items()}
                bg_refresh_pending = False
                print("Game changed via API — detection state reset.")

            tiles           = []
            now             = time.monotonic()
            all_tips_by_cam = {}
            frames_by_cam   = {}
            max_fg          = 0

            for reader in readers:
                frame = reader.get_frame()
                if frame is None:
                    tiles.append(np.zeros((TILE_H, TILE_W, 3), dtype=np.uint8))
                    continue

                frames_by_cam[reader.index] = frame
                tile, detected_tips, fg = draw_tile(
                    frame, bg_detect[reader.index], rois[reader.index],
                    reader.index, is_candidate_cam=(dart_state == "stabilising"),
                    empty_background=backgrounds[reader.index],
                )
                tiles.append(tile)
                all_tips_by_cam[reader.index] = detected_tips
                max_fg = max(max_fg, fg)

            STATUS["phase"] = dart_state
            STATUS["awaiting_clear"] = (dart_state == "all_done")

            # Foreground-rise detection: did a new object just land? (vs static noise)
            if fg_quiet is None:
                fg_quiet = float(max_fg)
            arrived = max_fg > fg_quiet + FG_RISE_DELTA
            if arrived:
                last_arrival = now
            # Advance the quiet baseline:
            # • Empty board while watching: slow EMA back to empty level.
            # • Post-score cooldown: fast EMA so fg_quiet tracks the arm withdrawing
            #   and settles at the dart-in-board level.  Once it settles, the next
            #   real dart needs to push fg above the NEW (dart-in-board) baseline,
            #   which closes the arrival gate between consecutive darts.
            # • Otherwise (darts in board, outside cooldown): no update — we don't
            #   want the baseline to creep up and mask the third dart.
            if dart_state == "watching" and not scored_canonical:
                fg_quiet += FG_QUIET_ALPHA * (max_fg - fg_quiet)
            elif now < post_score_cooldown_until:
                fg_quiet += FG_SETTLE_ALPHA * (max_fg - fg_quiet)
            recent_arrival = (now - last_arrival) < ARRIVAL_WINDOW

            if now - last_fg_log > 1.0:
                last_fg_log = now
                settling = now < post_score_cooldown_until
                print(f"    [fg] max_fg={max_fg} quiet={fg_quiet:.0f} "
                      f"arrived={arrived} recent={recent_arrival} "
                      f"settling={settling} phase={dart_state}")

            # Absorb the just-scored dart into the detection references once
            # the post-score cooldown has passed and the arm has withdrawn
            # (fg back near baseline). From then on the next dart is the ONLY
            # foreground object — clean contours, clean cross-camera consensus.
            if (bg_refresh_pending and dart_state == "watching"
                    and now >= post_score_cooldown_until and not arrived):
                for r in readers:
                    f = r.get_frame()
                    if f is not None:
                        bg_detect[r.index] = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                bg_refresh_pending = False
                print("    [bg] detection reference refreshed — scored darts absorbed")

            # Check for empty board to heal background
            if dart_state in ["watching", "all_done"] and not scored_canonical:
                empty_frames += 1
                if empty_frames > 30: # 1 second empty
                    # Slowly blend background to adapt to lighting.
                    # Backgrounds are single-channel uint8, so convert the live
                    # frame to grayscale and blend in uint8 space (accumulateWeighted
                    # would need a float dst and matching channels).
                    for r in readers:
                        f = r.get_frame()
                        if f is not None:
                            g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                            backgrounds[r.index] = cv2.addWeighted(
                                backgrounds[r.index], 0.95, g, 0.05, 0)
                            # Board is empty, so the detection reference is
                            # just the (healed) empty board again.
                            bg_detect[r.index] = backgrounds[r.index].copy()
            else:
                empty_frames = 0

            if dart_state == "watching":
                # Phantom guard: only look for a new dart if the foreground recently
                # rose (something physically landed). A static board with reflections
                # never rises, so it can't produce a phantom score.
                if not recent_arrival:
                    candidate_canonical = None
                else:
                    candidate_canonical, candidate_cams = find_consensus_tip(all_tips_by_cam, homographies, scored_canonical)
                    if candidate_canonical:
                        candidate_max_n_cams = len(candidate_cams)
                        if candidate_max_n_cams >= MIN_CAMS_TO_TRIGGER:
                            dart_state = "stabilising"
                            stable_frames = 1
                            consensus_frames = 1
                            candidate_absent_since = None
                            stabilising_since = time.time()
                            print(f"Potential dart detected! Stabilising... (1/{STABLE_FRAMES})  "
                                  f"fg={max_fg} quiet={fg_quiet:.0f}")

            elif dart_state == "stabilising":
                # Timeout if we've been stuck in stabilising for over 2 seconds (flickering ghost dart)
                if time.time() - stabilising_since > 2.0:
                    print("Stabilising timed out (ghost dart). Reverting to watching.")
                    dart_state = "watching"
                    candidate_canonical = None
                else:
                    result = find_consensus_tip(all_tips_by_cam, homographies, scored_canonical)
                    if not result[0]:
                        if candidate_absent_since is None:
                            candidate_absent_since = time.time()
                        elif time.time() - candidate_absent_since > CANDIDATE_GRACE:
                            dart_state             = "watching"
                            candidate_canonical    = None
                            candidate_n_cams       = 0
                            candidate_max_n_cams   = 0
                            candidate_absent_since = None
                    else:
                        candidate_absent_since = None
                        avg_c, c_set = result
                        n_cams = len(c_set)
                        dist_c = math.hypot(avg_c[0] - candidate_canonical[0], avg_c[1] - candidate_canonical[1])
                        blend = 0.35
                        candidate_canonical = (
                            blend * avg_c[0] + (1 - blend) * candidate_canonical[0],
                            blend * avg_c[1] + (1 - blend) * candidate_canonical[1],
                        )
                        candidate_n_cams     = n_cams
                        candidate_max_n_cams = max(candidate_max_n_cams, n_cams)

                        if dist_c >= CANONICAL_JUMP:
                            stable_frames = 1
                            consensus_frames = 1 if n_cams >= MIN_CAMS_TO_TRIGGER else 0
                        else:
                            stable_frames += 1
                            if n_cams >= MIN_CAMS_TO_TRIGGER:
                                consensus_frames += 1

                        if stable_frames >= STABLE_FRAMES:
                            cx, cy   = candidate_canonical
                            scale    = CANONICAL_RADIUS / dartboard.DOUBLE_OUT
                            r_mm     = math.hypot(cx - CANONICAL_CENTRE, cy - CANONICAL_CENTRE) / scale
                            # consensus_frames counts how many stabilising frames
                            # had >= MIN_CAMS_TO_TRIGGER cameras agreeing on this
                            # position. A phantom (throwing arm passing through)
                            # only racks up a couple before the arm withdraws; a
                            # real dart accumulates them steadily. This replaces
                            # the old "multi-cam on the exact scoring frame" rule,
                            # which dropped real darts whenever one camera
                            # flickered at the wrong moment.
                            in_board = (0 <= cx <= CANONICAL_SIZE and 0 <= cy <= CANONICAL_SIZE
                                        and r_mm <= dartboard.DOUBLE_OUT * 1.2
                                        and consensus_frames >= CONSENSUS_FRAMES_TO_SCORE)
                            # Alignment drift can project a dart that is physically
                            # inside the board to slightly outside CANONICAL_RADIUS.
                            # Clamp outward-projecting tips back onto the double ring
                            # so score_canonical returns the correct segment rather
                            # than MISS (0 pts), which would otherwise silently drop
                            # a real dart.
                            if in_board and r_mm > dartboard.DOUBLE_OUT:
                                r_c = math.hypot(cx - CANONICAL_CENTRE, cy - CANONICAL_CENTRE)
                                s = CANONICAL_RADIUS / r_c
                                cx = CANONICAL_CENTRE + (cx - CANONICAL_CENTRE) * s
                                cy = CANONICAL_CENTRE + (cy - CANONICAL_CENTRE) * s
                                candidate_canonical = (cx, cy)
                                r_mm = dartboard.DOUBLE_OUT
                            # Final-position dedup: individual tips are filtered by
                            # distance, but their *average* can drift back next to an
                            # already-scored dart and double-count it. Re-check the
                            # smoothed result before committing.
                            is_dup = not canonical_is_new(candidate_canonical, scored_canonical)
                            hit = score_canonical(candidate_canonical, debug=True) if in_board else None
                            turn_over = False
                            # Only register tips that land in a *scoring* region. A
                            # consensus tip outside the board (a "Miss") is almost
                            # always a phantom cluster — flight ends or arm motion —
                            # not a thrown dart, so we drop it instead of scoring 0.
                            if hit is not None and hit.points > 0 and not is_dup:
                                pos_mm = canonical_to_mm(candidate_canonical)
                                with GAME_LOCK:
                                    active = GAME
                                if active is None:
                                    # Game was ended via the API while we were stabilising.
                                    print("  No active game — dart dropped")
                                else:
                                    scored_canonical.append(candidate_canonical)
                                    # Jump fg baseline to dart-in-board level so the
                                    # arrival gate closes immediately.  The fast EMA
                                    # then tracks the arm withdrawing over the next
                                    # POST_SCORE_SETTLE_SECS so the baseline settles
                                    # at the true dart-in-board level before the next
                                    # dart can be scored.
                                    fg_quiet = float(max_fg)
                                    post_score_cooldown_until = now + POST_SCORE_SETTLE_SECS
                                    # Absorb this dart into the detection
                                    # references once the arm has withdrawn.
                                    bg_refresh_pending = True
                                    with GAME_LOCK:
                                        ev = GAME.record_hit(hit, pos_mm)
                                    print(f"  Dart {len(scored_canonical)}: {hit.label} "
                                          f"({hit.points})  [{candidate_max_n_cams} cams]  {ev['message']}")
                                    if not ev["bust"]:
                                        turn_points += hit.points
                                    turn_over = ev["turn_over"]
                                    if turn_over and not ev["bust"] and not ev["leg_won"] and not ev["match_won"]:
                                        with GAME_LOCK:
                                            rem = GAME.player.score
                                            co  = GAME.checkout_hint()
                                        print(f"  Turn total {turn_points}, requires {rem}"
                                              + (f"  ({' '.join(co)})" if co else ""))
                            elif is_dup:
                                print(f"    Dropped duplicate — within {CANONICAL_MATCH}px "
                                      f"of an already-scored dart (same dart re-detected)")
                            else:
                                print(f"    Dropped phantom (r={r_mm:.0f}mm, "
                                      f"{candidate_max_n_cams} cams) — not a scoring hit")
                            candidate_canonical    = None
                            candidate_n_cams       = 0
                            candidate_max_n_cams   = 0
                            candidate_absent_since = None
                            if turn_over or len(scored_canonical) >= 3:
                                dart_state       = "all_done"
                                last_seen        = now
                                fg_all_done_peak = max_fg
                                print("  Turn complete — REMOVE the darts from the "
                                      "board to start the next turn.")
                            else:
                                dart_state = "watching"

            elif dart_state == "all_done":
                # Track fg peak so we can detect a large drop (darts removed) even
                # when the background has drifted.  Lighting drift creeps up slowly;
                # physically pulling 3 darts out drops fg by thousands in under a
                # second.  We clear on EITHER:
                #   (a) absolute level < EMPTY_FG (normal case, no drift), or
                #   (b) current fg has dropped >10 000 below the peak seen so far
                #       in this all_done phase (drift-robust case).
                fg_all_done_peak = max(fg_all_done_peak, max_fg)
                board_clear = (max_fg < EMPTY_FG or
                               fg_all_done_peak - max_fg > 10_000)
                if now - last_alldone_log > 1.0:
                    last_alldone_log = now
                    print(f"    [all_done] waiting for board to clear — "
                          f"fg={max_fg} (clear when <{EMPTY_FG})")
                if not board_clear:
                    last_seen = now
                elif now - last_seen >= ABSENT_SECS:
                    # Board cleared — the engine already advanced to the next
                    # player; announce who is up and what they need.
                    scored_canonical     = []
                    candidate_n_cams     = 0
                    candidate_max_n_cams = 0
                    dart_state           = "watching"
                    last_seen            = 0.0
                    empty_frames         = 0
                    turn_points          = 0
                    # Board is empty again — detection diffs the empty board
                    # until the first dart of the next visit scores.
                    bg_detect = {i: b.copy() for i, b in backgrounds.items()}
                    bg_refresh_pending = False
                    with GAME_LOCK:
                        if GAME and not GAME.over:
                            p  = GAME.player
                            co = GAME.checkout_hint()
                            print(f"Up next: {p.name} requires {p.score}"
                                  + (f"  ({' '.join(co)})" if co else ""))
                            pass  # frontend handles next-player announcement

            # History saving has been moved to server.py to ensure it saves even if the stream is not actively being viewed.
            game_was_over = GAME.over if GAME else False

            grid = np.hstack(tiles)
            for i, reader in enumerate(readers):
                if reader.index in bull_ref:
                    bx, by = bull_ref[reader.index]
                    sx, sy = TILE_W / 1280, TILE_H / 720
                    cv2.drawMarker(grid, (i * TILE_W + int(bx * sx), int(by * sy)), (0, 255, 255), cv2.MARKER_STAR, 16, 2)

            confidence = candidate_n_cams if dart_state == "stabilising" else 0

            # Bottom panel: merged board view (all cameras warped into board space
            # — a live alignment check: the rings should overlap cleanly) beside
            # the scoreboard strip.
            PANEL_H = 300
            if homographies:
                merged = make_merged_view(frames_by_cam, homographies,
                                          scored_canonical, candidate_canonical)
                merged_small = cv2.resize(merged, (PANEL_H, PANEL_H))
                cv2.putText(merged_small, "Board (cameras overlaid)", (8, 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            else:
                merged_small = np.zeros((PANEL_H, PANEL_H, 3), dtype=np.uint8)
                cv2.putText(merged_small, "no alignment", (20, PANEL_H // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 120, 120), 1)

            sb     = draw_score_bar(grid.shape[1] - PANEL_H, GAME, dart_state, confidence)
            panel  = np.zeros((PANEL_H, grid.shape[1] - PANEL_H, 3), dtype=np.uint8)
            panel[:min(PANEL_H, sb.shape[0])] = sb[:min(PANEL_H, sb.shape[0])]
            bottom = np.hstack([merged_small, panel])
            display = np.vstack([grid, bottom])

            # Process Web Events
            while event_queue:
                ev = event_queue.pop(0)
                evt_type = ev.get('type')
                if evt_type == 'keydown':
                    key = ev.get('key', '').lower()
                    if key == 'r':
                        backgrounds, rois, board_info = capture_background(
                            readers, homographies=homographies)
                        bg_detect = {i: b.copy() for i, b in backgrounds.items()}
                        bg_refresh_pending = False
                    elif key == 'n':
                        new_game()
                        scored_canonical = []
                        candidate_canonical, candidate_n_cams, candidate_max_n_cams = None, 0, 0
                        candidate_absent_since, dart_state = None, "watching"
                        fg_quiet = float(max_fg)
                        last_arrival = 0.0
                        turn_points = 0
                        post_score_cooldown_until = 0.0
                        bg_detect = {i: b.copy() for i, b in backgrounds.items()}
                        bg_refresh_pending = False
                    elif key == 'u':
                        # Undo the last scored dart (misread correction).
                        with GAME_LOCK:
                            undone = GAME.undo()
                        if undone:
                            if scored_canonical:
                                scored_canonical.pop()
                            candidate_canonical, candidate_n_cams, candidate_max_n_cams = None, 0, 0
                            candidate_absent_since, dart_state = None, "watching"
                            say("Undo")
                    elif key == 'b':
                        tips_now = {}
                        for reader in readers:
                            f = reader.get_frame()
                            if f is None: continue
                            darts, _ = detect_all_darts(f, backgrounds[reader.index], rois[reader.index])
                            if darts: tips_now[reader.index] = darts[0][0]
                        if tips_now:
                            bull_ref.update(tips_now)
                            bull_path.write_text(json.dumps(bull_ref))

            ret, buffer = cv2.imencode('.jpg', display, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret:
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            time.sleep(0.03)

    finally:
        for r in readers:
            r.stop()
        # Signal the next session that the cameras are free to be re-opened.
        _cameras_free.set()

def main():
    pass

if __name__ == "__main__":
    main()
