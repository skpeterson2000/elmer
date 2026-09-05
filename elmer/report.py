"""Terminal progress report for `./elmer.py --stats`."""
from . import db, exams, ranks, srs
from .content import load_pools


def bar(value, width=22):
    filled = int(round(max(0.0, min(1.0, value)) * width))
    return "#" * filled + "." * (width - filled)


def print_roster(conn):
    """Everyone on the unit, when there is more than one of them."""
    people = db.users(conn)
    if len(people) < 2:
        return
    print("\n  On this unit\n")
    for person in people:
        answers = conn.execute(
            "SELECT COUNT(*) c FROM answer_log WHERE user_id = ?",
            (person["id"],)).fetchone()["c"]
        print(f"      {person['display_name']:12s} {person['xp']:6d} XP  "
              f"{answers:5d} answers  streak {person['streak_days']}d")
    print("\n  Show somebody else with  ./elmer.py --stats --user NAME\n")


def print_stats(who=None):
    conn = db.connect()
    if who:
        wanted = (who or "").strip().lower()
        match = next((u for u in db.users(conn)
                      if wanted in (u["display_name"].lower(), u["name"].lower())), None)
        if not match:
            print(f"\n  Nobody on this unit is called {who}. There is: "
                  + ", ".join(u["display_name"] for u in db.users(conn)) + "\n")
            conn.close()
            return
        conn.user_id = match["id"]
    prof = db.get_profile(conn)
    answered = conn.execute("SELECT COUNT(*) c FROM answer_log WHERE user_id = ?",
                            (conn.user_id,)).fetchone()["c"]
    standings = db.kv_get(conn, "standings", {}) or {}
    tracks = ranks.overall(list(standings.values())) if standings else {}

    print(f"\n  ELMER  {prof['display_name']}"
          + ("" if prof["licensed"] else "   (no callsign on file)"))
    for name, track in tracks.items():
        lapse = "  (lapsed)" if track["lapsed"] else ""
        print(f"  {track['label']:11s} {track['title']}{lapse}")
    print(f"  {prof['xp']} XP | streak {prof['streak_days']}d "
          f"(best {prof['best_streak']}) | {answered} answers logged\n")

    header = (f"  {'pool':11s} {'mastery':24s} {'seen':>10s} {'due':>5s}"
              f" {'odds':>6s}  {'standing':<22s}")
    print(header)
    print("  " + "-" * (len(header) - 2))
    for pool_id, pool in load_pools().items():
        cards = db.cards_for_pool(conn, pool_id)
        per_q, per_sec, _, mastery = srs.pool_skills(pool, cards)
        ready = srs.readiness(pool, per_q, per_sec, trials=2000, seed=7)
        seen = sum(1 for c in cards.values() if c["seen"])
        due = sum(1 for q in pool.questions
                  if (c := cards.get(q["id"])) and c["seen"] and c["due"]
                  and c["due"] <= db.utcnow().isoformat())
        standing = standings.get(pool_id, {})
        title = standing.get("step_name", "-")
        if standing.get("lapsed"):
            title += " (lapsed)"
        print(f"  {pool.name[:10]:11s} {bar(mastery)} {mastery*100:3.0f}%"
              f" {seen:5d}/{len(pool.questions):<4d} {due:5d}"
              f" {ready['pass_probability']*100:5.0f}%  {title:<22s}")

    recent = exams.history(conn, limit=5)
    if recent:
        print("\n  recent mock exams")
        for e in recent:
            mark = "PASS" if e["passed"] else "fail"
            print(f"    {e['finished'][:16].replace('T', ' ')}  {e['pool_id']:10s}"
                  f" {e['score']:3d}/{e['total']:<3d}  {mark}")
    print_roster(conn)
    print()
    conn.close()
