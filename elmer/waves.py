"""Radio waves, explained as the sound waves you already know.

Different medium, same game - and mostly the same equations with a different
constant in them. Light travels 874,000 times faster than sound, so a radio
wave and a sound wave of the same *size* are that far apart in pitch. Put a
radio band into air and it comes out as a note:

    160m   157.8 m across   2.2 Hz   below hearing
     10m    10.6 m         32.5 Hz   the note that comes through a wall
      2m     2.1 m        165.9 Hz   a bass guitar
    70cm     0.7 m        510.3 Hz   where words become audible

Which is a fact everybody has already learned without being taught. Two streets
away you hear the bass from a car and none of the tune, because the long waves
bend around the houses and the short ones do not. That is 160m and 70cm, and it
is the same physics both times: a wave bends around anything smaller than
itself and is stopped by anything bigger.

The analogy is not decoration. Diffraction, resonance, Q and bandwidth,
impedance matching, standing waves and dipole cancellation are the same
mathematics in both media, and a speaker is easier to picture than an antenna
because you have stood in front of one. Where it breaks, it is said plainly -
see MISMATCHES. A tool that lets a good analogy quietly carry somebody past its
own edge has taught them something they will have to unlearn.
"""
import math

C = 299792458.0          # metres per second
SOUND = 343.0            # metres per second in air at 20 C
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
HEARING = (20.0, 20000.0)


def wavelength_m(mhz):
    return C / (float(mhz) * 1e6)


def as_sound(mhz):
    """The audible note of the same size as this radio wave, in air."""
    return SOUND / wavelength_m(mhz)


def note_name(hz):
    """The nearest musical note, or None below the bottom of a piano."""
    if hz < 16.0:
        return None
    steps = round(12 * math.log2(hz / 440.0) + 69)
    return "%s%d" % (NOTE_NAMES[int(steps) % 12], int(steps) // 12 - 1)


# What that pitch is, in things somebody has actually heard.
def sounds_like(hz):
    if hz < 20:
        return ("below hearing", "You would feel this rather than hear it - "
                "the pressure in your chest at a concert, not a note. Nothing "
                "in a room is big enough to stop a wave this size.")
    if hz < 60:
        return ("a subwoofer", "The note that comes through a wall from the "
                "next room while the tune does not. It bends around the "
                "building because the building is smaller than the wave.")
    if hz < 250:
        return ("a bass guitar", "Low, and it still gets around corners, but "
                "you are starting to be able to point at where it came from.")
    if hz < 1000:
        return ("the middle of a voice", "Where words become audible. It "
                "travels in straight lines, and putting a hand in front of "
                "your mouth muffles it - a hand is now big enough to matter.")
    return ("high and directional", "Sharp, easy to locate, and stopped by "
            "almost anything. You know exactly which direction it came from "
            "and it does not reach round the corner at all.")


# Roughly how big an obstacle has to be before a wave notices it. Well under a
# wavelength and the wave closes back up behind it as though it were not there;
# well over, and there is a shadow.
def meets(mhz, obstacle_m):
    """What this wave does when it meets something this size."""
    lam = wavelength_m(mhz)
    ratio = float(obstacle_m) / lam
    if ratio < 0.25:
        return {"ratio": ratio, "verdict": "goes straight round it",
                "note": "The obstacle is a fraction of a wavelength, so the "
                        "wave closes up behind it and carries on as though it "
                        "were not there."}
    if ratio < 1.5:
        return {"ratio": ratio, "verdict": "bends round it, weakened",
                "note": "Comparable in size, so some gets round and some is "
                        "blocked. This is the messy middle where a hill costs "
                        "you signal without hiding you."}
    return {"ratio": ratio, "verdict": "casts a shadow",
            "note": "Much bigger than the wave, so there is a genuine shadow "
                    "behind it. This is why line of sight starts to mean what "
                    "it says as the frequency climbs."}


# Where the analogy is exact, and worth leaning on.
PARALLELS = [
    ("Size against the obstacle",
     "Bass gets round a building and treble does not, because a wave bends "
     "around anything smaller than itself. That is the same sentence as 160m "
     "reaching into a valley while 70cm leaves a shadow behind the ridge."),
    ("A speaker with no box",
     "A bare driver pushes air forward and pulls it back at the same moment, "
     "so at low frequencies the two wrap round and cancel - which is why it "
     "needs a baffle. A horizontal antenna does exactly this against its own "
     "reflection in the ground, and it is why a horizontal antenna has no "
     "ground wave worth the name."),
    ("A horn is a matching transformer",
     "A horn does not amplify. It matches the high impedance of a small "
     "driver to the low impedance of open air, so more of the power leaves "
     "instead of reflecting. That is precisely what an antenna does between a "
     "feedline and the 377 ohms of free space."),
    ("Damping is bandwidth",
     "A sharply resonant driver rings on one note; a damped one covers a wide "
     "range less loudly. A thin wire antenna is sharp and a fat one is broad, "
     "for the same reason and by the same arithmetic. Q is Q."),
    ("Standing waves in a pipe",
     "An organ pipe open at the end reflects sound back down itself and sets "
     "up a standing wave. An unterminated feedline does the same with RF, and "
     "SWR is the measure of it."),
    ("Warm air overhead bends sound back down",
     "On a still night a temperature inversion refracts sound back to the "
     "ground and you hear a train from miles away. The ionosphere does the "
     "same thing to HF, for the same reason: a gradient in the medium bends "
     "the wave back instead of letting it escape."),
]

# And where it does not hold. These matter more than the parallels, because an
# analogy is dangerous exactly where somebody has stopped checking it.
MISMATCHES = [
    ("Sound has no polarisation",
     "Sound is a pressure wave - a push and a pull along the direction of "
     "travel, with nothing to orient. Radio is transverse and has a direction "
     "of vibration, which is why a horizontal antenna hearing a vertical one "
     "loses about 20 dB. There is no such thing as a sideways loudspeaker, so "
     "the single most expensive mistake in VHF has no acoustic counterpart at "
     "all."),
    ("Absorption runs the other way",
     "Air absorbs treble, which is why distant thunder is a rumble and why "
     "you lose the cymbals before the bass. The D layer does the opposite: it "
     "absorbs the *low* bands hardest, which is why 80m is a local band at "
     "noon while 20m sails over it. The intuition about diffraction carries; "
     "the intuition about what fades does not."),
    ("Sound needs something to travel in",
     "Take the air away and sound stops. Radio does not need a medium at all, "
     "which is the whole reason a signal reaches a satellite."),
]


def describe(mhz, obstacle_m=None):
    """A radio frequency, put into terms somebody has heard."""
    mhz = float(mhz)
    lam = wavelength_m(mhz)
    hz = as_sound(mhz)
    label, meaning = sounds_like(hz)
    return {
        "mhz": mhz,
        "wavelength_m": round(lam, 2),
        "wavelength_ft": round(lam * 3.28084, 1),
        "sound_hz": round(hz, 1),
        "note": note_name(hz),
        "audible": HEARING[0] <= hz <= HEARING[1],
        "sounds_like": label,
        "meaning": meaning,
        "meets": meets(mhz, obstacle_m) if obstacle_m else None,
    }
