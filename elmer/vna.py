"""What a vector network analyser would show, for an antenna you have not built.

A NanoVNA costs about what a cheap handheld costs and has done more for
amateur antenna work than any other instrument of the last decade, because it
answers the question an SWR meter cannot: not "how bad is it" but "which way do
I cut". An SWR meter gives one number, and one number cannot tell a long
antenna from a short one - both read high. A VNA gives the reactance with its
sign, and the sign is the instruction.

So this module produces the two traces an operator needs to be able to read.

**At the feedpoint.** What the antenna is actually doing: resistance and
reactance against frequency, resonance where the reactance crosses zero, and
the span where SWR stays under two.

**At the shack end of the feedline.** What the instrument will really show if
it is plugged in indoors, which is not the same trace and is not supposed to
be. Line loss attenuates the reflected wave twice over, so a long lossy run
flatters the antenna: the SWR reads lower at the shack than at the antenna, and
the difference is your power being turned into heat in the coax. That is the
single most useful thing a beginner can be shown, because the improvement they
think they are seeing is the loss they are paying.

Nothing here is an antenna modeller. The feedpoint impedance is the
resonant-circuit approximation out of `patterns`, good near resonance and
honest about stopping, and the line transform is the one in `smith`. What it
adds is sweeping them together and reading the markers off, which is the part a
person otherwise has to do by eye on an instrument they have not learned yet.
"""
import math

from . import patterns, smith

# Kept to what the approximation can defend. Past about a sixth either side of
# resonance the series-resonant form stops describing a real antenna, and a
# trace drawn out to a whole octave would be confident nonsense - which on a
# teaching instrument is worse than no trace at all.
MAX_SPAN = 0.34
DEFAULT_POINTS = 201


def _swr(gamma):
    g = abs(gamma)
    return float("inf") if g >= 0.999999 else (1 + g) / (1 - g)


def _cap(swr, limit=20.0):
    return None if swr == float("inf") else round(min(swr, limit), 3)


def _crossings(rows, key, level):
    """Where a trace crosses a level, interpolated - the 2:1 points."""
    out = []
    for a, b in zip(rows, rows[1:]):
        ya, yb = a[key], b[key]
        if ya is None or yb is None:
            continue
        # An exact hit is a crossing. Missing that case is how a whip resonant
        # precisely on the sweep's centre frequency - the commonest thing
        # anybody will type in - reported no resonance at all.
        if ya == level:
            out.append(a["mhz"])
        elif (ya - level) * (yb - level) < 0:
            t = (level - ya) / (yb - ya)
            out.append(a["mhz"] + t * (b["mhz"] - a["mhz"]))
    if rows and rows[-1][key] == level:
        out.append(rows[-1]["mhz"])
    return out


def _markers(rows, swr_key, x_key):
    """Resonance, the best match, and the useful width - read off the trace.

    Resonance and best match are not the same frequency and are not always
    close: resonance is where the reactance crosses zero, the best match is
    where SWR bottoms out, and on a feedline they can be a long way apart. An
    instrument shows both and says neither, so both are reported.
    """
    usable = [r for r in rows if r[swr_key] is not None]
    if not usable:
        return {}
    best = min(usable, key=lambda r: r[swr_key])
    zero = _crossings(rows, x_key, 0.0)
    edges = _crossings(rows, swr_key, 2.0)
    # An odd number of crossings means the useful span runs off the edge of the
    # sweep, and so does none at all with the whole trace under the limit. Both
    # are reported as what they are rather than as "no bandwidth", which is the
    # opposite of the truth and the easy mistake here.
    band, clipped = None, False
    if edges:
        lo = min(edges) if any(e < best["mhz"] for e in edges) else rows[0]["mhz"]
        hi = max(edges) if any(e > best["mhz"] for e in edges) else rows[-1]["mhz"]
        clipped = lo == rows[0]["mhz"] or hi == rows[-1]["mhz"]
        band = {"low_mhz": round(lo, 4), "high_mhz": round(hi, 4),
                "khz": round((hi - lo) * 1000)}
    elif all(r[swr_key] <= 2.0 for r in usable):
        band, clipped = {"low_mhz": rows[0]["mhz"], "high_mhz": rows[-1]["mhz"],
                         "khz": round((rows[-1]["mhz"] - rows[0]["mhz"]) * 1000)}, True
    if band:
        band["wider_than_sweep"] = clipped
    return {
        "best_swr": round(best[swr_key], 3),
        "best_mhz": round(best["mhz"], 4),
        "resonance_mhz": round(zero[0], 4) if zero else None,
        "band_2to1": band,
    }


def sweep(kind="dipole", f0_mhz=14.2, line="rg8x", feet=0.0, centre_mhz=None,
          span=0.14, points=DEFAULT_POINTS, q=None):
    """One sweep, at the feedpoint and at the far end of `feet` of `line`.

    `f0_mhz` is where the antenna is resonant - the length you cut it to.
    `centre_mhz` is where you are looking, which is the point of the whole
    exercise: an antenna cut for 14.2 and swept around 14.2 tells you nothing
    about whether you cut it right.
    """
    spec = smith.LINES.get(line) or smith.LINES["rg8x"]
    z0 = spec["z0"]
    centre = float(centre_mhz or f0_mhz)
    span = max(0.01, min(MAX_SPAN, float(span)))
    points = max(21, min(801, int(points)))
    feet = max(0.0, float(feet))

    rows = []
    for n in range(points):
        f = centre * (1 - span / 2 + span * n / (points - 1))
        if f <= 0:
            continue
        z = patterns.feedpoint_z(kind, f, f0_mhz, q)
        g = smith.reflection(z, z0)
        z_in = smith.transform(z, line, f, feet) if feet else z
        g_in = smith.reflection(z_in, z0)
        s_ant, s_in = _swr(g), _swr(g_in)
        rows.append({
            "mhz": round(f, 5),
            "r": round(z.real, 2), "x": round(z.imag, 2),
            "swr": _cap(s_ant),
            "rl_db": round(smith.return_loss_db(g), 2) if abs(g) > 1e-9 else 60.0,
            "gx": round(g.real, 5), "gy": round(g.imag, 5),
            "r_in": round(z_in.real, 2), "x_in": round(z_in.imag, 2),
            "swr_in": _cap(s_in),
            "rl_in_db": round(smith.return_loss_db(g_in), 2) if abs(g_in) > 1e-9 else 60.0,
            "gx_in": round(g_in.real, 5), "gy_in": round(g_in.imag, 5),
        })

    at_antenna = _markers(rows, "swr", "x")
    at_shack = _markers(rows, "swr_in", "x_in")
    matched = smith.matched_loss_db(line, centre, feet) if feet else 0.0
    return {
        "kind": kind, "f0_mhz": round(f0_mhz, 4), "centre_mhz": round(centre, 4),
        "span": round(span, 4), "points": len(rows),
        "low_mhz": rows[0]["mhz"], "high_mhz": rows[-1]["mhz"],
        "line": line, "line_label": spec["label"], "z0": z0, "feet": round(feet, 1),
        "matched_loss_db": round(matched, 3),
        "antenna": at_antenna, "shack": at_shack,
        "rows": rows,
        "read": reading(centre, at_antenna, at_shack, feet, matched,
                        spec["label"], z0),
    }


def reading(centre, at_antenna, at_shack, feet, matched_db, line_label, z0):
    """The sentence an experienced operator would say looking at that screen.

    This is the part that is not on the instrument. A NanoVNA will show you a
    dip at 13.9 MHz all day and never once tell you that the antenna is long
    and by how much.
    """
    out = []
    res = at_antenna.get("resonance_mhz")
    if res:
        off = (res - centre) / centre
        if abs(off) < 0.002:
            out.append("Resonant essentially where you are looking - the "
                       "reactance crosses zero inside the sweep.")
        else:
            # A half-wave element is a half wavelength: the fractional length
            # error is the fractional frequency error, the other way up.
            pct = abs(off) * 100.0
            longer = res < centre
            out.append(
                "Resonance is at %.3f MHz, %.2f%% %s where you want it, so the "
                "antenna is %s. %s it by about %.1f%% and the dip comes to you."
                % (res, pct, "below" if longer else "above",
                   "long" if longer else "short",
                   "Shorten" if longer else "Lengthen", pct))
        out.append("Below resonance the reactance is negative and the antenna "
                   "is short; above it the reactance is positive and it is "
                   "long. That sign is the instruction, and it is the thing an "
                   "SWR meter cannot give you.")
    else:
        out.append("The reactance does not cross zero inside this sweep, so "
                   "resonance is outside it - widen the span or move the "
                   "centre until the dip appears.")

    best = at_antenna.get("best_swr")
    if best is not None and best > 2.0:
        out.append("Best SWR in the sweep is %.2f:1, which never gets under "
                   "two - so either resonance is outside this span, or the "
                   "feedpoint resistance is nowhere near %g ohms and no amount "
                   "of cutting will fix that on its own."
                   % (best, z0))

    band = at_antenna.get("band_2to1")
    if band:
        out.append("Under 2:1 from %.3f to %.3f MHz, which is %d kHz of usable "
                   "width." % (band["low_mhz"], band["high_mhz"], band["khz"]))

    if feet:
        sa, ss = at_antenna.get("best_swr"), at_shack.get("best_swr")
        if sa and ss and ss < sa - 0.05:
            out.append(
                "At the shack end the same antenna reads %.2f:1 instead of "
                "%.2f:1. That is not an improvement. The reflected wave makes "
                "the trip back down %.0f ft of %s and arrives weakened, so the "
                "meter sees less of it - %.2f dB of matched loss each way. A "
                "long lossy run always flatters the antenna, and the flattery "
                "is your power warming the coax."
                % (ss, sa, feet, line_label, matched_db))
    return out
