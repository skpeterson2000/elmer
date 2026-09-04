/* Lab: live calculators. Every formula here is one the pools ask about, so the
   wording of the outputs deliberately mirrors the exam vocabulary. */

/* ------------------------------------------------------------------ tabs */
function selectTab(name) {
  const btn = document.querySelector('#lab-tabs button[data-tab="' + name + '"]');
  if (!btn) return false;
  document.querySelectorAll('#lab-tabs button').forEach(b => {
    b.classList.toggle('primary', b === btn);
    b.classList.toggle('ghost', b !== btn);
  });
  document.querySelectorAll('.lab-pane').forEach(p => {
    p.hidden = p.id !== 'pane-' + name;
  });
  return true;
}

document.querySelectorAll('#lab-tabs button').forEach(btn => {
  btn.addEventListener('click', () => {
    selectTab(btn.dataset.tab);
    history.replaceState(null, '', '#' + btn.dataset.tab);
  });
});

/* A concept note links here as /lab#skip, so honour the fragment on arrival. */
function openFromHash() {
  const name = (location.hash || '').replace('#', '');
  if (name) selectTab(name);
}
window.addEventListener('hashchange', openFromHash);

const num = id => parseFloat(document.getElementById(id).value);
const out = (id, html) => { document.getElementById(id).innerHTML = html; };
const sig = (v, n) => Number(v).toPrecision(n || 4).replace(/\.?0+$/, '');

/* --------------------------------------------------- ionospheric hop sim */
const EARTH_R = 6371;

function mufFactor(elevDeg, h) {
  /* Angle of incidence at the layer, allowing for the curvature of the earth:
     sin(phi) = R*cos(elevation) / (R + h).  The flat-earth secant law blows up
     at low takeoff angles and would claim a MUF of 90 MHz; the real M-factor
     tops out near 3.4. */
  const sinPhi = Math.min(1, EARTH_R * Math.cos(elevDeg * Math.PI / 180) / (EARTH_R + h));
  const phi = Math.asin(sinPhi);
  return { factor: 1 / Math.cos(phi), phi: phi * 180 / Math.PI };
}

function hopKm(elevDeg, h) {
  const psi = 90 - elevDeg - mufFactor(elevDeg, h).phi;   // earth-central angle
  return 2 * EARTH_R * Math.max(0, psi) * Math.PI / 180;
}

function maxTakeoff(f, fof2, h) {
  /* Highest takeoff angle whose MUF still reaches f. Null means the band is
     closed on this path at every angle. */
  if (fof2 >= f) return 90;
  const sinPhi = Math.sqrt(1 - (fof2 / f) ** 2);
  const c = sinPhi * (EARTH_R + h) / EARTH_R;
  return c > 1 ? null : Math.acos(c) * 180 / Math.PI;
}

function drawSkip() {
  const f = num('s-f'), fof2 = num('s-fof2'), h = num('s-h');
  document.getElementById('s-f-v').textContent = f.toFixed(1) + ' MHz';
  document.getElementById('s-fof2-v').textContent = fof2.toFixed(1) + ' MHz';
  document.getElementById('s-h-v').textContent = h + ' km';

  const thetaMax = maxTakeoff(f, fof2, h);
  const nvis = thetaMax === 90;
  const closed = thetaMax === null;
  const skipKm = (nvis || closed) ? 0 : hopKm(thetaMax, h);
  const bestMuf = fof2 * mufFactor(0, h).factor;         // lowest angle, highest MUF

  const svg = document.getElementById('s-svg');
  const W = 640, ground = 250;
  const layerY = ground - Math.min(150, h * 0.42);
  const maxKm = 4200;
  const x = km => 40 + (km / maxKm) * (W - 70);

  const rayPaths = [5, 10, 20, 30, 45, 65, 88].map(angle => {
    const escapes = closed || (!nvis && angle > thetaMax);
    if (escapes) {
      const rise = ground - layerY;
      const ex = x(0) + (rise / Math.tan(angle * Math.PI / 180) / maxKm) * (W - 70);
      const cont = ex + ((layerY - 5) / Math.tan(angle * Math.PI / 180) / maxKm) * (W - 70);
      return '<path d="M' + x(0) + ',' + ground + ' L' + ex + ',' + layerY +
             ' L' + Math.min(W, cont) + ',6" stroke="#f85149" stroke-width="1.3" ' +
             'fill="none" stroke-dasharray="4 3" opacity=".8"/>';
    }
    const land = x(hopKm(angle, h));
    if (land > W - 12) return '';
    return '<path d="M' + x(0) + ',' + ground + ' Q' + ((x(0) + land) / 2) + ',' +
           (layerY - 12) + ' ' + land + ',' + ground +
           '" stroke="#3fb950" stroke-width="1.6" fill="none" opacity=".9"/>' +
           '<circle cx="' + land + '" cy="' + ground + '" r="3" fill="#3fb950"/>';
  }).join('');

  const skipMark = (!nvis && !closed && x(skipKm) < W - 12)
    ? '<line x1="' + x(0) + '" y1="' + (ground + 16) + '" x2="' + x(skipKm) + '" y2="' + (ground + 16) +
      '" stroke="#f85149" stroke-width="1.5"/>' +
      '<text x="' + ((x(0) + x(skipKm)) / 2) + '" y="' + (ground + 31) +
      '" fill="#f85149" font-size="11" text-anchor="middle" font-family="monospace">skip zone ' +
      Math.round(skipKm) + ' km</text>'
    : '<text x="' + x(0) + '" y="' + (ground + 31) + '" font-size="11" font-family="monospace" fill="' +
      (closed ? '#f85149' : '#3fb950') + '">' +
      (closed ? 'above the MUF at every angle — nothing comes back'
              : 'below foF2 — NVIS, no skip zone') + '</text>';

  svg.innerHTML =
    '<defs><linearGradient id="ion" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#39d3d8" stop-opacity=".28"/>' +
      '<stop offset="100%" stop-color="#39d3d8" stop-opacity="0"/></linearGradient></defs>' +
    '<rect x="0" y="' + (layerY - 22) + '" width="' + W + '" height="44" fill="url(#ion)"/>' +
    '<line x1="0" y1="' + layerY + '" x2="' + W + '" y2="' + layerY +
      '" stroke="#39d3d8" stroke-width="1" stroke-dasharray="6 4" opacity=".7"/>' +
    '<text x="8" y="' + (layerY - 8) + '" fill="#39d3d8" font-size="11" font-family="monospace">' +
      'F2 layer — ' + h + ' km, foF2 ' + fof2.toFixed(1) + ' MHz</text>' +
    rayPaths +
    '<line x1="0" y1="' + ground + '" x2="' + W + '" y2="' + ground + '" stroke="#8b98a5" stroke-width="1.5"/>' +
    '<circle cx="' + x(0) + '" cy="' + ground + '" r="4" fill="#ffb454"/>' +
    '<text x="' + (x(0) - 6) + '" y="' + (ground - 8) + '" fill="#ffb454" font-size="11" font-family="monospace">TX</text>' +
    skipMark +
    [1000, 2000, 3000, 4000].map(d =>
      '<text x="' + x(d) + '" y="' + (ground + 46) + '" fill="#626e7b" font-size="10" ' +
      'text-anchor="middle" font-family="monospace">' + d + ' km</text>').join('');

  out('s-out',
    '<div class="row" style="gap:1.4rem">' +
      '<span>foF2 (straight up): <b>' + fof2.toFixed(1) + ' MHz</b></span>' +
      '<span>Best-case MUF: <b>' + bestMuf.toFixed(1) + ' MHz</b> at a grazing takeoff</span>' +
      '<span>Highest usable takeoff angle: <b>' +
        (nvis ? 'any, even vertical' : closed ? 'none' : thetaMax.toFixed(1) + '&deg;') + '</b></span>' +
    '</div>' +
    '<p class="small muted" style="margin-top:.6rem">' +
    (nvis
      ? sig(f) + ' MHz is at or below foF2, so signals return at every angle including straight up. ' +
        'That is near-vertical incidence skywave — solid regional coverage with no skip zone.'
      : closed
      ? sig(f) + ' MHz is above the MUF even at the lowest takeoff angle (' + bestMuf.toFixed(1) +
        ' MHz), so every ray passes through the layer and out into space. The band is closed on this path — ' +
        'this is exactly what "10 metres is dead" means at low solar flux.'
      : sig(f) + ' MHz is above foF2, so only rays leaving below <b>' + thetaMax.toFixed(1) +
        '&deg;</b> bend back. The shortest hop lands about <b>' + Math.round(skipKm) +
        ' km</b> out; closer than that you are in the skip zone, reachable only by ground wave. ' +
        'Raise foF2 (more solar flux) or drop frequency and the skip zone shrinks.') +
    '</p>');
}
['s-f', 's-fof2', 's-h'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', drawSkip);
});

/* --------------------------------------------------------- ohm and power */
function solveOhm() {
  const v = num('o-v'), i = num('o-i'), r = num('o-r'), p = num('o-p');
  const have = [['V', v], ['I', i], ['R', r], ['P', p]].filter(x => !isNaN(x[1]));
  if (have.length < 2) { out('o-out', 'Enter any two values.'); return; }
  let V = v, I = i, R = r, P = p;
  for (let pass = 0; pass < 3; pass++) {
    if (isNaN(V)) V = !isNaN(I) && !isNaN(R) ? I * R : !isNaN(P) && !isNaN(I) ? P / I
                    : !isNaN(P) && !isNaN(R) ? Math.sqrt(P * R) : NaN;
    if (isNaN(I)) I = !isNaN(V) && !isNaN(R) ? V / R : !isNaN(P) && !isNaN(V) ? P / V
                    : !isNaN(P) && !isNaN(R) ? Math.sqrt(P / R) : NaN;
    if (isNaN(R)) R = !isNaN(V) && !isNaN(I) ? V / I : !isNaN(V) && !isNaN(P) ? V * V / P
                    : !isNaN(P) && !isNaN(I) ? P / (I * I) : NaN;
    if (isNaN(P)) P = !isNaN(V) && !isNaN(I) ? V * I : !isNaN(V) && !isNaN(R) ? V * V / R
                    : !isNaN(I) && !isNaN(R) ? I * I * R : NaN;
  }
  out('o-out', '<b>E</b> = ' + sig(V) + ' V &nbsp; <b>I</b> = ' + sig(I) +
    ' A &nbsp; <b>R</b> = ' + sig(R) + ' &Omega; &nbsp; <b>P</b> = ' + sig(P) + ' W' +
    '<div class="small muted" style="margin-top:.4rem">E = I&times;R &middot; P = E&times;I &middot; P = I&sup2;R &middot; P = E&sup2;/R</div>');
}
const ohmGo = document.getElementById('o-go');
if (ohmGo) {
  ohmGo.addEventListener('click', solveOhm);
  document.getElementById('o-clear').addEventListener('click', () => {
    ['o-v', 'o-i', 'o-r', 'o-p'].forEach(id => document.getElementById(id).value = '');
    out('o-out', '');
  });
  ['o-v', 'o-i', 'o-r', 'o-p'].forEach(id =>
    document.getElementById(id).addEventListener('keydown', e => { if (e.key === 'Enter') solveOhm(); }));
}

/* ------------------------------------------------ reactance and resonance */
function drawReact() {
  const f = num('r-f') * 1e3, L = num('r-l') * 1e-6, C = num('r-c') * 1e-12;
  if (!(f > 0) || !(L > 0) || !(C > 0)) { out('r-out', 'Enter positive values.'); return; }
  const XL = 2 * Math.PI * f * L, XC = 1 / (2 * Math.PI * f * C);
  const fRes = 1 / (2 * Math.PI * Math.sqrt(L * C));
  const Q = XL / 5;    /* illustrative: assumes 5 ohm series loss */
  out('r-out',
    '<b>X<sub>L</sub></b> = ' + sig(XL) + ' &Omega; &nbsp; <b>X<sub>C</sub></b> = ' + sig(XC) +
    ' &Omega; &nbsp; <b>net</b> = ' + sig(XL - XC) + ' &Omega; ' +
    (XL > XC ? '(inductive)' : XL < XC ? '(capacitive)' : '(resonant)') +
    '<div class="small muted" style="margin-top:.4rem">Resonance at <b>' +
    (fRes / 1e3).toFixed(1) + ' kHz</b> — where X<sub>L</sub> and X<sub>C</sub> cancel and the ' +
    'circuit looks purely resistive.</div>');

  const svg = document.getElementById('r-svg');
  const W = 640, H = 220, base = 190;
  const fLo = fRes * 0.25, fHi = fRes * 2.5;
  const xOf = fr => 40 + ((fr - fLo) / (fHi - fLo)) * (W - 60);
  const clamp = y => Math.max(10, Math.min(base, y));
  const scale = 1 / (2 * Math.PI * fRes * C) * 2.2;
  let lp = '', cp = '';
  for (let n = 0; n <= 120; n++) {
    const fr = fLo + (fHi - fLo) * n / 120;
    const xl = 2 * Math.PI * fr * L, xc = 1 / (2 * Math.PI * fr * C);
    lp += (n ? 'L' : 'M') + xOf(fr) + ',' + clamp(base - (xl / scale) * base);
    cp += (n ? 'L' : 'M') + xOf(fr) + ',' + clamp(base - (xc / scale) * base);
  }
  svg.innerHTML =
    '<line x1="40" y1="' + base + '" x2="' + (W - 15) + '" y2="' + base + '" stroke="#8b98a5"/>' +
    '<path d="' + lp + '" stroke="#58a6ff" fill="none" stroke-width="1.8"/>' +
    '<path d="' + cp + '" stroke="#bc8cff" fill="none" stroke-width="1.8"/>' +
    '<line x1="' + xOf(fRes) + '" y1="10" x2="' + xOf(fRes) + '" y2="' + base +
      '" stroke="#ffb454" stroke-dasharray="4 3"/>' +
    '<text x="' + (xOf(fRes) + 6) + '" y="24" fill="#ffb454" font-size="11" font-family="monospace">resonance ' +
      (fRes / 1e3).toFixed(0) + ' kHz</text>' +
    '<text x="46" y="24" fill="#58a6ff" font-size="11" font-family="monospace">X_L rises with frequency</text>' +
    '<text x="46" y="40" fill="#bc8cff" font-size="11" font-family="monospace">X_C falls with frequency</text>' +
    '<circle cx="' + xOf(f) + '" cy="' + clamp(base - (XL / scale) * base) + '" r="4" fill="#58a6ff"/>' +
    '<circle cx="' + xOf(f) + '" cy="' + clamp(base - (XC / scale) * base) + '" r="4" fill="#bc8cff"/>' +
    '<text x="' + (W - 15) + '" y="' + (base + 16) + '" fill="#626e7b" font-size="10" ' +
      'text-anchor="end" font-family="monospace">frequency →</text>';
}
['r-f', 'r-l', 'r-c'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', drawReact);
});

/* ------------------------------------------------------------------- SWR */
function calcSWR() {
  const z0 = num('w-z0'), zl = num('w-zl'), pw = num('w-p');
  if (!(z0 > 0) || !(zl >= 0)) { out('w-out', 'Enter positive impedances.'); return; }
  const gamma = Math.abs((zl - z0) / (zl + z0));
  const swr = gamma >= 1 ? Infinity : (1 + gamma) / (1 - gamma);
  const returnLoss = gamma > 0 ? -20 * Math.log10(gamma) : Infinity;
  const reflectedPct = gamma * gamma * 100;
  const mismatchLoss = -10 * Math.log10(1 - gamma * gamma);
  const fwd = isNaN(pw) ? null : pw;
  out('w-out',
    '<b>SWR</b> = ' + (isFinite(swr) ? swr.toFixed(2) + ':1' : '∞ (total reflection)') +
    ' &nbsp; <b>|&Gamma;|</b> = ' + gamma.toFixed(3) +
    ' &nbsp; <b>return loss</b> = ' + (isFinite(returnLoss) ? returnLoss.toFixed(1) + ' dB' : '∞') +
    '<div class="small muted" style="margin-top:.4rem">' +
      reflectedPct.toFixed(1) + '% of the forward power is reflected back to the transmitter' +
      (fwd ? ' — ' + (fwd * gamma * gamma).toFixed(1) + ' W of ' + fwd + ' W' : '') +
      '. Mismatch loss ' + mismatchLoss.toFixed(2) + ' dB' +
      (swr < 1.5 ? '. That is a good match; the loss is negligible.'
        : swr < 3 ? '. Most solid-state finals still run happily here.'
        : '. Expect the transmitter to fold back power to protect itself.') +
    '</div>');
}
['w-z0', 'w-zl', 'w-p'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', calcSWR);
});

/* -------------------------------------------------------------- antennas */
function calcAnt() {
  const f = num('a-f'), vf = num('a-vf'), frac = num('a-frac');
  if (!(f > 0)) { out('a-out', 'Enter a frequency.'); return; }
  const lambdaM = 299.792458 / f;
  const halfFt = 468 / f, quarterFt = 234 / f;
  const wantFt = frac === 0.5 ? halfFt : frac === 0.25 ? quarterFt : 936 / f;
  const coaxM = lambdaM * frac * vf;
  out('a-out',
    '<b>Free-space wavelength</b> = ' + lambdaM.toFixed(2) + ' m (' + (lambdaM * 3.2808).toFixed(1) + ' ft)' +
    '<div class="small muted" style="margin-top:.4rem">' +
      'Half-wave dipole ≈ <b>' + halfFt.toFixed(2) + ' ft</b> (' + (halfFt * 0.3048).toFixed(2) + ' m), ' +
      'each leg ' + (halfFt / 2).toFixed(2) + ' ft. Quarter-wave vertical ≈ <b>' +
      quarterFt.toFixed(2) + ' ft</b> (' + (quarterFt * 0.3048).toFixed(2) + ' m). ' +
      'The 468/f and 234/f figures already allow for end effect on real wire.' +
    '</div>' +
    '<div class="small muted" style="margin-top:.4rem">' +
      'A <b>' + (frac === 0.25 ? 'quarter' : frac === 0.5 ? 'half' : 'full') + '-wave</b> line at VF ' +
      vf + ' is <b>' + coaxM.toFixed(2) + ' m</b> (' + (coaxM * 3.2808).toFixed(2) + ' ft) of physical cable — ' +
      'velocity factor shortens the electrical length, which is why stubs are cut by VF, not by free space.' +
    '</div>');
}
['a-f', 'a-vf', 'a-frac'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', calcAnt);
});

/* -------------------------------------------------------------- decibels */
function calcDb() {
  const p1 = num('d-p1'), p2 = num('d-p2'), dbIn = num('d-db');
  if (!isNaN(dbIn) && !isNaN(p1)) {
    const result = p1 * Math.pow(10, dbIn / 10);
    out('d-out', '<b>' + sig(p1) + ' W</b> changed by <b>' + dbIn + ' dB</b> = <b>' + sig(result) + ' W</b>' +
      '<div class="small muted" style="margin-top:.4rem">Power ratio ' + sig(Math.pow(10, dbIn / 10)) +
      '× — every 3 dB doubles power, every 10 dB is ten times.</div>');
    return;
  }
  if (!(p1 > 0) || !(p2 > 0)) { out('d-out', 'Enter two positive powers, or a power and a dB figure.'); return; }
  const db = 10 * Math.log10(p2 / p1);
  out('d-out', '<b>' + sig(p1) + ' W → ' + sig(p2) + ' W</b> is <b>' + db.toFixed(2) + ' dB</b>' +
    '<div class="small muted" style="margin-top:.4rem">Ratio ' + sig(p2 / p1) + '×. ' +
    'In dBm: ' + (10 * Math.log10(p1 * 1000)).toFixed(1) + ' dBm → ' +
    (10 * Math.log10(p2 * 1000)).toFixed(1) + ' dBm. ' +
    'Voltage into the same impedance would be 20&middot;log&#8321;&#8320; instead of 10&middot;log&#8321;&#8320;.</div>');
}
['d-p1', 'd-p2', 'd-db'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', calcDb);
});

/* ------------------------------------------------------------ great circle */
function calcPath() {
  const a = gridToLatLon(document.getElementById('g-a').value);
  const b = gridToLatLon(document.getElementById('g-b').value);
  if (!a || !b) { out('g-out', 'Both fields need a Maidenhead locator, e.g. EM79 or IO91wm.'); return; }
  const toRad = d => d * Math.PI / 180;
  const dLat = toRad(b.lat - a.lat), dLon = toRad(b.lon - a.lon);
  const la1 = toRad(a.lat), la2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLon / 2) ** 2;
  const km = 2 * EARTH_R * Math.asin(Math.sqrt(h));
  const y = Math.sin(dLon) * Math.cos(la2);
  const x = Math.cos(la1) * Math.sin(la2) - Math.sin(la1) * Math.cos(la2) * Math.cos(dLon);
  const bearing = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  const long = 40075 - km;
  const hops = Math.max(1, Math.ceil(km / 3000));
  out('g-out',
    '<b>' + Math.round(km) + ' km</b> (' + Math.round(km * 0.6214) + ' miles) at <b>' +
    bearing.toFixed(0) + '&deg;</b> short path' +
    '<div class="small muted" style="margin-top:.4rem">Long path is ' + Math.round(long) +
    ' km on a bearing of ' + ((bearing + 180) % 360).toFixed(0) + '&deg;. ' +
    'At a typical 3000 km per F-layer hop that is about <b>' + hops + ' hop' + (hops > 1 ? 's' : '') +
    '</b>, so the path needs the MUF to hold up at every reflection point.</div>');
}
const pathGo = document.getElementById('g-go');
if (pathGo) {
  pathGo.addEventListener('click', calcPath);
  ['g-a', 'g-b'].forEach(id =>
    document.getElementById(id).addEventListener('keydown', e => { if (e.key === 'Enter') calcPath(); }));
}

/* first paint */
openFromHash();
if (document.getElementById('s-svg')) drawSkip();
if (document.getElementById('r-svg')) drawReact();
calcSWR(); calcAnt(); calcDb(); calcPath();
