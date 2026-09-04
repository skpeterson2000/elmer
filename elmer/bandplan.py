"""US amateur band plan: what the law allows, and what convention puts there.

Three layers, kept apart because they carry very different authority:

* **Privileges** are law - 47 CFR 97.301 and 97.305. Transmitting outside your
  class's segment is a violation, so these are stated exactly.
* **Activity** is convention. Nothing here is enforceable; it is what operators
  have agreed to expect where, and ignoring it makes you the problem rather
  than a criminal.
* **Regional** plans come from the local frequency coordinator and are fetched
  live rather than bundled, since they are somebody else's work and they change.

Frequencies are MHz throughout.
"""

CLASSES = ["Novice", "Technician", "General", "Advanced", "Extra"]
CLASS_RANK = {name: n for n, name in enumerate(CLASSES)}

# Activity kinds drive the colouring; the order here is the legend order.
KINDS = [
    ("cw", "CW"),
    ("digital", "Digital / data"),
    ("phone", "Phone"),
    ("image", "Image / SSTV"),
    ("beacon", "Beacons"),
    ("satellite", "Satellite"),
    ("repeater", "Repeaters"),
    ("simplex", "FM simplex"),
    ("calling", "Calling frequency"),
    ("special", "Special use"),
]

# --- 47 CFR 97.301 / 97.305: what each class may transmit, and with what ----
# Each entry: (low, high, modes) where modes is a short legal description.
PRIVILEGES = {
    "160 m": {
        "Novice": [], "Technician": [],
        "General": [(1.800, 2.000, "CW, phone, image, RTTY/data")],
        "Advanced": [(1.800, 2.000, "CW, phone, image, RTTY/data")],
        "Extra": [(1.800, 2.000, "CW, phone, image, RTTY/data")],
    },
    "80 m": {
        "Novice": [(3.525, 3.600, "CW only")],
        "Technician": [(3.525, 3.600, "CW only")],
        "General": [(3.525, 3.600, "CW, RTTY/data"), (3.800, 4.000, "CW, phone, image")],
        "Advanced": [(3.525, 3.600, "CW, RTTY/data"), (3.700, 4.000, "CW, phone, image")],
        "Extra": [(3.500, 3.600, "CW, RTTY/data"), (3.600, 4.000, "CW, phone, image")],
    },
    "60 m": {
        "Novice": [], "Technician": [],
        "General": [(5.3305, 5.4065, "5 channels, USB/CW/data, 100 W ERP")],
        "Advanced": [(5.3305, 5.4065, "5 channels, USB/CW/data, 100 W ERP")],
        "Extra": [(5.3305, 5.4065, "5 channels, USB/CW/data, 100 W ERP")],
    },
    "40 m": {
        "Novice": [(7.025, 7.125, "CW only")],
        "Technician": [(7.025, 7.125, "CW only")],
        "General": [(7.025, 7.125, "CW, RTTY/data"), (7.175, 7.300, "CW, phone, image")],
        "Advanced": [(7.025, 7.125, "CW, RTTY/data"), (7.125, 7.300, "CW, phone, image")],
        "Extra": [(7.000, 7.125, "CW, RTTY/data"), (7.125, 7.300, "CW, phone, image")],
    },
    "30 m": {
        "Novice": [], "Technician": [],
        "General": [(10.100, 10.150, "CW, RTTY/data only, 200 W PEP")],
        "Advanced": [(10.100, 10.150, "CW, RTTY/data only, 200 W PEP")],
        "Extra": [(10.100, 10.150, "CW, RTTY/data only, 200 W PEP")],
    },
    "20 m": {
        "Novice": [], "Technician": [],
        "General": [(14.025, 14.150, "CW, RTTY/data"), (14.225, 14.350, "CW, phone, image")],
        "Advanced": [(14.025, 14.150, "CW, RTTY/data"), (14.175, 14.350, "CW, phone, image")],
        "Extra": [(14.000, 14.150, "CW, RTTY/data"), (14.150, 14.350, "CW, phone, image")],
    },
    "17 m": {
        "Novice": [], "Technician": [],
        "General": [(18.068, 18.110, "CW, RTTY/data"), (18.110, 18.168, "CW, phone, image")],
        "Advanced": [(18.068, 18.110, "CW, RTTY/data"), (18.110, 18.168, "CW, phone, image")],
        "Extra": [(18.068, 18.110, "CW, RTTY/data"), (18.110, 18.168, "CW, phone, image")],
    },
    "15 m": {
        "Novice": [(21.025, 21.200, "CW only")],
        "Technician": [(21.025, 21.200, "CW only")],
        "General": [(21.025, 21.200, "CW, RTTY/data"), (21.275, 21.450, "CW, phone, image")],
        "Advanced": [(21.025, 21.200, "CW, RTTY/data"), (21.225, 21.450, "CW, phone, image")],
        "Extra": [(21.000, 21.200, "CW, RTTY/data"), (21.200, 21.450, "CW, phone, image")],
    },
    "12 m": {
        "Novice": [], "Technician": [],
        "General": [(24.890, 24.930, "CW, RTTY/data"), (24.930, 24.990, "CW, phone, image")],
        "Advanced": [(24.890, 24.930, "CW, RTTY/data"), (24.930, 24.990, "CW, phone, image")],
        "Extra": [(24.890, 24.930, "CW, RTTY/data"), (24.930, 24.990, "CW, phone, image")],
    },
    "10 m": {
        "Novice": [(28.000, 28.300, "CW, RTTY/data, 200 W PEP"),
                   (28.300, 28.500, "CW, phone, 200 W PEP")],
        "Technician": [(28.000, 28.300, "CW, RTTY/data"), (28.300, 28.500, "CW, phone")],
        "General": [(28.000, 28.300, "CW, RTTY/data"), (28.300, 29.700, "CW, phone, image")],
        "Advanced": [(28.000, 28.300, "CW, RTTY/data"), (28.300, 29.700, "CW, phone, image")],
        "Extra": [(28.000, 28.300, "CW, RTTY/data"), (28.300, 29.700, "CW, phone, image")],
    },
    "6 m": {"Novice": [], **{c: [(50.0, 50.1, "CW only"),
                                 (50.1, 54.0, "CW, phone, image, RTTY/data")]
                             for c in ("Technician", "General", "Advanced", "Extra")}},
    "2 m": {"Novice": [], **{c: [(144.0, 144.1, "CW only"),
                                 (144.1, 148.0, "CW, phone, image, RTTY/data")]
                             for c in ("Technician", "General", "Advanced", "Extra")}},
    "1.25 m": {"Novice": [(222.0, 225.0, "CW, phone, image, RTTY/data, 25 W PEP")],
               **{c: [(222.0, 225.0, "CW, phone, image, RTTY/data")]
                  for c in ("Technician", "General", "Advanced", "Extra")}},
    "70 cm": {"Novice": [], **{c: [(420.0, 450.0, "CW, phone, image, RTTY/data")]
                               for c in ("Technician", "General", "Advanced", "Extra")}},
    "33 cm": {"Novice": [], **{c: [(902.0, 928.0, "CW, phone, image, RTTY/data")]
                               for c in ("Technician", "General", "Advanced", "Extra")}},
    "23 cm": {"Novice": [(1270.0, 1295.0, "CW, phone, image, RTTY/data, 5 W PEP")],
              **{c: [(1240.0, 1300.0, "CW, phone, image, RTTY/data")]
                 for c in ("Technician", "General", "Advanced", "Extra")}},
}

BANDS = [
    {"name": "160 m", "low": 1.800, "high": 2.000, "group": "HF"},
    {"name": "80 m", "low": 3.500, "high": 4.000, "group": "HF"},
    {"name": "60 m", "low": 5.330, "high": 5.407, "group": "HF", "channelised": True},
    {"name": "40 m", "low": 7.000, "high": 7.300, "group": "HF"},
    {"name": "30 m", "low": 10.100, "high": 10.150, "group": "HF"},
    {"name": "20 m", "low": 14.000, "high": 14.350, "group": "HF"},
    {"name": "17 m", "low": 18.068, "high": 18.168, "group": "HF"},
    {"name": "15 m", "low": 21.000, "high": 21.450, "group": "HF"},
    {"name": "12 m", "low": 24.890, "high": 24.990, "group": "HF"},
    {"name": "10 m", "low": 28.000, "high": 29.700, "group": "HF"},
    {"name": "6 m", "low": 50.000, "high": 54.000, "group": "VHF"},
    {"name": "2 m", "low": 144.000, "high": 148.000, "group": "VHF"},
    {"name": "1.25 m", "low": 222.000, "high": 225.000, "group": "VHF"},
    {"name": "70 cm", "low": 420.000, "high": 450.000, "group": "UHF"},
    {"name": "33 cm", "low": 902.000, "high": 928.000, "group": "UHF"},
    {"name": "23 cm", "low": 1240.000, "high": 1300.000, "group": "UHF"},
]
BAND_INDEX = {b["name"]: b for b in BANDS}

# The 60 m channels are fixed, not a band segment (47 CFR 97.303(h)).
CHANNELS_60M = [
    (5.3305, "Channel 1"), (5.3465, "Channel 2"), (5.3570, "Channel 3"),
    (5.3715, "Channel 4"), (5.4035, "Channel 5"),
]


def privileges_for(band_name, licence_class):
    return PRIVILEGES.get(band_name, {}).get(licence_class, [])


def may_transmit(band_name, licence_class, mhz):
    """Whether this class may transmit on this frequency, and under what terms."""
    for low, high, modes in privileges_for(band_name, licence_class):
        if low <= mhz <= high:
            return True, modes
    return False, None


def gaps_for(band_name, licence_class):
    """Portions of a band this class may NOT use, as (low, high) pairs."""
    band = BAND_INDEX.get(band_name)
    if not band:
        return []
    allowed = sorted(privileges_for(band_name, licence_class))
    gaps, cursor = [], band["low"]
    for low, high, _ in allowed:
        if low > cursor:
            gaps.append((cursor, low))
        cursor = max(cursor, high)
    if cursor < band["high"]:
        gaps.append((cursor, band["high"]))
    return gaps


# --- Convention, not law ----------------------------------------------------
# What operators have agreed to expect where. Nothing here is enforceable, but
# a signal in the wrong place is still antisocial. Entries are
# (low, high, kind, label); a point frequency repeats it as low and high.
ACTIVITY = {
    "160 m": [
        (1.800, 1.810, "digital", "Digital modes"),
        (1.810, 1.810, "calling", "CW QRP calling"),
        (1.810, 1.843, "cw", "CW"),
        (1.840, 1.845, "digital", "FT8 and weak-signal digital"),
        (1.843, 2.000, "phone", "SSB, SSTV and other wideband modes"),
        (1.910, 1.910, "calling", "SSB QRP calling"),
        (1.995, 2.000, "special", "Experimental"),
    ],
    "80 m": [
        (3.500, 3.510, "cw", "CW DX window"),
        (3.510, 3.560, "cw", "CW"),
        (3.560, 3.560, "calling", "CW QRP calling"),
        (3.570, 3.600, "digital", "Digital modes"),
        (3.573, 3.573, "calling", "FT8"),
        (3.590, 3.590, "digital", "RTTY DX"),
        (3.600, 3.790, "phone", "SSB"),
        (3.790, 3.800, "phone", "DX window"),
        (3.845, 3.845, "image", "SSTV"),
        (3.885, 3.885, "phone", "AM calling"),
    ],
    "60 m": [
        (5.3305, 5.4065, "special", "Five fixed channels, USB, 2.8 kHz, 100 W ERP"),
    ],
    "40 m": [
        (7.000, 7.040, "cw", "CW, DX at the bottom"),
        (7.040, 7.040, "calling", "CW QRP calling"),
        (7.040, 7.070, "cw", "CW"),
        (7.070, 7.125, "digital", "Digital modes"),
        (7.074, 7.074, "calling", "FT8"),
        (7.125, 7.171, "phone", "SSB"),
        (7.171, 7.171, "image", "SSTV"),
        (7.171, 7.290, "phone", "SSB"),
        (7.290, 7.290, "phone", "AM calling"),
    ],
    "30 m": [
        (10.100, 10.130, "cw", "CW"),
        (10.130, 10.140, "digital", "RTTY"),
        (10.136, 10.136, "calling", "FT8"),
        (10.140, 10.150, "digital", "Unattended digital"),
    ],
    "20 m": [
        (14.000, 14.060, "cw", "CW, DX at the bottom"),
        (14.060, 14.060, "calling", "CW QRP calling"),
        (14.060, 14.070, "cw", "CW"),
        (14.070, 14.095, "digital", "Digital modes"),
        (14.074, 14.074, "calling", "FT8"),
        (14.095, 14.0995, "digital", "Unattended digital"),
        (14.100, 14.100, "beacon", "NCDXF/IARU international beacons"),
        (14.1005, 14.112, "digital", "Unattended digital"),
        (14.112, 14.230, "phone", "SSB"),
        (14.230, 14.230, "image", "SSTV"),
        (14.230, 14.286, "phone", "SSB"),
        (14.286, 14.286, "phone", "AM calling"),
        (14.286, 14.350, "phone", "SSB"),
    ],
    "17 m": [
        (18.068, 18.100, "cw", "CW"),
        (18.096, 18.096, "calling", "CW QRP calling"),
        (18.100, 18.110, "digital", "Digital modes"),
        (18.100, 18.100, "calling", "FT8"),
        (18.110, 18.110, "beacon", "IBP beacons"),
        (18.110, 18.168, "phone", "SSB"),
        (18.130, 18.130, "calling", "SSB QRP calling"),
    ],
    "15 m": [
        (21.000, 21.060, "cw", "CW, DX at the bottom"),
        (21.060, 21.060, "calling", "CW QRP calling"),
        (21.060, 21.070, "cw", "CW"),
        (21.070, 21.110, "digital", "Digital modes"),
        (21.074, 21.074, "calling", "FT8"),
        (21.110, 21.150, "digital", "Unattended digital"),
        (21.150, 21.150, "beacon", "IBP beacons"),
        (21.151, 21.340, "phone", "SSB"),
        (21.340, 21.340, "image", "SSTV"),
        (21.340, 21.450, "phone", "SSB"),
        (21.385, 21.385, "calling", "SSB QRP calling"),
    ],
    "12 m": [
        (24.890, 24.920, "cw", "CW"),
        (24.906, 24.906, "calling", "CW QRP calling"),
        (24.920, 24.925, "digital", "Digital modes"),
        (24.915, 24.915, "calling", "FT8"),
        (24.930, 24.930, "beacon", "IBP beacons"),
        (24.931, 24.990, "phone", "SSB"),
    ],
    "10 m": [
        (28.000, 28.060, "cw", "CW"),
        (28.060, 28.060, "calling", "CW QRP calling"),
        (28.070, 28.120, "digital", "Digital modes"),
        (28.074, 28.074, "calling", "FT8"),
        (28.120, 28.189, "digital", "Unattended digital"),
        (28.190, 28.225, "beacon", "Beacons"),
        (28.200, 28.200, "beacon", "IBP beacons"),
        (28.300, 28.680, "phone", "SSB"),
        (28.385, 28.385, "calling", "SSB QRP calling"),
        (28.680, 28.680, "image", "SSTV"),
        (28.680, 29.000, "phone", "SSB"),
        (29.000, 29.200, "phone", "AM"),
        (29.300, 29.510, "satellite", "Satellite downlinks"),
        (29.520, 29.590, "repeater", "FM repeater inputs"),
        (29.600, 29.600, "calling", "FM simplex calling"),
        (29.620, 29.680, "repeater", "FM repeater outputs"),
    ],
    "6 m": [
        (50.000, 50.100, "cw", "CW and beacons"),
        (50.060, 50.080, "beacon", "Beacon sub-band"),
        (50.100, 50.125, "phone", "DX window, SSB and CW"),
        (50.125, 50.125, "calling", "SSB calling"),
        (50.125, 50.300, "phone", "SSB"),
        (50.300, 50.600, "digital", "All modes, digital and weak signal"),
        (50.313, 50.313, "calling", "FT8"),
        (50.600, 50.800, "digital", "Non-voice, RTTY and data"),
        (51.000, 51.100, "phone", "Pacific DX window"),
        (51.120, 51.980, "repeater", "FM repeaters"),
        (52.000, 52.525, "simplex", "FM simplex and repeaters"),
        (52.525, 52.525, "calling", "FM simplex calling"),
        (52.525, 54.000, "repeater", "FM repeaters and simplex"),
    ],
    "2 m": [
        (144.000, 144.050, "cw", "EME, CW"),
        (144.050, 144.100, "cw", "General CW and weak signal"),
        (144.100, 144.200, "cw", "EME and weak-signal SSB"),
        (144.200, 144.200, "calling", "SSB calling"),
        (144.200, 144.275, "phone", "General SSB"),
        (144.275, 144.300, "beacon", "Propagation beacons"),
        (144.300, 144.500, "satellite", "Satellite"),
        (144.500, 144.600, "satellite", "Linear translator inputs"),
        (144.600, 144.900, "repeater", "FM repeater inputs"),
        (144.900, 145.100, "digital", "Weak signal, packet and FM simplex"),
        (145.100, 145.200, "satellite", "Linear translator outputs"),
        (145.200, 145.500, "repeater", "FM repeater outputs"),
        (145.500, 145.800, "digital", "Packet, miscellaneous, experimental"),
        (145.800, 146.000, "satellite", "Satellite"),
        (146.010, 146.400, "repeater", "FM repeater inputs"),
        (146.400, 146.580, "simplex", "FM simplex"),
        (146.520, 146.520, "calling", "FM national simplex calling"),
        (146.610, 147.390, "repeater", "FM repeaters"),
        (147.420, 147.570, "simplex", "FM simplex"),
        (147.600, 147.990, "repeater", "FM repeater inputs"),
    ],
    "1.25 m": [
        (222.000, 222.150, "cw", "Weak signal, EME and CW"),
        (222.100, 222.100, "calling", "SSB and CW calling"),
        (222.150, 222.250, "phone", "Weak signal SSB"),
        (222.250, 223.380, "repeater", "FM repeaters"),
        (223.400, 223.520, "simplex", "FM simplex"),
        (223.500, 223.500, "calling", "FM simplex calling"),
        (223.520, 223.640, "digital", "Digital and packet"),
        (223.640, 225.000, "repeater", "FM repeaters and links"),
    ],
    "70 cm": [
        (420.000, 426.000, "image", "ATV repeater outputs"),
        (426.000, 432.000, "image", "ATV simplex"),
        (432.000, 432.070, "cw", "EME"),
        (432.070, 432.100, "cw", "Weak signal CW"),
        (432.100, 432.100, "calling", "SSB and CW calling"),
        (432.100, 432.300, "phone", "Weak signal SSB"),
        (432.300, 432.400, "beacon", "Propagation beacons"),
        (432.400, 433.000, "phone", "Mixed mode weak signal"),
        (435.000, 438.000, "satellite", "Satellite"),
        (438.000, 444.000, "image", "ATV repeater inputs and links"),
        (442.000, 445.000, "repeater", "FM repeaters"),
        (446.000, 446.000, "calling", "FM simplex calling"),
        (446.000, 447.000, "simplex", "FM simplex"),
        (447.000, 450.000, "repeater", "FM repeaters"),
    ],
    "33 cm": [
        (902.000, 902.800, "cw", "Weak signal and EME"),
        (902.100, 902.100, "calling", "SSB and CW calling"),
        (903.000, 906.000, "digital", "Digital, mixed modes"),
        (906.000, 909.000, "repeater", "FM repeater inputs"),
        (909.000, 915.000, "image", "ATV"),
        (918.000, 921.000, "repeater", "FM repeater outputs"),
        (921.000, 928.000, "image", "ATV and mixed modes"),
    ],
    "23 cm": [
        (1240.000, 1246.000, "image", "ATV channel 1"),
        (1246.000, 1252.000, "digital", "Digital and links"),
        (1252.000, 1258.000, "image", "ATV channel 2"),
        (1258.000, 1260.000, "digital", "Digital"),
        (1260.000, 1270.000, "satellite", "Satellite uplinks"),
        (1270.000, 1276.000, "repeater", "FM repeater inputs"),
        (1276.000, 1282.000, "image", "ATV channel 3"),
        (1282.000, 1288.000, "repeater", "FM repeater outputs"),
        (1288.000, 1294.000, "digital", "Broadband experimental"),
        (1294.000, 1295.000, "simplex", "FM simplex"),
        (1294.500, 1294.500, "calling", "FM simplex calling"),
        (1295.000, 1297.000, "digital", "Narrow band, mixed modes"),
        (1296.100, 1296.100, "calling", "SSB and CW calling, EME"),
        (1297.000, 1300.000, "digital", "Digital and links"),
    ],
}


def activity_for(band_name):
    return ACTIVITY.get(band_name, [])
