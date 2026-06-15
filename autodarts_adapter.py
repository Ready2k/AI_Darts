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

import dartboard

# Set to True while the websocket worker is connected, False otherwise.
# Polled by GET /api/config to surface board-manager status in the UI.
CONNECTED = False

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


# ── one throw → Hit + board position ────────────────────────────────────────────

def throw_to_hit(throw):
    """Map one Autodarts throw to (dartboard.Hit, (x_mm, y_mm) | None).

    Shape (confirmed from a live local board manager v1.0.7):
        {"segment": {"name":"S20","number":20,"bed":"SingleOuter","multiplier":1},
         "coords":  {"x": 0.0517, "y": 0.8814}}
    `segment.name` is Autodarts' authoritative score; `coords` are normalized
    board units (origin = bull, y-up toward 20, 1.0 ≈ the double-out ring), so
    ×DOUBLE_OUT gives board-mm for click-to-correct display."""
    seg = throw.get("segment") or {}
    name = seg.get("name") or bed_to_notation(seg.get("bed"), seg.get("number"))
    hit = notation_to_hit(str(name))
    coords = throw.get("coords") or {}
    pos = None
    if "x" in coords and "y" in coords:
        pos = (coords["x"] * dartboard.DOUBLE_OUT, coords["y"] * dartboard.DOUBLE_OUT)
    return hit, pos


# ── stream consumer ──────────────────────────────────────────────────────────────

class AutodartsConsumer:
    """Reconciles the board manager's cumulative per-visit `state` stream into our
    game. Each `Throw detected` re-sends the full throws[] for the visit, so we
    record only the newly-added darts.

    Reconciliation guards (our game's visit model can close BEFORE Autodarts'
    visit does — Autodarts keeps reporting darts until takeout):
      • once our visit ends early — a BUST, a CHECKOUT/leg win, or our 3rd dart —
        further throws of the SAME Autodarts visit are IGNORED (consumed, not
        recorded) until takeout/rollover, so a busted player's extra dart can't
        leak onto the next player.
      • when the MATCH is over, throws are ignored until a new game is started.
      • before any game exists, throws are consumed (not backfilled) so starting a
        game mid-visit doesn't dump the in-progress darts in.

    `Takeout started` ends the visit: a genuinely short visit (1-2 darts, not
    already closed by a bust/checkout) is advanced (Autodarts is trusted, so no
    missing-dart prompt is needed the way our own cameras needed one). A new visit
    (numThrows rolls back) or a `Manual reset` resets the per-visit state."""

    def __init__(self):
        self._recorded = 0       # darts of the current visit already consumed
        self._closed = False     # takeout handled for this visit
        self._visit_done = False  # our game already closed this visit (bust/checkout/3rd)

    def reset(self):
        self._recorded = 0
        self._closed = False
        self._visit_done = False

    def on_message(self, msg, game):
        """Process one WS message against `game`. Returns the list of engine
        results (record_hit events) produced, for logging/telemetry."""
        results = []
        if not isinstance(msg, dict) or msg.get("type") != "state":
            return results
        d = msg.get("data") or {}
        event = str(d.get("event") or "")
        throws = d.get("throws") or []
        n = d.get("numThrows", len(throws))

        if event == "Manual reset" or n < self._recorded:   # new visit / reset
            self.reset()

        if game is None:
            # No game yet — consume so a later new-game doesn't backfill these.
            self._recorded = max(self._recorded, len(throws))
            return results

        if len(throws) > self._recorded:
            for t in throws[self._recorded:]:
                if self._visit_done or game.over:
                    continue          # visit already closed / match over — ignore
                hit, pos = throw_to_hit(t)
                if hit is None:
                    continue
                ev = game.record_hit(hit, pos, confidence="confirmed")
                results.append(ev)
                print(f"[autodarts] {hit.label} ({hit.points})")
                if ev.get("turn_over") or game.over:
                    self._visit_done = True   # bust / 3rd dart / leg|match win
            self._recorded = len(throws)

        if event == "Takeout started" and not self._closed:
            self._closed = True
            if (not self._visit_done and not game.over
                    and 0 < len(game.turn) < 3):
                # genuinely short visit (player stopped / bounce-out) — advance it
                game.enter_review(reason="autodarts_short")
                results.append(game.confirm_review())
        return results


# ── websocket worker ────────────────────────────────────────────────────────────

def _apply_to_shared_game(consumer, msg):
    """Thread-safe: apply a message to the shared detect.GAME (server.GameHub then
    broadcasts the change to the cinematic frontend)."""
    import detect
    with detect.GAME_LOCK:
        if detect.GAME is None:
            return
        consumer.on_message(msg, detect.GAME)


async def run(url, on_message=None, retry_secs=3.0):
    """Subscribe to the local board-manager WS and pump dart events into the game.
    Resilient: retries the initial connection and reconnects on drops, so it can
    be started before the board manager (or mock) is up. Intended to run as a
    background task in server.py when the detection source is 'autodarts'.
    `on_message(consumer, msg)` defaults to applying to the shared detect.GAME."""
    import asyncio
    import websockets
    global CONNECTED
    consumer = AutodartsConsumer()
    sink = on_message or (lambda c, m: _apply_to_shared_game(c, m))
    while True:
        try:
            async with websockets.connect(url, max_size=None) as ws:
                print(f"[autodarts] connected {url}")
                CONNECTED = True
                consumer.reset()
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                    except ValueError:
                        continue
                    sink(consumer, data)
        except asyncio.CancelledError:
            CONNECTED = False
            raise
        except Exception as e:
            CONNECTED = False
            print(f"[autodarts] not connected ({type(e).__name__}: {e}); "
                  f"retrying in {retry_secs:.0f}s")
            await asyncio.sleep(retry_secs)


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
