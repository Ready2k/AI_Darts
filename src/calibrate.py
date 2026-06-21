#!/usr/bin/env python3
"""
Darts camera calibration tool.

Phase 1 - Intrinsic (per camera): focal length, principal point, lens distortion.
Phase 2 - Extrinsic (all cameras together): relative positions and orientations.

Output: calibration.npz
"""

import sys
import time
import threading
import subprocess
from collections import deque
from pathlib import Path

import cv2
import numpy as np

# Checkerboard config — must match generate_checkerboard.py
CORNERS   = (7, 5)    # inner corners: 8x6 squares → 7x5 inner corners
SQUARE_MM = 20.0      # physical size of each square in mm

# Capture config
N_INTRINSIC   = 20
N_EXTRINSIC   = 15
COOLDOWN      = 2.0   # seconds between auto-captures
STABLE_THRESH = 3.0   # max pixel movement to count as stable
STABLE_FRAMES = 8     # consecutive stable frames before capturing

CAMERAS = [0, 1, 2]
LABELS  = {0: "Darts Cam 0", 1: "Darts Cam 1", 2: "Darts Cam 2"}

_objp = np.zeros((CORNERS[0] * CORNERS[1], 3), np.float32)
_objp[:, :2] = np.mgrid[0:CORNERS[0], 0:CORNERS[1]].T.reshape(-1, 2)
_objp *= SQUARE_MM

CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# Try fast detection first, fall back to exhaustive if not found
_FLAGS_FAST = (cv2.CALIB_CB_ADAPTIVE_THRESH |
               cv2.CALIB_CB_NORMALIZE_IMAGE  |
               cv2.CALIB_CB_FAST_CHECK)
_FLAGS_SLOW = (cv2.CALIB_CB_ADAPTIVE_THRESH |
               cv2.CALIB_CB_NORMALIZE_IMAGE  |
               cv2.CALIB_CB_EXHAUSTIVE)


# ── Audio ──────────────────────────────────────────────────────────────────────

_say_lock   = threading.Lock()
_say_proc   = None

def say(text):
    """Non-blocking macOS text-to-speech. Cancels any currently speaking phrase."""
    global _say_proc
    def _run():
        global _say_proc
        with _say_lock:
            if _say_proc and _say_proc.poll() is None:
                _say_proc.terminate()
            _say_proc = subprocess.Popen(["say", text])
            _say_proc.wait()
    threading.Thread(target=_run, daemon=True).start()


# ── Camera reader ──────────────────────────────────────────────────────────────

class CameraReader:
    def __init__(self, index):
        self.index = index
        self.cap   = cv2.VideoCapture(index)
        self.resolution = (
            int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
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


# ── Corner detection ───────────────────────────────────────────────────────────

def find_corners(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, CORNERS, _FLAGS_FAST)
    if not ret:
        ret, corners = cv2.findChessboardCorners(gray, CORNERS, _FLAGS_SLOW)
    if not ret:
        return None
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), CRITERIA)
    return corners


def is_stable(history):
    if len(history) < STABLE_FRAMES:
        return False
    recent = list(history)[-STABLE_FRAMES:]
    ref    = recent[-1]
    return all(np.max(np.abs(f - ref)) < STABLE_THRESH for f in recent)


# ── Drawing helpers ────────────────────────────────────────────────────────────

def draw_top_bar(frame, label, phase_text, count, total):
    h, w = frame.shape[:2]
    ov   = frame.copy()
    cv2.rectangle(ov, (0, 0), (w, 92), (0, 0, 0), -1)
    cv2.addWeighted(ov, 0.6, frame, 0.4, 0, frame)
    cv2.putText(frame, label,      (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8,  (0, 255, 0),     2)
    cv2.putText(frame, phase_text, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 200, 200), 1)
    bar_w  = w - 20
    filled = int(bar_w * count / total)
    cv2.rectangle(frame, (10, 64), (10 + bar_w, 80), (50, 50, 50), -1)
    cv2.rectangle(frame, (10, 64), (10 + filled, 80), (0, 200, 0), -1)
    cv2.putText(frame, f"{count}/{total}", (w // 2 - 22, 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1)


def draw_status(frame, text, color):
    h, w = frame.shape[:2]
    cv2.putText(frame, text, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)


def check_quit():
    key = cv2.waitKey(1) & 0xFF
    if key in (ord('q'), ord('Q'), 27):
        return True
    try:
        if cv2.getWindowProperty("Calibration", cv2.WND_PROP_VISIBLE) < 1:
            return True
    except Exception:
        return True
    return False




# ── Phase 1: intrinsic ─────────────────────────────────────────────────────────

def phase1_intrinsic(readers):
    print("\n=== Phase 1: Intrinsic calibration ===")
    results = {}

    for cam_num, reader in enumerate(readers):
        idx   = reader.index
        label = LABELS.get(idx, f"Camera {idx}")
        print(f"\n  {label} - hold board at {N_INTRINSIC} different positions/angles")


        obj_pts, img_pts = [], []
        history     = deque(maxlen=STABLE_FRAMES + 5)
        last_capture       = 0.0
        last_not_found_say = 0.0
        last_state         = None   # track state changes for audio

        while len(img_pts) < N_INTRINSIC:
            frame = reader.get_frame()
            if frame is None:
                continue

            display  = frame.copy()
            corners  = find_corners(frame)
            now      = time.monotonic()
            captured = False

            if corners is not None:
                history.append(corners)
                stable = is_stable(history)
                cv2.drawChessboardCorners(display, CORNERS, corners, True)

                if stable and (now - last_capture) > COOLDOWN:
                    obj_pts.append(_objp)
                    img_pts.append(corners)
                    last_capture = now
                    captured     = True
                    n = len(img_pts)
                    print(f"    Captured {n}/{N_INTRINSIC}")
                    say(str(n))

                if last_state != "stable" and stable:
                    last_state = "stable"
                elif last_state != "detected" and not stable:
                    last_state = "detected"

            else:
                history.clear()
                stable = False
                if last_state != "lost":
                    last_state = "lost"
                # Remind every 5s if board not visible

            if captured:
                flash = display.copy()
                cv2.rectangle(flash, (0, 0), (display.shape[1], display.shape[0]), (0, 255, 0), 12)
                cv2.addWeighted(flash, 0.4, display, 0.6, 0, display)

            draw_top_bar(display, label,
                         "Phase 1 of 2 - Intrinsic | Move to a new angle after each capture",
                         len(img_pts), N_INTRINSIC)

            if corners is None:
                draw_status(display, "Keep FULL board + white border in frame, tilt slightly", (160, 160, 160))
            elif stable:
                draw_status(display, "CAPTURING...", (0, 255, 255))
            else:
                draw_status(display, "HOLD STILL", (0, 200, 255))

            h, w = display.shape[:2]
            display = cv2.resize(display, (960, int(960 * h / w)))
            cv2.imshow("Calibration", display)

            if check_quit():
                print("Aborted.")
                return None


        print(f"    Computing intrinsics for {label}...")

        # Filter out captures that hurt calibration by iteratively dropping
        # the worst outlier until RMS is acceptable or we run out of captures
        MIN_CAPTURES = 10
        while len(obj_pts) >= MIN_CAPTURES:
            rms, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
                obj_pts, img_pts, reader.resolution, None, None
            )
            if rms < 1.5:
                break
            # Find the capture with the highest per-view error and drop it
            errors = []
            for i in range(len(obj_pts)):
                proj, _ = cv2.projectPoints(obj_pts[i], rvecs[i], tvecs[i], mtx, dist)
                err = cv2.norm(img_pts[i], proj, cv2.NORM_L2) / len(proj)
                errors.append(err)
            worst = int(np.argmax(errors))
            print(f"    Dropping capture {worst+1} (error {errors[worst]:.2f}px), retrying...")
            obj_pts.pop(worst)
            img_pts.pop(worst)

        print(f"    RMS reprojection error: {rms:.4f} px  (< 1.0 is good, using {len(obj_pts)} captures)")
        if rms > 2.0:
            print(f"    WARNING: RMS still high ({rms:.2f}). Consider recalibrating with more varied angles.")
        results[idx] = {"matrix": mtx, "dist": dist, "rms": rms, "resolution": reader.resolution}

    return results


# ── Phase 2: extrinsic ─────────────────────────────────────────────────────────

def phase2_extrinsic(readers, intrinsics):
    print("\n=== Phase 2: Extrinsic calibration ===")
    print(f"  Hold board so ALL 3 cameras can see it ({N_EXTRINSIC} captures needed)")

    captures     = {r.index: [] for r in readers}
    obj_points   = []
    histories    = {r.index: deque(maxlen=STABLE_FRAMES + 5) for r in readers}
    last_capture = 0.0
    last_all_vis_say = 0.0

    TILE_W, TILE_H = 640, 480

    while len(obj_points) < N_EXTRINSIC:
        tiles       = []
        all_corners = {}

        for reader in readers:
            idx    = reader.index
            frame  = reader.get_frame()
            if frame is None:
                tiles.append(np.zeros((TILE_H, TILE_W, 3), dtype=np.uint8))
                continue

            corners = find_corners(frame)
            tile    = cv2.resize(frame, (TILE_W, TILE_H))

            if corners is not None:
                all_corners[idx] = corners
                histories[idx].append(corners)
                cv2.drawChessboardCorners(tile, CORNERS, corners, True)
                cv2.rectangle(tile, (0, 0), (TILE_W - 1, TILE_H - 1), (0, 255, 0), 4)
                stxt, scol = "DETECTED", (0, 255, 0)
            else:
                histories[idx].clear()
                cv2.rectangle(tile, (0, 0), (TILE_W - 1, TILE_H - 1), (0, 0, 200), 3)
                stxt, scol = "not found", (0, 80, 255)

            cv2.putText(tile, f"{LABELS.get(idx, f'Cam {idx}')}  {stxt}",
                        (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, scol, 2)
            tiles.append(tile)

        now        = time.monotonic()
        n_detected = len(all_corners)
        all_vis    = n_detected == len(readers)
        all_stable = all_vis and all(is_stable(histories[r.index]) for r in readers)
        captured   = False


        if all_stable and (now - last_capture) > COOLDOWN:
            for r in readers:
                captures[r.index].append(all_corners[r.index])
            obj_points.append(_objp)
            last_capture = now
            captured     = True
            n = len(obj_points)
            print(f"    Captured {n}/{N_EXTRINSIC}")
            say(str(n))

        grid = np.hstack(tiles)

        bar   = np.zeros((56, grid.shape[1], 3), dtype=np.uint8)
        count = len(obj_points)

        if all_stable:
            msg, col = "CAPTURING...", (0, 255, 255)
        elif all_vis:
            msg, col = "ALL CAMERAS DETECTED - HOLD STILL", (0, 255, 0)
        else:
            msg, col = f"Get board visible in all 3 cameras ({n_detected}/3)", (160, 160, 160)

        cv2.putText(bar, f"Phase 2 of 2 - Extrinsic | {count}/{N_EXTRINSIC} | {msg}",
                    (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 1)
        bar_w  = grid.shape[1] - 20
        filled = int(bar_w * count / N_EXTRINSIC)
        cv2.rectangle(bar, (10, 34), (10 + bar_w, 50), (50, 50, 50), -1)
        cv2.rectangle(bar, (10, 34), (10 + filled, 50), (0, 200, 0), -1)

        if captured:
            flash = grid.copy()
            cv2.rectangle(flash, (0, 0), (grid.shape[1], grid.shape[0]), (0, 255, 0), 16)
            cv2.addWeighted(flash, 0.35, grid, 0.65, 0, grid)

        cv2.imshow("Calibration", np.vstack([grid, bar]))
        if check_quit():
            print("Aborted.")
            return None

    # Use solvePnP per camera rather than stereoCalibrate.
    # stereoCalibrate assumes corners appear in the same row-order in both images,
    # which breaks when cameras are 120 degrees apart (board looks rotated/flipped).
    # solvePnP lets each camera independently find the board pose; we then derive
    # the relative transform between cameras from those independent poses.
    ref_idx  = readers[0].index
    ref_mtx  = intrinsics[ref_idx]["matrix"]
    ref_dist = intrinsics[ref_idx]["dist"]

    # Build per-capture dict: { capture_index: { cam_index: corners } }
    cap_by_frame = [
        {r.index: captures[r.index][i] for r in readers}
        for i in range(len(obj_points))
    ]

    rel_rvecs = {r.index: [] for r in readers[1:]}
    rel_tvecs = {r.index: [] for r in readers[1:]}

    for obj_pt, cap in zip(obj_points, cap_by_frame):
        ret0, rvec0, tvec0 = cv2.solvePnP(obj_pt, cap[ref_idx], ref_mtx, ref_dist)
        if not ret0:
            continue
        R0, _ = cv2.Rodrigues(rvec0)

        for reader in readers[1:]:
            idx  = reader.index
            mtx  = intrinsics[idx]["matrix"]
            dist = intrinsics[idx]["dist"]
            ret1, rvec1, tvec1 = cv2.solvePnP(obj_pt, cap[idx], mtx, dist)
            if not ret1:
                continue
            R1, _ = cv2.Rodrigues(rvec1)
            R_rel = R1 @ R0.T
            T_rel = tvec1 - R_rel @ tvec0
            rvec_rel, _ = cv2.Rodrigues(R_rel)
            rel_rvecs[idx].append(rvec_rel)
            rel_tvecs[idx].append(T_rel)

    results = {}
    for reader in readers[1:]:
        idx     = reader.index
        R_avg, _ = cv2.Rodrigues(np.mean(rel_rvecs[idx], axis=0))
        T_avg    = np.mean(rel_tvecs[idx], axis=0)

        # Compute reprojection error as quality check
        cam_mtx  = intrinsics[idx]["matrix"]
        cam_dist = intrinsics[idx]["dist"]
        errors = []
        for obj_pt, cap in zip(obj_points, cap_by_frame):
            _, rvec0, tvec0 = cv2.solvePnP(obj_pt, cap[ref_idx], ref_mtx, ref_dist)
            R0, _ = cv2.Rodrigues(rvec0)
            # obj -> cam0 -> cam1
            pts_cam0 = R0 @ obj_pt.T + tvec0.reshape(3, 1)
            pts_cam1 = R_avg @ pts_cam0 + T_avg.reshape(3, 1)
            proj, _ = cv2.projectPoints(
                pts_cam1.T, np.zeros(3), np.zeros(3), cam_mtx, cam_dist
            )
            err = np.sqrt(np.mean(
                np.sum((cap[idx].reshape(-1, 2) - proj.reshape(-1, 2)) ** 2, axis=1)
            ))
            errors.append(err)
        rms = float(np.mean(errors))

        print(f"\n  Extrinsics {LABELS[ref_idx]} -> {LABELS[idx]}: RMS {rms:.4f} px")
        if rms > 3.0:
            print(f"    WARNING: RMS still high — try more varied board positions in phase 2")
        results[idx] = {"R": R_avg, "T": T_avg, "rms": rms}

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def load_intrinsics(path="calibration.npz"):
    data = np.load(path)
    intrinsics = {}
    for idx in CAMERAS:
        intrinsics[idx] = {
            "matrix":     data[f"camera_matrix_{idx}"],
            "dist":       data[f"dist_coeffs_{idx}"],
            "resolution": tuple(int(x) for x in data[f"resolution_{idx}"]),
        }
    return intrinsics


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--extrinsic-only", action="store_true",
                        help="Skip intrinsic calibration, load existing from calibration.npz")
    args = parser.parse_args()

    print("Darts camera calibration")
    print(f"Checkerboard: {CORNERS[0]}x{CORNERS[1]} inner corners, {SQUARE_MM:.0f}mm squares")
    print("Press Q at any time to abort.\n")

    readers = [CameraReader(i).start() for i in CAMERAS]
    time.sleep(1.0)

    try:
        if args.extrinsic_only:
            print("Loading intrinsics from calibration.npz...")
            intrinsics = load_intrinsics()
            for idx, d in intrinsics.items():
                print(f"  {LABELS.get(idx, f'Camera {idx}')}: loaded ({d['resolution'][0]}x{d['resolution'][1]})")
            print()
        else:
            intrinsics = phase1_intrinsic(readers)
            if intrinsics is None:
                return

        extrinsics = phase2_extrinsic(readers, intrinsics)
        if extrinsics is None:
            return

        save = {}
        for idx, data in intrinsics.items():
            save[f"camera_matrix_{idx}"] = data["matrix"]
            save[f"dist_coeffs_{idx}"]   = data["dist"]
            save[f"resolution_{idx}"]    = np.array(data["resolution"])
        for idx, data in extrinsics.items():
            save[f"R_{idx}"] = data["R"]
            save[f"T_{idx}"] = data["T"]
        save["R_0"] = np.eye(3)
        save["T_0"] = np.zeros((3, 1))
        save["reference_camera"] = np.array([0])

        out = Path("calibration.npz")
        np.savez(str(out), **save)
        print(f"\nCalibration saved -> {out}")
        print("Ready for dart triangulation.")

    finally:
        for r in readers:
            r.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
