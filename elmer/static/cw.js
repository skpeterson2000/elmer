/* CW: tone generation, copy practice, key decoding and off-air decoding.
   All the audio lives in the browser; the server supplies practice text and
   remembers which characters you actually copy. */

const CWS = window.CW || {};
const MORSE_UI = {};   // filled from the server's encode endpoint as needed

/* The tone player and the decoder are in morse.js, loaded before this. */

/* --------------------------------------------------------------- settings */
/* 1020 Hz to start on. It is the tone the aviation world already agrees on:
   ICAO has VOR, ILS and NDB stations identify themselves in Morse at 1020 Hz,
   and the TONE position on a military UHF set - the AN/ARC-164 in most of the
   cockpits anybody has sat in - keys 1020 Hz for a DF steer. So it is the
   pitch a great many people have actually heard code on, which is a better
   reason for a default than any number picked for being round. It is only a
   default: the slider runs from 300 to 1200 Hz and remembers where it is put,
   and plenty of operators settle lower. */
const CW_TONE_DEFAULT = 1020;

/* Loud enough to be heard on a unit with nothing else to turn up. This
   slider is ELMER's own and sits under the system volume, which is the right
   way round - but a Raspberry Pi wired to a monitor may have no volume
   button anywhere on it, and a first run that is inaudible reads as a
   program that does not make a sound rather than one turned down. So it
   starts most of the way up and is turned down by anybody who wants it
   quieter, which is the easier direction to discover. */
const CW_VOLUME_DEFAULT = 92;

const settings = Object.assign(
  {tone: CW_TONE_DEFAULT, volume: CW_VOLUME_DEFAULT, wpm: 20, effective: 10, lesson: 2,
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

/* -------------------------------------------------- the buttons speak CW */
/* Immersion: every control says what a contact would send, and keys it
   before it acts. Press Slower and QRS sounds as the gaps open; press
   Resend and QSM? goes out first. The sound, the letters and the meaning
   arrive together, which is how a newcomer comes to think "QRS" when they
   feel rushed - and that is the code learnt, not looked up. The switch in
   the settings row turns the keying off for somebody past needing it. */
const Q_MEANING = {
  'QRV': 'ready, go ahead', 'QRS': 'send slower', 'QRQ': 'send faster',
  'QSM?': 'please repeat the last message', 'QSL': 'received and understood',
  'QRT': 'stop sending', '?': 'again, please',
};

function qsayOn() { return settings.qsay !== false; }

function keyQ(code) {
  /* The code, keyed at the character speed with normal spacing, and the
     card at the foot of the page saying what it means for as long as it
     sounds. Resolves when done; at once when the keying is off or the
     player is busy sending something else. */
  const card = document.getElementById('cw-qsay-card');
  const word = Q_MEANING[code] || '';
  const show = ms => {
    if (!card) return;
    document.getElementById('cw-qsay-code').textContent = code;
    document.getElementById('cw-qsay-word').textContent = word;
    card.hidden = false;
    clearTimeout(card._timer);
    card._timer = setTimeout(() => { card.hidden = true; }, ms);
  };
  if (!qsayOn()) return Promise.resolve();
  const syms = [...code].map(c => ({char: c, code: CODE[c] || ''})).filter(s => s.code);
  if (!syms.length || sending || textSending) { show(900); return Promise.resolve(); }
  return new Promise(resolve => {
    const timing = localTiming();
    let ms = 0;
    syms.forEach(s => { for (const el of s.code) ms += (el === '-' ? timing.dah : timing.dit) + timing.symbol_gap; ms += timing.char_gap; });
    show(Math.max(900, ms + 200));
    try {
      player.send([syms], timing, null, () => setTimeout(resolve, 150));
    } catch (e) { resolve(); }
  });
}

/* Any button with data-q says its code first, then does what it does: the
   click is held, the code keyed, and the click let through with the
   button marked so this does not run twice. A Stop (data-q-after) acts
   first and says QRT after - stopping must not wait on anything. */
document.addEventListener('click', e => {
  const b = e.target.closest('button[data-q]');
  if (!b || b.dataset.qSung || b.disabled) return;
  if (b.hasAttribute('data-q-after')) { setTimeout(() => keyQ(b.dataset.q), 60); return; }
  e.stopImmediatePropagation();
  e.preventDefault();
  keyQ(b.dataset.q).then(() => {
    b.dataset.qSung = '1';
    try { b.click(); } finally { delete b.dataset.qSung; }
  });
}, true);

const qsayBox = document.getElementById('cw-qsay');
if (qsayBox) {
  qsayBox.checked = qsayOn();
  qsayBox.addEventListener('change', () => { settings.qsay = qsayBox.checked; saveSettings(); });
}

/* A badge earned on this page is said here, the moment it is earned. */
function freshBadges(res) {
  ((res && res.fresh) || []).forEach(a => toast('\u2605 ' + a.name, a.description));
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

/* A space in a code is the gap between two letters, not a symbol. It is drawn
   as a piece of silence the right width and it is sounded as one, which is
   what lets a Q signal be shown as the three letters it actually is - and it
   is the whole difference between QRM and a prosign, which has no gaps in it
   at all. */
function codeHTML(code) {
  return [...(code || '')].map(el =>
    el === ' ' ? '<i class="gap"></i>'
               : '<i class="' + (el === '-' ? 'dah' : 'dit') + '"></i>').join('');
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
    if (el === ' ') {
      // Silence, and it keeps its place in the list so the lighting stays
      // lined up with what was drawn. The symbol gap after the previous
      // element is already counted, so only the rest of it is added here.
      lit.push(null);
      t += (timing.char_gap - timing.symbol_gap) / 1000;
      continue;
    }
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
        if (!m) return;                      // a gap has nothing to light
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
        /* Named, not just shown. "Name it afterwards" used to put the bare
           letter on the screen, which is not what naming a character means
           to anybody learning one: the name is Kilo, said out loud, the way
           the Today session has always done it. One function does that for
           the whole page. */
        if (ui.word) sayBack(sym.char, ui.word);
        await sleep(REVEAL_MS);
        ui.letter.classList.remove('show');
        if (ui.word) ui.word.classList.remove('show');
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
  if (learnOn) learnEnd(false);
  if (name !== 'copy') player.stop();
  history.replaceState(null, '', '#' + name);
  remember('cw.mode', name);
}
document.querySelectorAll('#cw-modes button').forEach(b =>
  b.addEventListener('click', () => showMode(b.dataset.mode)));

/* ------------------------------------------------------------------ learn */
function charClass(stat) {
  if (!stat || !stat.sent) return 'unmet';
  const rate = stat.copied / stat.sent;
  return rate >= 0.9 ? 'solid' : rate >= 0.7 ? 'shaky' : 'weak';
}

function renderLesson(only) {
  const chars = only || (CWS.koch || []).slice(0, settings.lesson);
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
        (worst.length ? ' — heard as ' + worst.map(w => w[0] + '×' + w[1]).join(', ') : '') +
        (st.repeats ? ' — sent again ' + st.repeats + (st.repeats === 1 ? ' time' : ' times') : '');
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
  word: document.getElementById('cw-teach-word'),
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
  /* Once heard, the same button is the resend: "again, please" is the
     most natural thing to ask for and should not need a second thought. */
  const hear = document.getElementById('cw-hear');
  hear.innerHTML = 'Send them again <span class="q">QSM?</span>';
  hear.dataset.q = 'QSM?';
  hear.title = 'QSM? - please repeat the last message';
}

document.getElementById('cw-hear').addEventListener('click', () => {
  const chars = (CWS.koch || []).slice(0, settings.lesson);
  teachChars(chars.map(c => ({char: c, code: CODE[c] || ''})));
});
document.getElementById('cw-teach-stop').addEventListener('click', () => {
  teachHalt();
  teachUI.onDone();
});

/* ------------------------------------------ one at a time, at your own pace */
/* Crawl, then walk, then run. Koch's full speed is about the sound of a
   character - the shape of it, heard whole, rather than counted - and that
   argument says nothing at all about the gap between one character and the
   next. A beginner is still comparing what they just heard against the
   shapes on the screen, and how long that takes is their business and not
   the program's. Everybody's is different and none of them is wrong.

   So this runner sounds one character and then stops. Nothing is timed.
   The learner asks for it again as often as they like. When they have it,
   it is named - shown, spelled in the phonetic alphabet and said aloud -
   and only then does the next one sound.

   What decides which characters are in it is the record, and only the
   record. This used to take its characters from the slider - pick eight,
   press Begin, meet eight - and recorded nothing, so it could not know what
   anybody had earned and could not give them the next one when they had.
   It is the Koch method now, the same one the copy drill runs on:

     - two characters to start, because with one there is nothing to tell
       apart and every answer is right;
     - a new character is met first - sounded, drawn, named - with nothing
       asked, because finding out what a sound is comes before being asked
       which sound it was;
     - then it joins the drill, and every pick is recorded, so the record
       can say when it is solid: nine in ten over the last thirty;
     - the deal is by weight: the newest character most, each shaky one
       more the shakier it is, the known ones least and never none - and a
       character just missed is put back in the air within a few sends,
       because the long-run deal alone lets a miss go cold before it comes
       round again;
     - when the whole set is solid the next character in the order is met
       and joins, and the lesson says so;
     - nothing is ever taken away. Not advancing says the same thing
       kindly.

   That is the whole of it, and it is deliberately the smallest game on the
   page: telling two sounds apart is the ability everything else is built
   on, and the copying speed that ends up on a rating, or in a job, is what
   this turns into once the characters are known. T-ball first. */
const LEARN_LEAD_MS = 900;          // a breath after "ready" and before the first one
const LEARN_NAMED_MS = 1500;        // the name stands this long before the next sounds
const LEARN_MEET_MS = 2200;         // a new character, met: drawn and named, then a pause
let learnOn = false, learnWaiting = false;
/* Set when a character has just been missed: the shape goes up for the
   naming and stays up for the replay that follows, whatever the record
   says about it. Cleared by the replay that uses it. */
let learnShowNext = false;
let learnPlan = null;               // the record's plan: chars, new, weak, draw, solid, total
let learnChars = [];                // what is in the drill right now
let learnCur = null;                // the character in the air
let learnHeard = 0;                 // sends this sitting
/* A character just missed comes back soon, not only more often. Once it is
   answered right it goes here with a short countdown of other sends, and
   when the countdown is up it is the next one out whatever the deal says.
   Two to four sends later: far enough not to be the same sound again,
   close enough that the miss is still warm. */
let learnRecycle = [];              // [{ch, after}]
const RECYCLE_MIN = 2, RECYCLE_MAX = 4;

function learnShow(state) {
  const set = (id, on) => { const el = document.getElementById(id); if (el) el.hidden = !on; };
  set('cw-learn-begin', !learnOn);
  set('cw-hear', !learnOn && !teaching);
  set('cw-start-copy', !learnOn);
  set('cw-learn-again', learnOn && state === 'wait');
  set('cw-learn-stop', learnOn);
  const t = document.getElementById('cw-teach');
  if (t) t.classList.toggle('learning', learnOn);
  const row = document.getElementById('cw-lesson-chars');
  if (row) row.classList.toggle('picking', learnOn && state === 'wait');
  const n = document.getElementById('cw-learn-count');
  if (n) n.textContent = learnOn && learnPlan
    ? learnHeard + ' heard · ' + learnPlan.solid + ' of ' + learnPlan.total + ' solid'
    : '';
}

function learnHint(text) {
  const h = document.getElementById('cw-teach-hint');
  if (h) h.textContent = text;
}

function learnClear() {
  const letter = document.getElementById('cw-teach-letter');
  const word = document.getElementById('cw-teach-word');
  if (letter) letter.classList.remove('show', 'right', 'wrong');
  if (word) { word.textContent = ''; word.classList.remove('show'); }
}

/* The deal: which character sounds next. A recycled miss whose turn has
   come goes first; otherwise the record's shares decide. */
function learnDraw() {
  learnRecycle.forEach(r => { r.after -= 1; });
  const due = learnRecycle.find(r => r.after <= 0 && learnChars.includes(r.ch));
  if (due) {
    learnRecycle = learnRecycle.filter(r => r !== due);
    return due.ch;
  }
  const shares = (learnPlan && learnPlan.draw) || {};
  const pool = learnChars.filter(c => shares[c] > 0);
  if (!pool.length) return learnChars[Math.floor(Math.random() * learnChars.length)];
  let r = Math.random() * pool.reduce((s, c) => s + shares[c], 0);
  for (const c of pool) { r -= shares[c]; if (r <= 0) return c; }
  return pool[pool.length - 1];
}

function learnRecycleSoon(ch) {
  if (learnRecycle.some(r => r.ch === ch)) return;
  learnRecycle.push({ch: ch, after: RECYCLE_MIN + Math.floor(Math.random() * (RECYCLE_MAX - RECYCLE_MIN + 1))});
}

/* Meeting a character: it sounds, it is drawn, it is named, and nothing is
   asked. This is the one-letter moment, and it is an introduction and not
   a test - which is why it is not recorded. The drill after it is. */
async function learnMeet(c) {
  if (!learnOn) return;
  learnClear();
  learnShow('sounding');
  learnHint('new: ' + c + ' is ' + phoneticWord(c) + ' - listen');
  teachStop = false;
  await playSymbol({char: c, code: CODE[c] || ''}, localTiming(),
                   document.getElementById('cw-teach-code'));
  if (!learnOn) return;
  const letter = document.getElementById('cw-teach-letter');
  if (letter) { letter.innerHTML = escapeHTML(c); letter.classList.add('show'); }
  if (teachUI.reveal()) sayBack(c, document.getElementById('cw-teach-word'), true);
  await sleep(LEARN_MEET_MS);
}

async function learnSound() {
  if (!learnOn || !learnCur) return;
  learnClear();
  learnShow('sounding');
  learnHint('listen');
  teachStop = false;                       // a Stop earlier must not silence this
  const c = learnCur;
  /* "Which one was it?" is not a fair question with the answer drawn
     beside it. So the shape sounds bare once the record says this
     character is known by ear - and comes back the moment it is missed,
     which is the one time the drawing is teaching something. */
  const box = document.getElementById('cw-teach-code');
  const known = ((learnPlan && learnPlan.weaned) || []).indexOf(c) >= 0;
  const show = learnShowNext || !known;
  learnShowNext = false;
  if (!show) box.innerHTML = '';
  await playSymbol({char: c, code: CODE[c] || ''}, localTiming(),
                   show ? box : []);
  if (!learnOn) return;
  learnWaiting = true;
  learnShow('wait');
  learnHint('no rush - which one was it? pick it from the row above, or type it');
}

async function learnNext() {
  if (!learnOn) return;
  learnCur = learnDraw();
  learnHeard += 1;
  await learnSound();
}

/* The record has moved. If the set grew, a character went solid and the
   next in the order has been earned: say so, meet it, and carry on. If it
   did not, the shares have still shifted with the record, and the deal
   follows them. */
async function learnAdvance(fresh) {
  if (!fresh || !learnOn) return;
  const before = learnPlan ? learnPlan.chars : [];
  learnPlan = fresh;
  const joined = fresh.chars.filter(c => !before.includes(c));
  learnChars = fresh.chars;
  renderLesson(learnChars);
  learnShow('sounding');
  if (fresh.done) {
    learnHint('every character is solid - that is the whole code. Go and copy.');
    learnEnd(true);
    return;
  }
  for (const c of joined) {
    const earned = before.length ? before[before.length - 1] : null;
    learnHint((earned ? earned + ' is solid - ' : '') + c + ' joins');
    await sleep(LEARN_NAMED_MS);
    await learnMeet(c);
  }
}

/* The answer, and what is done with it.
 *
 * The letter put on the screen is the one the learner picked, in green if it
 * was right and red if it was not. The voice says the character that was
 * actually sent, either way: "Kilo" after a chime when they picked K, and
 * "Kilo" after a buzz when they picked R. That is the same rule the rest of
 * the page keys on - the word is always the truth, so the sound of a
 * character is coupled to its name and never to somebody's mistake - and it
 * is what makes a wrong answer worth having rather than just wrong.
 *
 * A miss brings the same character round again. And every answer is
 * recorded - one send, copied or not, and what it was heard as - because
 * the record is what decides when the next character is earned, and a
 * lesson that recorded nothing could only ever offer what a slider said.
 */
async function learnPick(picked) {
  if (!learnOn || !learnWaiting) return;
  learnWaiting = false;
  const actual = learnCur;
  const right = picked === actual;
  const letter = document.getElementById('cw-teach-letter');
  letter.innerHTML = escapeHTML(picked);
  letter.classList.remove('right', 'wrong');
  letter.classList.add('show', right ? 'right' : 'wrong');
  learnShow('named');
  learnHint(right ? 'that is the one' : 'that was ' + phoneticWord(actual) + ' - here it is again');
  /* Missed: here is what that sound actually was, drawn, and drawn again
     for the replay below - a copyist who got it wrong is owed the shape. */
  if (!right) {
    document.getElementById('cw-teach-code').innerHTML = codeHTML(CODE[actual] || '');
    learnShowNext = true;
  }
  if (teachUI.reveal()) sayBack(actual, document.getElementById('cw-teach-word'), right);
  else cue(right);
  /* Recorded on the spot, one send at a time, so nothing is lost if they
     stop mid-lesson and so the record can answer straight away. */
  const per = {}; per[actual] = {sent: 1, copied: right ? 1 : 0,
                                 confused: right ? {} : {[picked]: 1},
                                 outcomes: right ? '1' : '0'};
  const res = await postJSON('/api/cw/result', {per_char: per}).catch(() => null);
  if (res && res.progress) { CWS.progress = res.progress; renderProgress(); }
  await sleep(LEARN_NAMED_MS);
  if (!learnOn) return;
  if (res && res.learn) await learnAdvance(res.learn);
  if (!learnOn) return;
  if (!right) {
    learnRecycleSoon(actual);                     // and again in a few sends' time
    await learnSound();                           // round again now, at their pace
    return;
  }
  await learnNext();
}

function learnEnd(finished) {
  learnOn = false;
  learnWaiting = false;
  learnCur = null;
  learnRecycle = [];
  teachHalt();
  learnClear();
  learnShow('');
  renderLesson();                                 // the copy drill's row again
  learnHint(finished
    ? 'that is the lesson - hear them run together, or start copying'
    : 'Press below and each character is drawn as it sounds, then named.');
}

async function learnBegin() {
  if (learnOn) return;
  let d = null;
  try { d = await api('/api/cw/plan'); } catch (e) { return; }
  learnPlan = d.learn || d.plan;
  if (!learnPlan || !learnPlan.chars || !learnPlan.chars.length) return;
  if (learnPlan.done) {
    learnHint('every character is solid - that is the whole code. Go and copy.');
    return;
  }
  learnChars = learnPlan.chars;
  renderLesson(learnChars);
  teachHalt();
  learnOn = true;
  learnWaiting = false;
  learnHeard = 0;
  learnRecycle = [];
  learnClear();
  learnShow('sounding');
  learnHint('here they come');
  await sleep(LEARN_LEAD_MS);
  /* Anything never heard is met before it is asked about. */
  const unmet = learnChars.filter(c => !((CWS.progress || {})[c] || {}).sent);
  for (const c of unmet) { if (!learnOn) return; await learnMeet(c); }
  await learnNext();
}

document.getElementById('cw-learn-begin').addEventListener('click', learnBegin);
document.getElementById('cw-learn-again').addEventListener('click', () => { if (learnOn) learnSound(); });
document.getElementById('cw-learn-stop').addEventListener('click', () => learnEnd(false));

/* Typed, for anybody with a keyboard under their hands - the same answer as
   clicking it. Only the lesson's own characters count: the row above is the
   menu, and a stray key is a stray key and not a wrong answer. */
document.addEventListener('keydown', e => {
  if (!learnOn || !learnWaiting) return;
  if (e.metaKey || e.ctrlKey || e.altKey || e.key.length !== 1) return;
  const k = e.key.toUpperCase();
  if (!learnChars.includes(k)) return;
  e.preventDefault();
  learnPick(k);
});

/* Anything drawn as a code cell plays when clicked - the chart, and the
   lesson's own characters. */
document.addEventListener('click', e => {
  const cell = e.target.closest('.cw-chart-cell');
  if (!cell || !cell.dataset.code) return;
  /* While the lesson is waiting on an answer, the lesson's own characters
     are the answer buttons rather than a way of hearing them: the character
     in the air is the question, and playing the answer aloud before choosing
     it would be a different exercise. Again is there to hear the question
     once more, and the chart pane is there to browse. */
  if (learnOn && learnWaiting && cell.closest('#cw-lesson-chars')) {
    e.preventDefault();
    learnPick(cell.dataset.char);
    return;
  }
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
/* How many times this text was sent again before it was checked. A contact
   asks for a repeat when the copy is shaky, and a learner asks more often;
   the count is part of the record - copied first time, or copied after
   three resends, is the difference between knowing and nearly knowing. */
let copyResends = 0;

async function sendPractice(repeat) {
  const kind = document.getElementById('cw-kind').value;
  const status = document.getElementById('cw-copy-status');
  if (!repeat) {
    status.textContent = 'fetching…';
    currentData = await api('/api/cw/practice?' + new URLSearchParams({
      kind: kind, count: kind === 'qso' ? 1 : 5, lesson: settings.lesson,
      wpm: settings.wpm, effective: settings.effective}));
    currentText = currentData.plain || currentData.text;
    copyResends = 0;
  } else {
    copyResends++;
  }
  /* A repeat is a fresh copy of the same text: what was typed and what
     was marked go, so the second hearing is heard and not read. */
  document.getElementById('cw-typed').value = '';
  document.getElementById('cw-result').innerHTML = '';
  sending = true;
  document.getElementById('cw-send').hidden = true;
  document.getElementById('cw-stop').hidden = false;
  document.getElementById('cw-repeat').hidden = true;
  status.textContent = 'sending…';
  document.getElementById('cw-typed').focus();
  document.getElementById('cw-slower').hidden = true;
  document.getElementById('cw-faster').hidden = true;
  player.send(currentData.groups, currentData.timing, null, () => {
    sending = false;
    document.getElementById('cw-send').hidden = false;
    document.getElementById('cw-stop').hidden = true;
    document.getElementById('cw-repeat').hidden = false;
    document.getElementById('cw-slower').hidden = false;
    document.getElementById('cw-faster').hidden = false;
    status.textContent = (copyResends ? 'sent again (' + copyResends + ') — ' : 'sent — ') +
      'type what you heard, then check';
  });
}

document.getElementById('cw-send').addEventListener('click', () => sendPractice(false));
document.getElementById('cw-repeat').addEventListener('click', () => sendPractice(true));

/* QRS and QRQ: two words a minute off or on the effective speed - the gaps,
   never the characters, which is the Farnsworth rule the settings explain -
   and the same text sent again at the new pace. It counts as a resend, and
   the slider follows so the new pace is what the next send uses too. */
async function repace(delta) {
  const eff = document.getElementById('cw-eff');
  const was = settings.effective;
  settings.effective = Math.max(3, Math.min(settings.wpm, settings.effective + delta));
  eff.value = settings.effective;
  document.getElementById('cw-eff-v').textContent = settings.effective + ' wpm';
  saveSettings();
  if (!currentData) return;
  if (settings.effective === was) {
    document.getElementById('cw-copy-status').textContent = delta < 0
      ? 'already at the slowest spacing' : 'already as fast as the characters themselves';
    return;
  }
  const kind = document.getElementById('cw-kind').value;
  /* The same text, the new timing: re-encoded so the gaps are right. */
  const data = await api('/api/cw/encode?' + new URLSearchParams(
    {text: currentData.text, wpm: settings.wpm, effective: settings.effective})).catch(() => null);
  if (data && data.groups) { currentData.groups = data.groups; currentData.timing = data.timing; }
  void kind;
  await sendPractice(true);
}
document.getElementById('cw-slower').addEventListener('click', () => repace(-2));
document.getElementById('cw-faster').addEventListener('click', () => repace(2));
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
    perChar[want] = perChar[want] || {sent: 0, copied: 0, confused: {}, repeats: 0};
    perChar[want].sent++;
    perChar[want].repeats += copyResends;
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

  const heard = copyResends ? 'after ' + copyResends + ' resend' + (copyResends === 1 ? '' : 's') : 'first time through';
  document.getElementById('cw-result').innerHTML =
    '<div class="spread"><b>' + pct + '% copied</b> <span class="tiny muted">' + heard + '</span>' +
    '<span class="pill ' + (pct >= 90 ? 'good' : pct >= 70 ? 'warn' : 'bad') + '">' +
      (pct >= 90 ? (copyResends ? 'ready, once it comes first time' : 'ready for the next character')
        : pct >= 70 ? 'nearly' : 'more of this one') +
    '</span></div>' +
    '<div class="cw-compare mt">' + marks.join('') + '</div>' +
    '<div class="tiny muted" style="margin-top:.4rem">sent: <span class="mono">' +
      escapeHTML((currentData.text || sent).replace(/\s+/g, ' ').trim()) +
      '</span></div>' + glossary;

  const res = await postJSON('/api/cw/result',
    {per_char: perChar, settings: settings}).catch(() => null);
  if (res && res.progress) { CWS.progress = res.progress; renderProgress(); }
  freshBadges(res);
  /* The record decides the lesson: when the plan moves up, the slider
     follows and the toast says what arrived. */
  const before = todayPlan ? todayPlan.lesson : settings.lesson;
  await refreshPlan();
  if (todayPlan && todayPlan.lesson > before && todayPlan.new.length) {
    toast('Lesson ' + todayPlan.lesson, todayPlan.new.join(' ') + ' has arrived - meet it on Today.');
  } else if (pct >= 90 && document.getElementById('cw-kind').value === 'koch' && todayPlan && !todayPlan.done) {
    toast('Good copy', 'Nine in ten. Twenty sends of each and the next character arrives on its own.');
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
  if (!keyLive) keyLive = requestAnimationFrame(liveKey);
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

/* The raw line: the symbols of the character so far, and - while the key
   is down - the element in the making, a dit until it has been held long
   enough to be a dah. It used to print a middle dot as a placeholder when
   there was nothing to show, which read as a dit sitting at the head of
   every transmission and made a press look like a dah and a release like
   a dit. Nothing is shown when nothing has been sent. */
function rawLine() {
  let s = keyDecoder.symbols.join('');
  if (keyDown) s += (performance.now() - keyDownAt) < keyDecoder.dit * 2 ? '.' : '-';
  return s;
}

let keyLive = null;
function liveKey() {
  document.getElementById('cw-key-raw').textContent = rawLine() || '\u00a0';
  if (keyDown) keyLive = requestAnimationFrame(liveKey); else keyLive = null;
}

function renderKey() {
  document.getElementById('cw-key-raw').textContent = rawLine() || '\u00a0';
  document.getElementById('cw-key-decoded').textContent =
    keyDecoder.text || '\u00a0';
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

/* ----------------------------------------------------------- audio key */
/* A real key, wired the way it is on the bench: through a SignalLink or a
   rig's sidetone into Line-In, or any USB sound device that carries a keyed
   tone. The tone's coming and going is the key's down and up, read every
   eight milliseconds from the input, and it drives the same straight key
   as the space bar - so the timing chart measures the fist on the bench,
   not a keyboard's idea of it. */
let akStream = null, akCtx = null, akTimer = null;

async function listAudioInputs() {
  const sel = document.getElementById('cw-audio-device');
  if (!sel || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
  let devs = [];
  try { devs = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'audioinput'); } catch (e) { devs = []; }
  let chosen = '';
  try { chosen = localStorage.getItem('cw-audio-key-device') || ''; } catch (e) {}
  sel.innerHTML = '<option value="">default input</option>' + devs.map((d, i) =>
    '<option value="' + escapeHTML(d.deviceId) + '"' + (d.deviceId === chosen ? ' selected' : '') + '>' +
    escapeHTML(d.label || ('input ' + (i + 1))) + '</option>').join('');
  sel.hidden = false;
}

async function startAudioKey() {
  const status = document.getElementById('cw-audio-key-status');
  const sel = document.getElementById('cw-audio-device');
  const device = sel && sel.value ? {deviceId: {exact: sel.value}} : {};
  try {
    akStream = await navigator.mediaDevices.getUserMedia({audio: Object.assign({
      echoCancellation: false, noiseSuppression: false, autoGainControl: false}, device)});
  } catch (e) {
    status.innerHTML = '<span style="color:var(--red)">no audio input \u2014 ' +
      escapeHTML(e.name === 'NotAllowedError' ? 'permission refused' : e.message) + '</span>';
    return;
  }
  try { localStorage.setItem('cw-audio-key-device', sel ? sel.value : ''); } catch (e) {}
  await listAudioInputs();                       // labels arrive once permission has
  if (keyerMode !== 'straight') setKeyerMode('straight');
  const Ctx = window.AudioContext || window.webkitAudioContext;
  akCtx = new Ctx();
  const source = akCtx.createMediaStreamSource(akStream);
  const analyser = akCtx.createAnalyser();
  analyser.fftSize = 1024;                       // shorter than the off-air decoder's: this is a key, and 8 ms matters
  analyser.smoothingTimeConstant = 0.0;
  source.connect(analyser);
  const bins = new Float32Array(analyser.frequencyBinCount);
  const hz = akCtx.sampleRate / analyser.fftSize;
  const lo = Math.floor(250 / hz), hi = Math.ceil(1400 / hz);
  const st = {on: false, floor: 1e-4, peak: 1e-3};
  document.getElementById('cw-audio-key').hidden = true;
  document.getElementById('cw-audio-key-stop').hidden = false;
  status.textContent = 'listening for a keyed tone';
  akTimer = setInterval(() => {
    analyser.getFloatFrequencyData(bins);
    let bestDb = -Infinity, best = lo;
    for (let i = lo; i <= hi && i < bins.length; i++) if (bins[i] > bestDb) { bestDb = bins[i]; best = i; }
    const level = Math.pow(10, bestDb / 20);
    st.peak = Math.max(st.peak * 0.995, level);
    st.floor = Math.min(st.floor * 1.005 + 1e-7, level);
    const on = level > st.floor + (st.peak - st.floor) * 0.35 && st.peak > st.floor * 3;
    if (on !== st.on) {
      st.on = on;
      if (on) keyStart(); else keyEnd();
      status.textContent = 'keyed tone at about ' + Math.round(best * hz) + ' Hz';
    }
  }, 8);
}

function stopAudioKey() {
  clearInterval(akTimer); akTimer = null;
  if (keyDown) keyEnd();
  if (akStream) akStream.getTracks().forEach(t => t.stop());
  if (akCtx) akCtx.close();
  akStream = null; akCtx = null;
  const start = document.getElementById('cw-audio-key');
  if (start) { start.hidden = false; document.getElementById('cw-audio-key-stop').hidden = true; }
}

const akBtn = document.getElementById('cw-audio-key');
if (akBtn) {
  akBtn.addEventListener('click', startAudioKey);
  document.getElementById('cw-audio-key-stop').addEventListener('click', () => {
    stopAudioKey();
    document.getElementById('cw-audio-key-status').textContent = 'stopped';
  });
  listAudioInputs();
}

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
/* The fragment if a link supplied one, else wherever you were - somebody
   halfway through a Koch lesson who glances at the band plan should come back
   to the lesson, not to the top of the page. */
showMode((location.hash || '').replace('#', '')
         || recall('cw.mode', 'today'));


/* ------------------------------------------------------------------ today */
/* Say a key back. Whichever key it was: the code just heard, the key the
   fingers chose and its name, coupled - and the grading is separate. Letters
   are the phonetic alphabet, digits their words, a prosign or a Q signal its
   meaning, all from the recorded shelf; anything not recorded is silence. */
const DIGIT_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'];
if (window.Voice && CWS.voice_have) Voice.setHave(CWS.voice_have);
function phoneticWord(key) {
  const k = String(key || '').toUpperCase();
  if (/^[A-Z]$/.test(k)) return (CWS.phonetic || {})[k] || k;
  if (/^[0-9]$/.test(k)) return DIGIT_WORDS[+k];
  if (CWS.meanings && CWS.meanings[k]) return k + ' - ' + CWS.meanings[k];
  return k;
}
/* A chime before a right answer, a buzz before a wrong one - made here
   from the player's own audio context, so no file is needed and they are
   never late. The chime is two rising notes; the buzz is a low, rough
   note. Both short: they announce the word, they do not replace it. */
function cue(ok) {
  try {
    const ctx = player.ensure();
    const t = ctx.currentTime + 0.02;
    const g = ctx.createGain(); g.connect(ctx.destination);
    const v = Math.pow(settings.volume / 100, 2) * 0.5;
    if (ok) {
      [[880, 0], [1320, 0.09]].forEach(([hz, at]) => {
        const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.value = hz; o.connect(g);
        o.start(t + at); o.stop(t + at + 0.12);
      });
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t + 0.01);
      g.gain.setValueAtTime(v, t + 0.18); g.gain.linearRampToValueAtTime(0, t + 0.22);
    } else {
      const o = ctx.createOscillator(); o.type = 'sawtooth'; o.frequency.value = 150; o.connect(g);
      o.start(t); o.stop(t + 0.28);
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v * 0.6, t + 0.01);
      g.gain.setValueAtTime(v * 0.6, t + 0.24); g.gain.linearRampToValueAtTime(0, t + 0.28);
    }
    return ok ? 0.25 : 0.32;
  } catch (e) { return 0; }
}

/* Said, and shown: what the code WAS, not what the key was. When K is
   heard and M is pressed the word is Kilo, after a buzz; when K is
   pressed it is Kilo after a chime. The key decides the grading and the
   cue; the word is always the truth, so the sound of the code is coupled
   to its name and never to a mistake. */
function sayBack(actual, where, ok) {
  const box = document.getElementById('cw-sayback');
  const word = phoneticWord(actual);
  if (where) { where.textContent = word; where.classList.add('show'); }
  if (box && !box.checked) return word;
  let wait = 0;
  if (ok === true || ok === false) wait = cue(ok);
  const k = String(actual || '').toUpperCase();
  let token = null;
  if (/^[A-Z]$/.test(k)) token = 'phon-' + k.toLowerCase();
  else if (/^[0-9]$/.test(k)) token = DIGIT_WORDS[+k];
  else if (/^Q[A-Z]{2}$/.test(k)) token = 'q-' + k.toLowerCase();
  else if (/^[A-Z]{2}$/.test(k)) token = 'pro-' + k.toLowerCase();
  if (token && window.Voice) setTimeout(() => Voice.say([token]), wait * 1000);
  return word;
}

let todayPlan = CWS.plan || null, todaySession = CWS.session || [], todayStreak = CWS.streak || {};
let sessionOn = false, sessionStop = false, sessionStarted = 0;

function renderToday() {
  const p = todayPlan;
  if (!p) return;
  const streak = todayStreak || {};
  document.getElementById('cw-today-streak').textContent =
    (streak.streak ? streak.streak + ' day' + (streak.streak === 1 ? '' : 's') + ' running' : 'no streak yet') +
    (streak.minutes_today ? ' · ' + streak.minutes_today + ' min today' : '') +
    (streak.minutes_all ? ' · ' + streak.minutes_all + ' min in all' : '');
  document.getElementById('cw-today-where').innerHTML = p.done
    ? '<b>Every character is solid.</b> From here it is speed, and words.'
    : '<b>Lesson ' + p.lesson + ' of ' + p.total + '</b> - ' + p.solid + ' solid' +
      (p.new.length ? ', new: <b class="mono">' + escapeHTML(p.new.join(' ')) + '</b>' : '') +
      (p.ahead ? ' <span class="warntext">(the slider is ahead of the record - lesson ' + p.earned + ' is what it backs)</span>' : '') + '.';
  document.getElementById('cw-today-chars').innerHTML = p.chars.map(c =>
    '<span class="cw-char ' + charClass((CWS.progress || {})[c]) + (p.new.includes(c) ? ' new' : '') + '">' + escapeHTML(c) + '</span>').join('');
  document.getElementById('cw-today-weak').textContent = p.weak.length
    ? 'Still shaky: ' + p.weak.slice(0, 4).map(w => w.ch + (w.heard_as.length ? ' (heard as ' + w.heard_as.join(', ') + ')' : '')).join(', ')
    : (p.solid ? 'Nothing shaky among what you have met.' : '');
  const names = {meet: 'Meet', flash: 'One at a time', koch: 'Groups', words: 'Words', qso: 'A contact'};
  document.getElementById('cw-today-steps').innerHTML = todaySession.map(s =>
    '<li><b>' + names[s.kind] + (s.chars ? ' ' + escapeHTML(s.chars.join(' ')) : '') + (s.seconds ? ' - ' + s.seconds + ' s' : '') + '</b>' +
    '<div class="tiny muted">' + escapeHTML(s.why) + '</div></li>').join('');
}

async function refreshPlan() {
  try {
    const d = await api('/api/cw/plan');
    todayPlan = d.plan; todaySession = d.session; todayStreak = d;
    if (d.voice_have && window.Voice) Voice.setHave(d.voice_have);
    /* The lesson follows the record unless the slider was pushed ahead. */
    if (todayPlan && settings.lesson < todayPlan.lesson) {
      settings.lesson = todayPlan.lesson;
      const sl = document.getElementById('cw-lesson');
      if (sl) { sl.value = settings.lesson; sl.dispatchEvent(new Event('input')); }
    }
    renderToday(); renderLesson();
  } catch (e) { /* the page's own copy stands */ }
}

/* The flash drill: one character, the key for it straight away. The
   character sounds; the first key pressed within the window is the answer,
   said back and marked; then the next. Slow is wrong: a second and a half is
   the window, which is long enough to hear and press and not long enough to
   count dits. */
/* After the answer: the cue and the spoken name take most of a second,
   and the next character must not start over them. */
const FLASH_WINDOW_MS = 1500, FLASH_GAP_MS = 1000, FLASH_GAP_WRONG_MS = 1700;
/* The answer to a flashed character is a key press; '?' is not an answer
   but a request - "again, please" - and the button beside the card is the
   same request for a screen with no keyboard. */
const RESEND_KEY = '?';
let flashKey = null;
document.addEventListener('keydown', e => {
  if (!flashKey) return;
  if (e.key.length !== 1 || e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key === RESEND_KEY ? RESEND_KEY : e.key.toUpperCase();
  e.preventDefault();
  const take = flashKey; flashKey = null;
  take(k);
});
document.getElementById('cw-flash-again').addEventListener('click', () => {
  if (!flashKey) return;
  const take = flashKey; flashKey = null;
  take(RESEND_KEY);
});

async function flashRun(seconds) {
  const box = document.getElementById('cw-flash');
  const code = document.getElementById('cw-flash-code');
  const letter = document.getElementById('cw-flash-letter');
  const hint = document.getElementById('cw-flash-hint');
  const score = document.getElementById('cw-flash-score');
  const clock = document.getElementById('cw-flash-clock');
  const word = document.getElementById('cw-flash-word');
  box.hidden = false;
  let seq;
  try { seq = (await api('/api/cw/flash?count=200')).chars; } catch (e) { box.hidden = true; return null; }
  const perChar = {}, times = [];
  let right = 0, sent = 0, i = 0, resends = 0;
  const until = Date.now() + seconds * 1000;
  const again = document.getElementById('cw-flash-again');
  hint.textContent = 'press the key for what you hear - straight away; ? to hear it again';
  again.hidden = false;
  while (Date.now() < until && !sessionStop && i < seq.length) {
    const sym = seq[i++];
    letter.classList.remove('show'); letter.innerHTML = '';
    word.classList.remove('show'); word.textContent = '';
    clock.textContent = Math.max(0, Math.round((until - Date.now()) / 1000)) + ' s';
    const t0 = performance.now();
    /* Played, and played again for as long as ? is pressed instead of an
       answer. Each resend is counted against the character: the clock
       keeps running, because a contact's patience does too. */
    /* The shape is drawn while the character sounds only until the
       character has been heard right four times running - the server
       decides that from the record and says so per character. After
       that the sound has to stand on its own, because a shape read off
       the screen while it is still sounding is answered by the eye. A
       resend does not bring it back: asking to hear it again is asking
       to hear it, and the miss below will show it soon enough. */
    const showCode = sym.print !== false;
    if (!showCode) code.innerHTML = '';
    let answer = null, reps = 0;
    for (;;) {
      const played = playSymbol(sym, localTiming(), showCode ? [code] : []);
      answer = await new Promise(resolve => {
        const timer = setTimeout(() => { flashKey = null; resolve(null); }, FLASH_WINDOW_MS + 1200 / settings.wpm * sym.code.length * 2);
        flashKey = k => { clearTimeout(timer); resolve(k); };
      });
      await played;
      if (answer !== RESEND_KEY || sessionStop) break;
      reps++;
      hint.textContent = 'again (' + reps + ')';
      await sleep(250);
    }
    hint.textContent = 'press the key for what you hear - straight away; ? to hear it again';
    sent++;
    resends += reps;
    const want = sym.char;
    perChar[want] = perChar[want] || {sent: 0, copied: 0, confused: {}, repeats: 0};
    perChar[want].sent++;
    perChar[want].repeats += reps;
    const ok = answer === want;
    word.style.color = ok ? 'var(--green)' : 'var(--red)';
    sayBack(want, word, answer ? ok : undefined);
    if (ok) { right++; perChar[want].copied++; times.push(performance.now() - t0); }
    else if (answer) perChar[want].confused[answer] = (perChar[want].confused[answer] || 0) + 1;
    /* Wrong, or nothing at all: here the shape earns its keep. Whatever
       else is on screen, a copyist who missed is shown what the sound
       actually was, weaned or not - that is the one moment the drawing
       teaches instead of standing in the way. */
    if (!ok) code.innerHTML = codeHTML(sym.code);
    letter.innerHTML = escapeHTML(want) + (ok ? '' : ' <span class="cw-miss"><i>' + escapeHTML(answer || '·') + '</i></span>');
    letter.style.color = ok ? 'var(--green)' : 'var(--red)';
    letter.classList.add('show');
    score.textContent = right + ' / ' + sent;
    await sleep(ok ? FLASH_GAP_MS : FLASH_GAP_WRONG_MS);
  }
  flashKey = null;
  again.hidden = true;
  letter.style.color = '';
  box.hidden = true;
  const mean = times.length ? Math.round(times.reduce((a, b) => a + b, 0) / times.length) : null;
  return {perChar: perChar, right: right, sent: sent, mean_ms: mean, resends: resends};
}

async function runSession() {
  if (sessionOn) return;
  sessionOn = true; sessionStop = false; sessionStarted = Date.now();
  const status = document.getElementById('cw-today-status');
  const result = document.getElementById('cw-today-result');
  document.getElementById('cw-today-start').hidden = true;
  document.getElementById('cw-today-stop').hidden = false;
  result.innerHTML = '';
  const lines = [];
  let first = true;
  for (const step of todaySession) {
    if (sessionStop) break;
    /* A breath between chunks: the last word of one is still being said
       when the next would start, and two sounds at once is neither. */
    if (!first) await sleep(1200);
    first = false;
    if (step.kind === 'meet') {
      status.textContent = 'meet ' + step.chars.join(' ');
      const flash = document.getElementById('cw-flash'); flash.hidden = false;
      document.getElementById('cw-flash-hint').textContent = 'listen - the shape is drawn as it sounds, then named';
      const syms = step.chars.map(c => ({char: c, code: CODE[c] || ''}));
      for (let pass = 0; pass < 3 && !sessionStop; pass++) {
        for (const sym of syms) {
          if (sessionStop) break;
          const letter = document.getElementById('cw-flash-letter');
          letter.classList.remove('show'); letter.style.color = '';
          await playSymbol(sym, localTiming(), [document.getElementById('cw-flash-code')]);
          await sleep(500);
          letter.innerHTML = escapeHTML(sym.char); letter.classList.add('show');
          const w = document.getElementById('cw-flash-word'); w.style.color = '';
          sayBack(sym.char, w);
          await sleep(REVEAL_MS);
        }
      }
      flash.hidden = true;
      lines.push('<li>Met ' + escapeHTML(step.chars.join(' ')) + '.</li>');
    } else if (step.kind === 'flash') {
      status.textContent = 'one at a time - ' + step.seconds + ' seconds';
      const r = await flashRun(step.seconds);
      if (r && r.sent) {
        const pct = Math.round(100 * r.right / r.sent);
        lines.push('<li>One at a time: <b>' + pct + '%</b> of ' + r.sent + (r.mean_ms ? ', ' + (r.mean_ms / 1000).toFixed(1) + ' s to the key when right' : '') +
          (r.resends ? ', ' + r.resends + ' resend' + (r.resends === 1 ? '' : 's') + ' asked for' : '') + '.</li>');
        const res = await postJSON('/api/cw/result', {per_char: r.perChar, settings: settings}).catch(() => null);
        if (res && res.progress) { CWS.progress = res.progress; renderProgress(); }
        freshBadges(res);
      }
    } else if (step.kind === 'koch' || step.kind === 'words' || step.kind === 'qso') {
      status.textContent = step.kind === 'koch' ? 'groups - type what you hear, then Check' : step.kind === 'words' ? 'words - type what you hear, then Check' : 'a contact - copy it, then Check';
      document.getElementById('cw-kind').value = step.kind;
      showMode('copy');
      await sendPractice(false);
      /* The copy pane takes it from here: the person types and checks at
         their own pace, and the Today pane is a press away. */
      lines.push('<li>' + (step.kind === 'koch' ? 'Groups' : step.kind === 'words' ? 'Words' : 'A contact') + ' sent - check them on the Copy pane.</li>');
      break;
    }
  }
  const seconds = Math.round((Date.now() - sessionStarted) / 1000);
  try { todayStreak = await postJSON('/api/cw/minutes', {seconds: seconds}); freshBadges(todayStreak); } catch (e) {}
  sessionOn = false;
  document.getElementById('cw-today-start').hidden = false;
  document.getElementById('cw-today-stop').hidden = true;
  status.textContent = sessionStop ? 'stopped' : '';
  result.innerHTML = lines.length ? '<ul class="small" style="margin:0;padding-left:1.2rem">' + lines.join('') + '</ul>' : '';
  await refreshPlan();
}

document.getElementById('cw-today-start').addEventListener('click', runSession);
document.getElementById('cw-today-stop').addEventListener('click', () => { sessionStop = true; flashKey = null; player.stop(); teachHalt(); });
renderToday();

/* Say back on the copy pane too, once the sending has finished (while it
   is still sounding a spoken word masks the next character): the key at
   this position is set against the character that was sent there, and
   what is said is the character sent, after a chime or a buzz. */
document.getElementById('cw-typed').addEventListener('keydown', e => {
  const box = document.getElementById('cw-sayback');
  if (!box || !box.checked || sending || !currentText) return;
  if (e.key.length !== 1 || e.key === ' ') return;
  const typed = (e.target.value || '').replace(/\s+/g, '');
  const sentChars = currentText.replace(/\s+/g, '');
  const want = sentChars[typed.length];
  if (!want) return;
  document.getElementById('cw-copy-status').textContent = sayBack(want, null, e.key.toUpperCase() === want);
});

/* ---------------------------------------------------------------- rating */
/* Two numbers a person can watch move: the speed they copy at and the
   speed they send at. Each is the top rung of a ladder they passed - nine in
   ten right at that speed - kept with the profile, and what the games set
   their level from. Copying: a block comes, they type it, the rung moves two
   words a minute either way and settles when a pass is followed by a fail.
   Sending: a line is shown on the keying pane, they key it, the decoder is
   scored against it, and the speed is their own dit on a straight key or
   the keyer's setting on a paddle. */
const PASS_PCT = 90, RUNG = 2, RUNG_LOW = 5, RUNG_HIGH = 40, LADDER_MOST = 8;
let ladder = null;              // {wpm, passed: [], failed: [], data, text, rungs}

async function paintRating() {
  let r = {};
  try { r = await api('/api/cw/rating'); } catch (e) { r = {}; }
  const c = document.getElementById('cw-rating-copy'), sd = document.getElementById('cw-rating-send');
  if (c) c.textContent = r.copy_wpm ? Math.round(r.copy_wpm) : '\u2014';
  if (sd) sd.textContent = r.send_wpm ? Math.round(r.send_wpm) : '\u2014';
  const acc = document.getElementById('cw-rating-send-acc');
  if (acc) acc.textContent = r.send_accuracy != null ? 'wpm \u00b7 ' + Math.round(r.send_accuracy) + '% clean' : 'wpm';
  const w = document.getElementById('cw-rating-when');
  if (w) w.textContent = r.when ? r.when.replace('T', ' ') : 'never';
  return r;
}

function ladderWord(w) { return w + ' wpm'; }

async function ladderRung(repeat) {
  const status = document.getElementById('cw-ladder-status');
  if (!repeat) {
    status.textContent = 'fetching ' + ladderWord(ladder.wpm) + '\u2026';
    ladder.data = await api('/api/cw/ladder?' + new URLSearchParams({wpm: ladder.wpm, count: 5}));
    ladder.text = ladder.data.plain || ladder.data.text;
    ladder.rungResends = 0;
    document.getElementById('cw-ladder-typed').value = '';
  } else {
    ladder.rungResends = (ladder.rungResends || 0) + 1;
    ladder.resends = (ladder.resends || 0) + 1;
  }
  document.getElementById('cw-ladder-typed').hidden = false;
  document.getElementById('cw-ladder-checkrow').hidden = false;
  document.getElementById('cw-ladder-repeat').hidden = true;
  status.textContent = 'rung ' + (ladder.rungs + 1) + ' \u00b7 ' + ladderWord(ladder.wpm) + ' \u2026';
  document.getElementById('cw-ladder-typed').focus();
  player.send(ladder.data.groups, ladder.data.timing, null, () => {
    status.textContent = ladderWord(ladder.wpm) + ' \u2014 type what you heard, then check';
    document.getElementById('cw-ladder-repeat').hidden = false;
  });
}

function ladderFinish(rated) {
  const res = document.getElementById('cw-ladder-result');
  document.getElementById('cw-ladder-start').hidden = false;
  document.getElementById('cw-ladder-stop').hidden = true;
  document.getElementById('cw-ladder-repeat').hidden = true;
  document.getElementById('cw-ladder-typed').hidden = true;
  document.getElementById('cw-ladder-checkrow').hidden = true;
  document.getElementById('cw-ladder-status').textContent = '';
  if (rated) {
    postJSON('/api/cw/rating', {copy_wpm: rated}).then(r => { paintRating(r); freshBadges(r); }).catch(() => null);
    res.innerHTML = '<div class="spread"><b>Rated: you copy at ' + ladderWord(rated) + '</b>' +
      '<span class="pill good">the top rung you passed</span></div>' +
      '<div class="tiny muted mt">passed ' + (ladder.passed.map(ladderWord).join(', ') || 'none') +
      (ladder.failed.length ? ' \u00b7 short at ' + ladder.failed.map(ladderWord).join(', ') : '') +
      (ladder.resends ? ' \u00b7 ' + ladder.resends + ' resend' + (ladder.resends === 1 ? '' : 's') + ' asked for along the way' : '') + '</div>';
  } else {
    res.innerHTML = '<div class="small muted">No rung passed - the ladder starts at ' + ladderWord(RUNG_LOW) +
      ' next time. Keep at the lessons; it comes.</div>';
  }
  ladder = null;
}

document.getElementById('cw-ladder-start').addEventListener('click', async () => {
  const r = await paintRating();
  ladder = {wpm: Math.max(RUNG_LOW, Math.min(RUNG_HIGH, Math.round(r.copy_wpm || 10))), passed: [], failed: [], rungs: 0};
  document.getElementById('cw-ladder-start').hidden = true;
  document.getElementById('cw-ladder-stop').hidden = false;
  document.getElementById('cw-ladder-result').innerHTML = '';
  ladderRung(false);
});
document.getElementById('cw-ladder-repeat').addEventListener('click', () => ladder && ladderRung(true));
document.getElementById('cw-ladder-stop').addEventListener('click', () => {
  player.stop();
  if (ladder) ladderFinish(ladder.passed.length ? Math.max(...ladder.passed) : null);
});
document.getElementById('cw-ladder-check').addEventListener('click', () => {
  if (!ladder || !ladder.text) return;
  player.stop();
  const a = ladder.text.replace(/\s+/g, ''), b = (document.getElementById('cw-ladder-typed').value || '').toUpperCase().replace(/\s+/g, '');
  let hits = 0;
  for (let i = 0; i < a.length; i++) if (a[i] === b[i]) hits++;
  const pct = a.length ? Math.round(100 * hits / a.length) : 0;
  ladder.rungs++;
  const res = document.getElementById('cw-ladder-result');
  const rr = ladder.rungResends || 0;
  res.innerHTML = '<div class="spread"><b>' + ladderWord(ladder.wpm) + ': ' + pct + '% copied</b>' +
    (rr ? '<span class="tiny muted">after ' + rr + ' resend' + (rr === 1 ? '' : 's') + '</span>' : '') +
    '<span class="pill ' + (pct >= PASS_PCT ? 'good' : 'warn') + '">' + (pct >= PASS_PCT ? 'passed - up two' : 'short - down two') + '</span></div>' +
    '<div class="tiny muted" style="margin-top:.3rem">sent: <span class="mono">' + escapeHTML(ladder.text) + '</span></div>';
  if (pct >= PASS_PCT) ladder.passed.push(ladder.wpm); else ladder.failed.push(ladder.wpm);
  const best = ladder.passed.length ? Math.max(...ladder.passed) : null;
  // Settled: a pass with a fail two above it, or the ladder's ends, or enough rungs.
  const settled = (best !== null && ladder.failed.includes(best + RUNG)) ||
                  (pct >= PASS_PCT && ladder.wpm >= RUNG_HIGH) || (pct < PASS_PCT && ladder.wpm <= RUNG_LOW) ||
                  ladder.rungs >= LADDER_MOST;
  if (settled) { ladderFinish(best); return; }
  ladder.wpm = Math.max(RUNG_LOW, Math.min(RUNG_HIGH, ladder.wpm + (pct >= PASS_PCT ? RUNG : -RUNG)));
  setTimeout(() => ladder && ladderRung(false), 1200);
});

/* Sending: on the keying pane. A line to key; the decoder is scored
   against it when Done is pressed or the line is long enough. */
let sendRate = null;            // {text}
document.getElementById('cw-send-rate').addEventListener('click', async () => {
  const d = await api('/api/cw/ladder?' + new URLSearchParams({wpm: settings.wpm, count: 3}));
  sendRate = {text: (d.plain || d.text).replace(/\s+/g, ' ').trim()};
  keyDecoder.reset(1200 / settings.wpm); lastUpAt = 0; keyer.prevEnd = null; renderKey();
  document.getElementById('cw-send-prompt').textContent = 'send: ' + sendRate.text;
  document.getElementById('cw-send-rate').hidden = true;
  document.getElementById('cw-send-rate-done').hidden = false;
});
document.getElementById('cw-send-rate-done').addEventListener('click', async () => {
  if (!sendRate) return;
  keyDecoder.flush();
  const a = sendRate.text.replace(/\s+/g, ''), b = (keyDecoder.text || '').toUpperCase().replace(/\s+/g, '');
  let hits = 0;
  for (let i = 0; i < a.length; i++) if (a[i] === b[i]) hits++;
  const pct = a.length ? Math.round(100 * hits / a.length) : 0;
  const st = keyDecoder.stats();
  const wpm = keyerMode === 'straight' ? (st.dit ? Math.round(1200 / st.dit) : null) : Math.round(settings.wpm);
  const rated = wpm && pct >= PASS_PCT;
  const box = document.getElementById('cw-key-timing');
  box.innerHTML = '<div class="spread"><b>' + pct + '% clean' + (wpm ? ' at ' + wpm + ' wpm' : '') + '</b>' +
    '<span class="pill ' + (rated ? 'good' : 'warn') + '">' + (rated ? 'rated' : 'nine in ten to rate it') + '</span></div>' +
    '<div class="tiny muted" style="margin-top:.3rem">asked: <span class="mono">' + escapeHTML(sendRate.text) +
    '</span> \u00b7 heard: <span class="mono">' + escapeHTML(keyDecoder.text || '\u2014') + '</span></div>' + box.innerHTML;
  if (rated) postJSON('/api/cw/rating', {send_wpm: wpm, send_accuracy: pct}).then(r => { paintRating(r); freshBadges(r); }).catch(() => null);
  else if (wpm) postJSON('/api/cw/rating', {send_accuracy: pct}).then(paintRating).catch(() => null);
  sendRate = null;
  document.getElementById('cw-send-prompt').textContent = '';
  document.getElementById('cw-send-rate').hidden = false;
  document.getElementById('cw-send-rate-done').hidden = true;
});
paintRating();
