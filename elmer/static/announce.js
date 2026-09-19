/* ELMER says its own name, in code, when it opens - and whenever asked.

   Twenty words a minute, no Farnsworth stretch, on the 1020 Hz the rest of
   the program keys on. It is the station identifying itself, which is the
   most ordinary thing on the air and the first thing anybody learns to do,
   and it means the unit has come up and the sound works - on a Raspberry Pi
   wired to a monitor, that is worth knowing before you go looking for a
   volume control.

   In a room with other people in it the announcement does a second job.
   Somebody who knows the program hears it start, and what they have heard
   is an invitation to a game. A supporter who asked to be named has their
   own callsign keyed after ELMER's, so what the room hears is whose unit
   this is.

   Once when the program opens, not once a page: the announcement is marked
   in this tab's session storage, so walking round the pages is quiet and
   opening ELMER again is not. A tab that cannot store anything announces
   each time rather than never, which is the better way round for something
   whose whole job is to say the unit is awake.

   And on demand, from the icon in the corner. The name beside it is the
   Dashboard button - the only one, now - but the icon itself keys the
   name again. That is a plain thing to want (hear it again;
   check the sound; show somebody) and it costs nothing, because browsers
   keep audio silent until a page has been touched and a press on the icon
   is a touch. A second press restarts it rather than keying two names on
   top of each other.

   Off is a switch in the Station panel, and off means off: the icon is a
   plain link then, because a room where the announcement would be
   unwelcome - a net in progress, a classroom, a hospital, a field site at
   night - is exactly the room where a stray click must not key a tone.
   Being quiet is sometimes what being in a community asks of a station.

   Browsers keep audio silent until a page has been touched. Where that
   applies the opening announcement waits for the first press or key and
   goes then, which on a kiosk that allows audio is not needed at all and
   everywhere else costs one click nobody notices making. */
(() => {
  const cfg = window.ELMER_ANNOUNCE;
  if (!cfg || !cfg.on) return;
  if (typeof player === 'undefined' || typeof CODE === 'undefined') return;

  /* Twenty words a minute both ways. The lessons stretch the gaps because a
     learner needs the thinking time; a station identifying itself does not,
     and a stretched callsign is not what one sounds like. */
  const WPM = 20;
  const dit = 1200 / WPM;
  const TIMING = {dit: dit, dah: 3 * dit, symbol_gap: dit,
                  char_gap: 3 * dit, word_gap: 7 * dit};
  const TONE = 1020;

  /* ELMER, and for a supporter who asked to be named, DE and their own
     callsign after it. The room hears whose unit this is, which is the
     whole of the feature: a name read out to people who know what it
     means. The server decides what may be keyed - see cw.keyable - so
     nothing arrives here that the keyer cannot send. */
  const text = 'ELMER' + (cfg.de ? ' DE ' + cfg.de : '');
  const words = text.split(' ')
    .map(w => [...w].map(c => ({char: c, code: CODE[c] || ''})).filter(s => s.code))
    .filter(w => w.length);
  if (!words.length) return;

  const say = () => {
    try {
      player.stop();                       // a name half sent is not a name
      if (typeof holdTone === 'function') holdTone(TONE);
      player.send(words, TIMING, null, () => {
        if (typeof holdTone === 'function') holdTone(null);
      });
    } catch (e) { /* no audio on this machine; nothing to report */ }
  };
  window.elmerSayName = say;

  /* The opening announcement's wait for a first touch, if one is needed.
     Defined up here so the icon's press can stand in for that touch and
     not key the name twice - once for the press, once for the wake. */
  const TOUCH = ['pointerdown', 'keydown', 'touchstart'];
  let waiting = false;
  const unwait = () => {
    if (!waiting) return false;
    waiting = false;
    TOUCH.forEach(ev => document.removeEventListener(ev, wake, true));
    return true;
  };
  const wake = () => {
    if (unwait()) setTimeout(say, 120);    // let the press do its own job first
  };

  /* The icon, or the wordmark where a unit has no icon file. */
  const knob = document.querySelector('.brand-icon') || document.querySelector('.brand-mark');
  if (knob && !knob.dataset.cwBound) {
    knob.dataset.cwBound = '1';
    knob.title = 'ELMER, in code';
    knob.style.cursor = 'pointer';
    knob.addEventListener('click', e => {
      e.preventDefault();                  // the name beside it is what goes home
      e.stopPropagation();
      unwait();                            // this press is the touch; do not also wake
      try { player.ensure(); } catch (err) { return; }
      say();
    });
  }

  /* Once when the program opens. */
  const MARK = 'elmer.announced';
  try {
    if (sessionStorage.getItem(MARK)) return;
    sessionStorage.setItem(MARK, '1');
  } catch (e) { /* no storage: say it, rather than never say it */ }

  let ctx = null;
  try { ctx = player.ensure(); } catch (e) { return; }
  if (ctx && ctx.state === 'running') { say(); return; }

  /* Silenced until the page is touched. Wait for that, once. */
  waiting = true;
  TOUCH.forEach(ev => document.addEventListener(ev, wake, {capture: true, passive: true}));
})();
