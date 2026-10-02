/* The bench's calculators: the arithmetic the cards describe, for the
   numbers of the station in front of you. Each is guarded on its own
   elements, so the half that is not on this page does not start. Copper
   resistances and the fuse sizes are the ones in elmer/bench.py. */

const AWG_OHMS_PER_KFT = {4: 0.2485, 6: 0.3951, 8: 0.6282, 10: 0.9989, 12: 1.588, 14: 2.525,
                          16: 4.016, 18: 6.385, 20: 10.15, 22: 16.14};
const FUSES = [1, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100];

function benchNum(id, fallback) {
  const v = parseFloat(String(document.getElementById(id).value).replace(/[^-+0-9.]/g, ''));
  return isNaN(v) ? fallback : v;
}

/* R and X off an analyser: the SWR against 50 ohms, the impedance, and
   the instruction the sign carries. */
function benchAnalyser() {
  const r = benchNum('bc-r', 50), x = benchNum('bc-x', 0), z0 = 50;
  const out = document.getElementById('bc-out');
  if (r <= 0) { out.innerHTML = '<span class="muted">R has to be above zero - a reading of zero is a short.</span>'; return; }
  const rho = Math.hypot(r - z0, x) / Math.hypot(r + z0, x);
  const swr = rho < 1 ? (1 + rho) / (1 - rho) : Infinity;
  const mag = Math.hypot(r, x), phase = Math.atan2(x, r) * 180 / Math.PI;
  const cut = Math.abs(x) < 3 ? 'Resonant here: the reactance is gone, and what is left is the resistance.'
    : x > 0 ? 'Inductive (+X): the antenna is long for this frequency. Shorten it a little and sweep again.'
    : 'Capacitive (-X): the antenna is short for this frequency. Add a little and sweep again.';
  const match = swr <= 1.5 ? 'a good match' : swr <= 3 ? 'usable - a tuner will take it' : 'a poor match - look for a fault before cutting anything';
  out.innerHTML = '<b>SWR ' + (isFinite(swr) ? swr.toFixed(2) + ':1' : 'off the scale') + '</b> - ' + match +
    '. |Z| ' + mag.toFixed(0) + ' &Omega; at ' + phase.toFixed(0) + '&deg;. ' + cut +
    (r > 0 && r < 20 && Math.abs(x) < 3 ? ' A low resistance at resonance is a vertical without enough radials, or a dipole too near the ground.' : '') +
    (r > 150 && Math.abs(x) < 3 ? ' A high resistance at resonance is an end-fed or a full-wave loop - fed at a voltage point, and wanting a transformer.' : '') +
    (Math.abs(x) >= 3 ? '<div class="tiny muted" style="margin-top:.35rem">Whether to cut at all: if this antenna lives here, cut to it. If it travels, do not - resonance moves with height and with whatever is near the wire, so a length trimmed to this site is wrong at the next. Note the reading, let the tuner take the reactance, and spend the effort on height and clear ground. A match matters on transmit; on receive it matters least of all.</div>' : '');
}

/* The volts lost along the DC lead, and the fuse for the load. */
function benchDrop() {
  const awg = parseInt(document.getElementById('bd-awg').value, 10);
  const feet = benchNum('bd-feet', 10), amps = benchNum('bd-amps', 20);
  const ohms = AWG_OHMS_PER_KFT[awg] / 1000 * feet * 2;
  const drop = ohms * amps;
  const at = 13.8 - drop;
  const fuse = FUSES.find(f => f >= amps * 1.25);
  const verdict = drop < 0.5 ? 'a good run.' : drop < 1.0 ? 'on the edge - the radio will see it on transmit.'
    : 'too much: the radio will fold back or drop out on transmit. Go two gauges heavier, or shorter.';
  const better = Object.keys(AWG_OHMS_PER_KFT).map(Number).filter(g => g < awg).sort((a, b) => b - a)
    .find(g => AWG_OHMS_PER_KFT[g] / 1000 * feet * 2 * amps < 0.5);
  document.getElementById('bd-out').innerHTML =
    '<b>' + drop.toFixed(2) + ' V lost</b> along ' + feet + ' ft of ' + awg + ' AWG at ' + amps + ' A (' + (ohms * 1000).toFixed(0) +
    ' m&Omega; there and back): the radio sees about <b>' + at.toFixed(1) + ' V</b> from a 13.8 V supply - ' + verdict +
    (better && drop >= 0.5 ? ' ' + better + ' AWG would lose under half a volt.' : '') +
    (fuse ? ' Fuse the positive lead at the supply end with <b>' + fuse + ' A</b> (a quarter above the ' + amps + ' A draw).' : '');
}

/* Hours on the air from a battery, receive and transmit counted apart. */
function benchBattery() {
  const ah = benchNum('bb-ah', 20), rx = benchNum('bb-rx', 1), tx = benchNum('bb-tx', 20);
  const share = Math.max(0, Math.min(100, benchNum('bb-share', 20))) / 100;
  const draw = rx * (1 - share) + tx * share;
  const out = document.getElementById('bb-out');
  if (draw <= 0) { out.textContent = ''; return; }
  const hours = ah * 0.8 / draw;
  out.innerHTML = 'Average draw <b>' + draw.toFixed(1) + ' A</b> with the transmitter on ' + Math.round(share * 100) + '% of the time: about <b>' +
    (hours >= 1 ? hours.toFixed(1) + ' hours' : Math.round(hours * 60) + ' minutes') + '</b> from ' + ah + ' Ah, using four fifths of it - ' +
    'the last fifth is what a lead-acid battery will not forgive. Listening only: ' + (ah * 0.8 / rx).toFixed(0) + ' hours. Transmitting the whole time: ' +
    (ah * 0.8 / tx * 60).toFixed(0) + ' minutes.';
}

/* The pool's ten feet: a fall must not reach the line. */
function benchFall() {
  const h = benchNum('bf-h', 30), d = benchNum('bf-d', 35);
  const need = h + 10;
  const out = document.getElementById('bf-out');
  out.innerHTML = d >= need
    ? '<b>Clear.</b> A ' + h + ' ft mast falling full length reaches ' + h + ' ft from its base; the line at ' + d + ' ft is ' + (d - need).toFixed(0) +
      ' ft beyond the ten-foot rule. Look up before every raise all the same.'
    : '<b style="color:var(--red)">Not there.</b> A ' + h + ' ft mast needs the line at least <b>' + need + ' ft</b> from its base - its own height plus ten feet - and it is ' + d +
      ' ft. Move the base ' + (need - d).toFixed(0) + ' ft further away, or lower the mast to ' + Math.max(0, d - 10).toFixed(0) + ' ft. Never attach anything to a utility pole.';
}

/* The reactive near field: a wavelength over two pi. A conductor inside it
   is part of the antenna; a noise source inside it is in the receiver. */
const NEAR_BANDS = [['160 m', 1.9], ['80 m', 3.6], ['40 m', 7.1], ['20 m', 14.2], ['10 m', 28.4], ['6 m', 50.1], ['2 m', 146], ['70 cm', 446]];
/* Computed in metres; read in the operator's own. The name keeps 'Ft'
   because every caller below is about a distance you pace out. */
function nearFieldM(mhz) { return 299.792458 / mhz / (2 * Math.PI); }
function nearFieldFt(mhz) { return high(nearFieldM(mhz), 2); }
function benchNear() {
  const mhz = benchNum('bn-mhz', 7.1), d = benchNum('bn-d', 30);
  const nf = nearFieldFt(mhz);
  const out = document.getElementById('bn-out');
  const verdict = d <= nf
    ? '<b style="color:var(--red)">Inside.</b> At ' + mhz + ' MHz the near field reaches about <b>' + nf.toFixed(0) + ' ft</b>, and the thing at ' + d +
      ' ft is inside it: it is coupled to the antenna - detuning it, and if it makes noise, feeding that noise straight in. Moving to ' + Math.ceil(nf + 1) +
      ' ft gets it out of the near field; every doubling beyond that cuts what it couples by a quarter.'
    : '<b>Outside.</b> At ' + mhz + ' MHz the near field reaches about <b>' + nf.toFixed(0) + ' ft</b>; the thing at ' + d + ' ft is ' + (d - nf).toFixed(0) +
      ' ft beyond it. It still radiates noise the antenna can hear - at ' + (2 * d) + ' ft that would be a quarter of it, at ' + (4 * d) + ' ft a sixteenth.';
  out.innerHTML = verdict + '<table class="data mt" style="max-width:26rem"><thead><tr><th>Band</th><th>Near field</th></tr></thead><tbody>' +
    NEAR_BANDS.map(([n, f]) => '<tr><td>' + n + '</td><td class="mono">' + (nearFieldFt(f) >= 10 ? highText(nearFieldM(f)) : highText(nearFieldM(f), 1)) + '</td></tr>').join('') +
    '</tbody></table><div class="tiny muted">A wavelength over two pi - the boundary of the reactive near field for a wire-sized antenna. A rule of thumb, not a wall: coupling fades across it rather than stopping at it.</div>';
}

/* The terminator: a bank of identical resistors, s in series and p strings
   in parallel, so each carries an equal share of the heat. The same
   arithmetic as bench.termination_bank, and the tests hold that one. */
const E12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82];
const E24 = [10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91];
const RESISTOR_VOLTS = 350;

function seriesValues(series) {
  const out = [];
  for (let k = 0; k < 6; k++) (series === 'E12' ? E12 : E24).forEach(v => out.push(+(v * Math.pow(10, k) / 10).toFixed(6)));
  return out;
}

/* "1k", "4.7k", "1M", "106" -> ohms. */
function ohmsOf(text) {
  const m = String(text).trim().toLowerCase().match(/^([0-9]*\.?[0-9]+)\s*([km]?)/);
  if (!m) return NaN;
  return parseFloat(m[1]) * (m[2] === 'k' ? 1e3 : m[2] === 'm' ? 1e6 : 1);
}

function bankCandidates(target, watts, share, dissipate, each, pool, tol, fewest, above, most) {
  const out = [];
  for (let s = 1; s <= most; s++) {
    for (let p = 1; p <= Math.floor(most / s); p++) {
      const parts = s * p;
      if (parts < fewest || parts <= above) continue;
      const want = target * p / s;
      let value = pool[0];
      pool.forEach(v => { if (Math.abs(Math.log(v / want)) < Math.abs(Math.log(value / want))) value = v; });
      const total = value * s / p, error = total / target - 1;
      if (Math.abs(error) > tol + 1e-12) continue;
      const volts = Math.sqrt(watts * share * total) * Math.SQRT2 / s;
      out.push({series: s, parallel: p, parts: parts, value: value, total: total, error: error,
                watts_each: dissipate / parts, volts_peak_each: volts, volts_ok: volts <= RESISTOR_VOLTS});
    }
  }
  return out;
}

function terminationBank(target, watts, share, duty, margin, each, values, tol, maxParts, best) {
  tol = tol || 0.10; maxParts = maxParts || 400; best = best || 4;
  if (!(target > 0) || !(watts >= 0) || !(each > 0)) return null;
  const dissipate = watts * share * duty, rated = dissipate * margin;
  const fewest = Math.max(1, Math.ceil(rated / each - 1e-9));
  const pool = [...new Set((values && values.length ? values : seriesValues('E24')).filter(v => v > 0))].sort((a, b) => a - b);
  if (!pool.length) return null;
  let most = Math.min(maxParts, Math.max(fewest + 3, Math.ceil(fewest * 1.25))), looked = 0, cands = [];
  while (!cands.length && looked < maxParts) {
    cands = bankCandidates(target, watts, share, dissipate, each, pool, tol, fewest, looked, most);
    looked = most; most = Math.min(maxParts, most * 2);
  }
  const plan = {dissipate: dissipate, rated: rated, fewest: fewest, banks: []};
  if (!cands.length) return plan;
  const rank = b => [b.volts_ok ? 0 : 1, Math.round(Math.abs(b.error) / 0.02),
                     Math.max(b.series, b.parallel) / Math.min(b.series, b.parallel) > 8 ? 1 : 0, b.parts];
  const cmp = (a, b) => { const x = rank(a), y = rank(b); for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] - y[i]; return 0; };
  const least = Math.min(...cands.map(b => b.parts));
  const picked = [cands.filter(b => b.parts === least).sort(cmp)[0]];
  cands.slice().sort(cmp).forEach(b => {
    if (picked.length < best && picked.every(q => q.series !== b.series || q.parallel !== b.parallel)) picked.push(b);
  });
  picked.sort((a, b) => a.parts - b.parts || Math.abs(a.error) - Math.abs(b.error));
  plan.banks = picked;
  return plan;
}

function ohmsText(v) {
  return v >= 1e6 ? +(v / 1e6).toFixed(2) + ' M&Omega;' : v >= 1e3 ? +(v / 1e3).toFixed(2) + ' k&Omega;' : +v.toFixed(1) + ' &Omega;';
}

function benchTerminator() {
  const target = benchNum('bt-ohms', 600), watts = benchNum('bt-watts', 100);
  const share = Math.max(0, Math.min(100, benchNum('bt-share', 50))) / 100;
  const duty = parseFloat(document.getElementById('bt-duty').value) || 1;
  const each = parseFloat(document.getElementById('bt-each').value) || 2;
  const margin = Math.max(1, benchNum('bt-margin', 1.5));
  const which = document.getElementById('bt-series').value;
  const have = String(document.getElementById('bt-have').value).split(/[,;\s]+/).map(ohmsOf).filter(v => v > 0);
  const out = document.getElementById('bt-out');
  if (which === 'have' && !have.length) { out.innerHTML = '<span class="muted">Type the values you have, separated by commas - 106, 470, 1k.</span>'; return; }
  const plan = terminationBank(target, watts, share, duty, margin, each, which === 'have' ? have : seriesValues(which));
  if (!plan) { out.innerHTML = '<span class="muted">The terminator, the power and the rating all have to be above zero.</span>'; return; }
  const head = 'The terminator takes about <b>' + plan.dissipate.toFixed(1) + ' W</b> (' + Math.round(share * 100) + '% of ' + watts +
    ' W' + (duty < 1 ? ', averaged for the mode' : ', full carrier') + '). Rated ' + margin + ' times that, the bank wants <b>' +
    plan.rated.toFixed(0) + ' W</b> of resistors: at least <b>' + plan.fewest + '</b> of ' + each + ' W each.';
  if (!plan.banks.length) {
    out.innerHTML = head + ' <span style="color:var(--amber)">No bank of identical resistors from these values lands within 10% of ' +
      target + ' &Omega; - try another value, or a bigger rating each.</span>';
    return;
  }
  const rows = plan.banks.map(b =>
    '<tr><td class="mono">' + b.parts + ' &times; ' + ohmsText(b.value) + '</td><td>' +
    (b.series === 1 ? 'all ' + b.parallel + ' in parallel' : b.parallel === 1 ? 'all ' + b.series + ' in series'
      : b.parallel + ' strings of ' + b.series + ' in series, the strings in parallel') +
    '</td><td class="mono">' + ohmsText(b.total) + (Math.abs(b.error) >= 0.0005 ? ' (' + (b.error > 0 ? '+' : '') + (b.error * 100).toFixed(1) + '%)' : '') +
    '</td><td class="mono">' + b.watts_each.toFixed(2) + ' W</td><td class="mono"' + (b.volts_ok ? '' : ' style="color:var(--amber)"') + '>' +
    b.volts_peak_each.toFixed(0) + ' V</td></tr>').join('');
  const hot = plan.banks.some(b => !b.volts_ok);
  out.innerHTML = head +
    '<table class="data mt"><thead><tr><th>Bank</th><th>Wired</th><th>Total</th><th>Each carries</th><th>Peak volts each</th></tr></thead><tbody>' +
    rows + '</tbody></table>' +
    (hot ? '<div class="tiny" style="color:var(--amber)">A bank in amber puts more than ' + RESISTOR_VOLTS + ' V peak across each part, ' +
      'which is past what many small resistors are rated for - read the datasheet, or take a bank with more in series.</div>' : '') +
    '<div class="tiny muted" style="margin-top:.35rem">Every part the same value and rating, so they share the heat equally. ' +
    'Non-inductive only - metal oxide, carbon composition or film, or thick-film on a heat sink; never wirewound. ' +
    'Before it goes up, the meter should read the total within a few percent.</div>';
}

['bt-ohms', 'bt-watts', 'bt-share', 'bt-duty', 'bt-each', 'bt-series', 'bt-have', 'bt-margin'].forEach(id => {
  const el = document.getElementById(id);
  if (el) { el.addEventListener('input', benchTerminator); el.addEventListener('change', benchTerminator); }
});
if (document.getElementById('bt-out')) benchTerminator();
if (document.getElementById('bn-go')) { document.getElementById('bn-go').addEventListener('click', benchNear); benchNear(); }
if (document.getElementById('bc-go')) { document.getElementById('bc-go').addEventListener('click', benchAnalyser); benchAnalyser(); }
if (document.getElementById('bd-go')) { document.getElementById('bd-go').addEventListener('click', benchDrop); benchDrop(); }
if (document.getElementById('bb-ah')) { ['bb-ah', 'bb-rx', 'bb-tx', 'bb-share'].forEach(id => document.getElementById(id).addEventListener('input', benchBattery)); benchBattery(); }
if (document.getElementById('bf-go')) { document.getElementById('bf-go').addEventListener('click', benchFall); benchFall(); }
