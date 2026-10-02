#!/usr/bin/env python3
"""The spot layer on the Band Plan's reach map, in the browser.

    python3 tests/test_spots_page.py

The layer is driven directly - a placement, a band and a set of spots
handed to it - so it needs no QTH and no sky: what is held is the layer's
own behaviour. Only this band's spots are drawn; each toggle takes its own
kind away; the hover card names the station; and a callsign arriving over
UDP from anything on the network cannot write markup into the page.

And the way in from the POTA page: its "On the air now" panel counts the
parks by band and links each band with a map to it with the parks shown
("/bandplan#20m,spots") - HF with the forecast under them, 6 m and 2 m with
the spots alone, and the forecast's own controls put away there.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


JS = r"""
(() => {
  const now = Date.now() / 1000, iso = new Date(Date.now() - 5 * 60000).toISOString().slice(0, 19) + 'Z';
  bpReachFor = {};
  bpPlace = (lon, lat) => [720 + lon * 4, 360 - lat * 4];
  bpSpotBand = '20 m';
  bpSpots = {
    pota: {as_of: '2026-10-02T14:05:00+00:00', stale: false, spots: [
      {call: 'K1ABC', ref: 'US-1234', name: 'Acadia', lat: 44, lon: -68, mhz: 14.062, band: '20 m', mode: 'CW', spotted: iso},
      {call: 'W9XYZ', ref: 'US-5678', name: 'Elsewhere', lat: 40, lon: -90, mhz: 7.2, band: '40 m', mode: 'SSB',
       spotted: iso}]},
    heard: {enabled: true, listening: true, where: '127.0.0.1:2237', last_packet: '2026-10-02T14:05:00+00:00', quiet_s: 5,
      minutes: 30, dial: [{mhz: 14.074, mode: 'FT8'}], config: {}, spots: [
      {call: '<img src=x onerror=alert(1)>', grid: 'FN42', lat: 42, lon: -71, snr: -10, mhz: 14.075,
       band: '20 m', mode: 'FT8', at: now - 60},
      {call: 'JA1XYZ', grid: 'PM95', lat: 35, lon: 139, snr: -18, mhz: 14.075, band: '20 m', mode: 'FT8', at: now - 300},
      {call: 'DL1ZZ', grid: 'JO62', lat: 52, lon: 13, snr: -20, mhz: 7.074, band: '40 m', mode: 'FT8', at: now - 60}]}};
  const out = {};
  const kinds = () => bpSpotHits.map(h => h.kind + ':' + h.s.call.slice(0, 6)).sort().join(' ');
  document.getElementById('bp-spots-pota').checked = true;
  document.getElementById('bp-spots-heard').checked = true;
  bpSpotsDraw(); out.both = kinds();
  bpSpotsLine(); out.line = document.getElementById('bp-spots-line').textContent;
  document.getElementById('bp-spots-heard').checked = false;
  bpSpotsDraw(); out.parks_only = kinds();
  document.getElementById('bp-spots-heard').checked = true;
  document.getElementById('bp-spots-pota').checked = false;
  bpSpotsDraw(); out.heard_only = kinds();
  document.getElementById('bp-spots-pota').checked = true;
  bpSpotsDraw();
  const card = h => { const d = document.createElement('div'); d.innerHTML = bpSpotTipHTML(h); return d; };
  const park = card(bpSpotHits.find(h => h.kind === 'pota'));
  out.park_card = park.textContent;
  const bad = card(bpSpotHits.find(h => h.s.grid === 'FN42'));
  out.injected = bad.querySelector('img') !== null;
  out.bad_text = bad.textContent.slice(0, 30);
  // 6 m and 2 m: the forecast's controls put away, the reason said, and back again for HF
  const shown = id => { const el = document.getElementById(id); return el && getComputedStyle(el).display !== 'none'; };
  const title = () => document.querySelector('#bp-reach .panel-title').textContent.replace(/\s+/g, ' ').trim();
  bpReachForecastShown(false);
  out.spotsOnly = {antenna: shown('bp-reach-ant'), watts: shown('bp-reach-w'), view: shown('bp-reach-proj'),
                   spots: shown('bp-spots-pota'), reset: shown('bp-reach-reset'),
                   words: !document.getElementById('bp-reach-spotsonly').hidden, title: title()};
  bpReachForecastShown(true);
  out.forecast = {antenna: shown('bp-reach-ant'), words: !document.getElementById('bp-reach-spotsonly').hidden,
                  title: title()};
  bpSpotBand = '40 m'; bpSpotsDraw(); out.forty = kinds();
  bpSpots.heard.error = 'port 2237 is already taken'; bpSpotBand = '20 m'; bpSpotsLine();
  out.busy_line = document.getElementById('bp-spots-line').textContent;
  return JSON.stringify(out);
})()
"""


ACTIVATIONS_JS = r"""
(async () => {
  const out = {};
  const words = () => document.getElementById('ac-live-words').textContent;
  const links = () => [...document.querySelectorAll('#ac-live-bands a')].map(a => a.getAttribute('href'));
  const spans = () => [...document.querySelectorAll('#ac-live-bands span.btn')].map(e => e.textContent.trim());
  api = async () => ({pota: {as_of: null, stale: false, spots: []}});
  await acLive(); out.unsampled = words();
  const spot = (band, mhz) => ({call: 'K1ABC', band: band, mhz: mhz});
  api = async () => ({pota: {as_of: '2026-10-02T14:05:00+00:00', stale: false, spots: [
    spot('20 m', 14.062), spot('20 m', 14.285), spot('20 m', 14.074), spot('40 m', 7.2), spot('6 m', 50.313),
    spot('<b>x</b>', 14.1), spot('70 cm', 446.0)]}});
  await acLive();
  out.words = words(); out.links = links(); out.spans = spans();
  out.when = document.getElementById('ac-live-when').textContent;
  out.injected = document.querySelector('#ac-live-bands b') !== null;
  return JSON.stringify(out);
})()
"""

BANDPLAN_HASH_JS = r"""
(async () => {
  for (let i = 0; i < 40 && !bpData; i++) await new Promise(r => setTimeout(r, 250));
  return JSON.stringify({band: bpBand, wants: bpWantSpots || !!bpSpotTimer});
})()
"""


def main():
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        print("\nFAILED: this test needs chromium")
        return 1
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
         "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port, timeout=1).close()
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise SystemExit("the throwaway server never answered")
        got = json.loads(_browser.evaluate("http://127.0.0.1:%d/bandplan" % port, JS, settle=2.0))
        live = json.loads(_browser.evaluate("http://127.0.0.1:%d/activations" % port, ACTIVATIONS_JS, settle=2.0))
        hashed = json.loads(_browser.evaluate("http://127.0.0.1:%d/bandplan#20m,spots" % port, BANDPLAN_HASH_JS,
                                              settle=1.0))
    finally:
        server.terminate()

    print("\n-- only the band on the map, each kind its own toggle --")
    check("on 20 m: the park and the two stations heard on 20 m",
          got["both"], "heard:<img s heard:JA1XYZ pota:K1ABC")
    check("  parks alone", got["parks_only"], "pota:K1ABC")
    check("  heard alone", got["heard_only"], "heard:<img s heard:JA1XYZ")
    check("on 40 m, the 40 m ones", got["forty"], "heard:DL1ZZ pota:W9XYZ")
    check("the line counts them, and says the rest are on other bands",
          ("1 park on the air on 20 m" in got["line"], "2 stations heard here on 20 m" in got["line"],
           "1 on other bands" in got["line"], "WSJT-X is on 14.074 MHz FT8" in got["line"]), (True, True, True, True))
    check("a port another program holds is said on the line", "already taken" in got["busy_line"], True)

    print("\n-- 6 m and 2 m: the spots alone --")
    so = got["spotsOnly"]
    check("the forecast's controls are put away", (so["antenna"], so["watts"]), (False, False))
    check("  the view, the spots and the reset stay", (so["view"], so["spots"], so["reset"]), (True, True, True))
    check("  the reason there is no forecast is said, and the title says what the map is",
          (so["words"], so["title"].startswith("Who is on")), (True, True))
    check("and an HF band has them all back", (got["forecast"]["antenna"], got["forecast"]["words"],
                                               got["forecast"]["title"].startswith("Where")), (True, False, True))

    print("\n-- the hover card --")
    check("a park: who, where, and an invitation",
          ("K1ABC is on the air from US-1234" in got["park_card"], "give them a call" in got["park_card"]), (True, True))
    check("a callsign off the network is text, never markup", (got["injected"], got["bad_text"].startswith("<img")),
          (False, True))

    print("\n-- the POTA page points at the map --")
    check("before any sample, it says when the parks will show, and still points at the map",
          ("twenty minutes" in live["unsampled"]), True)
    check("the parks counted, and said as operators calling for contacts",
          ("7 parks are on the air" in live["words"], "calling for contacts" in live["words"]), (True, True))
    check("each HF band links to its reach map with the parks shown, busiest first",
          live["links"], ["/bandplan#20m,spots", "/bandplan#40m,spots", "/bandplan#%3Cb%3Ex%3C%2Fb%3E,spots",
                          "/bandplan#6m,spots"])
    check("  6 m is a way in too - its map has the spots alone", "/bandplan#6m,spots" in live["links"], True)
    check("  70 cm is counted but not linked - no map for it", any(t.startswith("70 cm") for t in live["spans"]), True)
    check("  and a band name from the feed is text, never markup", live["injected"], False)
    check("  with when the sample was taken", live["when"], "POTA, as of 14:05 UTC")
    check("the Band Plan opened on #20m,spots is on 20 m and asking for the spots",
          (hashed["band"], hashed["wants"]), ("20 m", True))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
