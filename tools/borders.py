#!/usr/bin/env python3
"""Turn public boundary data into the small line files the reach map draws
its borders with - countries, states and provinces, US counties - and a
finer coastline for when the map is zoomed in.

    python3 tools/borders.py <folder with the source files>

Sources, all public domain:
  Natural Earth (https://github.com/nvkelso/natural-earth-vector, geojson/):
    ne_110m_admin_0_boundary_lines_land.geojson   countries, coarse
    ne_50m_admin_1_states_provinces_lines.geojson states and provinces
    ne_50m_coastline.geojson                      the coast, finer than the EME page's
  US Census Bureau, 2010 cartographic boundaries at 1:20m, as GeoJSON
  (the copy at https://github.com/plotly/datasets, geojson-counties-fips.json):
    counties.json                                 US counties

Each comes out as a list of polylines of [lon, lat], rounded to what a
pixel is at the zoom that layer is drawn at, and - for the counties, which
arrive as one ring per county so every border is in the file twice - with
each shared segment kept once. The kiosks have no network, so the borders
ship with the program.
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "elmer" / "static" / "maps"

# (source, output, the grid the points are snapped to in degrees)
LAYERS = [
    ("ne_110m_admin_0_boundary_lines_land.geojson", "borders-countries.json", 0.1),
    ("ne_50m_admin_1_states_provinces_lines.geojson", "borders-states.json", 0.05),
    ("ne_50m_coastline.geojson", "coast-50m.json", 0.05),
]


def snap(value, quantum):
    return round(round(value / quantum) * quantum, 3)


def lines_of(data, quantum):
    out = []
    for feature in data["features"]:
        geom = feature["geometry"]
        if geom is None:
            continue
        if geom["type"] == "LineString":
            parts = [geom["coordinates"]]
        elif geom["type"] == "MultiLineString":
            parts = geom["coordinates"]
        elif geom["type"] == "Polygon":
            parts = geom["coordinates"]
        elif geom["type"] == "MultiPolygon":
            parts = [ring for poly in geom["coordinates"] for ring in poly]
        else:
            continue
        for part in parts:
            line, last = [], None
            for lon, lat in part:
                point = [snap(lon, quantum), snap(lat, quantum)]
                if point != last:
                    line.append(point)
                last = point
            if len(line) > 1:
                out.append(line)
    return out


def dedupe_segments(lines):
    """Rings that share an edge draw it twice; keep each segment once, and
    chain what is left back into runs so the file stays a list of lines."""
    seen, runs = set(), []
    for line in lines:
        run = []
        for a, b in zip(line, line[1:]):
            key = (tuple(a), tuple(b)) if tuple(a) <= tuple(b) else (tuple(b), tuple(a))
            if key in seen:
                if len(run) > 1:
                    runs.append(run)
                run = []
                continue
            seen.add(key)
            if not run:
                run = [a, b]
            else:
                run.append(b)
        if len(run) > 1:
            runs.append(run)
    return runs


def write(name, lines):
    path = OUT / name
    path.write_text(json.dumps(lines, separators=(",", ":")), encoding="utf-8")
    print(f"{len(lines):6d} lines, {sum(len(ln) for ln in lines):7d} points, {path.stat().st_size // 1024:5d} KB -> {path.name}")


def main(folder):
    folder = Path(folder)
    for src, name, quantum in LAYERS:
        data = json.loads((folder / src).read_text(encoding="utf-8"))
        write(name, lines_of(data, quantum))
    counties = folder / "counties.json"
    if counties.is_file():
        data = json.loads(counties.read_text(encoding="utf-8"))
        write("borders-counties.json", dedupe_segments(lines_of(data, 0.02)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
