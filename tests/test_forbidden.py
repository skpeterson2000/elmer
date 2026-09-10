#!/usr/bin/env python3
"""What happens when somebody walks into a pool that is not open yet.

    python3 tests/test_forbidden.py

The gate is a kindness to a beginner - 2,475 questions across six pools is a
wall, not a library - but the refusal used to be the framework's own 403: the
word Forbidden, no explanation, and nothing to press. On a kiosk that is a dead
end, because a full-screen browser has no back button and nobody is standing
there to type a URL.

So the way out is on the wall: the reason, the button that takes the wall down,
Escape bound to leave, and a clock that leaves without being asked. What is
checked here is that the refusal is still a refusal - 403, not 200 - and that
the API keeps its JSON, because something fetching /api and handed a page back
reports a parse error instead of the refusal it was given.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import gating  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


app.config["TESTING"] = True

print("\nthe sentence names no place that does not exist")
# The state a newcomer has: nothing reached, so nothing above Technician.
why = gating.why_closed("gen2023", {"reason": "start", "rung": 0})
check("there is a reason", bool(why), True)
check("and it does not send anybody to a Settings page",
      "Settings" in (why or ""), False)

with app.test_client() as client:
    print("\na closed pool is refused, and the refusal is a page")
    page = client.get("/study/gen2023")
    body = page.get_data(as_text=True)
    check("still a refusal", page.status_code, 403)
    check("with the reason on it", "opens when you hold a license" in body, True)
    check("the way back", 'id="fb-back"' in body, True)
    check("the button that takes the wall down",
          "data-open-pools" in body, True)
    check("Escape is bound", "'Escape'" in body, True)
    check("and it leaves on its own", 'id="fb-count"' in body, True)

    print("\nan open pool is not refused")
    check("technician is open to a newcomer",
          client.get("/study/tech2026").status_code, 200)

    print("\nthe API is answered in the language it asked in")
    # Handing JSON back as HTML turns a working refusal into a parse error.
    reply = client.get("/api/next?pool=gen2023")
    check("still a refusal", reply.status_code, 403)
    check("and still JSON", reply.is_json, True)
    check("carrying the same reason",
          "opens when you hold a license" in (reply.get_json() or {}).get("error", ""),
          True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
