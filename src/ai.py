import asyncio
import json
import math
import random
import time
from pathlib import Path

import detect
import dartboard
from checkout import suggest

# Levels to spread mapping (standard deviation in mm)
# The dartboard is 340mm across (double out radius is 170mm).
# Treble width is 8mm.
LEVEL_SPREAD = {
    "Beginner": 45.0,  # Wide spread: frequent misses into 1s and 5s, often single 20s
    "Semi Pro": 15.0,  # Medium spread: hits 20s consistently, sometimes trebles
    "Pro": 6.0,        # Tight spread: hits trebles frequently but not flawlessly
}

# ── Recurring nemesis: "The Machine" ──────────────────────────────────────────
# A named recurring AI rival whose difficulty ramps the more it has beaten the
# human. The win count persists to nemesis.json (read lazily, written on wins).
# Selectable as an opponent in setup (its name is the avatar key on the frontend).
NEMESIS_NAME = "The Machine"
NEMESIS_FILE = Path("nemesis.json")
_LEVEL_LADDER = ["Beginner", "Semi Pro", "Pro"]


def is_nemesis(name):
    return (name or "").strip().lower() == NEMESIS_NAME.lower()


def nemesis_state():
    """Return {"wins": N} read from nemesis.json (robust to missing/corrupt)."""
    try:
        data = json.loads(NEMESIS_FILE.read_text())
        return {"wins": int(data.get("wins", 0))}
    except (OSError, ValueError, json.JSONDecodeError):
        return {"wins": 0}


def nemesis_effective_level(base_level=None):
    """The nemesis's effective AI level, nudged up the ladder by its win count:
    every 2 wins over the human bumps it one rung (capped at 'Pro'). Falls back
    to the configured base level's rung if higher."""
    wins = nemesis_state()["wins"]
    base_idx = _LEVEL_LADDER.index(base_level) if base_level in _LEVEL_LADDER else 0
    idx = min(len(_LEVEL_LADDER) - 1, max(base_idx, wins // 2))
    return _LEVEL_LADDER[idx]


def nemesis_record_win():
    """Increment and persist the nemesis win counter. Returns the new total."""
    wins = nemesis_state()["wins"] + 1
    try:
        NEMESIS_FILE.write_text(json.dumps({"wins": wins}))
    except OSError as e:
        print(f"[AI] Could not persist nemesis win: {e}")
    return wins

def get_target_coord(label):
    """
    Given a throw label (e.g., 'T20', 'D16', '20', 'DBull'),
    return the ideal (x_mm, y_mm) target coordinate.
    """
    if label == "DBull":
        return 0.0, 0.0
    if label == "Bull":
        # Arbitrarily pick right side of outer bull, radius 11mm
        return 11.0, 0.0

    multiplier = 1
    if label.startswith("T"):
        multiplier = 3
        segment = int(label[1:])
    elif label.startswith("D"):
        multiplier = 2
        segment = int(label[1:])
    else:
        segment = int(label)

    # Find the angle for the segment
    try:
        idx = dartboard.SEGMENTS.index(segment)
    except ValueError:
        idx = 0
    angle_deg = 360 - (idx * 18)  # 0 is 20 (up), then clockwise 1 is 18 deg. But math angles: 0 is right, 90 is up.
    # Wait, dartboard.score_detail: angle = math.degrees(math.atan2(x_mm, y_mm))
    # y is up, x is right. 
    # If 20 is up, then x=0, y=r. atan2(0, r) = 0.
    # If 1 is 18 deg clockwise. math.atan2(sin, cos)? atan2(x, y).
    # So angle = atan2(x, y). x = r * sin(angle), y = r * cos(angle)
    angle_rad = math.radians(idx * 18)

    if multiplier == 3:
        r = (dartboard.TREBLE_IN + dartboard.TREBLE_OUT) / 2.0
    elif multiplier == 2:
        r = (dartboard.DOUBLE_IN + dartboard.DOUBLE_OUT) / 2.0
    else:
        # Standard single
        r = (dartboard.TREBLE_OUT + dartboard.DOUBLE_IN) / 2.0

    x = r * math.sin(angle_rad)
    y = r * math.cos(angle_rad)
    return x, y

CRICKET_PRIORITY = [20, 19, 18, 17, 16, 15, 25]  # highest value first, bull last


def _cricket_label(t, treble=True):
    """Best aiming label to put marks on cricket number `t`."""
    if t == 25:
        return "DBull"            # 2 marks per hit — fastest way to close the bull
    return ("T" if treble else "S") + str(t)


def decide_target_label(game):
    """Choose the throw LABEL (e.g. 'T20', 'DBull', '7') for the AI's current
    turn, picking a sensible strategy for whichever game mode is in play."""
    mode = getattr(game, "mode", "X01")
    p = game.player

    # ── Cricket: close your own numbers (high value first), then score on
    # numbers an opponent still has open. ────────────────────────────────────
    if mode == "Cricket":
        marks = p.state.get("marks", {})
        open_self = [t for t in CRICKET_PRIORITY if marks.get(str(t), 0) < 3]
        if open_self:
            return _cricket_label(open_self[0])
        # Everything closed — pile on points where an opponent is still open.
        scoreable = [t for t in CRICKET_PRIORITY
                     if any(q.state.get("marks", {}).get(str(t), 0) < 3
                            for q in game.players if q is not p)]
        if scoreable:
            return _cricket_label(scoreable[0])
        return "T20"

    # ── Around the Clock: aim the current target in the 1→20→Bull sequence. ──
    if mode == "Around the Clock":
        tgt = p.state.get("target", "1")
        if tgt in ("Bull", "Done"):
            return "Bull"
        return str(tgt)           # any single/double/treble of the number counts

    # ── Shanghai: only the round's number scores — go for the treble. ────────
    if mode == "Shanghai":
        return "T" + str(getattr(game, "target", 1))

    # ── Killer: arm on your own double, then hammer the strongest opponent. ──
    if mode == "Killer":
        own = p.state.get("number")
        if not p.state.get("killer"):
            # Arm: hit your own double (Hard) or rack up 3 marks (Standard).
            if getattr(game, "arm_mode", "marks") == "double":
                return "D" + str(own)
            return "T" + str(own)                 # treble = 3 marks → arm at once
        # Armed: target the alive opponent with the most lives; treble = 3 off.
        foes = [q for q in game.players
                if q is not p and not q.state.get("out") and q.state.get("lives", 0) > 0]
        if foes:
            target = max(foes, key=lambda q: q.state.get("lives", 0))
            return "T" + str(target.state.get("number"))
        return "D" + str(own)                     # nothing to hit (shouldn't happen)

    # ── Count Up / High Score: maximise points. ─────────────────────────────
    if mode == "Count Up":
        return "T20"

    # ── X01: use the checkout solver, else build the score. ─────────────────
    hint = suggest(p.score, game.darts_left, game.double_out)
    if hint:
        return hint[0]
    if p.score > 60:
        return "T20"
    if p.score > 40:
        return "20"
    return "10"                   # arbitrary setup dart


def decide_target(game):
    """
    Decide the best target for the current AI turn.
    Returns (x_mm, y_mm) of the ideal target.
    """
    return get_target_coord(decide_target_label(game))

def execute_ai_throw(game, level):
    """
    Execute a throw for the AI, adding gaussian noise based on level,
    and pushing the hit to the game.
    """
    tx, ty = decide_target(game)
    spread = LEVEL_SPREAD.get(level, 15.0)

    # Apply Gaussian noise
    x = random.gauss(tx, spread)
    y = random.gauss(ty, spread)

    hit = dartboard.score_detail(x, y)
    game.record_hit(hit, (x, y))

async def ai_loop():
    """
    Background loop that continually watches the game.
    If it's an AI's turn, it throws a dart.
    """
    print("[AI] Loop started")
    last_player_id = None   # detect when the active player changes (turn handover)
    stepped_up = False      # have we done the once-per-visit "step up to the oche" pause?
    while True:
        try:
            await asyncio.sleep(0.5)

            # Game paused → the AI holds its turn (no step-up, no throw).
            if detect.STATUS.get("paused"):
                continue

            with detect.GAME_LOCK:
                game = detect.GAME
                if not game or game.over:
                    continue

                # Reset the step-up pause whenever the active player changes
                # (human <-> AI handover, or AI <-> AI), so each fresh AI visit
                # gets exactly one step-up delay.
                pid = id(game.player)
                if pid != last_player_id:
                    last_player_id = pid
                    stepped_up = False

                # Re-check inside lock if it's AI's turn
                if not game.player.is_ai:
                    continue

                # Don't throw until the human's darts have been physically
                # removed from the board.  When a turn ends the engine advances
                # to the AI immediately, but detection is still in 'all_done'
                # waiting for the board to be cleared — throwing now is way too
                # quick.  Wait for the board to clear (awaiting_clear -> False).
                if detect.STATUS.get("awaiting_clear"):
                    continue

                # Ensure turn isn't over just in case
                if game.darts_left <= 0:
                    continue

                level = game.player.ai_level
                # The nemesis ramps its effective difficulty by its win record.
                if is_nemesis(game.player.name):
                    level = nemesis_effective_level(level)
                need_step_up = not stepped_up

            # Once per visit, after the board is clear, pause ~2s to mimic the
            # player walking up to the oche before their first dart.
            if need_step_up:
                await asyncio.sleep(2.0)
                stepped_up = True

            # Outside the lock, wait a realistic per-dart aiming time. Keep this
            # comfortably longer than the throw animation (~1.1s to SCORING) so
            # each dart's animation lands before the next is thrown.
            delay = random.uniform(1.4, 2.2)
            await asyncio.sleep(delay)

            with detect.GAME_LOCK:
                # Check state again after sleep in case game was reset,
                # or human undid a dart, or match ended.
                game = detect.GAME
                if not game or game.over:
                    continue
                if not game.player.is_ai:
                    continue
                if game.darts_left <= 0:
                    continue

                execute_ai_throw(game, level)
                detect.STATUS["game_gen"] += 1
        except Exception as e:
            import traceback
            print(f"[AI] Error in ai_loop: {e}")
            traceback.print_exc()
            await asyncio.sleep(2.0)
