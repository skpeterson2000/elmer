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
  {tone: 600, volume: 35, wpm: 20, effective: 10, lesson: 2},
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
  if (box) box.innerHTML = chars.map(c =>
    '<span class="cw-char ' + charClass((CWS.progress || {})[c]) + '">' +
    escapeHTML(c) + '</span>').join('');
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

document.getElementById('cw-hear').addEventListener('click', async () => {
  const chars = (CWS.koch || []).slice(0, settings.lesson).join(' ');
  const data = await api('/api/cw/encode?' + new URLSearchParams(
    {text: chars, wpm: settings.wpm, effective: Math.min(settings.effective, 12)}));
  player.send(data.groups, data.timing);
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
    currentText = currentData.text;
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
      escapeHTML(sent) + '</span></div>' + glossary;

  const res = await postJSON('/api/cw/result',
    {per_char: perChar, settings: settings}).catch(() => null);
  if (res && res.progress) { CWS.progress = res.progress; renderProgress(); }
  if (pct >= 90 && settings.lesson < (CWS.koch || []).length &&
      document.getElementById('cw-kind').value === 'koch') {
    toast('Lesson passed', 'Add ' + CWS.koch[settings.lesson] +
          ' — move the lesson slider up one.');
  }
});

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
const keyDecoder = new MorseDecoder(1200 / settings.wpm);
let keyDown = false, keyDownAt = 0, lastUpAt = 0;

function keyStart() {
  if (keyDown) return;
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
let keyIdle = null;

function renderKey() {
  document.getElementById('cw-key-raw').textContent =
    keyDecoder.symbols.join('') || '·';
  document.getElementById('cw-key-decoded').textContent =
    keyDecoder.text || '—';
  document.getElementById('cw-key-timing').innerHTML =
    timingReport(keyDecoder.stats(), 1200 / settings.wpm);
}

const paddle = document.getElementById('cw-paddle');
if (paddle) {
  paddle.addEventListener('mousedown', e => { e.preventDefault(); keyStart(); });
  paddle.addEventListener('touchstart', e => { e.preventDefault(); keyStart(); });
  ['mouseup', 'mouseleave', 'touchend'].forEach(ev =>
    paddle.addEventListener(ev, e => { e.preventDefault(); keyEnd(); }));
  document.getElementById('cw-key-clear').addEventListener('click', () => {
    keyDecoder.reset(1200 / settings.wpm); lastUpAt = 0; renderKey();
  });
}

document.addEventListener('keydown', e => {
  if (e.code !== 'Space' || isTyping(e)) return;
  if (document.getElementById('cw-key').hidden) return;
  e.preventDefault();
  keyStart();
});
document.addEventListener('keyup', e => {
  if (e.code !== 'Space' || isTyping(e)) return;
  if (document.getElementById('cw-key').hidden) return;
  e.preventDefault();
  keyEnd();
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
renderLesson();
renderKey();
showMode((location.hash || '#learn').replace('#', '') || 'learn');
