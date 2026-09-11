#!/usr/bin/env python3
"""The developer's reset, and the guards on it.

    python3 tests/test_devreset.py

This test never calls reset(). It cannot: the machine it runs on is somebody's
machine, and a test suite that wipes the study data of whoever ran it would be
a far worse bug than anything it could catch. So what is exercised is the dry
run and the refusals, which is where the behaviour worth protecting lives.

Two guards matter. It answers nothing to a request from off this machine,
because a study session anybody on the network can erase is not a study
session. And it will not act on a stale count: a page left open while somebody
fetched a day's worth of parks would otherwise take them on a press that was
meant for an empty unit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import devreset  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


app.config["TESTING"] = True

print("\nit can tell what it would take, without taking any of it")
before = sorted(p.name for p in devreset.DATA.iterdir()) if devreset.DATA.exists() else []
preview = devreset.would_remove()
check("it knows how", preview.get("ok"), True)
check("and lists them", isinstance(preview.get("items"), list), True)
check("the count matches the list", preview.get("count"),
      len(preview.get("items") or []))
after = sorted(p.name for p in devreset.DATA.iterdir()) if devreset.DATA.exists() else []
# The whole point of a dry run.
check("and nothing moved", after, before)

print("\nit only takes what a clone would not have")
items = preview.get("items") or []
# The pools, figures and rules ship with a checkout. Taking those would mean
# the reset leaves a unit that cannot ask a question, which is not "fresh".
for kept in ("data/pools", "data/figures", "data/rules", "data/places.json"):
    check(f"{kept} is not on the list",
          any(i.rstrip('/') == kept for i in items), False)

print("\nthe preview is local only")
with app.test_client() as client:
    here = client.get("/api/dev/reset")
    check("from this machine, it answers", here.status_code, 200)
    away = client.get("/api/dev/reset",
                      environ_overrides={"REMOTE_ADDR": "192.168.1.77"})
    check("from the network, it does not", away.status_code, 403)

print("\nand it will not act on a count that has gone stale")
with app.test_client() as client:
    real = client.get("/api/dev/reset").get_json().get("count")
    reply = client.post("/api/dev/reset", json={"count": (real or 0) + 500})
    check("refused", reply.status_code, 409)
    body = reply.get_json()
    check("said why", body.get("stale"), True)
    # Not compared against the earlier read: opening the app writes a log line,
    # so the count can legitimately move between the two calls. What matters is
    # that it answers with what is there rather than with the number it was
    # handed.
    check("and handed back a real count, not the one it was sent",
          isinstance(body.get("count"), int)
          and body["count"] != (real or 0) + 500, True)

print("\nasking to reset from the network is refused too")
with app.test_client() as client:
    away = client.post("/api/dev/reset", json={"count": 0},
                       environ_overrides={"REMOTE_ADDR": "10.0.0.9"})
    check("403, not a reset", away.status_code, 403)

print("\nit says how to remove itself, because it is meant to be removed")
check("the module says so", "delete this" in (devreset.__doc__ or "").lower(),
      True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
