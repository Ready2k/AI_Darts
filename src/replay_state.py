#!/usr/bin/env python3
"""Offline STATE-MACHINE replay — run the real scoring loop on a recording.

Where replay.py reproduces only the per-frame GEOMETRY (detect_all_darts +
find_tips_by_lines clusters), this harness drives the ACTUAL detection state
machine offline: it feeds a recording's raw frames through the SAME per-frame
body the live detect loop runs — `detect.step_tracker` (the tracker / pending /
scene-settle / contamination / commit / board-clear logic) — so the sequence of
*scored darts* and *state transitions* a match produced (or should now produce
with the current code) can be reproduced and diagnosed without the cameras.

There is ONE implementation of that logic: detect._run_detection and this replay
both call detect.step_tracker, so the replay can't drift from live behaviour. The
only things injected differently are the I/O effects step_tracker can't do itself
(telemetry, audio, the two background operations) — see `detect.step_tracker`.

Frame rate caveat: the recorder throttles raw_cam*.avi to ~15 fps while the live
loop ran ~30 fps, so replay calls step_tracker once per ~2 live iterations. The
per-frame counters (CONFIRM_FRAMES, seen, consensus…) therefore advance at half
the live rate, but darts persist on the board for seconds, so a dart still easily
clears those gates — only the exact confirming frame shifts. Wall-clock gates
(ARRIVAL_WINDOW, ABSENT_SECS, CLEAR_SETTLE_SECS) use the recording's real
per-frame timestamps (from the `raw_tick` telemetry), so they behave faithfully.

Usage:
    python3 replay_state.py debug_recordings/match_20260614_135743        # whole match
    python3 replay_state.py <dir> --frames 700-760                        # a window
    python3 replay_state.py <dir> --events                                # dump all events

Importable:
    sr = StateReplay("debug_recordings/match_20260614_135743")
    sr.run()                  # whole recording
    sr.scored                 # [{"label","points","canonical","n_cams","t"}, ...]
    sr.transitions            # [{"frm","to","t"}, ...]
"""

import argparse
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import cv2

import detect
import game
import replay


class _DummyLock:
    """No-op stand-in for GAME_LOCK — replay is single-threaded."""
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


class StateReplay:
    """Drive detect.step_tracker over a recording, collecting scored darts."""

    def __init__(self, path, *, game_config=None, verbose=False):
        self.rec = replay.Recording(path)
        self.verbose = verbose
        # Mutable copies — healing and board-clear mutate these exactly as the
        # live loop mutates its own `backgrounds` / `bg_detect`.
        self.backgrounds = {i: b.copy() for i, b in self.rec.backgrounds.items()}
        self.bg_detect   = {i: b.copy() for i, b in self.backgrounds.items()}
        self.rois         = self.rec.rois
        self.homographies = self.rec.homographies
        self.frame_times  = self._load_frame_times()

        cfg = dict(self.rec.meta or {})
        if game_config:
            cfg.update(game_config)
        players = cfg.get("players") or ["Player 1"]
        self.game = game.X01Game(
            players,
            start_score=cfg.get("start_score", 501),
            double_in=cfg.get("double_in", False),
            double_out=cfg.get("double_out", True),
            legs_to_win=cfg.get("legs_to_win", 1),
            sets_to_win=cfg.get("sets_to_win", 1),
        )
        self.lock = _DummyLock()
        self.st   = detect.TrackerState(len(self.backgrounds))

        self.events      = []   # every telemetry event step_tracker emitted
        self.scored      = []   # convenience: just the scored darts
        self.transitions = []   # phase changes (watching <-> all_done)
        self._now        = 0.0
        self._cur_gray   = {}
        self.settle_ref  = None   # arrival-isolation reference (see detect.step_tracker)

    # ── recording timing ───────────────────────────────────────────────────
    def _load_frame_times(self):
        """Map raw frame index -> seconds, read from the `raw_tick` telemetry.

        Each raw_tick logs the monotonic time of the batch and the per-camera
        frame counter; all cameras share the tick so one index maps to one time.
        """
        times = {}
        tel = self.rec.dir / "telemetry.jsonl"
        if tel.exists():
            for line in tel.read_text().splitlines():
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("kind") == "raw_tick":
                    idx = e.get("index", {})
                    n = next(iter(idx.values()), None)
                    if n is not None:
                        times[int(n)] = e.get("t", 0.0)
        return times

    def _time_for(self, frame_index, fallback_dt=1.0 / 15.0):
        """Seconds for a frame; interpolate/extrapolate if not directly logged."""
        if frame_index in self.frame_times:
            return self.frame_times[frame_index]
        if not self.frame_times:
            return frame_index * fallback_dt
        # nearest known index, advanced by the nominal frame interval
        keys = sorted(self.frame_times)
        if frame_index < keys[0]:
            return self.frame_times[keys[0]] - (keys[0] - frame_index) * fallback_dt
        prev = max(k for k in keys if k <= frame_index)
        return self.frame_times[prev] + (frame_index - prev) * fallback_dt

    # ── injected effects ────────────────────────────────────────────────────
    def _emit(self, kind, **fields):
        rec = {"kind": kind, "t": round(self._now, 3)}
        rec.update(fields)
        self.events.append(rec)
        if kind == "scored":
            self.scored.append({
                "t": round(self._now, 2), "label": fields.get("label"),
                "points": fields.get("points"),
                "canonical": [round(x) for x in fields.get("canonical", (0, 0))],
                "n_cams": fields.get("n_cams"), "spread": fields.get("spread"),
                "seen": fields.get("seen"),
            })

    def _heal(self):
        # Blend the current frame into the empty-board references (lighting
        # drift), keeping bg_detect tracking the healed board — mirrors the live
        # _heal, but on the recording's current frame (no fresh camera read).
        for cam, g in self._cur_gray.items():
            self.backgrounds[cam] = cv2.addWeighted(self.backgrounds[cam], 0.95,
                                                    g, 0.05, 0)
            self.bg_detect[cam] = self.backgrounds[cam].copy()

    def _reset_bg_detect(self):
        self.bg_detect = {i: b.copy() for i, b in self.backgrounds.items()}

    # ── per-frame ───────────────────────────────────────────────────────────
    def _step(self, frame_index, frames):
        self._now = self._time_for(frame_index)
        shafts_by_cam, darts_by_cam, fg_by_cam = {}, {}, {}
        self._cur_gray = {}
        max_fg = 0
        for cam in sorted(self.backgrounds):
            frame = frames.get(cam)
            if frame is None:
                continue
            self._cur_gray[cam] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            roi = self.rois.get(cam)
            min_aspect = detect.CAM_MIN_ASPECT.get(cam, 1.6)
            darts, fg = detect.detect_all_darts(
                frame, self.bg_detect[cam], roi, min_aspect=min_aspect,
                empty_background=self.backgrounds[cam])
            darts_by_cam[cam] = darts
            shafts_by_cam[cam] = [(p1, p2) for p1, p2, _c in darts]
            fg_by_cam[cam] = fg
            max_fg = max(max_fg, fg)

        # Arrival-isolation shafts (newest dart vs the last settled board) —
        # mirrors the live loop so the touching-darts path is exercised offline.
        new_shafts_by_cam = {}
        if self.settle_ref is not None and self.st.scored_canonical:
            for cam, frame in frames.items():
                ref = self.settle_ref.get(cam)
                if ref is None:
                    continue
                nd, _ = detect.detect_all_darts(
                    frame, ref, self.rois.get(cam),
                    min_aspect=detect.CAM_MIN_ASPECT.get(cam, 1.6),
                    empty_background=ref)
                new_shafts_by_cam[cam] = [(p1, p2) for p1, p2, _c in nd]

        prev_phase = self.st.dart_state
        out = sys.stdout if self.verbose else StringIO()
        with redirect_stdout(out):
            detect.step_tracker(
                self.st, self._now, max_fg, shafts_by_cam, darts_by_cam,
                self.homographies, self.game, self.lock,
                new_shafts_by_cam=new_shafts_by_cam, fg_by_cam=fg_by_cam,
                emit=self._emit, say=lambda *a, **k: None,
                heal=self._heal, reset_bg_detect=self._reset_bg_detect)
        # Maintain the arrival-isolation reference (capture after a commit, drop
        # on visit reset) — same policy as the live loop.
        if self.st.want_settle_snapshot:
            self.settle_ref = dict(self._cur_gray)
            self.st.want_settle_snapshot = False
        if not self.st.scored_canonical:
            self.settle_ref = None
        if self.st.dart_state != prev_phase:
            self.transitions.append({"t": round(self._now, 2),
                                     "frm": prev_phase, "to": self.st.dart_state})

    def run(self, start=1, end=None):
        """Replay frames [start, end] (1-based inclusive) through the state machine.

        Reads sequentially (one seek to `start`, then plain reads) so a full
        recording replays without per-frame seeking.
        """
        end = self.rec.n_frames if end is None else min(end, self.rec.n_frames)
        start = max(1, start)
        for cap in self.rec._caps.values():
            cap.set(cv2.CAP_PROP_POS_FRAMES, start - 1)
        for idx in range(start, end + 1):
            frames = {}
            for cam, cap in self.rec._caps.items():
                ok, fr = cap.read()
                if ok and fr is not None:
                    frames[cam] = fr
            if not frames:
                break
            self._step(idx, frames)
        return self.scored

    def close(self):
        self.rec.close()


# ── CLI ──────────────────────────────────────────────────────────────────────

def _parse_range(spec, n_frames):
    if not spec:
        return 1, n_frames
    if "-" in spec:
        a, b = spec.split("-", 1)
        return int(a), int(b)
    v = int(spec)
    return v, v


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Replay a recorded match through the real scoring state machine.")
    ap.add_argument("recording", help="path to debug_recordings/match_<stamp>/")
    ap.add_argument("--frames", help="frame index or range, e.g. 700-760 (default: all)")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="let step_tracker's per-frame diagnostics print")
    ap.add_argument("--events", action="store_true",
                    help="dump every emitted event (scored/dropped/board_cleared/…)")
    args = ap.parse_args(argv)

    sr = StateReplay(args.recording, verbose=args.verbose)
    start, end = _parse_range(args.frames, sr.rec.n_frames)
    cams = ",".join(str(c) for c in sorted(sr.rec.backgrounds))
    print(f"Recording: {sr.rec.dir}")
    print(f"  cameras: {cams}   raw frames: {sr.rec.n_frames}   "
          f"replaying {start}..{end}   state-machine replay")
    sr.run(start, end)

    print("\n── scored darts ──")
    if not sr.scored:
        print("  (none)")
    for d in sr.scored:
        print(f"  t={d['t']:>6}  {d['label']:<10} ({d['points']:>2})  "
              f"canon={d['canonical']}  cams={d['n_cams']}  "
              f"spread={d['spread']}  seen={d['seen']}")

    print("\n── phase transitions ──")
    for tr in sr.transitions:
        print(f"  t={tr['t']:>6}  {tr['frm']} -> {tr['to']}")

    if args.events:
        print("\n── all events ──")
        for e in sr.events:
            if e["kind"] != "fg":
                print(" ", json.dumps(e, default=str))

    visits = sum(1 for tr in sr.transitions if tr["to"] == "all_done")
    print(f"\nSummary: {len(sr.scored)} darts scored, {visits} visit(s) completed.")
    sr.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
