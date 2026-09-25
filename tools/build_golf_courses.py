#!/usr/bin/env python3
"""Write the three golf courses ELMER plays, from the real cards.

    python3 tools/build_golf_courses.py

Pebble Beach for the Technician pool, the Old Course for General, Augusta
for Extra - friendliest to hardest, which is roughly how golf ranks them
too. Par and yardage are the card's. The hazards are the famous ones on
each hole, placed as bands of yards from the tee along the line of play,
approximately; anyone who knows a hole better than this file is welcome to
move a bunker. The wind is the course's typical, and each round draws its
own around it.

Nothing here is taken from a video game. Real yardages, real hazards and
the real names of real places are facts; the games' own renderings of them
are theirs.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "golf"


def H(kind, frm, to, side="", name=""):
    """A hazard as a band of yards from the tee: where a ball would be lost
    (water), in sand (bunker), or in trouble (rough, out of bounds)."""
    return {"kind": kind, "from": frm, "to": to, "side": side, "name": name}


PEBBLE = {
    "id": "pebble-beach", "name": "Pebble Beach Golf Links", "where": "Pebble Beach, California",
    "pool": "technician", "par": 72,
    "wind": {"typical_mph": 12, "from": "the Pacific, off the left on the ocean holes",
             "note": "steady afternoon sea breeze; the 6th to the 10th and the 17th and 18th feel it most"},
    "notes": "Card from the resort tees. Hazards are the famous ones, placed approximately.",
    "holes": [
        {"n": 1, "par": 4, "yards": 377, "name": "", "wind": "with", "green": 28,
         "hazards": [H("bunker", 230, 250, "right", "fairway bunker"), H("bunker", 355, 377, "left", "greenside")]},
        {"n": 2, "par": 5, "yards": 502, "name": "", "wind": "with", "green": 30,
         "hazards": [H("bunker", 235, 260, "left", "fairway bunker"), H("water", 400, 420, "across", "the barranca")]},
        {"n": 3, "par": 4, "yards": 390, "name": "", "wind": "across", "green": 26,
         "hazards": [H("bunker", 250, 275, "left", "fairway bunkers"), H("bunker", 370, 390, "right", "greenside")]},
        {"n": 4, "par": 4, "yards": 331, "name": "", "wind": "across", "green": 24,
         "hazards": [H("bunker", 220, 250, "right", "fairway bunkers"), H("water", 240, 331, "right", "Stillwater Cove")]},
        {"n": 5, "par": 3, "yards": 195, "name": "", "wind": "into", "green": 30,
         "hazards": [H("bunker", 170, 195, "left", "front bunkers"), H("water", 195, 230, "beyond", "the cove beyond")]},
        {"n": 6, "par": 5, "yards": 513, "name": "", "wind": "into", "green": 32,
         "hazards": [H("bunker", 240, 270, "left", "fairway bunkers"), H("water", 250, 513, "right", "the cliff and the ocean")]},
        {"n": 7, "par": 3, "yards": 106, "name": "", "wind": "into", "green": 22,
         "hazards": [H("bunker", 85, 106, "around", "the ring of bunkers"), H("water", 106, 140, "beyond", "the Pacific")]},
        {"n": 8, "par": 4, "yards": 428, "name": "", "wind": "across", "green": 26,
         "hazards": [H("water", 255, 330, "across", "the chasm"), H("bunker", 400, 428, "right", "greenside")]},
        {"n": 9, "par": 4, "yards": 481, "name": "", "wind": "with", "green": 28,
         "hazards": [H("water", 200, 481, "right", "the beach and the ocean"), H("bunker", 440, 470, "left", "fairway bunker")]},
        {"n": 10, "par": 4, "yards": 446, "name": "", "wind": "with", "green": 26,
         "hazards": [H("water", 220, 446, "right", "the cliff"), H("bunker", 260, 285, "left", "fairway bunker")]},
        {"n": 11, "par": 4, "yards": 380, "name": "", "wind": "into", "green": 24,
         "hazards": [H("bunker", 240, 265, "right", "fairway bunker"), H("bunker", 355, 380, "left", "greenside")]},
        {"n": 12, "par": 3, "yards": 202, "name": "", "wind": "across", "green": 30,
         "hazards": [H("bunker", 175, 202, "front", "front bunker")]},
        {"n": 13, "par": 4, "yards": 401, "name": "", "wind": "across", "green": 28,
         "hazards": [H("bunker", 245, 270, "left", "fairway bunkers"), H("bunker", 380, 401, "right", "greenside")]},
        {"n": 14, "par": 5, "yards": 573, "name": "", "wind": "into", "green": 22,
         "hazards": [H("bunker", 250, 280, "right", "fairway bunker"), H("bunker", 545, 573, "left", "the deep greenside bunker")]},
        {"n": 15, "par": 4, "yards": 397, "name": "", "wind": "with", "green": 26,
         "hazards": [H("bunker", 235, 260, "left", "fairway bunkers")]},
        {"n": 16, "par": 4, "yards": 403, "name": "", "wind": "with", "green": 24,
         "hazards": [H("bunker", 250, 275, "right", "fairway bunker"), H("water", 300, 330, "across", "the barranca")]},
        {"n": 17, "par": 3, "yards": 178, "name": "", "wind": "into", "green": 40,
         "hazards": [H("bunker", 150, 178, "front", "the front bunkers"), H("water", 178, 220, "beyond", "the ocean")]},
        {"n": 18, "par": 5, "yards": 543, "name": "", "wind": "into", "green": 30,
         "hazards": [H("water", 0, 543, "left", "Carmel Bay, the whole way"), H("bunker", 260, 290, "right", "fairway bunkers"),
                     H("bunker", 515, 543, "right", "greenside")]},
    ]}

ST_ANDREWS = {
    "id": "st-andrews-old", "name": "The Old Course at St Andrews", "where": "St Andrews, Fife, Scotland",
    "pool": "general", "par": 72,
    "wind": {"typical_mph": 16, "from": "the south-west, helping out and against coming home",
             "note": "links wind; out with it, back into it, and the double greens are enormous"},
    "notes": "Card from the medal tees. Pot bunkers are the named ones; the Swilcan Burn and the road are where they are.",
    "holes": [
        {"n": 1, "par": 4, "yards": 376, "name": "Burn", "wind": "with", "green": 34,
         "hazards": [H("water", 340, 360, "across", "the Swilcan Burn")]},
        {"n": 2, "par": 4, "yards": 453, "name": "Dyke", "wind": "with", "green": 40,
         "hazards": [H("bunker", 240, 260, "left", "Cheape's bunker"), H("rough", 0, 453, "right", "gorse")]},
        {"n": 3, "par": 4, "yards": 397, "name": "Cartgate (out)", "wind": "with", "green": 40,
         "hazards": [H("bunker", 370, 397, "left", "Cartgate bunker")]},
        {"n": 4, "par": 4, "yards": 480, "name": "Ginger Beer", "wind": "with", "green": 40,
         "hazards": [H("bunker", 250, 270, "left", "Cottage bunker"), H("bunker", 430, 450, "left", "Ginger Beer bunkers")]},
        {"n": 5, "par": 5, "yards": 568, "name": "Hole O'Cross (out)", "wind": "with", "green": 50,
         "hazards": [H("bunker", 220, 250, "left", "the Seven Sisters"), H("bunker", 470, 490, "front", "the Spectacles")]},
        {"n": 6, "par": 4, "yards": 412, "name": "Heathery (out)", "wind": "across", "green": 40,
         "hazards": [H("bunker", 230, 255, "left", "Coffin bunkers"), H("rough", 0, 412, "right", "heather and gorse")]},
        {"n": 7, "par": 4, "yards": 371, "name": "High (out)", "wind": "across", "green": 40,
         "hazards": [H("bunker", 340, 371, "front", "Shell bunker")]},
        {"n": 8, "par": 3, "yards": 175, "name": "Short", "wind": "across", "green": 36,
         "hazards": [H("bunker", 150, 175, "front", "Short Hole bunker")]},
        {"n": 9, "par": 4, "yards": 352, "name": "End", "wind": "with", "green": 34,
         "hazards": [H("bunker", 210, 235, "left", "Boase's and End Hole bunkers")]},
        {"n": 10, "par": 4, "yards": 386, "name": "Bobby Jones", "wind": "into", "green": 34,
         "hazards": [H("bunker", 220, 245, "left", "Kruger bunkers")]},
        {"n": 11, "par": 3, "yards": 174, "name": "High (in)", "wind": "into", "green": 36,
         "hazards": [H("bunker", 150, 174, "left", "Hill bunker"), H("bunker", 155, 174, "right", "Strath bunker"),
                     H("water", 174, 200, "beyond", "the Eden estuary")]},
        {"n": 12, "par": 4, "yards": 348, "name": "Heathery (in)", "wind": "into", "green": 34,
         "hazards": [H("bunker", 200, 260, "center", "the hidden bunkers")]},
        {"n": 13, "par": 4, "yards": 465, "name": "Hole O'Cross (in)", "wind": "into", "green": 50,
         "hazards": [H("bunker", 250, 275, "left", "the Coffins"), H("bunker", 420, 445, "front", "Walkinshaw's")]},
        {"n": 14, "par": 5, "yards": 618, "name": "Long", "wind": "into", "green": 40,
         "hazards": [H("bunker", 230, 260, "left", "the Beardies"), H("bunker", 430, 470, "center", "Hell bunker"),
                     H("rough", 0, 618, "right", "the wall and out of bounds")]},
        {"n": 15, "par": 4, "yards": 455, "name": "Cartgate (in)", "wind": "into", "green": 40,
         "hazards": [H("bunker", 235, 260, "center", "Sutherland bunker")]},
        {"n": 16, "par": 4, "yards": 423, "name": "Corner of the Dyke", "wind": "into", "green": 34,
         "hazards": [H("bunker", 230, 260, "center", "the Principal's Nose"),
                     H("rough", 0, 423, "right", "the railway, out of bounds")]},
        {"n": 17, "par": 4, "yards": 495, "name": "Road", "wind": "across", "green": 30,
         "hazards": [H("rough", 0, 260, "right", "the hotel grounds, out of bounds"),
                     H("bunker", 470, 495, "left", "the Road Hole bunker"),
                     H("water", 495, 520, "beyond", "the road and the wall")]},
        {"n": 18, "par": 4, "yards": 357, "name": "Tom Morris", "wind": "into", "green": 30,
         "hazards": [H("water", 60, 80, "across", "the Swilcan Burn"), H("rough", 330, 357, "front", "the Valley of Sin")]},
    ]}

AUGUSTA = {
    "id": "augusta-national", "name": "Augusta National Golf Club", "where": "Augusta, Georgia",
    "pool": "extra", "par": 72,
    "wind": {"typical_mph": 9, "from": "swirling in the pines; unreadable at the 12th",
             "note": "light, but it turns in Amen Corner and the greens punish anything slow"},
    "notes": "Card from the tournament tees. Rae's Creek and the ponds are where they are; bunkers are the ones that decide holes.",
    "holes": [
        {"n": 1, "par": 4, "yards": 445, "name": "Tea Olive", "wind": "across", "green": 30,
         "hazards": [H("bunker", 270, 300, "right", "fairway bunker"), H("bunker", 420, 445, "left", "greenside")]},
        {"n": 2, "par": 5, "yards": 575, "name": "Pink Dogwood", "wind": "with", "green": 34,
         "hazards": [H("bunker", 280, 310, "right", "fairway bunker"), H("bunker", 540, 575, "front", "the two greenside bunkers")]},
        {"n": 3, "par": 4, "yards": 350, "name": "Flowering Peach", "wind": "into", "green": 22,
         "hazards": [H("bunker", 230, 270, "left", "the cluster of fairway bunkers")]},
        {"n": 4, "par": 3, "yards": 240, "name": "Flowering Crab Apple", "wind": "into", "green": 30,
         "hazards": [H("bunker", 210, 240, "front", "the front bunkers")]},
        {"n": 5, "par": 4, "yards": 495, "name": "Magnolia", "wind": "across", "green": 30,
         "hazards": [H("bunker", 280, 320, "left", "the deep fairway bunkers")]},
        {"n": 6, "par": 3, "yards": 180, "name": "Juniper", "wind": "across", "green": 32,
         "hazards": [H("bunker", 150, 180, "front", "front bunker")]},
        {"n": 7, "par": 4, "yards": 450, "name": "Pampas", "wind": "with", "green": 22,
         "hazards": [H("bunker", 415, 450, "around", "five greenside bunkers")]},
        {"n": 8, "par": 5, "yards": 570, "name": "Yellow Jasmine", "wind": "with", "green": 30,
         "hazards": [H("bunker", 290, 320, "right", "fairway bunker")]},
        {"n": 9, "par": 4, "yards": 460, "name": "Carolina Cherry", "wind": "across", "green": 28,
         "hazards": [H("bunker", 425, 460, "left", "greenside bunkers"), H("rough", 430, 460, "front", "the false front")]},
        {"n": 10, "par": 4, "yards": 495, "name": "Camellia", "wind": "with", "green": 30,
         "hazards": [H("bunker", 300, 340, "right", "the fairway bunker"), H("bunker", 460, 495, "right", "greenside")]},
        {"n": 11, "par": 4, "yards": 520, "name": "White Dogwood", "wind": "across", "green": 28,
         "hazards": [H("water", 470, 520, "left", "the pond"), H("bunker", 490, 520, "right", "greenside")]},
        {"n": 12, "par": 3, "yards": 155, "name": "Golden Bell", "wind": "swirling", "green": 14,
         "hazards": [H("water", 130, 150, "across", "Rae's Creek"), H("bunker", 145, 155, "front", "the front bunker"),
                     H("bunker", 155, 175, "beyond", "the back bunkers")]},
        {"n": 13, "par": 5, "yards": 545, "name": "Azalea", "wind": "across", "green": 30,
         "hazards": [H("water", 0, 545, "left", "Rae's Creek along the left"),
                     H("water", 500, 520, "across", "the tributary at the green"),
                     H("bunker", 520, 545, "beyond", "the back bunkers")]},
        {"n": 14, "par": 4, "yards": 440, "name": "Chinese Fir", "wind": "into", "green": 30,
         "hazards": [H("rough", 400, 440, "front", "the false front and the swale")]},
        {"n": 15, "par": 5, "yards": 550, "name": "Firethorn", "wind": "with", "green": 24,
         "hazards": [H("water", 500, 525, "across", "the pond in front"), H("water", 550, 575, "beyond", "the pond at the 16th")]},
        {"n": 16, "par": 3, "yards": 170, "name": "Redbud", "wind": "across", "green": 30,
         "hazards": [H("water", 0, 150, "left", "the pond, all the way"), H("bunker", 150, 170, "right", "the bunkers")]},
        {"n": 17, "par": 4, "yards": 440, "name": "Nandina", "wind": "into", "green": 26,
         "hazards": [H("bunker", 270, 300, "left", "fairway bunker"), H("bunker", 410, 440, "front", "greenside")]},
        {"n": 18, "par": 4, "yards": 465, "name": "Holly", "wind": "into", "green": 28,
         "hazards": [H("bunker", 280, 320, "left", "the fairway bunkers"), H("bunker", 435, 465, "front", "the greenside bunkers")]},
    ]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for course in (PEBBLE, ST_ANDREWS, AUGUSTA):
        assert sum(h["par"] for h in course["holes"]) == course["par"], course["id"]
        assert [h["n"] for h in course["holes"]] == list(range(1, 19)), course["id"]
        path = OUT / f"{course['id']}.json"
        path.write_text(json.dumps(course, indent=1) + "\n", encoding="utf-8")
        print(f"  {course['id']}: par {course['par']}, "
              f"{sum(h['yards'] for h in course['holes'])} yards, {len(course['holes'])} holes -> {path.name}")


if __name__ == "__main__":
    main()
