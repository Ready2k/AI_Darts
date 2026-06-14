#!/usr/bin/env python3
"""Skin the Autodarts LOCAL board manager with our game engine + cinematic UI.

Autodarts runs its proven multi-camera detection locally in the Board Manager
(http://localhost:3180) and streams board/throw events over a WebSocket — the
same local source ioBroker.autodarts consumes (no cloud account / auth needed).
This adapter subscribes to that stream and feeds each detected dart into OUR
scoring engine (game.X01Game via detect.GAME). Because server.GameHub already
watches detect.GAME and broadcasts changes to the frontend, the cinematic UI +
stats become a "skin" on Autodarts' detection: best-in-class detection, our
experience layer. detect.py (our own CV) stays as a selectable fallback.

Two clean wins from using Autodarts as the engine:
  • per-dart `confidence` → drives our confirmed/provisional model (confidence_level)
  • a `takeout` (board-cleared) event → makes the missing-dart prompt trivial and
    robust: takeout with <3 darts simply calls game.enter_review() — no fragile
    foreground collection-detection needed.

SCHEMA NOTE: the local board-manager WS path + exact message JSON are not cleanly
documented publicly and can vary by board-manager version, so capture them live:

    python3 autodarts_adapter.py --capture --url ws://localhost:3180/<path>

connects and pretty-prints every raw frame — run it, throw a dart and take out,
then paste the real JSON to finalise _parse_message(). EVERYTHING downstream of
the parse (notation→Hit, confidence, record-into-game, takeout→review) is
implemented and unit-tested against mock events (test_autodarts_adapter.py), so
only the field names in _parse_message need confirming from a capture.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

import dartboard


# ── score notation → Hit ───────────────────────────────────────────────────────

_NOTATION = re.compile(r"^([SDT])?(\d{1,2})$", re.I)


def notation_to_hit(s):
    """Map Autodarts score notation to a dartboard.Hit, or None if unrecognised.

    'T20'→Triple 20, 'D12'→Double 12, 'S5'/'5'→Single 5, 'BULL'/'50'→Bullseye(50),
    'OUTER'/'25'→Bull(25), 'MISS'/'OUT'→Miss."""
    s = (s or "").strip().upper()
    if s in ("BULL", "DBULL", "B50", "50", "IB"):
        return dartboard.Hit(50, "Bullseye", "INNER_BULL", 25, 1)
    if s in ("OUTER", "SBULL", "B25", "25", "OB"):
        return dartboard.Hit(25, "Bull", "OUTER_BULL", 25, 1)
    if s in ("MISS", "OUT", "M", "0", ""):
        return dartboard.Hit(0, "Miss", "MISS", 0, 1)
    m = _NOTATION.match(s)
    if not m:
        return None
    mult, num = m.group(1), int(m.group(2))
    if not 1 <= num <= 20:
        return None
    if mult == "T":
        return dartboard.Hit(num * 3, f"Triple {num}", "TRIPLE", num, 3)
    if mult == "D":
        return dartboard.Hit(num * 2, f"Double {num}", "DOUBLE", num, 2)
    return dartboard.Hit(num, str(num), "SINGLE", num, 1)


def bed_to_notation(bed, number):
    """Build notation from a structured segment {bed, number} if that's the shape
    the board manager sends (bed ∈ Single/Double/Triple/SingleInner/Outer/Inner…)."""
    if number in (25, 50) or str(bed).lower() in ("bull", "innerbull", "bullseye"):
        return "BULL" if (number == 50 or "inner" in str(bed).lower()) else "OUTER"
    b = str(bed or "").lower()
    pre = "T" if "triple" in b or b == "t" else "D" if "double" in b or b == "d" else "S"
    return f"{pre}{number}"


# ── confidence: Autodarts float → our level ─────────────────────────────────────

CONF_CONFIRMED_AT = 0.90   # >= → confirmed (auto-score)
CONF_PROVISIONAL_AT = 0.60  # >= → provisional; below → low


def confidence_level(conf):
    """Autodarts' 0..1 detection confidence → our confidence model. A missing
    confidence means the engine gave a definitive score → trust it (confirmed)."""
    if conf is None:
        return "confirmed"
    if conf >= CONF_CONFIRMED_AT:
        return "confirmed"
    if conf >= CONF_PROVISIONAL_AT:
        return "provisional"
    return "low"


# ── normalized event ────────────────────────────────────────────────────────────

@dataclass
class DartEvent:
    kind: str                      # "throw" | "takeout" | "other"
    hit: Optional[object] = None   # dartboard.Hit for a throw
    position: Optional[tuple] = None   # (x_mm, y_mm) if the engine gives board coords
    confidence: Optional[float] = None
    raw: dict = field(default_factory=dict)


def _parse_message(data):
    """Best-effort map of a local board-manager message to a DartEvent.

    >>> FINALISE the field names from `--capture` against your board manager. <<<
    Tolerant of a few likely shapes so a capture only needs small tweaks:
      throw:   {"event":"throw","throw":{"segment":{"name":"T20","bed":"Triple",
                "number":20},"coords":{"x":..,"y":..},"confidence":0.94}}
               or a flat {"score":"T20","confidence":..}
      takeout: {"event":"takeout"} / status "Takeout" / "board_stopped"
    """
    if not isinstance(data, dict):
        return None
    ev = str(data.get("event") or data.get("type") or data.get("status") or "").lower()
    if "takeout" in ev or ev in ("board_stopped", "stopped"):
        return DartEvent(kind="takeout", raw=data)

    throw = data.get("throw") or data.get("dart") or data
    if not isinstance(throw, dict):
        return DartEvent(kind="other", raw=data)

    seg = throw.get("segment")
    notation = None
    if isinstance(seg, dict):
        notation = seg.get("name") or bed_to_notation(seg.get("bed"), seg.get("number"))
    notation = notation or throw.get("score") or throw.get("notation")
    if notation is None:
        return DartEvent(kind="other", raw=data)

    hit = notation_to_hit(str(notation))
    if hit is None:
        return DartEvent(kind="other", raw=data)

    coords = throw.get("coords") or throw.get("position")
    position = None
    if isinstance(coords, dict) and "x" in coords and "y" in coords:
        # NOTE: confirm whether coords are board-mm (bull origin) — if so they can
        # be passed straight through for click-to-correct display. Pixel coords
        # would need the board homography; left None until confirmed.
        position = None
    return DartEvent(kind="throw", hit=hit, position=position,
                     confidence=throw.get("confidence"), raw=data)


# ── applying events to the game ─────────────────────────────────────────────────

def record_into(game, ev):
    """Apply a DartEvent to a game (pure — no locking). A throw is recorded with
    its confidence; a takeout on a SHORT visit (1-2 darts) opens the missing-dart
    review. Returns the engine result (or None)."""
    if ev is None or game is None:
        return None
    if ev.kind == "throw" and ev.hit is not None:
        return game.record_hit(ev.hit, ev.position, confidence=confidence_level(ev.confidence))
    if ev.kind == "takeout":
        if 0 < len(game.turn) < 3 and not game.over:
            return game.enter_review(reason="missing_dart")
    return None


def apply_event(ev):
    """Thread-safe apply to the shared detect.GAME (starts one if needed)."""
    import detect
    with detect.GAME_LOCK:
        if detect.GAME is None and ev is not None and ev.kind == "throw":
            pass  # caller should new_game() first; avoid surprise auto-start here
        return record_into(detect.GAME, ev)


# ── websocket worker ────────────────────────────────────────────────────────────

async def run(url, on_event=apply_event):
    """Subscribe to the local board-manager WS and pump events into the game.
    Auto-reconnects. Intended to run as a background task in server.py when the
    detection source is set to 'autodarts'."""
    import websockets
    async for ws in websockets.connect(url):
        print(f"[autodarts] connected {url}")
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except ValueError:
                    continue
                on_event(_parse_message(data))
        except websockets.ConnectionClosed:
            print("[autodarts] connection closed — reconnecting")
            continue


async def capture(url):
    """Connect and pretty-print every raw frame so the message schema can be read
    off a real board manager. Run it, throw a dart, then take the darts out."""
    import websockets
    async with websockets.connect(url) as ws:
        print(f"[autodarts] connected {url} — throw a dart, then take out. Ctrl-C to stop.")
        async for raw in ws:
            try:
                print(json.dumps(json.loads(raw), indent=2))
            except ValueError:
                print(repr(raw))


def main(argv=None):
    import asyncio
    ap = argparse.ArgumentParser(description="Skin the Autodarts local board manager.")
    ap.add_argument("--url", required=True,
                    help="local board-manager WS, e.g. ws://localhost:3180/<path> "
                         "(find the exact path via the board manager / a capture)")
    ap.add_argument("--capture", action="store_true",
                    help="just print raw frames to learn the message schema")
    args = ap.parse_args(argv)
    try:
        asyncio.run(capture(args.url) if args.capture else run(args.url))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
