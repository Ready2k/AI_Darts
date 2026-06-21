import asyncio
import math
import random
import time

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

def decide_target(game):
    """
    Decide the best target for the current AI turn.
    Returns (x_mm, y_mm) of the ideal target.
    """
    # Try to get a checkout hint
    hint = suggest(game.player.score, game.darts_left, game.double_out)
    if hint:
        # Aim at the first dart of the checkout hint
        return get_target_coord(hint[0])

    # If no checkout, usually aim T20
    # Unless score makes it bad to hit T20 (e.g. leaving a bogey)
    # For MVP, just aim T20 if score > 60, otherwise aim single 20 or bull
    if game.player.score > 60:
        return get_target_coord("T20")
    elif game.player.score > 40:
        return get_target_coord("20")
    else:
        # Prevent bust setups if not on a finish
        return get_target_coord("10") # arbitrary setup

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
                need_step_up = not stepped_up

            # Once per visit, after the board is clear, pause ~2s to mimic the
            # player walking up to the oche before their first dart.
            if need_step_up:
                await asyncio.sleep(2.0)
                stepped_up = True

            # Outside the lock, wait a realistic per-dart aiming time
            delay = random.uniform(0.8, 1.8)
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
