#!/usr/bin/env python3
"""What the numerical work costs on this machine: run it on each Pi.

    ./tools/pibench.py                 # the whole bench, a table on the screen
    ./tools/pibench.py --json pi4.json # and the numbers, for the plans
    ./tools/pibench.py --quick         # small sizes only, for a test run

The plans in docs/plans/ estimate what the antenna solver, the ground wave
by the ITU's method and golf's flight would cost on a Raspberry Pi by scaling
timings from a desktop. This measures them where they will run, so the
estimates can be replaced with numbers. It times:

  - imports: numpy, scipy.special, scipy.linalg and scipy.integrate, each
    in a fresh Python, since a unit pays for an import once per start;
  - the antenna solver: filling and solving the thin-wire matrix the
    solver plan describes (triangle basis, Galerkin testing, the reduced
    kernel) for 100 to 800 unknowns, and a half-wave dipole's feed
    impedance as a check that the machine's numpy answers correctly;
  - the ground wave: a 400-point field-strength curve by ITU-R P.368's
    method, from the ground-wave plan's prototype (which matched the ITU's
    own program within 0.009 dB), on three grounds;
  - golf: one flight, a cold launch-speed solve, and one player's club
    yards after a slider move, from the game's own code.

BLAS is held to one thread, as ELMER will run it: several threads on a
Pi's four cores fight the web server for them.

Nothing is fetched, nothing is written but the --json file, and it needs
numpy and scipy (./install.sh puts them in). The solver and the ground wave
here are the plans' stand-ins, not ELMER's code; neither exists in ELMER yet.
"""
import os

# Before numpy is imported anywhere, or it has already chosen its threads.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def best_ms(fn, repeat=5):
    """The fastest of `repeat` runs, in milliseconds: the machine's figure,
    not the scheduler's."""
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000.0)
    return min(times)


def machine():
    info = {"platform": platform.platform(), "machine": platform.machine(),
            "python": platform.python_version(), "cpus": os.cpu_count(),
            "blas_threads": os.environ.get("OPENBLAS_NUM_THREADS")}
    model = Path("/proc/device-tree/model")
    try:
        info["model"] = model.read_text(errors="replace").strip("\x00\n ")
    except OSError:
        info["model"] = platform.processor() or "unknown"
    try:
        import numpy
        import scipy
        info["numpy"], info["scipy"] = numpy.__version__, scipy.__version__
    except ImportError as exc:
        info["missing"] = str(exc)
    return info


def import_times():
    """Each import in a fresh interpreter, three times, the fastest kept."""
    out = {}
    for name in ("numpy", "scipy.special", "scipy.linalg", "scipy.integrate"):
        code = ("import os, time\n"
                "for v in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):\n"
                "    os.environ.setdefault(v, '1')\n"
                "t = time.perf_counter()\n"
                f"import {name}\n"
                "print((time.perf_counter() - t) * 1000)")
        runs = []
        for _ in range(3):
            done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
            if done.returncode != 0:
                runs = None
                break
            runs.append(float(done.stdout.strip()))
        out[name] = round(min(runs), 1) if runs else None
    return out


# --------------------------------------------------------------- the solver

def wire_matrix(segments, length=0.5, radius=0.001, quad=4, block=64):
    """The impedance matrix of a straight wire, one wavelength = 1 m.

    Triangle basis functions over pairs of segments, Galerkin testing, the
    reduced kernel exp(-jkR)/4piR with R = sqrt(dz^2 + a^2). Filled in row
    blocks the general way, without using the straight wire's symmetry, so
    the cost is what any geometry of this many segments costs.
    """
    import numpy as np
    c0 = 299792458.0
    mu = 4e-7 * math.pi
    eps = 1.0 / (mu * c0 * c0)
    k = 2 * math.pi
    omega = k * c0
    s = segments
    delta = length / s
    gx, gw = np.polynomial.legendre.leggauss(quad)
    t = 0.5 * (gx + 1.0)
    w = 0.5 * gw
    pts = (-length / 2 + (np.arange(s)[:, None] + t[None, :]) * delta)       # (s, q)
    i00 = np.empty((s, s), complex)
    i10 = np.empty((s, s), complex)
    i01 = np.empty((s, s), complex)
    i11 = np.empty((s, s), complex)
    ww = w[:, None] * w[None, :]
    for b0 in range(0, s, block):
        b1 = min(s, b0 + block)
        dz = pts[b0:b1, :, None, None] - pts[None, None, :, :]               # (b, q, s, q)
        r = np.sqrt(dz * dz + radius * radius)
        g = np.exp(-1j * k * r) / (4 * math.pi * r) * (delta * delta)
        g = g.transpose(0, 2, 1, 3)                                           # (b, s, q, q)
        i00[b0:b1] = np.einsum("bsqr,qr->bs", g, ww)
        i10[b0:b1] = np.einsum("bsqr,qr->bs", g, ww * t[:, None])
        i01[b0:b1] = np.einsum("bsqr,qr->bs", g, ww * t[None, :])
        i11[b0:b1] = np.einsum("bsqr,qr->bs", g, ww * t[:, None] * t[None, :])
    m = np.arange(s - 1)
    rr = i11[m[:, None], m[None, :]]
    rf = i10[m[:, None], m[None, :] + 1] - i11[m[:, None], m[None, :] + 1]
    fr = i01[m[:, None] + 1, m[None, :]] - i11[m[:, None] + 1, m[None, :]]
    ff = (i00 - i10 - i01 + i11)[m[:, None] + 1, m[None, :] + 1]
    vector = rr + rf + fr + ff
    scalar = (i00[m[:, None], m[None, :]] - i00[m[:, None], m[None, :] + 1]
              - i00[m[:, None] + 1, m[None, :]] + i00[m[:, None] + 1, m[None, :] + 1]) / (delta * delta)
    return 1j * omega * mu * vector + scalar / (1j * omega * eps)


def feed_impedance(z, feed):
    import numpy as np
    v = np.zeros(z.shape[0], complex)
    v[feed] = 1.0
    return 1.0 / np.linalg.solve(z, v)[feed]


def bench_solver(sizes):
    import numpy as np
    out = {}
    z = wire_matrix(40)
    zin = feed_impedance(z, 19)
    out["dipole_check"] = {"segments": 40, "r_ohm": round(zin.real, 1), "x_ohm": round(zin.imag, 1),
                           "ok": bool(60.0 < zin.real < 95.0 and 20.0 < zin.imag < 70.0)}
    for n in sizes:
        fill = best_ms(lambda: wire_matrix(n + 1), repeat=3)
        z = wire_matrix(n + 1)
        v = np.zeros(n, complex)
        v[n // 2] = 1.0
        solve = best_ms(lambda: np.linalg.solve(z, v), repeat=3)
        out[str(n)] = {"fill_ms": round(fill, 2), "solve_ms": round(solve, 2),
                       "matrix_mb": round(z.nbytes / 1e6, 1)}
    return out


# ------------------------------------------------------------ the ground wave
# ITU-R P.368-10's method (NTIA's LFMF, h = 0 terminals): the flat earth with
# a curvature correction close in, and the residue series past it, all roots
# found together. From the ground-wave plan's prototype.

EPS0 = 8.854187817e-12
C0 = 299792458.0
_AKP = [-1.0187929716, -3.2481975822, -4.8200992112, -6.1633073556, -7.3721772550,
        -8.4884867340, -9.5354490524, -10.5276603970, -11.4750666335, -12.3847883718]
_AK = [-2.3381074105, -4.0879494441, -5.5205698281, -6.7867080901, -7.9441335871,
       -9.0226508533, -10.0401743416, -11.0085243037, -11.9360255632, -12.8287867529]


def _w1(t):
    import numpy as np
    from scipy import special
    u = np.exp(-2j * np.pi / 3)
    ai, aip, _, _ = special.airy(t * u)
    return (2 * np.sqrt(np.pi) * np.exp(-1j * np.pi / 6) * ai,
            2 * np.sqrt(np.pi) * np.exp(-5j * np.pi / 6) * aip)


def _roots(q, n):
    import numpy as np
    i = np.arange(1, n + 1)
    small = abs(q) ** 3 <= 4 * (i - 1) + 3
    t_s = np.where(i <= 10, np.r_[_AKP, np.zeros(max(0, n - 10))][:n], 0.0)
    tt = (3 / 8) * np.pi * (4 * (i - 1) + 1)
    t_s = np.where(i <= 10, t_s, -tt ** (2 / 3) * (1 - 7 / 48 * tt ** -2 + 35 / 288 * tt ** -4))
    t_l = np.where(i <= 10, np.r_[_AK, np.zeros(max(0, n - 10))][:n], 0.0)
    tt = (3 / 8) * np.pi * (4 * (i - 1) + 3)
    t_l = np.where(i <= 10, t_l, -tt ** (2 / 3) * (1 + 5 / 48 * tt ** -2 - 5 / 36 * tt ** -4))
    ph = np.exp(2j * np.pi / 3)
    t = np.where(small, t_s * ph + q / (t_s * ph), t_l * ph + 1 / q)
    for _ in range(25):
        w, wd = _w1(t)
        a = (wd - q * w) / (t * w - q * wd)
        t = t - a
        if np.all(abs((a / t).real) + abs((a / t).imag) <= 0.5e-6):
            break
    return t


def field_db(f_mhz, eps, sigma, d_km, ns=315.0, nroots=200):
    """dB(uV/m) for 1 kW from P.368's reference short monopole, both ends on
    the ground."""
    import numpy as np
    from scipy import special
    d_km = np.atleast_1d(np.asarray(d_km, float))
    fhz = f_mhz * 1e6
    lam_km = C0 / fhz / 1000
    ae = 6370 / (1 - 0.04665 * math.exp(0.005577 * ns))
    k = 2 * np.pi / lam_km
    nu = (ae * k / 2) ** (1 / 3)
    eta = complex(eps, -sigma / (EPS0 * 2 * np.pi * fhz))
    delta = np.sqrt(eta - 1) / eta
    q = -1j * nu * delta
    out = np.empty_like(d_km)
    near = d_km < 80 * f_mhz ** (-1 / 3)
    if near.any():
        d = d_km[near]
        qi = (-0.5 + 0.5j) * np.sqrt(k * d) * delta
        p = qi * qi
        fp = 1 + np.sqrt(np.pi) * 1j * qi * special.wofz(qi)
        q3, q6 = q ** 3, q ** 6
        fx = fp + (1 - 1j * np.sqrt(np.pi * p) - (1 + 2 * p) * fp) / (4 * q3)
        fx = fx + (1 - 1j * np.sqrt(np.pi * p) * (1 - p) - 2 * p + 5 * p * p / 6 + (p * p / 2 - 1) * fp) / (4 * q6)
        out[near] = abs(fx)
    far = ~near
    if far.any():
        t = _roots(q, nroots)
        w = 1 / (t - q * q)
        x = nu * d_km[far] / ae
        gw = (w[None, :] * np.exp(-1j * np.outer(x, t))).sum(axis=1)
        out[far] = abs(np.sqrt(x) * np.sqrt(np.pi / 2) * (1 - 1j) * gw)
    return 60 + 20 * np.log10(out * 300.0 / d_km)


def bench_groundwave():
    import numpy as np
    ds = np.geomspace(0.5, 3000, 400)
    out = {}
    for name, f, eps, sigma in (("160 m, average", 1.8, 13.0, 0.005),
                                ("40 m, sea", 7.0, 70.0, 5.0),
                                ("11 m, average", 27.2, 13.0, 0.005)):
        curve = field_db(f, eps, sigma, ds)
        falls = bool(np.all(np.isfinite(curve)) and curve[0] > curve[-1])
        out[name] = {"curve_ms": round(best_ms(lambda: field_db(f, eps, sigma, ds)), 2), "ok": falls}
    return out


# ---------------------------------------------------------------------- golf

def bench_golf():
    from elmer import golf
    v = golf._launch_speed("driver", None, 0.0)
    out = {"flight_ms": round(best_ms(lambda: golf._fly(v, 10.9, 2686), repeat=20), 3)}
    flights = [0]
    real_fly = golf._fly

    def counting(*a, **k):
        flights[0] += 1
        return real_fly(*a, **k)
    golf._fly = counting
    try:
        golf._launch_speed.cache_clear()
        flights[0] = 0
        t0 = time.perf_counter()
        golf._launch_speed("7-iron", 0.37, 0.0)
        out["launch_solve_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        out["launch_solve_flights"] = flights[0]
    finally:
        golf._fly = real_fly
    course = {"id": "bench", "name": "Bench", "pool": "technician", "par": 4,
              "wind": {"typical_mph": 12},
              "holes": [{"n": 1, "par": 4, "yards": 400, "name": "", "wind": "into",
                         "green": 30, "hazards": []}]}
    g = golf.Golf(["a"], course, seed=1, seconds=30)
    g.club_yards("a")
    times = []
    for spin in (0.11, 0.33, 0.55, 0.77, 0.99):
        g.set_setup("a", shape=0.0, spin=spin)
        t0 = time.perf_counter()
        g.club_yards("a")
        times.append((time.perf_counter() - t0) * 1000.0)
    out["club_yards_after_slider_ms"] = round(sorted(times)[len(times) // 2], 2)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", help="also write the numbers to this file")
    ap.add_argument("--quick", action="store_true", help="small sizes only")
    args = ap.parse_args(argv)
    try:
        import numpy  # noqa: F401
        import scipy.special  # noqa: F401
    except ImportError as exc:
        print(f"pibench needs numpy and scipy: {exc}. ./install.sh puts them in.")
        return 2

    result = {"machine": machine()}
    m = result["machine"]
    print(f"\n  {m['model']} - {m['platform']}")
    print(f"  Python {m['python']}, numpy {m.get('numpy')}, scipy {m.get('scipy')}, "
          f"{m['cpus']} cores, BLAS threads {m['blas_threads']}")

    result["imports_ms"] = import_times()
    print("\n  imports, fresh interpreter (ms)")
    for name, ms in result["imports_ms"].items():
        print(f"    {name:<18} {ms if ms is not None else 'failed'}")

    sizes = [100, 200] if args.quick else [100, 200, 400, 800]
    result["solver"] = bench_solver(sizes)
    check = result["solver"]["dipole_check"]
    print("\n  antenna solver (plan's stand-in): thin wire, triangle basis, Galerkin")
    print(f"    half-wave dipole check: {check['r_ohm']} {check['x_ohm']:+} j ohm "
          f"({'ok' if check['ok'] else 'OUT OF RANGE - this numpy is not answering right'})")
    print("    unknowns   fill ms   solve ms   matrix MB")
    for n in sizes:
        r = result["solver"][str(n)]
        print(f"    {n:>8} {r['fill_ms']:>9} {r['solve_ms']:>10} {r['matrix_mb']:>11}")

    result["groundwave"] = bench_groundwave()
    print("\n  ground wave, P.368 method (plan's prototype): one 400-point curve")
    for name, r in result["groundwave"].items():
        print(f"    {name:<16} {r['curve_ms']:>8} ms{'' if r['ok'] else '   NOT A FALLING CURVE'}")

    result["golf"] = bench_golf()
    gr = result["golf"]
    print("\n  golf, the game's own code")
    print(f"    one flight                         {gr['flight_ms']} ms")
    print(f"    cold launch-speed solve            {gr['launch_solve_ms']} ms, {gr['launch_solve_flights']} flights")
    print(f"    club yards after a slider move     {gr['club_yards_after_slider_ms']} ms")

    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1))
        print(f"\n  written to {args.json}")
    ok = check["ok"] and all(r["ok"] for r in result["groundwave"].values())
    print("")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
