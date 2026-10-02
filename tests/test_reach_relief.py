#!/usr/bin/env python3
"""The reach map is drawn over a raised-relief globe, the forecast as a cloud.

    python3 tests/test_reach_relief.py

The map's land and sea were two flat tints. Now the ground is Natural
Earth's shaded relief (tools/relief.py), and the band is drawn over it
exactly as the plain map draws it - the same ramp of the band's color, the
same lines - with the relief where the plain map has its dim tints. **Map**
puts the plain tints back, and **Cloud** blends the band back to the bare
ground. What is held here:

  - the relief pictures ship, a whole world at two to one, small enough for
    a page and a Pi;
  - the map opens on the relief, the slider at 100%;
  - at 100% a strong place is the plain map's own pixel - switching the map
    does not change how the band looks;
  - the slider fades the band alone: at 0% a strong place is the ground
    itself, and an isoline is the same color whatever the slider says;
  - the isolines are numbered;
  - **plain** is the old map, its slider is put away, and the choice is kept;
  - in the great-circle view past the rim is still empty.
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
MAPS = ROOT / "elmer" / "static" / "maps"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


SNAP = {"sfi": 150.0, "k_index": 1.0, "hmf2": 300.0, "muf": 28.0, "fof2": 8.0, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}
SERVE = (
    "import sys; sys.path.insert(0, %r)\n"
    "from elmer import app as appmod, places, propagation\n"
    "propagation.snapshot = lambda *a, **k: dict(%r)\n"
    "places.refresh_in_background = lambda *a, **k: None\n"
    "appmod._prefetch_regional = lambda place: None\n"
    "appmod.app.run(host='127.0.0.1', port=%%d, threaded=True, use_reloader=False)" % (str(ROOT), SNAP))

DRIVE = """
new Promise(async resolve => { try {
  const nap = ms => new Promise(x => setTimeout(x, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof bpReachDraw === 'function' && document.getElementById('bp-reach-base'), 12000);
  const out = {};
  const base = document.getElementById('bp-reach-base'), cloud = document.getElementById('bp-reach-cloud');
  out.opens = base.value;
  out.slider = Number(cloud.value);
  out.sliderShown = !document.getElementById('bp-reach-cloud-wrap').hidden;
  await until(() => bpReachFor && bpReachFor.qth, 15000);
  const b20 = await until(() => document.querySelector('button[data-band="20 m"]'), 10000);
  if (b20) b20.click();
  await until(() => bpReachFor && bpReachFor.mhz === 14 && bpRelief.coarse, 15000);
  await nap(500);
  out.relief = bpRelief.coarse ? [bpRelief.coarse.W, bpRelief.coarse.H] : null;
  // What the sky does at this hour is the model's business (test_reach_*.py).
  // Here the map is drawn from a field that runs 0 to 100 west to east, so
  // there is a strong place and every isoline whatever the clock says.
  const cols = bpReachFor.cols;
  bpReachFor = Object.assign({}, bpReachFor, {cells: bpReachFor.cells.map((_, k) => Math.round((k % cols) * 100 / (cols - 1)))});
  bpView.refined = null;
  // the isolines' numbers, counted as they are written
  const realFill = CanvasRenderingContext2D.prototype.fillText;
  let numbers = 0;
  CanvasRenderingContext2D.prototype.fillText = function (t, x, y, w) {
    if (['20', '40', '60', '80'].includes(String(t))) numbers++;
    return realFill.apply(this, arguments);
  };
  bpReachDraw(false);
  CanvasRenderingContext2D.prototype.fillText = realFill;
  out.numbers = numbers;
  const canvas = document.getElementById('bp-reach-map');
  const g = canvas.getContext('2d');
  const at = i => { const x = i % canvas.width, y = (i - x) / canvas.width; return [...g.getImageData(x, y, 1, 1).data].slice(0, 3); };
  const f = bpCloudKept;
  out.kept = !!f && f.W === canvas.width;
  // a strong place well inside the cloud, and a pixel on an isoline
  const band = v => REACH_CONTOURS.filter(c => v >= c).length;
  // the strongest place on the map, and every pixel where the score crosses an isoline
  let strong = -1, lines = [];
  for (let i = canvas.width * 40; i < f.score.length - canvas.width * 40; i++) {
    const v = f.score[i];
    if (v >= 0 && (strong < 0 || v > f.score[strong])) strong = i;
    if (v >= 0 && band(v) !== band(f.score[i + 1])) lines.push(i);
  }
  out.strongest = strong >= 0 ? Math.round(f.score[strong]) : null;
  out.found = [strong >= 0 && f.score[strong] >= 70, lines.length > 100];
  // most of them: a coastline, a border or a number drawn over a few is fine
  // the plain map's own line: its ramp at that score, darkened, shaded by night
  const ink = (j, v) => { const k = Math.round(v) * 3; return [0, 1, 2].map(c => REACH_LUT[k + c] * f.shade[j] * 0.55); };
  const near = (c, k) => c.every((v, j) => Math.abs(v - k[j]) <= 3);
  const inked = () => lines.filter((i, n) => n % 9 === 0).filter(i => {
    const c = at(i);
    return [i, i - 1, i - canvas.width].some(j => near(c, ink(i, f.score[j])));
  }).length;
  const line = lines[0];
  const set = async pct => { cloud.value = pct; cloud.dispatchEvent(new Event('input')); await nap(250); };
  await set(100);
  const strong85 = at(strong), line85 = at(line);
  const plainPixel = [0, 1, 2].map(c => REACH_LUT[Math.round(f.score[strong]) * 3 + c] * f.shade[strong]);
  out.plainSame = near(strong85, plainPixel);
  out.plainPair = [strong85, plainPixel.map(Math.round)];
  await set(0);
  const strong0 = at(strong), line0 = at(line);
  const ground = [f.ground[strong * 3], f.ground[strong * 3 + 1], f.ground[strong * 3 + 2]];
  // and it is the band's own color: the pixel's channels rank as the band's do
  const rank = c => [0, 1, 2].sort((a, b) => c[b] - c[a]).join('');
  out.bandHue = [rank(strong85) === rank(REACH_RGB), rank(REACH_RGB)];
  out.bare = strong0.every((c, i) => Math.abs(c - ground[i]) <= 2);
  out.lineSteady = line85.every((c, i) => Math.abs(c - line0[i]) <= 2);
  const sampled = lines.filter((i, n) => n % 9 === 0).length;
  out.lineInk = inked() > sampled * 0.6;
  out.inkShare = [inked(), sampled];
  out.fieldKept = bpCloudKept === f;
  cloud.dispatchEvent(new Event('change'));
  out.sliderKept = recall('bandplan.cloud', null);
  base.value = 'plain'; base.dispatchEvent(new Event('change'));
  await nap(400);
  out.plainHidesSlider = document.getElementById('bp-reach-cloud-wrap').hidden;
  out.plainKept = recall('bandplan.base', null);
  out.plainDropsField = bpCloudKept === null;
  base.value = 'relief'; base.dispatchEvent(new Event('change'));
  await set(85);
  const proj = document.getElementById('bp-reach-proj');
  proj.value = 'globe'; proj.dispatchEvent(new Event('change'));
  await nap(500);
  out.globeCorner = [...g.getImageData(2, 2, 1, 1).data].slice(0, 3);
  proj.value = 'flat'; proj.dispatchEvent(new Event('change'));
  resolve(JSON.stringify(out));
} catch (e) { resolve(JSON.stringify({error: String(e) + ' ' + (e.stack || '')})); } })
"""


def shipped():
    from PIL import Image
    print("\n-- the relief pictures ship, a whole world each --")
    for name, width, most_kb in (("relief.jpg", 2048, 400), ("relief-4k.jpg", 4096, 1200)):
        path = MAPS / name
        check(f"{name} is there", path.exists(), True)
        if not path.exists():
            continue
        with Image.open(path) as im:
            check(f"  {name} is a JPEG at two to one", (im.format, im.size), ("JPEG", (width, width // 2)))
        check(f"  {name} is small enough for a page on a Pi (under {most_kb} KB)", path.stat().st_size < most_kb * 1024, True)


def main():
    shipped()
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    server = subprocess.Popen([sys.executable, "-c", SERVE % port], env=dict(os.environ),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", method="POST",
                                     data=json.dumps({"location": {"lat": 46.60, "lon": -94.31,
                                                                   "short": "Pequot Lakes", "grid": "EN36"}}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", DRIVE, width=1400, height=1200,
                                           settle=1.0, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    if got.get("error"):
        print("  page:", got["error"])

    print("\n-- the map opens on the relief, the band at full --")
    check("Map opens on relief", got.get("opens"), "relief")
    check("the slider opens at 100 and is shown", (got.get("slider"), got.get("sliderShown")), (100, True))
    check("the page's relief is read in, a whole world", got.get("relief"), [2048, 1024])
    check("the field under the cloud is kept for the view", got.get("kept"), True)

    print("\n-- the band is the plain map's, and the slider fades it alone --")
    check(f"a strong place (best {got.get('strongest')}) and isolines were found on the map", got.get("found"), [True, True])
    check(f"at 100% a strong place is the plain map's own pixel ({got.get('plainPair')})", got.get("plainSame"), True)
    check("  in the band's own color, not white - the band is the band on every map",
          (got.get("bandHue") or [False])[0], True)
    check("at 0% it is the ground itself", got.get("bare"), True)
    check("an isoline is the same whatever the slider says", got.get("lineSteady"), True)
    check(f"  and drawn as the plain map draws it, its ramp darkened ({got.get('inkShare')} sampled)",
          got.get("lineInk"), True)
    check("moving the slider blends again rather than working the map out again", got.get("fieldKept"), True)
    check("the slider's setting is kept", got.get("sliderKept"), 0)

    print("\n-- the isolines are numbered --")
    check("numbers are written on the lines", (got.get("numbers") or 0) > 0, True)

    print("\n-- plain is the old map, and the choice is kept --")
    check("plain puts the slider away", got.get("plainHidesSlider"), True)
    check("  and is kept", got.get("plainKept"), "plain")
    check("  and lets the kept field go", got.get("plainDropsField"), True)

    print("\n-- the great circle on the relief still ends at the far side --")
    check("past the rim there is nothing", got.get("globeCorner"), [13, 17, 23])


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
