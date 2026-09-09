"""What it takes to work the metal, and what stands in for the tool you lack.

Make Contact asks what the operator has on hand and then tells them the
antenna can be built out of what is standing around. That is only half true
until somebody counts the tools, because a fence you cannot cut and a tube you
cannot join is scenery rather than an antenna. So this is the third inventory,
and it is improvisable in exactly the way the second one is: every operation
below has the tool it wants, and then the things people actually reach for
when that tool is forty miles away.

Two things are worth knowing before any of it, and they are the reason this
module exists rather than a list of hardware.

**The joint is the part that fails.** Not the wire. When a scavenged antenna
goes intermittent, or the SWR wanders while the wind blows, or the radio makes
signals that are not on the air, it is a joint every time. Metal is forgiving
and joints are not.

**A tight mechanical joint is not a compromise.** At HF and VHF a bolted or
clamped joint, cleaned to bright metal and kept dry, is electrically as good
as a soldered one - which is worth saying because the instinct in a field
expedient is to reach for heat. Look at any commercial beam: every element
joint on it is a clamp, chosen by people who could have welded it.

That is also the honest answer to the question this module was written for.
You can make a welder out of a vehicle - `ARC` says how and what it costs -
and for an antenna you almost never want to, because the joint you actually
need is one you can undo, redo and test with cold hands.
"""

# The operations, in the order somebody meets them. `first` is the tool the
# job wants; `instead` is what has stood in for it, roughly best to worst.
OPERATIONS = [
    {
        "key": "cut",
        "title": "Cut it to length",
        "first": "Side cutters, a hacksaw, tin snips",
        "instead": [
            "a bare hacksaw blade with a rag wrapped round one end - the "
            "frame is a convenience, not the tool",
            "fatigue: nick the spot with a file or a sharp stone, then bend "
            "it back and forth, hard and tight and always in the same place, "
            "until the crack that starts at the nick runs through",
            "anything that will hold one half while you work the other - a "
            "door shut on it at the hinge side, a vice, two rocks, the gap "
            "in a fence post. The leverage is what keeps the bend tight and "
            "in one spot, which is the whole trick",
            "a cold chisel, or any hard edge and a rock",
        ],
        "why": "Length is the dimension that decides whether the thing "
               "resonates, and it is the only one you cannot add back. Cut "
               "long, measure, trim. Nobody has ever regretted a wire that "
               "started too long.",
        "aside": {
            "title": "Fatigue - what takes airliners apart, run on purpose",
            "body": [
                "Bending metal at one spot does two things at once. It work-"
                "hardens: dislocations pile up, and the metal gets harder and "
                "less willing to deform. And it starts a fatigue crack at the "
                "outer fibre of the bend, which grows a little on every cycle "
                "until what is left cannot carry the load.",

                "That is not a curiosity. It took the roof off Aloha 243 in "
                "1988 after tens of thousands of short pressurisation cycles, "
                "and it broke two Comets apart at altitude in 1954. The "
                "Comets are worth being accurate about, because the version "
                "everybody repeats - square windows - is the tidied-up one. "
                "The crack on the first aircraft was traced to a rivet hole "
                "near the corner of a cutout in the roof. It was a small flaw "
                "at a place where the stress was already concentrated, which "
                "is what a fatigue crack always needs and is the only part of "
                "the story a person with a coat hanger has to remember.",

                "So that is the instruction. The nick you file is the rivet "
                "hole: it decides where the break happens instead of leaving "
                "it to chance. Bend hard and tight rather than gently, "
                "because a wide curve spreads the strain over a length and "
                "will never crack, and keep every cycle in the same place. "
                "Ten or twenty of them do what thousands of pressurisations "
                "did.",

                "Two things follow. It only works on stock you can genuinely "
                "work by hand - wire, a coat hanger, thin soft tube - and "
                "never on half-inch pipe, which is what a saw is for. And the "
                "end it leaves is hardened and brittle: file it back before "
                "it becomes a joint, and bend any hook or eye you need "
                "somewhere else along the wire, because that spot will not "
                "take another bend.",
            ],
        },
    },
    {
        "key": "join",
        "title": "Join it, and to the feedline",
        "first": "A soldering iron for wire, a propane torch for pipe",
        "instead": [
            "a proper twisted splice - a Western Union joint carries RF "
            "perfectly well unsoldered, and always did",
            "a bolt, a washer either side and a nut, through two drilled or "
            "punched holes",
            "hose clamps, which are already holding every heater hose in "
            "the vehicle and grip tube beautifully",
            "self-tapping screws into conduit or thin tube",
            "a butane lighter for small copper - it will melt solder, "
            "slowly, and a camp stove will do better",
        ],
        "why": "This is where scavenged antennas die. Clean every mating "
               "face to bright metal first: paint, zinc, anodising and "
               "varnish are all insulators, and a corroded joint can read "
               "like a short on a meter and still rectify at RF - the rusty "
               "bolt effect, which invents spurious signals out of nothing.",
    },
    {
        "key": "hold",
        "title": "Get it up and hold it there",
        "first": "A mast, halyard, insulators and something to tie to",
        "instead": [
            "a rock on a line thrown over a branch - a water bottle throws "
            "further and does not stick in the tree",
            "a fishing rod and reel, which is the neatest launcher there is, "
            "or a slingshot if somebody has one",
            "a bottle neck, a pen barrel or a length of dry rope as an "
            "insulator at each end",
            "the vehicle itself as one anchor, a fence post as the other",
        ],
        "why": "Height and a clear horizon do more than power at VHF, and on "
               "HF the ground under a low wire is part of the antenna. "
               "Getting a mediocre conductor eight feet higher beats "
               "improving the conductor.",
    },
    {
        "key": "check",
        "title": "Find out whether it works",
        "first": "A NanoVNA, or an SWR meter",
        "instead": [
            "the radio's own reflected-power reading, if it has one",
            "listening: a resonant antenna is loud on receive, and a badly "
            "wrong one is quiet in a way you can hear",
            "cutting long and trimming in small steps while somebody "
            "reports on you, which is how it was done for fifty years",
        ],
        "why": "A VNA answers which way to cut, because it gives the "
               "reactance with its sign. Everything else answers only how "
               "bad it is - useful, but it will not tell a long antenna "
               "from a short one, and both read high.",
    },
]

# The MacGyver end of the tool inventory, which is real and is also the place
# where somebody gets hurt. It is stated in full rather than hinted at,
# because the half-remembered version of this is the dangerous one.
ARC = {
    "title": "And yes - the vehicle is also a welder",
    "it_works": "Two or three car batteries in series give 24 or 36 volts, "
                "and with heavy jumper cables and a welding rod that will "
                "strike and hold an arc. It is a documented field expedient "
                "and it does work.",
    "dangers": [
        "A lead-acid battery vents hydrogen, and a spark at the post can "
        "burst the case and throw acid. Make your connections away from the "
        "batteries, and never the last one at a terminal.",
        "Arc flash burns the cornea in seconds and you will not feel it for "
        "hours. Sunglasses are not eye protection - a welding lens is.",
        "Cheap jumper cables get hot enough to burn through their own "
        "insulation at these currents.",
        "Galvanised steel gives off zinc fumes when it is burned, and metal "
        "fume fever is a real illness. Grind the coating off, or stay out "
        "of the smoke.",
        "That battery is what starts the vehicle you intend to leave in.",
    ],
    "but": "For an antenna, though, this is the wrong instinct dressed up as "
           "resourcefulness. A bolted joint cleaned to bright metal is as "
           "good electrically, can be undone when the first attempt is the "
           "wrong length, and asks nothing of you but a spanner.",
}


def ladder():
    """The operations, for a page that is asking what the operator can do."""
    return OPERATIONS
