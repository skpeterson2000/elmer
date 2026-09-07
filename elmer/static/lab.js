/* Lab: live calculators. Every formula here is one the pools ask about, so the
   wording of the outputs deliberately mirrors the exam vocabulary. */

/* ------------------------------------------------------------------ tabs */
/* Points of the compass. Declared here rather than beside the plan view that
   uses it: a const is hoisted but not initialised, and the antenna panel draws
   itself at page load - which put this in the temporal dead zone and threw. */
const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
function compass(deg) {
  return COMPASS[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16];
}

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

/* --------------------------------------------------------- the arithmetic */
/* Where the dimensions come from, worked in front of the operator.

   A calculator that only prints 32.96 ft has taught nothing: the next time
   somebody is up a hill with a tape measure and no Pi, they have no antenna.
   The same three steps produce every wire length in amateur radio, and once
   they are seen a couple of times they are owned - so ELMER stops being the
   thing that knows and becomes the thing that showed you.

   There are plenty of antenna plans in the world. What is scarce is the
   habit of deriving one. */

function derivation(type, f, k, rows) {
  if (!(f > 0)) return '';
  const lam = LAMBDA_FT(f);
  const step = (sum, result, why) =>
    '<tr><td class="mono">' + sum + '</td><td class="mono">' + result +
    '</td><td class="tiny muted">' + why + '</td></tr>';

  /* Show the constant actually used, not the one usually quoted. Printing
     "984" beside a result computed from 983.571 means anybody who checks the
     line on a calculator gets a different answer - which is precisely the
     person this table exists for. */
  let steps = step('983.6 &divide; ' + f.toFixed(3) + ' MHz', lam.toFixed(2) + ' ft',
    'One whole wavelength in free space. 983.6 is the speed of light in feet ' +
    'per microsecond, and frequency in MHz is cycles per microsecond, so the ' +
    'division is just distance = speed &times; time. Most books round it to ' +
    '984, which is close enough to build from and half an inch different at ' +
    '14 MHz.');

  const kind = {
    dipole: ['&divide; 2', 2, 'A dipole is half a wave: two quarter-wave legs, fed in the middle.'],
    invertedv: ['&divide; 2', 2, 'Same half wave as a dipole - the droop changes the pattern and the feedpoint, not the length.'],
    efhw: ['&divide; 2', 2, 'An end-fed half wave is the same half wavelength of wire, fed at the end instead of the middle.'],
    bowtie: ['&divide; 2', 2, 'Still a half wave overall. The width is what buys the bandwidth; it does not change the resonant length much.'],
    quarter: ['&divide; 4', 4, 'A quarter-wave vertical is half an antenna - the ground plane is the other half, which is why the radials matter.'],
    groundplane: ['&divide; 4', 4, 'A quarter wave against its radials. Each radial is a quarter wave too.'],
    jpole: ['&divide; 2', 2, 'The radiator is an end-fed half wave; the stub below it is a quarter-wave matching section.'],
    fiveeighth: ['&times; 0.625', 1 / 0.625, 'Five eighths of a wave - not resonant, which is why it needs a base coil, and lower-angle in exchange.'],
    loop: ['&times; 1', 1, 'A full-wave loop is one whole wavelength of wire in the perimeter.'],
    yagi: ['&divide; 2', 2, 'Every element is about a half wave - the reflector a little longer, the directors a little shorter.'],
  }[type];

  if (kind) {
    steps += step(lam.toFixed(2) + ' ' + kind[0], (lam / kind[1]).toFixed(2) + ' ft', kind[2]);
    const vf = (lam / kind[1]) * k;
    steps += step('&times; ' + k.toFixed(3), vf.toFixed(2) + ' ft',
      'The velocity factor. A wire is not free space: the ends couple to ' +
      'everything around them, so it behaves electrically longer than it ' +
      'measures and has to be cut short. About 0.95 for ordinary wire, less ' +
      'for anything fatter - which is why <b>468 &divide; f</b> is the number ' +
      'everybody memorises for a dipole, and where it comes from.');
  }

  /* Reconcile with the constant everybody memorises, rather than leaving the
     working half an inch away from the table above it and hoping nobody
     checks. 984/2 x 0.95 is 467.4; the books say 468. That gap is the whole
     character of the number - it is a practical constant somebody rounded,
     not a derivation - and saying so is worth more than hiding it. */
  /* Account for the table above, or the reader is left with two numbers and
     no idea which to cut. ELMER prints the book constant - 468/f, scaled for
     this conductor - because that is what the craft uses and what the pools
     teach. The first-principles chain lands a fraction under it, and the size
     of that fraction is the lesson: these constants disagree at the half-inch
     level and it has never mattered. */
  if (kind && Math.abs(kind[1] - 2) < 0.01) {
    const derived = lam / 2 * k, printed = (468 / f) * (k / 0.95);
    const gapIn = Math.abs(printed - derived) * 12;
    steps += step('468 &divide; ' + f.toFixed(3) + ' &times; ' +
        (k / 0.95).toFixed(3),
      printed.toFixed(2) + ' ft',
      'What the table above prints. 468 is the constant the books and the ' +
      'question pools use, and it is 983.6 &divide; 2 &times; 0.95 = 467.2 ' +
      'rounded up. So it lands ' + gapIn.toFixed(1) + ' in away from the ' +
      'line above - inside the error of your tape and far inside what a ' +
      'gutter or a wet tree will shift it. Cut to either and trim on the ' +
      'analyser; that is what the trimming is for.');
  }

  return '<details class="derivation"><summary class="tiny">' +
    'Where these numbers come from &mdash; so you can do it without ELMER' +
    '</summary><table class="data tiny" style="max-width:640px"><tbody>' +
    steps + '</tbody></table>' +
    '<p class="tiny muted">Three steps, and they are the same three for every ' +
    'wire antenna on any band: a wavelength, the fraction of it this antenna ' +
    'uses, and the shortening the real world asks for. Learn them and the ' +
    'plan comes from you - which is the point of the lab, and the reason it ' +
    'does not ship cut-and-assemble instructions.</p></details>';
}

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
  // Two triangles instead of two wires. Same gain as a dipole to within a
  // rounding error - the whole point of it is the bandwidth, because a fat
  // element is a low-Q element and a low-Q element holds its SWR across a
  // band a thin wire cannot.
  bowtie: {shape: 'bowtie', label: 'Bowtie dipole', gain: 0.1, z: 60, ref: FREE_SPACE,
    build: f => ({'Overall span': 446 / f, 'Each element, feed to tip': 223 / f,
                  'Width across each tip': 257 / f,
                  'Feed gap between apexes': 0.5})},
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

/* Feedpoint resistance of a quarter wave against its radials, as they are
   drooped. Flat radials give about 36 ohms; at 45 degrees it is near 50, which
   is the whole reason anybody droops them; carried all the way to 90 it is a
   vertical dipole at about 72. This is a smooth curve through those three
   textbook figures, not a modelled result - it is here so the slider shows
   the effect the note claims, rather than asserting it at a drawing that
   contradicts it. */
function radialZ(deg) {
  const x = Math.max(0, Math.min(90, deg)) / 90;
  return Math.round(36 + 20 * x + 16 * x * x);
}


/* What the element is made of, refreshed whenever the frequency moves: the
   same pipe is a different antenna at 14 MHz and at 146. */
let COND = {key: 'wire14', k: 0.95, q_scale: 1, band_scale: 1, label: ''};
let CONDUCTORS = [];

async function loadConductors(mhz) {
  try {
    const d = await api('/api/conductors?mhz=' + encodeURIComponent(mhz));
    CONDUCTORS = d.conductors;
  } catch (e) { return; }
  const sel = document.getElementById('an-cond');
  if (!sel) return;
  const chosen = sel.value || COND.key || 'wire14';
  sel.innerHTML = CONDUCTORS.map(c =>
    '<option value="' + c.key + '"' + (c.key === chosen ? ' selected' : '') +
    '>' + escapeHTML(c.label) + '</option>').join('');
  COND = CONDUCTORS.find(c => c.key === chosen) || CONDUCTORS[0];
  showConductor();
}

function showConductor() {
  const out = document.getElementById('an-cond-v');
  if (!out || !COND) return;
  const wider = COND.band_scale;
  out.innerHTML = COND.od_mm + ' mm across &mdash; ' +
    (Math.abs(wider - 1) < 0.03
      ? 'the reference'
      : wider > 1
        ? '<b>' + wider.toFixed(2) + '&times; the bandwidth</b> of #14 wire'
        : '<b>' + (1 / wider).toFixed(2) + '&times; narrower</b> than #14 wire');
}

const NVIS_TYPES = ['dipole', 'invertedv', 'loop', 'efhw', 'bowtie'];

/* Which antennas are balanced, because that and nothing else decides what goes
   at the feedpoint. A balun crosses between balanced and unbalanced; an unun
   stays on the unbalanced side; and a choke stops common-mode current whatever
   else is fitted. The three get used as though they were interchangeable. */
const BALANCED = ['dipole', 'invertedv', 'bowtie', 'loop', 'yagi'];

function feedNote(type, slopeDeg) {
  if (type === 'efhw') return '';           /* it has its own, longer, note */
  const balanced = BALANCED.indexOf(type) >= 0;
  if (!balanced) {
    return '<b>Feeding it.</b> This is an unbalanced antenna, so coax suits it ' +
      'directly &mdash; no balun is called for. Put a choke on the feedline ' +
      'anyway: it stops the braid carrying current back into the shack and ' +
      'joining in with the pattern.';
  }
  let html = '<b>Feeding it.</b> This is a <b>balanced</b> antenna. On coax, ' +
    'which is not, put a <b>1:1 current balun</b> &mdash; a choke &mdash; at the ' +
    'feedpoint: that is exactly the balanced-to-unbalanced crossing a balun is ' +
    'for. On <b>ladder line</b> you need nothing at the antenna at all, because ' +
    'balanced line into a balanced antenna crosses nothing; the balun belongs at ' +
    'the far end, where the line meets an unbalanced rig or tuner. A ' +
    'link-coupled or genuinely balanced tuner needs none even there.';
  if (type === 'dipole' || type === 'bowtie' || type === 'loop') {
    html += ' The 4:1 balun that usually gets fitted at the shack end of ladder ' +
      'line is a habit rather than a calculation &mdash; the impedance up there ' +
      'swings enormously band to band, and a 1:1 current balun ahead of a ' +
      'wide-range tuner handles that better than a fixed 4:1 does.';
  }
  if (slopeDeg) {
    html += ' <b>And note what the slope does to that:</b> a sloping dipole is a ' +
      'balanced antenna in an unbalanced position. One half is higher than the ' +
      'other, so the two halves see different ground, and the currents will not ' +
      'match perfectly however carefully you feed it. The choke matters more ' +
      'here than on a flat dipole, not less.';
  }
  return html;
}

function antennaFields(type) {
  const show = (cls, on) => document.querySelectorAll(cls)
    .forEach(el => { el.style.display = on ? '' : 'none'; });
  show('.an-when-yagi', type === 'yagi');
  /* A vertical is the same in every direction, so asking which way it is laid
     would be a question with no answer - which is exactly why we call it
     omnidirectional. */
  show('.an-when-heading', (ANTENNAS[type] || {}).shape !== 'vert' && type !== 'whip');
  /* A straight wire on one support can be slung at an angle; a V already has
     its own droop and a beam has a boom. */
  show('.an-when-slope', type === 'efhw' || type === 'dipole');
  show('.an-when-whip', type === 'whip');
  show('.an-when-height', type !== 'whip');
  show('.an-when-v', type === 'invertedv');
  show('.an-when-radials', type === 'groundplane');
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
  /* The velocity factor is now mostly the conductor's business: a fat element
     resonates shorter than a thin one. The manual picker stays for anybody
     who has measured their own, and whichever moved last wins. */
  const k = COND.k || num('an-k');
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
    notes.push(feedNote('yagi', 0));
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
    /* The build formulas embed 0.95 - the wire case. Anything fatter comes
       out shorter, and by enough to matter at VHF: a 2 m dipole in half-inch
       copper is the better part of an inch short of the wire figure. */
    if (Math.abs(k - 0.95) > 0.0005) {
      Object.keys(rows).forEach(key => {
        if (!/gap|Feed tap/i.test(key)) rows[key] = rows[key] * k / 0.95;
      });
    }
    gain = spec.gain;
    z = spec.z;
    if (type === 'groundplane') z = radialZ(num('an-radials'));
    gainRef = spec.ref || FREE_SPACE;
    if (type === 'efhw') {
      notes.push('The end of a half wave is a high-voltage, high-impedance ' +
        'point &mdash; around ' + z + '&nbsp;&Omega; &mdash; so it needs a 49:1 ' +
        'transformer, not a direct coax feed.');
      /* Two different jobs, two different words, and they are not
         interchangeable however often the catalogue treats them as though
         they were. */
      notes.push('<b>Unun, not balun.</b> A <b>bal</b>un converts <b>bal</b>anced ' +
        'to <b>un</b>balanced &mdash; a dipole is balanced, coax is not, so a ' +
        'dipole wants one. An end-fed is a single wire worked against a ' +
        'counterpoise: unbalanced on both sides, so what transforms the ' +
        'impedance is an <b>un</b>balanced-to-<b>un</b>balanced transformer, an ' +
        '<b>unun</b>. It is wound as an autotransformer &mdash; one winding with ' +
        'a tap, the coax braid and the counterpoise sharing the common end &mdash; ' +
        'which is what an unun is. Plenty of them are sold as "49:1 balun"; the ' +
        'part is fine, the label is wrong.');
      notes.push('<b>On ladder line it is a different animal.</b> Balanced line ' +
        'into an unbalanced antenna is a crossing, and a crossing is what a ' +
        'balun is for &mdash; so yes, in principle. But what you have actually ' +
        'built is the <b>end-fed Zepp</b>: a half wave fed at the end through a ' +
        'quarter wave of open-wire line, which transforms that high impedance ' +
        'down for the tuner. It is a genuine antenna with a century of use ' +
        'behind it, and a known flaw. Only one conductor of the feeder attaches ' +
        'to the wire and the other attaches to nothing, so the two currents can ' +
        'never balance and the feeder radiates &mdash; which is the Zepp\'s ' +
        'reputation and is inherent to the topology rather than something a ' +
        'balun at the antenna end cures. Feed it with a balanced tuner, keep the ' +
        'feeder length deliberate, and expect some feeder radiation. If you want ' +
        'the wire on ladder line without that, feed it in the middle and build a ' +
        'doublet instead.');
      notes.push('That is not the end of it, and this is where end-feds get a ' +
        'bad name. The unun matches the impedance but does nothing about ' +
        'common-mode current, so give it a counterpoise and put a <b>choke</b> ' +
        '&mdash; a 1:1 current balun, which really is a balun &mdash; on the coax ' +
        'below it. Without one the braid becomes the counterpoise: the feedline ' +
        'radiates, the pattern goes where it likes, the SWR moves when you touch ' +
        'the rig, and the noise floor comes up. Most end-fed disappointment is ' +
        'this and not the antenna.');
    }
    const feeding = feedNote(type, (type === 'dipole') ? num('an-slope') : 0);
    if (feeding) notes.push(feeding);
    if (COND && COND.note) {
      notes.push('<b>' + escapeHTML(COND.label) + '.</b> ' +
        escapeHTML(COND.note) +
        (Math.abs(COND.band_scale - 1) > 0.03
          ? ' At this frequency that is <b>' + COND.band_scale.toFixed(2) +
            '&times;</b> the 2:1 bandwidth of #14 wire, and the element wants ' +
            'cutting to <b>' + COND.k.toFixed(3) + '</b> of a half wavelength ' +
            'rather than 0.95 &mdash; fatter resonates shorter.'
          : ''));
      if (COND.caution) {
        notes.push('<b>Watch out:</b> ' + escapeHTML(COND.caution));
      }
    }
    if (type === 'quarter' || type === 'groundplane') notes.push(
      'A quarter-wave vertical is half an antenna: the ground plane is the other half. ' +
      'Radial count matters more than radial length &mdash; 16 or more on the ground, or ' +
      'four elevated.');
    if (type === 'groundplane') {
      const dr = num('an-radials');
      notes.push('Radials at <b>' + dr.toFixed(0) + '&deg;</b> put the feed point near <b>' +
        radialZ(dr) + '&nbsp;&Omega;</b>. Flat radials give roughly 36&nbsp;&Omega; ' +
        '&mdash; a 1.4:1 mismatch you can live with but need not &mdash; and about ' +
        '45&deg; brings it to 50, which is the whole point of the droop. Past that ' +
        'it climbs on towards the 72&nbsp;&Omega; of a vertical dipole.' +
        (dr < 20 ? ' <b>At this angle they are barely drooped:</b> move the slider ' +
                   'and watch the figure, and the drawing, follow.' : ''));
    }
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
  const radEl = document.getElementById('an-radials-v');
  if (radEl) radEl.textContent = num('an-radials').toFixed(0) + '\u00b0 down \u2014 about '
    + radialZ(num('an-radials')) + ' \u03a9';

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
      const slopeDeg = (type === 'efhw' || type === 'dipole') ? num('an-slope') : 0;
      if (slopeDeg) {
        /* A sloping wire radiates from the height of its middle, not the top
           of the mast - which is the figure people quote, and the reason a
           sloper disappoints against the dipole they had imagined. */
        const wireFt = rows['Wire length'] || rows['Overall length'] || lamFt / 2;
        const drop = wireFt * Math.sin(slopeDeg * Math.PI / 180) /
                     (type === 'dipole' ? 2 : 1);
        const lowEnd = hFt - drop, midFt = hFt - drop / 2;
        /* Geometry before physics: a long wire at a steep angle from a short
           support puts its far end underground, and printing a negative height
           as though it were a result would be worse than useless. */
        const maxDeg = Math.round(Math.asin(
          Math.max(0, Math.min(1, (hFt - 8) / (wireFt / (type === 'dipole' ? 2 : 1))))
        ) * 180 / Math.PI);
        if (lowEnd < 8) {
          notes.push('<span style="color:var(--red)"><b>That does not fit.</b></span> ' +
            'A ' + wireFt.toFixed(0) + '&nbsp;ft wire at ' + slopeDeg +
            '&deg; drops ' + drop.toFixed(0) + '&nbsp;ft, so from a ' +
            hFt.toFixed(0) + '&nbsp;ft support the far end lands at ' +
            lowEnd.toFixed(0) + '&nbsp;ft &mdash; ' +
            (lowEnd < 0 ? 'below the ground.' : 'inside head height.') +
            ' From this support the wire will take about <b>' + maxDeg +
            '&deg;</b> before the end is too low' +
            (type === 'efhw'
              ? ', and on an end-fed that far end is the high-voltage point, so ' +
                'it is the one to keep up.'
              : '.') +
            ' Raise the support, shorten the angle, or run it flatter.');
        } else {
          notes.push('<b>Slung at ' + slopeDeg + '&deg;</b> the support end is ' +
            'at ' + hFt.toFixed(0) + '&nbsp;ft and the low end at <b>' +
            lowEnd.toFixed(0) + '&nbsp;ft</b>, so it radiates from about <b>' +
            midFt.toFixed(0) + '&nbsp;ft</b> &mdash; the height of its middle, ' +
            'not of the mast. That is the figure people quote when a sloper ' +
            'disappoints against the dipole they had imagined.' +
            (type === 'efhw'
              ? ' Feed it at the low end: the far end of an end-fed is the ' +
                'high-voltage point, and that is the one you want up the tree.'
              : ''));
        }
        notes.push('Tilting mixes vertical polarisation into what was a ' +
          'horizontal antenna, and the vertical part does not null along the ' +
          'horizon the way the horizontal part does. That is where the ' +
          'low-angle radiation below comes from, and it is the whole of the ' +
          'sloper\'s case. <b>Believe about half of it:</b> the plot assumes ' +
          'perfect ground, and over ordinary soil the vertical component gives ' +
          'up several decibels at exactly the low angles it is being credited ' +
          'with. Over salt water it delivers what the drawing shows; over dry ' +
          'sand it does not.');
        notes.push('It also favours the downhill direction by a few decibels, ' +
          'which is real but small &mdash; and it is not drawn below, because ' +
          'putting a number on it needs the wire modelled over your actual ' +
          'soil rather than a rule of thumb.');
      }
      const hLam = effFt / lamFt;
      takeoff = Math.min(90, Math.asin(Math.min(1, 1 / (4 * hLam))) * 180 / Math.PI);
      if (!slopeDeg) notes.push('At <b>' + hFt.toFixed(0) + '&nbsp;ft</b>' +
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
    derivation(type, f, k, rows) +
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
  const slope = (type === 'efhw' || type === 'dipole') ? num('an-slope') : 0;
  const slopeEl = document.getElementById('an-slope-v');
  if (slopeEl) {
    slopeEl.textContent = slope
      ? slope + '\u00b0 \u2014 a sloper' : 'flat';
  }
  const slopeWire = rows['Wire length'] || rows['Overall length'] || 0;
  const slopeDrop = slopeWire * Math.sin(slope * Math.PI / 180) /
                    (type === 'dipole' ? 2 : 1);
  const effHeight = slope ? Math.max(1, heightFt - slopeDrop / 2) : heightFt;
  const heading = num('an-head');
  const headEl = document.getElementById('an-head-v');
  if (headEl) {
    headEl.textContent = type === 'yagi'
      ? 'boom points ' + heading + '\u00b0 ' + compass(heading)
      : 'wire runs ' + heading + '\u00b0 ' + compass(heading) + ' to ' +
        ((heading + 180) % 360) + '\u00b0 ' + compass((heading + 180) % 360);
  }
  drawPattern(type, f, heightFt, heading, slope, effHeight);

  window.LAB_ANTENNA = {
    type: type,
    z: z,                       /* so the Smith chart can start from it */
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

  if (shape === 'bowtie') {
    /* Two triangles nose to nose: the picture is the explanation, because the
       width of the element is what buys the bandwidth. */
    /* Drawn from the dimensions, not from a guess. A real bowtie is nearly as
       wide across the tips as each half is long - the apex angle is about 70
       degrees - and it was being drawn as a slender dart at a fifth of that,
       which made the picture argue against the number beside it and against
       the whole reason for building one. */
    const edge = rows['Each element, feed to tip'] || 1;
    const tipW = rows['Width across each tip'] || edge;
    const axial = Math.sqrt(Math.max(0.0001, edge * edge - (tipW / 2) * (tipW / 2)));
    const cy = 96, halfSpan = 200, gap = 9;
    const halfW = Math.min(78, halfSpan * (tipW / 2) / Math.max(0.0001, axial));
    body =
      '<polygon points="' + (W / 2 - gap) + ',' + cy + ' ' +
        (W / 2 - halfSpan) + ',' + (cy - halfW) + ' ' +
        (W / 2 - halfSpan) + ',' + (cy + halfW) +
        '" fill="rgba(255,180,84,.20)" stroke="#ffb454" stroke-width="2"/>' +
      '<polygon points="' + (W / 2 + gap) + ',' + cy + ' ' +
        (W / 2 + halfSpan) + ',' + (cy - halfW) + ' ' +
        (W / 2 + halfSpan) + ',' + (cy + halfW) +
        '" fill="rgba(255,180,84,.20)" stroke="#ffb454" stroke-width="2"/>' +
      '<line x1="' + (W / 2) + '" y1="' + cy + '" x2="' + (W / 2) + '" y2="' + g +
        '" stroke="#58a6ff" stroke-width="1.4" stroke-dasharray="4 3"/>' +
      lbl(W / 2, cy - 60, 'feed at the apexes') +
      lbl(W / 2, cy + halfW + 22, 'wide element = low Q = wide band') +
      lbl(W / 2 + 40, (cy + g) / 2, 'height', 'start');
  } else if (shape === 'wire') {
    const y = 90;
    /* The angle on the screen is the angle you set. Both of these used to be
       drawn at a fixed shape whatever the slider said, which made the picture
       a decoration rather than a readout - and on a sloper the angle is the
       entire subject. The horizontal span shrinks as the angle steepens so the
       drop always fits between the wire and the ground, which keeps the drawn
       angle true rather than flattening it to fit. */
    const tilt = (deg, room) => {
      const rad = Math.abs(deg) * Math.PI / 180;
      const span = Math.min(200, rad > 0.01 ? room / Math.tan(rad) : 200);
      return {span: span, drop: span * Math.tan(rad)};
    };
    if (type === 'loop') {
      body = '<rect x="215" y="45" width="190" height="120" fill="none" stroke="#ffb454" stroke-width="2.5"/>' +
        '<line x1="310" y1="165" x2="310" y2="' + g + '" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4 3"/>' +
        lbl(310, 38, 'one full wavelength of wire') + lbl(310, 200, 'feed', 'middle');
    } else if (type === 'efhw') {
      const slope = num('an-slope') || 0;
      if (slope > 0) {
        /* Fed at the low end, rising to the support: that puts the far end -
           which on an end-fed is the high-voltage one - at the top, where it
           belongs and where it is out of reach. */
        const t = tilt(slope, 62);
        const top = 50, x1 = 310 - t.span, x2 = 310 + t.span;
        const yLow = top + 2 * t.drop;
        body =
          '<line x1="' + x2 + '" y1="' + top + '" x2="' + x2 + '" y2="' + g +
            '" stroke="#2a3441" stroke-width="3"/>' +
          '<line x1="' + x1 + '" y1="' + yLow + '" x2="' + x2 + '" y2="' + top +
            '" stroke="#ffb454" stroke-width="2.5"/>' +
          '<circle cx="' + x1 + '" cy="' + yLow + '" r="5" fill="#58a6ff"/>' +
          '<line x1="' + x1 + '" y1="' + yLow + '" x2="' + x1 + '" y2="' + g +
            '" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4 3"/>' +
          lbl(x1, yLow + 22, '49:1 unun, fed low') +
          lbl(x2, top - 10, 'far end, high voltage') +
          lbl((x1 + x2) / 2, (top + yLow) / 2 - 12, slope + '\u00b0');
      } else {
        body = '<line x1="120" y1="' + y + '" x2="520" y2="' + y + '" stroke="#ffb454" stroke-width="2.5"/>' +
          '<circle cx="120" cy="' + y + '" r="5" fill="#58a6ff"/>' +
          '<line x1="120" y1="' + y + '" x2="120" y2="' + g + '" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4 3"/>' +
          lbl(320, y - 12, 'half wavelength of wire') + lbl(120, y - 16, '49:1 unun');
      }
    } else if (type === 'dipole' && num('an-slope') > 0) {
      const slope = num('an-slope');
      const t = tilt(slope, 62);
      const top = 50, x1 = 310 - t.span, x2 = 310 + t.span;
      const yLow = top + 2 * t.drop, yMid = top + t.drop;
      body =
        '<line x1="' + x2 + '" y1="' + top + '" x2="' + x2 + '" y2="' + g +
          '" stroke="#2a3441" stroke-width="3"/>' +
        '<line x1="' + x1 + '" y1="' + yLow + '" x2="' + x2 + '" y2="' + top +
          '" stroke="#ffb454" stroke-width="2.5"/>' +
        '<circle cx="310" cy="' + yMid + '" r="5" fill="#58a6ff"/>' +
        '<line x1="310" y1="' + yMid + '" x2="310" y2="' + g +
          '" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4 3"/>' +
        lbl(310, yMid + 24, 'feed at the middle') +
        lbl(x2, top - 10, 'high end') + lbl(x1, yLow + 16, 'low end') +
        lbl((310 + x2) / 2, (top + yMid) / 2 - 10, slope + '\u00b0');
    } else {
      /* The droop follows the slider now, rather than a fixed 55 pixels that
         made the V look the same at 5 degrees as at 60. */
      const t = type === 'invertedv' ? tilt(num('an-droop'), 95) : {span: 200, drop: 0};
      const x1 = 310 - t.span, x2 = 310 + t.span;
      body = '<line x1="' + x1 + '" y1="' + (y + t.drop) + '" x2="310" y2="' + y + '" stroke="#ffb454" stroke-width="2.5"/>' +
        '<line x1="310" y1="' + y + '" x2="' + x2 + '" y2="' + (y + t.drop) + '" stroke="#ffb454" stroke-width="2.5"/>' +
        '<line x1="310" y1="' + y + '" x2="310" y2="' + g + '" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4 3"/>' +
        lbl((x1 + 310) / 2, y + t.drop / 2 - 10, 'leg') +
        lbl((310 + x2) / 2, y + t.drop / 2 - 10, 'leg') +
        lbl(310, y - 12, 'feed point') + lbl(350, (y + g) / 2, 'height', 'start');
    }
  } else if (shape === 'vert') {
    /* A ground plane is an elevated antenna - that is what lets the radials
       droop at all - so it is drawn up a mast, with the radials above the
       ground rather than driven through it. */
    const elevated = type === 'groundplane';
    const base = elevated ? 120 : g;
    const top = elevated ? 40 : (type === 'fiveeighth' ? 40 : 70);
    body = '<line x1="310" y1="' + top + '" x2="310" y2="' + base + '" stroke="#ffb454" stroke-width="3"/>' +
      lbl(330, (top + base) / 2, 'radiator', 'start');
    if (elevated) {
      body += '<line x1="310" y1="' + base + '" x2="310" y2="' + g +
        '" stroke="#8b98a5" stroke-width="1.5" stroke-dasharray="4 3"/>' +
        lbl(322, (base + g) / 2 + 26, 'mast', 'start');
    }
    if (type === 'jpole') {
      body += '<line x1="270" y1="140" x2="270" y2="' + g + '" stroke="#ffb454" stroke-width="3"/>' +
        '<line x1="270" y1="' + g + '" x2="310" y2="' + g + '" stroke="#ffb454" stroke-width="3"/>' +
        lbl(250, 135, 'stub', 'end') + '<circle cx="270" cy="' + (g - 18) + '" r="4" fill="#58a6ff"/>' +
        lbl(240, g - 18, 'feed', 'end');
    } else if (type === 'groundplane') {
      /* Drawn at the angle that is set, because the note next to it is about
         that angle. A flat line here while the text explains why you droop
         them is the program disagreeing with itself in front of a beginner. */
      /* 90 px of radial keeps the steepest droop clear of the ground line
         while staying about as long as the radiator, which is what a quarter
         wave against a quarter wave should look like. */
      const dr = num('an-radials'), r = 90;
      const dx = r * Math.cos(dr * Math.PI / 180), dy = r * Math.sin(dr * Math.PI / 180);
      body += '<line x1="310" y1="' + base + '" x2="' + (310 - dx).toFixed(1) +
        '" y2="' + (base + dy).toFixed(1) + '" stroke="#39d3d8" stroke-width="2"/>' +
        '<line x1="310" y1="' + base + '" x2="' + (310 + dx).toFixed(1) +
        '" y2="' + (base + dy).toFixed(1) + '" stroke="#39d3d8" stroke-width="2"/>' +
        /* the other two of the four, foreshortened, so it reads as a cone */
        '<line x1="310" y1="' + base + '" x2="' + (310 - dx * 0.45).toFixed(1) +
        '" y2="' + (base + dy * 0.72).toFixed(1) +
        '" stroke="#39d3d8" stroke-width="1.2" opacity="0.65"/>' +
        '<line x1="310" y1="' + base + '" x2="' + (310 + dx * 0.45).toFixed(1) +
        '" y2="' + (base + dy * 0.72).toFixed(1) +
        '" stroke="#39d3d8" stroke-width="1.2" opacity="0.65"/>' +
        '<circle cx="310" cy="' + base + '" r="4" fill="#58a6ff"/>' +
        lbl(300, base - 8, 'feed', 'end') +
        lbl(310 + dx + 12, base + dy, dr.toFixed(0) + '\u00b0 radials', 'start');
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
 'an-k', 'an-cond', 'an-droop', 'an-radials', 'an-nvis', 'an-head']
  .forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(el.type === 'checkbox' ? 'change' : 'input', () => {
      if (id === 'an-cond') {
        COND = CONDUCTORS.find(c => c.key === el.value) || COND;
        showConductor();
      }
      antennaFields(document.getElementById('an-type').value);
      calcAnt();
    });
  });

/* The same pipe is a different antenna at 14 MHz and at 146, so the list is
   re-costed whenever the frequency moves. */
(function () {
  const freq = document.getElementById('an-f');
  if (!freq) return;
  let pending = null;
  const refresh = () => {
    clearTimeout(pending);
    pending = setTimeout(() => loadConductors(num('an-f')).then(calcAnt), 250);
  };
  freq.addEventListener('input', refresh);
  loadConductors(num('an-f')).then(calcAnt);
})();

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
  if (locBtn) {
    locationAvailable().then(ok => { if (ok) locBtn.hidden = false; });
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

/* ---------- what to put up, and how ----------

   The calculator answers "how long is a dipole for 14.2 MHz", which is the
   easy half of the question a new licensee is actually asking. This asks the
   other half - what should I put up, how high, which way round - and then sets
   the calculator to that answer so the dimensions come out of it.

   Reached from the band plan: clicking a segment there arrives here with the
   frequency and the intended use already in the address. */

async function antennaAdvice(mhz, use, kind) {
  const box = document.getElementById('an-advice');
  if (!box) return;
  let d;
  try {
    d = await api('/api/antenna-advice?' + new URLSearchParams(
      Object.entries({mhz: mhz, use: use || '', kind: kind || ''})
        .filter(([, v]) => v !== '')));
  } catch (e) { return; }

  /* Set the calculator to the recommendation, so the dimensions below are the
     dimensions of the thing being recommended rather than of whatever was
     there before. */
  document.getElementById('an-type').value = d.type;
  document.getElementById('an-f').value = d.mhz;
  const h = document.getElementById('an-h');
  if (h) h.value = d.height_ft;
  const nvis = document.getElementById('an-nvis');
  if (nvis) nvis.checked = !!d.nvis;
  const useSel = document.getElementById('an-use');
  if (useSel) useSel.value = d.use;
  antennaFields(d.type);
  calcAnt();

  box.hidden = false;
  /* Say what the frequency is before saying what to build for it. Guessing
     from the band alone once produced "146.52, so you must want repeaters",
     which is wrong twice over: it is the national simplex calling channel, and
     a repeater there would be a faux pas. */
  const ctx = d.context;
  const said = ctx
    ? '<div class="advice-ctx"><b>' + d.mhz + ' MHz</b> is ' +
      (ctx.point ? '' : 'in ') + escapeHTML(ctx.label) + ' on ' +
      escapeHTML(ctx.band) + '. Taking it that you want <b>' +
      escapeHTML(d.use_label.toLowerCase()) + '</b> &mdash; change that below ' +
      'if not.</div>'
    : '<div class="advice-ctx">' + d.mhz + ' MHz is not in a US amateur band, ' +
      'so this assumes <b>' + escapeHTML(d.use_label.toLowerCase()) + '</b>.</div>';

  box.innerHTML =
    '<div class="advice-head">' +
      '<b>' + escapeHTML(d.title) + '</b>' +
      '<span class="tiny muted">' + d.mhz + ' MHz &middot; ' +
        escapeHTML(d.use_label) + ' &middot; wavelength ' + d.wavelength_ft +
        ' ft</span>' +
    '</div>' + said +
    '<div class="grid cols-2" style="gap:.9rem;margin-top:.5rem">' +
      '<div>' + d.why.map(w => '<p class="small">' + escapeHTML(w) + '</p>').join('') +
        '<p class="small"><b>Height to aim for: ' + d.height_ft + ' ft.</b> ' +
        escapeHTML(d.feedline) + '</p></div>' +
      '<div><div class="panel-title">What usually goes wrong</div>' +
        '<ul class="facts small">' +
        d.watch.map(w => '<li>' + escapeHTML(w) + '</li>').join('') + '</ul>' +
        (d.alternative ? '<p class="small muted"><b>Instead:</b> ' +
          escapeHTML(d.alternative) + '</p>' : '') +
      '</div>' +
    '</div>' +
    '<p class="tiny muted" style="margin:.5rem 0 0">A starting point, not a ' +
      'rule &mdash; good enough to make contacts with, which is what you need ' +
      'before you have the experience to disagree with it. The dimensions ' +
      'below are now set to it.</p>';
}

const adviseBtn = document.getElementById('an-advise');
if (adviseBtn) adviseBtn.addEventListener('click', () =>
  antennaAdvice(num('an-f'), document.getElementById('an-use').value));

/* Arriving from the band plan with a frequency in hand. */
(function () {
  const q = new URLSearchParams(location.search);
  const f = q.get('f');
  if (!f) return;
  selectTab('ant');
  history.replaceState(null, '', location.pathname + '#ant');
  antennaAdvice(f, q.get('use'), q.get('kind'));
})();

/* ---------------------------------------------------------- Smith chart ---
   Drawn rather than described, because the chart is a transformation and the
   only thing that teaches a transformation is watching it happen. The grid is
   geometry: a constant-resistance circle of r sits at x = r/(1+r) with radius
   1/(1+r), and a constant-reactance arc of x is centred a unit to the right of
   the rim at height 1/x with radius 1/|x|, trimmed to the unit circle. */

const SM_R = 250, SM_CX = 285, SM_CY = 275;      // chart radius and centre, px
const SM_RES = [0.2, 0.5, 1, 2, 5];
const SM_REACT = [0.2, 0.5, 1, 2, 5];

function smXY(x, y) {          // reflection coefficient -> pixels
  return [SM_CX + x * SM_R, SM_CY - y * SM_R];
}

function smithGrid(z0) {
  const g = [];
  g.push('<clipPath id="sm-clip"><circle cx="' + SM_CX + '" cy="' + SM_CY +
         '" r="' + SM_R + '"/></clipPath>');
  g.push('<circle cx="' + SM_CX + '" cy="' + SM_CY + '" r="' + SM_R +
         '" fill="#0c1116" stroke="#4a5663" stroke-width="1.2"/>');
  g.push('<g clip-path="url(#sm-clip)" fill="none" stroke="#2f3a46" stroke-width="0.8">');
  SM_RES.forEach(r => {
    const rad = SM_R / (1 + r), cx = SM_CX + SM_R * (r / (1 + r));
    g.push('<circle cx="' + cx.toFixed(1) + '" cy="' + SM_CY + '" r="' +
           rad.toFixed(1) + '"' + (r === 1 ? ' stroke="#46525f"' : '') + '/>');
  });
  SM_REACT.forEach(x => {
    [1, -1].forEach(sign => {
      const rad = SM_R / x;
      const cy = SM_CY - sign * rad;
      g.push('<circle cx="' + (SM_CX + SM_R) + '" cy="' + cy.toFixed(1) +
             '" r="' + rad.toFixed(1) + '"/>');
    });
  });
  g.push('</g>');
  g.push('<line x1="' + (SM_CX - SM_R) + '" y1="' + SM_CY + '" x2="' +
         (SM_CX + SM_R) + '" y2="' + SM_CY + '" stroke="#46525f" stroke-width="1"/>');
  /* The three landmarks worth knowing by sight. */
  /* The resistance circles get their value in ohms, not just normalised: "0.5"
     means nothing to somebody learning, and "25 Ω" means everything. Where the
     circle crosses the axis, r maps to (r-1)/(r+1) on the chart. */
  if (z0) {
    SM_RES.concat([0]).forEach(r => {
      const at = (r - 1) / (r + 1);
      const [tx] = smXY(at, 0);
      g.push('<line x1="' + tx.toFixed(1) + '" y1="' + (SM_CY - 3) + '" x2="' +
             tx.toFixed(1) + '" y2="' + (SM_CY + 3) + '" stroke="#6b7784"/>');
      g.push('<text x="' + tx.toFixed(1) + '" y="' + (SM_CY + 15) +
             '" fill="#8b98a5" font-size="9" text-anchor="middle">' +
             Math.round(r * z0) + '&#937;</text>');
    });
  }
  g.push('<text x="' + (SM_CX - SM_R + 4) + '" y="' + (SM_CY - 9) +
         '" fill="#8b98a5" font-size="10">short</text>');
  g.push('<text x="' + (SM_CX + SM_R - 4) + '" y="' + (SM_CY - 9) +
         '" fill="#8b98a5" font-size="10" text-anchor="end">open</text>');
  g.push('<text x="' + SM_CX + '" y="' + (SM_CY - 9) +
         '" fill="#3fb950" font-size="10" text-anchor="middle">match</text>');
  g.push('<text x="' + (SM_CX + 6) + '" y="' + (SM_CY - SM_R + 16) +
         '" fill="#8b98a5" font-size="10">+jX inductive</text>');
  g.push('<text x="' + (SM_CX + 6) + '" y="' + (SM_CY + SM_R - 8) +
         '" fill="#8b98a5" font-size="10">&minus;jX capacitive</text>');
  return g.join('');
}

function smithPlot(d) {
  const g = [smithGrid(d.z0)];
  const mag = d.load.gamma_mag;
  /* The constant-SWR circle: where a lossless line would keep you. */
  if (mag > 0.001) {
    g.push('<circle cx="' + SM_CX + '" cy="' + SM_CY + '" r="' +
           (mag * SM_R).toFixed(1) + '" fill="none" stroke="#ffb454" ' +
           'stroke-width="1" stroke-dasharray="4 3" opacity="0.75"/>');
  }
  /* The walk down the feedline, spiralling in as the line takes its cut. */
  const pts = d.path.map(p => smXY(p.x, p.y).map(n => n.toFixed(1)).join(',')).join(' ');
  g.push('<polyline points="' + pts + '" fill="none" stroke="#58a6ff" ' +
         'stroke-width="2" opacity="0.9"/>');
  const [lx, ly] = smXY(d.load.x, d.load.y);
  const [sx, sy] = smXY(d.shack.x, d.shack.y);
  g.push('<circle cx="' + lx.toFixed(1) + '" cy="' + ly.toFixed(1) +
         '" r="5.5" fill="#f85149" stroke="#0d1117" stroke-width="1.5"/>');
  g.push('<text x="' + (lx + 9).toFixed(1) + '" y="' + (ly - 7).toFixed(1) +
         '" fill="#f85149" font-size="11">antenna</text>');
  g.push('<circle cx="' + sx.toFixed(1) + '" cy="' + sy.toFixed(1) +
         '" r="5.5" fill="#3fb950" stroke="#0d1117" stroke-width="1.5"/>');
  g.push('<text x="' + (sx + 9).toFixed(1) + '" y="' + (sy + 15).toFixed(1) +
         '" fill="#3fb950" font-size="11">shack</text>');
  return '<svg viewBox="0 0 580 560" style="width:100%;max-width:580px">' +
         g.join('') + '</svg>';
}

function smithNotes(d) {
  const turns = d.electrical_wavelengths;
  const out = [];
  const z = (o) => o.r.toFixed(1) + (o.x >= 0 ? ' + j' : ' − j') +
                   Math.abs(o.x).toFixed(1) + ' Ω';
  out.push('<p class="small"><b>At the antenna</b> the feedpoint is ' + z(d.load) +
    '. Divided by the line\'s ' + d.z0 + '&nbsp;&#937; that is ' +
    (d.load.r / d.z0).toFixed(2) + (d.load.x >= 0 ? ' + j' : ' − j') +
    Math.abs(d.load.x / d.z0).toFixed(2) + ', which is the red dot. SWR there is <b>' +
    (d.load.swr === null ? '∞' : d.load.swr.toFixed(2)) + ':1</b>.</p>');

  out.push('<p class="small"><b>Down the line</b> you travel ' + turns.toFixed(3) +
    ' wavelengths, which is ' + (turns * 2).toFixed(2) + ' turns around the chart. ' +
    'A full turn is <b>half</b> a wavelength, not a whole one &mdash; the chart ' +
    'repeats every 180&deg; of line, and that is the fact that catches everybody ' +
    'out. The shack sees ' + z(d.shack) + '.</p>');

  if (d.loss.matched_db > 0.05) {
    const flatter = d.shack.swr !== null && d.load.swr !== null &&
                    d.shack.swr < d.load.swr - 0.05;
    out.push('<p class="small"><b>The spiral is the loss.</b> ' +
      d.loss.matched_db.toFixed(2) + ' dB of it matched, ' +
      d.loss.total_db.toFixed(2) + ' dB with this mismatch &mdash; so of ' +
      d.loss.power_in + ' W in, <b>' + d.loss.power_at_antenna +
      ' W</b> reaches the antenna.' +
      (flatter
        ? ' Notice the shack SWR (<b>' + d.shack.swr.toFixed(2) + ':1</b>) is ' +
          'lower than the antenna\'s (' + d.load.swr.toFixed(2) + ':1). That is ' +
          'not an improvement. The reflected wave has to travel the lossy line ' +
          'twice, so the meter in the shack sees less of it &mdash; a bad ' +
          'feedline flatters the SWR meter by wasting the power it is not ' +
          'showing you.'
        : '') + '</p>');
  }
  const near = Math.abs(d.shack.x) < 8 && Math.abs(d.shack.r - d.z0) < 12;
  if (near) {
    out.push('<p class="small" style="color:var(--green)">At this length the ' +
      'line has brought the shack end close to the centre. The antenna has not ' +
      'changed &mdash; the line has transformed it. This is what a matching ' +
      'section does, and why feedline length matters when the antenna is not ' +
      'resonant.</p>');
  }
  return out.join('');
}

async function calcSmith() {
  const box = document.getElementById('sm-out');
  if (!box) return;
  const q = new URLSearchParams({
    r: num('sm-r'), x: num('sm-x'), mhz: num('sm-f'),
    line: document.getElementById('sm-line').value,
    feet: num('sm-len'), watts: num('sm-w'),
  });
  document.getElementById('sm-len-v').textContent = num('sm-len') + ' ft';
  let d;
  try { d = await api('/api/smith?' + q); } catch (e) { return; }
  document.getElementById('sm-chart').innerHTML = smithPlot(d);
  box.innerHTML =
    '<div class="row" style="gap:1.1rem;flex-wrap:wrap">' +
      '<span>SWR at the antenna <b>' +
        (d.load.swr === null ? '∞' : d.load.swr.toFixed(2)) + ':1</b></span>' +
      '<span>at the shack <b>' +
        (d.shack.swr === null ? '∞' : d.shack.swr.toFixed(2)) + ':1</b></span>' +
      '<span>line loss <b>' + d.loss.total_db.toFixed(2) + ' dB</b></span>' +
      '<span>reaching the antenna <b>' + d.loss.power_at_antenna + ' W</b></span>' +
      '<span class="tiny muted">' + d.wavelength_ft + ' ft per wavelength in this line</span>' +
    '</div>' + '<div class="mt">' + smithNotes(d) + '</div>';
}

if (document.getElementById('sm-chart')) {
  const sel = document.getElementById('sm-line');
  [['rg58', 'RG-58 — thin, common, lossy'], ['rg8x', 'RG-8X — mini-8'],
   ['rg213', 'RG-213 — full size'], ['lmr400', 'LMR-400 — low loss'],
   ['rg6', 'RG-6 — 75 Ω TV coax'], ['ladder', '450 Ω window line']]
    .forEach(([v, l]) => sel.insertAdjacentHTML('beforeend',
      '<option value="' + v + '"' + (v === 'rg213' ? ' selected' : '') + '>' + l + '</option>'));
  ['sm-r', 'sm-x', 'sm-f', 'sm-len', 'sm-w', 'sm-line'].forEach(id => {
    const el = document.getElementById(id);
    el.addEventListener('input', calcSmith);
    el.addEventListener('change', calcSmith);
  });
  document.querySelectorAll('[data-preset]').forEach(b =>
    b.addEventListener('click', () => {
      const [r, x] = b.dataset.preset.split(',');
      document.getElementById('sm-r').value = r;
      document.getElementById('sm-x').value = x;
      calcSmith();
    }));
  const fromAnt = document.getElementById('sm-from-ant');
  if (fromAnt) fromAnt.addEventListener('click', () => {
    const a = window.LAB_ANTENNA;
    if (!a) { toast('Design one first', 'Build an antenna in the Antennas tab'); return; }
    document.getElementById('sm-r').value = a.z || 50;
    document.getElementById('sm-x').value = 0;
    document.getElementById('sm-f').value = a.f;
    calcSmith();
    toast('Carried over', a.label + ' at ' + a.f + ' MHz');
  });
  calcSmith();
}

/* ---------- where the energy goes, and how much band you get ----------

   The two questions a gain figure does not answer, and the two that decide
   whether an antenna suits what you want. Both are computed rather than
   sketched: the elevation pattern from the ground reflection that height
   creates, the SWR curve from the antenna's Q. */

function polarPlot(points, opts) {
  const R = 118, cx = 140, cy = 138;
  const pts = points.map(p => {
    const rad = (p.deg / 180) * Math.PI;
    const r = R * p.field;
    return [(cx + r * Math.cos(rad)).toFixed(1),
            (cy - r * Math.sin(rad)).toFixed(1)].join(',');
  }).join(' ');
  const rings = [0.25, 0.5, 0.75, 1].map(f =>
    '<circle cx="' + cx + '" cy="' + cy + '" r="' + (R * f).toFixed(1) +
    '" fill="none" stroke="#2a3441"/>').join('');
  const spokes = [0, 15, 30, 45, 60, 75, 90].map(d => {
    const rad = (d / 180) * Math.PI;
    return '<line x1="' + cx + '" y1="' + cy + '" x2="' +
      (cx + R * Math.cos(rad)).toFixed(1) + '" y2="' +
      (cy - R * Math.sin(rad)).toFixed(1) + '" stroke="#222c36"/>' +
      '<text x="' + (cx + (R + 12) * Math.cos(rad)).toFixed(1) + '" y="' +
      (cy - (R + 12) * Math.sin(rad) + 4).toFixed(1) +
      '" fill="#626e7b" font-size="9" text-anchor="middle">' + d + '&#176;</text>';
  }).join('');
  return '<svg viewBox="0 0 290 165" style="width:100%;max-width:290px">' +
    rings + spokes +
    '<line x1="' + (cx - R - 6) + '" y1="' + cy + '" x2="' + (cx + R + 6) +
      '" y2="' + cy + '" stroke="#8b98a5"/>' +
    '<polygon points="' + cx + ',' + cy + ' ' + pts + '" fill="rgba(63,185,80,.22)" ' +
      'stroke="#3fb950" stroke-width="1.6"/>' +
    (opts && opts.mark !== undefined
      ? '<line x1="' + cx + '" y1="' + cy + '" x2="' +
        (cx + R * Math.cos(opts.mark / 180 * Math.PI)).toFixed(1) + '" y2="' +
        (cy - R * Math.sin(opts.mark / 180 * Math.PI)).toFixed(1) +
        '" stroke="#ffb454" stroke-width="1.4" stroke-dasharray="4 3"/>' : '') +
    '</svg>';
}

function swrPlot(curve, band) {
  const W = 300, H = 150, pad = 26;
  const lo = curve[0].mhz, hi = curve[curve.length - 1].mhz;
  const xs = f => pad + (f - lo) / (hi - lo) * (W - pad - 8);
  const ys = s => H - 20 - (Math.min(s, 5) - 1) / 4 * (H - 40);
  const line = curve.map(p => xs(p.mhz).toFixed(1) + ',' + ys(p.swr).toFixed(1)).join(' ');
  const two = ys(2);
  const shade = (band.low && band.high)
    ? '<rect x="' + xs(band.low).toFixed(1) + '" y="' + ys(5).toFixed(1) +
      '" width="' + (xs(band.high) - xs(band.low)).toFixed(1) + '" height="' +
      (ys(1) - ys(5)).toFixed(1) + '" fill="rgba(63,185,80,.13)"/>' : '';
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;max-width:300px">' +
    shade +
    '<line x1="' + pad + '" y1="' + two + '" x2="' + (W - 8) + '" y2="' + two +
      '" stroke="#ffb454" stroke-dasharray="4 3"/>' +
    '<text x="' + (pad + 3) + '" y="' + (two - 4) + '" fill="#ffb454" font-size="9">2:1</text>' +
    '<polyline points="' + line + '" fill="none" stroke="#58a6ff" stroke-width="2"/>' +
    '<line x1="' + pad + '" y1="' + (H - 20) + '" x2="' + (W - 8) + '" y2="' + (H - 20) +
      '" stroke="#8b98a5"/>' +
    '<text x="' + pad + '" y="' + (H - 7) + '" fill="#626e7b" font-size="9">' +
      lo.toFixed(1) + '</text>' +
    '<text x="' + (W - 8) + '" y="' + (H - 7) + '" fill="#626e7b" font-size="9" ' +
      'text-anchor="end">' + hi.toFixed(1) + ' MHz</text>' +
    '</svg>';
}

async function drawPattern(type, mhz, heightFt, heading, slope, effHeight) {
  const box = document.getElementById('an-pattern');
  if (!box) return;
  let d;
  try {
    const nvisOn = (document.getElementById('an-nvis') || {}).checked ? 1 : 0;
    d = await api('/api/pattern?' + new URLSearchParams(
      {type: type, mhz: mhz, height: (effHeight || heightFt || 0),
       heading: heading || 0, nvis: nvisOn, slope: slope || 0,
       conductor: (COND && COND.key) || 'wire14'}));
  } catch (e) { box.innerHTML = ''; return; }
  const b = d.bandwidth;
  box.innerHTML =
    '<div class="grid cols-3" style="gap:1rem">' +
      '<div><div class="panel-title">Looking down on it</div>' +
        planPlot(d) + planWords(d) + '</div>' +
      '<div><div class="panel-title">Elevation pattern' +
        (d.shape === 'vertical' ? '' : ' at ' + d.height_wl + ' wavelengths up') +
        '</div>' + polarPlot(d.elevation, {mark: d.main_lobe_deg}) +
        '<p class="tiny muted">Strongest at <b>' + d.main_lobe_deg +
        '&deg;</b> above the horizon. ' +
        (d.shape === 'vertical'
          ? 'A vertical has no null at the horizon, which is why it works for DX from a small plot.'
          : 'Height sets this, not the antenna: the ground reflection interferes with the direct wave, and where they add is where you radiate. Perfect ground assumed &mdash; real earth fills the deepest nulls and takes a degree or two off the bottom.') +
        '</p></div>' +
      '<div><div class="panel-title">SWR across the band</div>' +
        swrPlot(d.swr, b) +
        '<p class="tiny muted"><b>' + (b.khz ? b.khz + ' kHz' : 'nothing') +
        '</b> under 2:1' + (b.khz ? ' (' + b.percent + '% of the frequency)' : '') +
        '. Q about ' + d.q + ' &mdash; ' + escapeHTML(d.fed) + '.</p></div>' +
    '</div>' +
    /* Full width, below the three plots: six columns of repeater do not fit in
       a third of a page, and a table you have to scroll sideways to read the
       bearing of is a table that failed at its one job. */
    positionNote(d) + repeaterList(d);
}

/* ---------- the plan view ----------
   The elevation pattern argues about height; this one argues about which way
   round you hang it, which is the cheaper mistake to fix and the more common
   one to make. A dipole strung along the fence radiates across the fence, and
   if the fence points at the house then so does the antenna. */

/* Say so when the answers are about where the GPS says the station is rather
   than where somebody told ELMER they live. In a vehicle those are different
   places, and which one the figures came from is the whole answer. */
function positionNote(d) {
  if (d.qth_source !== 'gps') return '';
  const age = d.qth_age_s;
  return '<p class="tiny muted">Position from GPS &mdash; <b>' +
    escapeHTML(d.qth || '') + '</b>, read ' +
    (!(age > 90) ? 'just now' : Math.round(age / 60) + ' min ago') +
    '. These figures are about here, not about the QTH on file.</p>';
}

/* Break a place name into at most two lines at a word boundary, as evenly as
   the words allow. One word long is left alone: there is nowhere to break it,
   and half a word is worse than a wide one. */
function wrapName(name, limit) {
  limit = limit || 10;
  const words = String(name).split(' ');
  if (name.length <= limit || words.length < 2) return [name];
  let best = 1, bestCost = Infinity;
  for (let n = 1; n < words.length; n++) {
    const a = words.slice(0, n).join(' ').length;
    const b = words.slice(n).join(' ').length;
    const cost = Math.max(a, b) * 2 + Math.abs(a - b);
    if (cost < bestCost) { bestCost = cost; best = n; }
  }
  return [words.slice(0, best).join(' '), words.slice(best).join(' ')];
}

function planPlot(d) {
  /* Room around the rim for the place names: they sit outside the circle, and
     at the top and bottom they need more than the radius plus a whisker. */
  const R = 96, cx = 160, cy = 148;
  const at = (bearing, r) => [
    (cx + r * Math.sin(bearing * Math.PI / 180)).toFixed(1),
    (cy - r * Math.cos(bearing * Math.PI / 180)).toFixed(1)];
  const g = [];
  [0.33, 0.66, 1].forEach(f => g.push('<circle cx="' + cx + '" cy="' + cy +
    '" r="' + (R * f).toFixed(1) + '" fill="none" stroke="#2a3441"/>'));
  /* Compass letters inside the rim, place names outside it, so the two rings
     of text cannot land on each other. */
  ['N', 'E', 'S', 'W'].forEach((c, i) => {
    const [x, y] = at(i * 90, R - 11);
    g.push('<text x="' + x + '" y="' + (+y + 4) + '" fill="#8b98a5" font-size="10" ' +
           'text-anchor="middle">' + c + '</text>');
  });
  /* The pattern itself, as laid. */
  const pts = d.azimuth.map(p => at(p.bearing, R * p.field).join(',')).join(' ');
  g.push('<polygon points="' + pts + '" fill="rgba(63,185,80,.22)" ' +
         'stroke="#3fb950" stroke-width="1.6"/>');
  /* The antenna drawn on top, so the shape and the hardware line up. */
  if (d.shape !== 'vertical') {
    if (d.type === 'yagi') {
      const [hx, hy] = at(d.heading, R * 0.92);
      g.push('<line x1="' + cx + '" y1="' + cy + '" x2="' + hx + '" y2="' + hy +
             '" stroke="#ffb454" stroke-width="2.5"/>');
    } else {
      const [ax, ay] = at(d.heading, R * 0.8), [bx, by] = at(d.heading + 180, R * 0.8);
      g.push('<line x1="' + ax + '" y1="' + ay + '" x2="' + bx + '" y2="' + by +
             '" stroke="#ffb454" stroke-width="2.5"/>');
    }
  } else {
    g.push('<circle cx="' + cx + '" cy="' + cy + '" r="4" fill="#ffb454"/>');
  }
  /* The edge of what this antenna reaches, where that is a distance at all. */
  if (d.reach && d.reach.inner_km) {
    /* The hole in the middle of a DX ring is the whole surprise: a high wire
       cannot work the next county. Drawn as a dashed circle so it reads as a
       boundary rather than as coverage. */
    const rin = R * Math.min(1, d.reach.inner_km / d.reach.outer_km);
    g.push('<circle cx="' + cx + '" cy="' + cy + '" r="' + rin.toFixed(1) +
           '" fill="none" stroke="#f85149" stroke-width="1" stroke-dasharray="4 4"/>');
    g.push('<text x="' + cx + '" y="' + (cy - rin - 4).toFixed(1) +
           '" fill="#f85149" font-size="8" text-anchor="middle">skip zone</text>');
  }
  if (d.reach && d.reach.radius_km) {
    g.push('<text x="' + cx + '" y="' + (cy + R + 42) +
           '" fill="#626e7b" font-size="9" text-anchor="middle">reach about ' +
           Math.round(d.reach.radius_km * 0.6214) + ' miles</text>');
  }
  /* Real places, at their real bearings. Every one gets its spoke; the names
     are thinned where two sit close together, because four labels on top of
     each other is less use than three and a gap. */
  let lastLabel = -999;
  /* Where distance is known, plot it: a spoke that stops where the town
     actually is turns a bearing chart into a map, and it is what makes the
     skip-zone circle mean something rather than decorate something. */
  const scaleKm = (d.reach && d.reach.outer_km) || (d.reach && d.reach.radius_km) || 0;
  (d.dx || []).forEach(t => {
    const frac = (scaleKm && t.km) ? Math.min(1, t.km / scaleKm) : 1;
    const [x, y] = at(t.bearing, R * frac);
    const weak = t.db !== undefined && t.db < -6;
    g.push('<line x1="' + cx + '" y1="' + cy + '" x2="' + x + '" y2="' + y +
           '" stroke="' + (weak ? '#f85149' : '#39d3d8') + '" stroke-width="0.7" ' +
           'opacity="0.55"/>');
    g.push('<circle cx="' + x + '" cy="' + y + '" r="2.2" fill="' +
           (weak ? '#f85149' : '#39d3d8') + '"/>');
    if (t.bearing - lastLabel < 16) return;
    lastLabel = t.bearing;
    const [lx, ly] = at(t.bearing, R + 16);
    /* Wrap rather than cut. "Grand Forks" trimmed to "Grand" and "Saint Cloud"
       to "Saint" are not names of anywhere, and the compass exists to be read
       at a glance. Two short lines read; one clipped word does not. */
    const lines = wrapName(t.name);
    const dy = -(lines.length - 1) * 4.5;
    g.push('<text x="' + lx + '" y="' + (+ly + 3 + dy) + '" fill="' +
           (weak ? '#f85149' : '#8b98a5') + '" font-size="8" text-anchor="middle">' +
           lines.map((line, n) => '<tspan x="' + lx + '" dy="' + (n ? 9 : 0) +
                     '">' + escapeHTML(line) + '</tspan>').join('') +
           '</text>');
  });
  return '<svg viewBox="0 0 320 300" style="width:100%;max-width:320px">' +
         g.join('') + '</svg>';
}

function planWords(d) {
  if (d.shape === 'vertical') {
    return '<p class="tiny muted">The same in every direction, so there is no ' +
      'wrong way to face it. That is what omnidirectional buys you, and what ' +
      'it costs: no gain anywhere, because there is no direction to take it ' +
      'from.</p>';
  }
  const best = d.type === 'yagi'
    ? [d.heading]
    : [(d.heading + 90) % 360, (d.heading + 270) % 360];
  const nulls = d.type === 'yagi'
    ? [(d.heading + 180) % 360]
    : [d.heading % 360, (d.heading + 180) % 360];
  const say = a => a.map(b => Math.round(b) + '&deg; ' + compass(b)).join(' and ');
  let html = '<p class="tiny muted">Strongest toward <b>' + say(best) +
    '</b>, deaf toward <b>' + say(nulls) + '</b>. ' +
    (d.type === 'yagi'
      ? 'Turn the boom and the whole pattern turns with it.'
      : 'A wire radiates across itself, not along itself &mdash; so the ' +
        'direction it is strung decides the direction it hears.') + '</p>';
  if (d.reach && d.reach.note) {
    html += '<p class="tiny muted">' + escapeHTML(d.reach.note) + '</p>';
  }
  /* Two answers, labelled, because they are not the same answer. The geometry
     is what this program can compute; the day is what decides whether any of
     it happens. Running them together as one paragraph is how a calculation
     gets mistaken for a promise. */
  if (d.reach && d.reach.lab) {
    html += '<p class="tiny muted"><b>On paper:</b> ' + escapeHTML(d.reach.lab) +
      '<br><b>In practice:</b> ' + escapeHTML(d.reach.real) + '</p>';
  }
  /* An empty compass is a real answer and a discouraging one, and the
     discouragement is misplaced: it means this combination is wrong, not that
     the operator is out of options. */
  if ((d.instead || []).length) {
    html += '<div class="instead"><p class="tiny"><b>Nothing in range with ' +
      'this setup.</b> That is a fixable problem, and rarely with the power ' +
      'knob:</p><ul class="tiny">';
    d.instead.forEach(a => {
      html += '<li><b>' + escapeHTML(a.do) + '.</b> ' + escapeHTML(a.why) + '</li>';
    });
    html += '</ul></div>';
  }

  /* Say where the names came from. A bundled answer is a guess at what is near
     you; a fetched one actually looked. */
  if (d.reach && d.reach.places_from === 'bundled' && (d.dx || []).length) {
    html += '<p class="tiny muted">Names from the list that ships with ELMER. ' +
      'Run <span class="mono">./elmer.py --fetch-places</span> once, with a ' +
      'network, and it will look up the towns actually around you &mdash; ' +
      'including the small ones no bundled list would carry.</p>';
  }
  const missed = (d.dx || []).filter(t => t.db < -6);
  const named = t => escapeHTML(t.region ? t.name + ', ' + t.region : t.name);
  if (missed.length) {
    html += '<p class="tiny" style="color:var(--red)">In the null from ' +
      escapeHTML(d.qth || 'here') + ': <b>' +
      missed.map(t => named(t) + ' (' + t.bearing + '&deg;, ' + t.db +
                 ' dB)').join(', ') + '</b>. Turning the antenna is free; the ' +
      'decibels are not.</p>';
  } else if ((d.dx || []).length) {
    html += '<p class="tiny" style="color:var(--green)">Nothing within reach ' +
      'is in the null at this orientation.</p>';
  } else if (d.reach && d.reach.kind === 'line_of_sight') {
    html += '<p class="tiny muted">Nothing in ELMER\'s list of towns is within ' +
      'line of sight of ' + escapeHTML(d.qth || 'here') + ', which is ordinary ' +
      'for VHF simplex &mdash; the repeater you are using is doing the reaching, ' +
      'not your antenna.</p>';
  } else if (d.reach && d.reach.radius_km) {
    /* The footprint is real even where the names are missing - an island, a
       thinly settled stretch, or anywhere outside the list's North American
       coverage. Say which of the two is missing. */
    html += '<p class="tiny muted">No towns in ELMER\'s list fall inside this ' +
      'footprint from ' + escapeHTML(d.qth || 'here') + '. The coverage is ' +
      'real; the names are what is missing, and the list is a few hundred ' +
      'North American cities rather than a gazetteer.</p>';
  }
  return html;
}

/* On FM the repeater is the antenna that matters, so name the ones in range.
   Nothing here claims a contact: it says where a machine is and how far, and
   marks the ones ELMER could only place to their county, because a bearing
   from a county centroid is a direction to a county. Terrain decides the rest,
   and terrain is not in a repeater list. */
function repeaterList(d) {
  const reps = d.repeaters || [];
  const cov = d.repeater_coverage;
  if (!reps.length) {
    /* An empty list means two very different things, and saying the wrong one
       is how a program loses somebody in a place they need it. Nothing on the
       air near you is a fact; nobody has ever looked here is an errand. */
    if (cov && !cov.known) {
      return '<p class="tiny" style="color:var(--amber)">' +
        (cov.nearest_km === null
          ? 'ELMER has no repeater list at all yet. '
          : 'ELMER knows no repeaters within ' + Math.round(cov.nearest_km * 0.6214) +
            ' miles of here &mdash; that is a gap in what it has been told, ' +
            'not a quiet band. ') +
        'TowerWitch can look this position up; ELMER reads what it writes. ' +
        'Do it while you have a signal, and the list keeps working after ' +
        'you lose one.</p>';
    }
    if (cov && cov.known) {
      return '<p class="tiny muted">No repeaters on this band within reach, ' +
        'though ELMER does know this area &mdash; the nearest it has is ' +
        Math.round(cov.nearest_km * 0.6214) + ' miles off.</p>';
    }
    return '';
  }
  const approx = reps.some(r => r.approx);
  let out = '<div class="rep-list"><p class="tiny"><b>Repeaters within about ' +
    Math.round((d.repeater_radius_km || 0) * 0.6214) + ' miles</b> ' +
    '<span class="muted">&mdash; a machine on a tower reaches much further ' +
    'than your antenna reaches another like it, which is the whole point of ' +
    'one.</span></p><table class="data rep-table"><tr>' +
    '<th>Output</th><th>Call</th><th>Where</th><th>Distance</th>' +
    '<th>Bearing</th><th>Tone</th></tr>';
  reps.forEach(r => {
    out += '<tr><td class="mono">' + r.output.toFixed(3) + '</td>' +
      '<td class="mono">' + escapeHTML(r.call) + '</td>' +
      '<td>' + escapeHTML(r.where || '') +
        (r.approx ? ' <span class="muted">~</span>' : '') + '</td>' +
      '<td>' + r.miles + ' mi</td>' +
      '<td>' + r.bearing + '&deg;' +
        (r.db !== undefined && r.db < -6
          ? ' <span style="color:var(--red)">' + r.db + ' dB</span>' : '') +
      '</td>' +
      '<td class="mono">' + (r.tone ? escapeHTML(String(r.tone)) : '&mdash;') +
      '</td></tr>';
  });
  out += '</table>';
  if (approx) {
    out += '<p class="tiny muted">~ placed to its county rather than its own ' +
      'site, so read that bearing as a direction to the county.</p>';
  }
  if (d.repeaters_from) {
    out += '<p class="tiny muted">List from ' + escapeHTML(d.repeaters_from) +
      '. Being in range on paper is not being in range: a hill between you ' +
      'and it wins every argument.</p>';
  }
  return out + '</div>';
}
