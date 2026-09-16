"""The pace of every endpoint, kept, so a creeper is caught by the unit
and not by somebody looking over their shoulder.

A page that took 40 ms in June and takes 400 ms in September has not
failed at anything; it has crept, and creeping is invisible from the
front of a kiosk until the day it is not. This keeps, per endpoint, how
many times it was asked, its mean, its slowest, and its last forty
timings for a ninety-fifth percentile; writes the ledger to the state
directory every few minutes so a restart does not lose the week; says
in the log, once an hour at most, which endpoints are over budget; and
hands the field report a table of the slow ones and the creepers, so the
report that goes home once a week carries the pace as well as the errors.

Two ways to be a creeper. Absolute: a ninety-fifth percentile over the
budget for its kind - a poll, a page, an API call - measured on this unit,
which is the machine that matters. Relative: a mean that has doubled since
the ledger's first hundred calls of it, which is what creeping looks like
before it crosses any budget at all.
"""
import json
import logging
import re
import threading
import time
from collections import deque

from . import paths

log = logging.getLogger("elmer")

LEDGER = paths.STATE / "pace.json"
KEEP = 40                          # timings kept per endpoint, for the p95
SAVE_EVERY = 600                   # seconds between writes of the ledger
SAY_EVERY = 3600                   # seconds between log lines about creepers
BASELINE_CALLS = 100               # the first this many set an endpoint's baseline
CREEP_FACTOR = 2.0                 # a mean this much over its baseline has crept
# Budgets for the ninety-fifth percentile, in milliseconds, on a Pi.
BUDGET = {"poll": 150, "api": 400, "page": 900, "static": 150, "pdf": 4000}
POLLS = ("/api/party/state", "/api/people", "/api/peers", "/health", "/api/party/net",
         "/api/net/checkin", "/api/discovery", "/api/gps", "/api/update", "/api/scoreboard")

_lock = threading.Lock()
_ledger = {}                        # key -> {"n", "total", "max", "last": deque, "base": mean or None, "base_n"}
_saved_at = 0.0
_said_at = 0.0
_loaded = False

RE_NUM = re.compile(r"/\d+(?=/|$)")
RE_FILE = re.compile(r"/[^/]+\.(png|jpg|jpeg|svg|pdf|mp3|js|css|json)$")


def key_of(method, path):
    """One key per endpoint, not per argument: numbers and file names in
    the path are folded, so /library/page/x/3.png and /library/page/y/7.png
    are the same thing timed."""
    p = path.split("?", 1)[0]
    p = RE_FILE.sub(lambda m: "/*." + m.group(1), p)
    p = RE_NUM.sub("/*", p)
    return f"{method} {p}"


def kind_of(path):
    p = path.split("?", 1)[0]
    if p.startswith("/static/"):
        return "static"
    if p.endswith(".pdf") or "/pdf" in p or p.startswith("/prints/"):
        return "pdf"
    if any(p.startswith(x) for x in POLLS):
        return "poll"
    if p.startswith("/api/"):
        return "api"
    return "page"


def note(method, path, ms):
    """One request, timed."""
    _load()
    k = key_of(method, path)
    with _lock:
        row = _ledger.get(k)
        if row is None:
            # The first call of an endpoint carries its imports and cold
            # caches - the pool loading, the first template compile - and
            # is not its pace. Noted, not timed.
            _ledger[k] = {"n": 0, "total": 0.0, "max": 0.0, "last": deque(maxlen=KEEP),
                          "base": None, "base_n": 0, "kind": kind_of(path)}
            return
        row["n"] += 1
        row["total"] += ms
        row["max"] = max(row["max"], ms)
        row["last"].append(ms)
        if row["base"] is None and row["n"] >= BASELINE_CALLS:
            row["base"] = row["total"] / row["n"]
            row["base_n"] = row["n"]


def _p95(samples):
    if not samples:
        return 0.0
    s = sorted(samples)
    return s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]


def rows(least_calls=5):
    """The ledger as rows, slowest p95 first."""
    _load()
    out = []
    with _lock:
        for k, row in _ledger.items():
            if row["n"] < least_calls:
                continue
            mean = row["total"] / row["n"]
            p95 = _p95(row["last"])
            kind = row["kind"]
            crept = bool(row["base"]) and mean >= CREEP_FACTOR * row["base"] and row["n"] >= row["base_n"] + 50
            out.append({"key": k, "kind": kind, "n": row["n"], "mean": round(mean), "p95": round(p95),
                        "max": round(row["max"]), "budget": BUDGET.get(kind, 400),
                        "over": p95 > BUDGET.get(kind, 400),
                        "base": round(row["base"]) if row["base"] else None, "crept": crept})
    out.sort(key=lambda r: -r["p95"])
    return out


def creepers():
    """The endpoints over budget or crept, worst first."""
    return [r for r in rows() if r["over"] or r["crept"]]


def report_lines(limit=8):
    """For the field report and the doctor: the slow ones and the creepers."""
    all_rows = rows()
    lines = []
    bad = [r for r in all_rows if r["over"] or r["crept"]]
    if not all_rows:
        return ["  no requests timed yet"]
    for r in all_rows[:limit]:
        flag = " CREPT x%.1f from %d ms" % ((r["mean"] / r["base"]) if r["base"] else 0, r["base"] or 0) if r["crept"] else (" over budget" if r["over"] else "")
        lines.append(f"  {r['key'][:44]:<44} {r['n']:>6} calls  mean {r['mean']:>5} ms  p95 {r['p95']:>5} ms  max {r['max']:>6} ms{flag}")
    if bad and any(b not in all_rows[:limit] for b in bad):
        lines.append("  and, further down:")
        for r in bad:
            if r in all_rows[:limit]:
                continue
            lines.append(f"  {r['key'][:44]:<44} {r['n']:>6} calls  mean {r['mean']:>5} ms  p95 {r['p95']:>5} ms"
                         + (" CREPT" if r["crept"] else " over budget"))
    if not bad:
        lines.append("  nothing over budget, nothing crept")
    return lines


def _load():
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    with _lock:
        for k, row in (data.get("endpoints") or {}).items():
            _ledger[k] = {"n": int(row.get("n", 0)), "total": float(row.get("total", 0.0)),
                          "max": float(row.get("max", 0.0)), "last": deque(row.get("last") or [], maxlen=KEEP),
                          "base": row.get("base"), "base_n": int(row.get("base_n", 0)),
                          "kind": row.get("kind") or kind_of(k.split(" ", 1)[-1])}


def save():
    """The ledger to disk - small, and not often."""
    global _saved_at
    with _lock:
        data = {"note": "How long each endpoint takes on this unit: calls, total and slowest "
                        "in ms, the last forty timings, and the mean of the first hundred "
                        "as a baseline. Read by the field report and the doctor.",
                "written": time.time(),
                "endpoints": {k: {"n": r["n"], "total": round(r["total"], 1), "max": round(r["max"], 1),
                                  "last": [round(x, 1) for x in r["last"]], "base": r["base"], "base_n": r["base_n"],
                                  "kind": r["kind"]} for k, r in _ledger.items()}}
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        tmp = LEDGER.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(LEDGER)
        _saved_at = time.time()
    except OSError as exc:
        log.debug("pace: could not write the ledger: %s", exc)


def reset():
    """A new ledger - after a change that was meant to fix a creeper."""
    with _lock:
        _ledger.clear()
    save()


def tick():
    """Called from the request path now and then: save when due, and say
    once an hour which endpoints are over budget or have crept."""
    global _said_at
    now = time.time()
    if now - _saved_at > SAVE_EVERY:
        save()
    if now - _said_at > SAY_EVERY:
        _said_at = now
        bad = creepers()
        if bad:
            log.warning("pace: %d endpoint(s) over budget or crept - %s",
                        len(bad), "; ".join(f"{r['key']} p95 {r['p95']} ms" + (" (crept from %d)" % r["base"] if r["crept"] else "")
                                            for r in bad[:4]))
