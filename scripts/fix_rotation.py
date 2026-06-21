"""
Programmatically find and apply the best rotation correction to alignment.json.
Loads the warped images from the latest debug snapshot, tests rotation angles
-25° to +25°, picks the sharpest (best-aligned segment wires), saves to alignment.json.
"""
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np


CANONICAL_SIZE = 500
CENTRE = 250


def make_rotation_matrix(theta_deg):
    """Rotation matrix that rotates the canonical board image CW by theta_deg."""
    theta = math.radians(theta_deg)
    c, s = math.cos(theta), math.sin(theta)
    return np.array([
        [c,  -s,  CENTRE * (1 - c + s)],
        [s,   c,  CENTRE * (1 - s - c)],
        [0,   0,  1                    ]
    ], dtype=np.float64)


def sharpness_in_annulus(img, inner_r=60, outer_r=200):
    """
    Mean gradient magnitude in the annular region between inner_r and outer_r px
    from the centre. Segment wire transitions show up as high-gradient edges.
    """
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gx = cv2.Sobel(grey, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(grey, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)

    ys, xs = np.ogrid[:CANONICAL_SIZE, :CANONICAL_SIZE]
    r = np.sqrt((xs - CENTRE)**2 + (ys - CENTRE)**2)
    mask = (r >= inner_r) & (r <= outer_r)
    return float(mag[mask].mean())


def load_alignment(path):
    with open(path) as f:
        data = json.load(f)
    # Keys are strings in JSON; convert to int and values to np arrays
    return {int(k): np.array(v, dtype=np.float64) for k, v in data.items()}


def save_alignment(homos, path):
    # Convert numpy arrays back to nested lists for JSON
    out = {str(k): v.tolist() for k, v in homos.items()}
    with open(path, "w") as f:
        json.dump(out, f, indent=2)


def score_rotation(raw_frames, homos, theta_deg):
    """Apply rotation R to all homographies, warp all frames, return mean sharpness."""
    R = make_rotation_matrix(theta_deg)
    scores = []
    for cam_idx, frame in raw_frames.items():
        H = homos.get(cam_idx)
        if H is None:
            continue
        H_new = R @ H  # keep as numpy array — do NOT call .tolist()
        warped = cv2.warpPerspective(frame, H_new, (CANONICAL_SIZE, CANONICAL_SIZE))
        scores.append(sharpness_in_annulus(warped))
    return float(np.mean(scores)) if scores else 0.0


def main():
    project = Path("/Users/jamescregeen/Code_Projects/darts")
    alignment_path = project / "alignment.json"

    # Find latest debug snapshot with raw camera images
    snapshots = sorted((project / "debug_snapshots").glob("*"))
    raw_frames = {}
    snap_used = None
    for snap in reversed(snapshots):
        frames = {}
        for p in snap.glob("cam*_raw.jpg"):
            idx = int(p.stem.replace("cam", "").replace("_raw", ""))
            frames[idx] = cv2.imread(str(p))
        if frames:
            raw_frames = frames
            snap_used = snap
            break

    if not raw_frames:
        print("ERROR: no raw camera frames found in any debug snapshot")
        return

    print(f"Using frames from: {snap_used.name}")
    print(f"Cameras found: {sorted(raw_frames.keys())}")

    homos = load_alignment(alignment_path)
    print(f"Cameras in alignment: {sorted(homos.keys())}")

    # Coarse sweep first
    angles = list(range(-25, 26, 3))
    print(f"\nCoarse sweep ({angles[0]}° to {angles[-1]}° in 3° steps)...")
    results = []
    for theta in angles:
        s = score_rotation(raw_frames, homos, theta)
        results.append((s, theta))
        print(f"  {theta:+4d}°  sharpness={s:.2f}")

    best_score, best_angle = max(results)
    print(f"\nCoarse best: {best_angle:+d}° (sharpness={best_score:.2f})")

    # Fine sweep around best
    fine_angles = [best_angle + 0.5 * i for i in range(-4, 5)]
    print(f"\nFine sweep around {best_angle}° ...")
    fine_results = []
    for theta in fine_angles:
        s = score_rotation(raw_frames, homos, theta)
        fine_results.append((s, theta))
        print(f"  {theta:+5.1f}°  sharpness={s:.2f}")

    fine_score, fine_angle = max(fine_results)
    print(f"\nFinal best: {fine_angle:+.1f}° (sharpness={fine_score:.2f})")

    # Apply the best rotation and save
    print(f"\nApplying rotation {fine_angle:+.1f}° to alignment.json ...")
    backup = alignment_path.with_suffix(".json.bak")
    shutil.copy(alignment_path, backup)
    print(f"  Backed up original → {backup.name}")

    R = make_rotation_matrix(fine_angle)
    new_homos = {k: R @ H for k, H in homos.items()}
    save_alignment(new_homos, alignment_path)
    print(f"  Saved rotated alignment → {alignment_path.name}")

    # Save a verification merged view
    merged_layers = []
    for cam_idx, frame in raw_frames.items():
        H = new_homos.get(cam_idx)
        if H is not None:
            warped = cv2.warpPerspective(frame, H, (CANONICAL_SIZE, CANONICAL_SIZE))
            merged_layers.append(warped.astype(np.float32))
    if merged_layers:
        merged = np.mean(merged_layers, axis=0).astype(np.uint8)
        out_path = project / "debug_snapshots" / "after_rotation.jpg"
        cv2.imwrite(str(out_path), merged)
        print(f"  Saved verification view → debug_snapshots/after_rotation.jpg")

    print("\nDone. Restart the server to pick up the new alignment.")


if __name__ == "__main__":
    main()
