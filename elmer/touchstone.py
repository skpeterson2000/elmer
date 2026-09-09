"""Touchstone: the file every other antenna program can already read.

A sweep off the NanoVNA is the one thing in ELMER that is a *measurement*
rather than a model, and a measurement that cannot leave the machine it was
taken on is half a measurement. Touchstone is the format the rest of the world
settled on decades ago - antenna modellers, NanoVNA-Saver, the simulation
packages, and the file an antenna manufacturer will ask you for. Writing it
costs almost nothing here because the instrument already hands back the raw
reflection coefficient, which is exactly what the file wants.

The format is older and simpler than it looks. A `.s1p` is a comment block, one
options line, and then a row per frequency:

    !comments, as many as you like
    # HZ S RI R 50
    14000000 0.03482 -0.11907

The options line says four things: what unit the frequencies are in, that these
are S-parameters, in what form, and against what reference impedance. `RI` is
real and imaginary, which is what a VNA actually measures and the form that
loses nothing - `MA` (magnitude and angle) and `DB` are conversions of it, and
converting on the way out only invites somebody to convert back. The `1` in
`s1p` is the port count, so a one-port antenna measurement is `.s1p` and it is
S11 all the way down.

Two things about this file are easy to get wrong and are worth stating because
they are what makes a file another program will actually accept:

    Frequencies are integers of hertz. The instrument sweeps in hertz and the
    program carries megahertz for the sake of the screen; writing 14.2 where
    14200000 belongs produces a file that parses and is wrong by six orders of
    magnitude, which some readers will happily plot.

    The reference impedance is stated, not assumed. Fifty ohms is the answer
    almost every time and it is still written down, because a file that does
    not say cannot be checked.

There is a reader here as well as a writer. It exists so the tests can take
the file apart and prove the numbers survived the trip, which is the only way
to be sure an export is real rather than merely well-formed.
"""
import math
import re
from datetime import datetime, timezone

# Hertz per unit, for the units Touchstone allows on the options line.
UNITS = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}

DEFAULT_Z0 = 50.0


def _swr(gx, gy):
    mag = math.hypot(gx, gy)
    if mag >= 0.999999:
        return None
    return (1.0 + mag) / (1.0 - mag)


def s1p(rows, z0=DEFAULT_Z0, device=None, when=None, note=None):
    """One-port S-parameters as Touchstone text.

    `rows` are the sweep points the instrument gave back: each needs `mhz` and
    the reflection coefficient as `gx` and `gy`. Anything else on them - SWR,
    return loss, the impedance - is derived from those two and is written into
    the comments rather than the data, because a Touchstone reader computes it
    for itself and a file that carried both could contradict itself.
    """
    z0 = float(z0 or DEFAULT_Z0)
    when = when or datetime.now(timezone.utc)
    points = [r for r in (rows or [])
              if r.get("mhz") is not None and r.get("gx") is not None
              and r.get("gy") is not None]
    if not points:
        raise ValueError("no sweep points to write")

    lines = [
        "!Touchstone 1.1 - one-port S-parameters (S11)",
        "!Measured by ELMER, radio study and propagation",
        f"!Date: {when.replace(microsecond=0).isoformat()}",
    ]
    if device:
        lines.append(f"!Instrument: {device}")
    if note:
        for piece in str(note).splitlines():
            lines.append("!" + piece)
    low, high = points[0]["mhz"], points[-1]["mhz"]
    lines.append(f"!Points: {len(points)}")
    lines.append(f"!Span: {low:.6f} to {high:.6f} MHz")
    lines.append(f"!Reference impedance: {z0:g} ohm")

    # The best point of the sweep, as a comment. It is the first thing anybody
    # looks for and the file is otherwise a wall of numbers - and being a
    # comment it cannot be mistaken for data by a reader that does not care.
    best = min(points, key=lambda r: math.hypot(r["gx"], r["gy"]))
    best_swr = _swr(best["gx"], best["gy"])
    if best_swr is not None:
        lines.append(f"!Best match: {best_swr:.2f}:1 at {best['mhz']:.6f} MHz")
    lines.append("!")
    lines.append("!freq(Hz)      real(S11)     imag(S11)")
    lines.append(f"# HZ S RI R {z0:g}")

    for row in points:
        hz = int(round(float(row["mhz"]) * 1e6))
        lines.append(f"{hz:<14d} {float(row['gx']):< 13.6f} "
                     f"{float(row['gy']):< 13.6f}")
    return "\n".join(lines) + "\n"


def read(text):
    """Parse a one-port Touchstone file back into rows. For the tests.

    Deliberately forgiving in the ways the format is: comments anywhere, the
    options line in any case, whitespace of any kind. Deliberately strict about
    the one thing that matters, which is that the frequency unit and the format
    on the options line are honoured rather than guessed.
    """
    unit, form, z0 = "GHZ", "MA", DEFAULT_Z0      # Touchstone's own defaults
    rows, seen_options = [], False
    for raw in (text or "").splitlines():
        line = raw.split("!", 1)[0].strip()
        if not line:
            continue
        if line.startswith("#"):
            parts = line[1:].upper().split()
            seen_options = True
            for i, token in enumerate(parts):
                if token in UNITS:
                    unit = token
                elif token in ("RI", "MA", "DB"):
                    form = token
                elif token == "R" and i + 1 < len(parts):
                    z0 = float(parts[i + 1])
            continue
        bits = re.split(r"[\s,]+", line)
        if len(bits) < 3:
            continue
        freq = float(bits[0]) * UNITS[unit]
        a, b = float(bits[1]), float(bits[2])
        if form == "RI":
            gx, gy = a, b
        elif form == "MA":
            gx = a * math.cos(math.radians(b))
            gy = a * math.sin(math.radians(b))
        else:                                     # DB: magnitude in decibels
            mag = 10.0 ** (a / 20.0)
            gx = mag * math.cos(math.radians(b))
            gy = mag * math.sin(math.radians(b))
        rows.append({"mhz": freq / 1e6, "gx": gx, "gy": gy})
    if not seen_options:
        raise ValueError("no Touchstone options line - this is not a .sNp file")
    return {"z0": z0, "unit": unit, "format": form, "rows": rows}


def filename(low_mhz, high_mhz, when=None):
    """A name that sorts and says what is in it."""
    when = when or datetime.now(timezone.utc)
    stamp = when.strftime("%Y%m%d-%H%M")
    return f"sweep-{low_mhz:.3f}-{high_mhz:.3f}mhz-{stamp}.s1p"
