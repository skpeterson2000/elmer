"""What radio a manual is for, from its title - so the shelf can say what
the operator owns.

A manual on the Library shelf is evidence of a radio in the shack: nobody
keeps the FT-991A's operating manual for the pleasure of it. Make Contact
asks "what have you got?" and used to assume a handheld; it can start from
the shelf instead, and say so, and be corrected.

This is a table of model names and what they are, matched against the
manual's title and filename with word boundaries. Deterministic: a model
not in the table is a manual ELMER cannot place, and it says that rather
than guessing from the maker's name. Kinds are the shapes Make Contact
reasons about - a handheld, a VHF/UHF mobile, an HF set, an all-mode set
that is both, a GMRS/FRS/CB radio - plus books and test gear, which are on
the shelf but are not radios.
"""
import re

# (pattern, make, model, kind, bands, watts). Patterns are matched
# case-insensitively with a word boundary each side; a hyphen in the model
# is optional in the match, because manuals spell them both ways.
RIGS = [
    # ---- Yaesu ---------------------------------------------------------
    (r"FT-?991A?", "Yaesu", "FT-991A", "allmode", "HF, 6 m, 2 m, 70 cm", 100),
    (r"FT-?891", "Yaesu", "FT-891", "hf", "HF and 6 m", 100),
    (r"FT-?710", "Yaesu", "FT-710", "hf", "HF and 6 m", 100),
    (r"FT-?DX-?10", "Yaesu", "FTDX10", "hf", "HF and 6 m", 100),
    (r"FT-?DX-?101", "Yaesu", "FTDX101", "hf", "HF and 6 m", 100),
    (r"FT-?450D?", "Yaesu", "FT-450D", "hf", "HF and 6 m", 100),
    (r"FT-?818", "Yaesu", "FT-818", "allmode", "HF, 6 m, 2 m, 70 cm", 6),
    (r"FT-?817", "Yaesu", "FT-817", "allmode", "HF, 6 m, 2 m, 70 cm", 5),
    (r"FT-?857D?", "Yaesu", "FT-857D", "allmode", "HF, 6 m, 2 m, 70 cm", 100),
    (r"FT-?897D?", "Yaesu", "FT-897D", "allmode", "HF, 6 m, 2 m, 70 cm", 100),
    (r"FT5D[RE]?", "Yaesu", "FT5D", "ht", "2 m and 70 cm", 5),
    (r"FT3D[RE]?", "Yaesu", "FT3D", "ht", "2 m and 70 cm", 5),
    (r"FT2D[RE]?", "Yaesu", "FT2D", "ht", "2 m and 70 cm", 5),
    (r"FT1X?D[RE]?", "Yaesu", "FT1D", "ht", "2 m and 70 cm", 5),
    (r"FT-?70D[RE]?", "Yaesu", "FT-70D", "ht", "2 m and 70 cm", 5),
    (r"FT-?65[RE]?", "Yaesu", "FT-65", "ht", "2 m and 70 cm", 5),
    (r"FT-?60[RE]?", "Yaesu", "FT-60", "ht", "2 m and 70 cm", 5),
    (r"FT-?4X[RE]?", "Yaesu", "FT-4X", "ht", "2 m and 70 cm", 5),
    (r"VX-?[678][RE]?", "Yaesu", "VX-6/7/8", "ht", "2 m and 70 cm", 5),
    (r"FTM-?(?:100|200|300|400|500|6000|3100|3200|7250)D?[RE]?", "Yaesu", "FTM series", "mobile", "2 m and 70 cm", 50),
    (r"FT-?2980[RE]?", "Yaesu", "FT-2980", "mobile", "2 m", 80),
    (r"FT-?(?:7900|8800|8900)[RE]?", "Yaesu", "FT-7900/8800/8900", "mobile", "2 m and 70 cm", 50),
    # ---- Icom ----------------------------------------------------------
    (r"IC-?705", "Icom", "IC-705", "allmode", "HF, 6 m, 2 m, 70 cm", 10),
    (r"IC-?7300", "Icom", "IC-7300", "hf", "HF and 6 m", 100),
    (r"IC-?7100", "Icom", "IC-7100", "allmode", "HF, 6 m, 2 m, 70 cm", 100),
    (r"IC-?7610", "Icom", "IC-7610", "hf", "HF and 6 m", 100),
    (r"IC-?7851", "Icom", "IC-7851", "hf", "HF and 6 m", 200),
    (r"IC-?718", "Icom", "IC-718", "hf", "HF", 100),
    (r"IC-?9700", "Icom", "IC-9700", "vhf_allmode", "2 m, 70 cm, 23 cm", 100),
    (r"IC-?905", "Icom", "IC-905", "vhf_allmode", "2 m and up", 10),
    (r"ID-?5[012]", "Icom", "ID-50/51/52", "ht", "2 m and 70 cm", 5),
    (r"IC-?T10", "Icom", "IC-T10", "ht", "2 m and 70 cm", 5),
    (r"IC-?V8[06]", "Icom", "IC-V80/V86", "ht", "2 m", 7),
    (r"IC-?T70", "Icom", "IC-T70", "ht", "2 m and 70 cm", 5),
    (r"ID-?(?:4100|5100)", "Icom", "ID-4100/5100", "mobile", "2 m and 70 cm", 50),
    (r"IC-?2730", "Icom", "IC-2730", "mobile", "2 m and 70 cm", 50),
    (r"IC-?2300", "Icom", "IC-2300", "mobile", "2 m", 65),
    # ---- Kenwood -------------------------------------------------------
    (r"TH-?D7[45]", "Kenwood", "TH-D74/D75", "ht", "2 m and 70 cm", 5),
    (r"TH-?K20", "Kenwood", "TH-K20", "ht", "2 m", 5),
    (r"TH-?F6", "Kenwood", "TH-F6", "ht", "2 m, 1.25 m, 70 cm", 5),
    (r"TM-?V71", "Kenwood", "TM-V71", "mobile", "2 m and 70 cm", 50),
    (r"TM-?D7[01]0", "Kenwood", "TM-D700/D710", "mobile", "2 m and 70 cm", 50),
    (r"TM-?281", "Kenwood", "TM-281", "mobile", "2 m", 65),
    (r"TS-?590", "Kenwood", "TS-590", "hf", "HF and 6 m", 100),
    (r"TS-?890", "Kenwood", "TS-890", "hf", "HF and 6 m", 100),
    (r"TS-?990", "Kenwood", "TS-990", "hf", "HF and 6 m", 200),
    (r"TS-?480", "Kenwood", "TS-480", "hf", "HF and 6 m", 100),
    (r"TS-?2000", "Kenwood", "TS-2000", "allmode", "HF, 6 m, 2 m, 70 cm", 100),
    # ---- Elecraft, Xiegu, QRP ------------------------------------------
    (r"KX2", "Elecraft", "KX2", "hf", "HF", 10),
    (r"KX3", "Elecraft", "KX3", "hf", "HF and 6 m", 10),
    (r"KH1", "Elecraft", "KH1", "hf", "HF", 5),
    (r"K[34]", "Elecraft", "K3/K4", "hf", "HF and 6 m", 100),
    (r"G90", "Xiegu", "G90", "hf", "HF", 20),
    (r"X6100", "Xiegu", "X6100", "hf", "HF and 6 m", 10),
    (r"G106", "Xiegu", "G106", "hf", "HF", 5),
    (r"TX-?500", "Lab599", "TX-500", "hf", "HF and 6 m", 10),
    (r"QMX|QCX", "QRP Labs", "QMX/QCX", "hf", "HF", 5),
    (r"u?BITX", "HF Signals", "uBITX", "hf", "HF", 10),
    # ---- Alinco, Anytone, TYT, Radioddity, Baofeng/BTECH, Wouxun -------
    (r"DJ-?[A-Z]{0,2}\d\w*", "Alinco", "DJ handheld", "ht", "2 m and 70 cm", 5),
    (r"DR-?[A-Z]{0,2}\d\w*", "Alinco", "DR mobile", "mobile", "2 m and 70 cm", 50),
    (r"DX-?SR[89]", "Alinco", "DX-SR8/SR9", "hf", "HF", 100),
    (r"AT-?D878", "Anytone", "AT-D878UV", "ht", "2 m and 70 cm", 7),
    (r"AT-?D578", "Anytone", "AT-D578UV", "mobile", "2 m and 70 cm", 50),
    (r"AT-?778", "Anytone", "AT-778UV", "mobile", "2 m and 70 cm", 25),
    (r"TH-?7800", "TYT", "TH-7800", "mobile", "2 m and 70 cm", 50),
    (r"TH-?9800", "TYT", "TH-9800", "mobile", "10 m, 6 m, 2 m, 70 cm FM", 50),
    (r"MD-?(?:380|390|UV380|UV390)", "TYT", "MD-380/UV380", "ht", "2 m and 70 cm", 5),
    (r"TH-?UV88", "TYT", "TH-UV88", "ht", "2 m and 70 cm", 5),
    (r"GD-?(?:77|88)", "Radioddity", "GD-77/88", "ht", "2 m and 70 cm", 5),
    (r"DB-?25", "Radioddity", "DB25", "mobile", "2 m and 70 cm", 25),
    (r"GM-?30", "Radioddity", "GM-30", "gmrs", "GMRS", 5),
    (r"UV-?5G", "Baofeng", "UV-5G", "gmrs", "GMRS", 5),
    (r"GMRS-?(?:V1|PRO)", "BTECH", "GMRS-V1/Pro", "gmrs", "GMRS", 5),
    (r"UV-?5R|UV-?82|BF-?F8|UV-?5X|UV-?9R|UV-?17|UV-?21", "Baofeng", "UV-5R family", "ht", "2 m and 70 cm", 5),
    (r"UV-?25X[24]|UV-?50X[23]", "BTECH", "UV-25X/50X", "mobile", "2 m and 70 cm", 50),
    (r"KG-?805G|KG-?935G|KG-?XS20G|KG-?Q10G", "Wouxun", "KG GMRS handheld", "gmrs", "GMRS", 5),
    (r"KG-?1000G|KG-?XS20G Plus", "Wouxun", "KG-1000G", "gmrs", "GMRS", 50),
    (r"KG-?UV\w*", "Wouxun", "KG-UV", "ht", "2 m and 70 cm", 5),
    (r"MXT-?\d+", "Midland", "MXT GMRS mobile", "gmrs", "GMRS", 40),
    (r"GXT-?\d+|T\d\d?[A-Z]? ?(?:two-way|frs|radio)", "Midland", "FRS/GMRS handheld", "gmrs", "GMRS / FRS", 2),
    (r"RT-?\d+", "Retevis", "RT series", "gmrs", "GMRS / FRS", 5),
    (r"MURS-?V[12]", "BTECH", "MURS-V1/V2", "murs", "MURS", 2),
    (r"Dakota Alert|M538|MURS Alert", "Dakota Alert", "MURS handheld", "murs", "MURS", 2),
    (r"29 ?LTD|29 ?LX|Cobra ?\d+", "Cobra", "CB", "cb", "CB", 4),
    (r"PRO-?5\d+XL|Bearcat ?\d+", "Uniden", "CB", "cb", "CB", 4),
    (r"President ?(?:McKinley|Lincoln|Bill|Randy|Walker|Johnny|Ronald)", "President", "CB", "cb", "CB", 4),
    (r"Galaxy ?DX-?\d+|Stryker ?SR-?\d+", "-", "10 m / 11 m export set", "cb", "CB", 4),
    # ---- antennas: not radios, but gear all the same ----------------------
    # A shelf with the Hamstick tuning sheet, the whip-dipole fact sheet or
    # the Octopus deck on it belongs to somebody with whips, and "HF with a
    # vehicle whip" is a tick about the antenna, not the radio.
    (r"Ham-?sticks?|Hamstiks?|Octopus Antenna|mobile whip", "", "Hamstick whips", "whips", "", 0),
    # ---- not radios ------------------------------------------------------
    (r"NanoVNA|RigExpert|MFJ-?2\d\d|antenna analy[sz]er", "-", "antenna analyser", "test", "", 0),
    (r"Antenna Book|ARRL Handbook|Operating Manual for Radio Amateurs|Handbook", "-", "reference book", "book", "", 0),
]

KIND_WORDS = {
    "ht": "handheld", "mobile": "VHF/UHF mobile", "hf": "HF set", "allmode": "all-mode set",
    "vhf_allmode": "VHF/UHF all-mode set", "gmrs": "GMRS/FRS radio", "murs": "MURS radio",
    "cb": "CB radio", "whips": "mobile whip antennas", "test": "test gear",
    "book": "reference book",
}

# What each kind ticks on Make Contact's "what have you got?" list. A manual
# proves the radio, not the antenna: an HF set is ticked as "HF and room to
# string a wire", the ordinary case, and the operator moves it to the whip
# if the set lives in the car.
KIND_GEAR = {
    "ht": ["ht"], "mobile": ["mobile_vhf"], "hf": ["hf_wire"],
    "allmode": ["hf_wire", "mobile_vhf", "vhf_ssb"], "vhf_allmode": ["mobile_vhf", "vhf_ssb"],
    "gmrs": ["gmrs"], "murs": ["murs"], "cb": ["cb"], "whips": ["hf_mobile"], "test": [], "book": [],
}


def identify(*texts):
    """What radio these words name, or None if the table does not know it."""
    hay = " ".join(str(t or "") for t in texts)
    for pattern, make, model, kind, bands, watts in RIGS:
        # A word boundary before; after, no digit - makers hang a letter on
        # the end for the market (FT5DR, TH-D75A, IC-705 vs IC-705E) and the
        # letter must not hide the model.
        if re.search(r"(?<![A-Za-z0-9])(?:" + pattern + r")(?![0-9])", hay, re.I):
            return {"make": make, "model": model, "kind": kind, "bands": bands,
                    "watts": watts, "word": KIND_WORDS.get(kind, kind)}
    return None


def gear_from(rigs):
    """The Make Contact keys a set of identified radios tick, in list order."""
    out = []
    for rig in rigs:
        for key in KIND_GEAR.get((rig or {}).get("kind"), []):
            if key not in out:
                out.append(key)
    return out


def sentence(rigs):
    """'an FT-991A (all-mode set, HF, 6 m, 2 m, 70 cm, 100 W) and an FT5D
    (handheld, 2 m and 70 cm)' - or '' with nothing to say."""
    radios = [r for r in rigs if r and r["kind"] not in ("test", "book")]
    if not radios:
        return ""
    # Three Hamstick sheets are one set of whips; two FT-991A manuals - the
    # operating and the advanced - are one radio. Said once each.
    seen, once = set(), []
    for r in radios:
        key = (r["make"], r["model"])
        if key not in seen:
            seen.add(key)
            once.append(r)
    parts = []
    for r in once:
        detail = r["word"] + (f", {r['bands']}" if r["bands"] else "") + (f", {r['watts']} W" if r["watts"] else "")
        if not r["make"]:
            # No maker to name: "Hamstick whips (mobile whip antennas)".
            parts.append(f"{r['model']} ({detail})")
            continue
        article = "an" if r["make"][:1].upper() in "AEIOU" else "a"
        parts.append(f"{article} {r['make']} {r['model']} ({detail})")
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]
