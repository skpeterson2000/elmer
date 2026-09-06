"""Repeaters near the station, for the bands where they are the answer.

Above 50 MHz "what can I reach" is a different question than it is on HF. A
2 m vertical at thirty feet reaches other antennas about fifteen miles away,
which around most stations names no towns at all - and ELMER used to say
exactly that and stop, having correctly observed that the repeater is doing the
reaching and then declining to say which repeater.

This is where the repeaters come from. TowerWitch, the station's own repeater
tool, already keeps a RepeaterBook export with coordinates on it; if it is
installed alongside, ELMER reads it rather than asking the operator to gather
the same list twice. `--import-repeaters` copies that list into ELMER's own
data so it keeps working on a Pi that has no TowerWitch on it.

Two honesties are carried through to the screen. A coordinate matched only to
the county is marked approximate, because a bearing computed from a county
centroid is a direction to a county, not to a machine on a hill. And nothing
here says a repeater is reachable: it says where it is and how far. Terrain
decides the rest, and terrain is not in a CSV.
"""
import csv
import json
import math
import os
import time
from pathlib import Path

from . import bandplan
from .terrain import great_circle

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "repeaters.json"

# A repeater is on a tower or a hill; the operator is usually not. Assuming a
# couple of hundred feet for the far end is what makes the radius resemble the
# distance people actually work, rather than the antenna-to-antenna figure.
ASSUMED_TOWER_FT = 200.0

_cache = {"key": None, "rows": [], "source": None}


def horizon_km(height_ft, other_ft=ASSUMED_TOWER_FT):
    """Radio horizon between two antennas, 4/3 earth, in kilometres."""
    miles = 1.415 * (math.sqrt(max(float(height_ft), 1.0))
                     + math.sqrt(max(float(other_ft), 1.0)))
    return miles * 1.609


def find_towerwitch():
    """Where TowerWitch is, if it is anywhere obvious."""
    named = os.environ.get("ELMER_TOWERWITCH")
    candidates = [Path(named).expanduser()] if named else []
    candidates += [Path.home() / "TowerWitch", ROOT.parent / "TowerWitch"]
    for path in candidates:
        try:
            if (path / "data").is_dir() or (path / "radio_cache").is_dir():
                return path
        except OSError:
            continue
    return None


def _band(mhz):
    band = bandplan.band_at(mhz)
    if isinstance(band, dict):
        return band.get("name")
    return band


def _row(call, output, **kw):
    """One repeater, with the fields the screen needs and nothing else."""
    try:
        output = round(float(output), 4)
    except (TypeError, ValueError):
        return None
    if not call or not 28.0 <= output <= 1300.0:
        return None
    row = {"call": str(call).strip().upper(), "output": output,
           "input": None, "offset": None, "tone": None, "location": "",
           "county": "", "modes": "", "lat": None, "lon": None,
           "approx": False}
    row.update({k: v for k, v in kw.items() if k in row})
    row["band"] = _band(output)
    return row


def _num(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _town_key(location, county, state):
    """RepeaterBook writes a site, not a town: "Nisswa - WJJY Tower"."""
    town = str(location or "").split(" - ")[0].split(",")[0].strip().lower()
    return f"{town}|{str(county or '').strip().lower()}|{str(state or '').strip().lower()}", town


def place_table(path):
    """TowerWitch's town coordinates, which are better than a county centroid."""
    try:
        raw = json.loads((Path(path) / "data" / "location_coordinates.json").read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for key, value in raw.items() if isinstance(raw, dict) else []:
        lat, lon = _num((value or {}).get("lat")), _num((value or {}).get("lon"))
        if lat is not None and lon is not None:
            out[str(key).strip().lower()] = (lat, lon)
    return out


def _from_csv(path, places=None):
    """A RepeaterBook export, enriched with coordinates."""
    places = places or {}
    out = []
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for line in csv.DictReader(handle):
                lat, lon = _num(line.get("Latitude")), _num(line.get("Longitude"))
                if lat is None or lon is None:
                    continue          # no coordinate, no bearing, no entry
                tone = (line.get("Uplink Tone") or line.get("Downlink Tone") or "").strip()
                # A county centroid puts five machines in five different towns
                # at one identical bearing, which looks like precision and is
                # not. Where the town itself is known, use it and say so.
                county = (line.get("County") or "").strip()
                key, town = _town_key(line.get("Location"), county, line.get("State"))
                approx = "county" in (line.get("Match Method") or "").lower()
                if key in places and town and town != county.lower():
                    lat, lon = places[key]
                    approx = False
                row = _row(
                    line.get("Call"), line.get("Output Freq"),
                    input=_num(line.get("Input Freq")),
                    offset=_num(line.get("Offset")), tone=tone or None,
                    location=(line.get("Location") or "").strip(),
                    county=(line.get("County") or "").strip(),
                    modes=(line.get("Modes") or "").strip(),
                    lat=lat, lon=lon,
                    # Where a machine could only be placed by county, say so
                    # rather than implying a bearing to something we have not
                    # actually located.
                    approx=approx)
                if row:
                    out.append(row)
    except (OSError, csv.Error):
        return []
    return out


def _from_cache_json(path):
    """One of TowerWitch's cached lookups, which already carry coordinates."""
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    out = []
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        row = _row(entry.get("call"),
                   entry.get("output") or entry.get("frequency"),
                   input=_num(entry.get("input")),
                   offset=_num(entry.get("offset")),
                   tone=entry.get("tone") or entry.get("pl_tone"),
                   location=(entry.get("location") or "").strip(),
                   lat=_num(entry.get("lat")), lon=_num(entry.get("lon")))
        if row and row["lat"] is not None and row["lon"] is not None:
            out.append(row)
    return out


def _dedupe(rows):
    """One entry per machine. Later sources win only where they say more."""
    best = {}
    for row in rows:
        key = (row["call"], round(row["output"], 3))
        was = best.get(key)
        if was is None or (was["approx"] and not row["approx"]):
            best[key] = row
    return sorted(best.values(), key=lambda r: (r["output"], r["call"]))


def from_towerwitch(path=None):
    """Every repeater TowerWitch knows where it is, with coordinates."""
    path = Path(path).expanduser() if path else find_towerwitch()
    if not path or not path.is_dir():
        return []
    rows = []
    places = place_table(path)
    data = path / "data"
    if data.is_dir():
        # Enriched exports first: they are the same rows with coordinates on.
        for csv_path in sorted(data.glob("*_enriched.csv")):
            rows += _from_csv(csv_path, places)
        for csv_path in sorted(data.glob("*.csv")):
            if not csv_path.name.endswith("_enriched.csv"):
                rows += _from_csv(csv_path, places)
    cache = path / "radio_cache"
    if cache.is_dir():
        for json_path in sorted(cache.glob("repeaters_*.json")):
            rows += _from_cache_json(json_path)
    return _dedupe(rows)


def load():
    """Every repeater ELMER knows about, and where the list came from."""
    store_stamp = STORE.stat().st_mtime if STORE.is_file() else None
    tw = find_towerwitch()
    key = (str(store_stamp), str(tw))
    if _cache["key"] == key:
        return _cache["rows"], _cache["source"]

    rows, source = [], None
    if STORE.is_file():
        try:
            payload = json.loads(STORE.read_text())
            rows = [r for r in payload.get("repeaters", []) if r.get("lat") is not None]
            for row in rows:
                row.setdefault("band", _band(row["output"]))
            source = payload.get("source") or "ELMER's own list"
        except (OSError, ValueError):
            rows = []
    if not rows and tw:
        rows = from_towerwitch(tw)
        source = f"TowerWitch ({tw})" if rows else None

    _cache.update({"key": key, "rows": rows, "source": source})
    return rows, source


def save(rows, source):
    """Keep a list of ELMER's own, so it works without TowerWitch there."""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps({
        "note": "Repeaters near this station, with coordinates. Imported "
                "rather than typed; entries marked approx were placed only to "
                "their county, so treat the bearing as a direction to the "
                "county rather than to the machine.",
        "source": source, "imported": time.time(),
        "repeaters": rows}, indent=1))
    _cache["key"] = None
    return len(rows)


def import_towerwitch(path=None):
    """Copy TowerWitch's repeater list into ELMER's own data."""
    where = Path(path).expanduser() if path else find_towerwitch()
    if not where:
        return False, ("no TowerWitch installation found - looked at "
                       "$ELMER_TOWERWITCH, ~/TowerWitch and next to ELMER"), 0
    rows = from_towerwitch(where)
    if not rows:
        return False, (f"found {where}, but nothing in it carried both a "
                       f"callsign and a coordinate"), 0
    return True, f"imported {save(rows, f'TowerWitch ({where})')} repeaters", len(rows)


def nearby(lat, lon, mhz=None, radius_km=None, height_ft=30.0, limit=8):
    """The repeaters within reach of here, nearest first.

    `mhz` restricts the answer to the band being worked: somebody setting up
    for 2 m is not helped by a list of 70 cm machines.
    """
    rows, source = load()
    if not rows:
        return [], None
    if radius_km is None:
        radius_km = horizon_km(height_ft)
    want = _band(mhz) if mhz else None

    out = []
    for row in rows:
        if want and row.get("band") != want:
            continue
        km, bearing = great_circle(lat, lon, row["lat"], row["lon"])
        if km > radius_km:
            continue
        entry = dict(row)
        entry["km"] = round(km, 1)
        entry["miles"] = round(km * 0.6214)
        entry["bearing"] = round(bearing)
        entry["where"] = (row.get("location")
                          or (f"{row['county']} County" if row.get("county") else ""))
        out.append(entry)
    out.sort(key=lambda r: r["km"])
    return out[:limit], source
