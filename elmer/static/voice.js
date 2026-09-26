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


  /* The engine every sound goes through.

     A phone will not play a sound the page starts on its own. It plays one
     started inside a tap, and after that - once audio has been unlocked -
     it plays whatever the page likes. A fresh <audio> element made for each
     clip, which is how this played everything, is a new request to play
     every time, and a phone refuses nearly all of them: the laptop at the
     table talked, the phones in the players' hands said nothing.

     So there is one Web Audio context for the page. The first tap or key
     press anywhere - joining, Ready, an answer - resumes it and plays a
     moment of silence through it, which is what unlocks it on an iPhone as
     well as on Android; every clip after is decoded once, kept, and played
     through it with no tap needed. On an iPhone it also asks, where Safari
     allows, for playback audio, so the ring/silent switch does not mute the
     game the way it mutes a web page's beeps. A browser with no Web Audio
     plays the old way. */
  const Ctx = window.AudioContext || window.webkitAudioContext;
  let ctx = null;
  const buffers = new Map();            // url -> Promise<AudioBuffer|null>
  const BUFFER_KEEP = 80;
  function engine() {
    if (!Ctx) return null;
    if (!ctx) {
      try { ctx = new Ctx(); } catch (e) { return null; }
    }
    return ctx;
  }
  function unlock() {
    try {
      if (navigator.audioSession && navigator.audioSession.type !== 'playback') navigator.audioSession.type = 'playback';
    } catch (e) { /* not this Safari - the switch will have its say */ }
    const c = engine();
    if (!c) return;
    if (c.state !== 'running' && c.resume) c.resume().catch(() => {});
    try {
      // a moment of silence, inside the tap: what an iPhone wants to see
      const b = c.createBuffer(1, 1, 22050), src = c.createBufferSource();
      src.buffer = b; src.connect(c.destination); src.start(0);
    } catch (e) { /* the resume above is the part that matters elsewhere */ }
  }
  ['pointerdown', 'touchend', 'keydown', 'click'].forEach(ev =>
    document.addEventListener(ev, unlock, {capture: true, passive: true}));
  // Back from the lock screen or another app, a phone suspends the context;
  // it is resumed on the next tap by the listeners above, and tried here.
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && ctx && ctx.state !== 'running' && ctx.resume) ctx.resume().catch(() => {});
  });
  function load(url) {
    if (buffers.has(url)) return buffers.get(url);
    const c = engine();
    const got = fetch(url).then(r => r.ok ? r.arrayBuffer() : null).then(raw => raw && new Promise(res => {
      try { c.decodeAudioData(raw, res, () => res(null)); } catch (e) { res(null); }
    })).catch(() => null);
    buffers.set(url, got);
    if (buffers.size > BUFFER_KEEP) buffers.delete(buffers.keys().next().value);
    return got;
  }
  const playing = new Set();
  /* Play one clip. Resolves when it has finished, or could not play. */
  function playUrl(url, volume, most) {
    return new Promise(resolve => {
      let done = false, handle = null;
      const finish = () => {
        if (done) return;
        done = true;
        if (handle) { playing.delete(handle); try { handle.stop ? handle.stop() : (handle.pause(), handle.removeAttribute('src'), handle.load()); } catch (e) {} }
        resolve();
      };
      setTimeout(finish, most || 12000);
      const c = ctx;
      if (c && c.state === 'running') {
        load(url).then(buf => {
          if (done || !buf) { finish(); return; }
          try {
            const src = c.createBufferSource(), g = c.createGain();
            g.gain.value = volume;
            src.buffer = buf;
            src.connect(g); g.connect(c.destination);
            handle = src; playing.add(src);
            src.onended = finish;
            src.start(0);
          } catch (e) { finish(); }
        });
        return;
      }
      // Not unlocked, or no Web Audio: the old way, which a desktop plays.
      try {
        const a = new Audio(url);
        a.volume = volume;
        handle = a; playing.add(a);
        a.addEventListener('ended', finish, {once: true});
        a.addEventListener('error', finish, {once: true});
        a.play().catch(finish);
      } catch (e) { finish(); }
    });
  }

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
    playUrl(SFX + encodeURIComponent(stem) + '.mp3', gain(), 8000);
  }
  const GAP_MS = 90;                  // between snippets
  const PAUSE_MS = 60;                // for a token the unit has not recorded: a breath, not a wait
  let have = null;                    // the stems on the shelf, or null for unknown
  let queue = [];
  let speaking = false;
  let lastLine = '';

  function setHave(list) { have = Array.isArray(list) ? new Set(list) : null; }

  /* The clips still playing or loading, so a stalled request elsewhere on
     the page can say whether the narrator had the browser's connections. A
     clip is let go the moment it is done. */
  function pending() {
    return playing.size + ' clip' + (playing.size === 1 ? '' : 's') + ' open, ' + queue.length + ' line' + (queue.length === 1 ? '' : 's') + ' queued';
  }
  function playOne(token) {
    if (have && !have.has(token)) return new Promise(resolve => setTimeout(resolve, PAUSE_MS));
    // a snippet is seconds; a hole read whole is longer
    return playUrl(BASE + encodeURIComponent(token) + '.mp3', gain(), token.startsWith('hole-') ? 40000 : 12000)
      .then(() => new Promise(resolve => setTimeout(resolve, GAP_MS)));
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

  window.Voice = {say: say, setHave: setHave, pending: pending, get have() { return have; },
                  // whether this screen can make a sound without a tap first
                  get unlocked() { return !!(ctx && ctx.state === 'running'); }, unlock: unlock};
  window.Sfx = {play: sfx, setHave: setSfx};
  window.Sound = {get level() { return level; }, get muted() { return muted; }};
  // The narrator's hook, which the table and the phone call with what they
  // show. Tokens when the state carries them; text alone stays silent.
  window.golfCue = function (text, tokens) { if (tokens) say(tokens); };
})();
