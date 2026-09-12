/* Band plan: colour by activity, shade what your license class may not use. */

const KIND_COLOUR = {
  cw: '#58a6ff', digital: '#bc8cff', phone: '#3fb950', image: '#ffb454',
  beacon: '#f85149', satellite: '#39d3d8', repeater: '#ff8f3f',
  simplex: '#c9d13a', calling: '#ffffff', special: '#8b98a5',
};

let bpData = null, bpRegional = null, bpBand = null, bpChannels = [];

function bpClass() { return document.getElementById('bp-class').value; }

/* The owl, where it is earned.
 *
 * Reading another class's privileges is a good and ordinary thing to do - it
 * is how somebody decides whether the upgrade is worth sitting for. Printing
 * one with a callsign on it is not the same act, and the two must never
 * produce the same document. The sheet already stamps itself when the class
 * is not held; this says so before the press rather than after it. */
function bpNotYours(d) {
  const box = document.getElementById('bp-notyours');
  if (!box) return;
  if (!d || !d.above_yours) { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML =
    '<img src="/static/owl-mind.png" alt="" class="lapse-owl">' +
    '<div>You are reading <b>' + escapeHTML(d.class) + '</b> privileges and ' +
    'you hold <b>' + escapeHTML(d.own_class) + '</b>. Worth reading &mdash; ' +
    'it is how you decide whether the upgrade is worth sitting for. Anything ' +
    'printed from here says on its face that it is a study sheet and not a ' +
    'licence, because a chart with a callsign on it gets read as a claim ' +
    'about that station.</div>';
}

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
  bpNotYours(bpData);
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
    /* A state with no readable plan is not a failure - most coordinators do
       not publish one this can parse. Keep the answer so the page can name
       who covers them instead of showing nothing. */
    bpRegional = r.ok ? r : (r.coordinators ? r : null);
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
  if (bpRegional && !bpRegional.ok && bpRegional.coordinators) {
    const who = bpRegional.coordinators;
    rbox.innerHTML = '<div class="tiny muted"><b>' +
      escapeHTML(bpRegional.state) + ' is coordinated by ' +
      who.map(c => '<a href="' + escapeHTML(c.url) + '" target="_blank" ' +
        'rel="noopener">' + escapeHTML(c.name) + '</a>').join(' and ') +
      '.</b> ELMER cannot read their plan yet &mdash; there is no common ' +
      'format between coordinators and most publish PDFs or a query form, so ' +
      'the ones it parses are added a site at a time. The national band plan ' +
      'above still applies; the local plan narrows it.' +
      (who.some(c => c.note)
        ? ' ' + who.filter(c => c.note).map(c => escapeHTML(c.note)).join(' ')
        : '') + '</div>';
    return;
  }
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

/* "Set your QTH" opens the station panel here rather than sending anybody to
   another page for it: the gear is on every page, so its button can be. */
document.addEventListener('click', e => {
  if (!e.target.closest('[data-open-station]')) return;
  const gear = document.getElementById('gear-btn');
  if (gear) gear.click();
});

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

/* One word for the sky, from the same three states the model uses. "Tonight"
   used to be hardcoded into three sentences here, which is how a page showing
   a 33-degree sun came to talk about tonight's critical frequency. */
function skyNow() {
  const r = bpProp && bpProp.regime;
  return r === 'grey' ? 'the grey line\u2019s' : r === 'dark' ? 'tonight\u2019s'
                                                : 'today\u2019s';
}

function hourLabel(iso) {
  const d = new Date(iso);
  return String(d.getHours()).padStart(2, '0');
}

/* The grey line as clock times rather than a shaded hour. Both ends come from
   the same ephemeris, differing only in the height asked for: the horizon the
   operator stands on, and the D layer's own horizon 9.03 degrees further down.
   Where the sun does not set at all there is no window and this says nothing
   rather than inventing one. */
function greyWindow() {
  const s = bpProp && bpProp.sun;
  if (!s || s.up_all_day || s.down_all_day) return '';
  const dusk = clockAt(s.set), dark = clockAt(s.d_layer_set);
  const dawn = clockAt(s.d_layer_rise), up = clockAt(s.rise);
  if (!dusk || !dark) return '';
  return ' Tonight the sun sets here at <b>' + dusk + '</b> and on the D ' +
    'layer at <b>' + dark + '</b>, so that is the evening window; in the ' +
    'morning it runs the other way, <b>' + dawn + '</b> to <b>' + up +
    '</b>.';
}

/* What the unit's own ledger says about its forecasting: yesterday's word
   for this hour against what the sondes then read, the correction the unit
   has learned from that record and is applying, and whether the outlook
   moved since last time with the sky still. All measured on this machine;
   none of it leaves it. */
function recordLine() {
  const r = bpProp && bpProp.record;
  if (!r) return '';
  const parts = [];
  const latest = r.skill && r.skill.latest;
  if (latest && latest.forecast != null && latest.measured != null) {
    parts.push('Yesterday at this hour ELMER said MUF <b>' + latest.forecast +
      '</b> MHz; the sondes read <b>' + latest.measured + '</b>.');
  }
  const words = {dark: 'at night', lit: 'by day', grey: 'on the grey line', twilight: 'in twilight'};
  const cal = r.calibration;
  if (cal && cal.this_month) {
    const on = Object.keys(cal.this_month).filter(k => cal.this_month[k].applied);
    if (on.length) {
      parts.push('Calibrated here against ' + (cal.stations || []).length + ' sonde' + ((cal.stations || []).length === 1 ? '' : 's') +
        ' over ' + cal.months_known + ' months (' + new Date(cal.made).toLocaleDateString() + '): this month the model runs ' +
        on.map(k => '\u00d7' + cal.this_month[k].factor.toFixed(2) + ' ' + (words[k] || k)).join(', ') +
        ', and the curve is corrected by that where no reading holds.');
    }
  }
  const adj = r.adjustment || {};
  const applied = Object.keys(adj).filter(k => adj[k].applied);
  const waiting = Object.keys(adj).filter(k => !adj[k].applied && adj[k].n && !adj[k].capped);
  const capped = Object.keys(adj).filter(k => adj[k].capped);
  if (applied.length) {
    parts.push('This unit\u2019s own record has the model running ' + applied.map(k =>
      Math.abs(adj[k].measured_bias).toFixed(1) + ' MHz ' + (adj[k].measured_bias > 0 ? 'under' : 'over') +
      ' the sondes ' + (words[k] || k) + ' (' + adj[k].n + ' measured hours)').join(', ') +
      '; the curve is corrected by that where no reading holds.');
  } else if (waiting.length) {
    const k = waiting[0];
    parts.push('This unit is keeping score against the sondes: ' + adj[k].n + ' measured hour' +
      (adj[k].n === 1 ? '' : 's') + ' ' + (words[k] || k) + ' so far; a correction waits for twelve.');
  }
  if (capped.length) {
    parts.push('The record ' + (words[capped[0]] || capped[0]) + ' is off by more than ELMER will correct for on its own (' +
      adj[capped[0]].measured_bias.toFixed(1) + ' MHz) \u2014 a station or a sky worth a look, not a model to nudge.');
  }
  const d = r.drift;
  if (d && d.moved && !d.inputs_moved) {
    parts.push('<span class="warntext">The outlook moved since ' + hourLabel(d.since) + ':00 with the sky unchanged' +
      (d.build_changed ? ' \u2014 the build changed.' : ' \u2014 the model did; it is in the log.') + '</span>');
  }
  return parts.length ? ' ' + parts.join(' ') : '';
}

function forecastStrip(cond) {
  const rows = cond.hours || [];
  if (!rows.length) {
    /* No QTH, so no outlook. This used to be one line of footnote type under
       a full-size heading, which read as a caption to something rather than
       as the something itself being absent - and was missed. The strip is
       drawn anyway, empty, so the space is the same shape it will be once
       filled, and the sentence that fills it is body size with the button
       that fixes it in it. The station panel is on every page, so the fix
       is here, not a link away. */
    const blanks = Array.from({length: 24}, () => '<i class="fc"></i>').join('');
    return '<div class="fcstrip fcempty">' + blanks + '</div>' +
      '<div class="fcwhy"><b>Set your QTH</b> and this becomes the next 24 hours ' +
      'on this band, hour by hour \u2014 the sun\'s angle where you are decides most of it. ' +
      '<button type="button" class="btn sm" data-open-station>Station&hellip;</button></div>';
  }
  /* The best window, worked out before the cells so they can be marked with
     it. A peak is nearly always a plateau and the strip already draws that -
     but "best around 19:00" underneath it says otherwise, so the run gets a
     bar along its top and the sentence gets its width. */
  const top = (cond.windows || []).reduce(
    (best, w) => (best && best.best >= w.best ? best : w), null);
  const peakFrom = top ? top.best_from : null;
  const peakTo = top ? top.best_to : null;

  const cells = rows.map((h, i) => {
    const label = hourLabel(h.at);
    const atBest = peakFrom && h.at >= peakFrom && h.at <= peakTo;
    // "now" under the first cell, then every sixth hour: enough to read the
    // shape against the clock without turning the strip into a ruler.
    const tick = i === 0 ? 'now' : (i % 6 === 0 ? label : '');
    const sky = h.regime === 'grey' ? ', grey line'
              : h.regime === 'twilight' ? ', twilight - the D layer never clears'
              : h.regime === 'dark' ? ', dark' : ', daylight';
    return '<i class="fc ' + QUALITY_CLASS(h.score) + (i === 0 ? ' now' : '') +
      (atBest ? ' peak' : '') +
      (h.regime === 'grey' ? ' grey' : h.regime === 'twilight' ? ' dusk'
                                     : h.regime === 'dark' ? '' : ' day') +
      '" title="' + label + ':00 local — ' + h.score +
      '/100, MUF about ' + h.muf + ' MHz' + sky +
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
  /* The peak, with the hours it covers rather than the hour it starts. A
     band's best is a stretch, not an instant: 40 m can sit within a point of
     its own maximum for eight hours, and naming one of them implies the other
     seven are worse when they are the same. Only a genuinely one-hour peak is
     reported as an hour. */
  const peak = !top ? ''
    : top.best_from === top.best_to
      ? 'best around <b>' + hourLabel(top.best_at) + ':00</b> at ' +
        top.best + '/100.'
      : 'best from <b>' + hourLabel(top.best_from) + ':00</b> to <b>' +
        hourLabel(top.best_to) + ':00</b> at ' + top.best + '/100' +
        // Only worth counting when there is something to count. "1 hours of
        // it" after a pair of adjacent hours is noise, and the two times
        // have already said it.
        (top.best_hours > 1 ? ' &mdash; ' + top.best_hours +
                              ' hours of it.' : '.');
  /* "Worth using right through the day" is true of 40 m at a floor of 38 and
     hides the fact that the middle of it is CW and FT8, not SSB. So the
     longest stretch inside a window where the band is merely Fair is named,
     with the modes that stretch is good for - the strip's colours say it,
     and now the sentence does too. */
  let dip = '';
  {
    let best = null, run = null;
    rows.forEach(h => {
      const fair = h.score >= 38 && h.score < 60;
      if (fair) { run = run || {from: h.at, to: h.at, n: 0}; run.to = h.at; run.n += 1; }
      else { if (run && (!best || run.n > best.n)) best = run; run = null; }
    });
    if (run && (!best || run.n > best.n)) best = run;
    if (best && best.n >= 2 && top && top.best >= 60) {
      dip = ' From <b>' + hourLabel(best.from) + ':00</b> to <b>' + hourLabel(best.to) +
        ':00</b> it is CW and FT8, not SSB' +
        (rows.some(h => h.at >= best.from && h.at <= best.to && h.day)
          ? ' &mdash; the D layer is taking its daytime share.' : '.');
    }
  }
  const say = wins.length
    ? 'Worth using ' + wins.join(' and ') + ', local time &mdash; ' + peak + dip
    : '<b>No usable window in the next day</b> on these numbers &mdash; the ' +
      'band stays under what a contact needs.';
  return '<div class="fcstrip">' + cells + '</div>' +
    '<div class="tiny muted fcsay">' + say +
    ' Colour is how good the hour looks; the pale bar along the foot of a ' +
    'cell is daylight, and an amber one is the grey line &mdash; sunset here, ' +
    'but not yet 80 km up, which is where the absorption is.' +
    /* The strip is hourly because the model is. The window itself is not, and
       the unit knows it to the minute: the sun leaves the ground at one time
       and the D layer 80 km up at another, and the gap is the whole event.
       Naming both makes the amber cell a thing somebody can be ready for
       rather than a colour they notice afterwards. */
    greyWindow() + recordLine() + '</div>';
}

/* Above about 30 MHz none of this applies, and pretending otherwise would put
   "Closed, 0/100" on 2 m every day of the year. The F layer does not refract
   up there: openings are sporadic E, tropospheric ducting, aurora and meteor
   scatter. So the bands above HF get what is actually known - what the network
   is reporting right now - and an honest sentence about why there is no curve.

   That sentence used to say there was "no daily curve to show", which claims
   more than we know. Two of those four keep fairly regular hours, and they
   keep DIFFERENT ones - which is the whole reason this is worth spelling out
   rather than saying "dawn" once and leaving it:

     Tropospheric ducting is a ground-level effect. The nocturnal inversion
     builds while the ground radiates its heat away and the air above it does
     not, so the duct is deepest at the end of the night and the sun pulls it
     apart within a couple of hours of clearing the horizon. Its clock is
     sunrise, and sunrise moves through the year.

     Meteor scatter is not a sunlight effect at all. The rate peaks near 06:00
     local because that is when your side of the Earth has swung round to face
     the direction of travel and is sweeping the debris up head-on, and that
     hour barely moves with the season. Here at 46 N the two anchors are
     within half an hour of each other in September and nearly two hours apart
     in December, so quoting one number for both would be wrong for a good
     part of the year.

   Note which sunrise is which. `regime` calls an hour "lit" at elevation >= 0,
   the sun over the horizon where the operator is standing, and "grey" down to
   D_LAYER_DIP - 9.03 degrees below, where the sun has left the ground but not
   yet the D layer 80 km up. That D-layer geometry is most of the shape of the
   HF strip. Up here it is worth almost nothing: D absorption falls as 1/f^2,
   so what costs 80 m its whole daylight costs 2 m nothing measurable. The
   inversion is weather at head height, and the ground's own sunrise is the
   one that governs it - so this reads the "lit" flip and not the grey hour.
   Getting that backwards would hand somebody an hour that is right on 80 m
   and 40 minutes early on 2 m. */

/* Sunrise where the operator is standing, to the minute.

   This used to hunt for the hour the daylight flag turned over in the forecast
   rows, which could only ever be right to the nearest hour and was reading a
   flag to answer a question about the sky. The unit computes the real time
   now: the same ephemeris that reduces a sextant sight, solved for the moment
   rather than for the altitude. Nothing is fetched and nothing is cached, so
   this is as true with the network unplugged as with it. Inside a polar day or
   night there is no sunrise to name and the server says so instead. */
function clockAt(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return String(d.getHours()).padStart(2, '0') + ':' +
         String(d.getMinutes()).padStart(2, '0');
}

function sunriseAt() {
  return clockAt(bpProp && bpProp.sun && bpProp.sun.rise);
}
function vhfBox(band) {
  const v = (bpProp && bpProp.vhf) || {};
  const hour = sunriseAt();
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
      'signal back, so there is no MUF to be under and no curve we can work ' +
      'out for you. What opens these bands is sporadic E, tropospheric ' +
      'ducting, aurora and meteor scatter, and not one of them follows a ' +
      'solar flux number &mdash; which is why the HF bands get a strip and ' +
      'this gets a paragraph. The line above is what the network is ' +
      'reporting at this moment' + (bpProp && bpProp.aurora ?
      ', with the auroral activity index at ' + bpProp.aurora : '') + '.</div>' +
    '<div class="tiny muted mt"><b>Two of them do keep hours, though, and ' +
      'they are not the same hours.</b> ' +
      '<b>Tropospheric ducting</b> runs on sunrise: the ground gives its heat ' +
      'back overnight, the air above stays warm, and that inversion bends ' +
      'signals far past the horizon. It is deepest at the end of the night ' +
      'and the sun takes it apart within a couple of hours of clearing the ' +
      'horizon' + (hour ? ' &mdash; sunrise here is <b>' + hour +
      '</b> local' : '') + '. ' +
      '<b>Meteor scatter</b> runs on a different clock entirely: it peaks ' +
      'near <b>06:00</b> local whatever the season, because that is when your ' +
      'side of the Earth has turned to face the way the planet is travelling ' +
      'and sweeps the debris up head-on instead of catching it from behind. ' +
      'In midsummer those two land almost together; in December they are ' +
      'nearly two hours apart. Neither is a prediction &mdash; both are just ' +
      'when it is worth going to look.</div>' +
    '<div class="tiny muted mt">The grey line does almost nothing for you up ' +
      'here. D-layer absorption falls as 1/f&sup2;, so what shuts 80 m all ' +
      'day costs 2 m nothing you could measure &mdash; the whole business of ' +
      'the sun setting on the ground before it sets 80 km up is an HF story. ' +
      'And line of sight is always there, at every hour: for that, the ' +
      '<a href="/lab#ant">antenna and terrain tools</a> are the ones that ' +
      'answer.</div></div>';
}

function conditionBar(band) {
  /* Above about 30 MHz there is usually no F layer return and so no daily
     curve worth drawing - but "usually" is not "never", and 6m is the band
     where it matters. It is in the propagation model, the outlook returns a
     full day of hours for it, and since the critical frequency was bounded at
     what has actually been observed the modelled MUF reaches 58 MHz at solar
     maximum, which is a real 6m F2 opening. Throwing that away and printing
     only the sporadic-E note told somebody nothing on the one VHF band the
     model can speak about. So it gets both: the curve where there is one, and
     the note about what else opens it. */
  if (band.high > 30) {
    const vhf = vhfBox(band);
    const cond = conditionsFor(band);
    if (!cond || !cond.now || !(cond.hours || []).length) return vhf;
    return vhf + '<div class="condbox">' +
      '<div class="panel-title" style="margin:0">If the F layer reaches it</div>' +
      '<div class="tiny muted">Rare, and worth showing because it is the one ' +
      'band above 30 MHz where it happens: at solar maximum the critical ' +
      'frequency can climb far enough that 6m opens like an HF band. This is ' +
      'the same model the HF bands use, and on most days it will say the ' +
      'band is shut - which is the honest answer.</div>' +
      forecastStrip(cond) + '</div>';
  }
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
      /* The wall chart beside ours. Agreement is worth a quiet line - it is
         a real second opinion and it confirming us is information. A
         disagreement gets said out loud and explained underneath, because a
         reader who spots the contradiction on their own and is not told why
         it exists has been given two numbers and no way to choose. */
      (cond.rating
        ? '<span class="pill ' + (now.wall && !now.wall.agree ? 'warn' : 'info') +
          '">wall chart: ' + escapeHTML(cond.rating) +
          (now.wall && !now.wall.agree ? ' \u2260 ' + escapeHTML(now.wall.ours)
                                       : ' \u2713') + '</span>'
        : '') +
    '</div>' +
    '<div class="condmeter"><i class="' + QUALITY_CLASS(now.score) +
      '" style="width:' + now.score + '%"></i></div>' +
    /* Said where the two numbers are, not in a footnote. */
    (now.wall && !now.wall.agree
      ? '<div class="small" style="color:var(--amber)">' +
        escapeHTML(now.wall.note) + '</div>'
      : '') +
    /* A score with no distance on it is the misleading part. The rating is
       against MUF(3000) - a full hop - so a band can read Good and still not
       reach the next county, which is how somebody ends up calling CQ into a
       skip zone and concluding the tool is wrong. */
    (now.skip_km === undefined ? '' :
      now.skip_km === null
        ? '<div class="small" style="color:var(--red)">Reaches nobody &mdash; ' +
          'nothing comes back at any angle just now.</div>'
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
                escapeHTML(now.fills_the_gap) + '</b> is under ' + skyNow() +
                ' critical frequency and reaches them.'
              : 'Nothing on HF is under ' + skyNow() + ' critical frequency, so ' +
                'the close-in answer is ground wave, VHF or a repeater.') +
            (now.ground_wave && now.ground_wave.miles
              ? ' Ground wave covers the first <b>' + now.ground_wave.miles +
                ' miles</b> of it on this band &mdash; from a vertical, over ' +
                escapeHTML(now.ground_wave.ground_label.toLowerCase()) +
                ', at 100 W. A horizontal antenna has almost none.'
              : '') +
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
          /* The class goes with it. This page has its own selector and
             every figure on it is drawn for whatever that says - so somebody
             reading the Extra plan and clicking through was being answered
             against whatever their profile happened to hold, which is a
             different question from the one they were looking at. */
          '<a class="btn sm primary" href="/lab?f=' + segMiddle(a).toFixed(3) +
            '&kind=' + encodeURIComponent(a.kind) +
            '&class=' + encodeURIComponent(bpClass()) +
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
