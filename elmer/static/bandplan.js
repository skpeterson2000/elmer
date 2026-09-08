/* Band plan: colour by activity, shade what your license class may not use. */

const KIND_COLOUR = {
  cw: '#58a6ff', digital: '#bc8cff', phone: '#3fb950', image: '#ffb454',
  beacon: '#f85149', satellite: '#39d3d8', repeater: '#ff8f3f',
  simplex: '#c9d13a', calling: '#ffffff', special: '#8b98a5',
};

let bpData = null, bpRegional = null, bpBand = null, bpChannels = [];

function bpClass() { return document.getElementById('bp-class').value; }

/* Bands in the order somebody would actually reach for them, rather than in
   frequency order. The first one this licence can hold a conversation on is
   the one to open. */
const BP_PREFERRED = ['20 m', '40 m', '2 m', '10 m', '70 cm', '17 m', '15 m',
                      '80 m', '6 m', '12 m', '30 m', '1.25 m', '160 m'];

function bpHasPhone(band) {
  return (band.privileges || []).some(p => !/CW only|data only|RTTY only/i.test(p[2] || ''));
}

function bpDefaultBand() {
  for (const name of BP_PREFERRED) {
    const band = bpData.bands.find(b => b.name === name && bpHasPhone(b));
    if (band) return band.name;
  }
  const usable = bpData.bands.find(b => b.privileges.length);
  return (usable || bpData.bands[0]).name;
}
function bpState() { return document.getElementById('bp-state').value; }

async function bpLoad() {
  bpData = await api('/api/bandplan?class=' + encodeURIComponent(bpClass()));
  bpChannels = bpData.channels_60m || [];
  document.getElementById('bp-legend').innerHTML =
    bpData.kinds.map(([k, label]) =>
      '<span class="legend"><i style="background:' + KIND_COLOUR[k] + '"></i>' +
      escapeHTML(label) + '</span>').join('') +
    '<span class="legend"><i class="legend-gap"></i>outside your privileges</span>';

  document.getElementById('bp-bands').innerHTML = bpData.bands.map(b =>
    '<button class="btn sm ' + (b.name === bpBand ? 'primary' : 'ghost') +
    '" data-band="' + escapeHTML(b.name) + '">' + escapeHTML(b.name) + '</button>').join('');
  document.querySelectorAll('#bp-bands [data-band]').forEach(btn =>
    btn.addEventListener('click', () => {
      bpBand = btn.dataset.band;
      remember('bandplan.band', bpBand);
      /* In the address, so a band can be linked to and comes back on reload. */
      history.replaceState(null, '', '#' + bpBand.replace(/\s+/g, ''));
      bpRender();
    }));
  /* Which band to open on. A link asking for one wins; then the one you were
     last looking at, because leaving for the Lab and coming back should not
     cost you your place; and only then a default.

     The old default was the first band this class may legally touch, which is
     the lowest one - 160 m for a General, and for a Technician 80 m, where
     they may send CW and nothing else. Both are legal and neither is where
     anybody operates. A Technician who opens the band plan and is shown a
     band they can only key CW on has been told, accurately and unhelpfully,
     that this hobby is not for them yet. So the default is the first band on
     this list they have *phone* privileges on: 20 m for a General, 2 m for a
     Technician, which is where each of them actually is. */
  const asked = decodeURIComponent(location.hash.slice(1)).toLowerCase();
  const linked = asked && bpData.bands.find(
    b => b.name.replace(/\s+/g, '').toLowerCase() === asked.replace(/\s+/g, ''));
  const known = name => name && bpData.bands.some(b => b.name === name);

  if (linked) {
    bpBand = linked.name;
  } else if (!known(bpBand)) {
    const last = recall('bandplan.band');
    bpBand = known(last) ? last : bpDefaultBand();
  }
  remember('bandplan.band', bpBand);
  await bpLoadRegional();
  bpRender();
}

async function bpLoadRegional() {
  const st = bpState();
  if (!st) { bpRegional = null; return; }
  try {
    const r = await api('/api/bandplan/regional/' + encodeURIComponent(st));
    bpRegional = r.ok ? r : null;
  } catch (e) { bpRegional = null; }
}

/* 60 m is five 2.8 kHz channels and nothing in between, which on a bar 77 kHz
   wide is five slivers a reader could easily take for rounding. So they are
   named under the bar, at the frequency an operator actually dials - the
   suppressed carrier, 1.5 kHz below the channel centre the rules name. */
function channelTicks(band) {
  if (!band.channelised || !bpChannels.length) return '';
  const span = band.high - band.low;
  const at = f => ((f - band.low) / span) * 100;
  return '<div class="chanticks">' + bpChannels.map(c =>
    '<i style="left:' + at(c.centre).toFixed(3) + '%" title="' + c.name +
      ' — channel centre ' + c.centre.toFixed(4) + ' MHz, 2.8 kHz wide">' +
      '<b>' + c.n + '</b><span>' + c.dial.toFixed(4) + '</span></i>').join('') +
    '</div>';
}

function bpRender() {
  document.querySelectorAll('#bp-bands [data-band]').forEach(b => {
    b.classList.toggle('primary', b.dataset.band === bpBand);
    b.classList.toggle('ghost', b.dataset.band !== bpBand);
  });
  const band = bpData.bands.find(b => b.name === bpBand);
  if (!band) return;
  const span = band.high - band.low;
  const pct = f => ((f - band.low) / span) * 100;

  /* The bar: activity in colour, privilege gaps hatched over the top. Each
     segment carries what it needs for the hover card and the click, so the
     bar becomes a way in rather than only a picture. */
  const bars = band.activity.map((a, i) => {
    const w = Math.max(0.35, pct(a.high) - pct(a.low));
    return '<i class="seg" data-seg="' + i + '" style="left:' +
      pct(a.low).toFixed(3) + '%;width:' + w.toFixed(3) + '%;background:' +
      KIND_COLOUR[a.kind] + '"></i>';
  }).join('');
  const gaps = band.gaps.map(([lo, hi]) =>
    '<i class="seg gap" style="left:' + pct(lo).toFixed(3) + '%;width:' +
    Math.max(0.3, pct(hi) - pct(lo)).toFixed(3) + '%" title="outside ' +
    escapeHTML(bpClass()) + ' privileges"></i>').join('');

  const priv = band.privileges.length
    ? band.privileges.map(([lo, hi, modes]) =>
        '<li><span class="mono">' + lo + ' – ' + hi + ' MHz</span> — ' +
        escapeHTML(modes) + '</li>').join('')
    : '<li class="muted">No privileges on this band for ' + escapeHTML(bpClass()) + '.</li>';

  /* Three answers, not two: convention and law do not share their edges, so a
     segment can be partly yours. A bare range in that column is a puzzle - the
     reader sees that something is different without being told what - so the
     reason travels with it, in words, next to the thing it is about. */
  const rows = band.activity.map(a => {
    const you = a.you || {state: 'no'};
    const mark = you.state === 'yes'
      ? '<span class="pill good">yes</span>'
      : you.state === 'part'
        ? '<span class="pill warn">' + you.low + '&ndash;' + you.high + '</span>'
        : '<span class="pill bad">no</span>';
    const why = you.note && you.state !== 'yes'
      ? '<div class="why ' + you.state + '">' + escapeHTML(you.note) + '</div>' : '';
    return '<tr class="' + (you.state === 'no' ? 'denied' : '') + '">' +
      '<td class="mono tiny">' + a.low + (a.high !== a.low ? '<br>' + a.high : '') + '</td>' +
      '<td><span class="dot" style="background:' + KIND_COLOUR[a.kind] + '"></span>' +
        escapeHTML((bpData.kinds.find(k => k[0] === a.kind) || [])[1] || a.kind) + '</td>' +
      '<td class="small">' + escapeHTML(a.label) + why + '</td>' +
      '<td>' + mark + '</td></tr>';
  }).join('');

  /* A key: three states in an unlabelled column are not self explanatory
     however carefully the middle one is worded. */
  const key =
    '<div class="tiny muted bp-key">' +
      'Can you use it, in that mode? &nbsp;' +
      '<span class="pill good">yes</span> all of it &nbsp;&middot;&nbsp; ' +
      '<span class="pill warn">range</span> only that part, and the row says why ' +
      '&nbsp;&middot;&nbsp; <span class="pill bad">no</span> none of it' +
    '</div>';

  document.getElementById('bp-out').innerHTML =
    '<div class="panel">' +
      '<div class="spread"><h2 style="margin:0">' + escapeHTML(band.name) + '</h2>' +
      '<span class="mono tiny muted">' + band.low + ' – ' + band.high + ' MHz · ' +
        escapeHTML(band.group) + '</span></div>' +
      '<div class="bandbar">' + bars + gaps + '</div>' +
      channelTicks(band) +
      '<div class="bandscale"><span>' + band.low + '</span><span>' + band.high + '</span></div>' +
      conditionBar(band) +
      '<div class="grid cols-2 mt">' +
        '<div><div class="panel-title">Your privileges — 47 CFR 97.301</div>' +
          '<ul class="privlist">' + priv + '</ul></div>' +
        '<div><div class="panel-title">Where the activity is</div>' + key +
          '<table class="data"><tbody>' + rows + '</tbody></table></div>' +
      '</div>' +
    '</div>';

  bindSegments(band);

  const rbox = document.getElementById('bp-regional');
  const segs = bpRegional && (bpRegional.bands || {})[band.name];
  if (!segs) {
    rbox.innerHTML = bpState() && bpRegional
      ? '<div class="panel tight mt"><span class="muted small">' +
        escapeHTML(bpRegional.short) + ' publishes no plan for ' + escapeHTML(band.name) +
        '.</span></div>'
      : (bpState() ? '<div class="panel tight mt"><span class="muted small">' +
         'Could not reach the coordinator — showing national conventions only.</span></div>' : '');
    return;
  }
  rbox.innerHTML =
    '<div class="panel mt">' +
      '<div class="spread"><div class="panel-title" style="margin:0">' +
        escapeHTML(bpRegional.name) + ' — coordinated segments for ' + escapeHTML(band.name) +
      '</div><a class="tiny" href="' + bpRegional.plans_url + '" target="_blank" rel="noopener">' +
        'their published plan &rarr;</a></div>' +
      '<table class="data mt"><tbody>' + segs.map(sg =>
        '<tr><td class="mono tiny">' + sg.low + (sg.high !== sg.low ? '<br>' + sg.high : '') + '</td>' +
        '<td><span class="dot" style="background:' + (KIND_COLOUR[sg.kind] || '#8b98a5') + '"></span>' +
          escapeHTML(sg.kind) + '</td>' +
        '<td class="small">' + escapeHTML(sg.label) + '</td></tr>').join('') +
      '</tbody></table>' +
      '<div class="tiny muted" style="margin-top:.5rem">Fetched ' +
        escapeHTML(bpRegional.fetched || '') +
        (bpRegional.cached ? ' (cached)' : '') + '. ' + escapeHTML(bpRegional.note || '') + '</div>' +
    '</div>';
}

document.getElementById('bp-class').addEventListener('change', async () => {
  await postJSON('/api/settings', {license_class: bpClass()}).catch(() => {});
  bpLoad();
});
document.getElementById('bp-state').addEventListener('change', async () => {
  await postJSON('/api/settings', {state: bpState()}).catch(() => {});
  await bpLoadRegional(); bpRender();
});
/* The one-page picture: the bands drawn to scale, for pinning up. The full
   chart is the reference; this is the thing you actually look at. */
document.getElementById('bp-card').addEventListener('click', async () => {
  const btn = document.getElementById('bp-card');
  btn.disabled = true; btn.textContent = 'Building…';
  try {
    const res = await fetch('/api/bandplan/pdf', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({class: bpClass(), layout: 'card'})});
    if (!res.ok) throw new Error(res.status);
    /* Straight to it. A chart that lands in a downloads folder is behind the
       application on a machine with no way out of it and no way back. */
    location.href = (await res.json()).view;
  } catch (e) { toast('Could not build it', 'See data/elmer.log'); }
  btn.disabled = false; btn.textContent = 'One page (PDF)';
});

document.getElementById('bp-pdf').addEventListener('click', async () => {
  const btn = document.getElementById('bp-pdf');
  btn.disabled = true; btn.textContent = 'Building…';
  try {
    const res = await fetch('/api/bandplan/pdf', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({class: bpClass(), state: bpState(),
                            bands: bpData.bands.map(b => b.name),
                            interop: !!(document.getElementById('bp-interop') || {}).checked})});
    if (!res.ok) throw new Error(res.status);
    location.href = (await res.json()).view;
  } catch (e) { toast('Could not build the chart', 'See data/elmer.log'); }
  btn.disabled = false; btn.textContent = 'Full chart (PDF)';
});

bpLoad();

/* Callsign lookup: the license knows the class, so the operator need not. */
const bpLookupBtn = document.getElementById('bp-lookup');
if (bpLookupBtn) {
  const field = document.getElementById('bp-call');
  const hint = document.getElementById('bp-call-hint');
  const run = async () => {
    const call = (field.value || '').trim().toUpperCase();
    if (!call) return;
    bpLookupBtn.disabled = true;
    hint.textContent = 'checking the FCC record…';
    try {
      const found = await api('/api/callsign/' + encodeURIComponent(call));
      if (!found.found) {
        hint.innerHTML = '<span style="color:var(--red)">' +
          escapeHTML(found.reason || 'no FCC record found') + '</span>';
      } else {
        await postJSON('/api/settings', {callsign: call});
        hint.textContent = 'found — reloading';
        location.reload();
      }
    } catch (e) {
      hint.innerHTML = '<span style="color:var(--red)">lookup unavailable ' +
        '&mdash; pick your class manually</span>';
    }
    bpLookupBtn.disabled = false;
  };
  bpLookupBtn.addEventListener('click', run);
  field.addEventListener('keydown', e => { if (e.key === 'Enter') run(); });
}

/* ---------- nationwide interoperability channels ----------
   Read out of the current NIFOG rather than transcribed, so the list is
   whatever CISA last published rather than whatever was true when this was
   written. Cached server-side; this only ever reads the cache. */
api('/api/nifog').then(d => {
  const box = document.getElementById('nifog-channels');
  if (!box) return;
  if (!d.have) {
    box.innerHTML = '<p class="small muted">ELMER can read the interoperability ' +
      'channels straight out of the current guide &mdash; run ' +
      '<span class="mono">./elmer.py --fetch-nifog</span> once and they appear ' +
      'here and on the printed chart.</p>';
    return;
  }
  /* Folded away by default. 59 rows of channels nobody here may transmit on
     should not be the biggest thing on the band plan page. */
  box.innerHTML =
    '<details class="nifog-more"><summary class="small">' +
      'Nationwide interoperability channels read from the guide (' + d.count +
      ') &mdash; for reference and monitoring</summary>' +
    '<p class="tiny muted" style="margin:.5rem 0">Read from NIFOG version ' +
      escapeHTML(d.version || '?') + ' (' + escapeHTML(d.dated || '') +
      '), fetched ' + escapeHTML(d.fetched) + '. ' + d.count + ' channels. ' +
      '<b>None of them is amateur spectrum.</b></p>' +
    d.bands.map(g =>
      '<div class="nifog-band"><div class="tiny mono muted">' + escapeHTML(g.band) +
      '</div><table class="data"><thead><tr><th>Channel</th><th>Use</th>' +
      '<th class="num">RX (MHz)</th><th>RX tone</th>' +
      '<th class="num">TX (MHz)</th><th>TX tone</th></tr></thead><tbody>' +
      g.channels.map(c =>
        '<tr><td class="mono"><b>' + escapeHTML(c.name) + '</b></td>' +
        '<td class="small">' + escapeHTML(c.use) + '</td>' +
        '<td class="num mono tiny">' + c.rx_mhz.toFixed(5).replace(/0+$/, '').replace(/\.$/, '.0') + '</td>' +
        '<td class="mono tiny">' + escapeHTML(c.rx_tone) + '</td>' +
        '<td class="num mono tiny">' + c.tx_mhz.toFixed(5).replace(/0+$/, '').replace(/\.$/, '.0') + '</td>' +
        '<td class="mono tiny">' + escapeHTML(c.tx_tone) + '</td></tr>').join('') +
      '</tbody></table></div>').join('') +
    '</details>';
}).catch(() => {});

/* ---------- the bar as a way in ----------

   Hovering a segment says what is there and whether the band is open right
   now; clicking one keeps that on screen and offers to carry the frequency
   into the antenna designer. The conditions come from the propagation feed
   already on the dashboard, matched to the band being looked at, so hovering
   costs nothing beyond the one fetch this page makes at load. */

let bpProp = null;

/* The outlook, not the snapshot: the same space weather, asked band by band
   and hour by hour. It costs no network of its own - the unit works it out
   from the reading the dashboard already fetched. */
api('/api/propagation/outlook').then(d => {
  bpProp = d.ok ? d : null;
  if (bpProp && bpData) bpRender();       // it arrived after the first draw
}).catch(() => {});

function conditionsFor(band) {
  if (!bpProp) return null;
  const key = band.name.replace(/\s+/g, '');
  return (bpProp.bands || []).find(b => b.band === key) || null;
}

/* ---------------------------------------------------- how good is it, now */
/* A wall chart rates a group of bands Poor, Fair or Good, twice a day. That
   answers "is it worth turning the radio on". It does not answer the question
   an operator is actually holding, which is whether to call CQ on SSB now or
   come back at eight o'clock and use CW - and the difference between those two
   is most of an evening. So: one number for this band at this hour, what it
   means for the mode, and the shape of the next day beside it.

   The number is a model and is labelled as one wherever it appears. It knows
   the sun's angle here, the MUF, and the state of the field; it knows nothing
   about your antenna, your power or the far end. What it is right about is the
   shape of the day, which is what timing is decided on. */

const QUALITY_CLASS = s =>
  s >= 80 ? 'q4' : s >= 60 ? 'q3' : s >= 35 ? 'q2' : s >= 15 ? 'q1' : 'q0';

function hourLabel(iso) {
  const d = new Date(iso);
  return String(d.getHours()).padStart(2, '0');
}

function forecastStrip(cond) {
  const rows = cond.hours || [];
  if (!rows.length) {
    return '<div class="tiny muted">Set a QTH on the ' +
      '<a href="/propagation">propagation page</a> and this becomes an ' +
      'hour-by-hour outlook for where you are &mdash; the sun\'s angle at your ' +
      'own location is most of what decides it.</div>';
  }
  const cells = rows.map((h, i) => {
    const label = hourLabel(h.at);
    // "now" under the first cell, then every sixth hour: enough to read the
    // shape against the clock without turning the strip into a ruler.
    const tick = i === 0 ? 'now' : (i % 6 === 0 ? label : '');
    return '<i class="fc ' + QUALITY_CLASS(h.score) + (i === 0 ? ' now' : '') +
      (h.day ? ' day' : '') +
      '" title="' + label + ':00 local — ' + h.score +
      '/100, MUF about ' + h.muf + ' MHz' + (h.day ? ', daylight' : ', dark') +
      '">' + (tick ? '<span>' + tick + '</span>' : '') + '</i>';
  }).join('');
  /* Said as an operator would say it: "now until eight", not a pair of
     timestamps - and a band that never shuts should not be reported as
     open from four o'clock until four o'clock. */
  const first = rows[0].at, last = rows[rows.length - 1].at;
  const wins = (cond.windows || []).map(w => {
    const a = hourLabel(w.from), b = hourLabel(w.to);
    if (w.from === first && w.to === last) return '<b>right through the day</b>';
    if (w.from === first) return '<b>now until ' + b + ':00</b>';
    return '<b>' + a + ':00&ndash;' + b + ':00</b>';
  });
  const say = wins.length
    ? 'Worth using ' + wins.join(' and ') + ' &mdash; best about ' +
      Math.max(...cond.windows.map(w => w.best)) + '/100, local time.'
    : '<b>No usable window in the next day</b> on these numbers &mdash; the ' +
      'band stays under what a contact needs.';
  return '<div class="fcstrip">' + cells + '</div>' +
    '<div class="tiny muted fcsay">' + say +
    ' Colour is how good the hour looks; the pale bar along the foot of a ' +
    'cell is daylight.</div>';
}

/* Above about 30 MHz none of this applies, and pretending otherwise would put
   "Closed, 0/100" on 2 m every day of the year. The F layer does not refract
   up there: openings are sporadic E, tropospheric ducting and aurora, which
   are local, short-lived and not forecast from a solar flux number. So the
   bands above HF get what is actually known - what the network is reporting
   right now - and an honest sentence about why there is no curve. */
function vhfBox(band) {
  const v = (bpProp && bpProp.vhf) || {};
  const eskip = v['E-Skip/north_america'] || '';
  const aurora = v['vhf-aurora/northern_hemi'] || '';
  const open = t => t && !/closed/i.test(t);
  const bits = [];
  if (eskip) bits.push('<span class="pill ' + (open(eskip) ? 'q4' : 'q0') +
    '">Sporadic E: ' + escapeHTML(eskip) + '</span>');
  if (aurora) bits.push('<span class="pill ' + (open(aurora) ? 'q2' : 'q0') +
    '">Aurora: ' + escapeHTML(aurora) + '</span>');
  return '<div class="condbox">' +
    '<div class="condhead"><span class="panel-title" style="margin:0">' +
      'Conditions on ' + escapeHTML(band.name) + ' now</span>' + bits.join(' ') +
    '</div>' +
    '<div class="tiny muted">Above about 30 MHz the F layer does not bend a ' +
      'signal back, so there is no MUF to be under and no daily curve to ' +
      'show. What opens these bands is sporadic E, tropospheric ducting and ' +
      'aurora &mdash; local, short-lived, and not predictable from a solar ' +
      'flux number. The line above is what the network is reporting at this ' +
      'moment' + (bpProp && bpProp.aurora ? ', with the auroral activity index at ' +
      bpProp.aurora : '') + '. Line of sight is always there: for that, the ' +
      '<a href="/lab#ant">antenna and terrain tools</a> are the ones that ' +
      'answer.</div></div>';
}

function conditionBar(band) {
  if (band.high > 30) return vhfBox(band);
  const cond = conditionsFor(band);
  if (!cond || !cond.now) {
    return '<div class="condbox"><div class="tiny muted">Band conditions ' +
      'unavailable &mdash; the space-weather feed could not be reached.</div></div>';
  }
  const now = cond.now;
  const st = bpProp.station;
  const where = st ? escapeHTML(st.name) + ', ' + st.km + ' km away, ' +
    st.age_minutes + ' min ago' : '';
  /* Where the MUF came from, in the words that are true of it. A reading a
     long way from the model is not thrown away and not swallowed either: it
     is pulled as far as it is allowed to go, and the line says so. */
  /* Four ways the MUF can have been arrived at, and they are not the same
     claim. Every sonde is compared against the model at its own sun angle, so
     a distant one can still correct the level here without dragging its own
     daylight along with it - but "corrected by stations a long way off" is a
     weaker thing to say than "measured next door", and the line says which. */
  const votes = st ? st.stations + ' sonde' + (st.stations === 1 ? '' : 's') : '';
  const from = bpProp.muf_source === 'measured'
    ? 'MUF from ' + votes + ', nearest ' + where
    : bpProp.muf_source === 'regional'
      ? 'MUF corrected by ' + votes + ', the nearest ' + where + ' — far ' +
        'enough that this is a regional figure rather than a local one'
      : bpProp.muf_source === 'bounded'
        ? 'MUF from ' + votes + ' (nearest ' + where + ', reading foF2 ' +
          st.measured + ' MHz), held partway back to the model, which disagrees'
        : 'MUF estimated from SFI ' + bpProp.sfi + ' — no sonde within range';
  return '<div class="condbox">' +
    '<div class="condhead">' +
      '<span class="panel-title" style="margin:0">Conditions on ' +
        escapeHTML(band.name) + ' now</span>' +
      '<span class="pill ' + QUALITY_CLASS(now.score) + '">' +
        escapeHTML(now.label) + ' &middot; ' + now.score + '/100</span>' +
      (cond.rating ? '<span class="tiny muted">wall chart says ' +
        escapeHTML(cond.rating) + '</span>' : '') +
    '</div>' +
    '<div class="condmeter"><i class="' + QUALITY_CLASS(now.score) +
      '" style="width:' + now.score + '%"></i></div>' +
    /* A score with no distance on it is the misleading part. The rating is
       against MUF(3000) - a full hop - so a band can read Good and still not
       reach the next county, which is how somebody ends up calling CQ into a
       skip zone and concluding the tool is wrong. */
    (now.skip_km === undefined ? '' :
      now.skip_km === null
        ? '<div class="small" style="color:var(--red)">Reaches nobody &mdash; ' +
          'nothing comes back at any angle tonight.</div>'
        : now.reaches_local
          ? '<div class="small" style="color:var(--green)">Reaches everywhere, ' +
            'local included &mdash; this band is under the critical frequency, ' +
            'so it comes back from straight overhead.</div>'
          : '<div class="small" style="color:var(--amber)">Nothing closer than ' +
            '<b>' + Math.round(now.skip_km / 1.609) + ' miles</b>. The rating ' +
            'is for a long path; inside that is a skip zone, and neither power ' +
            'nor a different antenna crosses it &mdash; the antenna decides ' +
            'what you launch, the ionosphere decides what comes back, and it ' +
            'is returning nothing steep enough to land nearer. A vertical is ' +
            'the wrong way: it launches lower, which lands further out still. ' +
            (now.fills_the_gap
              ? 'The lever that works is frequency &mdash; <b>' +
                escapeHTML(now.fills_the_gap) + '</b> is under tonight\'s ' +
                'critical frequency and reaches them.'
              : 'Nothing on HF is under tonight\'s critical frequency, so ' +
                'the close-in answer is ground wave, VHF or a repeater.') +
            '</div>') +
    '<div class="small condmode"><b>' + escapeHTML(now.modes) + '</b></div>' +
    '<div class="tiny muted">' + escapeHTML(now.why) + '. ' + from +
      '; K index ' + bpProp.k_index + '.</div>' +
    '<div class="panel-title mt" style="margin-bottom:.3rem">The next 24 hours</div>' +
    forecastStrip(cond) +
    '<div class="tiny muted fcnote">A model, not a prediction service: sun ' +
      'angle, MUF and the state of the field, with today\'s flux held where it ' +
      'is. It knows nothing about your antenna or the far end.</div>' +
    '</div>';
}

function segMiddle(a) {
  return a.high > a.low ? (a.low + a.high) / 2 : a.low;
}

/* The intention to carry across, read from what the segment is for. */

function segCardHTML(a, band, forPick) {
  const cond = conditionsFor(band);
  const you = a.you || {state: 'no'};
  const range = a.high > a.low ? a.low + '–' + a.high : String(a.low);
  const rate = cond && cond.now
    ? '<div class="small"><span class="pill ' + QUALITY_CLASS(cond.now.score) +
      '">' + escapeHTML(cond.now.label) + ' · ' + cond.now.score + '/100</span> ' +
      'on ' + escapeHTML(band.name) + ' right now</div>' +
      '<div class="tiny">' + escapeHTML(cond.now.modes) + '</div>' +
      '<div class="tiny muted">MUF about ' + (bpProp.muf || '?') + ' MHz · ' +
      'SFI ' + bpProp.sfi + ' · K ' + bpProp.k_index + '</div>'
    : '<div class="tiny muted">Band conditions unavailable.</div>';
  const mark = you.state === 'yes' ? '<span class="pill good">yours</span>'
    : you.state === 'part' ? '<span class="pill warn">' + you.low + '–' + you.high + '</span>'
    : '<span class="pill bad">not yours</span>';
  return '<div class="seg-card-head"><b>' + escapeHTML(a.label) + '</b> ' + mark +
      '<span class="tiny mono muted">' + range + ' MHz</span></div>' +
    rate +
    (you.note ? '<div class="tiny" style="color:var(--amber);margin-top:.3rem">' +
      escapeHTML(you.note) + '</div>' : '') +
    (forPick
      ? '<div class="row" style="gap:.5rem;margin-top:.6rem">' +
          /* No use= here on purpose. Deciding what a frequency is for by
             looking at the band is how 2 m SSB came out as "you want FM
             repeaters": the band plan already knows, and antenna_advice
             reads it. Send the frequency and let it answer. */
          '<a class="btn sm primary" href="/lab?f=' + segMiddle(a).toFixed(3) +
            '&kind=' + encodeURIComponent(a.kind) +
            '#ant">Set up an antenna for this →</a>' +
          '<a class="btn sm ghost" href="/propagation">Full conditions</a>' +
          '<button class="btn sm ghost" id="bp-unpick">close</button>' +
        '</div>'
      : '<div class="tiny muted" style="margin-top:.4rem">Click for what to put ' +
        'up for it.</div>');
}

function bindSegments(band) {
  const bar = document.querySelector('#bp-out .bandbar');
  const hover = document.getElementById('bp-hover');
  const picked = document.getElementById('bp-picked');
  if (!bar || !hover) return;
  picked.innerHTML = '';

  bar.querySelectorAll('.seg[data-seg]').forEach(el => {
    const a = band.activity[+el.dataset.seg];
    if (!a) return;
    el.addEventListener('mouseenter', e => {
      hover.innerHTML = segCardHTML(a, band, false);
      hover.hidden = false;
      place(e);
    });
    const place = e => {
      const box = bar.getBoundingClientRect();
      hover.style.left = Math.min(Math.max(e.clientX - 135, 8),
                                  window.innerWidth - 278) + 'px';
      hover.style.top = (box.bottom + 8) + 'px';
    };
    el.addEventListener('mousemove', place);
    el.addEventListener('mouseleave', () => { hover.hidden = true; });
    el.addEventListener('click', () => {
      hover.hidden = true;
      picked.innerHTML = '<div class="panel tight mt seg-picked">' +
        segCardHTML(a, band, true) + '</div>';
      const shut = document.getElementById('bp-unpick');
      if (shut) shut.addEventListener('click', () => { picked.innerHTML = ''; });
      picked.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    });
  });
}
