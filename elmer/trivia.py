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

    # --- the valves, and the antennas ---------------------------------------
    ("John Ambrose Fleming made the first thermionic valve in 1904 - a "
     "two-element diode, built for the Marconi company as a detector. Every "
     "tube since starts from it.", "Fleming, 1904"),
    ("Lee de Forest put a third element into Fleming's valve in 1906 and "
     "called it the Audion - the first tube that could amplify. By most "
     "accounts, including his own, he did not understand why it worked; "
     "Armstrong worked that out.", "the Audion, 1906"),
    ("Hertz's apparatus of 1887 was a spark gap between two rods with plates "
     "on the ends - a dipole. The dipole is the oldest antenna there is, and "
     "still the one every other is compared with.", "the dipole, 1887"),
    ("The Yagi antenna was designed by Shintaro Uda at Tohoku University in "
     "1926. His professor, Hidetsugu Yagi, published it in English in 1928, "
     "and so it carries Yagi's name; the fair name is Yagi-Uda.",
     "Yagi-Uda, 1926"),
    ("Grote Reber, W9GFZ, built a 31-foot parabolic dish in his back yard in "
     "Wheaton, Illinois, in 1937, and for most of a decade was the only radio "
     "astronomer in the world.", "Reber, 1937"),
    ("Karl Jansky at Bell Labs found in 1932 that a steady hiss on 20.5 MHz "
     "rose and set with the stars, not the sun. It was the Milky Way. Radio "
     "astronomy starts there; the unit of flux density is named for him.",
     "Jansky, 1932"),

    # --- the bands, and the licence -----------------------------------------
    ("The Radio Act of 1912 sent amateurs to wavelengths of 200 metres and "
     "shorter, which the experts of the day thought useless. The ARRL's own "
     "history of what happened next is titled 'Two Hundred Meters and Down'.",
     "200 metres and down, 1912"),
    ("In December 1921 Paul Godley, 2ZE, sat in a tent at Ardrossan in "
     "Scotland and heard 1BCG in Greenwich, Connecticut - the first amateur "
     "signal across the Atlantic. Two-way contact took two more years.",
     "the Transatlantic Tests, 1921"),
    ("The 1927 Washington radiotelegraph conference gave amateurs the bands "
     "near 80, 40, 20 and 10 metres - harmonically related on purpose, so a "
     "transmitter's harmonics fell in another amateur band rather than on "
     "somebody else.", "the harmonic bands, 1927"),
    ("The 30, 17 and 12 metre bands came from the World Administrative Radio "
     "Conference of 1979, which is why they are still called the WARC bands "
     "- and why, by agreement, there are no contests on them.",
     "the WARC bands, 1979"),
    ("The Novice and Technician classes were both created in 1951. The Novice "
     "stopped being issued in the restructuring of April 2000, which left the "
     "three classes there are today.", "Novice, 1951-2000"),
    ("The Morse code test was dropped from every US amateur licence on 23 "
     "February 2007. Nobody has had to pass one since - and more people send "
     "CW now than before.", "no more code test, 2007"),
    ("Vanity callsigns began in 1996. Before that you got what came next in "
     "the sequence, and kept it.", "vanity callsigns, 1996"),
    ("K, N, W, and AA through AL are the prefixes the ITU has allotted to the "
     "United States. Every US callsign starts with one of them, and no other "
     "country's does.", "the US prefixes"),

    # --- the practice ---------------------------------------------------------
    ("The RST system - readability 1 to 5, strength and tone 1 to 9 - was "
     "devised by Arthur Braaten, W2BSR, in 1934 and adopted by the ARRL the "
     "same year.", "RST, 1934"),
    ("The Amateur's Code - considerate, loyal, progressive, friendly, "
     "balanced, patriotic - was written by Paul Segal, W9EEA, in 1928. It "
     "still opens the Handbook.", "the Amateur's Code, 1928"),
    ("The Maidenhead locator - the grid square on your QSL card - was worked "
     "out at a meeting of European VHF managers in Maidenhead, England, in "
     "April 1980.", "Maidenhead, 1980"),
    ("The phonetic alphabet - Alfa, Bravo, Charlie - was settled by ICAO in "
     "1956 after testing words on speakers of many languages, and the ITU "
     "adopted it after. 'Alfa' and 'Juliett' are spelled that way so that "
     "French and Spanish speakers say them right.", "the phonetics, 1956"),
    ("OSCAR 3, launched in March 1965, carried the first amateur transponder "
     "- a linear translator on 2 metres - and relayed about a thousand "
     "contacts in its eighteen days.", "OSCAR 3, 1965"),
    ("Owen Garriott, W5LFL, made the first amateur radio contacts from space "
     "in December 1983, on 2 metres FM from the shuttle Columbia. The station "
     "on the ISS descends from it.", "amateur radio in space, 1983"),
    ("In 1943 the US Supreme Court held that key claims of Marconi's tuning "
     "patent had been anticipated by earlier work, including Tesla's and "
     "Lodge's. It is often summarised as 'Tesla invented radio', which is "
     "more than the court said.", "Marconi v. United States, 1943"),
    ("WWV, the standard time and frequency station, has been on the air since "
     "1919 and is one of the oldest callsigns in continuous use in the "
     "country. It moved from Maryland to Fort Collins, Colorado, in 1966.",
     "WWV, 1919"),
]


# Words from people who built the art, each with where it is written down.
# Radio "quotes" are folklore-prone - half of what is attributed to Tesla and
# Marconi online was said by neither - so a quotation is here only where the
# source is a document somebody can go and read, and the source is named. A
# paraphrase is marked as one.
QUOTES = [
    ("It's of no use whatsoever ... this is just an experiment that proves "
     "Maestro Maxwell was right - we just have these mysterious electromagnetic "
     "waves that we cannot see with the naked eye. But they are there.",
     "Heinrich Hertz, asked what his waves were for, as recounted by his "
     "students; the wording varies between accounts"),
    ("The wireless telegraph is not difficult to understand. The ordinary "
     "telegraph is like a very long cat. You pull the tail in New York, and it "
     "meows in Los Angeles. The wireless is the same, only without the cat.",
     "attributed to Albert Einstein; the earliest print appearances are in "
     "the 1920s and none quote him directly - a story, told as one"),
    ("The amateur is considerate ... loyal ... progressive ... friendly ... "
     "balanced ... patriotic.",
     "Paul M. Segal, W9EEA, The Amateur's Code, 1928 - printed at the front of "
     "every ARRL Handbook"),
    ("Have I done the world good, or have I added a menace?",
     "attributed to Guglielmo Marconi late in life and repeated in the "
     "biographies; the occasion is not recorded"),
    ("The radio craze ... will die out in time.",
     "Thomas Edison, 1922, as reported in the press that year - one of a set "
     "of predictions he made about broadcasting, most of them wrong"),
    ("Radio is the theatre of the mind; television is the theatre of the "
     "mindless.",
     "Steve Allen, quoted widely from the 1950s on; the first half is the "
     "part radio people keep"),
    ("When wireless is perfectly applied the whole earth will be converted "
     "into a huge brain ... we shall be able to communicate with one another "
     "instantly, irrespective of distance.",
     "Nikola Tesla, interview in Collier's, 30 January 1926 - one of the few "
     "Tesla predictions that is both his and came true"),
    ("Amateur radio is the only hobby in which the participant can, on the "
     "same day, talk to an astronaut and to a farmer in a field.",
     "a saying of the hobby's, unattributed, and kept because it is true"),
    ("The best antenna is the one you have up.",
     "operator's proverb - repeated so often nobody owns it"),
]

# Hams people have heard of. Callsigns are from the licence records or the
# person's own account; a licensee who has died is marked SK, silent key,
# as the hobby does. Nobody is here on a rumour.
HAMS = [
    ("Joe Walsh - WB6ACU", "Guitarist of the Eagles and the James Gang; a lifelong active "
     "ham, benefactor of the ARRL's spectrum defense fund, and a vintage-gear "
     "collector who works CW."),
    ("Walter Cronkite - KB2GSD (SK)", "The CBS anchor was licensed late in life and "
     "narrated the ARRL's film 'Amateur Radio Today' in 2003."),
    ("Marlon Brando - FO5GJ (SK)", "Held a French Polynesian licence for his atoll, "
     "Tetiaroa, and an American one as KE6PZH; operated under another name to "
     "keep the pile-ups honest."),
    ("Priscilla Presley - N6YOS", "Licensed as a Technician in the 1980s; the "
     "callsign is in the FCC's records."),
    ("Chet Atkins - W4CGP (SK)", "The guitarist and record producer was an active "
     "ham in Nashville."),
    ("Patty Loveless - KD4WUJ", "Country singer; licensed in the early 1990s."),
    ("Tim Allen - KK6OTD", "The actor got his licence in 2014 while his character "
     "on 'Last Man Standing' ran a ham station on screen."),
    ("King Hussein of Jordan - JY1 (SK)", "Held his country's first callsign, was a "
     "regular on the air for decades, and gave the hobby a head of state's "
     "backing at world radio conferences."),
    ("Juan Carlos I of Spain - EA0JC", "The former king's callsign; EA0 is the "
     "prefix Spain reserved for it."),
    ("Rajiv Gandhi - VU2RG (SK)", "Prime Minister of India, 1984-89; his widow Sonia "
     "also held a licence, VU2SON."),
    ("General Curtis LeMay - K0GRL (SK)", "Chief of Staff of the US Air Force; he "
     "pushed single-sideband into the military after using it as a ham, and the "
     "MARS programme owes much to him."),
    ("Barry Goldwater - K7UGA (SK)", "Senator and presidential candidate; his "
     "Arizona station relayed phone patches for servicemen in Vietnam."),
    ("Arthur Godfrey - K4LIB (SK)", "The radio and television host; also a pilot, "
     "and an early advocate of the hobby on the air."),
    ("Garry Shandling - KQ6KA (SK)", "The comedian was an active ham who found "
     "the hobby a rest from the business."),
    ("Andy Devine - WB6RER (SK)", "The gravel-voiced Western actor."),
    ("Ronnie Milsap - WB4KCG", "The country singer, blind from birth, is a "
     "long-time ham; he has said the radio was his window."),
    ("Donny Osmond - KA7EVD", "Licensed as a young man; the callsign is his."),
    ("Dick Rutan - KB6LQS (SK)", "Flew Voyager round the world without refuelling "
     "in 1986 and kept in touch with hams along the way."),
    ("Owen Garriott - W5LFL (SK)", "The astronaut who made the first amateur "
     "contacts from space, from Columbia in 1983."),
    ("Joe Taylor - K1JT", "Nobel laureate in physics for the binary pulsar; then "
     "wrote WSJT, WSPR and FT8, and changed weak-signal radio for everybody."),
    ("Steve Wozniak - ex WA6BND", "Co-founder of Apple; licensed as a boy in "
     "the 1960s, by his own account in 'iWoz'."),
    ("Cliff Stoll - K7TA", "The astronomer who caught a KGB hacker in 'The "
     "Cuckoo's Egg' is a ham and a maker of Klein bottles."),
]

# How the art is practised - the things an exam never asks and every net
# control knows. Rules are cited; the rest is the convention of the air and
# is called that.
TECHNIQUE = [
    ("Listen first, then ask: 'Is this frequency in use?' - on CW, 'QRL?'. "
     "A 'yes', a 'QRL' or a 'C' means it is; find another spot. The silence "
     "you hear may be the middle of somebody else's contact.",
     "the first thing said on any frequency"),
    ("Identify with your callsign at the end of a communication and at least "
     "every ten minutes during it. That is 47 CFR 97.119, and it is all the "
     "rule asks; giving the other station's call too is custom.",
     "47 CFR 97.119"),
    ("The ITU phonetic alphabet exists because B, D, P, T and V are the same "
     "sound in noise. Use it for callsigns on phone, and use its words - "
     "'Bravo', not 'Boston': the far end has learned one list, not yours.",
     "the phonetic alphabet"),
    ("Signal reports are RST: readability 1 to 5, strength 1 to 9, and on CW "
     "a tone 1 to 9. '59' on phone is perfectly readable and extremely strong; "
     "'599' is the CW form, and '5NN' is the contest shortcut for it.",
     "the RST system"),
    ("Q signals were adopted internationally in 1912 for ships' operators "
     "who shared no language. QTH is location, QSL is 'I acknowledge', QRZ "
     "is 'who is calling me', QRM is interference from stations and QRN "
     "from nature, QSY is 'change frequency', QRP is low power.",
     "the Q code, 1912"),
    ("73 comes from the telegraphers' numeric codes of the 1850s and means "
     "'best regards' - already plural, so '73s' says it twice. 88 is love "
     "and kisses, and is used advisedly.",
     "the telegraph number codes"),
    ("In a pile-up the DX station runs the show: send your full call once, "
     "then listen. Partial calls, doubled calls and calling when the DX has "
     "asked for another area slow everybody down, including you.",
     "pile-up manners"),
    ("A DX station 'listening up 5' transmits on one frequency and listens "
     "five kilohertz higher. Calling on the DX station's own frequency is the "
     "commonest pile-up mistake and the most resented, because it covers the "
     "station everyone is trying to hear.",
     "split operation"),
    ("Speak across the microphone, not into it, a few inches away and at a "
     "steady level. The ALC meter is the one that says you are overdriving; "
     "louder into the mic does not make you louder at the far end, only wider.",
     "microphone technique"),
    ("On a repeater, key up and wait half a second before speaking - the "
     "repeater has to come up and the far end's squelch has to open - and "
     "leave a pause between overs so somebody can break in. 'Break' is for "
     "traffic; an emergency says 'emergency'.",
     "repeater manners"),
    ("Checking into a net: give your callsign only when net control asks for "
     "check-ins, then say what you have - traffic, a comment, or nothing. Net "
     "control decides the order. A directed net is a conversation with one "
     "person choosing who speaks.",
     "net procedure"),
    ("On CW, send at the speed you can copy: the other station will match "
     "you. Sending faster than you receive earns a reply you cannot read, "
     "and a 'QRS' asks them to slow down without embarrassment on either side.",
     "CW speed"),
    ("The Maidenhead locator, adopted in 1980, puts the world into grid "
     "squares: two letters for a 10 by 20 degree field, two digits for a "
     "1 by 2 degree square, two more letters for a sub-square a few miles "
     "across. EN26 is a square; EN26uo is a place.",
     "grid squares, 1980"),
    ("Say where you are in words anybody would know when it matters - the "
     "road, the mile marker, the nearest town. A grid square is for the log; "
     "a stranger with a telephone needs a place they can repeat to a "
     "dispatcher.",
     "when it matters"),
]

# The gear: what the equipment does and does not do, with the numbers that
# decide it.
EQUIPMENT = [
    ("An SWR meter reads the mismatch where the meter is, not at the antenna. "
     "Lossy coax makes the SWR look better than it is at the far end, because "
     "the reflected power is being eaten on the way back to you.",
     "SWR and coax loss"),
    ("A dummy load is the one antenna it is legal to test into on any "
     "frequency, because it radiates nothing. It is how a station is tuned up "
     "without putting a carrier on a frequency somebody else is using.",
     "the dummy load"),
    ("Coax loss climbs with frequency and is quoted per hundred feet: RG-58 "
     "loses about 6 dB at 2 m - three quarters of your power - where RG-213 "
     "loses about 3 and LMR-400 about 1.5. On HF the same run of RG-58 loses "
     "a decibel and nobody notices.",
     "feedline loss, published figures"),
    ("An antenna tuner matches the transmitter to the feedline. It does not "
     "make the antenna efficient: a tuner showing the rig a perfect 50 ohms "
     "can be matching into a coil that is mostly heater.",
     "what a tuner does"),
    ("A ferrite choke where the coax meets the antenna stops the braid "
     "carrying RF back into the shack. RF in the shack shows up as a hot mic, "
     "distorted audio, or a radio that resets itself on transmit.",
     "common-mode current"),
    ("A vehicle's electrical system runs at about 13.8 V with the engine "
     "going, which is why mobile radios are rated at 13.8 V. Below about 11 V "
     "most transceivers cut power or refuse to transmit; the radio is not "
     "broken, the battery is.",
     "13.8 volts"),
    ("Fuse both the positive and the negative lead of a mobile installation. "
     "A corroded ground strap can leave the radio's negative lead as the "
     "return path for the starter motor, and a single fuse on the positive "
     "side does nothing about that.",
     "mobile wiring"),
    ("Lithium iron phosphate batteries hold about 13.2 V through most of "
     "their discharge - close to a running vehicle - where lead-acid falls "
     "from 12.6 toward 11. That flat curve, and a quarter of the weight, is "
     "why they took over portable HF.",
     "LiFePO4"),
    ("The Yagi-Uda antenna was described by Shintaro Uda in 1926 and made "
     "known in English by his professor Hidetsugu Yagi in 1928. Uda did most "
     "of the work; his name comes second on his own antenna.",
     "Yagi and Uda, 1926"),
    ("A quarter-wave vertical is half an antenna. The radials - or the car "
     "roof, or the ocean - are the other half, and a vertical with a poor "
     "ground plane spends its power warming the soil.",
     "the ground plane"),
    ("The PL-259 'UHF' connector was named in the 1930s, when UHF meant "
     "anything above 30 MHz. It is not a constant-impedance connector: fine "
     "at HF and 2 m, lossy at a gigahertz, where a type N belongs.",
     "connectors"),
    ("An antenna analyser reads reactance with its sign, and the sign is the "
     "instruction: +X at the frequency you want means the element is too "
     "long, cut; -X means too short, add. A plain SWR meter cannot tell you "
     "which way to go.",
     "reactance and its sign"),
    ("An RTL-SDR dongle covers roughly 24 to 1700 MHz for the price of a "
     "pizza and began life as a European television tuner; somebody noticed "
     "in 2012 that its chip would hand over raw samples. Most of the "
     "spectrum on a laptop screen since then traces to that.",
     "the RTL-SDR, 2012"),
]

DECKS = {"history": CARDS, "quotes": QUOTES, "hams": HAMS,
         "technique": TECHNIQUE, "equipment": EQUIPMENT}


def draw(rng=None, avoid=None, deck="history"):
    """One card, not the last one shown if that can be helped."""
    rng = rng or random
    cards = DECKS.get(deck) or CARDS
    pool = [c for c in cards if c[0] != (avoid or "")] or cards
    text, about = rng.choice(pool)
    return {"text": text, "about": about, "deck": deck if cards is not CARDS or deck == "history" else "history"}


def count(deck="history"):
    return len(DECKS.get(deck) or CARDS)
