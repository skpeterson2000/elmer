/* Morse, shared: the tone player and the decoder, as the CW page and the
   Gaming Center both need them - one plays the pitch, the other reads the
   throw. Load before cw.js or the party pages. */

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

