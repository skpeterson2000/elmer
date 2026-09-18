/* ELMER says its own name, in code, when it opens.

   Five characters at twenty words a minute, no Farnsworth stretch, on the
   1020 Hz the rest of the program keys on. It is the station identifying
   itself, which is the most ordinary thing on the air and the first thing
   anybody learns to do, and it means the unit has come up and the sound
   works - on a Raspberry Pi wired to a monitor, that is worth knowing
   before you go looking for a volume control.

   Once when the program opens, not once a page: the announcement is marked
   in this tab's session storage, so walking round the pages is quiet and
   opening ELMER again is not. A tab that cannot store anything announces
   each time rather than never, which is the better way round for something
   whose whole job is to say the unit is awake.

   Off is a switch in the Station panel, because a room where this would be
   unwelcome is easy to picture: a net in progress, a classroom, a hospital,
   a field site at night. Being quiet is sometimes what being in a community
   asks of a station.

   Browsers keep audio silent until a page has been touched. Where that
   applies the announcement waits for the first press or key and goes then,
   which on a kiosk that allows audio is not needed at all and everywhere
   else costs one click nobody notices making. */
(() => {
  if (!window.ELMER_ANNOUNCE) return;
  if (typeof player === 'undefined' || typeof CODE === 'undefined') return;

  const MARK = 'elmer.announced';
  try {
    if (sessionStorage.getItem(MARK)) return;
    sessionStorage.setItem(MARK, '1');
  } catch (e) { /* no storage: say it, rather than never say it */ }

  /* Twenty words a minute both ways. The lessons stretch the gaps because a
     learner needs the thinking time; a station identifying itself does not,
     and a stretched callsign is not what one sounds like. */
  const WPM = 20;
  const dit = 1200 / WPM;
  const TIMING = {dit: dit, dah: 3 * dit, symbol_gap: dit,
                  char_gap: 3 * dit, word_gap: 7 * dit};
  const TONE = 1020;

  const word = [...'ELMER']
    .map(c => ({char: c, code: CODE[c] || ''}))
    .filter(s => s.code);
  if (!word.length) return;

  const say = () => {
    try {
      if (typeof holdTone === 'function') holdTone(TONE);
      player.send([word], TIMING, null, () => {
        if (typeof holdTone === 'function') holdTone(null);
      });
    } catch (e) { /* no audio on this machine; nothing to report */ }
  };

  let ctx = null;
  try { ctx = player.ensure(); } catch (e) { return; }
  if (ctx && ctx.state === 'running') { say(); return; }

  /* Silenced until the page is touched. Wait for that, once. */
  let waiting = true;
  const wake = () => {
    if (!waiting) return;
    waiting = false;
    ['pointerdown', 'keydown', 'touchstart']
      .forEach(ev => document.removeEventListener(ev, wake, true));
    setTimeout(say, 120);            // let the press do its own job first
  };
  ['pointerdown', 'keydown', 'touchstart']
    .forEach(ev => document.addEventListener(ev, wake, {capture: true, passive: true}));
})();
