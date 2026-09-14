# The narrator's script

One line a snippet. Record each as its own MP3, named by the stem, into
`elmer/static/golf/voice/`; the narrator says what it has and is silent
for the rest. Names: `name-<slug>.mp3`, the slug the name lowercased with
anything but letters and digits made a hyphen (*Ann Lee* is
`name-ann-lee.mp3`). Regenerate this file with `python3 tools/voice_script.py --md`.

How a line is pieced together (the game composes these; see `elmer/voice.py`):

- the hole, at the tee: *pebble-beach · the-first · par · four · three · hundred · and · seventy · seven · yards · the-breeze-is-behind-you · twelve · miles-an-hour*
- the address: *name-scott · addresses-the-ball · the-driver · in-hand · three · hundred · and · seventy · seven · to-go · from-the-tee*
- the stroke: *the-driver · two · hundred · and · fifty · five · yards · fairway · one · hundred · and · twenty · two · to-go*
- the call: one of the *call-* files
- the card: *thats-the-hole · name-scott · for-a-bogey · name-ann · for-par · on-to-the-next*

## Numbers - reused for yards, feet, strokes, miles an hour

- `zero`: zero
- `one`: one
- `two`: two
- `three`: three
- `four`: four
- `five`: five
- `six`: six
- `seven`: seven
- `eight`: eight
- `nine`: nine
- `ten`: ten
- `eleven`: eleven
- `twelve`: twelve
- `thirteen`: thirteen
- `fourteen`: fourteen
- `fifteen`: fifteen
- `sixteen`: sixteen
- `seventeen`: seventeen
- `eighteen`: eighteen
- `nineteen`: nineteen
- `twenty`: twenty
- `thirty`: thirty
- `forty`: forty
- `fifty`: fifty
- `sixty`: sixty
- `seventy`: seventy
- `eighty`: eighty
- `ninety`: ninety
- `hundred`: hundred
- `and`: and

## The holes

- `the-first`: the first
- `the-second`: the second
- `the-third`: the third
- `the-fourth`: the fourth
- `the-fifth`: the fifth
- `the-sixth`: the sixth
- `the-seventh`: the seventh
- `the-eighth`: the eighth
- `the-ninth`: the ninth
- `the-tenth`: the tenth
- `the-eleventh`: the eleventh
- `the-twelfth`: the twelfth
- `the-thirteenth`: the thirteenth
- `the-fourteenth`: the fourteenth
- `the-fifteenth`: the fifteenth
- `the-sixteenth`: the sixteenth
- `the-seventeenth`: the seventeenth
- `the-eighteenth`: the eighteenth

## The calls - the golfer's word at contact

- `call-fairway-1`: Pured it.
- `call-fairway-2`: Right down the middle.
- `call-fairway-3`: That'll play.
- `call-green-1`: On the dance floor.
- `call-green-2`: Stuck it.
- `call-green-3`: That's looking at it.
- `call-long-1`: Flew the green.
- `call-long-2`: Too much club.
- `call-long-3`: Airmailed it.
- `call-holed-1`: In the hole!
- `call-holed-2`: Drained it.
- `call-holed-3`: Bottom of the cup.
- `call-rough-1`: Topped it.
- `call-rough-2`: Fat. Chunked it.
- `call-rough-3`: Skied that one.
- `call-sand-1`: Sliced it into the sand.
- `call-sand-2`: Pulled it into the bunker.
- `call-sand-3`: Beach.
- `call-water-1`: Hooked it into the water.
- `call-water-2`: Wet.
- `call-water-3`: That's a splash. What was the wind?
- `call-missed-1`: Lipped out.
- `call-missed-2`: Left it short.
- `call-missed-3`: Burned the edge.
- `call-ace`: A hole in one!

## Everything else - the address, the stroke, the wind, the card

- `par`: par
- `yards`: yards
- `feet`: feet
- `to-go`: to go
- `pebble-beach`: Pebble Beach
- `the-old-course`: the Old Course at Saint Andrews
- `augusta-national`: Augusta National
- `the-breeze-is-behind-you`: the breeze is behind you
- `into-the-breeze`: into the breeze
- `a-crosswind`: a crosswind
- `the-wind-swirls-here`: the wind swirls here
- `miles-an-hour`: miles an hour
- `the-player`: the player
- `addresses-the-ball`: addresses the ball
- `in-hand`: in hand
- `the-driver`: the driver
- `the-wood`: the wood
- `the-iron`: the iron
- `the-wedge`: the wedge
- `the-putter`: the putter
- `from-the-tee`: from the tee
- `from-the-fairway`: from the fairway
- `from-the-rough`: from the rough
- `from-the-sand`: from the sand
- `on-the-green`: on the green
- `your-shot`: your shot
- `a-foul-ball`: a foul ball
- `fairway`: fairway
- `into-the-sand`: into the sand
- `into-the-water`: into the water
- `into-the-rough`: into the rough
- `short-and-into-the-rough`: short, and into the rough
- `through-the-green`: through the green, into the rough behind
- `drop-and-a-penalty-stroke`: drop, and a penalty stroke
- `putt-holed`: putt holed
- `putt-missed`: putt missed
- `in-the-hole`: in the hole
- `an-ace`: an ace
- `picked-up`: picked up
- `for-an-albatross`: for an albatross
- `for-an-eagle`: for an eagle
- `for-a-birdie`: for a birdie
- `for-par`: for par
- `for-a-bogey`: for a bogey
- `for-a-double-bogey`: for a double bogey
- `for-a-triple-bogey`: for a triple bogey
- `over-par`: over par
- `thats-the-hole`: that's the hole
- `on-to-the-next`: on to the next
- `wins-the-round`: wins the round
- `a-playoff`: a playoff, sudden death
- `tee-time`: a tee time
