import history

def get_leaderboard():
    """
    Computes leaderboard statistics from the match history.
    """
    matches = history.load_history()
    stats = {}

    for m in matches:
        ts = m.get("ts")
        winner = m.get("winner")
        players = m.get("players", [])
        
        for p in players:
            name = p.get("name")
            if not name:
                continue
                
            if name not in stats:
                stats[name] = {
                    "name": name,
                    "played": 0,
                    "won": 0,
                    "lost": 0,
                    "total_darts": 0,
                    "total_points_implied": 0.0,
                    "highest_checkout": None,  # Not tracked currently
                    "best_leg": None,          # Not tracked currently
                    "last_played": ts
                }
            
            st = stats[name]
            st["played"] += 1
            if name == winner:
                st["won"] += 1
            else:
                st["lost"] += 1
                
            # Update last played date if this match is newer (assuming chronological order in history)
            st["last_played"] = ts
            
            # For overall 3-dart average, we reconstruct total points = avg / 3 * darts
            avg = p.get("avg", 0.0)
            darts = p.get("darts", 0)
            st["total_darts"] += darts
            st["total_points_implied"] += (avg / 3.0) * darts

    # Finalize stats
    leaderboard = []
    for name, st in stats.items():
        win_rate = (st["won"] / st["played"] * 100.0) if st["played"] > 0 else 0.0
        overall_avg = (st["total_points_implied"] / st["total_darts"] * 3.0) if st["total_darts"] > 0 else 0.0
        
        leaderboard.append({
            "name": name,
            "played": st["played"],
            "won": st["won"],
            "lost": st["lost"],
            "win_rate": round(win_rate, 1),
            "avg": round(overall_avg, 1),
            "highest_checkout": st["highest_checkout"],
            "best_leg": st["best_leg"],
            "last_played": st["last_played"],
        })

    # Sort: 1. Matches won, 2. Win rate, 3. 3-dart average, 4. Matches played
    leaderboard.sort(key=lambda x: (x["won"], x["win_rate"], x["avg"], x["played"]), reverse=True)
    
    # Add rank
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1
        
    return leaderboard
