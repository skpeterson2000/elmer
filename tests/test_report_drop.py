#!/usr/bin/env python3
"""The report drop's rate limit holds, run as the script itself.

    python3 tests/test_report_drop.py

tools/report_drop.gs runs on Google's side, where no test can reach. Its
limit is plain JavaScript over four of Google's services, so it is run here
in a real browser with small stand-ins for them - the cache, the lock, the
script properties and the date formatter - and held:

  - one unit mark may send PER_UNIT_HOUR reports in a clock hour, and the
    next is refused with a sentence saying so and when it resets;
  - every unit together may send ALL_HOUR in an hour, whatever marks they
    claim, since a sender can change its mark each time;
  - ALL_DAY in a day, counted in a script property because the cache keeps
    nothing past six hours, and a new day starts the count again;
  - a lock that cannot be had lets the report through rather than losing it;
  - GET says which limits the deployed version holds.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402

FAILS = []
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# Google's services, as much of them as the limit and doGet use.
STANDINS = r"""
let NOW = new Date(Date.UTC(2026, 8, 28, 14, 5, 0));
// The script asks "new Date()" for now; here now is whatever NOW says.
const RealDate = Date;
window.Date = class extends RealDate {
  constructor(...a) { if (a.length) super(...a); else super(NOW.getTime()); }
};
let LOCKED = false;
const store = {}, props = {};
const CacheService = {getScriptCache: () => ({
  getAll: keys => { const o = {}; keys.forEach(k => { if (k in store) o[k] = store[k]; }); return o; },
  put: (k, v) => { store[k] = v; },
})};
const LockService = {getScriptLock: () => ({tryLock: () => !LOCKED, releaseLock: () => {}})};
const PropertiesService = {getScriptProperties: () => ({
  getProperty: k => (k in props ? props[k] : null),
  setProperty: (k, v) => { props[k] = v; },
})};
const Utilities = {formatDate: (d, tz, fmt) => {
  const p = n => String(n).padStart(2, '0');
  const day = d.getUTCFullYear() + p(d.getUTCMonth() + 1) + p(d.getUTCDate());
  return fmt === 'yyyyMMdd' ? day : day + p(d.getUTCHours());
}};
const Session = {getEffectiveUser: () => ({getEmail: () => 'owner@example.org'})};
const ContentService = {createTextOutput: s => ({s, setMimeType() { return this; }}),
                        MimeType: {JSON: 'json'}};
"""

DRIVE = r"""
(() => {
  const out = {};
  const send = unit => overLimit(unit);
  const run = (n, unit) => { let last = null; for (let i = 0; i < n; i++) last = send(unit(i)); return last; };

  out.unitAllowed = run(PER_UNIT_HOUR, () => 'ab12');
  out.unitRefused = send('ab12');
  out.otherUnit = send('cd34');

  NOW = new Date(NOW.getTime() + 3600e3);             // the next hour
  out.nextHour = send('ab12');

  NOW = new Date(NOW.getTime() + 3600e3);
  out.hourAllowed = run(ALL_HOUR, i => 'u' + i);      // a new mark each time
  out.hourRefused = send('fresh');

  // The day: hours pass until the day's count is spent.
  for (let h = 0; h < 12 && !out.dayRefused; h++) {
    NOW = new Date(NOW.getTime() + 3600e3);
    for (let i = 0; i < ALL_HOUR; i++) {
      const said = send('d' + h + '-' + i);
      if (said && said.indexOf('today') >= 0) { out.dayRefused = said; break; }
    }
  }
  out.dayCount = PropertiesService.getScriptProperties().getProperty('DROP_DAY_COUNT');
  NOW = new Date(Date.UTC(2026, 8, 29, 1, 0, 0));      // tomorrow
  out.tomorrow = send('ab12');

  LOCKED = true;
  out.locked = send('ab12');
  LOCKED = false;

  out.get = JSON.parse(doGet().s).limits;
  out.numbers = [PER_UNIT_HOUR, ALL_HOUR, ALL_DAY];
  return JSON.stringify(out);
})()
"""


def main():
    if not _browser.available():
        check("chromium is on this machine", False, True)
        print("\nFAILED: this test needs chromium")
        return 1
    script = (ROOT / "tools" / "report_drop.gs").read_text(encoding="utf-8")
    scratch = Path(tempfile.mkdtemp(prefix="elmer-drop-"))
    try:
        (scratch / "drop.html").write_text(
            "<!doctype html><script>\n" + STANDINS + "\n" + script + "\n</script>", encoding="utf-8")
        with _browser.serve(scratch) as base:
            got = _browser.evaluate(base + "/drop.html", DRIVE, settle=0.2)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    try:
        out = json.loads(got)
    except (TypeError, ValueError):
        check("the script ran", got, "a JSON report")
        return 1

    per_unit, all_hour, all_day = out["numbers"]
    print("\n-- one unit in one hour --")
    check(f"{per_unit} reports from one unit are taken", out["unitAllowed"], None)
    check("  the next is refused, saying why and when",
          ("this unit has sent" in (out["unitRefused"] or ""), "after the hour" in (out["unitRefused"] or "")),
          (True, True))
    check("  another unit is not held by it", out["otherUnit"], None)
    check("  and the next hour starts again", out["nextHour"], None)

    print("\n-- every unit together --")
    check(f"{all_hour} in an hour from marks that change every time are taken", out["hourAllowed"], None)
    check("  the next is refused, whatever mark it claims",
          "every unit together" in (out["hourRefused"] or ""), True)

    print("\n-- the day --")
    check(f"the day's count stops at {all_day}",
          ("today" in (out["dayRefused"] or ""), (out["dayCount"] or "").endswith(f":{all_day}")),
          (True, True))
    check("  kept as a script property, by date", (out["dayCount"] or "").startswith("20260928:"), True)
    check("  and tomorrow starts again", out["tomorrow"], None)

    print("\n-- failing the right way --")
    check("a lock that cannot be had lets the report through", out["locked"], None)
    check("GET says which limits this version holds",
          out["get"], {"per_unit_hour": per_unit, "all_hour": all_hour, "all_day": all_day})
    check("  and they are the numbers the script's own note gives", out["numbers"], [6, 30, 80])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
