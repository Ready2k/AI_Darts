#!/usr/bin/env python3
"""Generate a printable A4 checkerboard PDF for camera calibration.

Pattern: 10x7 squares (9x6 inner corners), 25mm per square.
Print at 100% scale (no 'fit to page') on A4 paper.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

COLS = 8        # squares wide
ROWS = 6        # squares tall
SQUARE_MM = 20  # physical size of each square in mm

# A5 in mm (half of A4, fits in hand and in tight camera FOVs)
PAGE_W_MM = 148
PAGE_H_MM = 210

BOARD_W_MM = COLS * SQUARE_MM   # 160mm
BOARD_H_MM = ROWS * SQUARE_MM   # 120mm

# Centre the board on the page
MARGIN_X = (PAGE_W_MM - BOARD_W_MM) / 2
MARGIN_Y = (PAGE_H_MM - BOARD_H_MM) / 2

fig = plt.figure(figsize=(PAGE_W_MM / 25.4, PAGE_H_MM / 25.4))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, PAGE_W_MM)
ax.set_ylim(0, PAGE_H_MM)
ax.set_aspect("equal")
ax.axis("off")

# White background
fig.patch.set_facecolor("white")

# Draw squares
for row in range(ROWS):
    for col in range(COLS):
        if (row + col) % 2 == 0:
            color = "black"
        else:
            color = "white"
        x = MARGIN_X + col * SQUARE_MM
        y = MARGIN_Y + row * SQUARE_MM
        rect = patches.Rectangle((x, y), SQUARE_MM, SQUARE_MM,
                                  linewidth=0, facecolor=color)
        ax.add_patch(rect)

# Border around the whole board
border = patches.Rectangle((MARGIN_X, MARGIN_Y), BOARD_W_MM, BOARD_H_MM,
                             linewidth=0.5, edgecolor="black", facecolor="none")
ax.add_patch(border)

# Label at bottom
label = (f"Darts camera calibration checkerboard  |  "
         f"{COLS}x{ROWS} squares  |  {SQUARE_MM}mm per square  |  "
         f"Print at 100% scale on A5 (or A4 - do not scale)")
ax.text(PAGE_W_MM / 2, MARGIN_Y / 2, label,
        ha="center", va="center", fontsize=6, color="#333333")

out = "checkerboard_20mm_A5.pdf"
plt.savefig(out, format="pdf", dpi=300, bbox_inches=None,
            facecolor="white", edgecolor="none")
print(f"Saved: {out}")
print(f"Pattern: {COLS-1}x{ROWS-1} inner corners  ({COLS}x{ROWS} squares)")
print(f"Square size: {SQUARE_MM}mm  —  measure one square after printing to verify scale")
