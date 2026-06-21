#!/usr/bin/env python3
"""
Offline replay harness — re-run dart detection on a recorded match.

A `debug_recordings/match_<stamp>/` folder (written by debug_recorder.py during a
live match) holds everything needed to reproduce detection deterministically:

    raw_cam0.avi, raw_cam1.avi, raw_cam2.avi   the RAW (unannotated) inputs the
        pipeline saw; frame N of each file lines up in time (all three are written
        on the same throttle tick by DebugRecorder.raw_frames).
    alignment.json    the per-camera homographies (cam pixel -> canonical) the
        match ran with.
    backgrounds.npz   the empty-board grayscale references used for subtraction
        (keys are STRING cam indices: "0","1","2").
    telemetry.jsonl   per-event log incl `raw_tick` events (frame index per cam).
    meta.json         tuning constants + game config.

This module feeds those raw frames through the REAL detection primitives in
detect.py — `detect_all_darts` (the per-camera contour/shaft extraction),
`find_consensus_tips` (cross-camera tip clustering), `roi_from_homography`
(board mask) and `to_canonical`/`score_canonical` — so a phantom or a missed dart
can be diagnosed offline frame-by-frame without reproducing it live.

It is NOT the detect loop / tracker: it runs the same *primitives* the loop runs
each iteration and prints per-frame, per-camera diagnostics (shafts per camera,
their canonical-projected endpoints, the resulting clusters). The tracker /
scene-settle / contamination gates that decide *when* to commit a score are
deliberately out of scope — this rig is for understanding what each camera and
the triangulation produce on a given recorded frame.

Usage:
    python3 replay.py debug_recordings/match_20260613_221200          # all frames
    python3 replay.py <dir> --frames 660-708                          # a range
    python3 replay.py <dir> --frames 708 --canonical out.png          # dump warp

Importable:
    rec = Recording("debug_recordings/match_20260613_221200")
    for fr in rec.frames(660, 708):
        diag = rec.analyse(fr)        # FrameDiag with per-cam shafts + clusters
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

import detect
import line_tips


# ── Per-frame diagnostics ──────────────────────────────────────────────────────

class CamDiag:
    """What one camera produced on one replayed frame."""
    def __init__(self, cam_idx):
        self.cam_idx   = cam_idx
        self.n_shafts  = 0           # contours that passed area/aspect/ROI filters
        self.fg_area   = 0           # foreground pixel count (occupancy metric)
        self.shafts    = []          # list of (p1, p2, shaft_len) in camera px
        self.tips_canon = []         # both endpoints projected to canonical space


class FrameDiag:
    """All cameras + the cross-camera clustering for one replayed frame."""
    def __init__(self, index):
        self.index    = index        # raw frame index (1-based, matches raw_tick)
        self.cams     = {}           # cam_idx -> CamDiag
        self.clusters = []           # find_consensus_tips output: (avg, cams, spread)

    def cam_counts(self):
        """Compact 'c0:N c1:N c2:N' summary of shafts per camera."""
        return " ".join(f"c{i}:{self.cams[i].n_shafts}"
                        for i in sorted(self.cams))


# ── Recording ──────────────────────────────────────────────────────────────────

class Recording:
    """A recorded match, replayable through the real detection primitives."""

    def __init__(self, path):
        self.dir = Path(path)
        if not self.dir.is_dir():
            raise FileNotFoundError(f"not a recording dir: {self.dir}")

        # Homographies (cam pixel -> canonical). load_alignment() reads ./alignment.json
        # from the cwd, so parse the recording's own copy directly here.
        align = json.loads((self.dir / "alignment.json").read_text())
        self.homographies = {int(k): np.array(v, dtype=np.float64)
                             for k, v in align.items()}

        # Empty-board grayscale references for background subtraction. Keys are
        # STRING cam indices in the npz (save_arrays stringifies them).
        bg = np.load(self.dir / "backgrounds.npz")
        self.backgrounds = {int(k): bg[k] for k in bg.files}

        # Per-camera board ROI masks — the same deterministic disc-inverse-warp the
        # live loop uses (roi_from_homography), so a tip outside the board is masked
        # off identically. Falls back to no mask if a camera lacks a homography.
        self.rois = {}
        for cam_idx, bgimg in self.backgrounds.items():
            H = self.homographies.get(cam_idx)
            self.rois[cam_idx] = (detect.roi_from_homography(H, bgimg.shape)
                                  if H is not None else None)

        # Raw video readers, one per camera that has a file.
        self._caps = {}
        for cam_idx in sorted(self.backgrounds):
            f = self.dir / f"raw_cam{cam_idx}.avi"
            if f.exists():
                self._caps[cam_idx] = cv2.VideoCapture(str(f))
        if not self._caps:
            raise FileNotFoundError(f"no raw_cam*.avi files in {self.dir}")

        self.n_frames = min(int(c.get(cv2.CAP_PROP_FRAME_COUNT))
                            for c in self._caps.values())

        self.meta = {}
        meta_f = self.dir / "meta.json"
        if meta_f.exists():
            self.meta = json.loads(meta_f.read_text())

    # ── frame access ──────────────────────────────────────────────────────────
    def read_frame(self, index):
        """Read raw frame `index` (1-based, matching the raw_tick telemetry) from
        every camera. Returns {cam_idx: BGR frame} (missing/short cameras omitted)."""
        frames = {}
        for cam_idx, cap in self._caps.items():
            cap.set(cv2.CAP_PROP_POS_FRAMES, index - 1)   # 0-based seek
            ok, frame = cap.read()
            if ok and frame is not None:
                frames[cam_idx] = frame
        return frames

    def frames(self, start=1, end=None):
        """Yield frame indices in [start, end] (1-based inclusive)."""
        end = self.n_frames if end is None else min(end, self.n_frames)
        for i in range(max(1, start), end + 1):
            yield i

    # ── analysis ──────────────────────────────────────────────────────────────
    def analyse(self, index):
        """Run the real per-camera detection + cross-camera clustering on one frame.

        Mirrors what the live loop does each iteration: per camera, diff the raw
        frame against the empty-board background (detect_all_darts with the camera's
        ROI + its CAM_MIN_ASPECT floor), collect BOTH endpoints of every shaft,
        project them to canonical space, then cluster across cameras with
        find_consensus_tips. Returns a FrameDiag.
        """
        frames = self.read_frame(index)
        diag = FrameDiag(index)
        all_tips_by_cam = {}
        shafts_by_cam = {}

        for cam_idx in sorted(self.backgrounds):
            cd = CamDiag(cam_idx)
            diag.cams[cam_idx] = cd
            frame = frames.get(cam_idx)
            if frame is None:
                continue
            bg  = self.backgrounds[cam_idx]
            roi = self.rois.get(cam_idx)
            min_aspect = detect.CAM_MIN_ASPECT.get(cam_idx, 1.6)
            darts, fg_area = detect.detect_all_darts(
                frame, bg, roi, min_aspect=min_aspect, empty_background=bg)
            cd.fg_area  = fg_area
            cd.n_shafts = len(darts)

            tips = []
            for p1, p2, _contour in darts:
                shaft_len = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
                cd.shafts.append((p1, p2, shaft_len))
                # Both endpoints feed the consensus, weighted by shaft length — the
                # flight end scatters across cameras and falls out as a singleton.
                tips.append((p1, shaft_len))
                tips.append((p2, shaft_len))
                for end in (p1, p2):
                    c = detect.to_canonical(end, cam_idx, self.homographies)
                    if c is not None:
                        cd.tips_canon.append(c)
            all_tips_by_cam[cam_idx] = tips
            # Full shaft lines in pixel space for the line-intersection tip finder —
            # the same input the live detect loop now feeds find_tips_by_lines.
            shafts_by_cam[cam_idx] = [(p1, p2) for p1, p2, _c in darts]

        # Mirror the live loop: shaft-line intersection (warp whole shafts to
        # canonical and meet them at the board plane), gated by the same tight
        # limits, instead of both-endpoint clustering.
        diag.clusters = line_tips.find_tips_by_lines(
            shafts_by_cam, self.homographies,
            min_cams=detect.MIN_CAMS_TO_TRIGGER,
            tight_2cam=detect.CLUSTER_TIGHT, tight_3cam=detect.CLUSTER_TIGHT_3CAM)
        return diag

    def close(self):
        for cap in self._caps.values():
            cap.release()


# ── diagnostic printing ─────────────────────────────────────────────────────────

def _print_frame(rec, diag, verbose=False):
    """One-line-per-camera + cluster summary for a replayed frame."""
    print(f"\nframe {diag.index:>5}   shafts {diag.cam_counts()}")
    for cam_idx in sorted(diag.cams):
        cd = diag.cams[cam_idx]
        print(f"  cam{cam_idx}: {cd.n_shafts} shaft(s)  fg={cd.fg_area}")
        if verbose:
            for (p1, p2, slen), c in zip(cd.shafts,
                                         _pairs(cd.tips_canon)):
                ca, cb = c
                print(f"      shaft len={slen:5.1f}px  "
                      f"p1=({p1[0]:6.1f},{p1[1]:6.1f})->canon"
                      f"({ca[0]:6.1f},{ca[1]:6.1f})  "
                      f"p2=({p2[0]:6.1f},{p2[1]:6.1f})->canon"
                      f"({cb[0]:6.1f},{cb[1]:6.1f})")
    if not diag.clusters:
        print("  clusters: none")
        return
    print("  clusters (most cameras first):")
    for avg, cams, spread in diag.clusters:
        hit = detect.score_canonical(avg)
        tag = "".join(str(c) for c in sorted(cams))
        print(f"      canon=({avg[0]:6.1f},{avg[1]:6.1f})  "
              f"cams={{{tag}}} ({len(cams)})  spread={spread:4.1f}  "
              f"-> {hit.label} ({hit.points})")


def _pairs(flat):
    """Group a flat [p1c, p2c, p1c, p2c, ...] list back into per-shaft pairs."""
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def _parse_range(spec, n_frames):
    """'660-708' -> (660,708); '708' -> (708,708); None -> (1,n_frames)."""
    if not spec:
        return 1, n_frames
    if "-" in spec:
        a, b = spec.split("-", 1)
        return int(a), int(b)
    v = int(spec)
    return v, v


def main(argv=None):
    ap = argparse.ArgumentParser(description="Replay a recorded darts match offline.")
    ap.add_argument("recording", help="path to debug_recordings/match_<stamp>/")
    ap.add_argument("--frames", help="frame index or range, e.g. 660-708 (default: all)")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="print every shaft's endpoints + canonical projection")
    ap.add_argument("--canonical", metavar="PNG",
                    help="for a single --frames F, warp+merge all cameras into the "
                         "canonical board and save the overlay to this PNG")
    args = ap.parse_args(argv)

    rec = Recording(args.recording)
    start, end = _parse_range(args.frames, rec.n_frames)
    cams = ",".join(str(c) for c in sorted(rec.backgrounds))
    print(f"Recording: {rec.dir}")
    print(f"  cameras: {cams}   raw frames: {rec.n_frames}   "
          f"replaying {start}..{end}")

    for idx in rec.frames(start, end):
        diag = rec.analyse(idx)
        _print_frame(rec, diag, verbose=args.verbose)

    if args.canonical and start == end:
        _dump_canonical(rec, start, args.canonical)

    rec.close()
    return 0


def _dump_canonical(rec, index, out_png):
    """Warp every camera's raw frame into the canonical board and stack them, so a
    misread can be eyeballed (where did each camera think the tip was?)."""
    frames = rec.read_frame(index)
    panels = []
    for cam_idx in sorted(frames):
        H = rec.homographies.get(cam_idx)
        if H is None:
            continue
        warp = cv2.warpPerspective(frames[cam_idx], H,
                                   (detect.CANONICAL_SIZE, detect.CANONICAL_SIZE))
        cv2.putText(warp, f"cam{cam_idx}", (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        panels.append(warp)
    if panels:
        cv2.imwrite(out_png, np.hstack(panels))
        print(f"  wrote canonical overlay -> {out_png}")


if __name__ == "__main__":
    sys.exit(main())
