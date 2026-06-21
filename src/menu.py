#!/usr/bin/env python3
"""
Darts launcher — OpenCV GUI menu.
"""

import os
import sys
import json
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).parent

W, H = 520, 400

BG      = (18,  18,  18)
CARD    = (30,  30,  30)
BORDER  = (55,  55,  55)
WHITE   = (240, 240, 240)
DIM     = (90,  90,  90)
GREEN   = (0,  200, 100)
AMBER   = (0,  170, 255)
RED     = (60,  60, 220)


def alignment_status():
    p = SCRIPT_DIR.parent / "alignment.json"
    if not p.exists():
        return "No alignment — run Align Cameras first", AMBER
    try:
        data = json.loads(p.read_text())
        cams = sorted(int(k) for k in data.keys())
        return f"Alignment ready  (cameras {cams})", GREEN
    except Exception:
        return "Alignment file unreadable", RED


def make_menu(hover_idx):
    img = np.full((H, W, 3), BG, dtype=np.uint8)

    # Title
    cv2.putText(img, "Darts", (32, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 1.4, WHITE, 2, cv2.LINE_AA)

    # Status bar
    status_text, status_col = alignment_status()
    cv2.rectangle(img, (32, 68), (W - 32, 100), CARD, -1)
    cv2.rectangle(img, (32, 68), (W - 32, 100), BORDER, 1)
    cv2.putText(img, status_text, (44, 89),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, status_col, 1, cv2.LINE_AA)

    # Buttons
    buttons = [
        ("Start Detection",  "Score darts across all 3 cameras"),
        ("Align Cameras",    "Drag mesh overlay to fit each camera view"),
        ("Check Cameras",    "Live feed from all cameras"),
    ]

    align_ready = alignment_status()[1] == GREEN

    for i, (label, sub) in enumerate(buttons):
        y0 = 118 + i * 78
        y1 = y0 + 64

        is_primary = (i == 0 and align_ready)
        is_hover   = (i == hover_idx)

        if is_primary:
            bg_col = (0, 160, 80) if is_hover else (0, 140, 70)
            fg_col = (0, 0, 0)
            sf_col = (0, 80, 40)
        else:
            bg_col = (42, 42, 42) if is_hover else CARD
            fg_col = WHITE
            sf_col = DIM

        cv2.rectangle(img, (32, y0), (W - 32, y1), bg_col, -1)
        cv2.rectangle(img, (32, y0), (W - 32, y1), BORDER, 1)
        cv2.putText(img, label, (48, y0 + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, fg_col, 1, cv2.LINE_AA)
        cv2.putText(img, sub, (48, y0 + 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, sf_col, 1, cv2.LINE_AA)

    # Footer
    cv2.putText(img, "Q / Esc to quit",
                (32, H - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.36, DIM, 1, cv2.LINE_AA)

    return img


def button_at(my):
    """Return button index (0-2) if my is inside a button row, else -1."""
    for i in range(3):
        y0 = 118 + i * 78
        y1 = y0 + 64
        if y0 <= my <= y1:
            return i
    return -1


def launch(script):
    cv2.destroyAllWindows()
    os.execv(sys.executable, [sys.executable, str(SCRIPT_DIR / script)])


def main():
    scripts = ["detect.py", "align.py", "check_cameras.py"]

    WIN = "Darts"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, W, H)

    hover_idx = -1

    def on_mouse(event, mx, my, flags, _):
        nonlocal hover_idx
        idx = button_at(my) if 32 <= mx <= W - 32 else -1

        if event == cv2.EVENT_MOUSEMOVE:
            hover_idx = idx

        elif event == cv2.EVENT_LBUTTONDOWN and idx >= 0:
            launch(scripts[idx])

    cv2.setMouseCallback(WIN, on_mouse)

    while True:
        cv2.imshow(WIN, make_menu(hover_idx))
        key = cv2.waitKey(30) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            break
        if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
