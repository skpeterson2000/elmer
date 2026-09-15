#!/usr/bin/env python3
"""Turn Natural Earth's coarse coastline into the small file the EME page
draws its world with.

    python3 tools/coastline.py ne_110m_coastline.geojson

The source is Natural Earth's 1:110m coastline (public domain), fetched from
https://github.com/nvkelso/natural-earth-vector - geojson/ne_110m_coastline.geojson.
What comes out is a list of polylines, each a list of [lon, lat] rounded to a
tenth of a degree, which is a pixel at the size the page draws it and about
a third of the GeoJSON's weight. The kiosks have no network, so the coast
ships with the program rather than being fetched.
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "elmer" / "static" / "maps" / "coast.json"


def main(src):
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    lines = []
    for feature in data["features"]:
        geom = feature["geometry"]
        parts = [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]
        for part in parts:
            line, last = [], None
            for lon, lat in part:
                point = [round(lon, 1), round(lat, 1)]
                if point != last:
                    line.append(point)
                last = point
            if len(line) > 1:
                lines.append(line)
    OUT.write_text(json.dumps(lines, separators=(",", ":")), encoding="utf-8")
    print(f"{len(lines)} coastlines, {sum(len(line) for line in lines)} points, "
          f"{OUT.stat().st_size // 1024} KB -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
