#!/usr/bin/env python3
"""Bundle the National Park Service units as POTA lists them.

    python3 tools/build_national_parks.py

Every unit gets the national parks without fetching anything: they are the
places people drive across the country for, the ones a visitor plans a
radio afternoon around, and there are only about four hundred of them. The
state parks are a different bargain - thousands, and of interest only near
home - so those stay with "Fetch what is near", for the interested.

How the list is made, because "National" in a name is not enough: national
forests are the Forest Service's, wildlife refuges are Fish and Wildlife's,
grasslands and conservation areas are somebody else's again, and the rules
on the activations page differ for each. So the candidates are picked by
name from every US location's POTA list, and then each one is confirmed
against the park's own record, which names the agency. Only those the
National Park Service manages are kept. That is a few hundred requests,
throttled, run once when the list is rebuilt - not something a unit does.

Writes data/parks/national.json in the same shape references.py holds
fetched parks in, so the activations page draws on both without knowing
which is which.
"""
import json
import re
from collections import Counter
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elmer import references  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data" / "parks" / "national.json"
PARK = "https://api.pota.app/park/{ref}"

# The unit types the National Park Service uses in names. Not "National
# Forest", "National Wildlife Refuge", "National Grassland" - those are
# other agencies', and the confirmation step would throw them out anyway;
# this keeps the confirmation to a few hundred requests rather than a few
# thousand.
CANDIDATE = re.compile(
    r"\bNational (Park|Monument|Seashore|Lakeshore|Historical Park|Historic Site|"
    r"Memorial|Battlefield|Military Park|Recreation Area|Preserve|Reserve|Parkway|"
    r"River|Riverway|Scenic River|Wild and Scenic River|Historic Trail|Scenic Trail|"
    r"Heritage Area|Cemetery|Mall)\b", re.I)
THROTTLE = 0.25

# The unit types POTA assigns that are the National Park Service's, used
# when a record names no agency. A "National Monument" or "National
# Recreation Area" with no agency named could be BLM's or the Forest
# Service's; those two are kept on the type when nothing says otherwise,
# and the note in the file says so.
NPS_UNITS = {
    "National Park", "National Monument", "National Seashore", "National Lakeshore",
    "National Historical Park", "National Historic Site", "National Memorial",
    "National Battlefield", "National Battlefield Park", "National Military Park",
    "National Recreation Area", "National Preserve", "National Reserve", "National Parkway",
    "National River", "National Scenic Riverway", "National Historic Trail",
    "National Scenic Trail", "National Heritage Area", "National Mall",
}


def main():
    locations = references._get(references.POTA_LOCATIONS) or []
    us = [loc for loc in locations if str(loc.get("locationDesc", "")).startswith("US-")]
    print(f"{len(us)} US locations")
    candidates = {}
    for loc in us:
        rows = references._get(references.POTA_PARKS.format(code=loc["locationDesc"])) or []
        for park in rows:
            name = park.get("name") or ""
            if CANDIDATE.search(name) and "State" not in name and park.get("latitude") is not None:
                candidates[park["reference"]] = park
        time.sleep(THROTTLE)
    print(f"{len(candidates)} candidates by name")
    kept, dropped = [], Counter()
    for n, (ref, park) in enumerate(sorted(candidates.items()), 1):
        detail = references._get(PARK.format(ref=ref)) or {}
        agencies = detail.get("agencies") or ""
        unit = detail.get("parktypeDesc") or ""
        # The agency field is the answer when it is filled in; it is empty
        # on a good many NPS records (Padre Island's among them), and then
        # the unit type POTA assigns has to stand in for it.
        if agencies and "National Park Service" not in agencies:
            dropped[agencies] += 1
            continue
        if not agencies and unit not in NPS_UNITS:
            dropped["type: " + unit] += 1
            continue
        kept.append({
            "kind": "park", "ref": ref, "name": park.get("name") or ref,
            "lat": round(park["latitude"], 4), "lon": round(park["longitude"], 4),
            "where": park.get("locationDesc") or "", "grid": park.get("grid") or "",
            "activations": park.get("activations") or 0,
            "type": detail.get("parktypeDesc") or "",
            "website": detail.get("website") or park.get("website") or "",
        })
        if n % 50 == 0:
            print(f"  {n}/{len(candidates)} checked, {len(kept)} kept")
        time.sleep(THROTTLE)
    for why, count in dropped.most_common(12):
        print(f"  dropped {count:4d}  {why}")
    kept.sort(key=lambda p: p["ref"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "National Park Service units as Parks on the Air lists them: candidates by name "
                "from every US location, each checked against its own POTA record - kept when the "
                "record names the National Park Service, dropped when it names another agency, and "
                "judged by the unit type when it names none. Built by tools/build_national_parks.py; "
                "rebuild when POTA adds references.",
        "built": time.strftime("%Y-%m-%d"),
        "source": "api.pota.app",
        "parks": kept}, indent=1), encoding="utf-8")
    print(f"{len(kept)} National Park Service units -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
