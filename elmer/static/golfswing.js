/* The golfer's own hand in the shot - the phone's and the table screen's.

   Before the question a golfer sets the shot up: its shape, draw to fade,
   and its spin, none to all the club has. After choosing an answer they
   swing at the meter - it bounces from nothing to a full swing and back,
   and Hit stops it. The notch on the meter is where the mark wants the
   swing; the band round it is the sweet zone. The server holds the rules
   (golf.py, "the golfer's own hand in the shot"); this is only the hands.

   The meter's speed is the golfer's, kept on the device: slower is not
   easier golf, it is golf somebody's hands can play. It is never turned
   off - a swing nobody makes is luck, and the point is to take luck out.
*/
(function () {
  const SPEEDS = [
    {name: 'slowest', period: 4.0},
    {name: 'slow', period: 3.0},
    {name: 'steady', period: 2.2},
    {name: 'quick', period: 1.6},
    {name: 'quickest', period: 1.1},
  ];
  const KEY = 'elmer_golf_meter_speed';
  const DEFAULT_SPEED = 2;

  function speed() {
    try {
      const v = parseInt(localStorage.getItem(KEY), 10);
      if (v >= 0 && v < SPEEDS.length) return v;
    } catch (e) { /* storage refused - the default is fine */ }
    return DEFAULT_SPEED;
  }
  function setSpeed(i) {
    try { localStorage.setItem(KEY, String(i)); } catch (e) { /* kept for this page only */ }
  }

  const css = `
.gs-set { margin: .5rem 0; }
.gs-row { display: flex; align-items: center; gap: .5rem; margin: .35rem 0; }
.gs-row label { min-width: 3.4rem; font-size: .85rem; color: var(--dim, #aab); }
.gs-row input[type=range] { flex: 1; accent-color: var(--amber, #e8a33d); height: 1.6rem; }
.gs-row .gs-said { min-width: 6.5rem; font-size: .8rem; text-align: right; }
.gs-ends { display: flex; justify-content: space-between; font-size: .7rem; color: var(--dimmer, #778); margin: -.3rem 0 .2rem 3.9rem; }
.gs-speed { display: flex; gap: .3rem; flex-wrap: wrap; }
.gs-speed button { flex: 1; padding: .35rem .2rem; font-size: .75rem; border-radius: 6px;
  border: 1px solid #3a4250; background: #161a21; color: inherit; }
.gs-speed button.on { border-color: var(--amber, #e8a33d); background: #2a2216; }
.gs-meter { position: relative; height: 2.6rem; border-radius: 8px; background: #11151b;
  border: 1px solid #3a4250; overflow: hidden; margin: .5rem 0; touch-action: manipulation; }
.gs-meter .gs-fill { position: absolute; left: 0; top: 0; bottom: 0; background: linear-gradient(90deg, #1e3a26, #2f6b3c); }
.gs-meter .gs-sweet { position: absolute; top: 0; bottom: 0; background: rgba(232, 163, 61, .28); }
.gs-meter .gs-notch { position: absolute; top: -2px; bottom: -2px; width: 3px; margin-left: -1px; background: var(--amber, #e8a33d); }
.gs-meter .gs-tick { position: absolute; bottom: 0; height: 30%; width: 1px; background: #3a4250; }
.gs-meter .gs-need { position: absolute; top: 1px; font: 600 .62rem ui-monospace, monospace; color: var(--amber, #e8a33d); }
.gs-meter .gs-cursor { position: absolute; top: 0; bottom: 0; width: 4px; margin-left: -2px; background: #f4f4f4; }
.gs-meter.idle { opacity: .45; }
.gs-hit { display: block; width: 100%; padding: .9rem; font-size: 1.3rem; font-weight: 700; border-radius: 10px;
  border: 2px solid var(--amber, #e8a33d); background: #2a2216; color: inherit; }
.gs-hit[disabled] { opacity: .4; }
`;
  function style() {
    if (document.getElementById('golfswing-css')) return;
    const s = document.createElement('style');
    s.id = 'golfswing-css';
    s.textContent = css;
    document.head.appendChild(s);
  }

  function shapeWords(v) {
    const a = Math.abs(v);
    if (a < 0.1) return 'straight';
    const how = a < 0.4 ? 'a little ' : a < 0.75 ? '' : 'a big ';
    return how + (v < 0 ? 'draw' : 'fade');
  }
  function spinWords(v, cap) {
    const eff = v * (cap == null ? 1 : cap);
    if (v < 0.05) return 'none';
    if (cap != null && cap < 0.25) return 'little to give';
    if (eff > 0.6) return 'bites back';
    return eff > 0.35 ? 'checks it' : 'a touch';
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  }

  /* The set-up: shape, spin and the meter's speed. `shot` is {shape, spin}
     as the server has it; `reading` the mark's reading for the club in hand
     (its spin_cap says how much spin that club has at all). */
  function setupHTML(shot, reading, prefix) {
    style();
    const p = prefix || 'gs';
    const sh = (shot && shot.shape) || 0, sp = (shot && shot.spin) || 0;
    const cap = reading ? reading.spin_cap : null;
    const cur = speed();
    return `<div class="gs-set" data-gs="${p}">
      <div class="gs-row"><label for="${p}-shape">Shape</label>
        <input type="range" id="${p}-shape" min="-100" max="100" step="5" value="${Math.round(sh * 100)}">
        <span class="gs-said" id="${p}-shape-said">${esc(shapeWords(sh))}</span></div>
      <div class="gs-ends"><span>&#9664; draw</span><span>fade &#9654;</span></div>
      <div class="gs-row"><label for="${p}-spin">Spin</label>
        <input type="range" id="${p}-spin" min="0" max="100" step="5" value="${Math.round(sp * 100)}">
        <span class="gs-said" id="${p}-spin-said">${esc(spinWords(sp, cap))}</span></div>
      <div class="gs-row"><label>Meter</label><div class="gs-speed">${SPEEDS.map((s, i) =>
        `<button type="button" data-gs-speed="${i}" class="${i === cur ? 'on' : ''}">${s.name}</button>`).join('')}</div></div>
    </div>`;
  }

  /* Wire the set-up: `post({shape, spin})` sends a change to the server,
     on release - a slider dragged sends once, not fifty times. */
  function wireSetup(root, reading, post, prefix) {
    const p = prefix || 'gs';
    const box = (root || document).querySelector(`[data-gs="${p}"]`);
    if (!box) return;
    const cap = reading ? reading.spin_cap : null;
    const shape = box.querySelector(`#${p}-shape`), spin = box.querySelector(`#${p}-spin`);
    const shapeSaid = box.querySelector(`#${p}-shape-said`), spinSaid = box.querySelector(`#${p}-spin-said`);
    shape.addEventListener('input', () => { shapeSaid.textContent = shapeWords(shape.value / 100); });
    spin.addEventListener('input', () => { spinSaid.textContent = spinWords(spin.value / 100, cap); });
    shape.addEventListener('change', () => post({shape: shape.value / 100}));
    spin.addEventListener('change', () => post({spin: spin.value / 100}));
    box.querySelectorAll('[data-gs-speed]').forEach(b => b.addEventListener('click', () => {
      setSpeed(parseInt(b.dataset.gsSpeed, 10));
      box.querySelectorAll('[data-gs-speed]').forEach(x => x.classList.toggle('on', x === b));
    }));
  }

  /* One line for the question screen: the shot as it is set up. */
  function summary(shot, reading) {
    const sh = (shot && shot.shape) || 0, sp = (shot && shot.spin) || 0;
    const cap = reading ? reading.spin_cap : null;
    return `${shapeWords(sh)}, spin ${spinWords(sp, cap)}`;
  }

  function meterHTML(reading, prefix) {
    style();
    const p = prefix || 'gs';
    const need = reading && reading.need != null ? reading.need : 1;
    const sweet = reading && reading.sweet != null ? reading.sweet : 0.03;
    const lo = Math.max(0, need - sweet), hi = Math.min(1, need + sweet);
    return `<div class="gs-meter idle" id="${p}-meter">
        <div class="gs-fill" id="${p}-fill" style="width:0"></div>
        <div class="gs-sweet" style="left:${(lo * 100).toFixed(1)}%;width:${((hi - lo) * 100).toFixed(1)}%"></div>
        <div class="gs-notch" style="left:${(need * 100).toFixed(1)}%"></div>
        ${[25, 50, 75].map(t => `<div class="gs-tick" style="left:${t}%"></div>`).join('')}
        <div class="gs-need" style="left:${Math.min(88, Math.max(2, need * 100 - 6)).toFixed(1)}%">${(need * 100).toFixed(1)}</div>
        <div class="gs-cursor" id="${p}-cursor" style="left:0"></div></div>
      <button type="button" class="gs-hit" id="${p}-hit" disabled>Hit</button>`;
  }

  /* The meter itself. start() sets it bouncing from nothing; read() is where
     it is now, 0..1 of a full swing; stop() freezes it there. It stops by
     itself when its element leaves the page. */
  function meter(prefix) {
    const p = prefix || 'gs';
    let running = false, t0 = 0, frozen = null, raf = 0;
    const period = SPEEDS[speed()].period * 1000;
    function pos(now) {
      const phase = ((now - t0) / period) % 1;
      return phase < 0.5 ? phase * 2 : 2 - phase * 2;
    }
    function frame(now) {
      const cursor = document.getElementById(`${p}-cursor`), fill = document.getElementById(`${p}-fill`);
      if (!cursor || !running) { running = false; return; }
      const v = pos(now);
      cursor.style.left = (v * 100).toFixed(2) + '%';
      fill.style.width = (v * 100).toFixed(2) + '%';
      raf = requestAnimationFrame(frame);
    }
    return {
      start() {
        if (running) return;
        const el = document.getElementById(`${p}-meter`);
        if (el) el.classList.remove('idle');
        const hit = document.getElementById(`${p}-hit`);
        if (hit) hit.disabled = false;
        running = true; frozen = null; t0 = performance.now();
        raf = requestAnimationFrame(frame);
      },
      running() { return running; },
      read() { return frozen != null ? frozen : running ? pos(performance.now()) : null; },
      // `when` is the moment of the press - the event's own time stamp -
      // not the moment the page got round to handling it, which can be a
      // frame or two later. The difference is the next decimal place.
      stop(when) {
        if (!running) return frozen;
        const at = (typeof when === 'number' && when > 0 && when <= performance.now() + 1) ? when : performance.now();
        frozen = pos(at);
        running = false;
        cancelAnimationFrame(raf);
        const cursor = document.getElementById(`${p}-cursor`), fill = document.getElementById(`${p}-fill`);
        if (cursor) cursor.style.left = (frozen * 100).toFixed(2) + '%';
        if (fill) fill.style.width = (frozen * 100).toFixed(2) + '%';
        return Math.round(frozen * 10000) / 10000;
      },
    };
  }

  /* The swing said back: where it stopped against the notch, to a tenth of a
     percent, and the strike in a word. For the result on either screen. */
  function strikeLine(shot) {
    if (!shot || shot.meter == null || shot.meter_need == null) return '';
    const at = (shot.meter * 100).toFixed(1), want = (shot.meter_need * 100).toFixed(1);
    const off = ((shot.meter - shot.meter_need) * 100).toFixed(1);
    return `Stopped at ${at} &middot; notch ${want} (${off > 0 ? '+' : ''}${off}) &middot; ${esc(shot.strike || '')}`;
  }

  window.GolfSwing = {setupHTML, wireSetup, summary, meterHTML, meter, speed, SPEEDS, strikeLine};
})();
