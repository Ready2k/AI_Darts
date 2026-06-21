"""Persist completed matches to match_history.json."""

import json
import time
from pathlib import Path

HISTORY_FILE = Path("match_history.json")


def load_history(limit=None):
    """Return saved matches (oldest first). `limit` keeps only the most recent N."""
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return data[-limit:] if limit else data


def save_match(game):
    """Append a finished match record. Returns the record."""
    record = {
        "ts": time.strftime("%Y-%m-%d %H:%M"),
        "mode": getattr(game, "mode", "X01"),
        "start_score": game.start_score,
        "double_in": game.double_in,
        "double_out": game.double_out,
        "winner": game.winner.name if game.winner else None,
        "players": [
            {
                "name": p.name,
                "sets": p.sets,
                "legs": p.legs,
                "avg": round(p.three_dart_avg, 1),
                "darts": p.total_darts,
            }
            for p in game.players
        ],
    }
    data = load_history()
    data.append(record)
    try:
        HISTORY_FILE.write_text(json.dumps(data, indent=2))
    except OSError as e:
        print(f"Could not write match history: {e}")
    return record
