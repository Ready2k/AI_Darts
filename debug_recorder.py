"""Per-match debug recorder.

Toggle "Debug recording" when starting a game and the detection pipeline writes
everything needed to diagnose a glitch (phantom dart, missed dart, misread) into
a single folder under debug_recordings/:

    debug_recordings/match_<timestamp>/
        meta.json         game config + start/stop times + environment
        telemetry.jsonl   one JSON object per detection event (scored darts,
                          dropped phantoms/duplicates, state changes, fg samples,
                          undo/correct corrections, settle windows, …)
        detection.avi     the composite detection view (all cameras + overlays +
                          scoreboard) — the same frames streamed to the web UI
        raw_cam<i>.avi    each camera's RAW (unannotated) input, written on a shared
                          throttle tick so frame N lines up across cameras
        alignment.json    the homographies the match ran with (snapshot)
        backgrounds.npz   the empty-board references used for subtraction

The raw_cam*.avi + alignment.json + backgrounds.npz are what replay.py needs to
re-run detection deterministically offline (debug a phantom/miss without having to
reproduce it live). Zip the folder and send it over to reproduce/diagnose a glitch.

The recorder is a process-wide singleton shared by detect.py and server.py (they
run in the same process). All writes happen under a lock so start/stop from the
API thread can't race the detect thread's event/frame writes.
"""

import atexit
import json
import os
import shutil
import threading
import time
from datetime import datetime

import cv2

RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "debug_recordings")

# Target video frame rate. The detect loop runs ~20-30 fps; we cap recording to
# this so the file stays a sensible size and plays back near real time.
VIDEO_FPS = 15.0


class DebugRecorder:
    def __init__(self):
        self._lock = threading.Lock()
        self.active = False
        self.dir = None
        self._tel = None              # telemetry.jsonl file handle
        self._video = None            # cv2.VideoWriter
        self._video_size = None       # (w, h) the writer was opened with
        self._raw = {}                # cam_idx -> cv2.VideoWriter (raw per-camera)
        self._raw_size = {}           # cam_idx -> (w, h)
        self._raw_index = {}          # cam_idx -> frames written (for replay sync)
        self._last_raw_t = 0.0        # raw-capture fps throttle
        self._t0 = None               # monotonic start
        self._last_frame_t = 0.0      # for fps throttling
        self._frame_interval = 1.0 / VIDEO_FPS

    # ── lifecycle ──────────────────────────────────────────────────────────
    def start(self, meta=None):
        """Begin a new recording folder. Stops any in-progress recording first."""
        with self._lock:
            self._stop_locked()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.dir = os.path.join(RECORDINGS_DIR, f"match_{stamp}")
            os.makedirs(self.dir, exist_ok=True)
            self._tel = open(os.path.join(self.dir, "telemetry.jsonl"),
                             "w", buffering=1)  # line-buffered
            self._video = None
            self._video_size = None
            self._raw = {}
            self._raw_size = {}
            self._raw_index = {}
            self._last_raw_t = 0.0
            self._t0 = time.monotonic()
            self._last_frame_t = 0.0
            self.active = True
            meta = dict(meta or {})
            meta["started_at"] = datetime.now().isoformat(timespec="seconds")
            with open(os.path.join(self.dir, "meta.json"), "w") as f:
                json.dump(meta, f, indent=2)
            print(f"    [debug] recording match to {self.dir}")
        self.event("match_start", **(meta or {}))
        return self.dir

    def stop(self):
        with self._lock:
            self._stop_locked()

    def _stop_locked(self):
        if not self.active:
            return
        path = self.dir
        try:
            self.event_locked("match_stop")
        except Exception:
            pass
        if self._tel:
            try:
                self._tel.close()
            except Exception:
                pass
        if self._video is not None:
            try:
                self._video.release()
            except Exception:
                pass
        for w in self._raw.values():
            try:
                w.release()
            except Exception:
                pass
        self.active = False
        self._tel = None
        self._video = None
        self._video_size = None
        self._raw = {}
        self._raw_size = {}
        self._raw_index = {}
        print(f"    [debug] recording saved to {path}")

    # ── writes ─────────────────────────────────────────────────────────────
    def event(self, kind, **fields):
        """Append a structured event to telemetry.jsonl (no-op if inactive)."""
        if not self.active:
            return
        with self._lock:
            self.event_locked(kind, **fields)

    def event_locked(self, kind, **fields):
        if not self._tel:
            return
        rec = {
            "t": time.monotonic() - (self._t0 or 0.0),
            "wall": datetime.now().isoformat(timespec="milliseconds"),
            "kind": kind,
        }
        rec.update(fields)
        try:
            self._tel.write(json.dumps(rec, default=_json_safe) + "\n")
        except Exception:
            pass

    def frame(self, img):
        """Write one composite frame to detection.mp4 (throttled to VIDEO_FPS)."""
        if not self.active or img is None:
            return
        now = time.monotonic()
        if now - self._last_frame_t < self._frame_interval:
            return
        with self._lock:
            if not self.active:
                return
            self._last_frame_t = now
            h, w = img.shape[:2]
            if self._video is None:
                # AVI/MJPG, not mp4: an mp4 keeps its index in a trailing moov
                # atom written only on release(), so if the process is killed the
                # whole video is unreadable. AVI writes self-contained frames, so
                # a truncated file is still playable up to the last flushed frame.
                fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                path = os.path.join(self.dir, "detection.avi")
                self._video = cv2.VideoWriter(path, fourcc, VIDEO_FPS, (w, h))
                self._video_size = (w, h)
            if (w, h) != self._video_size:
                img = cv2.resize(img, self._video_size)
            try:
                self._video.write(img)
            except Exception:
                pass

    def raw_frames(self, frames_by_cam):
        """Write each camera's RAW frame to raw_cam<idx>.avi (throttled to VIDEO_FPS).

        These are the unannotated inputs the detection pipeline saw, so a recorded
        match can be replayed deterministically offline (see replay.py) instead of
        guessed at from the annotated composite. All cameras are written on the same
        throttle tick, so frame N of every raw_cam file lines up. A `raw_tick` event
        records the monotonic time of each batch so telemetry can be aligned to it.
        """
        if not self.active or not frames_by_cam:
            return
        now = time.monotonic()
        if now - self._last_raw_t < self._frame_interval:
            return
        with self._lock:
            if not self.active:
                return
            self._last_raw_t = now
            for idx, img in frames_by_cam.items():
                if img is None:
                    continue
                h, w = img.shape[:2]
                writer = self._raw.get(idx)
                if writer is None:
                    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                    path = os.path.join(self.dir, f"raw_cam{idx}.avi")
                    writer = cv2.VideoWriter(path, fourcc, VIDEO_FPS, (w, h))
                    self._raw[idx] = writer
                    self._raw_size[idx] = (w, h)
                    self._raw_index[idx] = 0
                if (w, h) != self._raw_size[idx]:
                    img = cv2.resize(img, self._raw_size[idx])
                try:
                    writer.write(img)
                    self._raw_index[idx] += 1
                except Exception:
                    pass
            self.event_locked("raw_tick",
                              index={i: self._raw_index.get(i) for i in frames_by_cam})

    def snapshot_file(self, src):
        """Copy a state file (e.g. alignment.json) into the recording dir, so replay
        can reproduce the exact homographies/config the match ran with."""
        if not self.active or not src or not os.path.exists(src):
            return
        with self._lock:
            if not self.active:
                return
            try:
                shutil.copy2(src, os.path.join(self.dir, os.path.basename(src)))
            except Exception:
                pass

    def save_arrays(self, name, arrays):
        """Save a dict of {cam_idx: np.ndarray} (e.g. empty-board backgrounds) into
        the recording dir as an .npz, so replay can reproduce background subtraction."""
        if not self.active or not arrays:
            return
        with self._lock:
            if not self.active:
                return
            try:
                import numpy as np
                np.savez(os.path.join(self.dir, name),
                         **{str(k): v for k, v in arrays.items()})
            except Exception:
                pass


def _json_safe(o):
    """Best-effort serialisation for numpy scalars / arrays in event fields."""
    try:
        return o.item()          # numpy scalar
    except Exception:
        pass
    try:
        return list(o)           # numpy array / tuple-likes
    except Exception:
        return str(o)


# Process-wide singleton.
recorder = DebugRecorder()

# Backstop: finalise the recording on interpreter exit (graceful shutdown via
# stop.sh / Ctrl-C) so the video and telemetry are always closed cleanly even if
# nothing called stop() explicitly.
atexit.register(recorder.stop)
