/* CW: tone generation, copy practice, key decoding and off-air decoding.
   All the audio lives in the browser; the server supplies practice text and
   remembers which characters you actually copy. */

const CWS = window.CW || {};
const MORSE_UI = {};   // filled from the server's encode endpoint as needed

/* ------------------------------------------------------------------ audio */
/* One oscillator runs continuously and the gain is ramped for each element.
   Starting and stopping an oscillator per dit produces key clicks - the same
   wide sidebands E8D asks about - so the envelope is shaped instead. */
const RISE = 0.005;                    // 5 ms rise and fall

class CWPlayer {
  constructor() { this.ctx = null; this.osc = null; this.gain = null; }

  ensure() {
    if (!this.ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      this.ctx = new Ctx();
      this.gain = this.ctx.createGain();
      this.gain.gain.value = 0;
      this.osc = this.ctx.createOscillator();
      this.osc.type = 'sine';
      this.osc.frequency.value = settings.tone;
      this.osc.connect(this.gain);
      this.gain.connect(this.ctx.destination);
      this.osc.start();
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
    this.osc.frequency.setTargetAtTime(settings.tone, this.ctx.currentTime, 0.01);
    return this.ctx;
  }

  get level() { return Math.pow(settings.volume / 100, 2) * 0.6; }

  /* Schedule one tone. Times are AudioContext seconds. */
  mark(at, seconds) {
    const g = this.gain.gain, v = this.level;
    g.setValueAtTime(0, at);
    g.linearRampToValueAtTime(v, at + RISE);
    g.setValueAtTime(v, Math.max(at + RISE, at + seconds - RISE));
    g.linearRampToValueAtTime(0, at + seconds);
  }

  /* Key down/up for hand sending. */
  down() { this.ensure(); const t = this.ctx.currentTime;
           this.gain.gain.cancelScheduledValues(t);
           this.gain.gain.setValueAtTime(this.gain.gain.value, t);
           this.gain.gain.linearRampToValueAtTime(this.level, t + RISE); }
  up() { if (!this.ctx) return; const t = this.ctx.currentTime;
         this.gain.gain.cancelScheduledValues(t);
         this.gain.gain.setValueAtTime(this.gain.gain.value, t);
         this.gain.gain.linearRampToValueAtTime(0, t + RISE); }

  silence() {
    if (!this.ctx) return;
    this.gain.gain.cancelScheduledValues(this.ctx.currentTime);
    this.gain.gain.setValueAtTime(0, this.ctx.currentTime);
  }

  /* Play groups (from the server) with the given timing. Returns the schedule
     so the caller knows when each character lands. */
  send(groups, timing, onChar, onDone) {
    this.ensure();
    const ms = x => x / 1000;
    let t = this.ctx.currentTime + 0.15;
    const marks = [];
    groups.forEach((word, w) => {
      word.forEach((sym, i) => {
        const charStart = t;
        for (const el of sym.code) {
          const dur = ms(el === '-' ? timing.dah : timing.dit);
          this.mark(t, dur);
          t += dur + ms(timing.symbol_gap);
        }
        t -= ms(timing.symbol_gap);
        marks.push({char: sym.char, at: charStart, end: t});
        if (i < word.length - 1) t += ms(timing.char_gap);
      });
      if (w < groups.length - 1) t += ms(timing.word_gap);
    });
    const startedAt = this.ctx.currentTime;
    if (onChar) marks.forEach(m => setTimeout(
      () => onChar(m.char), Math.max(0, (m.at - startedAt) * 1000)));
    this.playingUntil = t;
    if (onDone) this.doneTimer = setTimeout(
      () => onDone(), Math.max(0, (t - startedAt) * 1000) + 120);
    marks.startedAt = startedAt;
    marks.until = t;
    return marks;
  }

  stop() {
    clearTimeout(this.doneTimer);
    this.silence();
  }
}

const player = new CWPlayer();

/* --------------------------------------------------------------- settings */
const settings = Object.assign(
  {tone: 600, volume: 35, wpm: 20, effective: 10, lesson: 2,
   /* Which keys are the paddles, and which instrument you were last using.
      Arrows to begin with because they are where a hand already is, but the
      right pair depends on the keyboard and on the operator, so they are
      settings rather than a decision made here. */
   keyer: 'straight', keyDit: 'ArrowLeft', keyDah: 'ArrowRight'},
  CWS.settings || {});

function bindSetting(id, key, fmt) {
  const el = document.getElementById(id);
  const out = document.getElementById(id + '-v');
  if (!el) return;
  el.value = settings[key];
  const show = () => { if (out) out.textContent = fmt(settings[key]); };
  show();
  el.addEventListener('input', () => {
    settings[key] = +el.value;
    if (key === 'wpm') {
      const eff = document.getElementById('cw-eff');
      if (settings.effective > settings.wpm) {
        settings.effective = settings.wpm;
        eff.value = settings.wpm;
        document.getElementById('cw-eff-v').textContent = settings.wpm + ' wpm';
      }
      eff.max = settings.wpm;
    }
    if (key === 'lesson') renderLesson();
    show();
    if (player.ctx) player.osc.frequency.setTargetAtTime(
      settings.tone, player.ctx.currentTime, 0.01);
    saveSettings();
  });
}

let saveTimer = null;
function saveSettings() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    postJSON('/api/cw/result', {per_char: {}, settings: settings}).catch(() => {});
  }, 800);
}

bindSetting('cw-tone', 'tone', v => v + ' Hz');
bindSetting('cw-vol', 'volume', v => v + '%');
bindSetting('cw-wpm', 'wpm', v => v + ' wpm');
bindSetting('cw-eff', 'effective', v => v + ' wpm');
bindSetting('cw-lesson', 'lesson', v => 'characters 1–' + v);

/* ------------------------------------------------------- the code, drawn */
/* A dit is a short sound and a dah is a long one, three times over. Printed as
   a full stop and a hyphen the eye has to translate punctuation into duration;
   drawn to length it is just the shape, which is the thing being learnt. */

function codeHTML(code) {
  return [...(code || '')].map(el =>
    '<i class="' + (el === '-' ? 'dah' : 'dit') + '"></i>').join('');
}

/* Fill every .cw-code that carries a data-code - the chart and the paddle
   levers are rendered by the template and only need their shapes putting in. */
function paintCodes(root) {
  (root || document).querySelectorAll('.cw-code[data-code]').forEach(el => {
    if (!el.dataset.painted) {
      el.innerHTML = codeHTML(el.dataset.code);
      el.dataset.painted = '1';
    }
  });
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

/* Play one character on its own and light each element as it sounds. Returns
   when the last element has finished. Scheduling is on the audio clock, so the
   tone is exact; the lighting follows it rather than the other way round. */
function playSymbol(sym, timing, boxes) {
  player.ensure();
  const ctx = player.ctx;
  let t = ctx.currentTime + 0.08;
  const start = t;
  /* One scheduling, any number of displays: the chart cell you clicked and the
     big panel above it are the same sound, and must not be two of them. */
  const rows = (Array.isArray(boxes) ? boxes : [boxes]).filter(Boolean);
  rows.forEach(box => { box.innerHTML = codeHTML(sym.code); });
  const spans = rows.map(box => [...box.querySelectorAll('i')]);
  const lit = [];
  for (const el of sym.code) {
    const dur = (el === '-' ? timing.dah : timing.dit) / 1000;
    player.mark(t, dur);
    lit.push({at: t, end: t + dur});
    t += dur + timing.symbol_gap / 1000;
  }
  const end = t - timing.symbol_gap / 1000;
  return new Promise(resolve => {
    const frame = () => {
      if (!player.ctx || teachStop) { resolve(); return; }
      const now = player.ctx.currentTime;
      lit.forEach((m, i) => {
        const on = now >= m.at && now < m.end;
        spans.forEach(row => { if (row[i]) row[i].classList.toggle('lit', on); });
      });
      if (now >= end) {
        spans.forEach(row => row.forEach(sp => sp.classList.remove('lit')));
        resolve();
      } else {
        requestAnimationFrame(frame);
      }
    };
    requestAnimationFrame(frame);
  }).then(() => ({start, end}));
}

/* Sound first, name second. The character is drawn while it sounds; the letter
   arrives afterwards and is held long enough to read. That order matters: a
   letter shown at the same time as the sound is what teaches people to
   translate rather than to hear. */
const REVEAL_MS = 2000;
let teachStop = false, teaching = false;

async function teachRun(symbols, timing, ui, opts) {
  const settle = (opts && opts.settle) || 260;
  teachStop = false;
  teaching = true;
  try {
    for (const sym of symbols) {
      if (teachStop) break;
      ui.letter.classList.remove('show');
      await playSymbol(sym, timing, ui.code);
      if (teachStop) break;
      if (ui.reveal && ui.reveal()) {
        ui.letter.innerHTML = escapeHTML(sym.char) +
          (sym.meaning ? '<small>' + escapeHTML(sym.meaning) + '</small>' : '');
        ui.letter.classList.add('show');
        await sleep(REVEAL_MS);
        ui.letter.classList.remove('show');
      }
      await sleep(settle);
    }
  } finally {
    teaching = false;
    if (ui.onDone) ui.onDone();
  }
}

function teachHalt() {
  teachStop = true;
  teaching = false;
  player.stop();
}

document.getElementById('cw-test').addEventListener('click', () => {
  player.ensure();
  player.mark(player.ctx.currentTime + 0.05, 0.35);
});

/* ------------------------------------------------------------------ modes */
function showMode(name) {
  document.querySelectorAll('#cw-modes button').forEach(b => {
    b.classList.toggle('primary', b.dataset.mode === name);
    b.classList.toggle('ghost', b.dataset.mode !== name);
  });
  document.querySelectorAll('.cw-pane').forEach(p => {
    p.hidden = p.id !== 'cw-' + name;
  });
  if (name !== 'decode') stopMic();
  teachHalt();
  if (name !== 'copy') player.stop();
  history.replaceState(null, '', '#' + name);
}
document.querySelectorAll('#cw-modes button').forEach(b =>
  b.addEventListener('click', () => showMode(b.dataset.mode)));

/* ------------------------------------------------------------------ learn */
function charClass(stat) {
  if (!stat || !stat.sent) return 'unmet';
  const rate = stat.copied / stat.sent;
  return rate >= 0.9 ? 'solid' : rate >= 0.7 ? 'shaky' : 'weak';
}

function renderLesson() {
  const chars = (CWS.koch || []).slice(0, settings.lesson);
  const box = document.getElementById('cw-lesson-chars');
  if (box) {
    /* The lesson's characters with their shapes beside them, and clickable:
       "what does K sound like again" should not need a trip to the chart. */
    box.innerHTML = chars.map(c =>
      '<button class="cw-chart-cell" data-char="' + escapeHTML(c) +
      '" data-code="' + (CODE[c] || '') + '">' +
      '<b class="' + charClass((CWS.progress || {})[c]) + '">' + escapeHTML(c) +
      '</b><span class="cw-code" data-code="' + (CODE[c] || '') + '"></span></button>'
    ).join('');
    paintCodes(box);
  }
  renderProgress();
}

function renderProgress() {
  const box = document.getElementById('cw-progress');
  if (!box) return;
  box.innerHTML = (CWS.koch || []).map(c => {
    const st = (CWS.progress || {})[c];
    let title = c + ': not met yet';
    if (st && st.sent) {
      const confused = JSON.parse(st.confused || '{}');
      const worst = Object.entries(confused).sort((a, b) => b[1] - a[1]).slice(0, 3);
      title = c + ': copied ' + st.copied + ' of ' + st.sent +
        ' (' + Math.round(100 * st.copied / st.sent) + '%)' +
        (worst.length ? ' — heard as ' + worst.map(w => w[0] + '×' + w[1]).join(', ') : '');
    }
    return '<span class="cw-char ' + charClass(st) + '" title="' +
      escapeHTML(title) + '">' + escapeHTML(c) + '</span>';
  }).join('');
}

/* The same PARIS timing the server computes, worked out here because a single
   character does not need a round trip for it. */
function localTiming() {
  const dit = 1200 / settings.wpm;
  return {dit: dit, dah: 3 * dit, symbol_gap: dit,
          char_gap: 3 * dit, word_gap: 7 * dit};
}

const teachUI = {
  code: document.getElementById('cw-teach-code'),
  letter: document.getElementById('cw-teach-letter'),
  reveal: () => document.getElementById('cw-teach-reveal').checked,
  onDone: () => {
    document.getElementById('cw-hear').hidden = false;
    document.getElementById('cw-teach-stop').hidden = true;
    document.getElementById('cw-teach-hint').textContent =
      'Press below and each character is drawn as it sounds, then named.';
  },
};

/* One character at a time with a pause you can think in. The Farnsworth
   spacing used for copy practice cannot do this: at any speed worth learning
   at, three dits of gap is a fifth of a second, and the name has to be
   readable. So the sequence is driven here instead of scheduled in one go. */
async function teachChars(symbols) {
  if (teaching) { teachHalt(); return; }
  document.getElementById('cw-hear').hidden = true;
  document.getElementById('cw-teach-stop').hidden = false;
  document.getElementById('cw-teach-hint').textContent = 'listen';
  await teachRun(symbols, localTiming(), teachUI);
}

document.getElementById('cw-hear').addEventListener('click', () => {
  const chars = (CWS.koch || []).slice(0, settings.lesson);
  teachChars(chars.map(c => ({char: c, code: CODE[c] || ''})));
});
document.getElementById('cw-teach-stop').addEventListener('click', () => {
  teachHalt();
  teachUI.onDone();
});

/* Anything drawn as a code cell plays when clicked - the chart, and the
   lesson's own characters. */
document.addEventListener('click', e => {
  const cell = e.target.closest('.cw-chart-cell');
  if (!cell || !cell.dataset.code) return;
  document.querySelectorAll('.cw-chart-cell.playing')
    .forEach(c => c.classList.remove('playing'));
  cell.classList.add('playing');
  /* Lit where it was clicked, so the shape and the sound are in the same
     place. In the lesson it also drives the big display above. */
  const own = cell.querySelector('.cw-code');
  const big = cell.closest('#cw-learn')
    ? document.getElementById('cw-teach-code') : null;
  const sym = {char: cell.dataset.char, code: cell.dataset.code};
  teachHalt();
  setTimeout(() => {
    playSymbol(sym, localTiming(), [own, big]).then(() => {
      setTimeout(() => cell.classList.remove('playing'), 200);
      if (big) {
        const letter = document.getElementById('cw-teach-letter');
        letter.innerHTML = escapeHTML(sym.char);
        letter.classList.add('show');
        setTimeout(() => letter.classList.remove('show'), REVEAL_MS);
      }
    });
  }, 30);
});
document.getElementById('cw-start-copy').addEventListener('click', () => {
  document.getElementById('cw-kind').value = 'koch';
  showMode('copy');
  sendPractice();
});

/* ------------------------------------------------------------------- copy */
let currentText = '', currentData = null, sending = false;

async function sendPractice(repeat) {
  const kind = document.getElementById('cw-kind').value;
  const status = document.getElementById('cw-copy-status');
  if (!repeat) {
    status.textContent = 'fetching…';
    currentData = await api('/api/cw/practice?' + new URLSearchParams({
      kind: kind, count: kind === 'qso' ? 1 : 5, lesson: settings.lesson,
      wpm: settings.wpm, effective: settings.effective}));
    currentText = currentData.plain || currentData.text;
    document.getElementById('cw-typed').value = '';
    document.getElementById('cw-result').innerHTML = '';
  }
  sending = true;
  document.getElementById('cw-send').hidden = true;
  document.getElementById('cw-stop').hidden = false;
  document.getElementById('cw-repeat').hidden = true;
  status.textContent = 'sending…';
  document.getElementById('cw-typed').focus();
  player.send(currentData.groups, currentData.timing, null, () => {
    sending = false;
    document.getElementById('cw-send').hidden = false;
    document.getElementById('cw-stop').hidden = true;
    document.getElementById('cw-repeat').hidden = false;
    status.textContent = 'sent — type what you heard, then check';
  });
}

document.getElementById('cw-send').addEventListener('click', () => sendPractice(false));
document.getElementById('cw-repeat').addEventListener('click', () => sendPractice(true));
document.getElementById('cw-stop').addEventListener('click', () => {
  player.stop(); sending = false;
  document.getElementById('cw-send').hidden = false;
  document.getElementById('cw-stop').hidden = true;
  document.getElementById('cw-copy-status').textContent = 'stopped';
});

document.getElementById('cw-check').addEventListener('click', async () => {
  if (!currentText) return;
  player.stop();
  const typed = (document.getElementById('cw-typed').value || '').toUpperCase();
  const sent = currentText.replace(/\s+/g, ' ').trim();
  const got = typed.replace(/\s+/g, ' ').trim();
  const a = sent.replace(/ /g, ''), b = got.replace(/ /g, '');

  const perChar = {}, marks = [];
  let hits = 0;
  for (let i = 0; i < a.length; i++) {
    const want = a[i], had = b[i] || '';
    const ok = want === had;
    hits += ok ? 1 : 0;
    perChar[want] = perChar[want] || {sent: 0, copied: 0, confused: {}};
    perChar[want].sent++;
    if (ok) perChar[want].copied++;
    else if (had) perChar[want].confused[had] = (perChar[want].confused[had] || 0) + 1;
    marks.push('<span class="' + (ok ? 'cw-hit' : 'cw-miss') + '">' +
      escapeHTML(want) + (ok ? '' : '<i>' + escapeHTML(had || '·') + '</i>') + '</span>');
  }
  const pct = a.length ? Math.round(100 * hits / a.length) : 0;
  const meanings = currentData.meanings || {};
  const glossary = Object.keys(meanings).length
    ? '<div class="small muted mt">' + Object.entries(meanings).map(
        ([w, m]) => '<b class="mono">' + escapeHTML(w) + '</b> ' + escapeHTML(m)
      ).join(' &middot; ') + '</div>'
    : '';

  document.getElementById('cw-result').innerHTML =
    '<div class="spread"><b>' + pct + '% copied</b>' +
    '<span class="pill ' + (pct >= 90 ? 'good' : pct >= 70 ? 'warn' : 'bad') + '">' +
      (pct >= 90 ? 'ready for the next character' : pct >= 70 ? 'nearly' : 'more of this one') +
    '</span></div>' +
    '<div class="cw-compare mt">' + marks.join('') + '</div>' +
    '<div class="tiny muted" style="margin-top:.4rem">sent: <span class="mono">' +
      escapeHTML((currentData.text || sent).replace(/\s+/g, ' ').trim()) +
      '</span></div>' + glossary;

  const res = await postJSON('/api/cw/result',
    {per_char: perChar, settings: settings}).catch(() => null);
  if (res && res.progress) { CWS.progress = res.progress; renderProgress(); }
  if (pct >= 90 && settings.lesson < (CWS.koch || []).length &&
      document.getElementById('cw-kind').value === 'koch') {
    toast('Lesson passed', 'Add ' + CWS.koch[settings.lesson] +
          ' — move the lesson slider up one.');
  }
});

/* -------------------------------------------------------------- send text */
/* Type a sentence and hear it. The characters are drawn as they sound and
   named as they pass, and the line builds up underneath, so it can be read as
   well as heard - which is how you find out that <BT> is one sound. */

let textSending = false;

async function sendTypedText() {
  const input = document.getElementById('cw-text-input');
  const status = document.getElementById('cw-text-status');
  const line = document.getElementById('cw-text-line');
  const text = (input.value || '').trim();
  if (!text) { status.textContent = 'nothing to send'; input.focus(); return; }

  status.textContent = 'encoding…';
  let data;
  try {
    data = await api('/api/cw/encode?' + new URLSearchParams(
      {text: text, wpm: settings.wpm, effective: settings.effective}));
  } catch (e) {
    status.textContent = 'could not encode that';
    return;
  }
  if (!data.characters) {
    status.textContent = 'nothing in there has a Morse equivalent';
    return;
  }
  textSending = true;
  document.getElementById('cw-text-send').hidden = true;
  document.getElementById('cw-text-stop').hidden = false;
  /* The skipped characters outlive the sending. Somebody who typed a semicolon
     needs to know the code has no semicolon, and that is still true a second
     after the last dah - so it is kept, not replaced by "sent". */
  const skipped = data.skipped.length
    ? ' — no code for ' + data.skipped.map(c => '"' + c + '"').join(' ') +
      ', so ' + (data.skipped.length === 1 ? 'it was' : 'they were') + ' skipped'
    : '';
  const heading = data.characters + ' characters at ' +
    Math.round(data.timing.wpm) + ' wpm' +
    (data.timing.farnsworth
      ? ' (spaced as ' + Math.round(data.timing.effective_wpm) + ')' : '');
  status.textContent = heading + skipped;
  line.textContent = '';

  const sched = player.send(data.groups, data.timing, null, () => {
    textSending = false;
    document.getElementById('cw-text-send').hidden = false;
    document.getElementById('cw-text-stop').hidden = true;
    document.getElementById('cw-text-code').innerHTML = '';
    document.getElementById('cw-text-letter').classList.remove('show');
    status.textContent = 'sent' + skipped;
  });

  /* Follow the schedule rather than re-timing it: the audio is already laid
     out on the audio clock, and the display should agree with the ear. */
  const codeBox = document.getElementById('cw-text-code');
  const letterBox = document.getElementById('cw-text-letter');
  const words = data.groups;
  const flat = [];
  words.forEach((w, wi) => w.forEach(sym => flat.push({sym: sym, word: wi})));
  let shown = -1, lastWord = -1;

  const follow = () => {
    if (!textSending || !player.ctx) return;
    const now = player.ctx.currentTime;
    let at = -1;
    for (let i = 0; i < sched.length; i++) if (now >= sched[i].at) at = i;
    if (at >= 0 && at !== shown) {
      shown = at;
      const item = flat[at];
      codeBox.innerHTML = codeHTML(item.sym.code);
      letterBox.textContent = item.sym.char;
      letterBox.classList.add('show');
      if (item.word !== lastWord && lastWord >= 0) line.textContent += ' ';
      lastWord = item.word;
      line.textContent += item.sym.char;
    }
    if (at >= 0) {
      const spans = codeBox.querySelectorAll('i');
      const sym = flat[at].sym;
      let t = sched[at].at;
      [...sym.code].forEach((el, i) => {
        const dur = (el === '-' ? data.timing.dah : data.timing.dit) / 1000;
        if (spans[i]) spans[i].classList.toggle('lit', now >= t && now < t + dur);
        t += dur + data.timing.symbol_gap / 1000;
      });
    }
    requestAnimationFrame(follow);
  };
  requestAnimationFrame(follow);
}

const textSendBtn = document.getElementById('cw-text-send');
if (textSendBtn) {
  textSendBtn.addEventListener('click', sendTypedText);
  document.getElementById('cw-text-stop').addEventListener('click', () => {
    textSending = false;
    player.stop();
    document.getElementById('cw-text-send').hidden = false;
    document.getElementById('cw-text-stop').hidden = true;
    document.getElementById('cw-text-status').textContent = 'stopped';
  });
  /* Ctrl+Enter sends, because the box is a textarea and Enter is a newline. */
  document.getElementById('cw-text-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      sendTypedText();
    }
  });
}

/* ------------------------------------------------------- decoding tables */
const CODE = {
  'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
  'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
  'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
  'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
  'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.----', '2': '..---',
  '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...',
  '8': '---..', '9': '----.', '.': '.-.-.-', ',': '--..--', '?': '..--..',
  '/': '-..-.', '=': '-...-', '+': '.-.-.', '-': '-....-', ':': '---...',
  '(': '-.--.', ')': '-.--.-', '"': '.-..-.', "'": '.----.', '@': '.--.-.',
  '!': '-.-.--',
};
const FROM_CODE = {};
Object.keys(CODE).forEach(c => { FROM_CODE[CODE[c]] = c; });
const PROSIGN_CODE = {'.-.-.': 'AR', '...-.-': 'SK', '-...-': 'BT',
                      '-.--.': 'KN', '.-...': 'AS', '........': 'HH'};

function codeToChar(code) {
  return FROM_CODE[code] || PROSIGN_CODE[code] || '?';
}

/* A decoder shared by hand keying and off-air audio. Both produce a stream of
   mark and space durations; only the source differs. */
class MorseDecoder {
  constructor(ditMs) { this.reset(ditMs); }

  reset(ditMs) {
    this.dit = ditMs || 60;
    this.adaptive = !ditMs;
    this.symbols = [];       // current character
    this.text = '';
    this.marks = [];         // observed mark durations
    this.gaps = [];
  }

  /* Estimate the dit from the marks seen so far: the short cluster's median.
     A fist that is not the speed you asked for still decodes. */
  learn(ms) {
    this.marks.push(ms);
    if (this.marks.length > 60) this.marks.shift();
    if (!this.adaptive || this.marks.length < 6) return;
    const sorted = this.marks.slice().sort((a, b) => a - b);
    /* Split on twice the shortest marks rather than the median. A median split
       fails whenever dahs outnumber dits - it lands inside the dah cluster and
       the estimated dit comes out three times too long, after which every dit
       reads as a dah. A low percentile resists a single clipped mark. */
    const base = sorted[Math.floor(sorted.length * 0.15)];
    const top = sorted[Math.floor(sorted.length * 0.85)];
    /* Only adapt once both kinds of mark have actually been heard. A run of
       nothing but dahs looks exactly like a run of nothing but dits, so
       guessing there would relabel every dah as a dit; keeping the previous
       estimate decodes it correctly instead. */
    if (top < base * 2) return;
    const shorts = sorted.filter(m => m <= base * 2);
    if (shorts.length) this.dit = shorts[Math.floor(shorts.length / 2)];
  }

  mark(ms) {
    this.learn(ms);
    this.symbols.push(ms < this.dit * 2 ? '.' : '-');
  }

  space(ms) {
    this.gaps.push(ms);
    if (this.gaps.length > 60) this.gaps.shift();
    if (ms < this.dit * 2) return;                     // inside a character
    this.flush();
    if (ms >= this.dit * 5) this.text += ' ';
  }

  flush() {
    if (!this.symbols.length) return;
    this.text += codeToChar(this.symbols.join(''));
    this.symbols = [];
  }

  stats() {
    const dits = this.marks.filter(m => m < this.dit * 2);
    const dahs = this.marks.filter(m => m >= this.dit * 2);
    const mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;
    return {dit: mean(dits), dah: mean(dahs),
            gap: mean(this.gaps.filter(g => g < this.dit * 2)),
            charGap: mean(this.gaps.filter(g => g >= this.dit * 2 && g < this.dit * 5)),
            count: this.marks.length};
  }
}

function timingReport(stats, targetDit) {
  if (!stats.count) return '<span class="muted small">nothing sent yet</span>';
  const row = (label, value, target) => {
    if (value === null) return '';
    const pct = target ? Math.round(100 * (value - target) / target) : 0;
    const off = Math.abs(pct);
    const cls = off <= 10 ? 'good' : off <= 25 ? 'warn' : 'bad';
    const width = Math.max(4, Math.min(100, (value / (targetDit * 4)) * 100));
    return '<tr><td>' + label + '</td>' +
      '<td class="mono">' + Math.round(value) + ' ms</td>' +
      '<td class="mono muted">target ' + Math.round(target) + '</td>' +
      '<td style="width:40%"><div class="meter thin"><i class="fill-' +
        (cls === 'good' ? 'high' : cls === 'warn' ? 'mid' : 'low') +
        '" style="width:' + width.toFixed(1) + '%"></i></div></td>' +
      '<td><span class="pill ' + cls + '">' + (pct >= 0 ? '+' : '') + pct + '%</span></td></tr>';
  };
  const ratio = stats.dit && stats.dah ? stats.dah / stats.dit : null;
  return '<table class="data" style="max-width:640px"><tbody>' +
    row('dit', stats.dit, targetDit) +
    row('dah', stats.dah, targetDit * 3) +
    row('gap inside a character', stats.gap, targetDit) +
    row('gap between characters', stats.charGap, targetDit * 3) +
    '</tbody></table>' +
    (ratio ? '<div class="small muted mt">Your dah to dit ratio is <b>' +
      ratio.toFixed(2) + '</b> against a target of 3.00. ' +
      (ratio > 3.4 ? 'Long dahs are the commonest swing, and they make you harder to copy at speed.'
       : ratio < 2.6 ? 'Short dahs blur into dits for anyone copying you.'
       : 'That is a clean fist.') + '</div>' : '');
}

/* -------------------------------------------------------- hand key input */
/* Two instruments, not one. A straight key is a switch and every bit of the
   timing is yours - which is what the chart below measures. A paddle is not:
   you ask for dits and dahs and the keyer makes them, perfectly, and what you
   are practising is which lever to hold and when to let go. Both belong here,
   because most people learning to send now learn on a paddle. */

const keyDecoder = new MorseDecoder(1200 / settings.wpm);
let keyerMode = settings.keyer || 'straight';   // 'straight' | 'A' | 'B'

/* KeyboardEvent.code is what gets stored - it names the physical key, so a
   binding survives a change of layout - but nobody wants to read "BracketLeft"
   on a paddle, so it is printed the way the key is printed. */
const KEY_LABELS = {
  ArrowLeft: '\u2190', ArrowRight: '\u2192', ArrowUp: '\u2191',
  ArrowDown: '\u2193', Space: 'Space', Enter: 'Enter', Tab: 'Tab',
  ControlLeft: 'L Ctrl', ControlRight: 'R Ctrl',
  ShiftLeft: 'L Shift', ShiftRight: 'R Shift',
  AltLeft: 'L Alt', AltRight: 'R Alt',
  MetaLeft: 'L Meta', MetaRight: 'R Meta',
  Comma: ',', Period: '.', Slash: '/', Semicolon: ';', Quote: "'",
  BracketLeft: '[', BracketRight: ']', Backslash: '\\', Backquote: '`',
  Minus: '-', Equal: '=', CapsLock: 'Caps',
};

function keyLabel(code) {
  if (KEY_LABELS[code]) return KEY_LABELS[code];
  if (/^Key[A-Z]$/.test(code)) return code.slice(3);
  if (/^Digit\d$/.test(code)) return code.slice(5);
  if (/^Numpad/.test(code)) return 'Num ' + code.slice(6);
  return code;
}

function paintBindings() {
  const d = document.getElementById('cw-kbd-dit');
  const h = document.getElementById('cw-kbd-dah');
  if (d && !d.classList.contains('listening')) d.textContent = keyLabel(settings.keyDit);
  if (h && !h.classList.contains('listening')) h.textContent = keyLabel(settings.keyDah);
}

/* Rebinding: click the key, press the one you want. Assigning a key that the
   other paddle already has swaps them rather than leaving both on it, because
   a binding screen that can produce a broken state is a worse binding screen. */
let capturing = null;

function startCapture(which) {
  if (capturing) stopCapture();
  capturing = which;
  const el = document.getElementById('cw-kbd-' + which);
  el.classList.add('listening');
  el.textContent = 'press a key';
}

function stopCapture() {
  if (!capturing) return;
  document.getElementById('cw-kbd-' + capturing).classList.remove('listening');
  capturing = null;
  paintBindings();
}

document.addEventListener('keydown', e => {
  if (!capturing) return;
  e.preventDefault();
  e.stopPropagation();
  if (e.code === 'Escape') { stopCapture(); return; }
  const mine = capturing === 'dit' ? 'keyDit' : 'keyDah';
  const other = capturing === 'dit' ? 'keyDah' : 'keyDit';
  if (settings[other] === e.code) settings[other] = settings[mine];
  settings[mine] = e.code;
  stopCapture();
  saveSettings();
}, true);

const KEY_BLURB = {
  straight:
    'Hold the space bar, or the key below, as a straight key. ELMER decodes ' +
    'what you actually sent and measures your timing \u2014 you cannot hear ' +
    'your own swing, but the chart can show it to you.',
  A:
    'The two keys below, or the levers themselves, are the paddles. Hold one ' +
    'for a run of dits or dahs; squeeze both and it alternates. Curtis A: ' +
    'when you let go, the element in progress finishes and it stops.',
  B:
    'The two keys below, or the levers themselves, are the paddles. Curtis B: ' +
    'releasing both during an element still owes you the opposite one, so a ' +
    'squeezed dit-dah comes out complete even if you let go early. If that ' +
    'sounds like an extra element you did not ask for, you want A.',
};

/* ------------------------------------------------------------ straight key */
let keyDown = false, keyDownAt = 0, lastUpAt = 0, keyIdle = null;

function keyStart() {
  if (keyDown || keyerMode !== 'straight') return;
  keyDown = true;
  const now = performance.now();
  if (lastUpAt) keyDecoder.space(now - lastUpAt);
  keyDownAt = now;
  player.down();
  document.getElementById('cw-paddle').classList.add('down');
  renderKey();
}
function keyEnd() {
  if (!keyDown) return;
  keyDown = false;
  const now = performance.now();
  keyDecoder.mark(now - keyDownAt);
  lastUpAt = now;
  player.up();
  document.getElementById('cw-paddle').classList.remove('down');
  renderKey();
  clearTimeout(keyIdle);
  keyIdle = setTimeout(() => { keyDecoder.flush(); renderKey(); }, 1400);
}

/* ------------------------------------------------------------ iambic keyer */
/* The keyer owns the clock. Elements are laid on the audio timeline so they
   are exact, and the decoder is told the same figures rather than a
   measurement of them - there is nothing to measure, which is the point of a
   keyer and worth saying plainly under the chart. */

class IambicKeyer {
  constructor(decoder) {
    this.decoder = decoder;
    this.ditDown = this.dahDown = false;
    this.ditMem = this.dahMem = false;
    this.squeezed = false;
    this.last = null;
    this.running = false;
    this.prevEnd = null;
    this.nextAt = 0;
    this.timer = null;
  }

  get ditMs() { return 1200 / settings.wpm; }

  press(which) {
    if (this[which + 'Down']) return;
    this[which + 'Down'] = true;
    if (this.running) {
      this[which + 'Mem'] = true;
      if (this.ditDown && this.dahDown) this.squeezed = true;
    }
    this.paint();
    if (!this.running) this.start();
  }

  release(which) {
    this[which + 'Down'] = false;
    this.paint();
  }

  /* What to send next, from the paddles, the memory, and - in mode B - the
     squeeze that was on when this element began. */
  decide() {
    const dit = this.ditDown || this.ditMem;
    const dah = this.dahDown || this.dahMem;
    if (dit && dah) return this.last === 'dit' ? 'dah' : 'dit';
    if (dit) return 'dit';
    if (dah) return 'dah';
    if (keyerMode === 'B' && this.squeezed) {
      this.squeezed = false;
      return this.last === 'dit' ? 'dah' : 'dit';
    }
    return null;
  }

  start() {
    player.ensure();
    this.running = true;
    this.nextAt = player.ctx.currentTime + 0.012;
    this.step();
  }

  step() {
    const element = this.decide();
    if (!element) {
      this.running = false;
      this.squeezed = false;
      clearTimeout(keyIdle);
      keyIdle = setTimeout(() => { this.decoder.flush(); renderKey(); }, 1400);
      this.paint();
      renderKey();
      return;
    }
    const dit = this.ditMs;
    const ms = element === 'dit' ? dit : dit * 3;
    const ctx = player.ctx;
    const at = Math.max(ctx.currentTime + 0.008, this.nextAt);

    player.mark(at, ms / 1000);
    if (this.prevEnd !== null) {
      const gap = (at - this.prevEnd) * 1000;
      if (gap > 1) this.decoder.space(gap);
    }
    this.decoder.mark(ms);
    this.prevEnd = at + ms / 1000;

    this[element + 'Mem'] = false;
    this.last = element;
    this.squeezed = this.ditDown && this.dahDown;
    this.nextAt = at + (ms + dit) / 1000;

    clearTimeout(keyIdle);
    renderKey();
    this.timer = setTimeout(() => this.step(),
      Math.max(0, (this.nextAt - ctx.currentTime) * 1000 - 4));
  }

  stop() {
    clearTimeout(this.timer);
    this.running = false;
    this.ditDown = this.dahDown = this.ditMem = this.dahMem = false;
    this.squeezed = false;
    this.prevEnd = null;
    player.silence();
    this.paint();
  }

  paint() {
    const d = document.getElementById('cw-lever-dit');
    const h = document.getElementById('cw-lever-dah');
    if (d) d.classList.toggle('down', this.ditDown);
    if (h) h.classList.toggle('down', this.dahDown);
  }
}

const keyer = new IambicKeyer(keyDecoder);

function renderKey() {
  document.getElementById('cw-key-raw').textContent =
    keyDecoder.symbols.join('') || '\u00b7';
  document.getElementById('cw-key-decoded').textContent =
    keyDecoder.text || '\u2014';
  const box = document.getElementById('cw-key-timing');
  if (keyerMode === 'straight') {
    box.innerHTML = timingReport(keyDecoder.stats(), 1200 / settings.wpm);
  } else {
    /* Showing a timing chart here would be theatre: it grades the keyer, and
       the keyer is a machine set to the speed above. It will always be
       perfect, which tells you nothing about your sending. */
    box.innerHTML = '<div class="small muted">The keyer is making the ' +
      'elements, so the timing below is its own and always perfect \u2014 ' +
      'there is nothing of your fist in it to measure. What a paddle asks of ' +
      'you is which lever, and when to let go: watch the decoded line above ' +
      'and see whether you got the character you meant. Switch to the ' +
      'straight key to have your timing measured.</div>';
  }
}

function setKeyerMode(mode, remember) {
  keyerMode = mode;
  settings.keyer = mode;
  stopCapture();
  keyer.stop();
  keyEnd();
  document.querySelectorAll('#cw-keyer-modes button').forEach(b => {
    b.classList.toggle('primary', b.dataset.keyer === mode);
    b.classList.toggle('ghost', b.dataset.keyer !== mode);
  });
  const straight = mode === 'straight';
  document.getElementById('cw-paddle').hidden = !straight;
  document.getElementById('cw-levers').hidden = straight;
  document.getElementById('cw-swap').hidden = straight;
  document.getElementById('cw-bind-hint').hidden = straight;
  document.getElementById('cw-key-blurb').textContent = KEY_BLURB[mode];
  paintBindings();
  renderKey();
  if (remember !== false) saveSettings();
}

/* --------------------------------------------------------------- bindings */
const paddle = document.getElementById('cw-paddle');
if (paddle) {
  paddle.addEventListener('mousedown', e => { e.preventDefault(); keyStart(); });
  paddle.addEventListener('touchstart', e => { e.preventDefault(); keyStart(); });
  ['mouseup', 'mouseleave', 'touchend'].forEach(ev =>
    paddle.addEventListener(ev, e => { e.preventDefault(); keyEnd(); }));

  ['dit', 'dah'].forEach(which => {
    const el = document.getElementById('cw-lever-' + which);
    if (!el) return;
    el.addEventListener('mousedown', e => { e.preventDefault(); keyer.press(which); });
    el.addEventListener('touchstart', e => { e.preventDefault(); keyer.press(which); });
    ['mouseup', 'mouseleave', 'touchend'].forEach(ev =>
      el.addEventListener(ev, e => { e.preventDefault(); keyer.release(which); }));

    /* The key sits inside the lever, and pressing the lever is how you send -
       so clicking the key to rebind it must not also key the transmitter. */
    const kbd = document.getElementById('cw-kbd-' + which);
    ['mousedown', 'touchstart'].forEach(ev =>
      kbd.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); }));
    ['click', 'touchend'].forEach(ev =>
      kbd.addEventListener(ev, e => {
        e.preventDefault(); e.stopPropagation(); startCapture(which);
      }));
  });

  document.getElementById('cw-key-clear').addEventListener('click', () => {
    keyDecoder.reset(1200 / settings.wpm);
    lastUpAt = 0; keyer.prevEnd = null;
    renderKey();
  });
  /* With the keys assignable, reversing the paddles is just exchanging two
     bindings - so it is an action, not a mode the levers have to lie about. */
  document.getElementById('cw-swap').addEventListener('click', () => {
    const was = settings.keyDit;
    settings.keyDit = settings.keyDah;
    settings.keyDah = was;
    stopCapture();
    paintBindings();
    saveSettings();
  });
  document.querySelectorAll('#cw-keyer-modes button').forEach(b =>
    b.addEventListener('click', () => setKeyerMode(b.dataset.keyer)));
}

document.addEventListener('keydown', e => {
  if (isTyping(e) || document.getElementById('cw-key').hidden || e.repeat) return;
  if (keyerMode === 'straight') {
    if (e.code !== 'Space') return;
    e.preventDefault();
    keyStart();
    return;
  }
  if (e.code === settings.keyDit) { e.preventDefault(); keyer.press('dit'); }
  else if (e.code === settings.keyDah) { e.preventDefault(); keyer.press('dah'); }
});

document.addEventListener('keyup', e => {
  if (isTyping(e) || document.getElementById('cw-key').hidden) return;
  if (keyerMode === 'straight') {
    if (e.code !== 'Space') return;
    e.preventDefault();
    keyEnd();
    return;
  }
  if (e.code === settings.keyDit) { e.preventDefault(); keyer.release('dit'); }
  else if (e.code === settings.keyDah) { e.preventDefault(); keyer.release('dah'); }
});

/* --------------------------------------------------------- off-air decode */
let micStream = null, micCtx = null, micTimer = null, micDecoder = null;
let micState = {on: false, since: 0, floor: 0.0001, peak: 0.001, bin: 0};

async function startMic() {
  const status = document.getElementById('cw-mic-status');
  try {
    micStream = await navigator.mediaDevices.getUserMedia({audio: {
      echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
  } catch (e) {
    status.innerHTML = '<span style="color:var(--red)">no microphone — ' +
      escapeHTML(e.name === 'NotAllowedError' ? 'permission refused'
                 : e.message) + '</span>';
    return;
  }
  const Ctx = window.AudioContext || window.webkitAudioContext;
  micCtx = new Ctx();
  const source = micCtx.createMediaStreamSource(micStream);
  const analyser = micCtx.createAnalyser();
  analyser.fftSize = 2048;
  analyser.smoothingTimeConstant = 0.1;
  source.connect(analyser);

  const bins = new Float32Array(analyser.frequencyBinCount);
  const hz = micCtx.sampleRate / analyser.fftSize;
  const lo = Math.floor(250 / hz), hi = Math.ceil(1400 / hz);
  micDecoder = new MorseDecoder(null);          // adaptive: learn their speed
  micState = {on: false, since: performance.now(), floor: 1e-4, peak: 1e-3, bin: 0};
  document.getElementById('cw-mic').hidden = true;
  document.getElementById('cw-mic-stop').hidden = false;
  status.textContent = 'listening';

  const scope = document.getElementById('cw-scope');
  const g2d = scope.getContext('2d');
  const trace = [];

  micTimer = setInterval(() => {
    analyser.getFloatFrequencyData(bins);
    let best = lo, bestDb = -Infinity;
    for (let i = lo; i <= hi && i < bins.length; i++) {
      if (bins[i] > bestDb) { bestDb = bins[i]; best = i; }
    }
    const level = Math.pow(10, bestDb / 20);
    micState.bin = best;
    micState.peak = Math.max(micState.peak * 0.995, level);
    micState.floor = Math.min(micState.floor * 1.005 + 1e-7, level);
    const threshold = micState.floor + (micState.peak - micState.floor) * 0.35;
    const on = level > threshold && micState.peak > micState.floor * 3;

    const now = performance.now();
    if (on !== micState.on) {
      const held = now - micState.since;
      if (held > 8) {                       // ignore contact bounce and clicks
        if (micState.on) micDecoder.mark(held); else micDecoder.space(held);
        micState.since = now;
        micState.on = on;
      }
    }
    trace.push(on ? 1 : 0);
    if (trace.length > scope.width) trace.shift();

    g2d.clearRect(0, 0, scope.width, scope.height);
    g2d.strokeStyle = '#3fb950'; g2d.lineWidth = 2; g2d.beginPath();
    trace.forEach((v, i) => {
      const y = v ? 14 : scope.height - 14;
      i ? g2d.lineTo(i, y) : g2d.moveTo(i, y);
    });
    g2d.stroke();

    document.getElementById('cw-mic-freq').textContent =
      Math.round(best * hz) + ' Hz';
    document.getElementById('cw-mic-wpm').textContent =
      micDecoder.marks.length >= 6
        ? Math.round(1200 / micDecoder.dit) + ' wpm' : '—';
    document.getElementById('cw-mic-decoded').textContent =
      micDecoder.text.slice(-400) || '—';
  }, 8);
}

function stopMic() {
  clearInterval(micTimer); micTimer = null;
  if (micStream) micStream.getTracks().forEach(t => t.stop());
  if (micCtx) micCtx.close();
  micStream = null; micCtx = null;
  const start = document.getElementById('cw-mic');
  if (start) { start.hidden = false; document.getElementById('cw-mic-stop').hidden = true; }
}

const micBtn = document.getElementById('cw-mic');
if (micBtn) {
  micBtn.addEventListener('click', startMic);
  document.getElementById('cw-mic-stop').addEventListener('click', () => {
    stopMic();
    document.getElementById('cw-mic-status').textContent = 'stopped';
  });
  const scope = document.getElementById('cw-scope');
  const fit = () => { scope.width = scope.clientWidth; };
  window.addEventListener('resize', fit);
  fit();
}

/* ------------------------------------------------------------------ start */
paintCodes();
renderLesson();
setKeyerMode(settings.keyer || 'straight', false);
showMode((location.hash || '#learn').replace('#', '') || 'learn');
