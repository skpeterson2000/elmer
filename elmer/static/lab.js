/* Lab: live calculators. Every formula here is one the pools ask about, so the
   wording of the outputs deliberately mirrors the exam vocabulary. */

/* ------------------------------------------------------------------ tabs */
/* Points of the compass. Declared here rather than beside the plan view that
   uses it: a const is hoisted but not initialised, and the antenna panel draws
   itself at page load - which put this in the temporal dead zone and threw. */
const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];

/* The sweep off the instrument, shared by the two panes that care: the VNA
   takes it and the Smith chart draws it. Declared here for the same reason
   COMPASS is - the Smith chart paints itself during this file's own
   evaluation, and a `let` further down is hoisted without being initialised,
   so reading it from up here threw and the chart quietly did not appear until
   somebody moved a control. On the Lab it is filled from the server, since
   the instrument is on another page now. */
let vnMeasured = null;
function compass(deg) {
  return COMPASS[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16];
}

/* Which bench this is. One script serves the Lab and Tools, and the tab each
   was left on is remembered separately: coming back to the Lab should reopen
   the Lab's tab, not whichever instrument was last looked at next door. */
const BENCH = 'tab.' + location.pathname;

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
    remember(BENCH, btn.dataset.tab);
  });
});

/* A concept note links here as /lab#skip, so honour the fragment on arrival -
   and otherwise reopen whatever was last being used, because coming back from
   the propagation page to a Lab that has forgotten which tool you had open is
   the same small waste as the band plan forgetting your band. */
function openFromHash() {
  const name = (location.hash || '').replace('#', '');
  if (name) {
    if (selectTab(name)) remember(BENCH, name);
    return;
  }
  const last = recall(BENCH);
  if (last) selectTab(last);
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

/* Where the sonde network was last read, and whether it was day where the
   operator is. Filled by the "use a real measurement" button; null until then,
   which is when the slider is a thought experiment rather than tonight. */
let skipWhen = null;

/* What a layer height means, which depends on the hour.
 *
 * The F2 layer sits around 270 km by day and 330 at night, so the same 245 km
 * is ordinary at noon and distinctly low at eleven in the evening. This used
 * to read the number alone and call anything under 250 "typical of a daytime
 * layer" whatever the clock said - which is how a real measurement taken at
 * half past ten at night came back labelled daytime.
 *
 * A measurement that disagrees with the hour is the interesting case rather
 * than an error, so it is named instead of smoothed over. */
function heightSays(h) {
  if (!skipWhen || skipWhen.day === null || skipWhen.day === undefined) {
    // No idea what time it is where they are: describe the height, and make
    // no claim about the hour.
    return h < 250 ? ' — low for an F2 layer'
         : h > 380 ? ' — high for an F2 layer' : '';
  }
  const typical = skipWhen.day ? (skipWhen.typicalDay || 270)
                               : (skipWhen.typicalNight || 330);
  const when = skipWhen.day ? 'by day' : 'after dark';
  const off = h - typical;
  if (Math.abs(off) <= 35) return ' — about usual ' + when;
  return (off < 0 ? ' — low for ' : ' — high for ') +
         (skipWhen.day ? 'a daytime layer' : 'a night layer') +
         ', which usually sits nearer ' + Math.round(typical) + ' km';
}

function drawSkip() {
  const f = num('s-f'), fof2 = num('s-fof2'), h = num('s-h');
  document.getElementById('s-f-v').textContent = f.toFixed(3) + ' MHz';
  document.getElementById('s-fof2-v').textContent = fof2.toFixed(1) + ' MHz';
  document.getElementById('s-h-v').textContent = h + ' km' + heightSays(h);

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
  // Keep what the reply says about the hour, so the height can be read
  // against what is usual now rather than against a fixed number.
  skipWhen = {day: data.day, sun: data.sun_deg,
              typicalDay: (data.typical_hmf2 || {}).day,
              typicalNight: (data.typical_hmf2 || {}).night};
  const height = Math.round(Math.max(150, Math.min(450, near.hmf2)));
  const critical = Math.max(2, Math.min(16, near.fof2));
  document.getElementById('s-h').value = height;
  document.getElementById('s-fof2').value = critical;
  drawSkip();

  /* This is one station's measurement of the sky above that station, and the
     sliders now hold it exactly. The propagation page shows a foF2 too, and it
     will not be quite this number: that one is the model corrected by every
     sonde in range and then evaluated at your own sun angle, which is the
     right number for your QTH. Saying so here is the difference between two
     figures that look like a bug and two that look like what they are. */
  const far = near.distance_km > 1500;
  note.innerHTML =
    '<b>' + escapeHTML(near.name) + '</b>, ' + near.distance_km + ' km away, ' +
    near.age_minutes + ' min old — hmF2 <b>' + near.hmf2 + ' km</b>, foF2 <b>' +
    near.fof2 + ' MHz</b>' +
    (near.m3000 ? ', M(3000)F2 <b>' + near.m3000.toFixed(2) + '</b>' : '') +
    (near.mufd ? ', so its own MUF(3000) is ' + near.mufd.toFixed(1) + ' MHz' : '') + '.' +
    (critical !== near.fof2
      ? '<br><span style="color:var(--amber)">The slider stops at ' + critical +
        ' MHz, so it is holding that rather than the ' + near.fof2 + ' measured.</span>'
      : '') +
    '<br>' + (far
      ? '<span style="color:var(--amber)">That is a long way off — it is the ionosphere ' +
        'over ' + escapeHTML(near.name.split(',')[0]) + ', not over you, and at this hour ' +
        'the sun is at a different angle there.</span> '
      : '') +
    'This is one station\'s measurement. The foF2 on the ' +
    '<a href="/propagation">band conditions page</a> is a different figure on purpose: ' +
    'the model corrected by every sonde in range, then read at <i>your</i> sun angle.' +
    '<br>Across the ' + sp.count + ' stations reporting now the peak sits between ' +
    sp.hmf2.low + ' and ' + sp.hmf2.high + ' km — that spread is mostly day against night' +
    (sp.m3000 ? ', and the median M(3000)F2 is ' + sp.m3000.toFixed(2) +
                ' — the factor that turns foF2 into MUF' : '') + '.';
  sondeBtn.disabled = false;
});

['s-f', 's-fof2', 's-h'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', drawSkip);
});

/* ------------------------------------------------- where in the bands */
/* The Lab has five places to type a frequency and until now no way of saying
   whether the number typed was in a band at all. The hop slider runs 1.8 to
   30 MHz and spends most of that travel between bands; it would model 12.0
   MHz as cheerfully as 14.074, and only one of those is a frequency anybody
   can use. So every frequency input gets a meter under it: which band it is
   in and what is at that spot, or - just as useful - that it is between bands
   and where the nearest edges are. In a band, the name is a link to the band
   plan opened on that band, so the two tools stop being strangers.

   Privileges are deliberately not here. Whether *you* may transmit there is
   the band plan's question and it answers it properly, with a class. */
let BANDS = [];
const bandMeters = [];

api('/api/bands').then(d => {
  BANDS = d.bands || [];
  bandMeters.forEach(m => m());
  paintBandChips();
}).catch(() => {});

function bandAt(mhz) {
  return BANDS.find(b => mhz >= b.low && mhz <= b.high) || null;
}

/* The narrowest activity segment covering a frequency: the plan overlaps
   on purpose - a calling frequency sits inside a wider segment - and the
   narrow one is the more useful answer. Mirrors bandplan.segment_at. */
function segmentAt(mhz, band) {
  let best = null;
  (band ? band.activity : []).forEach(([lo, hi, kind, label]) => {
    if (mhz >= lo - 1e-6 && mhz <= hi + 1e-6) {
      const width = hi - lo;
      if (!best || width < best.width) best = {lo, hi, kind, label, width};
    }
  });
  return best;
}

function edgesAround(mhz) {
  let below = null, above = null;
  BANDS.forEach(b => {
    if (b.high < mhz && (!below || b.high > below.high)) below = b;
    if (b.low > mhz && (!above || b.low < above.low)) above = b;
  });
  return {below, above};
}

function bandMeterHTML(mhz) {
  if (!BANDS.length || !(mhz > 0)) return '';
  const band = bandAt(mhz);
  if (band) {
    const seg = segmentAt(mhz, band);
    return '<i class="dot in"></i><a href="/bandplan#' + band.key + '" ' +
      'title="open the band plan on ' + escapeHTML(band.name) + '">' +
      escapeHTML(band.name) + '</a>' +
      (seg ? ' &middot; ' + escapeHTML(seg.label) : '') +
      (band.channelised ? ' &middot; channels only' : '');
  }
  const {below, above} = edgesAround(mhz);
  const parts = [];
  if (below) parts.push(escapeHTML(below.name) + ' ends at ' + below.high.toFixed(3));
  if (above) parts.push(escapeHTML(above.name) + ' starts at ' + above.low.toFixed(3));
  return '<i class="dot out"></i>not an amateur band' +
    (parts.length ? ' &mdash; ' + parts.join(', ') : '');
}

/* Fit a meter under an input. `scale` turns what is typed into MHz: the
   reactance pane works in kHz, everything else in MHz. */
function attachBandMeter(id, scale) {
  const el = document.getElementById(id);
  if (!el) return;
  const meter = document.createElement('div');
  meter.className = 'bandmeter';
  const field = el.closest('.field') || el.parentElement;
  field.appendChild(meter);
  const paint = () => {
    const mhz = parseFloat(el.value) * (scale || 1);
    meter.innerHTML = bandMeterHTML(mhz);
  };
  el.addEventListener('input', paint);
  el.addEventListener('change', paint);
  bandMeters.push(paint);
  paint();
}

attachBandMeter('s-f');
attachBandMeter('an-f');
attachBandMeter('sm-f');
attachBandMeter('p-f');
attachBandMeter('r-f', 0.001);          // kHz on that pane

/* ------------------------------------------------- the chips on the hop */
/* One chip per HF band. Pressing one puts the slider where that band opens:
   the last antenna you designed for it if there is one, because the point of
   the hand-off from the antenna page is to check *that* frequency against
   the sky, and otherwise the band's calling frequency, which is a place
   people actually are. The lit chip follows the slider, so dragging it
   through 12 MHz shows no chip lit - which is the meter saying the same thing
   a second way. */
function bandKeyOf(mhz) {
  const b = bandAt(mhz);
  return b ? b.key : null;
}

function paintBandChips() {
  const box = document.getElementById('s-bands');
  if (!box) return;
  const here = bandKeyOf(num('s-f'));
  box.innerHTML = BANDS.filter(b => b.group === 'HF').map(b =>
    '<button type="button" class="chip' + (b.key === here ? ' on' : '') +
    '" data-band="' + b.key + '" title="' +
    (recall('lab.antenna.' + b.key) ? 'your last antenna for this band'
      : b.calling ? escapeHTML(b.calling_label || '') + ' - ' + b.calling.toFixed(3) : '') +
    '">' + escapeHTML(b.name) + '</button>').join('');
}

document.addEventListener('click', e => {
  const chip = e.target.closest('#s-bands [data-band]');
  if (!chip) return;
  const band = BANDS.find(b => b.key === chip.dataset.band);
  if (!band) return;
  const remembered = recall('lab.antenna.' + band.key);
  const to = (remembered && remembered >= band.low && remembered <= band.high)
    ? remembered : (band.calling || (band.low + band.high) / 2);
  const slider = document.getElementById('s-f');
  slider.value = Math.max(parseFloat(slider.min), Math.min(parseFloat(slider.max), to));
  slider.dispatchEvent(new Event('input', {bubbles: true}));
});

const hopSlider = document.getElementById('s-f');
if (hopSlider) hopSlider.addEventListener('input', paintBandChips);

/* Sending an antenna to the hop simulator.

   The antenna page offers this and the link used to be a bare fragment: it
   changed tab and carried nothing, so the simulator went on showing whichever
   frequency the slider was left at. Worse, the sentence offering it says to
   check the frequency against foF2 - and the foF2 slider would still be at its
   default, so there was nothing real on either axis. Both ends now come
   across: the antenna's own frequency, and the ionosphere that is actually up
   there tonight. */
document.addEventListener('click', e => {
  const link = e.target.closest('[data-skip-f]');
  if (!link) return;
  e.preventDefault();
  const freq = document.getElementById('s-f');
  const wanted = parseFloat(link.dataset.skipF);
  if (freq && isFinite(wanted)) {
    freq.value = Math.max(parseFloat(freq.min),
                          Math.min(parseFloat(freq.max), wanted));
  }
  selectTab('skip');
  history.replaceState(null, '', location.pathname + '#skip');
  drawSkip();
  document.getElementById('pane-skip').scrollIntoView({block: 'start'});
  // Checking it against a default is not checking it against anything.
  const measure = document.getElementById('s-measure');
  if (measure && !measure.disabled) measure.click();
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

async function loadConductors(mhz, kind) {
  /* Narrowed to what this antenna is plausibly made of. Offering a coat hanger
     as the element of a commercial mobile whip is a question nobody is asking;
     what they want to know is what the thing in their hand is made of and what
     that costs them, which is a better question and has an answer. */
  try {
    const d = await api('/api/conductors?' + new URLSearchParams(
      kind ? {mhz: mhz, kind: kind} : {mhz: mhz}));
    CONDUCTORS = d.conductors;
  } catch (e) { return; }
  const sel = document.getElementById('an-cond');
  if (!sel) return;
  let chosen = sel.value || COND.key || 'wire14';
  if (!CONDUCTORS.some(c => c.key === chosen)) chosen = CONDUCTORS[0].key;
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
      '<a href="#skip" data-skip-f="' + f + '">Check it against foF2 in ' +
      'the hop simulator &rarr;</a></p>'
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

/* Whether the antenna in the selector was ELMER's suggestion or somebody's
   own choice. A suggestion follows the questions above it - change what you
   have to work with and the suggestion changes; a choice is a fact about
   somebody's plans and is left alone, the way a typed height is. */
let anTypeByHand = false;

function anSiteValue() {
  const v = (document.getElementById('an-site') || {}).value || '';
  return v === 'textbook' ? '' : v;      // "nothing in particular" imposes nothing
}

/* The questions have been answered enough to suggest from: what you have to
   work with is the one that matters, because it is the one that rules
   antennas out. "Nothing in particular" is an answer too. */
function anReadyToSuggest() {
  return !!(document.getElementById('an-site') || {}).value;
}

function suggestIfWanted() {
  if (anTypeByHand || !anReadyToSuggest()) return;
  antennaAdvice(num('an-f'), document.getElementById('an-use').value, '');
  const note = document.getElementById('an-type-note');
  if (note) {
    note.hidden = false;
    note.textContent = 'ELMER\u2019s suggestion for what you told it. Change it if you have something else in mind.';
  }
}

function calcAnt() {
  const type = document.getElementById('an-type').value;
  const f = num('an-f');
  if (!type) {
    // Nothing chosen and nothing suggested yet: say what to do, rather than
    // computing a dipole nobody asked about.
    out('an-out', anReadyToSuggest()
      ? 'Working out what suits that\u2026'
      : 'Start with what you have to work with. ELMER will suggest an antenna from that, and the numbers follow. Or pick one from the list.');
    ['an-pattern', 'an-plan', 'an-reach'].forEach(id => {
      const el = document.getElementById(id); if (el) el.innerHTML = '';
    });
    return;
  }
  // Remembered per band, so the hop simulator's chip for this band opens
  // on the frequency you actually built for rather than a calling frequency.
  if (f > 0 && typeof bandKeyOf === 'function') {
    const key = bandKeyOf(f);
    if (key) remember('lab.antenna.' + key, f);
  }
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
        /* The commonest real deployment of this antenna, and the one the Lab
           said nothing about: the slope slider is on screen for an end-fed and
           its value went nowhere.

           A sloping dipole's problem is balance. An end-fed has no balance to
           lose - it is unbalanced on both sides by construction - so what the
           slope changes is where the return current has to live, and the
           answer is: on the ground, right under the transformer. */
        if (num('an-slope') > 0) {
          notes.push('<b>Sloping it is the normal arrangement, not a ' +
            'compromise.</b> Transformer low, wire rising to a branch or a mast. ' +
            'Three things follow and all three are wanted. The high-voltage end ' +
            'finishes at the top, which is where it belongs and out of reach. The ' +
            'slope fills in the low angles a flat wire at this height throws ' +
            'away, which is how the same piece of wire stops being a regional ' +
            'antenna and starts being a DX one. And the feedpoint is now down on ' +
            'the ground &mdash; which is exactly where the return current is, so ' +
            'the counterpoise and the choke buy more here than another ten feet ' +
            'of height would. Tune it against the ground rather than trying to ' +
            'get clear of it: you are working against it either way, and the ' +
            'only question is whether you meant to.');
        }
    }
    // feedNote returns nothing for an end-fed - it has the longer
    // note above, and the slope paragraph now sits in there with it.
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

/* an-slope was missing from this list, so the slope slider was inert: it
   showed for an end-fed and a dipole, its value was read in four places, and
   nothing ever re-ran to use it. A control that does nothing is worse than no
   control - it tells somebody the program has considered their arrangement
   when it has not. */
['an-type', 'an-f', 'an-h', 'an-el', 'an-sp', 'an-wh', 'an-loss', 'an-hat',
 'an-k', 'an-cond', 'an-droop', 'an-radials', 'an-nvis', 'an-head', 'an-site',
 'an-slope', 'an-use', 'an-pw']
  .forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener(el.type === 'checkbox' ? 'change' : 'input', () => {
      if (id === 'an-cond') {
        COND = CONDUCTORS.find(c => c.key === el.value) || COND;
        showConductor();
      }
      // Typed here, so it is a measurement from now on and follows nothing.
      if (id === 'an-h') anHeightSuggested = false;
      antennaFields(document.getElementById('an-type').value);
      /* The advice panel sits above all this and only refreshed when the
         button was pressed, so changing the antenna underneath it left it
         describing whichever one you last asked about. That was harmless
         while the advice was generic and is wrong now that it follows the
         type. It refreshes itself, and deliberately does not touch the
         numbers you have typed - see antennaAdvice's `quiet`. */
      if (id === 'an-type') {
        // A hand on the selector makes it a choice. Back to "let ELMER
        // suggest one" hands it back.
        anTypeByHand = !!el.value;
        const note = document.getElementById('an-type-note');
        if (note && anTypeByHand) note.hidden = true;
        refreshAdvice();
        if (el.value) loadConductors(num('an-f'), el.value);
      }
      if (id === 'an-site') {
        // What you have to work with is a fact about you, not about this
        // visit: it is kept, and put back before any frequency handed in
        // from elsewhere is answered - or the band plan's "set up an antenna
        // for this" on 160 m was answered for nobody's garden at all.
        remember('lab.antenna.site', el.value);
      }
      if (id === 'an-pw') { refreshAdvice(); calcAnt(); return; }
      if (id === 'an-site' || id === 'an-use') {
        // The questions changed. A suggested antenna follows them; a chosen
        // one stays, and only the advice about it is refreshed.
        if (!anTypeByHand && anReadyToSuggest()) { suggestIfWanted(); return; }
        refreshAdvice();
      }
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
    pending = setTimeout(() => {
      loadConductors(num('an-f'),
                     (document.getElementById('an-type') || {}).value)
        .then(calcAnt);
      // The panel refreshed for the type and the site and not for the band,
      // so changing bands left it describing the last one while every figure
      // underneath described the new one.
      refreshAdvice();
    }, 250);
  };
  freq.addEventListener('input', refresh);
  loadConductors(num('an-f'), (document.getElementById('an-type') || {}).value).then(calcAnt);
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
function sendToRf() {
  const a = window.LAB_ANTENNA;
  if (!a) return;
  const near = exposurePrefill(a);
  const row = rfDefaultRow();
  row.frequency_mhz = a.f;
  // The watts typed on this page go with it. The exposure evaluation used to
  // open at its own default of 100 W whatever had been said here.
  if (num('an-pw') > 0) row.pep_watts = num('an-pw');
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

  /* The evaluation lives on Tools and the antennas live here, so the antenna
     has to survive a page load to reach it. Put down where the other bench
     will look, and picked up there once - a row left lying about would
     reappear in every evaluation somebody opened afterwards. */
  if (!document.getElementById('pane-rf')) {
    remember('rf.handoff', {row: row, said: {
      title: 'Sent from the Antennas tab',
      text: a.description + ' at ' + a.f + ' MHz — ' + near.why + '.',
      warn: near.warn}});
    location.href = '/tools#rf';
    return;
  }

  renderRfRows();
  selectTab('rf');
  history.replaceState(null, '', '#rf');
  rfEvaluate();
  toast('Sent to RF exposure',
        a.description + ' at ' + a.f + ' MHz — ' + near.why + '.');
  if (near.warn) setTimeout(() => toast('Worth knowing', near.warn, 9000), 600);
}
if (toRf) toRf.addEventListener('click', sendToRf);
document.addEventListener('click', e => {
  const link = e.target.closest('[data-rf-handoff]');
  if (!link) return;
  e.preventDefault();
  sendToRf();
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
        toast('Could not locate you',
              (e && e.message ? e.message + '. ' : '') +
              'Type a place name or grid square instead.');
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

/* first paint. Every one of these is guarded on something it needs, because
   this script serves two benches now and the panes are split between them:
   an initialiser that assumes its own pane is present throws on the page it
   is not, and a throw at the top level takes every pane after it down with
   it - which is how the analyser stopped drawing when the sextant moved. */
if (document.getElementById('pane-path')) initPathPlaces();
openFromHash();
if (document.getElementById('s-svg')) drawSkip();
if (document.getElementById('r-svg')) drawReact();
if (document.getElementById('an-type')) {
  antennaFields(document.getElementById('an-type').value);
  calcAnt();
}
if (document.getElementById('pane-swr')) calcSWR();
if (document.getElementById('pane-db')) calcDb();

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
   row is tuned, for the license class on the profile.

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
      escapeHTML(d.license_class) + ' licensee may not transmit on ' + mhz +
      ' MHz.</span> 47 CFR 97.301.';
  } else {
    html = '<b>' + escapeHTML(d.band) + '</b>, ' + escapeHTML(d.license_class) +
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

  /* The owl, where it is earned. This is a limit somebody can exceed with a
     person standing in the field, and a licence somebody can exceed with a
     transmitter - the two cases in this tool where a raised eyebrow is the
     correct response rather than a decoration. It is deliberately not on
     anything else here. */
  const stern = (!data.compliant || (data.privilege_warnings || []).length)
    ? '<img src="/static/owl-mind.png" alt="" class="stern-owl" ' +
      'title="worth stopping on">' : '';

  const overall = stern + (data.compliant
    ? '<span class="pill good">compliant at the distances entered</span>'
    : '<span class="pill bad">one or more positions exceed the limit</span>') +
    /* A green pill next to an operation the license does not allow would read
       as approval of the whole thing. It is not: this evaluates exposure. */
    ((data.privilege_warnings || []).length
      ? '<span class="pill bad">not permitted by this license</span>' : '');

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
    /* Straight to the record, in the page. It is a document to sign and post
       in the shack, and finding it in a downloads folder was a trip out of
       ELMER on a machine that may have no way out of it. */
    location.href = (await res.json()).view;
  } catch (e) {
    toast('Could not build the PDF', 'See data/elmer.log');
  }
  btn.disabled = false; btn.textContent = 'Station record (PDF)';
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

  /* An antenna handed over from the Lab's Antennas tab, which is on the other
     bench now. Applied after the pane is wired rather than instead of wiring
     it, and taken once: a row left lying about would turn up again in the
     next evaluation somebody opened, days later, as though they had entered
     it. */
  const handed = recall('rf.handoff', null);
  if (handed && handed.row) {
    remember('rf.handoff', null);
    rfRows = [handed.row];
    renderRfRows();
    selectTab('rf');
    history.replaceState(null, '', '#rf');
    const said = handed.said || {};
    toast(said.title || 'Sent to RF exposure', said.text || '');
    if (said.warn) setTimeout(() => toast('Worth knowing', said.warn, 9000), 600);
  }
  rfEvaluate();
}
if (document.getElementById('pane-rf')) initRf();

/* ---------- what to put up, and how ----------

   The calculator answers "how long is a dipole for 14.2 MHz", which is the
   easy half of the question a new licensee is actually asking. This asks the
   other half - what should I put up, how high, which way round - and then sets
   the calculator to that answer so the dimensions come out of it.

   Reached from the band plan: clicking a segment there arrives here with the
   frequency and the intended use already in the address. */

/* Re-ask about the antenna now selected, but only if advice is already on
   screen: somebody who has not asked for it should not have it appear because
   they browsed the list. */
/* Where the feed matches, by height. A dipole is 73 ohms in free space and
   something else at every height over the ground - 22 ohms at a tenth of a
   wave, 50 near 0.16, a 98 ohm high point at 0.35, back through 73 at half a
   wave. The ideal height is worth knowing; so are the heights the garden can
   actually reach where the match happens to be good, which is what this
   lists. Perfect-ground figures: real ground damps the swings. */
function matchingHeightsHTML(d) {
  const rows = d.heights || [];
  if (!rows.length) return '';
  const WORD = {match: '50 \u03a9 match', natural: 'natural 73 \u03a9',
                peak: 'high point', dip: 'dip'};
  const near = rows.filter(r => r.reachable), far = rows.filter(r => !r.reachable);
  const line = r => '<tr class="' + (r.reachable ? '' : 'far') + '">' +
    '<td class="mono">' + r.ft + ' ft</td><td class="mono">' + r.wavelengths.toFixed(2) + ' \u03bb</td>' +
    '<td class="mono">' + r.ohms + ' \u03a9</td><td class="mono">SWR ' + r.swr.toFixed(1) + '</td>' +
    '<td>' + WORD[r.what] + (r.what === 'match' ? ' \u2014 coax matches it with nothing in between' : '') + '</td></tr>';
  return '<div class="panel-title" style="margin-top:.9rem">Heights where the feed matches</div>' +
    '<table class="facts small heights">' + near.map(line).join('') +
    (far.length && near.length ? '<tr class="far sep"><td colspan="5">beyond what the site allows</td></tr>' : '') +
    far.slice(0, 3).map(line).join('') + '</table>' +
    '<p class="tiny muted">The feedpoint swings with height because the wire sees its own ' +
    'reflection in the ground; the period is half a wavelength. Perfect-ground figures - real ' +
    'ground damps the swings and shifts them a little, so start looking at these heights ' +
    'rather than stop at them. The pattern changes with height too; that is drawn below.</p>';
}

/* What the power asks of the parts. Led with the thing people get wrong,
   because they do: a thicker element does not need more power. */
function powerHTML(d) {
  const p = d.power;
  if (!p || !p.items || !p.items.length) return '';
  return '<div class="panel-title" style="margin-top:.9rem">What ' + p.watts + ' W asks of it</div>' +
    '<ul class="facts small">' + p.items.map(t => '<li>' + escapeHTML(t) + '</li>').join('') +
    '<li>The people nearby: <a href="#" data-rf-handoff>check the RF exposure at ' + p.watts + ' W</a>.</li></ul>';
}

function refreshAdvice() {
  const box = document.getElementById('an-advice');
  if (!box || box.hidden) return;
  antennaAdvice(num('an-f'), document.getElementById('an-use').value,
                document.getElementById('an-type').value, true);
}

/* Whether the operator may key up where this antenna is being cut for.
   ELMER holds 97.301 in full and the RF exposure tab already refuses a
   frequency this licence has no business on - and the antenna calculator, the
   one place that hands over a length somebody cuts wire to, never asked. A
   dipole for 3.885 is eleven feet shorter than one for the only part of 80 m
   a Technician may use, so the silence did not merely fail to warn: it gave
   out the wrong number with confidence.

   The class comes from the profile, and a profile is a setting, and settings
   drift. Somebody who upgraded and never went back to change it is at least
   as likely as somebody who has forgotten the rules, and a program that
   assumes the second is wrong about half the people it corrects. So the
   notice names the class it is judging by, and offers to judge by another -
   which changes this evaluation and not the profile, because guessing at
   somebody's licence and then writing it down would be worse than either. */
/* Whether the number in the height box is ELMER's suggestion or a height
   somebody measured. It matters because a height only means anything as a
   fraction of a wavelength: 35 ft is half a wave on 20 m and a seventh of one
   on 80. A suggestion made for one band is meaningless on another and has to
   follow the frequency; a measured height is a fact about somebody's garden
   and must not be touched. Guiding a build on a height that belongs to a band
   nobody is on is how the tool ends up describing an antenna that does not
   exist. */
let anHeightSuggested = false;

let anAsClass = null;             // null means "whatever the profile says"
let anClassFrom = '';             // and where that came from, for the notice

async function antennaPrivilege(mhz) {
  const box = document.getElementById('an-advice');
  if (!box || box.hidden) return;
  const gone = document.getElementById('an-priv');
  if (gone) gone.remove();
  let d;
  try {
    d = await api('/api/privileges?mhz=' + encodeURIComponent(mhz) +
                  (anAsClass ? '&class=' + encodeURIComponent(anAsClass) : ''));
  } catch (err) { return; }
  // Nothing to say when the licence is unknown, the frequency is outside the
  // amateur bands entirely, or the answer is simply yes.
  if (!d.license_class || !d.in_band || d.allowed) return;

  /* Where the class being judged by came from. Getting this wrong is how a
     warning loses its authority: told "as a Technician" by a page they
     reached while reading the Extra plan, an operator learns that the
     program is guessing. */
  const where = got => {
    if (anClassFrom === 'bandplan') {
      return 'Carried over from the band plan, which you were reading as ' +
             escapeHTML(got.license_class) + '.';
    }
    if (anClassFrom === 'here') {
      return 'You picked this here' +
             (got.profile_class && got.profile_class !== got.license_class
               ? '; your profile says ' + escapeHTML(got.profile_class) : '') +
             '.';
    }
    return 'Taken from your profile.';
  };

  const segs = (d.band_segments || []).map(seg =>
    '<b>' + seg.low.toFixed(3) + '&ndash;' + seg.high.toFixed(3) + '</b>' +
    (seg.terms ? ' (' + escapeHTML(seg.terms) + ')' : '')).join(', ');
  const options = (d.classes || []).map(c =>
    '<option value="' + escapeHTML(c) + '"' +
    (c === d.license_class ? ' selected' : '') + '>' + escapeHTML(c) +
    '</option>').join('');

  box.insertAdjacentHTML('afterbegin',
    '<div id="an-priv" class="notice" style="margin-bottom:.7rem">' +
      '<b>' + mhz + ' MHz is not yours to transmit on as a ' +
      escapeHTML(d.license_class) + '.</b> ' +
      (segs ? 'On ' + escapeHTML(d.band) + ' that class has ' + segs + '. '
            : 'That class has nothing on ' + escapeHTML(d.band) + '. ') +
      (d.suggest_mhz
        ? '<button class="btn sm" id="an-priv-go">Work it out for ' +
          d.suggest_mhz + ' instead</button> '
        : '') +
      '<label class="tiny" style="margin-left:.4rem">judging as ' +
        '<select id="an-priv-class" class="mono">' + options + '</select>' +
      '</label>' +
      '<div class="tiny muted" style="margin-top:.35rem">' + where(d) +
        ' Changing it here changes this evaluation and not the profile.</div>' +
    '</div>');

  const pick = document.getElementById('an-priv-class');
  if (pick) pick.addEventListener('change', () => {
    anAsClass = pick.value;
    anClassFrom = 'here';
    antennaPrivilege(mhz);
  });
  const go = document.getElementById('an-priv-go');
  if (go) go.addEventListener('click', () => {
    const f = document.getElementById('an-f');
    f.value = d.suggest_mhz;
    f.dispatchEvent(new Event('change', {bubbles: true}));
    antennaAdvice(d.suggest_mhz, document.getElementById('an-use').value,
                  document.getElementById('an-type').value, true);
  });
}

async function antennaAdvice(mhz, use, kind, quiet) {
  const box = document.getElementById('an-advice');
  if (!box) return;
  let d;
  try {
    d = await api('/api/antenna-advice?' + new URLSearchParams(
      Object.entries({mhz: mhz, use: use || '', kind: kind || '',
                      site: anSiteValue(),
                      watts: num('an-pw') > 0 ? num('an-pw') : '',
                      conductor: (document.getElementById('an-cond') || {}).value || ''})
        .filter(([, v]) => v !== '')));
  } catch (e) { return; }

  /* Set the calculator to the recommendation, so the dimensions below are the
     dimensions of the thing being recommended rather than of whatever was
     there before - unless the antenna was the question. Somebody who picked a
     full-wave loop and asked about it should not find the selector quietly
     changed to "dipole" underneath them. */
  if (!quiet) {
    document.getElementById('an-type').value = d.type;
    document.getElementById('an-f').value = d.mhz;
    const h = document.getElementById('an-h');
    if (h) { h.value = d.height_ft; anHeightSuggested = true; }
    const nvis = document.getElementById('an-nvis');
    if (nvis) nvis.checked = !!d.nvis;
    const useSel = document.getElementById('an-use');
    if (useSel) useSel.value = d.use;
    antennaFields(d.type);
    calcAnt();
  } else if (anHeightSuggested && d.height_ft) {
    /* Quiet means "leave the operator's numbers alone", and this one is not
       theirs - ELMER put it there for a different band. Leaving it would have
       the reach, the pattern and the takeoff angle all answering about an
       antenna nobody has. */
    const h = document.getElementById('an-h');
    if (h && String(h.value) !== String(d.height_ft)) {
      h.value = d.height_ft;
      calcAnt();
    }
  }

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

  antennaPrivilege(d.mhz);
  box.innerHTML =
    '<div class="advice-head">' +
      '<b>' + escapeHTML(d.title) + '</b>' +
      '<span class="tiny muted">' + d.mhz + ' MHz &middot; ' +
        escapeHTML(d.use_label) + ' &middot; wavelength ' + d.wavelength_ft +
        ' ft</span>' +
    '</div>' + said +
    '<div class="grid cols-2" style="gap:.9rem;margin-top:.5rem">' +
      '<div>' + d.why.map(w => '<p class="small">' + escapeHTML(w) + '</p>').join('') +
        /* A flat has no height to aim for - the wire starts at the window and
           slopes down - and "0 ft" there is a number standing where a sentence
           belongs. A vehicle likewise: the roof is the height. */
        '<p class="small"><b>' + (d.reality && d.reality.max_ft === 0
            ? 'Height: the window or rail you start from, and the slope down from it does the rest.'
            : d.reality && d.reality.site === 'mobile'
              ? 'Height: the roof of the vehicle.'
              : 'Height to aim for: ' + d.height_ft + ' ft.') + '</b> ' +
        escapeHTML(d.feedline) + '</p>' +
        matchingHeightsHTML(d) + powerHTML(d) + '</div>' +
      '<div><div class="panel-title">What usually goes wrong</div>' +
        '<ul class="facts small">' +
        d.watch.map(w => '<li>' + escapeHTML(w) + '</li>').join('') + '</ul>' +
        /* "Instead:" told the reader to do the other thing. It is not an
           instead, it is the runner-up and the conditions under which it
           wins - and labelling it as a replacement made the page look like
           it was recommending two antennas at once. */
        (d.alternative ? '<p class="small muted"><b>Second choice:</b> ' +
          escapeHTML(d.alternative) + '</p>' : '') +
      '</div>' +
    '</div>' +
    /* Whether the antenna somebody chose suits what they said they are doing.
       Not to overrule them - one mast and one wire is a real constraint - but
       the mismatch is the thing worth knowing, and it is nearly always
       polarisation or takeoff angle rather than anything exotic. */
    (d.fit && d.fit.note
      ? '<div class="' + (d.fit.verdict === 'wrong shape' ? 'watchout' : 'nvis') +
        '" style="margin-top:.7rem"><b>' + escapeHTML(d.fit.verdict) +
        ' for ' + escapeHTML(d.use_label.toLowerCase()) + '.</b> ' +
        escapeHTML(d.fit.note) + '</div>'
      : '') +
    /* The point of the page is not a set of plans. It is a baseline honest
       enough to depart from, so it says which way to depart. */
    /* What is actually possible where somebody lives. "Half a wavelength up"
       is 69 ft on 40m: a mast on a farm and a daydream in a flat, and printing
       it at somebody in a flat is not advice, it is a door closing. */
    (d.reality
      ? '<div class="nvis mt"><b>' + escapeHTML(d.reality.label) + '.</b> ' +
        (d.reality.capped
          ? 'The textbook answer is <b>' + d.reality.wanted_ft + ' ft</b>, ' +
            (d.reality.height_ft > 0
              ? 'and what fits here is <b>' + d.reality.height_ft + ' ft</b>. '
              : 'and there is no height to be had here at all. That rules out ' +
                'the low bands for distance and rules almost nothing else out. ') +
            escapeHTML(d.reality.means || '')
          : 'The textbook height fits here.') +
        '<div class="mt"><b>What works:</b><ul class="facts small">' +
        d.reality.works.map(w => '<li>' + escapeHTML(w) + '</li>').join('') +
        '</ul></div>' +
        (d.reality.costs.length
          ? '<div><b>What it costs:</b><ul class="facts small">' +
            d.reality.costs.map(w => '<li>' + escapeHTML(w) + '</li>').join('') +
            '</ul></div>'
          : '') +
        '<div class="small">And what it is <b>good at</b>: ' +
        escapeHTML(d.reality.good_at) + '.</div></div>'
      : '') +
    (d.better && d.better.length
      ? '<div class="panel-title mt">Where to go from here</div>' +
        '<ul class="facts small">' +
        d.better.map(b => '<li>' + escapeHTML(b) + '</li>').join('') + '</ul>'
      : '') +
    '<p class="tiny muted" style="margin:.5rem 0 0">' +
      (d.chosen
        ? 'How to get the best out of the antenna you picked, at this ' +
          'frequency. Change the type above and this changes with it; clear ' +
          'it and ELMER will suggest one instead.'
        : 'A starting point, not a rule &mdash; good enough to make contacts ' +
          'with, which is what you need before you have the experience to ' +
          'disagree with it.') +
      ' The dimensions below are now set to it.</p>';
}

/* Two different questions, and they had been sharing one button. "Evaluate
   this setup" asks about the antenna on screen; "suggest one" is for somebody
   who does not yet know what to put up, which was the button's original job
   and became unreachable when the advice started following the selector. */
const suggestBtn = document.getElementById('an-suggest');
if (suggestBtn) suggestBtn.addEventListener('click', () => {
  anTypeByHand = false;
  const note = document.getElementById('an-type-note');
  if (note) { note.hidden = false; note.textContent = 'ELMER\u2019s suggestion. Change it if you have something else in mind.'; }
  const use = document.getElementById('an-use').value;
  rememberAntenna({mhz: num('an-f'), use: use, kind: ''});
  antennaAdvice(num('an-f'), use);        // no kind: let it choose, and set up for it
});

const adviseBtn = document.getElementById('an-advise');
if (adviseBtn) adviseBtn.addEventListener('click', () => {
  /* Ask about the antenna on screen. The button used to send no type at all,
     so however carefully somebody had chosen one, the answer came back about
     a dipole. */
  const ctx = {mhz: num('an-f'),
               use: document.getElementById('an-use').value,
               kind: document.getElementById('an-type').value};
  rememberAntenna(ctx);
  antennaAdvice(ctx.mhz, ctx.use, ctx.kind);
});

/* The sheet. Everything worked out on this page is worked out indoors, and
   the tape measure is not - so the same answers go on a piece of paper that
   can be carried to the far end of the garden with a pencil.

   Only the choices are sent. The PDF recomputes every figure from the same
   modules that drew the screen, so a sheet found in a toolbox next year cannot
   quietly disagree with the program that made it. */
const printBtn = document.getElementById('an-print');
if (printBtn) printBtn.addEventListener('click', async () => {
  const was = printBtn.textContent;
  printBtn.disabled = true; printBtn.textContent = 'Building\u2026';
  try {
    const body = {
      kind: document.getElementById('an-type').value || 'dipole',
      mhz: num('an-f'),
      height: num('an-h'),
      use: document.getElementById('an-use').value,
      site: anSiteValue(),
      conductor: (document.getElementById('an-cond') || {}).value || ''
    };
    const res = await fetch('/api/antenna/pdf', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)});
    if (!res.ok) throw new Error(res.status);
    // Straight to it, the way the band charts go: a file in a downloads
    // folder is out of reach on a unit running full screen.
    location.href = (await res.json()).view;
  } catch (e) { toast('Could not build the sheet', 'See data/elmer.log'); }
  printBtn.disabled = false; printBtn.textContent = was;
});

/* Arriving from the band plan with a frequency in hand - and still having it
   on the way back.

   The handoff used to be one-shot: the frequency came in on the query string,
   the URL was tidied a line later, and that was the only record of it. Leave
   the page to look up the MUF and come back and there was nothing to come back
   to - the tool had been set up for a band it no longer knew about. So the
   context is kept, and restored whenever the page loads without one. */
const rememberAntenna = ctx => remember('lab.antenna', ctx);
const recallAntenna = () => recall('lab.antenna', null);

(function () {
  /* Whatever was last said about what you have to work with, before anything
     is answered. A recommendation made for nobody's site is the textbook
     one, and the textbook wants a wire half a wavelength up. */
  const siteSel = document.getElementById('an-site');
  const knownSite = recall('lab.antenna.site', '');
  if (siteSel && knownSite && [...siteSel.options].some(o => o.value === knownSite)) {
    siteSel.value = knownSite;
  }

  const q = new URLSearchParams(location.search);
  const f = q.get('f');
  if (f) {
    /* Arriving from the band plan with the class that page was being read
       as. Without it the answer here would be against the profile, which is
       a different question from the one on the screen they left. */
    const asClass = q.get('class');
    if (asClass) { anAsClass = asClass; anClassFrom = 'bandplan'; }
    const ctx = {mhz: f, use: q.get('use') || '', kind: q.get('kind') || '',
                 asClass: asClass || ''};
    rememberAntenna(ctx);
    selectTab('ant');
    history.replaceState(null, '', location.pathname + '#ant');
    antennaAdvice(ctx.mhz, ctx.use, ctx.kind);
    return;
  }
  /* No frequency on the URL: either a plain visit or a return trip. Restore
     what was last set up, without stealing the tab - somebody arriving at
     #smith wanted the Smith chart. */
  const ctx = recallAntenna();
  if (ctx && ctx.mhz) {
    if (ctx.asClass) { anAsClass = ctx.asClass; anClassFrom = 'bandplan'; }
    antennaAdvice(ctx.mhz, ctx.use, ctx.kind);
  }
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

function smithPlot(d, measured) {
  const g = [smithGrid(d.z0)];
  if (measured) g.push(smithLocus(measured.rows, measured.at));
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

/* The measurement on the Smith chart, which is the view the SWR plot cannot
   give. A point at or past |G| = 1 has no SWR - the formula divides by
   (1 - |G|) - so it is missing from that trace entirely and the trace can
   come out empty with nothing said. Here the same point simply lands outside
   the unit circle, and that is not a missing reading, it is the diagnosis:
   nothing passive returns more than was sent into it, so what you are looking
   at is an instrument with no calibration loaded. */
function smithLocus(rows, at) {
  if (!rows || !rows.length) return '';
  const g = [];
  const pts = rows.map(r => smXY(r.gx, r.gy).map(n => n.toFixed(1)).join(','))
                  .join(' ');
  g.push('<polyline points="' + pts + '" fill="none" stroke="#3fb950" ' +
         'stroke-width="2" opacity="0.85"/>');
  if (at) {
    const [mx, my] = smXY(at.gx, at.gy);
    g.push('<circle cx="' + mx.toFixed(1) + '" cy="' + my.toFixed(1) +
           '" r="6" fill="none" stroke="#3fb950" stroke-width="2"/>');
    g.push('<text x="' + (mx + 10).toFixed(1) + '" y="' + (my + 4).toFixed(1) +
           '" fill="#3fb950" font-size="11">' + at.mhz.toFixed(3) +
           ' MHz measured</text>');
  }
  return g.join('');
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

/* Whether there is a measurement to offer, and whether the operator has asked
   for it. Kept as two questions because they answer differently: a sweep can
   exist while somebody is deliberately looking at a typed impedance instead,
   and taking a new sweep should not yank the chart out from under them. */
function smMeasSync() {
  const none = document.getElementById('sm-meas-none');
  const label = document.getElementById('sm-meas-on');
  const slider = document.getElementById('sm-point');
  if (!none || !label || !slider) return;
  const rows = (vnMeasured && vnMeasured.rows) || [];
  none.hidden = rows.length > 0;
  label.hidden = !rows.length;
  const on = rows.length && document.getElementById('sm-use').checked;
  slider.hidden = !on;
  if (!rows.length) { document.getElementById('sm-point-v').textContent = ''; return; }
  document.getElementById('sm-use-label').innerHTML =
    'Read it from the measured sweep &mdash; ' + rows.length + ' points, ' +
    vnMeasured.low_mhz.toFixed(3) + '–' + vnMeasured.high_mhz.toFixed(3) + ' MHz';
  slider.max = String(rows.length - 1);
  if (+slider.value > rows.length - 1) slider.value = String(rows.length - 1);
}

/* The sweep was taken on the Tools page and this is the Lab, so it comes off
   the server rather than out of a variable. Asked for once, not on every
   event: a slider dragged across the chart should not fetch a measurement on
   every pixel of the drag. */
let smAsked = false;

async function smHeldSweep() {
  if (smAsked || vnMeasured) return;
  smAsked = true;
  let d;
  try {
    d = await api('/api/vna/last');
  } catch (err) {
    return;                       // no sweep to be had is not a page error
  }
  if (!d || !d.sweep || !(d.sweep.rows || []).length) return;
  vnMeasured = d.sweep;
  smMeasSync();
  calcSmith();
}

function smMeasuredPoint() {
  const rows = (vnMeasured && vnMeasured.rows) || [];
  const use = document.getElementById('sm-use');
  if (!rows.length || !use || !use.checked) return null;
  const slider = document.getElementById('sm-point');
  return rows[Math.max(0, Math.min(rows.length - 1, +slider.value))] || null;
}

async function calcSmith() {
  const box = document.getElementById('sm-out');
  if (!box) return;
  smMeasSync();
  const point = smMeasuredPoint();
  if (point) {
    /* The measurement fills the boxes rather than bypassing them, so
       everything downstream - the walk down the line, the loss, the notes -
       is the same machinery working on a real antenna instead of a typed one.
       A resistance below zero is not a thing a feedline can be walked down,
       and it is what a point outside the circle means; it is floored here and
       named underneath rather than sent to the server to be refused. */
    document.getElementById('sm-f').value = point.mhz.toFixed(3);
    document.getElementById('sm-r').value =
      Math.max(0, point.r === null ? 50 : point.r).toFixed(1);
    document.getElementById('sm-x').value =
      (point.x === null ? 0 : point.x).toFixed(1);
    document.getElementById('sm-point-v').innerHTML =
      point.mhz.toFixed(3) + ' MHz &nbsp; |&#915;| ' +
      (point.gmag === undefined ? '—' : point.gmag.toFixed(3)) +
      ' &nbsp; SWR ' + (point.swr === null ? 'undefined' : point.swr + ':1');
  }
  const q = new URLSearchParams({
    r: num('sm-r'), x: num('sm-x'), mhz: num('sm-f'),
    line: document.getElementById('sm-line').value,
    feet: num('sm-len'), watts: num('sm-w'),
  });
  document.getElementById('sm-len-v').textContent = num('sm-len') + ' ft';
  let d;
  try { d = await api('/api/smith?' + q); } catch (e) { return; }
  document.getElementById('sm-chart').innerHTML = smithPlot(d,
    point ? {rows: vnMeasured.rows, at: point} : null);
  const outside = point && point.gmag !== undefined && point.gmag >= 1
    ? '<p class="small" style="color:var(--amber)">This point is outside the ' +
      'circle: |&#915;| is ' + point.gmag.toFixed(3) + ', so more came back ' +
      'than went out and there is no SWR to quote. Nothing passive does that ' +
      '&mdash; it is what an uncalibrated instrument looks like, and it is why ' +
      'the SWR trace has a hole in it. Calibrate at the far end of the jumper ' +
      'that screws onto the antenna and sweep again.</p>'
    : '';
  box.innerHTML =
    '<div class="row" style="gap:1.1rem;flex-wrap:wrap">' +
      '<span>SWR at the antenna <b>' +
        (d.load.swr === null ? '∞' : d.load.swr.toFixed(2)) + ':1</b></span>' +
      '<span>at the shack <b>' +
        (d.shack.swr === null ? '∞' : d.shack.swr.toFixed(2)) + ':1</b></span>' +
      '<span>line loss <b>' + d.loss.total_db.toFixed(2) + ' dB</b></span>' +
      '<span>reaching the antenna <b>' + d.loss.power_at_antenna + ' W</b></span>' +
      '<span class="tiny muted">' + d.wavelength_ft + ' ft per wavelength in this line</span>' +
    '</div>' + outside + '<div class="mt">' + smithNotes(d) + '</div>';
}

if (document.getElementById('sm-chart')) {
  const sel = document.getElementById('sm-line');
  [['rg58', 'RG-58 — thin, common, lossy'], ['rg8x', 'RG-8X — mini-8'],
   ['rg213', 'RG-213 — full size'], ['lmr400', 'LMR-400 — low loss'],
   ['rg6', 'RG-6 — 75 Ω TV coax'], ['ladder', '450 Ω window line']]
    .forEach(([v, l]) => sel.insertAdjacentHTML('beforeend',
      '<option value="' + v + '"' + (v === 'rg213' ? ' selected' : '') + '>' + l + '</option>'));
  ['sm-r', 'sm-x', 'sm-f', 'sm-len', 'sm-w', 'sm-line',
   'sm-use', 'sm-point'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
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
  smHeldSweep();
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
      /* The SWR curve used to be drawn here too, small and static, next to
         the two patterns. It has moved to the sweep at the foot of this tab,
         where it is the same quantity with a feedline, a trim slider and a
         marker readout attached - two charts of one number on one page is one
         chart too many. What is kept is the sentence, because Q and what the
         feedpoint is fed through are not on the trace. */
      '<div><div class="panel-title">How sharp it is</div>' +
        '<p class="small muted"><b>' + (b.khz ? b.khz + ' kHz' : 'nothing') +
        '</b> under 2:1' + (b.khz ? ' (' + b.percent + '% of the frequency)' : '') +
        '. Q about ' + d.q + ' &mdash; ' + escapeHTML(d.fed) + '.</p>' +
        '<p class="tiny muted">The trace for this, with a feedline on it and a ' +
        'length you can drag, is at the foot of this tab.</p></div>' +
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

/* ------------------------------------------------------------- sextant ---
   Where you are, from the sun and a clock.

   The arithmetic lives on the server, but the point of the tool is that it is
   shown rather than pronounced: somebody who might one day depend on this
   needs to have watched it work. So every correction that turns a sextant
   reading into a true altitude is listed with its sign and its reason, and the
   answer arrives with an honest uncertainty rather than a reassuring one. */

const SX_ROWS = document.getElementById('sx-rows');

function sxRow(n) {
  return '<tr>' +
    '<td class="mono muted">' + n + '</td>' +
    '<td class="row" style="gap:.3rem;flex-wrap:nowrap">' +
      '<input type="number" class="sx-deg" style="width:5.5rem" min="0" max="179" step="1" placeholder="deg">' +
      '<input type="number" class="sx-min" style="width:5.5rem" min="0" max="59.9" step="0.1" placeholder="min">' +
    '</td>' +
    '<td><input type="time" class="sx-time" step="1" style="width:9rem"></td>' +
    '<td><select class="sx-limb mono">' +
      '<option value="lower">lower</option>' +
      '<option value="upper">upper</option>' +
      '<option value="centre">centre</option>' +
    '</select></td>' +
    '<td><button class="btn sm ghost sx-now" title="stamp this row with the time now">now</button></td>' +
  '</tr>';
}

/* ------------------------------------------------------ the VNA trace ---
   What a NanoVNA puts on its screen, for an antenna that is still a plan.

   The point of drawing it rather than printing an SWR number is that the
   shape carries the instruction. A dip to the left of where you are means the
   antenna is long; a dip to the right means it is short; no dip at all means
   you are not looking in the right place. None of that survives being reduced
   to "2.4:1", which is what an SWR meter gives you and why an SWR meter
   cannot tell you which way to cut. */

const VN_W = 640, VN_H = 260, VN_L = 46, VN_R = 14, VN_T = 16, VN_B = 34;
const VN_TOP_SWR = 5;

function vnSwrY(swr) {                       // 1:1 at the floor, 5:1 at the ceiling
  const s = Math.max(1, Math.min(VN_TOP_SWR, swr || VN_TOP_SWR));
  return VN_H - VN_B - (s - 1) / (VN_TOP_SWR - 1) * (VN_H - VN_T - VN_B);
}

function vnPath(rows, key, lo, hi) {
  const pts = [];
  rows.forEach(r => {
    const v = r[key];
    if (v === null || v === undefined) return;
    const x = VN_L + (r.mhz - lo) / (hi - lo) * (VN_W - VN_L - VN_R);
    pts.push(x.toFixed(1) + ',' + vnSwrY(v).toFixed(1));
  });
  return pts.length ? 'M ' + pts.join(' L ') : '';
}

/* `extra` may carry a measured sweep and a cursor frequency. Everything is
   optional: the same chart draws a prediction alone, a measurement alone, or
   the two on top of each other, which is the comparison that teaches. */
function vnaChart(d, extra) {
  extra = extra || {};
  const rows = d.rows || [];
  if (!rows.length) return '<div class="tiny muted">no sweep</div>';
  const lo = extra.lo || rows[0].mhz, hi = extra.hi || rows[rows.length - 1].mhz;
  const X = mhz => VN_L + (mhz - lo) / (hi - lo) * (VN_W - VN_L - VN_R);
  const g = [];

  g.push('<rect x="' + VN_L + '" y="' + VN_T + '" width="' + (VN_W - VN_L - VN_R) +
         '" height="' + (VN_H - VN_T - VN_B) + '" fill="#0b1015" stroke="' +
         SX_LINE + '"/>');

  /* The 2:1 line is drawn heavier than the rest. It is not physics - nothing
     happens at 2:1 - but it is the number every rig's foldback is set near,
     so it is the line an operator is actually trying to get under. */
  [1.5, 2, 3, 5].forEach(s => {
    const y = vnSwrY(s);
    g.push('<line x1="' + VN_L + '" y1="' + y.toFixed(1) + '" x2="' + (VN_W - VN_R) +
           '" y2="' + y.toFixed(1) + '" stroke="' + (s === 2 ? '#4a5663' : '#222c36') +
           '" stroke-width="' + (s === 2 ? 1.2 : 0.8) + '"' +
           (s === 2 ? '' : ' stroke-dasharray="3 3"') + '/>');
    g.push('<text x="' + (VN_L - 6) + '" y="' + (y + 3.5).toFixed(1) + '" fill="' +
           SX_INK + '" font-size="10" text-anchor="end">' + s + ':1</text>');
  });

  const band = (d.antenna && d.antenna.band_2to1) || null;
  if (band && !band.wider_than_sweep) {
    g.push('<rect x="' + X(band.low_mhz).toFixed(1) + '" y="' + VN_T + '" width="' +
           Math.max(0, X(band.high_mhz) - X(band.low_mhz)).toFixed(1) + '" height="' +
           (VN_H - VN_T - VN_B) + '" fill="' + SX_OK + '" opacity=".07"/>');
  }

  for (let i = 0; i <= 4; i++) {
    const f = lo + (hi - lo) * i / 4, x = X(f);
    g.push('<line x1="' + x.toFixed(1) + '" y1="' + (VN_H - VN_B) + '" x2="' +
           x.toFixed(1) + '" y2="' + (VN_H - VN_B + 4) + '" stroke="' + SX_INK + '"/>');
    g.push('<text x="' + x.toFixed(1) + '" y="' + (VN_H - VN_B + 16) + '" fill="' +
           SX_INK + '" font-size="10" text-anchor="middle">' + f.toFixed(3) + '</text>');
  }
  g.push('<text x="' + ((VN_L + VN_W - VN_R) / 2) + '" y="' + (VN_H - 4) +
         '" fill="' + SX_INK + '" font-size="10" text-anchor="middle">MHz</text>');

  if (extra.cursor && extra.cursor >= lo && extra.cursor <= hi) {
    const x = X(extra.cursor);
    g.push('<line x1="' + x.toFixed(1) + '" y1="' + VN_T + '" x2="' + x.toFixed(1) +
           '" y2="' + (VN_H - VN_B) + '" stroke="#e6edf3" stroke-width="1" ' +
           'stroke-dasharray="4 3" opacity=".55"/>');
    g.push('<text x="' + (x + 4).toFixed(1) + '" y="' + (VN_T + 12) +
           '" fill="#e6edf3" font-size="10">where you transmit</text>');
  }

  if (d.feet) {
    const p = vnPath(rows, 'swr_in', lo, hi);
    if (p) g.push('<path d="' + p + '" fill="none" stroke="' + SX_GLASS +
                  '" stroke-width="1.6" stroke-dasharray="5 3"/>');
  }
  const main = vnPath(rows, 'swr', lo, hi);
  if (main) g.push('<path d="' + main + '" fill="none" stroke="' + SX_SUN +
                   '" stroke-width="2.2"/>');
  if (extra.measured && extra.measured.length) {
    const p = vnPath(extra.measured, 'swr', lo, hi);
    if (p) g.push('<path d="' + p + '" fill="none" stroke="' + SX_OK +
                  '" stroke-width="2"/>');
  }

  const best = d.antenna && d.antenna.best_mhz;
  if (best !== undefined && best !== null && best >= lo && best <= hi) {
    g.push('<circle cx="' + X(best).toFixed(1) + '" cy="' +
           vnSwrY(d.antenna.best_swr).toFixed(1) + '" r="4" fill="' + SX_SUN +
           '" stroke="#0b1015" stroke-width="1.5"/>');
  }

  const keys = [['antenna, at the feedpoint', SX_SUN, false]];
  if (d.feet) keys.push(['at the shack end of ' + d.feet + ' ft', SX_GLASS, true]);
  if (extra.measured && extra.measured.length) keys.push(['measured', SX_OK, false]);
  const legend = keys.map((k, i) =>
    '<span style="white-space:nowrap"><svg width="26" height="8" style="vertical-align:middle">' +
    '<line x1="1" y1="4" x2="25" y2="4" stroke="' + k[1] + '" stroke-width="2.4"' +
    (k[2] ? ' stroke-dasharray="5 3"' : '') + '/></svg> ' + k[0] + '</span>').join(
    '<span class="muted"> &nbsp;&middot;&nbsp; </span>');

  return '<svg viewBox="0 0 ' + VN_W + ' ' + VN_H + '" style="width:100%;max-width:' +
    VN_W + 'px">' + g.join('') + '</svg>' +
    '<div class="tiny muted" style="margin-top:.2rem">' + legend + '</div>';
}

/* The numbers under the trace: what a marker readout would say. */
function vnaMarkers(d) {
  const a = d.antenna || {}, sh = d.shack || {};
  const cell = (label, value, note) =>
    '<div class="panel stat"><span class="stat-label">' + label + '</span>' +
    '<span class="stat-value">' + value + '</span>' +
    '<span class="stat-note">' + (note || '') + '</span></div>';
  const band = a.band_2to1;
  return '<div class="grid cols-3 mt">' +
    cell('Resonance', a.resonance_mhz ? a.resonance_mhz.toFixed(3) + ' MHz' : '—',
         'where the reactance crosses zero') +
    cell('Best match', (a.best_swr !== undefined ? a.best_swr.toFixed(2) + ':1' : '—'),
         a.best_mhz ? 'at ' + a.best_mhz.toFixed(3) + ' MHz' : '') +
    cell('Under 2:1', band ? band.khz + ' kHz' : 'nowhere',
         band ? band.low_mhz.toFixed(3) + '–' + band.high_mhz.toFixed(3) +
           (band.wider_than_sweep ? ' (runs off the sweep)' : '') : 'not in this span') +
    (d.feet ? cell('At the shack', (sh.best_swr !== undefined ? sh.best_swr.toFixed(2) + ':1' : '—'),
         d.matched_loss_db + ' dB matched loss in ' + d.feet + ' ft') : '') +
    '</div>';
}

/* --- the sweep on the Antennas tab, and the VNA tab ------------------------
   Both drive the same chart off the same endpoint. The only difference is
   that one of them can also ask a real instrument, and lay what it says over
   what the model predicted. */

let vnTimer = null;
function vnSoon(fn) {                 // a slider fires on every pixel of drag
  clearTimeout(vnTimer);
  vnTimer = setTimeout(fn, 110);
}

async function vnFetch(params) {
  try { return await api('/api/vna/sweep?' + new URLSearchParams(params)); }
  catch (e) { return null; }
}

function vnDraw(chartId, markerId, readId, d, extra) {
  if (!d) return;
  document.getElementById(chartId).innerHTML = vnaChart(d, extra);
  document.getElementById(markerId).innerHTML = vnaMarkers(d);
  document.getElementById(readId).innerHTML =
    (d.read || []).map(t => '<p style="margin:.35rem 0">' + t + '</p>').join('');
}

/* The Antennas tab. The trim slider is a length, not a frequency, because a
   length is what somebody is actually holding a pair of cutters over - and
   resonance goes inversely with it, so 5% long is a dip 5% low. */
async function avUpdate() {
  const trim = +document.getElementById('av-trim').value;
  const feet = +document.getElementById('av-feet').value;
  const f = parseFloat(document.getElementById('an-f').value);
  if (!isFinite(f) || f <= 0) return;
  document.getElementById('av-trim-v').textContent =
    trim.toFixed(2) + '% ' + (Math.abs(trim - 100) < 0.01 ? '(as calculated)'
      : trim > 100 ? '(long)' : '(short)');
  document.getElementById('av-feet-v').textContent =
    feet ? feet + ' ft' : 'measuring at the antenna';
  const d = await vnFetch({
    kind: document.getElementById('an-type').value,
    f0: (f / (trim / 100)).toFixed(6), centre: f, span: 0.14,
    line: document.getElementById('av-line').value, feet: feet,
  });
  vnDraw('av-chart', 'av-markers', 'av-read', d, {cursor: f});
}

/* The VNA tab. Same chart, plus whatever the instrument on the bench says.
   `vnMeasured` is declared at the top of this file, not here - see the note
   beside it. */

/* What the instrument itself is set to, once it has said so - from driving it
   or from a sweep coming back. While this is known it owns the horizontal
   axis, because a chart that says 14.10-14.25 while the instrument in front
   of you is sweeping 14.00-14.35 is not a second opinion, it is a wrong
   caption. Touch the model's own centre or span and it lets go: at that point
   the operator has taken the wheel and asked to look somewhere else. */
let vnFollow = null;

function vnFollowing(span) {
  if (!span) return;
  const lo = +span.low_mhz, hi = +span.high_mhz;
  // An instrument parked on a single frequency reports every point the same,
  // and a window with no width divides by zero and draws nothing. Decline to
  // follow that rather than take the axis somewhere it cannot come back from.
  if (!isFinite(lo) || !isFinite(hi) || hi <= lo) return;
  vnFollow = {low_mhz: lo, high_mhz: hi, points: span.points};
  const centre = (lo + hi) / 2;
  const box = document.getElementById('vn-centre');
  if (box) box.value = centre.toFixed(3);   // set, not typed: fires nothing
  vnSoon(vnUpdate);
}

async function vnUpdate() {
  const f0 = parseFloat(document.getElementById('vn-f0').value);
  const feet = +document.getElementById('vn-feet').value;
  if (!isFinite(f0) || f0 <= 0) return;

  let centre, span, lo, hi;
  if (vnFollow) {
    lo = vnFollow.low_mhz;
    hi = vnFollow.high_mhz;
    centre = (lo + hi) / 2;
    span = (hi - lo) / centre;
    document.getElementById('vn-span-v').textContent =
      'following the instrument: ' + lo.toFixed(3) + '–' + hi.toFixed(3) +
      ' MHz' + (vnFollow.points ? ', ' + vnFollow.points + ' points' : '');
  } else {
    const spanPct = +document.getElementById('vn-span').value;
    centre = parseFloat(document.getElementById('vn-centre').value) || f0;
    span = spanPct / 100;
    document.getElementById('vn-span-v').textContent = '±' + (spanPct / 2) + '%';
  }
  document.getElementById('vn-feet-v').textContent =
    feet ? feet + ' ft' : 'at the antenna';
  const d = await vnFetch({
    kind: document.getElementById('vn-kind').value,
    f0: f0, centre: centre, span: span,
    line: document.getElementById('vn-line').value, feet: feet,
  });
  if (!d) return;
  /* The axis is the instrument's when there is one, even where the model
     cannot follow it that far: the prediction is only defended near
     resonance, so a wide sweep draws it across the part it can answer for and
     leaves the rest to the measurement. Stretching the axis to fit the model
     instead would put the measured trace off the side of the picture, which
     is the bug this is here to stop. */
  vnDraw('vn-chart', 'vn-markers', 'vn-read', d, {
    cursor: centre,
    measured: vnMeasured && vnMeasured.rows,
    lo: lo || d.low_mhz, hi: hi || d.high_mhz,
  });
  window.vnLast = d;
}

function vnPorts(list, error) {
  const sel = document.getElementById('vn-port');
  sel.innerHTML = (list || []).map(p =>
    '<option value="' + p.device + '">' + p.device +
    (p.description ? ' — ' + p.description : '') + '</option>').join('');
  const any = (list || []).length > 0;
  document.getElementById('vn-id').disabled = !any;
  document.getElementById('vn-measure').disabled = !any;
  vnCtlEnable(any);
  const slots = document.getElementById('vn-ctl-slot');
  if (any && slots && !slots.options.length) {
    /* How many slots there are is the server's to say - five on an H, seven
       on an H4 - so it is asked once, when there is finally an instrument to
       ask about. */
    api('/api/vna/controls').then(c => {
      let html = '';
      for (let n = 0; n <= c.slots; n++) html += '<option>' + n + '</option>';
      slots.innerHTML = html;
    }).catch(() => { slots.innerHTML = '<option>0</option>'; });
  }
  document.getElementById('vn-dev').innerHTML = any
    ? (list[0].looks_right
        ? 'Found <b>' + escapeHTML(list[0].why) + '</b> on ' + list[0].device +
          '. Ask it what it is before sweeping.'
        : 'Found ' + list.length + ' serial port' + (list.length === 1 ? '' : 's') +
          ', none of which announces itself as a VNA. ' +
          escapeHTML(list[0].why) + '.')
    : '<span style="color:var(--amber)">' + escapeHTML(error || 'nothing found') +
      '</span> Plug it in, switch it on, and press again. On Linux you may need ' +
      'to be in the <span class="mono">dialout</span> group.';
}

/* ------------------------------------------------ driving the instrument */
/* Reading a VNA and driving one are different acts, and this is the second.
   Every press sends exactly one command and prints both halves of the
   exchange, because most of these are accepted in silence - "it said nothing"
   is the truth about this protocol rather than a shrug, and the instrument's
   own screen is two feet away and shows the rest.

   What may be sent is decided on the server, in one table, and so is the
   warning on anything that destroys work: this asks, is refused with the
   reason, puts that reason in front of the operator, and only then asks again
   having said it meant it. The page does not carry its own copy of what is
   dangerous, so the two cannot drift apart. */
function vnCtlEnable(on) {
  document.querySelectorAll('[data-vna]').forEach(b => { b.disabled = !on; });
}

function vnCtlSay(html, tone) {
  const box = document.getElementById('vn-ctl-out');
  if (!box) return;
  const line = document.createElement('div');
  line.className = 'small';
  line.style.cssText = 'border-left:2px solid ' + (tone || 'var(--line-2)') +
    ';padding:.2rem .6rem;margin-top:.35rem';
  line.innerHTML = html;
  box.prepend(line);
  while (box.children.length > 12) box.lastChild.remove();
}

function vnCtlValue(button) {
  const action = button.getAttribute('data-vna');
  if (action === 'cal-step') return button.getAttribute('data-value');
  if (action === 'save' || action === 'recall') {
    return parseInt(document.getElementById('vn-ctl-slot').value, 10);
  }
  if (action === 'sweep') {
    return {
      start_mhz: parseFloat(document.getElementById('vn-ctl-start').value),
      stop_mhz: parseFloat(document.getElementById('vn-ctl-stop').value),
      points: parseInt(document.getElementById('vn-ctl-points').value, 10),
    };
  }
  return null;
}

async function vnControl(button, confirmed) {
  const action = button.getAttribute('data-vna');
  const device = (document.getElementById('vn-port') || {}).value;
  if (!device) return;
  const label = button.textContent;
  button.disabled = true;
  button.textContent = 'Sending…';
  let d;
  try {
    d = await postJSON('/api/vna/control', {
      device: device, action: action, value: vnCtlValue(button),
      confirmed: !!confirmed,
    });
  } catch (err) {
    vnCtlSay('The server would not pass that on.', 'var(--red)');
    button.disabled = false; button.textContent = label;
    return;
  }
  button.disabled = false;
  button.textContent = label;

  if (!d.ok) {
    /* The refusal carries its own reason, which is the warning text. Asking
       again with that shown is the whole of the confirmation. */
    if (/^that one destroys/.test(d.error || '') && !confirmed &&
        confirm(d.error + '\n\nGo ahead?')) {
      return vnControl(button, true);
    }
    vnCtlSay(escapeHTML(d.error || 'refused'), 'var(--amber)');
    return;
  }
  const r = d.result;
  /* The instrument just told us where it is. That is the chart's window from
     now on - the whole point of setting a span is seeing it. */
  vnFollowing(r.span);
  const span = r.span
    ? ' &middot; now sweeping <b>' + r.span.low_mhz + '–' + r.span.high_mhz +
      ' MHz</b> over ' + r.span.points + ' points'
    : '';
  vnCtlSay('<span class="mono">' + escapeHTML(r.sent) + '</span> &rarr; ' +
    (r.said ? '<span class="mono">' + escapeHTML(r.said) + '</span>'
            : '<span class="muted">accepted without comment</span>') + span,
    'var(--green)');
}

document.addEventListener('click', e => {
  const b = e.target.closest('[data-vna]');
  if (b && !b.disabled) vnControl(b, false);
});

if (document.getElementById('vn-chart')) {
  ['vn-f0', 'vn-centre', 'vn-span', 'vn-kind', 'vn-line', 'vn-feet'].forEach(id => {
    const el = document.getElementById(id);
    // Moving the window by hand is a request to look somewhere else, so the
    // chart stops following the instrument until it is driven again.
    const own = (id === 'vn-centre' || id === 'vn-span');
    el.addEventListener('input', () => {
      if (own) vnFollow = null;
      vnSoon(vnUpdate);
    });
    el.addEventListener('change', () => {
      if (own) vnFollow = null;
      vnSoon(vnUpdate);
    });
  });

  document.getElementById('vn-find').addEventListener('click', async e => {
    e.target.disabled = true;
    try {
      const d = await api('/api/vna/ports');
      vnPorts(d.ports, d.error);
    } catch (err) {
      document.getElementById('vn-dev').textContent = 'could not look for ports';
    }
    e.target.disabled = false;
  });

  document.getElementById('vn-id').addEventListener('click', async e => {
    const dev = document.getElementById('vn-port').value;
    e.target.disabled = true;
    document.getElementById('vn-dev').textContent = 'asking ' + dev + '…';
    try {
      const d = await api('/api/vna/identify?device=' + encodeURIComponent(dev));
      document.getElementById('vn-dev').innerHTML = d.ok
        ? '<b>' + escapeHTML(dev) + '</b> answers:<pre class="mono tiny" ' +
          'style="white-space:pre-wrap;margin:.3rem 0">' +
          escapeHTML((d.info.info || '') + '\n' + (d.info.version || '')).trim() +
          '</pre>'
        : '<span style="color:var(--amber)">' + escapeHTML(d.error) + '</span>';
    } catch (err) {
      document.getElementById('vn-dev').textContent = 'no answer from ' + dev;
    }
    e.target.disabled = false;
  });

  document.getElementById('vn-measure').addEventListener('click', async e => {
    const dev = document.getElementById('vn-port').value;
    const d = window.vnLast;
    if (!d) return;
    /* Where the instrument is, if it has said - otherwise the window on
       screen. Imposing the model's span here would undo the span somebody
       had just set on the instrument, which is the opposite of driving it. */
    const low = vnFollow ? vnFollow.low_mhz : d.low_mhz;
    const high = vnFollow ? vnFollow.high_mhz : d.high_mhz;
    const points = (vnFollow && vnFollow.points) || 101;
    e.target.disabled = true;
    document.getElementById('vn-dev').innerHTML =
      'sweeping ' + low.toFixed(3) + '–' + high.toFixed(3) +
      ' MHz on ' + escapeHTML(dev) + '… this takes a few seconds.';
    try {
      const got = await api('/api/vna/measure?device=' + encodeURIComponent(dev) +
        '&start=' + low + '&stop=' + high + '&points=' + points);
      if (got.ok) {
        vnMeasured = got.sweep;
        // What came back is what it actually swept, which is not always what
        // it was asked for - so the axis follows the data, not the request.
        vnFollowing({low_mhz: got.sweep.low_mhz, high_mhz: got.sweep.high_mhz,
                     points: got.sweep.points});
        document.getElementById('vn-dev').innerHTML =
          '<span style="color:var(--green)">' + got.sweep.points +
          ' points back from ' + escapeHTML(dev) + '.</span> The green trace is ' +
          'what it measured. Where it disagrees with the model, believe the ' +
          'instrument &mdash; but check the calibration below before you believe ' +
          'either of them.';
        /* "There is no green trace" has three causes and none of them is a
           drawing bug, so the page says which one it is rather than leaving
           somebody hunting for one.

           SWR is not defined at or past |G| = 1: the formula divides by
           (1 - |G|), and past unity more has come back than went out, which
           nothing passive does. Those points are null, they are missing from
           the trace, and if they all are then the trace is genuinely empty.
           That is the ordinary look of an instrument with no calibration
           loaded - and it is exactly what the Smith chart draws well, because
           there the same points land outside the circle instead of vanishing.

           Failing that, the scale here stops at 5:1, so a sweep entirely
           above it is drawn along the very top of the frame where it reads as
           part of the border. */
        const rows = got.sweep.rows || [];
        const drawn = rows.filter(r => r.swr !== null);
        const unity = got.sweep.over_unity || 0;
        let why = '';
        if (!drawn.length) {
          why = 'There is no SWR trace because SWR is not defined for any of ' +
            'it: every point came back at or past total reflection, |&#915;| ' +
            '&ge; 1, meaning more returned than went out. No passive antenna ' +
            'does that, so this is an instrument with no calibration loaded, ' +
            'or an open port. Take it to the Smith chart tab - it draws these ' +
            'points outside the circle, which is the picture that says so.';
        } else if (unity) {
          why = unity + ' of ' + rows.length + ' points came back at |&#915;| ' +
            '&ge; 1 and are missing from the trace, because SWR is not defined ' +
            'there. That is usually the calibration rather than the antenna.';
        } else if (drawn.every(r => r.swr >= 5)) {
          why = 'Every point is above 5:1, which is the top of this scale ' +
            '&mdash; the green trace is pinned along the ceiling rather than ' +
            'missing. An open port, no calibration, or the standards measured ' +
            'at the wrong end of the coax all look like this.';
        }
        if (why) {
          document.getElementById('vn-dev').innerHTML +=
            ' <span style="color:var(--amber)">' + why + '</span>';
        }
        // The other tab can offer it now, whether or not anybody goes there.
        smMeasSync();
        const ex = document.getElementById('vn-export');
        if (ex) ex.hidden = false;         // there is now something to export
        vnUpdate();
      } else {
        document.getElementById('vn-dev').innerHTML =
          '<span style="color:var(--amber)">' + escapeHTML(got.error) + '</span>';
      }
    } catch (err) {
      document.getElementById('vn-dev').textContent = 'the sweep did not come back';
    }
    e.target.disabled = false;
  });

  /* Out of the building. A sweep is the one number in this program that was
     measured rather than modelled, and a measurement that cannot leave the
     machine it was taken on is half a measurement. Touchstone is what the
     modelling packages, NanoVNA-Saver and an antenna manufacturer all read, so
     that is what goes out - the raw reflection coefficient the instrument
     handed back, not a picture of it and not a conversion of it.

     The file is fetched rather than linked because it is a POST: the sweep
     lives in this page and nowhere else, so it has to be sent up to be
     written. The blob is what turns the reply into a save dialog. */
  const exportBtn = document.getElementById('vn-export');
  if (exportBtn) exportBtn.addEventListener('click', async () => {
    if (!vnMeasured || !(vnMeasured.rows || []).length) return;
    const was = exportBtn.textContent;
    exportBtn.disabled = true; exportBtn.textContent = 'Writing\u2026';
    try {
      const kind = (document.getElementById('an-type') || {}).value || '';
      const res = await fetch('/api/vna/s1p', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          rows: vnMeasured.rows, device: vnMeasured.device,
          note: kind ? 'Antenna under test: ' + kind : ''})});
      if (!res.ok) throw new Error(res.status);
      const name = (res.headers.get('Content-Disposition') || '')
        .match(/filename="([^"]+)"/);
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement('a');
      a.href = url; a.download = name ? name[1] : 'sweep.s1p';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast('Saved ' + (name ? name[1] : 'the sweep'),
            'Touchstone .s1p - any antenna program will read it');
    } catch (err) { toast('Could not write it', 'See data/elmer.log'); }
    exportBtn.disabled = false; exportBtn.textContent = was;
  });

  vnUpdate();
}

if (document.getElementById('av-chart')) {
  ['av-trim', 'av-feet', 'av-line', 'an-f', 'an-type'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', () => vnSoon(avUpdate));
    el.addEventListener('change', () => vnSoon(avUpdate));
  });
  avUpdate();
}

/* ------------------------------------------------- drawing the sextant ---
   The Smith chart is drawn rather than described because a transformation can
   only be watched. A sextant is drawn for a plainer reason: the skill has
   died, and the words "bring the lower limb tangent to the horizon and rock
   for the bottom of the arc" mean nothing at all to somebody who has never
   seen the thing. Three pictures - what the parts are, why the light gets to
   your eye at all, and what you are looking at while you do it. */

const SX_INK = '#8b98a5', SX_LINE = '#4a5663', SX_DIM = '#2f3a46',
      SX_SUN = '#ffb454', SX_GLASS = '#5b6b7d', SX_OK = '#3fb950';

function sxLabel(x, y, text, anchor) {
  return '<text x="' + x + '" y="' + y + '" fill="' + SX_INK +
    '" font-size="11" text-anchor="' + (anchor || 'start') + '">' + text + '</text>';
}

function sxLead(x1, y1, x2, y2) {
  return '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 +
    '" stroke="' + SX_LINE + '" stroke-width="0.8" stroke-dasharray="2 2"/>';
}

/* --- 1. the instrument, with its parts named -------------------------------
   Pivot at the top, arc below it: the frame is a sector of sixty degrees,
   which is where the name comes from. The arc is graduated to a hundred and
   twenty, which is the fact the next picture explains. */
function sxInstrument() {
  const P = [330, 92], R = 196, IN = 150, ARM = 97;
  const at = (deg, r) => [P[0] + r * Math.cos(deg * Math.PI / 180),
                          P[1] + r * Math.sin(deg * Math.PI / 180)];
  const xy = a => a[0].toFixed(1) + ' ' + a[1].toFixed(1);
  const arm = at(ARM, R), g = [];

  g.push('<path d="M ' + xy(P) + ' L ' + xy(at(60, R)) + ' A ' + R + ' ' + R +
         ' 0 0 1 ' + xy(at(120, R)) + ' Z" fill="#151b23" stroke="' + SX_LINE +
         '" stroke-width="1.4"/>');
  g.push('<path d="M ' + xy(at(90, 44)) + ' L ' + xy(at(67, IN)) + ' A ' + IN +
         ' ' + IN + ' 0 0 1 ' + xy(at(113, IN)) + ' Z" fill="#0d1117" stroke="' +
         SX_DIM + '" stroke-width="1"/>');

  /* Ticks every 2.5 degrees of frame. The numbers are twice that, which is the
     whole trick of the instrument and is why they are worth drawing on. */
  for (let d = 60; d <= 120.01; d += 2.5) {
    const major = Math.abs(d % 5) < 0.01;
    g.push('<line x1="' + xy(at(d, R)) .replace(' ', '" y1="') + '" x2="' +
           xy(at(d, major ? R - 14 : R - 8)).replace(' ', '" y2="') +
           '" stroke="' + SX_INK + '" stroke-width="' + (major ? 1.1 : 0.6) + '"/>');
    if (Math.abs(d - 60) % 30 < 0.01) {          // 0, 60, 120 only: enough to
                                                 // make the point, and it
                                                 // leaves room for the callouts
      const t = at(d, R + 20);
      g.push('<text x="' + t[0].toFixed(1) + '" y="' + t[1].toFixed(1) +
             '" fill="' + SX_INK + '" font-size="11" text-anchor="middle" ' +
             'dominant-baseline="middle">' + Math.round((d - 60) * 2) + '</text>');
    }
  }

  g.push('<line x1="' + P[0] + '" y1="' + P[1] + '" x2="' + arm[0].toFixed(1) +
         '" y2="' + arm[1].toFixed(1) + '" stroke="' + SX_INK +
         '" stroke-width="8" stroke-linecap="round"/>');
  g.push('<line x1="' + P[0] + '" y1="' + P[1] + '" x2="' + arm[0].toFixed(1) +
         '" y2="' + arm[1].toFixed(1) + '" stroke="#c9d4e0" stroke-width="2.4"/>');
  g.push('<circle cx="' + arm[0].toFixed(1) + '" cy="' + arm[1].toFixed(1) +
         '" r="15" fill="#151b23" stroke="' + SX_INK + '" stroke-width="1.6"/>');
  g.push('<circle cx="' + arm[0].toFixed(1) + '" cy="' + arm[1].toFixed(1) +
         '" r="7.5" fill="' + SX_DIM + '"/>');
  g.push('<g transform="translate(' + P[0] + ',' + P[1] + ') rotate(-22)">' +
         '<rect x="-3.5" y="-20" width="7" height="40" rx="1.5" fill="#dfe7ef" ' +
         'stroke="' + SX_LINE + '"/></g>');

  g.push('<g transform="translate(240,198) rotate(-58)">' +
         '<rect x="-3.5" y="-21" width="7" height="21" rx="1.5" fill="#dfe7ef" ' +
         'stroke="' + SX_LINE + '"/>' +
         '<rect x="-3.5" y="0" width="7" height="21" rx="1.5" fill="none" ' +
         'stroke="' + SX_GLASS + '" stroke-dasharray="3 2"/></g>');
  g.push('<g transform="translate(289,144) rotate(-58)">' +
         '<rect x="-12" y="-4" width="10" height="17" fill="#8a6427"/>' +
         '<rect x="-1" y="-4" width="10" height="17" fill="#5c421d"/></g>');
  g.push('<g transform="translate(207,250) rotate(-58)">' +
         '<rect x="-5" y="-4" width="10" height="15" fill="#3a4a5a"/></g>');
  g.push('<rect x="112" y="190" width="116" height="18" rx="6" fill="#151b23" ' +
         'stroke="' + SX_INK + '" stroke-width="1.3"/>');
  g.push('<circle cx="112" cy="199" r="11" fill="#0d1117" stroke="' + SX_INK +
         '" stroke-width="1.3"/>');
  g.push('<rect x="356" y="140" width="27" height="78" rx="12" fill="#20160c" ' +
         'stroke="' + SX_LINE + '" stroke-width="1.2"/>');

  /* Numbered callouts against a list, rather than leader lines to text this
     code cannot measure and therefore cannot aim. */
  const marks = [[330, 74], [296, 158], [285, 126], [369, 150],
                 [366, 300], [222, 212], [196, 262], [150, 199], [212, 306]];
  const leads = [null, [318, 170], null, null, [325, 292], [236, 202],
                 [205, 252], null, [244, 276]];
  leads.forEach((l, i) => {
    if (l) g.push('<line x1="' + marks[i][0] + '" y1="' + marks[i][1] +
                  '" x2="' + l[0] + '" y2="' + l[1] + '" stroke="' + SX_LINE +
                  '" stroke-width="0.9"/>');
  });
  marks.forEach((m, i) => {
    g.push('<circle cx="' + m[0].toFixed(1) + '" cy="' + m[1].toFixed(1) +
           '" r="10" fill="#0d1117" stroke="' + SX_SUN + '" stroke-width="1.4"/>');
    g.push('<text x="' + m[0].toFixed(1) + '" y="' + m[1].toFixed(1) +
           '" fill="' + SX_SUN + '" font-size="11" text-anchor="middle" ' +
           'dominant-baseline="central">' + (i + 1) + '</text>');
  });

  const legend = [
    'Index mirror, fully silvered. It is fixed to the arm, so it turns when the arm does.',
    'Index arm. Swinging it is how you bring the sun down.',
    'Index shades. These go in <b>before</b> the instrument comes near your eye.',
    'Handle, on the back. The frame is held, never the arm.',
    'Micrometer drum and vernier: degrees come off the arc, minutes off here.',
    'Horizon glass. Silvered on one half, clear on the other, so you see the reflected sun and the real horizon at once.',
    'Horizon shades, for glare coming off water.',
    'Telescope. It looks at the horizon glass, not at the sky.',
    'The arc. Sixty degrees of frame &mdash; that is where the name comes from &mdash; graduated to 120.',
  ];
  return '<div class="row" style="gap:1.1rem;align-items:flex-start;flex-wrap:wrap">' +
    '<div style="flex:1 1 380px;min-width:300px">' +
      '<svg viewBox="0 0 470 330" style="width:100%">' + g.join('') + '</svg></div>' +
    '<div style="flex:1 1 250px;min-width:240px"><ol class="small muted" ' +
      'style="margin:0;padding-left:1.3rem;line-height:1.45">' +
      legend.map(t => '<li>' + t + '</li>').join('') + '</ol></div></div>';
}

/* --- 2. why it works at all -----------------------------------------------
   The part nobody guesses: you are not looking at the sun through the
   instrument. You are looking straight ahead at the horizon, through a piece
   of clear glass - and the sun has been folded down onto it by two mirrors.
   Both arrive at the same eye at the same instant, which is what makes the
   comparison possible from a moving deck. */
function sxOptics() {
  const SUN = [608, 56], IM = [558, 170], HG = [252, 238], EYE = [92, 266];
  const g = [];

  /* A mirror at b turning a ray a->b into b->c lies along the bisector, so it
     is drawn at the angle it would really sit at rather than a guessed one.
     Getting this wrong is what made the first attempt read as a straight
     line with a kink in it. */
  const unit = (p, q) => {
    const dx = q[0] - p[0], dy = q[1] - p[1], m = Math.hypot(dx, dy);
    return [dx / m, dy / m];
  };
  const mirrorDeg = (a, b, c) => {
    const u = unit(a, b), v = unit(b, c);
    const n = [v[0] - u[0], v[1] - u[1]];
    return Math.atan2(n[1], n[0]) * 180 / Math.PI + 90;
  };

  g.push('<line x1="690" y1="' + EYE[1] + '" x2="' + EYE[0] + '" y2="' + EYE[1] +
         '" stroke="' + SX_GLASS + '" stroke-width="1.8"/>');
  g.push('<text x="688" y="' + (EYE[1] + 18) + '" fill="' + SX_GLASS +
         '" font-size="11" text-anchor="end">the horizon, straight through the clear half</text>');

  g.push('<circle cx="' + SUN[0] + '" cy="' + SUN[1] + '" r="18" fill="' + SX_SUN + '"/>');
  for (let a = 0; a < 360; a += 45) {
    const rad = a * Math.PI / 180;
    g.push('<line x1="' + (SUN[0] + 24 * Math.cos(rad)).toFixed(1) + '" y1="' +
           (SUN[1] + 24 * Math.sin(rad)).toFixed(1) + '" x2="' +
           (SUN[0] + 33 * Math.cos(rad)).toFixed(1) + '" y2="' +
           (SUN[1] + 33 * Math.sin(rad)).toFixed(1) + '" stroke="' + SX_SUN +
           '" stroke-width="1.7"/>');
  }

  g.push('<polyline points="' + (SUN[0] - 8) + ',' + (SUN[1] + 24) + ' ' +
         IM + ' ' + HG + ' ' + EYE + '" fill="none" stroke="' + SX_SUN +
         '" stroke-width="2.2" stroke-linejoin="round"/>');
  /* Arrowheads placed along each leg, pointing the way the light travels. */
  [[SUN, IM, 0.55], [IM, HG, 0.5], [HG, EYE, 0.5]].forEach(([a, b, t]) => {
    const x = a[0] + (b[0] - a[0]) * t, y = a[1] + (b[1] - a[1]) * t;
    const deg = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
    g.push('<path d="M -6 -6 L 5 0 L -6 6" fill="none" stroke="' + SX_SUN +
           '" stroke-width="2" transform="translate(' + x.toFixed(1) + ',' +
           y.toFixed(1) + ') rotate(' + deg.toFixed(1) + ')"/>');
  });

  g.push('<g transform="translate(' + IM[0] + ',' + IM[1] + ') rotate(' +
         mirrorDeg(SUN, IM, HG).toFixed(1) + ')">' +
         '<rect x="-4" y="-30" width="8" height="60" rx="2" fill="#dfe7ef" ' +
         'stroke="' + SX_LINE + '"/></g>');
  g.push('<g transform="translate(' + HG[0] + ',' + HG[1] + ') rotate(' +
         mirrorDeg(IM, HG, EYE).toFixed(1) + ')">' +
         '<rect x="-4" y="-46" width="8" height="46" rx="2" fill="#dfe7ef" ' +
         'stroke="' + SX_LINE + '"/>' +
         '<rect x="-4" y="0" width="8" height="46" rx="2" fill="none" stroke="' +
         SX_GLASS + '" stroke-width="1.4" stroke-dasharray="4 3"/></g>');

  g.push('<circle cx="' + EYE[0] + '" cy="' + EYE[1] + '" r="16" fill="#151b23" ' +
         'stroke="' + SX_INK + '" stroke-width="1.6"/>');
  g.push('<circle cx="' + EYE[0] + '" cy="' + EYE[1] + '" r="5.5" fill="' + SX_INK + '"/>');

  g.push('<text x="' + EYE[0] + '" y="304" fill="' + SX_INK + '" font-size="11" ' +
         'text-anchor="middle">your eye</text>');
  g.push('<text x="' + (IM[0] - 22) + '" y="' + (IM[1] + 56) + '" fill="' + SX_INK +
         '" font-size="11" text-anchor="end">index mirror, on the arm</text>');
  g.push('<text x="' + (HG[0] + 20) + '" y="192" fill="' + SX_INK +
         '" font-size="11">horizon glass &mdash; silvered above&hellip;</text>');
  g.push('<text x="' + (HG[0] + 20) + '" y="300" fill="' + SX_GLASS +
         '" font-size="11">&hellip;and clear below</text>');
  g.push('<text x="16" y="40" fill="' + SX_SUN + '" font-size="12.5">' +
         'Swing the arm and the sun slides down your eyepiece to meet the horizon.</text>');
  g.push('<text x="16" y="62" fill="' + SX_INK + '" font-size="11">' +
         'Turn a mirror through an angle and the beam turns through twice it,</text>');
  g.push('<text x="16" y="79" fill="' + SX_INK + '" font-size="11">' +
         'which is why sixty degrees of frame is graduated to a hundred and twenty.</text>');
  return '<svg viewBox="0 0 700 320" style="width:100%;max-width:700px">' +
    g.join('') + '</svg>';
}

/* --- 3. what you actually see, step by step -------------------------------- */
const SX_VIEW = [
  {title: 'Shades in, arc at zero, look at the sun',
   note: 'Set the arc to zero and put the index shades in <b>before</b> the ' +
         'instrument comes up to your eye. Now look straight at the sun ' +
         'through it. Both images sit together, because at zero the mirrors ' +
         'are parallel.',
   suns: [[0, -46, 1]], horizon: null},
  {title: 'Swing the arm: the sun comes down',
   note: 'Keeping the sun in view, turn the index arm. Its image slides down ' +
         'the field. Follow it down, lowering the instrument as you go, until ' +
         'the horizon comes into the bottom of the view.',
   suns: [[0, -46, .25], [0, 4, 1]], horizon: 64, arrow: true},
  {title: 'Rock it: the sun swings an arc',
   note: 'Tilt the sextant slowly side to side. The sun swings through an arc ' +
         'and dips lowest when the instrument is truly vertical. <b>That</b> ' +
         'is the reading &mdash; a sight taken without rocking is always too high.',
   suns: [[-58, 8, .3], [0, 30, 1], [58, 8, .3]], horizon: 64, swing: true},
  {title: 'Contact: lower limb just kisses the horizon',
   note: 'At the bottom of the swing, turn the micrometer until the sun’s ' +
         'lower edge sits exactly on the horizon &mdash; touching, not ' +
         'overlapping. Call the instant. <b>Then</b> read the arc; it will not move.',
   suns: [[0, 42, 1]], horizon: 64, contact: true},
  {title: 'Inland: the same thing, twice over',
   note: 'With a pan of water there is no horizon, so you bring the real sun ' +
         'down to its own reflection until the two discs touch. The arc then ' +
         'reads <b>twice</b> the altitude &mdash; type in what it says and let ' +
         'ELMER halve it.',
   suns: [[0, -13, 1], [0, 29, .55]], horizon: null, pan: true},
];

function sxEyepiece(step) {
  const v = SX_VIEW[step] || SX_VIEW[0];
  const CX = 150, CY = 140, RAD = 112, g = [];
  g.push('<defs><clipPath id="sx-field"><circle cx="' + CX + '" cy="' + CY +
         '" r="' + RAD + '"/></clipPath></defs>');
  g.push('<circle cx="' + CX + '" cy="' + CY + '" r="' + RAD +
         '" fill="#0b1015" stroke="' + SX_LINE + '" stroke-width="3"/>');
  g.push('<g clip-path="url(#sx-field)">');
  if (v.horizon !== null && v.horizon !== undefined) {
    const y = CY + v.horizon;
    g.push('<rect x="' + (CX - RAD) + '" y="' + y + '" width="' + (RAD * 2) +
           '" height="' + RAD + '" fill="#111c26"/>');
    g.push('<line x1="' + (CX - RAD) + '" y1="' + y + '" x2="' + (CX + RAD) +
           '" y2="' + y + '" stroke="' + SX_GLASS + '" stroke-width="2"/>');
  }
  if (v.pan) {
    g.push('<line x1="' + (CX - RAD) + '" y1="' + (CY + 8) + '" x2="' +
           (CX + RAD) + '" y2="' + (CY + 8) + '" stroke="' + SX_DIM +
           '" stroke-width="1" stroke-dasharray="4 4"/>');
  }
  if (v.swing) {
    g.push('<path d="M ' + (CX - 76) + ' ' + (CY - 6) + ' Q ' + CX + ' ' +
           (CY + 56) + ' ' + (CX + 76) + ' ' + (CY - 6) + '" fill="none" ' +
           'stroke="' + SX_SUN + '" stroke-width="1" stroke-dasharray="3 3" ' +
           'opacity=".65"/>');
  }
  if (v.arrow) {
    g.push('<path d="M ' + (CX + 62) + ' ' + (CY - 40) + ' L ' + (CX + 62) +
           ' ' + (CY - 6) + '" stroke="' + SX_SUN + '" stroke-width="1.6" ' +
           'opacity=".8"/><path d="M ' + (CX + 56) + ' ' + (CY - 12) + ' L ' +
           (CX + 62) + ' ' + (CY - 2) + ' L ' + (CX + 68) + ' ' + (CY - 12) +
           '" fill="none" stroke="' + SX_SUN + '" stroke-width="1.6" opacity=".8"/>');
  }
  v.suns.forEach(([dx, dy, op]) =>
    g.push('<circle cx="' + (CX + dx) + '" cy="' + (CY + dy) + '" r="21" fill="' +
           SX_SUN + '" opacity="' + op + '"/>'));
  if (v.contact) {
    g.push('<circle cx="' + CX + '" cy="' + (CY + 42) + '" r="21" fill="none" ' +
           'stroke="' + SX_OK + '" stroke-width="2"/>');
  }
  g.push('</g>');
  return '<svg viewBox="0 0 300 300" style="width:100%;max-width:300px">' +
    g.join('') + '</svg>';
}

function sxShowStep(n) {
  const view = document.getElementById('sx-eyepiece');
  if (!view) return;
  const step = Math.max(0, Math.min(SX_VIEW.length - 1, n));
  view.dataset.step = step;
  view.innerHTML = sxEyepiece(step);
  document.getElementById('sx-step-title').innerHTML =
    '<b>' + (step + 1) + '.</b> ' + SX_VIEW[step].title;
  document.getElementById('sx-step-note').innerHTML = SX_VIEW[step].note;
  document.querySelectorAll('#sx-steps button').forEach((b, i) => {
    b.classList.toggle('primary', i === step);
    b.classList.toggle('ghost', i !== step);
  });
}

function sxDrawArt() {
  const a = document.getElementById('sx-instrument');
  if (!a || a.dataset.drawn) return;
  a.innerHTML = sxInstrument();
  document.getElementById('sx-optics').innerHTML = sxOptics();
  const steps = document.getElementById('sx-steps');
  steps.innerHTML = SX_VIEW.map((v, i) =>
    '<button class="btn sm ghost" data-step="' + i + '">' + (i + 1) + '</button>').join('');
  steps.addEventListener('click', e => {
    const b = e.target.closest('button[data-step]');
    if (b) sxShowStep(+b.dataset.step);
  });
  sxShowStep(0);
  a.dataset.drawn = '1';
}

/* A worked example, because "here is a form, take three sights" asks somebody
   to buy an instrument before they can find out whether any of this is real.
   These are the altitudes the sun genuinely had over a point in the Boundary
   Waters on 8 September 2026, rounded to the tenth of a minute a sextant can
   actually be read to. Pressing the button fills the form and works it out, so
   the first time anybody sees the arithmetic run it is running on numbers that
   land somewhere checkable rather than on their own first shaky sight. */
const SX_DEMO = {
  date: '2026-09-08', horizon: 'artificial', index: 0, height: 0,
  where: 'a lake in the Boundary Waters, about 20 miles east of Ely',
  truth: {lat: 47.95, lon: -91.50, grid: 'EN47fw'},
  sights: [
    {deg: 67, min: 3.0,  time: '15:10:00', limb: 'lower'},
    {deg: 94, min: 15.7, time: '18:20:00', limb: 'lower'},
    {deg: 64, min: 43.4, time: '21:05:00', limb: 'lower'},
  ],
};

function sxLoadDemo() {
  document.getElementById('sx-horizon').value = SX_DEMO.horizon;
  document.getElementById('sx-horizon').dispatchEvent(new Event('change'));
  document.getElementById('sx-index').value = SX_DEMO.index;
  document.getElementById('sx-height').value = SX_DEMO.height;
  document.getElementById('sx-date').value = SX_DEMO.date;
  document.getElementById('sx-useqth').checked = false;
  SX_ROWS.innerHTML = SX_DEMO.sights.map((_, i) => sxRow(i + 1)).join('');
  [...SX_ROWS.rows].forEach((row, i) => {
    const sight = SX_DEMO.sights[i];
    row.querySelector('.sx-deg').value = sight.deg;
    row.querySelector('.sx-min').value = sight.min;
    row.querySelector('.sx-time').value = sight.time;
    row.querySelector('.sx-limb').value = sight.limb;
  });
  sxSolve();
}

function sxRenumber() {
  [...SX_ROWS.rows].forEach((r, i) => { r.cells[0].textContent = i + 1; });
}

if (SX_ROWS) {
  SX_ROWS.innerHTML = sxRow(1) + sxRow(2) + sxRow(3);
  const today = new Date();
  document.getElementById('sx-date').value =
    today.toISOString().slice(0, 10);

  document.getElementById('sx-add').addEventListener('click', () => {
    if (SX_ROWS.rows.length >= 8) return;
    SX_ROWS.insertAdjacentHTML('beforeend', sxRow(SX_ROWS.rows.length + 1));
    sxRenumber();
  });

  /* Stamping the time from the machine's own clock, which is the one thing in
     this that has to be right - so it goes in to the second. */
  SX_ROWS.addEventListener('click', e => {
    const btn = e.target.closest('.sx-now');
    if (!btn) return;
    e.preventDefault();
    const now = new Date();
    btn.closest('tr').querySelector('.sx-time').value =
      now.toISOString().slice(11, 19);
    document.getElementById('sx-date').value = now.toISOString().slice(0, 10);
  });

  /* Dip is a sea-horizon correction. With a pan of water there is no horizon
     to be above, so the field says so rather than sitting there inviting a
     number that will be ignored. */
  const horizon = document.getElementById('sx-horizon');
  const heightNote = document.getElementById('sx-height-note');
  /* The three ways of taking a sight want three different sets of numbers,
     and offering fields that will be ignored is how people come to distrust a
     tool. Dip belongs to a sea horizon; a limb belongs to an instrument you
     sight through; a stick has neither. */
  const syncHorizon = () => {
    const how = horizon.value;
    const shadow = how === 'shadow';
    const sea = how === 'sea';
    document.getElementById('sx-height').disabled = !sea;
    heightNote.textContent = sea ? '' : '— no dip without a sea horizon';
    document.getElementById('sx-index').disabled = shadow;
    document.getElementById('sx-shadow-note').hidden = !shadow;
    document.getElementById('sx-head-angle').textContent =
      shadow ? 'Stick height / shadow length' : 'Sextant reading';
    document.getElementById('sx-head-limb').textContent = shadow ? '' : 'Limb';
    [...SX_ROWS.rows].forEach(r => {
      r.querySelector('.sx-deg').placeholder = shadow ? 'height' : 'deg';
      r.querySelector('.sx-min').placeholder = shadow ? 'shadow' : 'min';
      r.querySelector('.sx-deg').step = shadow ? 0.01 : 1;
      r.querySelector('.sx-min').step = shadow ? 0.01 : 0.1;
      r.querySelector('.sx-min').max = shadow ? 100000 : 59.9;
      r.querySelector('.sx-limb').hidden = shadow;
    });
  };
  horizon.addEventListener('change', syncHorizon);
  syncHorizon();

  document.getElementById('sx-go').addEventListener('click', sxSolve);
  /* The drawings cost nothing to build but there is no reason to build them
     for somebody who never opens the fold. */
  const art = document.getElementById('sx-art');
  if (art) art.addEventListener('toggle', () => { if (art.open) sxDrawArt(); });
  const demo = document.getElementById('sx-demo');
  if (demo) demo.addEventListener('click', sxLoadDemo);
}

async function sxSolve() {
  const out = document.getElementById('sx-out');
  const date = document.getElementById('sx-date').value;
  if (!date) { out.innerHTML = '<div class="watchout">Set the UTC date.</div>'; return; }

  const how = document.getElementById('sx-horizon').value;
  const shadow = how === 'shadow';
  const sights = [];
  for (const row of SX_ROWS.rows) {
    const a = parseFloat(row.querySelector('.sx-deg').value);
    const b = parseFloat(row.querySelector('.sx-min').value);
    const time = row.querySelector('.sx-time').value;
    if (!isFinite(a) || !time) continue;        // a blank row is not an error
    let hs;
    if (shadow) {
      if (!isFinite(b) || b <= 0 || a <= 0) continue;
      hs = Math.atan2(a, b) * 180 / Math.PI;    // atan(height / shadow)
    } else {
      hs = a + (isFinite(b) ? b : 0) / 60;
    }
    sights.push({hs: hs, when: date + 'T' + time + 'Z',
                 limb: shadow ? 'centre' : row.querySelector('.sx-limb').value});
  }
  if (sights.length < 2) {
    out.innerHTML = '<div class="watchout">Two sights at least &mdash; one ' +
      'is a circle, not a place. Fill in the angle and the time for each.</div>';
    return;
  }

  out.innerHTML = '<div class="small muted">working&hellip;</div>';
  let d;
  try {
    d = await postJSON('/api/celestial/fix', {
      sights: sights,
      horizon: how,
      height_ft: parseFloat(document.getElementById('sx-height').value) || 0,
      index_error_arcmin: parseFloat(document.getElementById('sx-index').value) || 0,
      use_qth: document.getElementById('sx-useqth').checked,
    });
  } catch (e) {
    out.innerHTML = '<div class="watchout">' +
      escapeHTML((e && e.message) || 'that did not work') + '</div>';
    return;
  }
  if (!d.ok) {
    out.innerHTML = '<div class="watchout">' + escapeHTML(d.error) + '</div>';
    return;
  }
  out.innerHTML = sxWorking(d) + sxAnswer(d) + sxWalkOut(d);
}

/* A latitude and a longitude are not what somebody in trouble needs. "Which
   way do I walk, and how far" is, and the gap between the two is a skill
   nobody has any more. So the fix is followed by the part that uses it. */
/* Charts and topographic maps are ruled in degrees and minutes, not in the
   decimal degrees a computer likes, and the margin ticks somebody has to count
   along are minutes. Handing over only the decimal form leaves them to do a
   conversion in the one situation where arithmetic is hardest. */
function dm(value, pos, neg) {
  const hemi = value >= 0 ? pos : neg;
  const abs = Math.abs(value);
  const deg = Math.floor(abs);
  return deg + '&deg; ' + ((abs - deg) * 60).toFixed(1) + '&prime; ' + hemi;
}

function sxWalkOut(d) {
  const north = d.north || {};
  const places = d.landfall || [];
  const first = places[0];

  const rows = places.map(p =>
    '<tr><td><b>' + escapeHTML(p.name) +
      (p.region ? ' <span class="muted">' + escapeHTML(p.region) + '</span>' : '') +
    '</b></td>' +
    '<td class="mono">' + p.miles + ' mi</td>' +
    '<td class="mono">' + p.bearing + '&deg; true</td>' +
    '<td class="mono muted">' + compass(p.bearing) + '</td></tr>').join('');

  return '<div class="panel-title mt">Putting it on a map, and walking out</div>' +

    '<div class="small muted">Charts and topographic maps are ruled in degrees ' +
      'and minutes, and the ticks in the margin you count along are minutes. ' +
      'So the same position, in the form the map is in:</div>' +
    '<div class="mono mt" style="font-size:1.05rem">' +
      dm(d.lat, 'N', 'S') + ' &nbsp; ' + dm(d.lon, 'E', 'W') + '</div>' +
    '<div class="tiny muted">Find the latitude on the left and right edges, the ' +
      'longitude on the top and bottom, lay a straight edge between each pair, ' +
      'and you are where they cross &mdash; inside a circle of about <b>' +
      d.uncertainty_nm + ' nautical miles</b>, which is ' +
      Math.round(d.uncertainty_nm * 1.151) + ' statute miles and is the circle ' +
      'to draw rather than the dot.</div>' +

    (rows
      ? '<div class="panel-title mt" style="margin-bottom:.3rem">What is near you</div>' +
        '<table class="data" style="max-width:560px"><tbody>' + rows + '</tbody></table>' +
        '<div class="tiny muted">' +
          (d.landfall_from === 'bundled'
            ? 'From the list that ships with ELMER, which is a few hundred ' +
              'North American towns &mdash; so it names the ones worth walking ' +
              'to and misses the hamlet down the road.'
            : 'From the places ELMER looked up for this area while it had a ' +
              'network.') +
        '</div>'
      : '<div class="small muted mt">ELMER has no place list for here, so the ' +
        'position is all it can give you. On a paper map it is still the whole ' +
        'answer.</div>') +

    '<div class="panel-title mt" style="margin-bottom:.3rem">Finding true north ' +
      'without a compass</div>' +
    '<div class="small muted">Those bearings are <b>true</b>, not magnetic, and ' +
      'a compass points at neither without knowing the local declination. You do ' +
      'not need one: the sun that gave you the fix gives you north as well. ' +
      (north.sun_azimuth !== undefined
        ? 'Right now, from where you are, the sun bears <b>' + north.sun_azimuth +
          '&deg; true</b> and stands <b>' + north.sun_altitude + '&deg;</b> up. ' +
          'Face it, and true north is <b>' +
          Math.round(((360 - north.sun_azimuth) % 360)) + '&deg; to your right' +
          '</b> &mdash; or simply that the sun is ' + compass(north.sun_azimuth) +
          ' of you. '
        : '') +
      'Sight along a stick to the sun, turn off the angle, and you have a ' +
      'reference good to a degree or two, which is better than a compass with ' +
      'an unknown correction.</div>' +

    '<div class="panel-title mt" style="margin-bottom:.3rem">Then walk it</div>' +
    '<div class="small muted">' +
      (first
        ? '<b>Do not walk at ' + escapeHTML(first.name) + '.</b> It is a point, ' +
          'your position has a ' + d.uncertainty_nm + ' nm circle around it, ' +
          'and you will not know which side of the point you came out on. Walk ' +
          'at a <b>line</b> instead &mdash; a road, a river, a shoreline, a ' +
          'power line, a railway &mdash; because a line is impossible to miss ' +
          'and it tells you where you are the moment you reach it. '
        : '<b>Walk at a line, not at a point</b> &mdash; a road, a river, a ' +
          'shoreline, a power line. A point can be missed and a line cannot. ') +
      'Then <b>aim off</b>: pick a heading deliberately to one side of where ' +
      'the line meets your target, ten or fifteen degrees of it, so that when ' +
      'you hit the line you already know which way to turn along it. Aiming ' +
      'straight at a thing means arriving at the line with no idea whether it ' +
      'is left or right, and half of those guesses are wrong.</div>' +
    '<div class="small muted mt">Take a fresh set of sights after a few hours ' +
      'of walking. Two fixes are a track: they tell you your speed over the ' +
      'ground and whether you are actually going where you meant to, which one ' +
      'fix cannot. On foot in rough country three miles in an hour is good ' +
      'going, and it is usually less.</div>';
}

/* Every correction, with its sign and its reason. */
function sxWorking(d) {
  const shadow = document.getElementById('sx-horizon').value === 'shadow';
  return '<div class="panel-title mt">Working each sight up</div>' +
    '<div class="tiny muted">' + (shadow
      ? 'The angle a shadow gives you is not quite the sun\'s altitude ' +
        'either: the atmosphere has lifted it, and you are standing on a ' +
        'planet with a radius rather than at its centre.'
      : 'A sextant reading is not an altitude. It is an altitude plus the ' +
        'instrument, your height, the atmosphere, and the fact that you ' +
        'brought an edge of the sun down rather than a centre you cannot see.'
    ) + '</div>' +
    d.working.map(w =>
      '<table class="data mt" style="max-width:720px"><thead><tr>' +
        '<th colspan="3">Sight ' + w.n + ' &mdash; ' +
        escapeHTML(w.when.slice(11, 19)) + ' UTC' +
        (shadow ? '' : ', ' + escapeHTML(w.limb) + ' limb') +
        '</th></tr></thead><tbody>' +
      w.steps.map(s =>
        '<tr><td>' + escapeHTML(s.name) + '</td>' +
        '<td class="mono">' + s.value.toFixed(4) + '&deg;</td>' +
        '<td class="tiny muted">' + escapeHTML(s.why) + '</td></tr>').join('') +
      '<tr><td><b>true altitude</b></td><td class="mono"><b>' +
        w.ho.toFixed(4) + '&deg;</b></td>' +
        '<td class="tiny muted">what the sky actually did, good to about ' +
        w.sigma_arcmin + '&prime; the way you took it</td></tr>' +
      '</tbody></table>').join('');
}

function sxAnswer(d) {
  const cls = d.geometry === 'good' ? 'good' : d.geometry === 'usable' ? 'warn' : 'bad';
  const alts = (d.alternatives || []).map(a =>
    '<li class="small"><span class="mono">' + a.lat.toFixed(3) + ', ' +
    a.lon.toFixed(3) + '</span> (' + escapeHTML(a.grid) + ') &mdash; ' +
    a.away_nm + ' nm away</li>').join('');

  return '<div class="panel-title mt">Where that puts you</div>' +
    '<div class="row" style="gap:1.4rem;flex-wrap:wrap;align-items:baseline">' +
      '<span style="font:700 1.7rem var(--mono);color:var(--amber)">' +
        escapeHTML(d.grid) + '</span>' +
      '<span class="mono">' + d.lat.toFixed(4) + ', ' + d.lon.toFixed(4) + '</span>' +
      '<span class="pill ' + cls + '">&plusmn;' + d.uncertainty_nm +
        ' nautical miles</span>' +
      '<span class="pill">' + escapeHTML(d.geometry) + ' geometry, ' +
        d.bearing_spread_deg + '&deg; apart</span>' +
    '</div>' +
    /* The residual is not the safety check and must not be dressed up as one:
       three sights taken minutes apart can agree beautifully with each other
       and with the wrong place. */
    '<div class="tiny muted mt">Your ' + d.sights + ' sights agree with each ' +
      'other to <b>' + d.rms_arcmin + '&prime;</b>. That is not the same as ' +
      'being right &mdash; sights close together in time agree easily and can ' +
      'agree on the wrong place, which is why the figure to read is the ' +
      '&plusmn;' + d.uncertainty_nm + ' nm, worked out from how widely the ' +
      'bearings were spread rather than from how neatly they fit.' +
      (d.hinted ? ' Your saved QTH was used to settle which crossing you are at.' : '') +
    '</div>' +
    (d.ambiguous
      ? '<div class="watchout mt"><b>Two places fit.</b> ' +
        escapeHTML(d.ambiguity_note) + '<ul>' + alts + '</ul></div>'
      : (alts ? '<div class="tiny muted mt">Other crossings considered and ' +
                'rejected:<ul>' + alts + '</ul></div>' : '')) +
    '<div class="row mt">' +
      '<button class="btn sm" id="sx-setqth" data-lat="' + d.lat +
        '" data-lon="' + d.lon + '">Set this as my QTH</button>' +
      '<span class="tiny muted">a four-character grid needs about 30 nm; ' +
      'six characters needs about 2</span>' +
    '</div>';
}

/* Handing the answer to the rest of the program, which is the point of having
   worked it out on a unit whose GPS may have nothing to say. */
document.addEventListener('click', async e => {
  const btn = e.target.closest('#sx-setqth');
  if (!btn) return;
  e.preventDefault();
  btn.disabled = true;
  try {
    await saveQTH({lat: +btn.dataset.lat, lon: +btn.dataset.lon,
                   name: 'By sextant', short: 'By sextant', kind: 'celestial',
                   grid: btn.closest('#sx-out').querySelector('span').textContent});
    toast('QTH set', 'from your sights');
  } catch (err) {
    btn.disabled = false;
  }
});
