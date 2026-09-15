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
import pathlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
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

print("\nthe press marks the reset and restarts; the clean is done on the way back up")
import subprocess, tempfile  # noqa: E402
scratch = pathlib.Path(tempfile.mkdtemp(prefix="elmer-reset-"))
subprocess.run(["git", "init", "-q", "."], cwd=str(scratch), check=True)
(scratch / ".gitignore").write_text("data/x.db\ndata/x.log\n", encoding="utf-8")
(scratch / "data").mkdir()
(scratch / "data" / "pools.txt").write_text("ships with a clone\n", encoding="utf-8")
subprocess.run(["git", "add", "."], cwd=str(scratch), check=True)
subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=str(scratch), check=True)
(scratch / "data" / "x.db").write_text("study\n", encoding="utf-8")
(scratch / "data" / "x.log").write_text("lines\n", encoding="utf-8")
was = (devreset.ROOT, devreset.DATA, devreset.PENDING)
devreset.ROOT, devreset.DATA = scratch, scratch / "data"
devreset.PENDING = devreset.DATA / "reset-pending"
try:
    check("nothing pending on a unit nobody asked to reset", devreset.perform_if_pending(), None)
    asked = devreset.request()
    check("the press marks it", (asked.get("ok"), asked.get("restarting"), devreset.pending()), (True, True, True))
    check("  and takes nothing yet", (scratch / "data" / "x.db").exists(), True)
    done = devreset.perform_if_pending()
    check("the next start does the clean", done.get("ok"), True)
    check("  the study and the log are gone, the mark with them",
          ((scratch / "data" / "x.db").exists(), (scratch / "data" / "x.log").exists(), devreset.pending()),
          (False, False, False))
    check("  what a clone ships with stays", (scratch / "data" / "pools.txt").exists(), True)
    check("  and the start after that has nothing to do", devreset.perform_if_pending(), None)
finally:
    devreset.ROOT, devreset.DATA, devreset.PENDING = was
    shutil.rmtree(scratch, ignore_errors=True)

print("\nfrom the panel, the right count marks and restarts rather than deleting in place")
import elmer.app as appmod  # noqa: E402
restarts = []
real_restart, real_request = appmod.request_restart, devreset.request
appmod.request_restart = lambda: restarts.append(True)
devreset.request = lambda: {"ok": True, "restarting": True}    # the mark, without writing into this checkout's data/
try:
    with app.test_client() as client:
        real = client.get("/api/dev/reset").get_json().get("count")
        reply = client.post("/api/dev/reset", json={"count": real})
        check("accepted", (reply.status_code, reply.get_json().get("restarting")), (200, True))
        check("  and ELMER restarts to do it", restarts, [True])
        check("  with this checkout's study still here", devreset.DATA.joinpath("elmer.db").exists()
              or not any(devreset.DATA.iterdir()), True)
finally:
    appmod.request_restart, devreset.request = real_restart, real_request

print("\nit says how to remove itself, because it is meant to be removed")
check("the module says so", "delete this" in (devreset.__doc__ or "").lower(),
      True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
