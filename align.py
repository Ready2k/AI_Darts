#!/usr/bin/env python3
"""
Mesh-based camera alignment.

For each camera, drag the 5 coloured handles to align the dartboard mesh
overlay with the physical board visible in the feed. When the rings and
segment numbers sit on the board, press Enter to confirm.

Run once:  ./start.sh align
Then detect.py uses the saved alignment for scoring.

Controls (per camera):
  Left-drag  — move the nearest handle
  Enter      — confirm this camera
  R          — reset handles to auto-detected position
  Q / Esc    — quit without saving
"""

import math
import json
import time
import threading
from pathlib import Path

import cv2
import numpy as np

import dartboard
import auto_calibrate

CAMERAS  = [0, 1, 2]
LABELS   = {0: "Darts Cam 0", 1: "Darts Cam 1", 2: "Darts Cam 2"}
OUT_FILE = Path("alignment.json")

CANONICAL_SIZE   = 500
CANONICAL_CENTRE = CANONICAL_SIZE // 2   # 250 px
CANONICAL_RADIUS = 220                   # px = DOUBLE_OUT ring

# Diamond control points in canonical board space.
# Using a diamond (top/right/bottom/left) instead of a cross (bull/top/right/left)
# ensures only 2 of 4 points share the same canonical y-coordinate.
# A cross (old design) put 3 points at y=250, which made the perspective transform
# degenerate: canonical y always collapsed to 250 regardless of camera position.
CTRL_CANONICAL_DEFAULT = np.array([
    [CANONICAL_CENTRE,                    CANONICAL_CENTRE - CANONICAL_RADIUS],  # 0 top    (Seg 20)
    [CANONICAL_CENTRE + CANONICAL_RADIUS, CANONICAL_CENTRE],                     # 1 right  (Seg  6)
    [CANONICAL_CENTRE,                    CANONICAL_CENTRE + CANONICAL_RADIUS],  # 2 bottom (Seg  3)
    [CANONICAL_CENTRE - CANONICAL_RADIUS, CANONICAL_CENTRE],                     # 3 left   (Seg 11)
], dtype=np.float32)

CTRL_LABELS_DEFAULT  = ["Seg 20", "Seg 6", "Seg 3", "Seg 11"]
CTRL_COLOURS_DEFAULT = [
    (0,   255,   0),   # green   — outer double of 20 (12 o'clock)
    (255, 100,   0),   # blue    — outer double of  6 ( 3 o'clock)
    (0,   200, 200),   # cyan    — outer double of  3 ( 6 o'clock)
    (255,   0, 255),   # magenta — outer double of 11 ( 9 o'clock)
]

def _cam_ctrl(cam_idx):
    return (CTRL_CANONICAL_DEFAULT, CTRL_LABELS_DEFAULT, CTRL_COLOURS_DEFAULT)
HANDLE_R = 14   # hit-test radius in display pixels

DISP_W = 960
DISP_H = 540


# ── Camera reader ─────────────────────────────────────────────────────────────

class CameraReader:
    def __init__(self, index):
        self.index   = index
        self.cap     = cv2.VideoCapture(index)
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
        self.cap.release()

    def _run(self):
        while not self._stop.is_set():
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self._frame = frame

    def get_frame(self):
        with self._lock:
            return self._frame.copy() if self._frame is not None else None


# ── Mesh drawing ──────────────────────────────────────────────────────────────

def _canonical_to_display(cx, cy, H_c2cam, sx, sy):
    """Transform a canonical (cx,cy) to display pixel via H_c2cam."""
    pt  = np.array([[[float(cx), float(cy)]]], dtype=np.float32)
    cam = cv2.perspectiveTransform(pt, H_c2cam).reshape(2)
    return (int(cam[0] * sx), int(cam[1] * sy))


def _ring_poly(r_mm, H_c2cam, sx, sy, n=72):
    """Return display-space polygon approximating a ring of radius r_mm."""
    c     = float(CANONICAL_CENTRE)
    scale = CANONICAL_RADIUS / dartboard.DOUBLE_OUT
    pts   = []
    for i in range(n):
        a  = math.radians(i * 360 / n)
        cx = c + r_mm * scale * math.sin(a)
        cy = c - r_mm * scale * math.cos(a)
        pts.append(_canonical_to_display(cx, cy, H_c2cam, sx, sy))
    return np.array(pts, dtype=np.int32)


def draw_mesh(img, H_c2cam, sx, sy):
    """Overlay the dartboard mesh on img using canonical→camera homography."""
    c     = float(CANONICAL_CENTRE)
    scale = CANONICAL_RADIUS / dartboard.DOUBLE_OUT

    # Rings
    for r_mm, col, thick in [
        (dartboard.DOUBLE_OUT, (80,  80, 220), 2),
        (dartboard.DOUBLE_IN,  (60,  60, 160), 1),
        (dartboard.TREBLE_OUT, (80,  80, 220), 2),
        (dartboard.TREBLE_IN,  (60,  60, 160), 1),
        (dartboard.BULLS_R,    (0,  200, 200), 2),
        (dartboard.BULL_R,     (0,  200, 200), 2),
    ]:
        poly = _ring_poly(r_mm, H_c2cam, sx, sy)
        cv2.polylines(img, [poly], True, col, thick)

    # Segment dividers (from bull to outer ring)
    r_outer = dartboard.DOUBLE_OUT * scale
    r_bull  = dartboard.BULL_R    * scale
    for i in range(20):
        a  = math.radians(i * 18 - 9)
        ox = c + r_outer * math.sin(a)
        oy = c - r_outer * math.cos(a)
        bx = c + r_bull  * math.sin(a)
        by = c - r_bull  * math.cos(a)
        p1 = _canonical_to_display(bx, by, H_c2cam, sx, sy)
        p2 = _canonical_to_display(ox, oy, H_c2cam, sx, sy)
        cv2.line(img, p1, p2, (55, 55, 110), 1)

    # Segment numbers
    r_lbl = dartboard.DOUBLE_IN * scale * 0.82
    for i, seg in enumerate(dartboard.SEGMENTS):
        a  = math.radians(i * 18 + 9)
        lx = c + r_lbl * math.sin(a)
        ly = c - r_lbl * math.cos(a)
        dx, dy = _canonical_to_display(lx, ly, H_c2cam, sx, sy)
        if 0 <= dx < img.shape[1] and 0 <= dy < img.shape[0]:
            cv2.putText(img, str(seg), (dx - 8, dy + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (170, 170, 170), 1)


def draw_handles(img, ctrl_cam, sx, sy, drag_idx=None, labels=None, colours=None):
    """Draw draggable control point handles in display space."""
    labels  = labels  or CTRL_LABELS_DEFAULT
    colours = colours or CTRL_COLOURS_DEFAULT
    for i, (ox, oy) in enumerate(ctrl_cam):
        dx, dy = int(ox * sx), int(oy * sy)
        col    = colours[i]
        size   = HANDLE_R + 5 if i == drag_idx else HANDLE_R
        cv2.circle(img, (dx, dy), size, col, 2)
        cv2.circle(img, (dx, dy), 3,    col, -1)
        cv2.putText(img, labels[i], (dx + size + 4, dy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1)


# ── Auto-detect board for initial handle placement ────────────────────────────

def center_handles(frame):
    """Place handles in a diamond pattern matching the canonical layout order:
    index 0=top, 1=right, 2=bottom, 3=left."""
    h, w = frame.shape[:2]
    cx, cy = w / 2, h / 2
    r = min(w, h) * 0.25
    return np.array([
        [cx,     cy - r],   # 0 Top    (Seg 20) — Green
        [cx + r, cy    ],   # 1 Right  (Seg  6) — Blue
        [cx,     cy + r],   # 2 Bottom (Seg  3) — Cyan
        [cx - r, cy    ],   # 3 Left   (Seg 11) — Magenta
    ], dtype=np.float32)


def auto_place_handles(frame):
    """Try HoughCircles for initial placement; fall back to diamond cross."""
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    h, w    = gray.shape
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2,
        minDist=min(h, w) // 2,
        param1=80, param2=35,
        minRadius=int(min(h, w) * 0.15),
        maxRadius=int(min(h, w) * 0.65),
    )
    if circles is not None:
        cx, cy, r = np.round(circles[0][0]).astype(float)
        pts = np.array([
            [cx,     cy - r],   # 0 Top    (Seg 20)
            [cx + r, cy    ],   # 1 Right  (Seg  6)
            [cx,     cy + r],   # 2 Bottom (Seg  3)
            [cx - r, cy    ],   # 3 Left   (Seg 11)
        ], dtype=np.float32)
        margin = 20
        if (pts[:, 0].min() >= margin and pts[:, 0].max() <= w - margin and
                pts[:, 1].min() >= margin and pts[:, 1].max() <= h - margin):
            print(f"    Board circle found at ({cx:.0f},{cy:.0f}) r={r:.0f}px")
            return pts
    print("    Using centre cross — drag handles onto the board")
    return center_handles(frame)


def apply_auto_detect(state, frame, ctrl_canonical):
    """Fit the board ellipse and snap the handles to it. Returns True on success."""
    handles = auto_calibrate.auto_handles(frame, debug=True)
    if handles is None:
        print("    Auto-detect failed — drag the handles manually")
        return False
    state["ctrl_cam"] = handles
    h1, h2 = compute_homographies(handles, ctrl_canonical)
    if h1 is not None:
        state["H_c2cam"], state["H_cam2c"] = h1, h2
    print("    Auto-detected board — rotate the handles so the numbers line up")
    return True


def compute_homographies(ctrl_cam, ctrl_canonical):
    """
    Compute H_canonical→cam and H_cam→canonical from the 4 control points.
    Both directions are computed via getPerspectiveTransform (not via matrix
    inversion, which is numerically catastrophic for ill-conditioned layouts).
    Returns (H_c2cam, H_cam2c) or (None, None) if points are degenerate.
    """
    try:
        H_c2cam = cv2.getPerspectiveTransform(ctrl_canonical, ctrl_cam)
        H_cam2c = cv2.getPerspectiveTransform(ctrl_cam, ctrl_canonical)
        return H_c2cam, H_cam2c
    except (cv2.error, np.linalg.LinAlgError):
        return None, None


# ── Per-camera alignment session ──────────────────────────────────────────────

def stream_frames(event_queue):
    print("Darts mesh alignment starting in Web UI...")
    
    existing = {}
    if OUT_FILE.exists():
        try:
            data = json.loads(OUT_FILE.read_text())
            existing = {int(k): v for k, v in data.items()}
        except Exception:
            pass

    readers = [CameraReader(i).start() for i in CAMERAS]
    time.sleep(1.0)
    
    saved = {str(k): v for k, v in existing.items()}

    for reader in readers:
        cam_idx = reader.index
        ctrl_canonical, ctrl_labels, ctrl_colours = _cam_ctrl(cam_idx)
        
        frame = None
        for _ in range(60):
            frame = reader.get_frame()
            if frame is not None:
                break
            time.sleep(0.05)
            
        if frame is None:
            continue

        ctrl_cam = None
        if existing.get(cam_idx) is not None:
            try:
                H_existing = np.array(existing[cam_idx], dtype=np.float64)
                H_c2cam_init = np.linalg.inv(H_existing)
                pts = cv2.perspectiveTransform(
                    ctrl_canonical.reshape(-1, 1, 2), H_c2cam_init.astype(np.float32)
                ).reshape(-1, 2)
                h, w = frame.shape[:2]
                if (pts[:, 0].min() > -w * 0.3 and pts[:, 0].max() < w * 1.3 and
                        pts[:, 1].min() > -h * 0.3 and pts[:, 1].max() < h * 1.3):
                    ctrl_cam = pts.astype(np.float32)
            except Exception:
                pass
                
        if ctrl_cam is None:
            ctrl_cam = auto_place_handles(frame)

        H_c2cam, H_cam2c = compute_homographies(ctrl_cam, ctrl_canonical)
        label = LABELS.get(cam_idx, f"Camera {cam_idx}")

        state = {"drag_idx": None, "ctrl_cam": ctrl_cam, "H_c2cam": H_c2cam, "H_cam2c": H_cam2c}
        
        confirmed = False
        
        hint = "  |  ".join(f"{lbl.split()[0]}" for lbl in ctrl_labels)
        hint_line = f"Handles: {hint}  |  Auto-detect (A)  |  Place on outer double wire  |  Confirm  |  Reset"

        while not confirmed:
            frame = reader.get_frame()
            if frame is None:
                time.sleep(0.03)
                continue

            sx = DISP_W / frame.shape[1]
            sy = DISP_H / frame.shape[0]
            display = cv2.resize(frame, (DISP_W, DISP_H))

            if state["H_c2cam"] is not None:
                draw_mesh(display, state["H_c2cam"], sx, sy)

            draw_handles(display, state["ctrl_cam"], sx, sy, state["drag_idx"], labels=ctrl_labels, colours=ctrl_colours)

            ov = display.copy()
            cv2.rectangle(ov, (0, 0), (DISP_W, 52), (0, 0, 0), -1)
            cv2.addWeighted(ov, 0.6, display, 0.4, 0, display)
            cv2.putText(display, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
            cv2.putText(display, hint_line, (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (180, 180, 180), 1)

            # Process Web Events
            while event_queue:
                ev = event_queue.pop(0)
                evt_type = ev.get('type')
                
                if evt_type == 'mousedown':
                    mx, my = ev['x'], ev['y']
                    ox, oy = mx / sx, my / sy
                    dists = [math.hypot(ox - p[0], oy - p[1]) for p in state["ctrl_cam"]]
                    idx = int(np.argmin(dists))
                    thresh = HANDLE_R / min(sx, sy) * 2.5
                    if dists[idx] < thresh:
                        state["drag_idx"] = idx
                elif evt_type == 'mousemove' and state["drag_idx"] is not None:
                    mx, my = ev['x'], ev['y']
                    state["ctrl_cam"][state["drag_idx"]] = [mx / sx, my / sy]
                    h1, h2 = compute_homographies(state["ctrl_cam"], ctrl_canonical)
                    if h1 is not None:
                        state["H_c2cam"] = h1
                        state["H_cam2c"] = h2
                elif evt_type == 'mouseup':
                    state["drag_idx"] = None
                elif evt_type == 'keydown':
                    key = ev.get('key', '').lower()
                    if key == 'r':
                        state["ctrl_cam"] = center_handles(frame)
                        h1, h2 = compute_homographies(state["ctrl_cam"], ctrl_canonical)
                        if h1 is not None:
                            state["H_c2cam"] = h1
                            state["H_cam2c"] = h2
                    elif key == 'a':
                        apply_auto_detect(state, frame, ctrl_canonical)
                    elif key == 'enter':
                        if state["H_cam2c"] is not None:
                            saved[str(cam_idx)] = state["H_cam2c"].tolist()
                            OUT_FILE.write_text(json.dumps(saved, indent=2))
                            confirmed = True
                            break
                elif evt_type == 'auto':
                    apply_auto_detect(state, frame, ctrl_canonical)
                elif evt_type == 'reset':
                    state["ctrl_cam"] = center_handles(frame)
                    h1, h2 = compute_homographies(state["ctrl_cam"], ctrl_canonical)
                    if h1 is not None:
                        state["H_c2cam"] = h1
                        state["H_cam2c"] = h2
                elif evt_type == 'confirm':
                    if state["H_cam2c"] is not None:
                        saved[str(cam_idx)] = state["H_cam2c"].tolist()
                        OUT_FILE.write_text(json.dumps(saved, indent=2))
                        confirmed = True
                        break

            ret, buffer = cv2.imencode('.jpg', display, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            
            time.sleep(0.03)

    for r in readers:
        r.stop()

    # Finished alignment, yield a black frame or completion message
    final_frame = np.zeros((DISP_H, DISP_W, 3), dtype=np.uint8)
    cv2.putText(final_frame, "Alignment Complete! Saved to alignment.json", (50, DISP_H//2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    ret, buffer = cv2.imencode('.jpg', final_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if ret:
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

def main():
    pass

if __name__ == "__main__":
    main()
