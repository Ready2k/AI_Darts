#!/usr/bin/env python3
"""Mock Autodarts local board manager — replays the REAL /api/events schema so the
full server + adapter + cinematic frontend can be developed and demoed WITHOUT a
board. Streams a scripted 501 game that ends on a D12 checkout, using the exact
message shape captured live from board manager v1.0.7.

    python3 mock_autodarts.py                      # ws://0.0.0.0:3180/api/events (loops)
    python3 mock_autodarts.py --port 13180 --once --delay 0.4

Drive the app with it (separate terminals):
    python3 mock_autodarts.py
    DETECTION_SOURCE=autodarts AUTODARTS_URL=ws://localhost:3180/api/events python3 server.py
    (start a 501 game in the frontend and watch it score + check out)

The message builders are importable so tests can exercise the full adapter→game
path without the WS server (see test_autodarts_adapter.py).
"""

import argparse
import asyncio
import json
import math
import re
import sys

import dartboard

# A scripted 501 single-player game: 180, 180, then a 141 checkout (T20 T19 D12).
SCRIPT_501 = [
    ["T20", "T20", "T20"],   # 501 -> 321
    ["T20", "T20", "T20"],   # 321 -> 141
    ["T20", "T19", "D12"],   # 141 -> 0  (finish on the double)
]

# Mid-ring radii (mm) for plausible coords per ring (coords are cosmetic — scoring
# uses segment.name — but realistic ones round-trip through dartboard.score_detail).
_RING_MM = {"S": 130.0, "T": 103.0, "D": 166.0}


def _coords(notation):
    """Normalized board coords (origin=bull, y-up toward 20, 1.0≈double ring)."""
    n = notation.upper()
    if n in ("BULL", "50"):
        return 0.0, 0.0
    if n in ("OUTER", "25"):
        return 0.0, 11.0 / dartboard.DOUBLE_OUT
    m = re.match(r"([SDT]?)(\d{1,2})$", n)
    ring, num = (m.group(1) or "S"), int(m.group(2))
    ang = math.radians(dartboard.SEGMENTS.index(num) * 18)   # 0°=up=20
    r = _RING_MM.get(ring, 130.0)
    return (math.sin(ang) * r) / dartboard.DOUBLE_OUT, (math.cos(ang) * r) / dartboard.DOUBLE_OUT


def throw(notation):
    """Build one throw object in the real board-manager shape."""
    n = notation.upper()
    if n in ("BULL", "50"):
        seg = {"name": "BULL", "number": 50, "bed": "InnerBull", "multiplier": 1}
    elif n in ("OUTER", "25"):
        seg = {"name": "OUTER", "number": 25, "bed": "OuterBull", "multiplier": 1}
    else:
        m = re.match(r"([SDT]?)(\d{1,2})$", n)
        ring, num = (m.group(1) or "S"), int(m.group(2))
        bed = {"S": "SingleOuter", "D": "Double", "T": "Triple"}[ring]
        mult = {"S": 1, "D": 2, "T": 3}[ring]
        seg = {"name": f"{'S' if ring == 'S' else ring}{num}", "number": num,
               "bed": bed, "multiplier": mult}
    x, y = _coords(n)
    return {"segment": seg, "coords": {"x": x, "y": y}}


def state(event, status, throws):
    return {"type": "state",
            "data": {"connected": True, "running": True, "status": status,
                     "event": event, "numThrows": len(throws), "throws": list(throws)}}


def game_messages(script=SCRIPT_501):
    """The ordered message sequence for a whole game (no timing) — for tests and
    the WS server. Mirrors the live stream: cumulative 'Throw detected' per visit,
    then 'Takeout started/finished' + 'Manual reset' between visits."""
    msgs = []
    for visit in script:
        thrown = []
        for n in visit:
            thrown.append(throw(n))
            msgs.append(state("Throw detected", "Throw", thrown))
        msgs.append(state("Takeout started", "Takeout in progress", thrown))
        msgs.append(state("Takeout finished", "Throw", []))
        msgs.append(state("Manual reset", "Throw", []))
    return msgs


async def _serve_client(ws, delay, once):
    print("[mock] client connected")
    try:
        while True:
            for visit in SCRIPT_501:
                thrown = []
                for n in visit:
                    thrown.append(throw(n))
                    await ws.send(json.dumps(state("Throw detected", "Throw", thrown)))
                    await asyncio.sleep(delay)
                await ws.send(json.dumps(state("Takeout started", "Takeout in progress", thrown)))
                await asyncio.sleep(delay * 0.7)
                await ws.send(json.dumps(state("Takeout finished", "Throw", [])))
                await ws.send(json.dumps(state("Manual reset", "Throw", [])))
                await asyncio.sleep(delay)
            print("[mock] game complete (501 -> 0 on D12)")
            if once:
                break
            await asyncio.sleep(2.0)
    except Exception as e:
        print(f"[mock] client gone ({type(e).__name__})")


async def main(argv=None):
    import websockets
    ap = argparse.ArgumentParser(description="Mock Autodarts board manager (/api/events).")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=3180)
    ap.add_argument("--delay", type=float, default=1.2, help="seconds between darts")
    ap.add_argument("--once", action="store_true", help="play one game then idle")
    args = ap.parse_args(argv)

    async def handler(ws):
        await _serve_client(ws, args.delay, args.once)

    async with websockets.serve(handler, args.host, args.port):
        print(f"[mock] serving ws://{args.host}:{args.port}/api/events "
              f"(delay={args.delay}s, {'once' if args.once else 'loop'})")
        await asyncio.Future()   # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
