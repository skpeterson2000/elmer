"""Terminal progress report for `./elmer.py --stats`."""
from . import db, exams, srs
from .content import load_pools
from .game import rank_for


def bar(value, width=22):
    filled = int(round(max(0.0, min(1.0, value)) * width))
    return "#" * filled + "." * (width - filled)


def print_stats():
    conn = db.connect()
    prof = db.get_profile(conn)
    rank = rank_for(prof["xp"])
    answered = conn.execute("SELECT COUNT(*) c FROM answer_log").fetchone()["c"]

    print(f"\n  ELMER  {prof['callsign'] or 'unlicensed'}")
    print(f"  {rank['name']} - {prof['xp']} XP"
          + (f", {rank['to_next']} to {rank['next_name']}" if rank["next_name"] else "")
          + f" | streak {prof['streak_days']}d (best {prof['best_streak']})"
          + f" | {answered} answers logged\n")

    header = f"  {'pool':11s} {'mastery':24s} {'seen':>10s} {'due':>5s} {'pass odds':>10s}"
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
        print(f"  {pool.name[:10]:11s} {bar(mastery)} {mastery*100:3.0f}%"
              f" {seen:5d}/{len(pool.questions):<4d} {due:5d}"
              f" {ready['pass_probability']*100:9.0f}%")

    recent = exams.history(conn, limit=5)
    if recent:
        print("\n  recent mock exams")
        for e in recent:
            mark = "PASS" if e["passed"] else "fail"
            print(f"    {e['finished'][:16].replace('T', ' ')}  {e['pool_id']:10s}"
                  f" {e['score']:3d}/{e['total']:<3d}  {mark}")
    print()
    conn.close()
