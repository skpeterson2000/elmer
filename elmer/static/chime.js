/* The study page's sounds: a short tone for an answer, a figure for a
   milestone, and nothing at all until somebody asks for it.

   Why this is not the CW player. morse.js holds one oscillator at the
   operator's own sidetone pitch - what they are learning the code at - and
   a chime that moved that pitch would be teaching two sounds for one thing.
   So this keeps its own context and leaves the sidetone alone.

   Off by default, and remembered per browser. A study tool that starts
   beeping in a quiet house on the first answer of the evening is one that
   gets closed; the control is in the HUD and the setting is the person's.

   A miss gets a tone, but not a buzzer. Missing is the signal the
   scheduler runs on - the same reasoning as the owl in study.js - so the
   sound for it is low, short and flat: a mark that the answer landed, not
   a verdict on the person who gave it. The sounds that are allowed to be
   pleased about themselves are the ones that mark something that took
   work: a rung on the run ladder, a badge, a promotion. */

/* Everything but the two names the page uses lives inside the closure.
   base.html loads morse.js on every page and morse.js has a top-level
   `const RISE`; a second one out here is a redeclaration, which is a parse
   error, which takes this whole file with it - and a dead script is a
   speaker button that silently does nothing. tests/test_pages_run.py asks
   the browser whether chimeControl() exists, which is how that was found. */
const Chime = (() => {
  const CHIME_KEY = 'elmer.chime';
  const RISE = 0.006;            /* shaped, so there is no click - E8D's sidebands */
  let ctx = null, on = false, armed = false;

  try { on = localStorage.getItem(CHIME_KEY) === '1'; } catch (e) { on = false; }

  /* The volume the rest of the program is set to, when there is one.
     voice.js publishes window.Sound on pages that have its control; a
     study page has its own switch and borrows only the level, so muting
     the Gaming Center does not silently leave this one on. */
  function level() {
    const snd = window.Sound;
    const base = snd ? (snd.muted ? 0 : snd.level) : 0.8;
    return Math.pow(base, 2) * 0.28;        /* quieter than a sidetone */
  }

  /* Browsers keep an AudioContext silent until the page has had a touch or
     a key. The first answer is one, but the context has to exist by then,
     so it is brought up on the first interaction of any kind. */
  function arm() {
    if (armed) return;
    armed = true;
    const wake = () => { try { ensure(); } catch (e) {} };
    ['pointerdown', 'keydown', 'touchstart'].forEach(ev =>
      document.addEventListener(ev, wake, { capture: true, passive: true }));
  }

  function ensure() {
    if (!ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return null;                /* no audio here; the page is fine */
      ctx = new Ctx();
    }
    if (ctx.state === 'suspended') ctx.resume().catch(() => {});
    return ctx;
  }

  /* One shaped tone. Times are seconds from now. */
  function tone(hz, at, seconds, loud) {
    const c = ensure();
    if (!c) return;
    const t0 = c.currentTime + at, v = level() * (loud === undefined ? 1 : loud);
    const osc = c.createOscillator(), gain = c.createGain();
    osc.type = 'sine';
    osc.frequency.value = hz;
    gain.gain.setValueAtTime(0, t0);
    gain.gain.linearRampToValueAtTime(v, t0 + RISE);
    gain.gain.setValueAtTime(v, Math.max(t0 + RISE, t0 + seconds - RISE));
    gain.gain.linearRampToValueAtTime(0, t0 + seconds);
    osc.connect(gain);
    gain.connect(c.destination);
    osc.start(t0);
    osc.stop(t0 + seconds + 0.02);
  }

  /* A figure: notes in order, each one after the last. */
  function figure(notes, each, gap, loud) {
    notes.forEach((hz, i) => tone(hz, i * (each + gap), each, loud));
  }

  /* Nothing here may take the page down. An audio failure - a context the
     browser refused, a device that went away with a headset - is a sound
     not played, and the study loop carries on without it. */
  function guard(fn) {
    return function () {
      if (!on) return;
      try { fn.apply(null, arguments); }
      catch (e) { reportError('chime', e && e.message ? e.message : String(e)); }
    };
  }

  return {
    get on() { return on; },
    arm: arm,
    set: function (want) {
      on = !!want;
      try { localStorage.setItem(CHIME_KEY, on ? '1' : '0'); } catch (e) {}
      if (on) { try { ensure(); tone(880, 0, 0.07); } catch (e) {} }
      return on;
    },
    toggle: function () { return this.set(!on); },

    /* An answer landed and it was right: one short blip, out of the way. */
    right: guard(() => tone(880, 0, 0.055, 0.7)),
    /* And it was not: low, short, flat. See the note at the top. */
    wrong: guard(() => tone(311, 0, 0.085, 0.55)),
    /* A rung on the run ladder. Rises, and rises further the higher the
       rung, so ten sounds like more than three without being louder. */
    rung: guard(n => {
      const up = n >= 25 ? [523, 659, 784, 1047] :
                 n >= 10 ? [523, 659, 880] : [523, 784];
      figure(up, 0.075, 0.015);
    }),
    /* A run ended further along than the last one did. Not a fanfare -
       the run is still gone - but the progression is the thing being
       taught, so it gets a sound of its own: two notes, level. */
    further: guard(() => figure([587, 587], 0.06, 0.05, 0.6)),
    /* A badge. */
    badge: guard(() => figure([784, 1047, 1319], 0.08, 0.02)),
    /* A step on the rank ladder: the longest figure here, because it is
       the rarest thing that happens on this page. */
    promoted: guard(() => figure([523, 659, 784, 1047, 1319], 0.09, 0.02)),
  };
})();

/* The switch, for a HUD. Returns the element; the caller places it. */
function chimeControl() {
  const b = document.createElement('button');
  b.className = 'btn sm ghost chime-btn';
  b.type = 'button';
  const paint = () => {
    b.textContent = Chime.on ? '\u{1F50A}' : '\u{1F507}';
    b.title = Chime.on ? 'sound on - press for silence'
                       : 'sound off - press for a tone on each answer';
    b.setAttribute('aria-pressed', Chime.on ? 'true' : 'false');
    b.setAttribute('aria-label', b.title);
  };
  b.addEventListener('click', () => { Chime.toggle(); paint(); });
  paint();
  Chime.arm();
  return b;
}
