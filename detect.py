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
import line_tips
from debug_recorder import recorder as dbg

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
    "debug":       False,    # record this match for debugging (video + telemetry)
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
    # Start a fresh debug recording for the new match (or stop any running one).
    if GAME_CONFIG.get("debug"):
        names = [p["name"] if isinstance(p, dict) else str(p)
                 for p in GAME_CONFIG["players"]]
        dbg.start(meta={
            "players": names,
            "start_score": GAME_CONFIG["start_score"],
            "double_in": GAME_CONFIG["double_in"],
            "double_out": GAME_CONFIG["double_out"],
            "legs_to_win": GAME_CONFIG["legs_to_win"],
            "sets_to_win": GAME_CONFIG["sets_to_win"],
            "tuning": {
                "DIFF_THRESH": DIFF_THRESH, "MIN_DART_AREA": MIN_DART_AREA,
                "MAX_DART_AREA": MAX_DART_AREA, "MIN_CAMS_TO_TRIGGER": MIN_CAMS_TO_TRIGGER,
                "CONFIRM_FRAMES": CONFIRM_FRAMES,
                "CONFIRM_CONSENSUS_FRAMES": CONFIRM_CONSENSUS_FRAMES,
                "CONFIRM_MIN_CAMS": CONFIRM_MIN_CAMS,
                "PENDING_GRACE_FRAMES": PENDING_GRACE_FRAMES,
                "CANONICAL_CLUSTER": CANONICAL_CLUSTER, "CANONICAL_JUMP": CANONICAL_JUMP,
                "CLUSTER_TIGHT": CLUSTER_TIGHT, "CLUSTER_TIGHT_3CAM": CLUSTER_TIGHT_3CAM,
                "FG_SETTLE_DELTA": FG_SETTLE_DELTA, "FG_STABLE_FRAMES": FG_STABLE_FRAMES,
                "MAX_SCORE_CONTOURS": MAX_SCORE_CONTOURS,
                "FG_RISE_DELTA": FG_RISE_DELTA, "EMPTY_FG": EMPTY_FG,
                "CLEAR_FRACTION": CLEAR_FRACTION,
                "CLEAR_SETTLE_SECS": CLEAR_SETTLE_SECS, "ABSENT_SECS": ABSENT_SECS,
            },
        })
    else:
        dbg.stop()
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
# After the board is cleared, hold detection off this long so the board can
# stop vibrating from the darts being yanked out (vibration looks like a dart)
CLEAR_SETTLE_SECS = 1.5
# Candidate tip may disappear this long (seconds) before we give up on it
CANDIDATE_GRACE = 0.5

# Detection tuning
DIFF_THRESH   = 25    # pixel intensity change to count as foreground
MIN_DART_AREA = 120   # minimum contour area
MAX_DART_AREA = 8000  # maximum for a SQUAT blob (ignore hand/arm/lighting washes)
# A camera viewing the board edge-on sees several grouped darts STACK into one
# elongated contour far larger than a single dart (e.g. cam1 on a top-of-board
# cluster: ~18k px, aspect ~4). Capping every contour at MAX_DART_AREA made that
# camera go blind on grouped darts — it contributed nothing and the cluster
# collapsed to 2-camera, where a flight end can mis-triangulate. A merged-dart
# blob stays linear (high aspect), so it gets a looser ceiling; a genuine arm/
# lighting wash is squat (low aspect) and is still held to MAX_DART_AREA. The
# single fitted line through such a blob ends at the true tip cluster, so it
# still feeds a usable tip to the cross-camera consensus.
MAX_MERGED_DART_AREA = 25000  # ceiling for an ELONGATED (aspect >= MERGED_ASPECT) blob
MERGED_ASPECT        = 2.5     # above this a large contour reads as stacked darts, not a wash

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
# Max px between two cameras' views of the SAME dart — alignment won't be perfect.
# This is the loose *association* radius used to gather a cluster.
CANONICAL_CLUSTER = 55
# A confirmed cluster must also be TIGHT: its members must agree within this many
# px of the cluster centre. A real tip (all cameras' rays meeting at the board
# plane) is tight ≈ alignment error; a flight-end or noise coincidence that merely
# falls inside CANONICAL_CLUSTER is looser and gets rejected. The allowance is
# camera-count dependent: full 3-camera agreement (strong evidence of a real
# triangulated tip) tolerates a looser spread, because alignment error grows toward
# the board edges and real edge darts legitimately spread ~40px; a 2-camera cluster
# must be tight, since a loose 2-camera match is the flight/noise-phantom signature.
# Raise CLUSTER_TIGHT_3CAM if real edge darts are dropped; lower if phantoms slip in.
CLUSTER_TIGHT      = 32   # 2-camera clusters
CLUSTER_TIGHT_3CAM = 50   # full 3-camera clusters
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

# ── Multi-dart tracker ──────────────────────────────────────────────────────
# The detector diffs every camera against the EMPTY board and clusters all tips
# in canonical space, so every dart on the board is localised at once (no
# one-at-a-time absorb-and-wait). A cluster that is new (not near an
# already-scored dart) and persists is confirmed and scored. This is cadence
# independent: three darts thrown in a second are each their own cluster.
#
# A new dart must be tracked for this many consecutive frames before it scores
# (debounce against flicker / a dart in flight). ~0.25s at 30fps.
CONFIRM_FRAMES = 7
# …and seen by >= MIN_CAMS_TO_TRIGGER cameras on at least this many of them.
CONFIRM_CONSENSUS_FRAMES = 4
# A pending candidate may go unseen this many frames before we forget it.
PENDING_GRACE_FRAMES = 5
# A confirmed dart must have been seen TIGHTLY by at least this many cameras at
# some point (capped at the number of cameras present). Set to 2 (not 3): on this
# rig one camera intermittently fails to detect a dart that is plainly visible, so
# requiring full 3-camera agreement silently dropped real darts. Two cameras is
# enough to triangulate the tip; flight-end / edge phantoms are held back instead
# by the tightness, current-support (cur_cams) and CONSECUTIVE-consensus gates
# (every phantom observed flickered, so a consecutive multi-camera streak rejects
# them). Raise back to 3 if alignment/detection improve enough that real darts are
# reliably seen by all three.
CONFIRM_MIN_CAMS = 2
# Arrival-isolation dedup-bypass (lets a 2nd dart score within CANONICAL_MATCH of an
# already-scored one — see step_tracker's arrival path). DISABLED by default: it is a
# tracker heuristic that trades a narrow touching-darts win for a double-count risk,
# and the reliability work is being refocused on per-camera DETECTION + a camera-count
# confidence model, not more tracker gates. The machinery + its replay tests remain so
# it can be re-enabled if a specific repeatable case justifies it.
ARRIVAL_DEDUP_BYPASS = False
# ── Confidence model ──────────────────────────────────────────────────────────
# A dart's confidence is its CAMERA COUNT, never its triangulation spread: two
# warped shaft lines always intersect EXACTLY (spread 0), so spread says nothing
# about a 2-camera read's correctness — it is geometrically unconstrained and can
# sit anywhere a single camera's error allows. Only 3-camera agreement pins the tip.
CONF_CONFIRMED   = "confirmed"     # >=3 cameras — auto-score
CONF_PROVISIONAL = "provisional"   # exactly 2 cameras — unconstrained, low confidence
CONF_LOW         = "low"           # <=1 camera — cannot triangulate


def dart_confidence(n_cams):
    """Classify a dart by how many cameras saw it (NOT by spread). Returns
    (level, reason). 3+ = confirmed, 2 = provisional (unconstrained), <=1 = low."""
    if n_cams >= 3:
        return CONF_CONFIRMED, f"{n_cams} cameras agree (triangulation constrained)"
    if n_cams == 2:
        return CONF_PROVISIONAL, "only 2 cameras — intersection is exact regardless of correctness"
    return CONF_LOW, f"{n_cams} camera — cannot triangulate"


def _camera_audit(cam_set, darts_by_cam, fg_by_cam):
    """Per-camera evidence for the detection audit log: did this camera contribute
    to the scored tip, how many candidates it saw, its foreground area, and the
    areas of its detected contours. Lets a misread/miss be traced to the camera(s)
    that failed."""
    fg_by_cam = fg_by_cam or {}
    cams = sorted(set(darts_by_cam) | set(cam_set) | set(fg_by_cam))
    audit = {}
    for cam in cams:
        darts = darts_by_cam.get(cam, [])
        audit[str(cam)] = {
            "seen": cam in cam_set,
            "candidates": len(darts),
            "fg_area": int(fg_by_cam.get(cam, 0)),
            "contour_areas": sorted(
                (int(cv2.contourArea(c)) for _p1, _p2, c in darts), reverse=True)[:5],
        }
    return audit


# Anti-phantom: a dart is only committed once the scene has SETTLED — i.e. the
# total foreground stopped changing, meaning the dart has landed and the arm /
# motion is gone. Confirming during motion is how a transient blob (e.g. an
# incoming dart's flight or arm wash) gets scored as a phantom. The frame-to-frame
# fg change must stay under FG_SETTLE_DELTA for FG_STABLE_FRAMES frames.
FG_SETTLE_DELTA  = 1500
FG_STABLE_FRAMES = 3
# Anti-phantom (contamination gate): a settled board shows only a SMALL number of
# blobs per camera — roughly one per dart present. A hand/arm reaching in to throw
# or retrieve shatters into many contours (observed: 24 in one camera at the moment
# a phantom "Double 14" was scored). The frame-to-frame fg-settle test above is
# fooled by an arm held momentarily still (high fg, low delta → "settled"), so we
# ALSO refuse to commit a score on any frame where any camera sees more than this
# many blobs. The pending persists across the contamination and scores once the arm
# is clear, so a real dart is only delayed, never lost.
MAX_SCORE_CONTOURS = 6
# Board-clear: a visit's darts read some "darts-in" fg level. The board is judged
# clear once fg drops below this fraction of that level (robust to lighting drift
# and, unlike a drop-from-peak test, NOT fooled by the arm briefly spiking fg high
# then withdrawing while the darts are still in the board).
CLEAR_FRACTION = 0.4
# Collection-based board-clear. An ABSOLUTE empty-fg threshold is fragile: a
# grazing camera (cam1 here) outlines the board's metal spider wires as a few
# thousand px of phantom foreground whenever a tiny board/camera shift desyncs it
# from its background reference, so an EMPTY board can read max_fg≈3,800 — above
# the absolute clear threshold — and the board never "clears". Instead detect the
# unmistakable RELATIVE signature of a collection (immune to that baseline offset
# because it's measured against this visit's darts-in level):
#   1. an ARM SPIKE — the player reaches in: max_fg jumps far above the darts-in
#      level (×COLLECT_SPIKE_FACTOR), and/or a contour storm appears; THEN
#   2. fg SETTLES BELOW the darts-in level — darts removed, so the settled board
#      reads lower than when the darts were in (×COLLECT_DROP_FRACTION).
COLLECT_SPIKE_FACTOR = 1.5    # max_fg above darts-in × this = a hand reaching in
COLLECT_DROP_FRACTION = 0.7   # after a spike, clear once settled max_fg < darts-in × this


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
    # Foreground-occupancy count: OPEN the mask before counting. A stale or
    # slightly-shifted background reference makes a grazing camera (cam1) diff the
    # dartboard's thin metal SPIDER WIRES into thousands of phantom px — enough to
    # defeat the board-clear / arrival gates even though the board is empty.
    # Opening (erode→dilate, 5x5) erases those thin lines while keeping the thick
    # dart blobs, so occupancy tracks real darts, not reference drift. (Measured on
    # match_20260614_110606: a stale-ref empty board 7844px → 0; a 3-dart board
    # stays ~6500.) The detection/contour `mask` below is left untouched, so this
    # does not change which shafts are detected — only the occupancy magnitude.
    fg_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    if empty_background is None:
        fg_mask = mask
    else:
        ediff = cv2.absdiff(gray, empty_background)
        _, fg_mask = cv2.threshold(ediff, DIFF_THRESH, 255, cv2.THRESH_BINARY)
        if roi is not None:
            fg_mask = cv2.bitwise_and(fg_mask, roi)
    fg_area = int(cv2.countNonZero(cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, fg_kernel)))

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    for c in contours:
        area = cv2.contourArea(c)
        if area <= MIN_DART_AREA:
            continue
        rect = cv2.minAreaRect(c)
        w, h = rect[1]
        if min(w, h) == 0:
            continue
        aspect = max(w, h) / min(w, h)
        if aspect < min_aspect:
            continue
        # Aspect-dependent area ceiling: an elongated blob can be several grouped
        # darts merged in an edge-on view (keep it — its fitted line still ends at
        # the tip), but a large SQUAT blob is an arm/lighting wash (reject).
        area_cap = MAX_MERGED_DART_AREA if aspect >= MERGED_ASPECT else MAX_DART_AREA
        if area >= area_cap:
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


def find_consensus_tips(all_tips_by_cam, homographies, min_cams=1):
    """Multi-dart consensus: cluster all cameras' tips into one cluster PER dart.

    Unlike find_consensus_tip (singular), this localises every dart on the board
    at once, so darts thrown in quick succession don't have to be processed one
    at a time. Every endpoint from every camera is projected to canonical space;
    clusters are formed greedily, densest first, each holding at most one tip per
    camera (the nearest to the seed). A dart's flight end sits ~10cm above the
    board, so it projects to inconsistent canonical coords across cameras and
    fails to cluster — only the true tips (z=0) form multi-camera clusters.

    Returns a list of (avg_canonical, cam_set), strongest (most cameras) first,
    filtered to clusters seen by >= min_cams cameras.
    """
    candidates = []   # (canonical_pt, cam_idx, weight)
    for cam_idx, tips in all_tips_by_cam.items():
        if cam_idx not in homographies:
            continue
        for tip, weight in tips:
            c = to_canonical(tip, cam_idx, homographies)
            if c is not None:
                candidates.append((c, cam_idx, weight))

    used     = [False] * len(candidates)
    clusters = []
    while not all(used):
        best_members, best_cams = None, set()
        for i, (ci, cam_i, _wi) in enumerate(candidates):
            if used[i]:
                continue
            cams    = {cam_i}
            members = [i]
            nearest = {}   # other cam -> (dist, idx)
            for j, (cj, cam_j, _wj) in enumerate(candidates):
                if used[j] or j == i or cam_j == cam_i:
                    continue
                d = math.hypot(ci[0] - cj[0], ci[1] - cj[1])
                if d < CANONICAL_CLUSTER and (cam_j not in nearest or d < nearest[cam_j][0]):
                    nearest[cam_j] = (d, j)
            for cam_j, (_d, j) in nearest.items():
                members.append(j)
                cams.add(cam_j)
            if best_members is None or len(cams) > len(best_cams):
                best_members, best_cams = members, cams
        if best_members is None:
            break
        for idx in best_members:
            used[idx] = True
        pts  = [(candidates[idx][0], candidates[idx][2]) for idx in best_members]
        wsum = sum(w * w for _, w in pts) or 1.0
        avg  = (sum(p[0] * w * w for p, w in pts) / wsum,
                sum(p[1] * w * w for p, w in pts) / wsum)
        # Spread = how far the farthest member sits from the cluster centre. A real
        # tip is where every camera's ray meets the board plane, so members agree
        # tightly (≈ alignment error); a flight-end / noise coincidence that merely
        # falls within the loose association radius is geometrically loose.
        spread = max((math.hypot(p[0] - avg[0], p[1] - avg[1]) for p, _ in pts),
                     default=0.0)
        clusters.append((avg, best_cams, spread))

    clusters = [c for c in clusters if len(c[1]) >= min_cams]
    clusters.sort(key=lambda c: (-len(c[1]), c[2]))   # most cameras, then tightest
    return clusters


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

    return tile, all_tips, fg_area, darts


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


_cameras_free = threading.Event()   # set while no worker is holding the cameras
_cameras_free.set()

# ── Persistent detection worker ────────────────────────────────────────────
# Detection runs in a background thread that owns the cameras and the scoring
# state machine, independent of whether anyone is viewing the MJPEG stream. The
# stream endpoint just serves the latest annotated frame. This means:
#   • the background is captured ONCE per worker start — no re-capture (and no
#     "board not empty" poisoning) when the Live Track tab remounts or you switch
#     tabs mid-throw, and
#   • darts keep being detected while you're on the Dashboard / cinematic view.
# Cameras are an exclusive resource shared with the Align/Cameras tabs, so those
# call stop_detection() to take the hardware; detection restarts when Live Track
# is opened again.
DETECT_EVENTS  = []                     # web input events (keydown, etc.)
_latest_jpeg   = None                   # most recent annotated frame (JPEG bytes)
_latest_lock   = threading.Lock()
_worker_thread = None
_worker_stop   = threading.Event()      # set to ask the worker loop to exit
_worker_lock   = threading.Lock()       # guards start/stop


def _publish_jpeg(data):
    global _latest_jpeg
    with _latest_lock:
        _latest_jpeg = data


def _publish(display):
    """Record (if debugging) and store an annotated BGR frame for the stream."""
    dbg.frame(display)
    ok, buf = cv2.imencode('.jpg', display, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if ok:
        _publish_jpeg(buf.tobytes())


def detection_running():
    return _worker_thread is not None and _worker_thread.is_alive()


def start_detection():
    """Start the background detection worker if it isn't already running."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_stop.clear()
        _worker_thread = threading.Thread(
            target=_run_detection, args=(DETECT_EVENTS,), daemon=True)
        _worker_thread.start()


def stop_detection():
    """Stop the detection worker and wait for it to release the cameras."""
    global _worker_thread
    with _worker_lock:
        t = _worker_thread
        _worker_thread = None
    if t is not None and t.is_alive():
        _worker_stop.set()
        t.join(timeout=10)


def stream_frames(event_queue=None):
    """Thin MJPEG generator: ensure detection is running and serve its frames.

    Does NOT own the cameras or stop the worker on disconnect — closing the
    browser tab just detaches this viewer; the detection worker keeps running.
    """
    start_detection()
    blank = None
    while True:
        with _latest_lock:
            data = _latest_jpeg
        if data is None:
            if blank is None:
                img = np.zeros((TILE_H, TILE_W, 3), dtype=np.uint8)
                cv2.putText(img, "Starting detection...", (40, TILE_H // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 180, 180), 2)
                ok, b = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                blank = b.tobytes() if ok else b""
            data = blank
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + data + b'\r\n')
        time.sleep(0.03)


class TrackerState:
    """All per-loop mutable state for the dart tracker / scoring state machine.

    Factored out of _run_detection so the SAME stepper (step_tracker) drives both
    the live detection loop and the offline state-machine replay
    (replay_state.py) — one source of truth, so replay can't drift from live
    behaviour. A fresh TrackerState is also what each new game / board-clear
    effectively resets to.
    """
    def __init__(self, n_cams):
        self.dart_state         = "watching"   # "watching" (tracking) or "all_done"
        self.scored_canonical   = []           # confirmed dart positions this visit
        self.pendings           = []           # candidate darts being confirmed
        self.last_seen          = 0.0
        self.empty_frames       = 0
        self.turn_points        = 0
        self.fg_quiet           = None         # slow baseline of the foreground level
        self.last_arrival       = 0.0          # when fg last arose (a dart landed)
        self.clear_settle_until = 0.0          # end of post-clear settle window
        self.fg_prev            = None         # previous frame's max_fg (settle test)
        self.fg_stable_frames   = 0            # consecutive low-fg-change frames
        self.fg_darts_in        = 0            # fg level with this visit's darts in
        self.arm_spiked         = False        # saw the collection arm reach in
        # How many cameras must tightly agree to confirm a dart (full agreement
        # when 3 cameras are present; degrades to whatever is available).
        self.confirm_min_cams   = min(CONFIRM_MIN_CAMS, n_cams)
        self.last_fg_log        = 0.0          # throttle timers
        self.last_alldone_log   = 0.0
        self.last_loose_log     = 0.0
        # Set after each commit → caller refreshes the arrival-isolation
        # reference (settle_ref) to the board WITH the just-scored darts in.
        self.want_settle_snapshot = False


def step_tracker(st, now, max_fg, shafts_by_cam, darts_by_cam, homographies,
                 game, game_lock, *, new_shafts_by_cam=None, fg_by_cam=None,
                 emit=None, say=None, heal=None, reset_bg_detect=None):
    """One frame of the dart tracker / scoring state machine (mutates `st`).

    This is the EXACT per-frame body the live loop (_run_detection) runs, factored
    out so replay_state.py can drive the real state machine offline against a
    recording's raw frames — there is ONE implementation, so replay cannot drift
    from live. Inputs:

        st                       : TrackerState (mutated in place)
        now, max_fg              : timing + foreground-occupancy this frame
        shafts_by_cam            : {cam: [(p1,p2),...]} for the line-tip finder
        darts_by_cam             : {cam: [(p1,p2,contour),...]} (contour-storm count)
        new_shafts_by_cam        : {cam: [(p1,p2),...]} from the ARRIVAL-isolation
                                   diff (current frame vs the last settled board) —
                                   only the newest dart's shafts. Lets a dart that
                                   landed touching an existing one (fused in the
                                   empty-board diff) still be localised and scored,
                                   even within the scored-dedup radius (it is
                                   provably new foreground, not a re-detection).
                                   None / empty = no arrival isolation this frame.
        homographies             : {cam: 3x3 cam->canonical}
        game, game_lock          : the X01Game to score into (+ its lock)

    Effects are injected so the caller owns I/O — the live loop wires the debug
    recorder / audio / camera-frame healing; replay wires lightweight stand-ins:

        emit(kind, **fields)     : telemetry event (dbg.event live; collector in replay)
        say(text)                : audio announcement
        heal()                   : blend current frames into the bg references
        reset_bg_detect()        : reset the detection reference to the empty board
    """
    if emit is None:            emit = lambda *a, **k: None
    if say is None:             say = lambda *a, **k: None
    if heal is None:            heal = lambda: None
    if reset_bg_detect is None: reset_bg_detect = lambda: None

    # Foreground-rise detection: did a new object just land? (vs static noise)
    if st.fg_quiet is None:
        st.fg_quiet = float(max_fg)
    arrived = max_fg > st.fg_quiet + FG_RISE_DELTA
    if arrived:
        st.last_arrival = now

    # Scene-settle: has the foreground stopped changing? A dart is only
    # committed while settled, so a transient blob during motion (incoming
    # dart / arm) can't confirm as a phantom.
    if st.fg_prev is None:
        st.fg_prev = max_fg
    if abs(max_fg - st.fg_prev) < FG_SETTLE_DELTA:
        st.fg_stable_frames += 1
    else:
        st.fg_stable_frames = 0
    st.fg_prev = max_fg
    scene_settled = st.fg_stable_frames >= FG_STABLE_FRAMES
    # Only drift the quiet baseline up while the board is empty; once any
    # dart is in the board, freeze it so it stays a true empty reference for
    # the board-clear test and the recent-arrival gate.
    if st.dart_state == "watching" and not st.scored_canonical:
        st.fg_quiet += FG_QUIET_ALPHA * (max_fg - st.fg_quiet)
    recent_arrival = (now - st.last_arrival) < ARRIVAL_WINDOW

    if now - st.last_fg_log > 1.0:
        st.last_fg_log = now
        print(f"    [fg] max_fg={max_fg} quiet={st.fg_quiet:.0f} "
              f"arrived={arrived} recent={recent_arrival} settled={scene_settled} "
              f"pending={len(st.pendings)} scored={len(st.scored_canonical)} "
              f"phase={st.dart_state}")
        emit("fg", max_fg=int(max_fg), quiet=round(st.fg_quiet, 1),
             arrived=bool(arrived), recent=bool(recent_arrival),
             settled=bool(scene_settled),
             clean=bool(max((len(d) for d in darts_by_cam.values()),
                            default=0) <= MAX_SCORE_CONTOURS),
             cam_darts={i: len(d) for i, d in darts_by_cam.items()},
             pending=len(st.pendings), scored=len(st.scored_canonical),
             phase=st.dart_state)

    # Heal the empty-board reference for lighting drift while the board is
    # empty (the injected heal() also keeps bg_detect tracking the healed
    # empty board so the next visit starts from a clean reference).
    if st.dart_state in ["watching", "all_done"] and not st.scored_canonical:
        st.empty_frames += 1
        if st.empty_frames > 30:   # ~1s empty
            heal()
    else:
        st.empty_frames = 0

    if st.dart_state == "watching":
        # Post-clear settle: the board can still be vibrating from the darts
        # being yanked out. Hold detection off and keep re-baselining so the
        # wobble can't confirm a phantom.
        if now < st.clear_settle_until:
            st.pendings     = []
            st.fg_quiet     = float(max_fg)
            st.last_arrival = 0.0
        # A dart must have landed recently (fg rose) for there to be anything
        # new to find — a static board with only reflections never rises.
        elif not recent_arrival:
            st.pendings = []
        else:
            # ── Multi-dart tracker ──────────────────────────────────────
            # Localise EVERY dart on the board this frame, match each NEW one
            # (not near an already-scored dart) to a pending candidate, and
            # confirm the ones that have persisted with camera agreement.
            # Cadence-independent: three darts in a second are three pendings.
            # Shaft-line intersection: warp each camera's whole shaft to
            # canonical and meet the lines at the board plane — far more robust
            # than clustering both endpoints (the flight end mis-triangulates).
            # Returns (pos, cams, residual) with residual playing the role of
            # the old cluster `spread`. line_tips already gates residual against
            # the SAME tight limits below (passed in here so there is ONE source
            # of truth), so the per-cluster spread re-gate that follows is a
            # harmless pass-through — kept for the loose-cluster telemetry it
            # also produces. Single-camera darts can't intersect and never
            # scored anyway (a pending needs MIN_CAMS_TO_TRIGGER to start).
            clusters = line_tips.find_tips_by_lines(
                shafts_by_cam, homographies, min_cams=MIN_CAMS_TO_TRIGGER,
                tight_2cam=CLUSTER_TIGHT, tight_3cam=CLUSTER_TIGHT_3CAM)
            # Keep only NEW clusters that are geometrically TIGHT — a loose
            # multi-camera cluster is a flight-end / noise coincidence, not a
            # real tip (this is how one dart was scoring as three). Each fresh
            # entry is (pos, cams, spread, arrival): arrival=False here (came from
            # the full empty-board diff); the arrival-isolation pass below adds
            # arrival=True entries that may bypass the scored-dedup at commit.
            fresh, loose = [], []
            for pos, cams, spread in clusters:
                if not canonical_is_new(pos, st.scored_canonical):
                    continue
                # 3-camera clusters get a looser spread allowance (alignment
                # error is larger at board edges, where real darts still earn
                # full agreement); 2-camera clusters must be tight.
                tight_limit = CLUSTER_TIGHT_3CAM if len(cams) >= 3 else CLUSTER_TIGHT
                if spread <= tight_limit:
                    fresh.append((pos, cams, spread, False))
                elif len(cams) >= MIN_CAMS_TO_TRIGGER:
                    loose.append((pos, len(cams), spread))

            # ── Arrival isolation (touching darts) ──────────────────────────
            # A dart landing next to an existing one fuses into ONE contour in
            # the empty-board diff, so the pair never separates into two tips.
            # new_shafts_by_cam comes from diffing the current frame against the
            # last SETTLED board (which already contains the scored darts), so
            # the only foreground left is the newly-arrived dart — its own clean
            # shafts. Triangulate those and add any tight cluster the empty-board
            # pass missed. Because the cluster is provably NEW foreground (not a
            # re-detection of a dart already in the settled reference), it is
            # allowed to seed a pending even WITHIN the scored-dedup radius — that
            # is the only way a 2nd dart a few px from the 1st can ever register.
            # The full-board diff above is untouched, so no detection blind spots.
            if new_shafts_by_cam:
                arr_clusters = line_tips.find_tips_by_lines(
                    new_shafts_by_cam, homographies, min_cams=MIN_CAMS_TO_TRIGGER,
                    tight_2cam=CLUSTER_TIGHT, tight_3cam=CLUSTER_TIGHT_3CAM)
                for pos, cams, spread in arr_clusters:
                    tight_limit = CLUSTER_TIGHT_3CAM if len(cams) >= 3 else CLUSTER_TIGHT
                    if spread > tight_limit:
                        continue
                    # SURGICAL: only resurrect a dart the empty-board pass would
                    # DROP as a duplicate of an already-scored dart (the touching
                    # case). A canonically-new cluster is already handled by the
                    # empty-board pass — leaving it alone here means arrival
                    # isolation never perturbs a normally-detected dart's position
                    # or camera count, only rescues one that would otherwise be lost.
                    if canonical_is_new(pos, st.scored_canonical):
                        continue
                    # Skip if an existing fresh cluster already covers this dart —
                    # avoid a double pending for one physical dart.
                    if any(math.hypot(pos[0] - fp[0], pos[1] - fp[1]) < CANONICAL_MATCH
                           for fp, _, _, _ in fresh):
                        continue
                    fresh.append((pos, cams, spread, True))
            # Log loose (rejected) multi-camera clusters so a real dart that
            # is being dropped as "too loose" is visible (→ raise CLUSTER_TIGHT
            # / improve alignment) vs a phantom correctly rejected.
            if loose and now - st.last_loose_log > 0.5:
                st.last_loose_log = now
                for lp, lc, ls in loose:
                    print(f"    [loose] rejected cluster ({lp[0]:.0f},{lp[1]:.0f}) "
                          f"{lc} cams spread={ls:.0f} > {CLUSTER_TIGHT}")
                emit("cluster_rejected",
                     clusters=[{"pos": [round(lp[0]), round(lp[1])],
                                "cams": lc, "spread": round(ls, 1)}
                               for lp, lc, ls in loose])

            for p in st.pendings:
                p["matched"] = False
            for pos, cams, spread, arrival in fresh:
                n_cams = len(cams)
                best_p, best_d = None, CANONICAL_JUMP
                for p in st.pendings:
                    if p["matched"]:
                        continue
                    d = math.hypot(pos[0] - p["pos"][0], pos[1] - p["pos"][1])
                    if d < best_d:
                        best_p, best_d = p, d
                if best_p is not None:
                    bl = 0.35   # smooth the tracked position
                    best_p["pos"] = (bl * pos[0] + (1 - bl) * best_p["pos"][0],
                                     bl * pos[1] + (1 - bl) * best_p["pos"][1])
                    best_p["seen"]    += 1
                    best_p["absent"]   = 0
                    best_p["matched"]  = True
                    best_p["max_cams"] = max(best_p["max_cams"], n_cams)
                    best_p["cur_cams"] = n_cams   # cameras agreeing THIS frame
                    best_p["cams"]     = set(cams)  # which cameras THIS frame (audit)
                    best_p["spread"]   = spread
                    # Sticky arrival flag: once a pending has been corroborated by
                    # the arrival-isolation diff it may bypass the scored-dedup —
                    # it is a genuinely new dart, not a re-detection.
                    best_p["arrival"] = best_p.get("arrival", False) or arrival
                    # consensus is a CONSECUTIVE streak of multi-camera frames,
                    # not a cumulative count: a real static dart is multi-camera
                    # every frame so it climbs fast, whereas a persistent edge
                    # artifact that's only occasionally multi-camera (mostly 1)
                    # keeps getting reset and can never accumulate enough — that
                    # was scoring a phantom after sitting for ~100 frames.
                    if n_cams >= MIN_CAMS_TO_TRIGGER:
                        best_p["consensus"] += 1
                    else:
                        best_p["consensus"] = 0
                elif n_cams >= MIN_CAMS_TO_TRIGGER:
                    # Only START tracking a candidate that >= 2 cameras agree
                    # on — a lone single-camera blip is noise (and can't be
                    # triangulated to the board plane anyway).
                    st.pendings.append({
                        "pos": pos, "seen": 1, "absent": 0, "matched": True,
                        "max_cams": n_cams, "cur_cams": n_cams, "cams": set(cams),
                        "consensus": 1, "spread": spread, "arrival": arrival,
                    })

            # Forget pendings unseen for too long (flicker / arm motion). A
            # pending not matched this frame has no current support, and its
            # consecutive-multi-camera streak is broken.
            for p in st.pendings:
                if not p["matched"]:
                    p["absent"] += 1
                    p["cur_cams"] = 0
                    p["consensus"] = 0
            st.pendings = [p for p in st.pendings if p["absent"] <= PENDING_GRACE_FRAMES]

            # Confirm + score one dart per frame, re-checking turn-over before
            # the next so a bust ignores a dart that was already in the air.
            # Gates: scene settled (never mid-motion) + persistence +
            #   • max_cams >= confirm_min_cams : reached FULL agreement at some
            #     point (rules out pure 2-camera flight phantoms), AND
            #   • cur_cams >= MIN_CAMS_TO_TRIGGER : still has real multi-camera
            #     support THIS frame. A real static dart is seen by every camera
            #     every frame; a flight-end phantom's agreement flickers and it
            #     ends up confirming on a lone 1-camera frame (spread 0) — this
            #     current-support check is what kills that, while staying lenient
            #     enough (2 cams) not to drop a real dart one camera briefly lost.
            # Contamination gate: if any camera is showing far more blobs
            # than there are darts present, a hand/arm is in the scene and
            # every cluster this frame is suspect — defer all scoring until
            # it clears. (scene_settled alone is fooled by a still arm.)
            max_cam_contours = max((len(d) for d in darts_by_cam.values()),
                                   default=0)
            scene_clean = max_cam_contours <= MAX_SCORE_CONTOURS
            ready = [p for p in st.pendings
                     if p["seen"] >= CONFIRM_FRAMES
                     and p["consensus"] >= CONFIRM_CONSENSUS_FRAMES
                     and p["max_cams"] >= st.confirm_min_cams
                     and p["cur_cams"] >= MIN_CAMS_TO_TRIGGER] \
                    if (scene_settled and scene_clean) else []
            if ready:
                # Prefer the most trustworthy candidate, NOT the longest-lived
                # one: a lingering edge artifact accumulates a high `seen` while
                # a freshly-landed real dart has a low one, so sorting by -seen
                # let the phantom win. Rank by tightest spread, then most
                # cameras, then persistence as a final tie-break.
                ready.sort(key=lambda p: (p["spread"], -p["max_cams"], -p["seen"]))
                p      = ready[0]
                st.pendings.remove(p)
                n_cams = p["max_cams"]
                cx, cy = p["pos"]
                scale  = CANONICAL_RADIUS / dartboard.DOUBLE_OUT
                r_mm   = math.hypot(cx - CANONICAL_CENTRE, cy - CANONICAL_CENTRE) / scale
                in_board = (0 <= cx <= CANONICAL_SIZE and 0 <= cy <= CANONICAL_SIZE
                            and r_mm <= dartboard.DOUBLE_OUT * 1.2)
                # Clamp a tip projected just outside the double ring (alignment
                # drift) back onto it, so a real dart isn't scored as MISS.
                if in_board and r_mm > dartboard.DOUBLE_OUT:
                    r_c = math.hypot(cx - CANONICAL_CENTRE, cy - CANONICAL_CENTRE)
                    s   = CANONICAL_RADIUS / r_c
                    cx  = CANONICAL_CENTRE + (cx - CANONICAL_CENTRE) * s
                    cy  = CANONICAL_CENTRE + (cy - CANONICAL_CENTRE) * s
                    r_mm = dartboard.DOUBLE_OUT
                pos    = (cx, cy)
                # A dart near an already-scored one is a duplicate UNLESS the
                # arrival-isolation diff proved it is new foreground (a 2nd dart
                # touching the 1st) — that evidence overrides the dedup radius.
                # Gated by ARRIVAL_DEDUP_BYPASS (off by default — the bypass is a
                # tracker heuristic with a double-count risk; see its definition).
                is_dup = (not canonical_is_new(pos, st.scored_canonical)
                          and not (p.get("arrival") and ARRIVAL_DEDUP_BYPASS))
                hit    = score_canonical(pos, debug=True) if in_board else None
                ev     = None
                # Only register tips in a *scoring* region. A consensus tip
                # outside the board is almost always a phantom (flight ends),
                # so drop it rather than score 0.
                if hit is not None and hit.points > 0 and not is_dup:
                    pos_mm = canonical_to_mm(pos)
                    active = game
                    if active is None:
                        print("  No active game — dart dropped")
                    else:
                        st.scored_canonical.append(pos)
                        st.last_arrival = now   # keep the gate open for the next dart
                        # Snapshot the settled board after this commit so the NEXT
                        # dart can be arrival-isolated against it (caller captures
                        # the current frames into settle_ref).
                        st.want_settle_snapshot = True
                        # Confidence is the CAMERA COUNT, not the spread (a 2-camera
                        # intersection is exact regardless of correctness).
                        conf, conf_reason = dart_confidence(n_cams)
                        with game_lock:
                            ev = game.record_hit(hit, pos_mm)
                        say(hit.label)
                        print(f"  Dart {len(st.scored_canonical)}: {hit.label} "
                              f"({hit.points})  [{n_cams} cams, {conf}]  {ev['message']}")
                        emit("scored", n=len(st.scored_canonical),
                             label=hit.label, points=hit.points,
                             ring=hit.ring, segment=hit.segment,
                             canonical=pos, pos_mm=pos_mm, n_cams=n_cams,
                             cur_cams=p.get("cur_cams"),
                             spread=round(p.get("spread", 0.0), 1),
                             confidence=conf, confidence_reason=conf_reason,
                             seen=p.get("seen"), consensus=p.get("consensus"),
                             max_fg=int(max_fg), bust=ev["bust"],
                             turn_over=ev["turn_over"], message=ev["message"])
                        # Detection audit: per-camera evidence behind this score, so a
                        # misread/miss can be traced to which camera(s) failed.
                        emit("dart_audit", n=len(st.scored_canonical), label=hit.label,
                             canonical=[round(pos[0]), round(pos[1])], ring=hit.ring,
                             segment=hit.segment, n_cams=n_cams, confidence=conf,
                             reason=conf_reason,
                             cameras=_camera_audit(p.get("cams", set()),
                                                   darts_by_cam, fg_by_cam))
                        if not ev["bust"]:
                            st.turn_points += hit.points
                        if ev["turn_over"] and not ev["bust"] and not ev["leg_won"] and not ev["match_won"]:
                            with game_lock:
                                rem = game.player.score
                                co  = game.checkout_hint()
                            print(f"  Turn total {st.turn_points}, requires {rem}"
                                  + (f"  ({' '.join(co)})" if co else ""))
                elif is_dup:
                    print(f"    Dropped duplicate — within {CANONICAL_MATCH}px "
                          f"of an already-scored dart")
                    emit("dropped_duplicate", canonical=pos,
                         n_cams=n_cams, max_fg=int(max_fg))
                else:
                    print(f"    Dropped phantom (r={r_mm:.0f}mm, {n_cams} cams) "
                          f"— not a scoring hit")
                    emit("dropped_phantom", canonical=pos, r_mm=round(r_mm, 1),
                         n_cams=n_cams, max_fg=int(max_fg))

                # End the visit on 3 darts, a bust, or a finished leg/match.
                if len(st.scored_canonical) >= 3 or (ev is not None and ev["turn_over"]):
                    st.dart_state  = "all_done"
                    st.last_seen   = now
                    st.fg_darts_in = 0         # measured on the first settled all_done frame
                    st.arm_spiked  = False     # await this visit's collection arm
                    st.pendings    = []
                    print("  Turn complete — REMOVE the darts from the board "
                          "to start the next turn.")

    elif st.dart_state == "all_done":
        # Measure the darts-in fg on the first SETTLED all_done frame (arm
        # gone, darts standing) — the reference for the collection detector.
        if scene_settled and st.fg_darts_in == 0 and max_fg > EMPTY_FG:
            st.fg_darts_in = max_fg
        # Collection signature, not an absolute empty level: an ABSOLUTE
        # threshold is permanently defeated when a grazing camera outlines
        # the spider wires as a few-thousand-px phantom on a board/camera
        # shift, so an empty board reads above the threshold and never
        # "clears". A collection is unmistakable RELATIVE to the darts-in
        # level (immune to that baseline offset): the arm reaches in
        # (max_fg spikes far above darts-in, and/or a contour storm), THEN
        # fg settles BELOW darts-in (darts removed → less foreground than
        # when they were in). Require the spike before trusting a low
        # settled level so the darts STANDING (a quiet level all along)
        # can't be mistaken for "collected".
        storm = max((len(d) for d in darts_by_cam.values()), default=0)
        if st.fg_darts_in and (max_fg > st.fg_darts_in * COLLECT_SPIKE_FACTOR
                               or storm > MAX_SCORE_CONTOURS):
            st.arm_spiked = True
        drop_target = int(st.fg_darts_in * COLLECT_DROP_FRACTION)
        board_clear = (
            (st.arm_spiked and scene_settled and max_fg < drop_target)
            or max_fg < EMPTY_FG)     # genuine-empty fallback (quiet full clear)
        if now - st.last_alldone_log > 1.0:
            st.last_alldone_log = now
            print(f"    [all_done] waiting for board to clear — "
                  f"fg={max_fg} darts_in={st.fg_darts_in} "
                  f"arm_spiked={st.arm_spiked} (clear when settled <{drop_target} "
                  f"after spike, or <{EMPTY_FG})")
        if not board_clear:
            st.last_seen = now
        elif now - st.last_seen >= ABSENT_SECS:
            # Board cleared — the engine already advanced to the next player.
            st.scored_canonical   = []
            st.pendings           = []
            st.dart_state         = "watching"
            st.last_seen          = 0.0
            st.empty_frames       = 0
            st.turn_points        = 0
            # The hand that pulled the darts set last_arrival a moment ago;
            # clear it and re-seed the baseline so the next wobble isn't read
            # as a fresh dart, and hold detection off until the board settles.
            st.last_arrival       = 0.0
            st.fg_quiet           = None
            st.clear_settle_until = now + CLEAR_SETTLE_SECS
            # Board empty again — reset the detection reference to the empty
            # board so the next visit's first dart is the only foreground.
            reset_bg_detect()
            emit("board_cleared", settle_secs=CLEAR_SETTLE_SECS,
                 max_fg=int(max_fg), arm_spiked=bool(st.arm_spiked),
                 darts_in=int(st.fg_darts_in))
            with game_lock:
                if game and not game.over:
                    pl = game.player
                    co = game.checkout_hint()
                    print(f"Up next: {pl.name} requires {pl.score}"
                          + (f"  ({' '.join(co)})" if co else ""))


def _run_detection(event_queue):
    # The worker owns the cameras for its whole lifetime. Wait for any previous
    # holder (a just-stopped worker, or an Align/Cameras stream) to release the
    # USB devices first — opening a still-busy device yields a reader that never
    # produces frames.
    print("Starting dart detection worker...")
    if not _cameras_free.wait(timeout=8):
        print("Detection worker: timed out waiting for camera release — opening anyway.")
    if _worker_stop.is_set():
        print("Detection worker stopped before opening cameras — exiting.")
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
            ok, buf = cv2.imencode('.jpg', msg_img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            if ok:
                _publish_jpeg(buf.tobytes())
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
    # Contour detection diffs against the empty board (`bg_detect`, tracked from
    # the lighting-healed `backgrounds`). All darts on the board are visible at
    # once — flight-end / contamination phantoms are filtered downstream by the
    # tightness + full-camera-agreement + consecutive-consensus gates, not by
    # absorbing darts into the reference (that created detection blind spots
    # around already-scored darts, so a nearby dart was seen by too few cameras).
    bg_detect = {i: b.copy() for i, b in backgrounds.items()}

    # Snapshot the inputs needed to replay this match offline (see replay.py): the
    # homographies it ran with and the empty-board backgrounds it subtracts against.
    dbg.snapshot_file("alignment.json")
    dbg.save_arrays("backgrounds.npz", backgrounds)

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
            ok, buf = cv2.imencode('.jpg', warn_img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            if ok:
                _publish_jpeg(buf.tobytes())
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

    # All per-loop tracker/scoring state lives in `st`; the per-frame body is
    # step_tracker (shared with the offline replay so they can't drift).
    st                        = TrackerState(len(readers))
    game_was_over             = False
    known_game_gen            = STATUS["game_gen"]   # detect API-triggered game changes
    # Arrival-isolation reference: the last SETTLED board (grayscale per camera)
    # WITH the visit's scored darts in. None until the first dart of a visit is
    # scored; a new dart is diffed against this so a dart touching an existing one
    # still isolates as its own foreground. See step_tracker(new_shafts_by_cam=).
    settle_ref                = None

    try:
        while True:
            if _worker_stop.is_set():
                print("Detection worker stopping — releasing cameras.")
                break

            # If the game was replaced or ended via the API, flush all per-turn
            # state so we start clean rather than carrying stale dart positions.
            if STATUS["game_gen"] != known_game_gen:
                known_game_gen         = STATUS["game_gen"]
                st.scored_canonical    = []
                st.pendings            = []
                st.dart_state          = "watching"
                st.turn_points         = 0
                st.fg_quiet            = None   # will re-seed from max_fg this iteration
                st.last_arrival        = 0.0
                bg_detect = {i: b.copy() for i, b in backgrounds.items()}
                print("Game changed via API — detection state reset.")

            tiles           = []
            now             = time.monotonic()
            all_tips_by_cam = {}
            shafts_by_cam   = {}
            frames_by_cam   = {}
            darts_by_cam    = {}
            fg_by_cam       = {}
            max_fg          = 0

            for reader in readers:
                frame = reader.get_frame()
                if frame is None:
                    tiles.append(np.zeros((TILE_H, TILE_W, 3), dtype=np.uint8))
                    continue

                frames_by_cam[reader.index] = frame
                # Detect against bg_detect (scored darts absorbed); measure fg
                # against the empty board (so it still counts all darts present).
                tile, detected_tips, fg, darts = draw_tile(
                    frame, bg_detect[reader.index], rois[reader.index],
                    reader.index, is_candidate_cam=bool(st.pendings),
                    empty_background=backgrounds[reader.index],
                )
                tiles.append(tile)
                all_tips_by_cam[reader.index] = detected_tips
                # Full shaft lines (not split endpoints) for the line-intersection
                # tip finder — it warps each shaft to canonical and meets them at the
                # board plane, which the flight end can't fake.
                shafts_by_cam[reader.index] = [(p1, p2) for p1, p2, _c in darts]
                darts_by_cam[reader.index] = darts
                fg_by_cam[reader.index] = fg
                max_fg = max(max_fg, fg)

            # Persist the raw camera inputs (throttled) for offline replay/debugging.
            dbg.raw_frames(frames_by_cam)

            if st.dart_state != STATUS["phase"]:
                dbg.event("phase", to=st.dart_state, frm=STATUS["phase"],
                          max_fg=int(max_fg))
            STATUS["phase"] = st.dart_state
            STATUS["awaiting_clear"] = (st.dart_state == "all_done")

            # ── Tracker / scoring state machine (one frame) ─────────────────
            # The per-frame body lives in step_tracker so the offline replay
            # (replay_state.py) runs the IDENTICAL logic — see its docstring.
            # I/O effects are injected: the recorder for telemetry, audio, and
            # the two camera/background operations the stepper can't do itself.
            def _heal():
                # Blend current frames into the empty-board references for
                # lighting drift, keeping bg_detect tracking the healed board.
                for r in readers:
                    f = r.get_frame()
                    if f is not None:
                        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                        backgrounds[r.index] = cv2.addWeighted(
                            backgrounds[r.index], 0.95, g, 0.05, 0)
                        bg_detect[r.index] = backgrounds[r.index].copy()

            def _reset_bg_detect():
                nonlocal bg_detect
                bg_detect = {i: b.copy() for i, b in backgrounds.items()}

            # Arrival-isolation shafts: only once a dart is already in the board
            # (settle_ref exists). Diff each current frame against the settled
            # board so the newest dart — even one fused with an existing one in
            # the empty-board diff — gives its own clean shafts to step_tracker.
            new_shafts_by_cam = {}
            if settle_ref is not None and st.scored_canonical:
                for reader in readers:
                    f = frames_by_cam.get(reader.index)
                    ref = settle_ref.get(reader.index)
                    if f is None or ref is None:
                        continue
                    nd, _ = detect_all_darts(
                        f, ref, rois[reader.index],
                        min_aspect=CAM_MIN_ASPECT.get(reader.index, 1.6),
                        empty_background=ref)
                    new_shafts_by_cam[reader.index] = [(p1, p2) for p1, p2, _c in nd]

            with GAME_LOCK:
                _game = GAME
            step_tracker(st, now, max_fg, shafts_by_cam, darts_by_cam, homographies,
                         _game, GAME_LOCK, new_shafts_by_cam=new_shafts_by_cam,
                         fg_by_cam=fg_by_cam, emit=dbg.event, say=say,
                         heal=_heal, reset_bg_detect=_reset_bg_detect)

            # Maintain the arrival-isolation reference: snapshot the settled board
            # (with the just-scored darts) after a commit; drop it when the visit
            # resets so the next visit's first dart isolates against nothing.
            if st.want_settle_snapshot:
                settle_ref = {i: cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                              for i, f in frames_by_cam.items()}
                st.want_settle_snapshot = False
            if not st.scored_canonical:
                settle_ref = None
            # History saving has been moved to server.py to ensure it saves even if the stream is not actively being viewed.
            game_was_over = GAME.over if GAME else False

            grid = np.hstack(tiles)
            for i, reader in enumerate(readers):
                if reader.index in bull_ref:
                    bx, by = bull_ref[reader.index]
                    sx, sy = TILE_W / 1280, TILE_H / 720
                    cv2.drawMarker(grid, (i * TILE_W + int(bx * sx), int(by * sy)), (0, 255, 255), cv2.MARKER_STAR, 16, 2)

            # Best in-flight candidate (most-tracked pending) drives the overlay.
            track_pos  = (max(st.pendings, key=lambda p: p["seen"])["pos"]
                          if st.pendings else None)
            confidence = max((p["max_cams"] for p in st.pendings), default=0)

            # Bottom panel: merged board view (all cameras warped into board space
            # — a live alignment check: the rings should overlap cleanly) beside
            # the scoreboard strip.
            PANEL_H = 300
            if homographies:
                merged = make_merged_view(frames_by_cam, homographies,
                                          st.scored_canonical, track_pos)
                merged_small = cv2.resize(merged, (PANEL_H, PANEL_H))
                cv2.putText(merged_small, "Board (cameras overlaid)", (8, 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            else:
                merged_small = np.zeros((PANEL_H, PANEL_H, 3), dtype=np.uint8)
                cv2.putText(merged_small, "no alignment", (20, PANEL_H // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 120, 120), 1)

            sb     = draw_score_bar(grid.shape[1] - PANEL_H, GAME, st.dart_state, confidence)
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
                        st.pendings = []
                    elif key == 'n':
                        new_game()
                        st.scored_canonical = []
                        st.pendings = []
                        st.dart_state = "watching"
                        st.fg_quiet = float(max_fg)
                        st.last_arrival = 0.0
                        st.turn_points = 0
                        bg_detect = {i: b.copy() for i, b in backgrounds.items()}
                    elif key == 'u':
                        # Undo the last scored dart (misread correction).
                        with GAME_LOCK:
                            undone = GAME.undo()
                        if undone:
                            if st.scored_canonical:
                                st.scored_canonical.pop()
                            st.pendings = []
                            st.dart_state = "watching"
                            say("Undo")
                            dbg.event("undo", source="key")
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

            _publish(display)

            time.sleep(0.03)

    finally:
        for r in readers:
            r.stop()
        # Signal the next worker (or an Align/Cameras stream) that the cameras
        # are free to be re-opened.
        _cameras_free.set()

def main():
    pass

if __name__ == "__main__":
    main()
