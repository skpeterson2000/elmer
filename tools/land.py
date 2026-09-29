#!/usr/bin/env python3
"""Turn Natural Earth's land and lakes into the small files the reach map
fills land and water with.

    python3 tools/land.py <folder with the source files>

Sources, public domain, from Natural Earth
(https://github.com/nvkelso/natural-earth-vector, geojson/):
    ne_110m_land.geojson    ne_110m_lakes.geojson    the whole world
    ne_50m_land.geojson     ne_50m_lakes.geojson     zoomed in

The reach map drew only coastlines, over land and sea of the same near-black,
so the band's glow read as sitting on the lines rather than on the ocean or a
continent. These are the shapes to fill: each file is {"land": rings,
"lakes": rings}, every ring a closed list of [lon, lat] snapped to what a
pixel is at the zoom it is drawn at. A polygon's holes are rings like any
other - the page fills with the even-odd rule, so a hole comes out a hole -
and the lakes are filled as water over the land. Natural Earth splits its
polygons at 180 degrees, so no ring crosses the date line. The kiosks have
no network, so these ship with the program.
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "elmer" / "static" / "maps"

# (land source, lakes source, output, the grid the points are snapped to in degrees)
LAYERS = [
    ("ne_110m_land.geojson", "ne_110m_lakes.geojson", "land.json", 0.1),
    ("ne_50m_land.geojson", "ne_50m_lakes.geojson", "land-50m.json", 0.05),
]


def snap(value, quantum):
    return round(round(value / quantum) * quantum, 3)


def rings_of(data, quantum):
    """Every ring of every polygon, outer and holes alike, snapped and closed.
    A ring that snaps down to fewer than four points is a speck at this
    size and is left out."""
    out = []
    for feature in data["features"]:
        geom = feature.get("geometry")
        if not geom:
            continue
        if geom["type"] == "Polygon":
            rings = geom["coordinates"]
        elif geom["type"] == "MultiPolygon":
            rings = [ring for poly in geom["coordinates"] for ring in poly]
        else:
            continue
        for ring in rings:
            pts, last = [], None
            for lon, lat in ring:
                p = [snap(lon, quantum), snap(lat, quantum)]
                if p != last:
                    pts.append(p)
                last = p
            if len(pts) >= 4:
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                out.append(pts)
    return out


def main(src):
    src = Path(src)
    for land_src, lakes_src, name, quantum in LAYERS:
        land = rings_of(json.loads((src / land_src).read_text(encoding="utf-8")), quantum)
        lakes = rings_of(json.loads((src / lakes_src).read_text(encoding="utf-8")), quantum)
        out = OUT / name
        out.write_text(json.dumps({"land": land, "lakes": lakes}, separators=(",", ":")), encoding="utf-8")
        print(f"{name}: {len(land)} land rings, {len(lakes)} lakes, "
              f"{sum(len(r) for r in land) + sum(len(r) for r in lakes)} points, {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1])
