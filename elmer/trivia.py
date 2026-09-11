"""Cards for the wait: a little of the history of the art.

Somebody who has answered sits looking at a phone that says "waiting" until
the rest of the table is in. That is dead time in a game, and it is also the
one moment in an evening when a person is holding a screen with nothing to do
but read it - so it gets a card. Not exam material: the exam is what the game
is already made of. The history of the craft, which the exam never asks and
which is why most people who stay in this hobby stayed.

Every card here must be checkable. Where the record is disputed the card
says so - "by his own account", "is usually traced to" - because a program
whose numbers are measured cannot start handing out folklore as fact the
moment it changes the subject. Add a card only if you could point somebody
at where it is written down.
"""
import random

CARDS = [
    # --- the physics, and the people who found it ---------------------------
    ("James Clerk Maxwell's equations of 1865 predicted electromagnetic waves "
     "travelling at the speed of light - more than twenty years before anyone "
     "had made one on purpose.", "Maxwell, 1865"),
    ("Heinrich Hertz produced and detected radio waves in 1887, proving Maxwell "
     "right. Asked what use they were, he is reported to have said none at all. "
     "The unit of frequency is named for him.", "Hertz, 1887"),
    ("The hertz replaced 'cycles per second' as the international unit of "
     "frequency in 1960. Older equipment and older operators still say kc "
     "and Mc.", "the unit, 1960"),
    ("In 1902 Arthur Kennelly in America and Oliver Heaviside in England each "
     "proposed, independently, a conducting layer high in the atmosphere to "
     "explain how Marconi's signal had got over the horizon. It was called the "
     "Kennelly-Heaviside layer for decades.", "the E layer, 1902"),
    ("Edward Appleton proved the reflecting layer was really there in 1924, by "
     "measuring the height a signal came back from. He got the Nobel Prize in "
     "Physics for it in 1947.", "Appleton, 1924"),
    ("Edwin Armstrong invented the regenerative receiver in 1912, the "
     "superheterodyne in 1918 and wideband FM in 1933. Nearly every receiver "
     "made since is one of his in some part.", "Armstrong"),

    # --- the first signals -------------------------------------------------
    ("Samuel Morse's first public telegraph message, Washington to Baltimore "
     "in May 1844, was 'What hath God wrought'. Alfred Vail, who worked out "
     "much of the code, was at the far end.", "Morse and Vail, 1844"),
    ("On 12 December 1901 Marconi reported hearing the letter S - three dots - "
     "at Signal Hill, Newfoundland, sent from Poldhu in Cornwall. Whether he "
     "really heard it has been argued about ever since.", "Marconi, 1901"),
    ("Reginald Fessenden said he made the first voice broadcast on Christmas "
     "Eve 1906 from Brant Rock, Massachusetts - playing a violin and reading "
     "from Luke. The account is his own; there is little independent record.",
     "Fessenden, 1906"),
    ("SOS was agreed as the international distress signal at Berlin in 1906 "
     "and came into force in 1908. It does not stand for anything. It was "
     "chosen because nine elements with no gaps is unmistakable.", "SOS, 1906"),
    ("The Titanic's operators, Jack Phillips and Harold Bride, sent both CQD - "
     "the Marconi company's distress call - and the newer SOS. Phillips stayed "
     "at the key and did not survive.", "Titanic, 1912"),
    ("The Radio Act of 1912, passed months after the Titanic, required every "
     "American radio operator to hold a licence. The amateur licence you are "
     "studying for descends from it.", "the licence, 1912"),

    # --- the language ------------------------------------------------------
    ("'73' comes from the numeric shorthand of nineteenth-century landline "
     "telegraphers - the 92 Code of 1859 - where it meant 'my compliments'. "
     "It has meant 'best regards' to radio operators for over a century.",
     "73"),
    ("The Q signals were drawn up by the British in 1909 and adopted "
     "internationally at the London convention of 1912, so that operators "
     "with no common language could still ask 'is my signal fading?' - QSB.",
     "Q signals, 1912"),
    ("'CQ' as a general call is usually traced to the French 'securite' - "
     "the landline telegraphers' way of saying 'attention, all stations'. It "
     "was in use before radio was.", "CQ"),
    ("Nobody is certain where 'ham' came from. The most likely source is "
     "landline telegraph slang, where a 'ham' was a clumsy operator; amateurs "
     "adopted the insult and kept it.", "ham"),
    ("The word 'Elmer', for the person who helps a newcomer into the hobby, "
     "comes from Rod Newkirk, W9BRD, in his 'How's DX' column in QST in March "
     "1971. This program is named for the idea.", "Elmer, 1971"),

    # --- the amateurs ------------------------------------------------------
    ("The ARRL was founded in 1914 by Hiram Percy Maxim in Hartford, "
     "Connecticut, to relay messages across the country by radio in hops - "
     "which is what 'Relay League' means.", "ARRL, 1914"),
    ("The first two-way amateur contact across the Atlantic was made in "
     "November 1923, between Fred Schnell 1MO and John Reinartz 1XAM in "
     "Connecticut and Leon Deloy 8AB in Nice, on about 110 metres.",
     "across the Atlantic, 1923"),
    ("The FCC was created by the Communications Act of 1934, taking over "
     "from the Federal Radio Commission, which had lasted seven years.",
     "FCC, 1934"),
    ("Field Day was first held in 1933. The idea - take the station "
     "somewhere with no mains and see what you can work - has not changed.",
     "Field Day, 1933"),
    ("When Sputnik 1 went up on 4 October 1957, amateurs around the world "
     "were listening to its beacon on 20.005 MHz within hours. Many of the "
     "first recordings of it are theirs.", "Sputnik, 1957"),
    ("The first amateur moonbounce contact was made in July 1960 on 1296 "
     "MHz, between W6HB in California and W1BU in Massachusetts - about two "
     "and a half seconds each way.", "EME, 1960"),
    ("OSCAR 1, the first amateur radio satellite, was launched on 12 December "
     "1961 as a piggyback payload and sent 'HI' in Morse for three weeks. "
     "It was built by amateurs in a garage.", "OSCAR 1, 1961"),
    ("W1AW, the ARRL's station in Newington, Connecticut, is the Hiram Percy "
     "Maxim Memorial Station. It has sent code practice on schedule for most "
     "of a century.", "W1AW"),
    ("Jamboree on the Air, which puts Scouts on the radio with amateurs "
     "every October, has run since 1958.", "JOTA, 1958"),
]


def draw(rng=None, avoid=None):
    """One card, not the last one shown if that can be helped."""
    rng = rng or random
    pool = [c for c in CARDS if c[0] != (avoid or "")] or CARDS
    text, about = rng.choice(pool)
    return {"text": text, "about": about}


def count():
    return len(CARDS)
