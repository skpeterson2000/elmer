"""The ground, once: every soil's permittivity and conductivity, and where
each figure comes from.

The antenna patterns reflect off it, the ground wave runs along it, and the
Lab rates the ground under a station from the surveys. Each kept its own
table, and the tables had drifted: "poor" was one soil in the patterns and
another in the ground wave, and sea water had a permittivity that was nobody's
figure. Now everything that needs the ground asks here.

The figures are ITU-R P.527-6 (09/2021), Attachment to Annex 1, Figure 24
(reproduced from Fig. 1 of P.527-3), read at HF, where each curve is flat,
wherever that figure gives the soil. It is the table ITU-R P.368's ground-wave
curves are drawn for. Two are not P.527's, and say so:

  - "average" is the textbook default, σ = 0.005 S/m and εr = 13, the
    "average ground" of the antenna books. It is not one of P.527's curves;
    it sits between wet ground and medium dry. It stays because it is what
    every book and every modeling program means by average, and what an
    operator who has not rated their ground should get.
  - "city" is the textbook figure for built-up ground, σ = 0.001 S/m and
    εr = 5. P.527 has no curve for it.

"good" is the patterns' old name for the best ordinary ground, "rich
farmland, marsh". That is P.527's wet ground, and it reads wet's figures.

Ice is read by eye from Figure 24's two curves for fresh-water ice (−1 °C and
−10 °C), which run between about 3e-5 and 1e-4 S/m across HF. The others are
read from flat curves on labeled grid lines.
"""

P527 = "ITU-R P.527-6 (09/2021), Attachment to Annex 1, Figure 24"

# epsilon: relative permittivity. sigma: conductivity, siemens per meter.
SOILS = {
    "sea": {"epsilon": 70.0, "sigma": 5.0,
            "label": "Sea water",
            "source": P527 + ", curve A: sea water, average salinity, 20 °C",
            "note": "The best ground there is. Coastal stations get ground "
                    "wave ranges inland stations never see."},
    "fresh": {"epsilon": 80.0, "sigma": 0.003,
              "label": "Fresh water",
              "source": P527 + ", curve C: fresh water, 20 °C",
              "note": "High permittivity, poor conductivity - a lake is not "
                      "the sea and does not behave like it."},
    "wet": {"epsilon": 30.0, "sigma": 0.01,
            "label": "Wet ground, marsh",
            "source": P527 + ", curve B: wet ground",
            "note": "Rich damp soil, bog, irrigated land. The best ordinary "
                    "ground and worth siting for."},
    "average": {"epsilon": 13.0, "sigma": 0.005,
                "label": "Average ground",
                "source": "the textbook default, not one of P.527's curves; "
                          "it sits between P.527's wet ground and medium dry",
                "note": "The default in every textbook and the right guess "
                        "for ordinary farmland and pasture."},
    "poor": {"epsilon": 15.0, "sigma": 0.001,
             "label": "Poor ground, medium dry",
             "source": P527 + ", curve D: medium dry ground",
             "note": "Hills, rock, sandy loam. Common and quietly costly."},
    "sand": {"epsilon": 3.0, "sigma": 0.0001,
             "label": "Dry sand, desert",
             "source": P527 + ", curve E: very dry ground",
             "note": "Close to an insulator. A ground wave dies fast on it, "
                     "and radials matter more here than anywhere."},
    "city": {"epsilon": 5.0, "sigma": 0.001,
             "label": "City, industrial",
             "source": "the textbook figure for built-up ground; P.527 has "
                       "no curve for it",
             "note": "Buildings and dry fill. Poor ground and a high noise "
                     "floor arriving together."},
    "ice": {"epsilon": 3.0, "sigma": 5e-5,
            "label": "Ice, frozen ground",
            "source": P527 + ", curve G: fresh-water ice, between the -1 °C "
                             "and -10 °C curves across HF, read by eye",
            "note": "Frozen soil conducts far worse than the same soil thawed "
                    "- a winter ground wave is shorter than a summer one."},
}

# Other names a caller may use for a soil in the table.
ALIASES = {"good": "wet"}

DEFAULT = "average"


def soil(name):
    """The table's entry for this ground, by name or alias; None for
    "perfect" and for a name the table does not know."""
    return SOILS.get(ALIASES.get(name, name))


def constants(name):
    """(epsilon_r, sigma) for this ground, or None for "perfect" and for a
    name the table does not know."""
    s = soil(name)
    return (s["epsilon"], s["sigma"]) if s else None
