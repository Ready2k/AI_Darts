#!/usr/bin/env python3
"""Quick check that all USB cameras are working — shows a live tiled view with stats."""

import sys
import time
import threading
import argparse
import cv2
import numpy as np
from collections import deque

CAMERA_LABELS = {
    0: "Darts Cam 0",
    1: "Darts Cam 1",
    2: "Darts Cam 2",
    3: "MacBook Cam",
    4: "iPhone",
}


class CameraReader:
    """Reads frames from a single camera on a background thread."""

    def __init__(self, index):
        self.index = index
        self.cap = cv2.VideoCapture(index)
        self.frame = None
        self.ok = False
        self.resolution = (0, 0)
        self.timestamps = deque(maxlen=30)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        self.cap.release()

    def _run(self):
        self.resolution = (
            int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        while not self._stop.is_set():
            ret, frame = self.cap.read()
            now = time.monotonic()
            with self._lock:
                self.ok = ret
                if ret:
                    self.frame = frame
                    self.timestamps.append(now)

    def get(self):
        """Return (frame_or_None, fps, resolution, ok) — never blocks."""
        with self._lock:
            ts = self.timestamps
            fps = (len(ts) - 1) / (ts[-1] - ts[0]) if len(ts) > 1 else 0.0
            return self.frame, fps, self.resolution, self.ok


def find_cameras(max_index=10):
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"  Camera {i}: {CAMERA_LABELS.get(i, f'Camera {i}'):15s}  {w}x{h}")
                found.append(i)
            else:
                print(f"  Camera {i}: opened but couldn't read frame")
            cap.release()
    return found


def draw_stats(frame, label, fps, resolution, ok):
    h, w = frame.shape[:2]
    green, red, white, black = (0, 255, 0), (0, 0, 255), (255, 255, 255), (0, 0, 0)

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 52), black, -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    cv2.putText(frame, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, green if ok else red, 2)
    stats = f"{fps:.1f} fps  |  {resolution[0]}x{resolution[1]}" if ok else "NO SIGNAL"
    cv2.putText(frame, stats, (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.55, white, 1)
    return frame


def parse_args():
    parser = argparse.ArgumentParser(description="Darts camera viewer")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--cameras", "-c",
        metavar="N",
        type=int,
        nargs="+",
        help="Camera indices to use (default: 0 1 2)",
    )
    group.add_argument(
        "--all", "-a",
        action="store_true",
        help="Use all detected cameras",
    )
    return parser.parse_args()


def stream_frames(cameras=None):
    print("Scanning for cameras...")
    detected = find_cameras()

    if not detected:
        print("No cameras found.")
        return

    if cameras is not None:
        indices = [i for i in cameras if i in detected]
    else:
        indices = [i for i in [0, 1, 2] if i in detected]

    if not indices:
        return

    readers = [CameraReader(i) for i in indices]
    for r in readers:
        r.start()

    TILE_W, TILE_H = 640, 480

    try:
        while True:
            tiles = []
            all_ok = True

            for r in readers:
                frame, fps, res, ok = r.get()
                if ok and frame is not None:
                    tile = cv2.resize(frame, (TILE_W, TILE_H))
                else:
                    tile = np.zeros((TILE_H, TILE_W, 3), dtype=np.uint8)
                    all_ok = False

                label = CAMERA_LABELS.get(r.index, f"Camera {r.index}")
                tile = draw_stats(tile, label, fps, res, ok)
                tiles.append(tile)

            while len(tiles) % 3 != 0:
                tiles.append(np.zeros((TILE_H, TILE_W, 3), dtype=np.uint8))

            rows = [np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]
            grid = np.vstack(rows)

            bar = np.zeros((32, grid.shape[1], 3), dtype=np.uint8)
            status = "ALL CAMERAS OK" if all_ok else "WARNING: signal lost on one or more cameras"
            cv2.putText(bar, status, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        (0, 255, 0) if all_ok else (0, 0, 255), 2)
            grid = np.vstack([grid, bar])

            # Instead of cv2.imshow, yield jpeg
            ret, buffer = cv2.imencode('.jpg', grid, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.03)

    finally:
        for r in readers:
            r.stop()

def main():
    # Only called if run manually from CLI
    for _ in stream_frames():
        pass

if __name__ == "__main__":
    main()
