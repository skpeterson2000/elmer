/* The narrator's voice: recorded snippets, pieced together.

   The server composes a line as a list of tokens - the stems of sound files
   in /static/golf/voice/ (three, hundred, addresses-the-ball) - the way an
   ATIS reads the weather from a shelf of words. This plays them in order,
   one after another, and is silent for any token the unit has no recording
   of, so a voice can be built up a snippet at a time and a unit with none
   says nothing. What the unit has is on the golf state as `voice_have`.

   One queue: a line that arrives while another is speaking waits its turn,
   and the same line is not said twice in a row - screens repaint. */
(function () {
  const BASE = '/static/golf/voice/';
  const SFX = '/static/golf/sound/';

  /* One volume and one mute for everything the page plays - the narrator
     and the effects - remembered on this screen (a table's screen is a
     table's; a phone's is its owner's). The controls are drawn into any
     element with id "soundctl" the page has. */
  let level = 0.8, muted = false;
  try {
    const v = localStorage.getItem('elmer.sound.level'); if (v !== null) level = Math.max(0, Math.min(1, parseFloat(v)));
    muted = localStorage.getItem('elmer.sound.muted') === '1';
  } catch (e) {}
  function remember() {
    try { localStorage.setItem('elmer.sound.level', String(level)); localStorage.setItem('elmer.sound.muted', muted ? '1' : '0'); } catch (e) {}
  }
  function gain() { return muted ? 0 : level; }
  function drawControl() {
    const box = document.getElementById('soundctl');
    if (!box || box.dataset.drawn) return;
    box.dataset.drawn = '1';
    box.innerHTML = '<button type="button" class="btn sm ghost" id="sound-mute" title="mute"></button>' +
      '<input type="range" id="sound-level" min="0" max="100" step="5" title="volume" style="width:5.5rem;vertical-align:middle">';
    const b = box.querySelector('#sound-mute'), r = box.querySelector('#sound-level');
    const paint = () => { b.textContent = muted || level === 0 ? '\u{1F507}' : level < 0.5 ? '\u{1F509}' : '\u{1F50A}'; b.title = muted ? 'sound off - press for sound' : 'sound on - press to mute'; r.value = String(Math.round(level * 100)); r.disabled = muted; };
    b.addEventListener('click', () => { muted = !muted; remember(); paint(); });
    r.addEventListener('input', () => { level = parseInt(r.value, 10) / 100; muted = false; remember(); paint(); });
    paint();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', drawControl); else drawControl();

  /* The effects: short, fire-and-forget, never queued behind the voice.
     `have` is what the unit has, from the state; a name with a number
     range ("strike", 1..4) picks one at random. */
  let sfxHave = null;
  function setSfx(list) { sfxHave = Array.isArray(list) ? new Set(list) : null; }
  function sfx(name) {
    if (!gain()) return;
    let stem = name;
    if (sfxHave) {
      const pool = [...sfxHave].filter(x => x === name || x.startsWith(name + '-'));
      if (!pool.length) return;
      stem = pool[Math.floor(Math.random() * pool.length)];
    }
    try {
      const a = new Audio(SFX + encodeURIComponent(stem) + '.mp3');
      a.volume = gain();
      a.play().catch(() => {});
    } catch (e) {}
  }
  const GAP_MS = 90;                  // between snippets
  const PAUSE_MS = 60;                // for a token the unit has not recorded: a breath, not a wait
  let have = null;                    // the stems on the shelf, or null for unknown
  let queue = [];
  let speaking = false;
  let lastLine = '';

  function setHave(list) { have = Array.isArray(list) ? new Set(list) : null; }

  /* The elements still playing or loading, so a stalled request elsewhere
     on the page can say whether the narrator had the browser's connections.
     An element is let go the moment it is done: a clip that has finished
     must not keep a connection, and there are six to the whole host. */
  const playing = new Set();
  function pending() {
    return playing.size + ' clip' + (playing.size === 1 ? '' : 's') + ' open, ' + queue.length + ' line' + (queue.length === 1 ? '' : 's') + ' queued';
  }
  function playOne(token) {
    return new Promise(resolve => {
      if (have && !have.has(token)) { setTimeout(resolve, PAUSE_MS); return; }
      let done = false, a = null;
      const finish = () => {
        if (done) return;
        done = true;
        if (a) { playing.delete(a); try { a.pause(); a.removeAttribute('src'); a.load(); } catch (e) {} }
        setTimeout(resolve, GAP_MS);
      };
      try {
        a = new Audio(BASE + encodeURIComponent(token) + '.mp3');
        a.volume = gain();
        playing.add(a);
        a.addEventListener('ended', finish, {once: true});
        a.addEventListener('error', finish, {once: true});
        a.play().catch(finish);
        setTimeout(finish, token.startsWith('hole-') ? 40000 : 12000);  // a snippet is seconds; a hole read whole is longer
      } catch (e) { finish(); }
    });
  }

  async function run() {
    if (speaking) return;
    speaking = true;
    while (queue.length) {
      const tokens = queue.shift();
      for (const t of tokens) await playOne(t);
    }
    speaking = false;
  }

  /* What is said is about what is on the screen. A line that is still
     waiting when the next one arrives is about a moment that has gone -
     the address of a stroke already played - so the newest line replaces
     whatever was queued, and the narrator is never more than one line
     behind the game. The clip playing finishes; it is short. */
  function say(tokens) {
    if (!tokens || !tokens.length) return;
    if (!gain()) return;                                   // muted: nothing said, nothing queued
    if (have && !tokens.some(t => have.has(t))) return;   // nothing of it is recorded
    const line = tokens.join(' ');
    if (line === lastLine) return;
    lastLine = line;
    queue = [tokens.filter(t => !have || have.has(t))];   // the unrecorded are skipped, not waited for
    run();
  }

  window.Voice = {say: say, setHave: setHave, pending: pending, get have() { return have; }};
  window.Sfx = {play: sfx, setHave: setSfx};
  window.Sound = {get level() { return level; }, get muted() { return muted; }};
  // The narrator's hook, which the table and the phone call with what they
  // show. Tokens when the state carries them; text alone stays silent.
  window.golfCue = function (text, tokens) { if (tokens) say(tokens); };
})();
