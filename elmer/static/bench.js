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

if (document.getElementById('bn-go')) { document.getElementById('bn-go').addEventListener('click', benchNear); benchNear(); }
if (document.getElementById('bc-go')) { document.getElementById('bc-go').addEventListener('click', benchAnalyser); benchAnalyser(); }
if (document.getElementById('bd-go')) { document.getElementById('bd-go').addEventListener('click', benchDrop); benchDrop(); }
if (document.getElementById('bb-ah')) { ['bb-ah', 'bb-rx', 'bb-tx', 'bb-share'].forEach(id => document.getElementById(id).addEventListener('input', benchBattery)); benchBattery(); }
if (document.getElementById('bf-go')) { document.getElementById('bf-go').addEventListener('click', benchFall); benchFall(); }
