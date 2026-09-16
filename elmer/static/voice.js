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
  const GAP_MS = 90;                  // between snippets
  const PAUSE_MS = 350;               // for a token the unit has not recorded
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

  function say(tokens) {
    if (!tokens || !tokens.length) return;
    if (have && !tokens.some(t => have.has(t))) return;   // nothing of it is recorded
    const line = tokens.join(' ');
    if (line === lastLine) return;
    lastLine = line;
    queue.push(tokens.slice());
    run();
  }

  window.Voice = {say: say, setHave: setHave, pending: pending, get have() { return have; }};
  // The narrator's hook, which the table and the phone call with what they
  // show. Tokens when the state carries them; text alone stays silent.
  window.golfCue = function (text, tokens) { if (tokens) say(tokens); };
})();
