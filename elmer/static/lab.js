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
  document.getElementById('s-h-v').textContent = h + ' km'
    + (h < 250 ? ' — low, typical of a daytime layer'
       : h > 380 ? ' — high, typical of a night layer'
       : '');

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
/* The height and critical frequency are measurements, not preferences: an
   ionosonde reports both. Offering the real numbers is more use than a slider
   the operator has no way to set honestly. */
const sondeBtn = document.getElementById('s-measure');
if (sondeBtn) sondeBtn.addEventListener('click', async () => {
  const note = document.getElementById('s-sonde');
  sondeBtn.disabled = true;
  note.textContent = 'asking the ionosonde network…';
  let data;
  try {
    data = await api('/api/ionosonde');
  } catch (e) {
    note.innerHTML = '<span style="color:var(--amber)">No ionosonde data reachable. ' +
      'The slider still works — 300 km by day, 350 at night are fair guesses.</span>';
    sondeBtn.disabled = false;
    return;
  }
  const near = data.nearest, sp = data.spread;
  if (!near) {
    note.innerHTML = 'Set a QTH on the propagation page and ELMER can pick the ' +
      'nearest station. Right now the network reports hmF2 between <b>' +
      sp.hmf2.low + '</b> and <b>' + sp.hmf2.high + ' km</b> (median ' +
      sp.hmf2.median + ').';
    sondeBtn.disabled = false;
    return;
  }
  document.getElementById('s-h').value = Math.round(
    Math.max(150, Math.min(450, near.hmf2)));
  document.getElementById('s-fof2').value = Math.max(2, Math.min(16, near.fof2));
  drawSkip();
  note.innerHTML =
    '<b>' + escapeHTML(near.name) + '</b>, ' + near.distance_km + ' km away, ' +
    near.age_minutes + ' min old — hmF2 <b>' + near.hmf2 + ' km</b>, foF2 <b>' +
    near.fof2 + ' MHz</b>' + (near.mufd ? ', its own MUF(3000) ' + near.mufd.toFixed(1) + ' MHz' : '') +
    '.<br>Across the ' + sp.count + ' stations reporting now the peak sits between ' +
    sp.hmf2.low + ' and ' + sp.hmf2.high + ' km — that spread is mostly day against night.';
  sondeBtn.disabled = false;
});

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
/* Lengths use the practical constants the pools teach (468/f and friends),
   which already allow for end effect on real wire. Gain figures are honest
   estimates for a competent build, not manufacturer claims. */

const LAMBDA_FT = f => 983.571 / f;          // free space wavelength, feet
const FT_M = 0.3048;

/* ---------------------------------------------------------------- Yagi gain

   What a Yagi does is set by how long the boom is, not by how many elements
   are bolted to it: elements are how the aperture gets filled, and past a
   point another one on the same boom buys almost nothing. So gain is taken
   from the boom length, and then charged for spacing that no good design
   would use.

   The anchors are free-space gains of optimised monoband designs against
   boom length in wavelengths. They are deliberately at the conservative end
   of what is published - a real antenna's figure depends on its own design,
   and every one of these is worth about +/-1 dB. Nothing here is measured;
   it is an estimate, and the panel says so.

   Beyond the last anchor the curve continues at about 2.2 dB per doubling of
   boom, which is what the anchors themselves work out at. It is emphatically
   not the 6 dB per doubling that gets repeated on the bands - ground
   reflection is capped at 6 dB in total, so it cannot be paid out again at
   every doubling. */
const BOOM_GAIN = [          // [boom length in wavelengths, free-space dBi]
  [0.00,  5.2], [0.15,  6.0], [0.35,  7.8], [0.60,  8.8], [0.90,  9.8],
  [1.30, 10.6], [2.00, 11.8], [3.00, 13.0], [4.50, 14.2], [6.00, 15.0],
  [8.00, 15.9],
];
const BOOM_PER_DOUBLING = 2.2;      // dB, past the last anchor

/* Directors in a good design sit between about 0.15 and 0.30 wavelengths
   apart. Crammed closer, the elements shadow each other and the gain is not
   there however many are added; stretched further, the aperture is left with
   holes in it and the sidelobes grow. Either way it costs, and the cost is
   capped because a badly spaced Yagi is still a Yagi. */
const SPACING_GOOD = [0.15, 0.30];

function boomGain(boomLam) {
  const last = BOOM_GAIN[BOOM_GAIN.length - 1];
  if (boomLam >= last[0]) {
    return last[1] + BOOM_PER_DOUBLING * Math.log2(boomLam / last[0]);
  }
  for (let i = 0; i < BOOM_GAIN.length - 1; i++) {
    const [l0, g0] = BOOM_GAIN[i], [l1, g1] = BOOM_GAIN[i + 1];
    if (boomLam <= l1) {
      return g0 + (g1 - g0) * ((boomLam - l0) / (l1 - l0));
    }
  }
  return last[1];
}

function spacingPenalty(spacing) {
  if (spacing >= SPACING_GOOD[0] && spacing <= SPACING_GOOD[1]) return 0;
  const edge = spacing < SPACING_GOOD[0] ? SPACING_GOOD[0] : SPACING_GOOD[1];
  const off = Math.abs(Math.log10(spacing / edge));
  return Math.min(3.0, 26 * off * off);
}

/* Free-space gain in dBd for `n` elements at `spacing` wavelengths apart. */
function yagiGain(n, spacing) {
  if (!(n >= 2)) return 0;                  // a driven element on its own
  const boom = (n - 1) * spacing;
  const dbi = Math.max(5.2, boomGain(boom) - spacingPenalty(spacing));
  return dbi - 2.15;
}

/* Every gain here is against a half-wave dipole, and every one needs to say
   what it was measured against and where - a gain figure without those is
   the thing antenna advertising is made of.

   `ref` is that condition. Horizontal wires are quoted in free space, which
   is the honest reference but is not where anybody's antenna is: over real
   ground a horizontal antenna picks up as much as 6 dB more at the peak of
   its lobe, most of it once it is about half a wavelength up. Verticals are
   quoted over an average ground plane instead, because a vertical without
   ground is not an antenna at all, and theirs is the number that a real
   installation most easily fails to reach. */
const FREE_SPACE = 'free space';
const OVER_GROUND = 'over an average ground plane';

const ANTENNAS = {
  dipole: {shape: 'wire', label: 'Half-wave dipole', gain: 0, z: 73, ref: FREE_SPACE,
    build: f => ({'Overall length': 468 / f, 'Each leg': 234 / f})},
  // Its legs hang below the apex, so its average height is lower than a flat
  // dipole strung at the same point, and the pattern is rounder. Modelled at
  // the same average height it gives up about a dB; the much larger figures
  // quoted for this comparison are usually against a *rotatable* dipole,
  // which is a comparison of pointability rather than of gain.
  invertedv: {shape: 'wire', label: 'Inverted-V dipole', gain: -1.0, z: 50,
    ref: FREE_SPACE,
    build: f => ({'Overall length': 445 / f, 'Each leg': 222.5 / f})},
  efhw: {shape: 'wire', label: 'End-fed half wave', gain: 0, z: 2400,
    ref: FREE_SPACE,
    build: f => ({'Wire length': 468 / f})},
  loop: {shape: 'wire', label: 'Full-wave loop', gain: 1.2, z: 115, ref: FREE_SPACE,
    build: f => ({'Total perimeter': 1005 / f, 'Each side (square)': 251.25 / f})},
  quarter: {shape: 'vert', label: 'Quarter-wave vertical', gain: 0, z: 36,
    ref: OVER_GROUND,
    build: f => ({'Radiator': 234 / f, 'Each radial (16+)': 234 / f})},
  fiveeighth: {shape: 'vert', label: '5/8-wave vertical', gain: 2.0, z: null,
    ref: OVER_GROUND,
    build: f => ({'Radiator': 585 / f, 'Each radial': 234 / f})},
  // A J-pole is an end-fed half wave with a matching stub, and radiates like
  // one. The 3 dBd on the box is where the stub's own radiation went in the
  // advertising rather than in the pattern.
  jpole: {shape: 'vert', label: 'J-pole', gain: 0, z: 50, ref: OVER_GROUND,
    build: f => ({'Long element': 702 / f, 'Matching stub': 234 / f,
                  'Feed tap above base': 234 / f * 0.12})},
  groundplane: {shape: 'vert', label: 'Ground plane, drooping radials', gain: 0, z: 50,
    ref: OVER_GROUND,
    build: f => ({'Radiator': 234 / f, 'Each of 4 radials': 246 / f})},
};

const NVIS_TYPES = ['dipole', 'invertedv', 'loop', 'efhw'];

function antennaFields(type) {
  const show = (cls, on) => document.querySelectorAll(cls)
    .forEach(el => { el.style.display = on ? '' : 'none'; });
  show('.an-when-yagi', type === 'yagi');
  show('.an-when-whip', type === 'whip');
  show('.an-when-height', type !== 'whip');
  show('.an-when-v', type === 'invertedv');
  show('.an-when-nvis', NVIS_TYPES.indexOf(type) >= 0);
}

/* NVIS wants the first lobe pushed straight up, which happens when a
   horizontal wire sits low over ground. Below about 0.15 lambda ground loss
   starts eating the gain; above 0.25 lambda the lobe splits and comes down.
   For an inverted-V the pattern follows the current-weighted mean height, not
   the apex: current is greatest at the centre, and the weighted mean sits
   (pi-2)/pi = 0.3634 of the way out along each leg. */
const NVIS_LOW = 0.15, NVIS_HIGH = 0.25, V_CENTROID = (Math.PI - 2) / Math.PI;

function nvisBlock(type, f, lamFt, heightFt, legFt) {
  const droop = type === 'invertedv' ? num('an-droop') : 0;
  const sinD = Math.sin(droop * Math.PI / 180);
  const effective = type === 'invertedv'
    ? heightFt - V_CENTROID * legFt * sinD
    : heightFt;
  const endFt = heightFt - legFt * sinD;
  const spanFt = 2 * legFt * Math.cos(droop * Math.PI / 180);
  const lam = effective / lamFt;
  const takeoff = Math.min(90, Math.asin(Math.min(1, 1 / (4 * lam))) * 180 / Math.PI);

  const lo = NVIS_LOW * lamFt, mid = 0.20 * lamFt, hi = NVIS_HIGH * lamFt;
  const inBand = lam >= NVIS_LOW && lam <= NVIS_HIGH;
  const verdict = inBand
    ? '<span class="pill good">in the NVIS window</span>'
    : lam < NVIS_LOW
      ? '<span class="pill warn">lower than ideal &mdash; ground loss</span>'
      : '<span class="pill warn">too high &mdash; the lobe is coming down</span>';

  /* NVIS only works below the critical frequency; above roughly 10 MHz the
     ionosphere usually will not return a vertical signal. */
  const freqNote = f > 10.5
    ? '<p class="watchout">At ' + f.toFixed(3) + ' MHz NVIS will usually fail: a ' +
      'near-vertical signal only comes back below foF2, which is rarely above ' +
      '8&nbsp;MHz. NVIS is an 80, 60 and 40 metre technique. ' +
      '<a href="/lab#skip">Check it against foF2 in the hop simulator &rarr;</a></p>'
    : '';

  const apexRow = type === 'invertedv'
    ? '<tr><td>Apex height</td><td class="mono">' + heightFt.toFixed(1) + ' ft</td>' +
      '<td class="mono">' + (heightFt * FT_M).toFixed(2) + ' m</td></tr>' +
      '<tr><td>End height, each leg</td><td class="mono">' +
        (endFt > 0 ? endFt.toFixed(1) + ' ft' : 'on the ground') + '</td>' +
      '<td class="mono">' + (endFt > 0 ? (endFt * FT_M).toFixed(2) + ' m' : '—') + '</td></tr>' +
      '<tr><td>Span between ends</td><td class="mono">' + spanFt.toFixed(1) + ' ft</td>' +
      '<td class="mono">' + (spanFt * FT_M).toFixed(2) + ' m</td></tr>' +
      '<tr><td>Effective height (current-weighted)</td><td class="mono">' +
        effective.toFixed(1) + ' ft</td><td class="mono">' +
        (effective * FT_M).toFixed(2) + ' m</td></tr>'
    : '<tr><td>Height above ground</td><td class="mono">' + heightFt.toFixed(1) +
      ' ft</td><td class="mono">' + (heightFt * FT_M).toFixed(2) + ' m</td></tr>';

  return '<div class="nvis">' +
    '<div class="spread"><div class="explain-head" style="margin:0">NVIS setup</div>' +
      verdict + '</div>' +
    '<table class="data" style="max-width:520px"><tbody>' + apexRow +
      '<tr><td>Effective height in wavelengths</td><td class="mono" colspan="2">' +
        lam.toFixed(3) + ' &lambda;</td></tr>' +
      '<tr><td>Main lobe elevation</td><td class="mono" colspan="2">' +
        (takeoff >= 89.5 ? 'straight up' : takeoff.toFixed(0) + '&deg;') + '</td></tr>' +
    '</tbody></table>' +
    '<p class="small muted" style="margin-top:.5rem">Aim for <b>' + lo.toFixed(1) +
      '&ndash;' + hi.toFixed(1) + ' ft</b> of effective height at ' + f.toFixed(3) +
      '&nbsp;MHz (' + NVIS_LOW + '&ndash;' + NVIS_HIGH + '&nbsp;&lambda;), with <b>' +
      mid.toFixed(1) + ' ft</b> a good middle. ' +
      (type === 'invertedv'
        ? 'The droop matters: the pattern follows the current-weighted mean height, ' +
          'which sits about a third of the way out along each leg, so an inverted-V ' +
          'behaves lower than its apex suggests.'
        : 'A flat dipole radiates from its whole length at the same height, so the ' +
          'number above is the one that counts.') +
    '</p>' +
    '<p class="small muted">A reflector wire on the ground beneath the antenna, about ' +
      '5% longer than the radiator, is worth a couple of dB and steadies the pattern ' +
      'over poor soil &mdash; the cheapest improvement an NVIS wire can have.</p>' +
    freqNote + '</div>';
}

function calcAnt() {
  const type = document.getElementById('an-type').value;
  const f = num('an-f');
  const k = num('an-k');
  if (!(f > 0)) { out('an-out', 'Enter a frequency.'); return; }
  const lamFt = LAMBDA_FT(f);
  let rows = {}, gain = 0, z = null, notes = [], shape = 'wire';
  let gainRef = FREE_SPACE;

  if (type === 'yagi') {
    shape = 'yagi';
    const n = Math.round(num('an-el')), sp = num('an-sp');
    document.getElementById('an-el-v').textContent = n + ' elements';
    document.getElementById('an-sp-v').textContent = sp.toFixed(2) + ' wavelengths';
    rows['Reflector'] = 0.495 * lamFt * k / 0.95;
    rows['Driven element'] = 0.473 * lamFt * k / 0.95;
    for (let d = 1; d <= n - 2; d++) {
      rows['Director ' + d] = (0.44 - 0.008 * (d - 1)) * lamFt * k / 0.95;
    }
    rows['Element spacing'] = sp * lamFt;
    rows['Boom length'] = (n - 1) * sp * lamFt;
    gain = yagiGain(n, sp);
    z = 22;
    const boomLam = (n - 1) * sp;
    const gLin = Math.pow(10, (gain + 2.15) / 10);
    notes.push('Estimated gain <b>' + gain.toFixed(1) + ' dBd</b> (' +
      (gain + 2.15).toFixed(1) + ' dBi) in <b>free space</b>, beamwidth roughly <b>' +
      Math.round(Math.sqrt(41253 / (1.1 * gLin))) + '&deg;</b>. ' +
      'Worth about &plusmn;1&nbsp;dB: a real antenna depends on its own design.');
    notes.push('That comes from the <b>' + boomLam.toFixed(2) +
      '&nbsp;wavelength boom</b>, not the element count. Boom length is what ' +
      'sets a Yagi\'s gain &mdash; doubling it is worth roughly 2.2&nbsp;dB, ' +
      'while another element on the same boom is worth very little.');
    const penalty = spacingPenalty(sp);
    if (penalty > 0.15) {
      notes.push('At ' + sp.toFixed(2) + '&nbsp;wavelength spacing this design is ' +
        'charged <b>' + penalty.toFixed(1) + '&nbsp;dB</b> against an optimised one. ' +
        (sp < SPACING_GOOD[0]
          ? 'Elements this close shadow each other, and adding more does not help.'
          : 'Spread this far the aperture has holes in it and the sidelobes grow.') +
        ' Good designs sit between ' + SPACING_GOOD[0] + ' and ' + SPACING_GOOD[1] +
        '&nbsp;wavelengths.');
    }
    notes.push('A Yagi pulls the driven element impedance down to around ' + z +
      '&nbsp;&Omega;, so it needs a gamma, hairpin or beta match to reach 50&nbsp;&Omega;.');
  } else if (type === 'whip') {
    shape = 'vert';
    gainRef = 'over the vehicle body';
    const hFt = num('an-wh'), loss = num('an-loss'), hat = num('an-hat');
    if (!(hFt > 0)) { out('an-out', 'Enter a whip height.'); return; }
    const ratio = (hFt * hat) / lamFt;                 // effective electrical height
    const Rr = 395 * ratio * ratio;                    // short monopole
    const eff = Rr / (Rr + loss);
    const lossDb = 10 * Math.log10(eff);
    const Za = 300;                                    // typical thin whip
    const theta = 2 * Math.PI * (hFt / lamFt);
    const Xc = Za / Math.tan(Math.min(theta, Math.PI / 2 - 1e-3));
    const L = Xc / (2 * Math.PI * f * 1e6) * 1e6;      // microhenries
    rows['Physical height'] = hFt;
    rows['Height in wavelengths'] = null;
    gain = lossDb;
    notes.push('Radiation resistance <b>' + Rr.toFixed(1) + '&nbsp;&Omega;</b> against ' +
      loss + '&nbsp;&Omega; of ground and coil loss, so efficiency is <b>' +
      (eff * 100).toFixed(1) + '%</b> &mdash; a loss of <b>' + Math.abs(lossDb).toFixed(1) +
      '&nbsp;dB</b> before the signal ever leaves.');
    notes.push('Resonating it needs roughly <b>' + L.toFixed(1) + '&nbsp;&micro;H</b> of ' +
      'loading. A coil at the centre or top of the whip works better than one at the ' +
      'base, because it sits where the current still is.');
    if (hat > 1) notes.push('The capacity hat raises the effective height, which is why ' +
      'it buys efficiency for no extra length &mdash; it is the cheapest improvement here.');
    notes.push('This is why mobile HF is hard: at ' + f.toFixed(3) + '&nbsp;MHz the whip is only ' +
      (ratio * 100).toFixed(1) + '% of a wavelength tall.');
  } else {
    const spec = ANTENNAS[type];
    shape = spec.shape;
    rows = spec.build(f);
    gain = spec.gain;
    z = spec.z;
    gainRef = spec.ref || FREE_SPACE;
    if (type === 'efhw') notes.push('The end of a half wave is a high-voltage, ' +
      'high-impedance point &mdash; around ' + z + '&nbsp;&Omega; &mdash; so it needs a 49:1 ' +
      'transformer, not a direct coax feed.');
    if (type === 'quarter' || type === 'groundplane') notes.push(
      'A quarter-wave vertical is half an antenna: the ground plane is the other half. ' +
      'Radial count matters more than radial length &mdash; 16 or more on the ground, or ' +
      'four elevated.');
    if (type === 'groundplane') notes.push('Drooping the radials about 45&deg; raises the ' +
      'feed point impedance from roughly 36&nbsp;&Omega; to near 50&nbsp;&Omega;, which is the ' +
      'whole point of the droop.');
    if (type === 'fiveeighth') notes.push('A 5/8-wave radiator is not resonant, so it needs ' +
      'a base matching coil. In exchange it pushes the lobe down and gains about ' +
      '2&nbsp;dB over a quarter wave on flat ground.');
    if (type === 'loop') notes.push('A full-wave loop runs about 1&nbsp;dB ahead of a dipole ' +
      'and is quieter on receive, because it responds to the magnetic rather than the ' +
      'electric component of local noise.');
    if (type === 'invertedv') notes.push('The sloping legs shorten it by about 5% and pull ' +
      'the feed impedance down near 50&nbsp;&Omega;, which is why an inverted-V often matches ' +
      'better than a flat dipole at the same height.');
  }

  const droopEl = document.getElementById('an-droop-v');
  if (droopEl) droopEl.textContent = num('an-droop').toFixed(0) + '\u00b0 from horizontal';

  /* Height above ground sets the takeoff angle for anything horizontal. */
  let takeoff = null;
  if (type !== 'whip') {
    const hFt = num('an-h');
    if (hFt > 0 && shape === 'wire') {
      // An inverted-V radiates from a current-weighted mean height below its
      // apex, so quoting the apex here would contradict the NVIS panel.
      const legFt = rows['Each leg'] || (rows['Overall length'] || lamFt / 2) / 2;
      const effFt = type === 'invertedv'
        ? hFt - V_CENTROID * legFt * Math.sin(num('an-droop') * Math.PI / 180)
        : hFt;
      const hLam = effFt / lamFt;
      takeoff = Math.min(90, Math.asin(Math.min(1, 1 / (4 * hLam))) * 180 / Math.PI);
      notes.push('At <b>' + hFt.toFixed(0) + '&nbsp;ft</b>' +
        (type === 'invertedv'
          ? ' at the apex &mdash; an effective <b>' + effFt.toFixed(1) + '&nbsp;ft</b> &mdash;'
          : '') +
        ' that is <b>' + hLam.toFixed(2) +
        ' wavelengths</b> up, putting the main lobe near <b>' + takeoff.toFixed(0) +
        '&deg;</b> elevation. ' + (takeoff > 45
          ? 'That is high-angle NVIS coverage — good for regional work, poor for DX.'
          : takeoff > 25 ? 'Reasonable for medium haul; get it higher for DX.'
          : 'A useful low angle for DX.'));
    }
  }

  const dims = Object.entries(rows).filter(([, v]) => v !== null).map(([label, ft]) =>
    '<tr><td>' + label + '</td><td class="mono">' + ft.toFixed(2) + ' ft</td>' +
    '<td class="mono">' + (ft * FT_M).toFixed(3) + ' m</td>' +
    '<td class="mono muted">' + (ft * 12).toFixed(1) + ' in</td></tr>').join('');

  const wantNvis = document.getElementById('an-nvis');
  const nvis = (wantNvis && wantNvis.checked && NVIS_TYPES.indexOf(type) >= 0)
    ? nvisBlock(type, f, lamFt, num('an-h'),
                (rows['Each leg'] || rows['Overall length'] / 2 ||
                 rows['Wire length'] / 2 || lamFt / 4))
    : '';

  out('an-out', nvis +
    '<table class="data" style="max-width:520px"><thead><tr><th>Dimension</th>' +
      '<th>feet</th><th>metres</th><th>inches</th></tr></thead><tbody>' + dims +
    '</tbody></table>' +
    '<div class="row mt" style="gap:1rem">' +
      '<span>Wavelength <b>' + lamFt.toFixed(2) + ' ft</b></span>' +
      (z ? '<span>Feed impedance &asymp; <b>' + z + ' &Omega;</b></span>' : '') +
      '<span>Gain <b>' + (gain >= 0 ? '+' : '') + gain.toFixed(1) + ' dBd</b> ' +
        '<span class="tiny muted">(' + (gain + 2.15).toFixed(1) + ' dBi, ' +
        escapeHTML(gainRef) + ')</span></span>' +
    '</div>' +
    '<div class="small muted" style="margin-top:.6rem">' +
      notes.map(n => '<p>' + n + '</p>').join('') +
      '<p><b>What this figure is.</b> An estimate against a half-wave dipole, ' +
      escapeHTML(gainRef) + ' &mdash; not a measurement, and worth about ' +
      '&plusmn;1&nbsp;dB. Your own installation decides the rest: over real ' +
      'ground a horizontal antenna gains as much as 6&nbsp;dB at the peak of ' +
      'its lobe, most of it once it is half a wavelength up, and height ' +
      'lowers the takeoff angle, which usually matters more for distance than ' +
      'the peak figure does. A gain number quoted without saying what it was ' +
      'measured against, and where, is worth nothing at all.</p>' +
      '</div>');

  const heightFt = type === 'whip' ? null : num('an-h');
  const legFt = rows['Each leg'] || (rows['Overall length'] || 0) / 2 ||
                rows['Radiator'] || 0;
  window.LAB_ANTENNA = {
    type: type,
    label: (ANTENNAS[type] || {}).label || (type === 'yagi' ? 'Yagi' : 'Loaded whip'),
    gain: gain, f: f, heightFt: heightFt > 0 ? heightFt : null,
    legFt: legFt, droop: type === 'invertedv' ? num('an-droop') : 0,
    whipFt: type === 'whip' ? num('an-wh') : null,
    description: ((ANTENNAS[type] || {}).label ||
                  (type === 'yagi' ? Math.round(num('an-el')) + '-element Yagi'
                                   : 'loaded mobile whip')) +
                 (type === 'whip' ? ' on a vehicle'
                  : heightFt > 0 ? ' at ' + heightFt.toFixed(0) + ' ft' : ''),
  };
  drawAntenna(shape, rows, type);
}

function drawAntenna(shape, rows, type) {
  const svg = document.getElementById('an-svg');
  if (!svg) return;
  const W = 620, H = 250, g = 210;
  const lbl = (x, y, t, anchor) => '<text x="' + x + '" y="' + y + '" fill="#8b98a5" ' +
    'font-size="11" font-family="monospace" text-anchor="' + (anchor || 'middle') + '">' + t + '</text>';
  const ground = '<line x1="0" y1="' + g + '" x2="' + W + '" y2="' + g +
    '" stroke="#8b98a5" stroke-width="1.5"/>' +
    Array.from({length: 26}, (_, i) =>
      '<line x1="' + (i * 24) + '" y1="' + g + '" x2="' + (i * 24 - 8) + '" y2="' + (g + 8) +
      '" stroke="#2a3441"/>').join('');
  let body = '';

  if (shape === 'wire') {
    const y = 90;
    if (type === 'loop') {
      body = '<rect x="215" y="45" width="190" height="120" fill="none" stroke="#ffb454" stroke-width="2.5"/>' +
        '<line x1="310" y1="165" x2="310" y2="' + g + '" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4 3"/>' +
        lbl(310, 38, 'one full wavelength of wire') + lbl(310, 200, 'feed', 'middle');
    } else if (type === 'efhw') {
      body = '<line x1="120" y1="' + y + '" x2="520" y2="' + y + '" stroke="#ffb454" stroke-width="2.5"/>' +
        '<circle cx="120" cy="' + y + '" r="5" fill="#58a6ff"/>' +
        '<line x1="120" y1="' + y + '" x2="120" y2="' + g + '" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4 3"/>' +
        lbl(320, y - 12, 'half wavelength of wire') + lbl(120, y - 16, '49:1 unun');
    } else {
      const drop = type === 'invertedv' ? 55 : 0;
      body = '<line x1="120" y1="' + (y + drop) + '" x2="320" y2="' + y + '" stroke="#ffb454" stroke-width="2.5"/>' +
        '<line x1="320" y1="' + y + '" x2="520" y2="' + (y + drop) + '" stroke="#ffb454" stroke-width="2.5"/>' +
        '<line x1="320" y1="' + y + '" x2="320" y2="' + g + '" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4 3"/>' +
        lbl(220, y + drop / 2 - 10, 'leg') + lbl(420, y + drop / 2 - 10, 'leg') +
        lbl(320, y - 12, 'feed point') + lbl(360, (y + g) / 2, 'height', 'start');
    }
  } else if (shape === 'vert') {
    const top = type === 'fiveeighth' ? 40 : 70;
    body = '<line x1="310" y1="' + top + '" x2="310" y2="' + g + '" stroke="#ffb454" stroke-width="3"/>' +
      lbl(330, (top + g) / 2, 'radiator', 'start');
    if (type === 'jpole') {
      body += '<line x1="270" y1="140" x2="270" y2="' + g + '" stroke="#ffb454" stroke-width="3"/>' +
        '<line x1="270" y1="' + g + '" x2="310" y2="' + g + '" stroke="#ffb454" stroke-width="3"/>' +
        lbl(250, 135, 'stub', 'end') + '<circle cx="270" cy="' + (g - 18) + '" r="4" fill="#58a6ff"/>' +
        lbl(240, g - 18, 'feed', 'end');
    } else if (type !== 'whip') {
      body += '<line x1="180" y1="' + (g + 4) + '" x2="440" y2="' + (g + 4) +
        '" stroke="#39d3d8" stroke-width="2"/>' + lbl(460, g + 8, 'radials', 'start');
    } else {
      body += '<rect x="296" y="130" width="28" height="26" rx="4" fill="none" stroke="#39d3d8" stroke-width="2"/>' +
        lbl(340, 146, 'loading coil', 'start');
    }
  } else {
    const n = Object.keys(rows).filter(k => /Reflector|Driven|Director/.test(k)).length;
    const boomY = 130, x0 = 90, x1 = 530;
    body = '<line x1="' + x0 + '" y1="' + boomY + '" x2="' + x1 + '" y2="' + boomY +
      '" stroke="#8b98a5" stroke-width="3"/>';
    for (let i = 0; i < n; i++) {
      const x = x0 + (x1 - x0) * (n === 1 ? 0 : i / (n - 1));
      const half = i === 0 ? 58 : (i === 1 ? 55 : 50 - i);
      const col = i === 0 ? '#f85149' : (i === 1 ? '#ffb454' : '#39d3d8');
      body += '<line x1="' + x + '" y1="' + (boomY - half) + '" x2="' + x + '" y2="' +
        (boomY + half) + '" stroke="' + col + '" stroke-width="2.5"/>';
    }
    body += lbl(x0, boomY + 78, 'reflector') + lbl(x0 + (x1 - x0) / (n - 1), boomY + 78, 'driven') +
      lbl(x1, boomY + 78, 'directors →', 'end') + lbl((x0 + x1) / 2, boomY - 78, 'boom');
    return void (svg.innerHTML = body);
  }
  svg.innerHTML = ground + body;
}

['an-type', 'an-f', 'an-h', 'an-el', 'an-sp', 'an-wh', 'an-loss', 'an-hat',
 'an-k', 'an-droop', 'an-nvis']
  .forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(el.type === 'checkbox' ? 'change' : 'input', () => {
      antennaFields(document.getElementById('an-type').value);
      calcAnt();
    });
  });

/* How close a person can actually get differs completely by antenna type, and
   it is not the antenna's height. A horizontal wire is nearest directly
   beneath it; an inverted-V is nearest at its drooping ends, which are also
   its high-voltage points; a ground-mounted vertical can be walked up to and
   touched; and a mobile whip sits a couple of feet from the people in the car.
   Guessing one number for all of them understates the case that matters. */
function exposurePrefill(a) {
  const horizontalWire = ['dipole', 'loop', 'efhw'];
  const vertical = ['quarter', 'fiveeighth', 'jpole', 'groundplane'];

  if (a.type === 'whip') {
    return {controlled: 3, uncontrolled: 6,
            why: 'a vehicle whip sits within a few feet of the people in the car, ' +
                 'so the distances start at 3 ft for occupants and 6 ft for someone ' +
                 'outside it — measure yours',
            warn: 'A mobile whip is the case where exposure limits most often bite: ' +
                  'high power, a short antenna and people very close to it.'};
  }
  if (a.type === 'invertedv') {
    const ends = Math.max(0, (a.heightFt || 0) -
                          a.legFt * Math.sin((a.droop || 0) * Math.PI / 180));
    const d = Math.max(2, Math.round(ends));
    return {controlled: d, uncontrolled: d,
            why: 'the drooping ends are the closest point, at ' + ends.toFixed(1) +
                 ' ft, not the ' + (a.heightFt || 0).toFixed(0) + ' ft apex',
            warn: 'The ends of a dipole are its high-voltage points. Keep them out ' +
                  'of reach: an RF burn there does not need the field to exceed any limit.'};
  }
  if (vertical.indexOf(a.type) >= 0) {
    const base = a.heightFt || 0;
    const d = base > 8 ? Math.round(base) : 6;
    return {controlled: d, uncontrolled: d,
            why: base > 8
              ? 'elevated at ' + base.toFixed(0) + ' ft, so directly beneath is the closest point'
              : 'a ground-mounted vertical can be walked up to, so this starts at 6 ft — ' +
                'set the real distance to a path, fence or seating area',
            warn: base > 8 ? null
              : 'The base of a ground-mounted vertical is a high-current point at ' +
                'touchable height. A fence around it is the usual answer.'};
  }
  if (horizontalWire.indexOf(a.type) >= 0 || a.type === 'yagi') {
    const d = Math.max(2, Math.round(a.heightFt || 0));
    const endNote = a.type === 'efhw'
      ? ' The far end of an end-fed half wave is a very high-voltage point — keep it high and out of reach.'
      : '';
    return {controlled: d, uncontrolled: d,
            why: 'directly beneath is the closest anyone on the ground can get',
            warn: endNote || null};
  }
  return {controlled: null, uncontrolled: null,
          why: 'set the distances to where people actually are', warn: null};
}

const toRf = document.getElementById('an-torf');
if (toRf) toRf.addEventListener('click', () => {
  const a = window.LAB_ANTENNA;
  if (!a) return;
  const near = exposurePrefill(a);
  const row = rfDefaultRow();
  row.frequency_mhz = a.f;
  /* Rounded up, not to nearest. Gain is the largest single lever on an
     exposure result, and the estimate carries about a dB either way - so the
     half dB goes to the side that puts the person further from the antenna,
     never the side that brings them closer. */
  row.gain_dbd = Math.ceil(a.gain * 2) / 2;
  row.antenna = a.description;
  row.gain_source = 'modelled';        // computed here, not typed by hand
  if (near.controlled) row.distance_controlled_ft = near.controlled;
  if (near.uncontrolled) row.distance_uncontrolled_ft = near.uncontrolled;
  /* Replace an untouched default row rather than stacking one on it. */
  const blank = rfDefaultRow();
  if (rfRows.length === 1 &&
      JSON.stringify(rfRows[0]) === JSON.stringify(blank)) rfRows = [];
  rfRows.push(row);
  renderRfRows();
  selectTab('rf');
  history.replaceState(null, '', '#rf');
  rfEvaluate();
  toast('Sent to RF exposure',
        a.description + ' at ' + a.f + ' MHz — ' + near.why + '.');
  if (near.warn) setTimeout(() => toast('Worth knowing', near.warn, 9000), 600);
});

const toPath = document.getElementById('an-topath');
if (toPath) toPath.addEventListener('click', () => {
  const a = window.LAB_ANTENNA;
  if (!a) return;
  document.getElementById('p-ag').value = a.gain.toFixed(1);
  document.getElementById('p-f').value = a.f;
  selectTab('path');
  history.replaceState(null, '', '#path');
  toast('Carried over', a.label + ' at ' + a.gain.toFixed(1) + ' dBd on ' + a.f + ' MHz');
  calcPath();
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

/* --------------------------------------------------- path and line of sight */
/* Radio horizon uses the 4/3 earth radius, which is what makes it reach about
   15% further than the visual horizon. Terrain, when reachable, is checked
   against 60% of the first Fresnel zone - the usual working rule for a link
   that behaves like free space. */

const M_FT = 3.280839895;

/* Both ends accept a grid, coordinates or a place name; the shared picker in
   elmer.js does the resolving, so the path tool only ever sees coordinates. */
let placeA = null, placeB = null;

function initPathPlaces() {
  placeA = initPlace('p-a', {onPick: () => { if (window.PATH_READY) calcPath(); }});
  placeB = initPlace('p-b', {onPick: () => { if (window.PATH_READY) calcPath(); }});
  if (!placeA) return;

  /* Default your end to the saved QTH, so the tool opens where you are. */
  const qth = window.QTH || {};
  if (qth.lat !== undefined && qth.lon !== undefined) {
    placeA.set({name: qth.name || qth.grid, short: qth.short || qth.grid || 'my QTH',
                kind: qth.kind || 'grid', lat: qth.lat, lon: qth.lon,
                grid: qth.grid || latLonToGrid(qth.lat, qth.lon)}, true);
  }

  const useBtn = document.getElementById('p-use-qth');
  if (useBtn) useBtn.addEventListener('click', () => {
    const q = window.QTH || {};
    if (q.lat === undefined) { toast('No QTH saved', 'Type where you are, then "save as my QTH"'); return; }
    document.getElementById('p-a').value = q.short || q.grid;
    placeA.set({name: q.name || q.grid, short: q.short || q.grid, kind: q.kind || 'grid',
                lat: q.lat, lon: q.lon, grid: q.grid || latLonToGrid(q.lat, q.lon)});
  });

  const saveBtn = document.getElementById('p-save-qth');
  if (saveBtn) saveBtn.addEventListener('click', async () => {
    const place = placeA.get();
    if (!place) { toast('Nothing to save', 'Enter a location at your end first'); return; }
    await saveQTH(place);
    window.QTH = place;
    toast('QTH saved', place.short + ' · ' + place.grid +
          ' — the propagation page uses this too');
  });

  const locBtn = document.getElementById('p-locate');
  if (locBtn && geolocationAvailable()) {
    locBtn.hidden = false;
    locBtn.addEventListener('click', async () => {
      locBtn.textContent = 'locating…';
      try {
        const place = await locateMe();
        document.getElementById('p-a').value = place.short;
        placeA.set(place);
        await saveQTH(place);
        window.QTH = place;
        toast('Located', place.short + ' · ' + place.grid + ' — saved as your QTH');
      } catch (e) {
        toast('Could not locate you', 'Type a place name or grid square instead');
      }
      locBtn.textContent = 'locate me';
    });
  }
}

function radioHorizonKm(hMetres) {
  return 4.12 * Math.sqrt(Math.max(0, hMetres));      // 4/3 earth radius
}

function fresnel1(d1km, d2km, dkm, fMHz) {
  if (dkm <= 0 || fMHz <= 0) return 0;
  return 17.32 * Math.sqrt((d1km * d2km) / ((fMHz / 1000) * dkm));   // metres
}

function earthBulge(d1km, d2km) {
  return (d1km * d2km) / 17.0;                        // metres, k = 4/3
}

/* Single knife-edge diffraction loss, ITU-R P.526. `h` is how far the
   obstruction rises above the straight line between the antennas, in metres;
   negative means the path is clear over it. Without this the tool would quote
   a free-space budget over a blocked path and call it comfortable. */
function knifeEdgeLoss(hM, d1km, d2km, fMHz) {
  if (d1km <= 0 || d2km <= 0 || fMHz <= 0) return 0;
  const lambda = 299.792458 / fMHz;                   // metres
  const d1 = d1km * 1000, d2 = d2km * 1000;
  const v = hM * Math.sqrt((2 / lambda) * (1 / d1 + 1 / d2));
  if (v <= -0.78) return 0;
  return 6.9 + 20 * Math.log10(Math.sqrt((v - 0.1) ** 2 + 1) + v - 0.1);
}

async function calcPath() {
  if (!placeA || !placeB) return;
  /* Resolve anything typed but not yet committed, so pressing Analyse works
     without having to press Enter in the box first. */
  if (!placeA.get() && document.getElementById('p-a').value.trim()) await placeA.lookup();
  if (!placeB.get() && document.getElementById('p-b').value.trim()) await placeB.lookup();
  const A = placeA.get(), B = placeB.get();
  if (!A || !B) {
    document.getElementById('p-summary').innerHTML =
      '<span class="muted">Both ends need a location — a grid square (FN31pr), ' +
      'coordinates (41.71, -72.73), or a place name such as "Newington, CT".</span>';
    return;
  }
  window.PATH_READY = true;
  const f = num('p-f'), pw = num('p-pw'), sens = num('p-sens');
  const ahFt = num('p-ah'), bhFt = num('p-bh');
  const ag = num('p-ag'), bg = num('p-bg'), al = num('p-al'), bl = num('p-bl');
  const ahM = ahFt / M_FT, bhM = bhFt / M_FT;

  const toRad = d => d * Math.PI / 180;
  const dLat = toRad(B.lat - A.lat), dLon = toRad(B.lon - A.lon);
  const la1 = toRad(A.lat), la2 = toRad(B.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLon / 2) ** 2;
  const dKm = 2 * EARTH_R * Math.asin(Math.min(1, Math.sqrt(h)));
  const y = Math.sin(dLon) * Math.cos(la2);
  const x = Math.cos(la1) * Math.sin(la2) - Math.sin(la1) * Math.cos(la2) * Math.cos(dLon);
  const bearing = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;

  const horA = radioHorizonKm(ahM), horB = radioHorizonKm(bhM);
  const combined = horA + horB;

  const fspl = 32.44 + 20 * Math.log10(Math.max(f, 0.001)) + 20 * Math.log10(Math.max(dKm, 0.001));
  const ptxDbm = 10 * Math.log10(Math.max(pw, 0.0001) * 1000);
  const prx = ptxDbm + (ag + 2.15) + (bg + 2.15) - al - bl - fspl;
  const margin = prx - sens;

  const midF1 = fresnel1(dKm / 2, dKm / 2, dKm, f);
  const midBulge = earthBulge(dKm / 2, dKm / 2);

  const verdict = (ok, text, cls) =>
    '<span class="pill ' + cls + '">' + text + '</span>';
  const geoOk = dKm <= combined;

  document.getElementById('p-summary').innerHTML =
    '<div class="row" style="gap:1.4rem">' +
      '<span>Path <b>' + dKm.toFixed(1) + ' km</b> (' + (dKm * 0.6214).toFixed(1) + ' mi)</span>' +
      '<span>Bearing <b>' + bearing.toFixed(0) + '&deg;</b> out, ' +
        ((bearing + 180) % 360).toFixed(0) + '&deg; back</span>' +
      '<span>Smooth-earth horizon <b>' + combined.toFixed(1) + ' km</b> ' +
        '(' + horA.toFixed(1) + ' + ' + horB.toFixed(1) + ')</span>' +
      verdict(geoOk, geoOk ? 'inside the horizon' : 'past the horizon',
              geoOk ? 'good' : 'warn') +
    '</div>' +
    '<div class="row mt" style="gap:1.4rem" id="p-budget">' +
      '<span>Free-space loss <b>' + fspl.toFixed(1) + ' dB</b></span>' +
      '<span>Received <b>' + prx.toFixed(1) + ' dBm</b></span>' +
      '<span>Margin <b>' + margin.toFixed(1) + ' dB</b> ' +
        '<span class="muted tiny">if unobstructed</span></span>' +
    '</div>' +
    '<div class="small muted mt">First Fresnel zone is <b>' + midF1.toFixed(0) +
      ' m</b> across at the midpoint, and the earth itself bulges <b>' +
      midBulge.toFixed(1) + ' m</b> up there. Clearing 60% of that zone &mdash; ' +
      (0.6 * midF1).toFixed(0) + ' m &mdash; is what keeps a path behaving like free space.</div>';

  drawPath({dKm: dKm, f: f, ahM: ahM, bhM: bhM, terrain: null, loading: true});
  document.getElementById('p-notes').innerHTML =
    '<span class="muted">Fetching terrain…</span>';

  let profile = null;
  try {
    profile = await api('/api/terrain?' + new URLSearchParams({
      lat1: A.lat, lon1: A.lon, lat2: B.lat, lon2: B.lon, samples: 90}));
  } catch (e) { profile = null; }

  if (!profile || !profile.ok) {
    document.getElementById('p-notes').innerHTML =
      '<span class="muted">Terrain data is unavailable, so the figures above assume a ' +
      'smooth earth. A ridge in the way would not show here.</span>';
    drawPath({dKm: dKm, f: f, ahM: ahM, bhM: bhM, terrain: null});
    return;
  }

  /* Worst clearance against 60% of the first Fresnel zone. */
  const pts = profile.points;
  const tA = pts[0].elevation + ahM, tB = pts[pts.length - 1].elevation + bhM;
  let worst = null;
  pts.forEach(pt => {
    const d1 = pt.km, d2 = dKm - pt.km;
    if (d1 <= 0 || d2 <= 0) return;
    const los = tA + (tB - tA) * (d1 / dKm);
    const ground = pt.elevation + earthBulge(d1, d2);
    const f1 = fresnel1(d1, d2, dKm, f);
    const ratio = f1 > 0 ? (los - ground) / f1 : 99;
    if (worst === null || ratio < worst.ratio) {
      worst = {ratio: ratio, km: d1, ground: ground, los: los, f1: f1,
               elevation: pt.elevation};
    }
  });

  /* Free-space loss alone would call a blocked path comfortable, so the
     obstruction has to be costed and taken off the budget. */
  const obstruction = worst.ground - worst.los;
  const diffraction = knifeEdgeLoss(obstruction, worst.km, dKm - worst.km, f);
  const realPrx = prx - diffraction;
  const realMargin = realPrx - sens;

  const state = worst.ratio >= 0.6 ? ['line of sight clear', 'good']
    : worst.ratio > 0 ? ['grazing — obstruction inside the Fresnel zone', 'warn']
    : ['no line of sight — terrain in the way', 'bad'];
  const quality = realMargin >= 20 ? ['comfortable', 'good']
    : realMargin >= 10 ? ['workable', 'good']
    : realMargin > 0 ? ['marginal', 'warn'] : ['will not close', 'bad'];

  const budgetRow = document.getElementById('p-budget');
  if (budgetRow) budgetRow.innerHTML +=
    '<span>Diffraction <b>' + diffraction.toFixed(1) + ' dB</b></span>' +
    '<span>Actual margin <b>' + realMargin.toFixed(1) + ' dB</b></span>' +
    '<span class="pill ' + quality[1] + '">' + quality[0] + '</span>';

  document.getElementById('p-notes').innerHTML =
    '<div class="row" style="gap:1rem"><span class="pill ' + state[1] + '">' + state[0] + '</span>' +
    '<span class="small">Tightest point is <b>' + worst.km.toFixed(1) + ' km</b> along, ground at <b>' +
    worst.elevation.toFixed(0) + ' m</b>, clearing <b>' + (worst.ratio * 100).toFixed(0) +
    '%</b> of the first Fresnel zone.</span></div>' +
    '<div class="small muted mt">' +
    (worst.ratio >= 0.6
      ? 'Above 60% clearance the path behaves essentially as free space, so the margin above is the number that matters.'
      : worst.ratio > 0
        ? 'The straight line is clear but the ground intrudes into the Fresnel zone, costing <b>' +
          diffraction.toFixed(1) + ' dB</b> beyond free space. Raising either antenna is the usual fix.'
        : 'The ground stands <b>' + obstruction.toFixed(0) + ' m</b> above the straight line between ' +
          'the antennas, so nothing travels directly between them. What gets through is diffracted ' +
          'over the ridge, and that costs <b>' + diffraction.toFixed(1) + ' dB</b>' +
          (realMargin > 0
            ? ' — which this link can still afford, leaving ' + realMargin.toFixed(1) + ' dB in hand.'
            : ' — more than this link has to give. You would need about ' +
              Math.ceil(obstruction) + ' m more antenna height, a repeater, or more power.')) +
    ' Diffraction is a single knife-edge estimate (ITU-R P.526); real ridges are kinder or crueller ' +
    'depending on their shape. Terrain from ' + escapeHTML(profile.source) + '.</div>';

  drawPath({dKm: dKm, f: f, ahM: ahM, bhM: bhM, terrain: pts, worst: worst,
            tA: tA, tB: tB});
}

function drawPath(o) {
  const svg = document.getElementById('p-svg');
  if (!svg) return;
  const W = 900, H = 300, L = 52, R = 14, T = 18, B = 42;
  const px = km => L + (km / o.dKm) * (W - L - R);

  if (o.loading || !o.terrain) {
    const mid = (W + L) / 2;
    svg.innerHTML =
      '<line x1="' + L + '" y1="' + (H - B) + '" x2="' + (W - R) + '" y2="' + (H - B) +
        '" stroke="#8b98a5" stroke-width="1.5"/>' +
      '<line x1="' + L + '" y1="' + (H - B - 60) + '" x2="' + (W - R) + '" y2="' + (H - B - 40) +
        '" stroke="#ffb454" stroke-width="2" stroke-dasharray="6 4"/>' +
      '<text x="' + mid + '" y="' + (H / 2) + '" fill="#626e7b" font-size="12" ' +
        'text-anchor="middle" font-family="monospace">' +
        (o.loading ? 'fetching terrain…' : 'smooth earth — no terrain data') + '</text>';
    return;
  }

  const grounds = o.terrain.map((p, i) => {
    const d1 = p.km, d2 = o.dKm - p.km;
    return p.elevation + (d1 > 0 && d2 > 0 ? earthBulge(d1, d2) : 0);
  });
  const tops = o.terrain.map((p, i) => {
    const d1 = p.km, d2 = o.dKm - p.km;
    const los = o.tA + (o.tB - o.tA) * (d1 / o.dKm);
    return los + (d1 > 0 && d2 > 0 ? fresnel1(d1, d2, o.dKm, o.f) : 0);
  });
  const lo = Math.min(...grounds) - 15;
  const hi = Math.max(Math.max(...tops), o.tA, o.tB) + 15;
  const py = m => (H - B) - ((m - lo) / Math.max(1, hi - lo)) * (H - B - T);

  const groundPath = o.terrain.map((p, i) =>
    (i ? 'L' : 'M') + px(p.km).toFixed(1) + ',' + py(grounds[i]).toFixed(1)).join('');
  const fill = groundPath + 'L' + px(o.dKm) + ',' + (H - B) + 'L' + px(0) + ',' + (H - B) + 'Z';

  const upper = o.terrain.map((p, i) => {
    const d1 = p.km, d2 = o.dKm - p.km;
    const los = o.tA + (o.tB - o.tA) * (d1 / o.dKm);
    const r = d1 > 0 && d2 > 0 ? fresnel1(d1, d2, o.dKm, o.f) : 0;
    return (i ? 'L' : 'M') + px(p.km).toFixed(1) + ',' + py(los + r).toFixed(1);
  }).join('');
  const lower = o.terrain.slice().reverse().map((p, i) => {
    const d1 = p.km, d2 = o.dKm - p.km;
    const los = o.tA + (o.tB - o.tA) * (d1 / o.dKm);
    const r = d1 > 0 && d2 > 0 ? fresnel1(d1, d2, o.dKm, o.f) : 0;
    return 'L' + px(p.km).toFixed(1) + ',' + py(los - r).toFixed(1);
  }).join('');

  const worstX = px(o.worst.km);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(fr =>
    '<text x="' + px(o.dKm * fr) + '" y="' + (H - B + 16) + '" fill="#626e7b" font-size="10" ' +
    'text-anchor="middle" font-family="monospace">' + (o.dKm * fr).toFixed(1) + ' km</text>').join('');
  const yLabels = [lo, (lo + hi) / 2, hi].map(m =>
    '<text x="' + (L - 6) + '" y="' + (py(m) + 4) + '" fill="#626e7b" font-size="10" ' +
    'text-anchor="end" font-family="monospace">' + m.toFixed(0) + '</text>').join('');

  svg.innerHTML =
    '<defs><clipPath id="plotclip"><rect x="' + L + '" y="' + T + '" width="' +
      (W - L - R) + '" height="' + (H - B - T) + '"/></clipPath></defs>' +
    '<g clip-path="url(#plotclip)">' +
    '<path d="' + upper + lower + 'Z" fill="rgba(57,211,216,.10)" stroke="#39d3d8" ' +
      'stroke-width="1" stroke-dasharray="4 4"/>' +
    '<path d="' + fill + '" fill="rgba(139,152,165,.18)" stroke="#8b98a5" stroke-width="1.5"/>' +
    '<line x1="' + px(0) + '" y1="' + py(o.tA) + '" x2="' + px(o.dKm) + '" y2="' + py(o.tB) +
      '" stroke="#ffb454" stroke-width="2"/>' +
    '<line x1="' + px(0) + '" y1="' + py(o.terrain[0].elevation) + '" x2="' + px(0) + '" y2="' +
      py(o.tA) + '" stroke="#58a6ff" stroke-width="2"/>' +
    '<line x1="' + px(o.dKm) + '" y1="' + py(o.terrain[o.terrain.length - 1].elevation) +
      '" x2="' + px(o.dKm) + '" y2="' + py(o.tB) + '" stroke="#58a6ff" stroke-width="2"/>' +
    '</g>' +
    '<line x1="' + worstX + '" y1="' + T + '" x2="' + worstX + '" y2="' + (H - B) +
      '" stroke="' + (o.worst.ratio >= 0.6 ? '#3fb950' : '#f85149') + '" stroke-dasharray="3 3"/>' +
    '<text x="' + worstX + '" y="' + (T + 12) + '" fill="' +
      (o.worst.ratio >= 0.6 ? '#3fb950' : '#f85149') + '" font-size="11" ' +
      'text-anchor="middle" font-family="monospace">' + (o.worst.ratio * 100).toFixed(0) + '% F1</text>' +
    '<line x1="' + L + '" y1="' + (H - B) + '" x2="' + (W - R) + '" y2="' + (H - B) +
      '" stroke="#2a3441"/>' + ticks + yLabels +
    '<text x="' + (L - 6) + '" y="' + (T + 4) + '" fill="#626e7b" font-size="10" ' +
      'text-anchor="end" font-family="monospace">m</text>' +
    '<text x="' + (L + 6) + '" y="' + (T + 12) + '" fill="#ffb454" font-size="11" ' +
      'font-family="monospace">line of sight</text>' +
    '<text x="' + (L + 6) + '" y="' + (T + 26) + '" fill="#39d3d8" font-size="11" ' +
      'font-family="monospace">first Fresnel zone</text>';
}

const pathGo = document.getElementById('p-go');
if (pathGo) {
  pathGo.addEventListener('click', calcPath);
  ['p-a', 'p-b', 'p-ah', 'p-bh', 'p-f'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('keydown', e => { if (e.key === 'Enter') calcPath(); });
  });
  ['p-pw', 'p-sens', 'p-ag', 'p-bg', 'p-al', 'p-bl'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(el.type === 'checkbox' ? 'change' : 'input', () => {
      if (window.PATH_READY) calcPath();
    });
  });
}

/* first paint */
initPathPlaces();
openFromHash();
if (document.getElementById('s-svg')) drawSkip();
if (document.getElementById('r-svg')) drawReact();
if (document.getElementById('an-type')) {
  antennaFields(document.getElementById('an-type').value);
  calcAnt();
}
calcSWR(); calcDb();

/* ------------------------------------------------------- RF exposure ----- */
/* The evaluation every station is required to have done. Numbers come from
   the server so the screen and the printed record can never disagree. */

const RF_MODES = [
  ['ssb', 'SSB voice, no processing'], ['ssb_proc', 'SSB voice, heavy processing'],
  ['am', 'AM voice'], ['fm', 'FM voice'], ['cw', 'CW'],
  ['rtty', 'RTTY / FSK'], ['digital', 'FT8, PSK, other digital'],
  ['carrier', 'Continuous carrier / tune'],
];

let rfRows = [];

function rfDefaultRow() {
  return {frequency_mhz: 14.200, pep_watts: 100, mode: 'ssb',
          transmit_fraction: 0.5, gain_dbd: 2.1, antenna: 'dipole at 35 ft',
          gain_source: 'entered',
          distance_uncontrolled_ft: 25, distance_controlled_ft: 10};
}

function renderRfRows() {
  const box = document.getElementById('rf-rows');
  if (!box) return;
  box.innerHTML = rfRows.map((r, i) =>
    '<div class="rf-row" data-i="' + i + '">' +
      '<div class="field"><label>MHz</label><input data-k="frequency_mhz" value="' + r.frequency_mhz + '"></div>' +
      '<div class="field"><label>PEP (W)</label><input data-k="pep_watts" value="' + r.pep_watts + '"></div>' +
      '<div class="field"><label>Mode</label><select data-k="mode">' +
        RF_MODES.map(([v, l]) => '<option value="' + v + '"' +
          (v === r.mode ? ' selected' : '') + '>' + l + '</option>').join('') +
      '</select></div>' +
      '<div class="field"><label>TX time %</label><input data-k="transmit_fraction_pct" value="' +
        Math.round(r.transmit_fraction * 100) + '"></div>' +
      '<div class="field"><label>Gain (dBd)</label><input data-k="gain_dbd" value="' + r.gain_dbd + '"></div>' +
      '<div class="field wide"><label>Antenna</label><input data-k="antenna" value="' +
        escapeHTML(r.antenna) + '"></div>' +
      '<div class="field"><label>Public (ft)</label><input data-k="distance_uncontrolled_ft" value="' +
        r.distance_uncontrolled_ft + '"></div>' +
      '<div class="field"><label>You (ft)</label><input data-k="distance_controlled_ft" value="' +
        r.distance_controlled_ft + '"></div>' +
      '<button class="btn sm ghost rf-del" title="remove this band">&times;</button>' +
      '<div class="rf-priv" data-priv="' + i + '"></div>' +
    '</div>').join('');

  box.querySelectorAll('.rf-row').forEach(row => {
    const i = +row.dataset.i;
    row.querySelectorAll('[data-k]').forEach(el => {
      const handler = () => {
        const k = el.dataset.k;
        if (k === 'gain_dbd') rfRows[i].gain_source = 'entered';
        if (k === 'antenna' || k === 'mode') rfRows[i][k] = el.value;
        else if (k === 'transmit_fraction_pct') rfRows[i].transmit_fraction = (+el.value || 0) / 100;
        else rfRows[i][k] = +el.value;
        /* The frequency decides what may be sent, and the mode decides
           whether what is selected is one of those things. Either one moving
           means the answer under the row is now out of date. */
        if (k === 'frequency_mhz' || k === 'mode' || k === 'pep_watts') showPrivilege(i);
      };
      el.addEventListener('input', handler);
      el.addEventListener('change', handler);
    });
    row.querySelector('.rf-del').addEventListener('click', () => {
      if (rfRows.length > 1) { rfRows.splice(i, 1); renderRfRows(); rfEvaluate(); }
    });
    showPrivilege(i);
  });
}

/* ---------- what may actually be sent here ----------

   ELMER holds 47 CFR 97.301 and 97.305 in full, so a mode list that offers
   every mode on every frequency is not neutral - it quietly suggests the
   operation is fine. Each option now says whether it is permitted where the
   row is tuned, for the licence class on the profile.

   Nothing is disabled. A licensee may legitimately evaluate a station they
   cannot yet operate - a General planning an Extra segment, somebody working
   out what a club station needs - and blocking that would be wrong. But the
   record says so, on screen and on the printed sheet. */
const privCache = {};

async function showPrivilege(i) {
  const row = document.querySelector('.rf-row[data-i="' + i + '"]');
  if (!row) return;
  const note = row.querySelector('.rf-priv');
  const select = row.querySelector('select[data-k="mode"]');
  const mhz = +rfRows[i].frequency_mhz;
  if (!(mhz > 0)) { note.innerHTML = ''; return; }

  let d = privCache[mhz];
  if (!d) {
    try {
      d = await api('/api/privileges?mhz=' + encodeURIComponent(mhz));
    } catch (e) { return; }
    privCache[mhz] = d;
  }
  const byMode = {};
  d.modes.forEach(m => { byMode[m.key] = m; });

  /* The list itself carries the answer, so it is visible before a mode is
     chosen rather than only after. */
  select.querySelectorAll('option').forEach(opt => {
    const m = byMode[opt.value];
    const base = (RF_MODES.find(([v]) => v === opt.value) || [null, opt.value])[1];
    opt.textContent = base + (m && m.permitted === false ? '  \u2014 not permitted here' : '');
    opt.classList.toggle('not-permitted', !!(m && m.permitted === false));
  });

  const chosen = byMode[rfRows[i].mode];
  let html = '';
  if (!d.in_band) {
    html = '<span class="warntext">' + mhz + ' MHz is not in a US amateur band.</span> ' +
           'The exposure limits still apply, and are still evaluated.';
  } else if (!d.known_class) {
    html = '<b>' + escapeHTML(d.band) + '</b> &mdash; add your callsign on the ' +
           'band plan page and ELMER can also say what your class may send here.';
  } else if (!d.allowed) {
    html = '<span class="warntext"><b>' + escapeHTML(d.band) + ':</b> a ' +
      escapeHTML(d.licence_class) + ' licensee may not transmit on ' + mhz +
      ' MHz.</span> 47 CFR 97.301.';
  } else {
    html = '<b>' + escapeHTML(d.band) + '</b>, ' + escapeHTML(d.licence_class) +
      ': ' + escapeHTML(d.terms) + '.';
    if (chosen && chosen.permitted === false) {
      html += ' <span class="warntext">' + escapeHTML(chosen.label) +
        ' is not one of them.</span>';
    }
    const pep = +rfRows[i].pep_watts;
    if (d.max_pep && pep > d.max_pep) {
      html += ' <span class="warntext">' + pep + ' W is over the ' + d.max_pep +
        ' W PEP limit here.</span>';
    }
    if (d.max_erp && pep > d.max_erp) {
      html += ' <span class="warntext">This segment is limited to ' + d.max_erp +
        ' W ERP.</span>';
    }
    if (d.channelised && !d.channel) {
      html += ' <span class="warntext">Not one of the five 60 m channels.</span>';
    } else if (d.channel) {
      html += ' ' + escapeHTML(d.channel.name) + '.';
    }
  }
  if (chosen && chosen.caution) {
    html += ' <span class="muted">' + escapeHTML(chosen.caution) + '.</span>';
  }
  note.innerHTML = html;
}

function rfStation() {
  return {callsign: (document.getElementById('rf-call') || {}).value || '',
          location: (document.getElementById('rf-loc') || {}).value || '',
          grid: (document.getElementById('rf-grid') || {}).value || ''};
}

async function rfEvaluate() {
  const out = document.getElementById('rf-out');
  if (!out) return;
  let data;
  try {
    const res = await fetch('/api/rf-exposure', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({station: rfStation(), cases: rfRows})});
    data = await res.json();
    if (!res.ok) {
      out.innerHTML = '<div class="notice" style="border-left-color:var(--red)">' +
        '<b>That is not a station ELMER will sign off.</b> ' +
        escapeHTML(data.error || 'Check the numbers entered.') + '</div>';
      return;
    }
  } catch (e) {
    out.innerHTML = '<span class="muted">Check the numbers entered.</span>'; return;
  }

  const overall = (data.compliant
    ? '<span class="pill good">compliant at the distances entered</span>'
    : '<span class="pill bad">one or more positions exceed the limit</span>') +
    /* A green pill next to an operation the licence does not allow would read
       as approval of the whole thing. It is not: this evaluates exposure. */
    ((data.privilege_warnings || []).length
      ? '<span class="pill bad">not permitted by this licence</span>' : '');

  const seen = [];
  (data.warnings || []).forEach(w => { if (seen.indexOf(w) < 0) seen.push(w); });
  const warnBlock = seen.length
    ? '<div class="notice mt" style="border-left-color:var(--amber)">' +
      '<b>Check these before relying on it</b><ul style="margin:.35rem 0 0 1rem">' +
      seen.map(w => '<li>' + escapeHTML(w) + '</li>').join('') + '</ul></div>'
    : '';
  const gainNote = data.asserted_gain
    ? '<div class="tiny muted mt">Gain figures marked <b>as entered</b> have not ' +
      'been checked against any antenna. Design one in the Antennas tab and send ' +
      'it here to have the gain modelled instead.</div>'
    : '';

  out.innerHTML = '<div class="row" style="gap:1rem">' + overall +
    '<span class="small muted">' + escapeHTML(data.method.equation) +
    ' &middot; limits per 47 CFR 1.1310</span></div>' + warnBlock + gainNote +
    data.cases.map(c =>
      '<div class="panel tight mt">' +
        '<div class="spread"><b>' + escapeHTML(c.band) + ' &mdash; ' +
          c.frequency_mhz + ' MHz</b>' +
          '<span class="tiny mono muted">' + escapeHTML(c.antenna || '') + '</span></div>' +
        '<div class="tiny muted" style="margin:.25rem 0 .4rem">' +
          escapeHTML(c.mode_label) + ' &middot; duty ' + (c.duty_cycle * 100).toFixed(1) +
          '% &middot; average <b>' + c.average_watts + ' W</b> &middot; ' +
          c.gain_dbi.toFixed(2) + ' dBi <span class="pill ' +
          (c.gain_source === 'modelled' ? 'good' : '') + '">gain ' +
          (c.gain_source === 'modelled' ? 'modelled' : 'as entered') + '</span></div>' +
        '<table class="data"><thead><tr><th>Environment</th><th>Avg</th>' +
          '<th>Limit</th><th>At</th><th>Estimated</th><th>% of limit</th>' +
          '<th>Safe beyond</th><th></th></tr></thead><tbody>' +
        c.results.map(r =>
          '<tr><td class="small">' + escapeHTML(r.environment) + '</td>' +
          '<td class="mono tiny">' + r.averaging_minutes + ' min</td>' +
          '<td class="mono tiny">' + r.limit.toFixed(3) + '</td>' +
          '<td class="mono tiny">' + r.distance_ft.toFixed(1) + ' ft' +
            (r.near_field ? '<span style="color:var(--amber)" title="inside the near field">&dagger;</span>' : '') + '</td>' +
          '<td class="mono tiny">' + (r.density === null ? '—' : r.density.toFixed(4)) + '</td>' +
          '<td class="mono tiny">' + (r.margin_ratio === null ? '—'
            : (r.margin_ratio * 100).toFixed(1) + '%') + '</td>' +
          '<td class="mono tiny">' + (r.compliance_distance_ft === null ? '—'
            : r.compliance_distance_ft.toFixed(1) + ' ft') + '</td>' +
          '<td><span class="pill ' + (r.compliant ? 'good' : 'bad') + '">' +
            (r.compliant ? 'pass' : 'exceeds') + '</span></td></tr>').join('') +
        '</tbody></table>' +
        (c.results.some(r => r.near_field)
          ? '<div class="tiny muted" style="margin-top:.4rem">&dagger; inside the near ' +
            'field at this frequency &mdash; the estimate is indicative, keep people further back.</div>'
          : '') +
      '</div>').join('') +
    /* The same words that go on the printed sheet. Somebody comparing this
       against a figure from elsewhere should be able to see which way it was
       built to err, and that a different method is not the same as this one
       being wrong. */
    '<div class="panel tight mt"><div class="panel-title">Where this ' +
      'evaluation errs</div><p class="small muted" style="margin:0">' +
      escapeHTML(data.method.conservatism || '') + '</p></div>';
}

async function rfDownload() {
  const btn = document.getElementById('rf-pdf');
  btn.disabled = true; btn.textContent = 'Building…';
  try {
    const res = await fetch('/api/rf-exposure/pdf', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({station: rfStation(), cases: rfRows})});
    if (!res.ok) throw new Error('status ' + res.status);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (res.headers.get('Content-Disposition') || '')
      .match(/filename="?([^"]+)"?/)?.[1] || 'RF-exposure.pdf';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast('Station record ready', 'Print it and post it in the shack');
  } catch (e) {
    toast('Could not build the PDF', 'See data/elmer.log');
  }
  btn.disabled = false; btn.textContent = 'Download station record (PDF)';
}

function initRf() {
  if (!document.getElementById('rf-rows')) return;
  const qth = window.QTH || {};
  const loc = document.getElementById('rf-loc'), grid = document.getElementById('rf-grid');
  if (loc && !loc.value) loc.value = qth.short || qth.name || '';
  if (grid && !grid.value) grid.value = qth.grid || '';
  const call = document.getElementById('rf-call');
  if (call && window.CALLSIGN) call.value = window.CALLSIGN;
  rfRows = [rfDefaultRow()];
  renderRfRows();
  document.getElementById('rf-add').addEventListener('click', () => {
    rfRows.push(rfDefaultRow()); renderRfRows();
  });
  document.getElementById('rf-eval').addEventListener('click', rfEvaluate);
  document.getElementById('rf-pdf').addEventListener('click', rfDownload);
  if (call) call.addEventListener('change', () =>
    postJSON('/api/settings', {callsign: call.value}).catch(() => {}));
  rfEvaluate();
}
initRf();
