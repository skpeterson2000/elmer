/* Band plan: color by activity, shade what your license class may not use. */

/* The activity colors are palette.py's, handed over with the page, so the
   screen and the printed chart read one copy. The same color for a kind on
   every band; the band's own color is the other family, on the buttons,
   the headings and the reach map. */
const KIND_COLOR = window.KIND_COLOR || {};

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
  /* No license is not a lapse and gets no owl: it is where everybody
     starts, and the honest sheet for it is the one further down the page -
     FRS, MURS and CB now, GMRS for a fee and no exam, and the amateur bands
     above shown for what they are, the reason to sit the Technician. */
  if (d && d.class === 'none') {
    box.hidden = false;
    box.className = 'notice';
    box.innerHTML =
      '<div><b>No license yet.</b> Every amateur band above reads <i>no</i> ' +
      'for you, and that is the truth of it - but it is not the whole list. ' +
      '<a href="#personal">FRS, MURS and CB</a> are yours today with a radio ' +
      'certified for them, GMRS is a fee and a form with no exam, and CB has ' +
      'its own skip forecast down there, worked from the same sky as 10 m. ' +
      'The Technician exam is thirty-five questions and the pool is in this ' +
      'program.</div>';
    return;
  }
  /* A license from somewhere else, being used here. 47 CFR 97.107 lets a
     visitor holding their own government's amateur authorisation be the
     control operator of a station in the US where there is a reciprocal
     arrangement, and caps what they may do at what an Amateur Extra may do.
     That cap is what the chart above draws, and it is only half the answer:
     the other half is their own license, which this program has never seen.
     Saying the first half without the second would be the dangerous half. */
  /* The charts print a class, and "visiting" is not one. A sheet headed
     that way, with a callsign on it, would read as a claim about an
     operator's authority in a country whose license they do not hold -
     and the chart they actually want exists already, because the ceiling
     they are drawn at is the Amateur Extra one. So the buttons say that
     rather than failing at the server. */
  ['bp-card', 'bp-pdf'].forEach(id => {
    const b = document.getElementById(id);
    if (!b) return;
    const off = !!(d && d.reciprocal);
    b.disabled = off;
    b.title = off ? 'Print the Amateur Extra chart instead - it is the same ceiling. '
                  + 'A sheet headed "visiting" with a callsign on it would read as a claim.' : '';
  });
  if (d && d.reciprocal) {
    box.hidden = false;
    box.className = 'notice';
    box.innerHTML =
      '<div><b>Visiting, on your own license.</b> Under ' +
      '<a href="https://www.ecfr.gov/current/title-47/section-97.107" target="_blank" rel="noopener">47 CFR 97.107</a> ' +
      'an operator holding an amateur authorisation from their own government may be ' +
      'the control operator of a station here, wherever a reciprocal arrangement ' +
      'reaches - CEPT, the IARP, or a bilateral one, and Canada&rsquo;s is written into ' +
      'the rule itself. <b>The chart above is the ceiling, not your privileges.</b> ' +
      'What you may do here is the terms of your own license and the FCC&rsquo;s rules ' +
      'together, and in no case more than an Amateur Extra may do - so read this ' +
      'against your own license and take whichever is the narrower of the two. ' +
      'ELMER has never seen your license and is not guessing at it.' +
      '<br><br>Identify under ' +
      '<a href="https://www.ecfr.gov/current/title-47/section-97.119" target="_blank" rel="noopener">97.119(g)</a>: ' +
      'a Canadian licensee puts the indicator for the US call sign area after their ' +
      'own call, and everybody else puts it before, separated by a slant. ' +
      'None of this is for a US citizen or for anybody already holding an FCC ' +
      'license - that is their FCC license, and it is the class above.</div>';
    return;
  }
  box.className = 'lapse';
  if (!d || !d.above_yours) { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML =
    '<img src="/static/owl-mind.png" alt="" class="lapse-owl">' +
    '<div>You are reading <b>' + escapeHTML(d.class) + '</b> privileges and ' +
    'you hold <b>' + escapeHTML(d.own_class) + '</b>. Worth reading &mdash; ' +
    'it is how you decide whether the upgrade is worth sitting for. Anything ' +
    'printed from here says on its face that it is a study sheet and not a ' +
    'license, because a chart with a callsign on it gets read as a claim ' +
    'about that station.</div>';
}

/* Bands in the order somebody would actually reach for them, rather than in
   frequency order. The first one this license can hold a conversation on is
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
      '<span class="legend"><i style="background:' + KIND_COLOR[k] + '"></i>' +
      escapeHTML(label) + '</span>').join('') +
    '<span class="legend"><i class="legend-gap"></i>outside your privileges</span>';

  /* One button a band, outlined in the band's own color and filled with it
     when it is the one open: the row is the palette, learned by using it. */
  document.getElementById('bp-bands').innerHTML = bpData.bands.map(b =>
    '<button class="btn sm band-btn' + (b.name === bpBand ? ' on' : '') +
    '" style="' + bandStyle(b.name) + '" data-band="' + escapeHTML(b.name) + '">' + escapeHTML(b.name) + '</button>').join('');
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
   suppressed carrier, 1.5 kHz below the channel center the rules name. */
function channelTicks(band) {
  if (!band.channelised || !bpChannels.length) return '';
  const span = band.high - band.low;
  const at = f => ((f - band.low) / span) * 100;
  return '<div class="chanticks">' + bpChannels.map(c =>
    '<i style="left:' + at(c.center).toFixed(3) + '%" title="' + c.name +
      ' — channel center ' + c.center.toFixed(4) + ' MHz, 2.8 kHz wide">' +
      '<b>' + c.n + '</b><span>' + c.dial.toFixed(4) + '</span></i>').join('') +
    '</div>';
}

function bpRender() {
  document.querySelectorAll('#bp-bands [data-band]').forEach(b => {
    b.classList.toggle('on', b.dataset.band === bpBand);
  });
  const band = bpData.bands.find(b => b.name === bpBand);
  if (!band) return;
  const span = band.high - band.low;
  const pct = f => ((f - band.low) / span) * 100;

  /* The bar: activity in color, privilege gaps hatched over the top. Each
     segment carries what it needs for the hover card and the click, so the
     bar becomes a way in rather than only a picture. */
  const bars = band.activity.map((a, i) => {
    const w = Math.max(0.35, pct(a.high) - pct(a.low));
    return '<i class="seg" data-seg="' + i + '" style="left:' +
      pct(a.low).toFixed(3) + '%;width:' + w.toFixed(3) + '%;background:' +
      KIND_COLOR[a.kind] + '"></i>';
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
      '<td><span class="dot" style="background:' + KIND_COLOR[a.kind] + '"></span>' +
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
      '<div class="spread"><h2 class="band-tag" style="margin:0;' + bandStyle(band.name) + '">' + bandSwatch(band.name) + escapeHTML(band.name) + '</h2>' +
      '<span class="mono tiny muted">' + band.low + ' – ' + band.high + ' MHz · ' +
        escapeHTML(band.group) + (band.personal ? ' · ' + escapeHTML(band.personal) + ', no license' : '') + '</span></div>' +
      '<div class="bandbar">' + bars + gaps + '</div>' +
      channelTicks(band) +
      '<div class="bandscale"><span>' + band.low + '</span><span>' + band.high + '</span></div>' +
      (band.personal === 'CB' ? cbConditions() : conditionBar(band)) +
      '<div class="grid cols-2 mt">' +
        '<div><div class="panel-title">Your privileges — ' + escapeHTML(band.rule || '47 CFR 97.301') + '</div>' +
          '<ul class="privlist">' + priv + '</ul></div>' +
        '<div><div class="panel-title">Where the activity is</div>' + key +
          '<table class="data"><tbody>' + rows + '</tbody></table></div>' +
      '</div>' +
    '</div>';

  bindSegments(band);
  bpReach(band);

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
        '<td><span class="dot" style="background:' + (KIND_COLOR[sg.kind] || '#8b98a5') + '"></span>' +
          escapeHTML(sg.kind) + '</td>' +
        '<td class="small">' + escapeHTML(sg.label) + '</td></tr>').join('') +
      '</tbody></table>' +
      '<div class="tiny muted" style="margin-top:.5rem">Fetched ' +
        escapeHTML(bpRegional.fetched || '') +
        (bpRegional.cached ? ' (cached)' : '') + '. ' + escapeHTML(bpRegional.note || '') + '</div>' +
    '</div>';
}

/* The picker is a view, not a claim.
 *
 * Reading another class's privileges is the point of this page - it is how
 * somebody decides whether the upgrade is worth sitting for - so the list
 * offers every class to everybody. What it must not do is tell the rest of
 * the program that this station holds the class being read. It used to save
 * the choice to the profile on every change, and that one line had two
 * quiet consequences: the study pools are gated on the license, so looking
 * at Extra here opened every pool on the dashboard and at the table; and
 * the owl above compares the class being read with the class held, so with
 * the setting chasing the dropdown the two were never different and the
 * owl could not appear. A license is set where a license is set - the setup
 * page, or the FCC record behind a callsign - and this page opens on it
 * every time, whatever was looked at last. */
document.getElementById('bp-class').addEventListener('change', () => { bpLoad(); });
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

/* ---------------------------------------------- the other radios in America
   FRS, GMRS, MURS and CB from /api/personal: one fold per service with its
   law and its channels, then the honest paragraph about an amateur radio on
   those channels. Folded like the NIFOG rows, for the same reason - the
   amateur bands are the page, and this is the rest of the country. */
function psFreq(mhz) {
  return mhz.toFixed(4).replace(/0+$/, '').replace(/\.$/, '.0');
}

function psFacts(svc) {
  const rows = [
    ['Who may use it', svc.license], ['Channels', svc.band],
    ['Power', svc.power], ['Antenna', svc.antenna],
    ['Identification', svc.id], ['Range', svc.range],
    ['Equipment', svc.equipment], ['Uses', svc.uses],
  ];
  return '<table class="data ps-facts"><tbody>' +
    rows.map(([k, v]) => '<tr><th>' + k + '</th><td class="small">' +
      escapeHTML(v) + '</td></tr>').join('') + '</tbody></table>';
}

function psFrsGmrs(rows) {
  return '<table class="data"><thead><tr><th>Ch</th><th class="num">MHz</th>' +
    '<th>FRS</th><th>GMRS</th><th class="num">Repeater in</th><th>Notes</th></tr></thead><tbody>' +
    rows.map(c => '<tr><td class="mono"><b>' + c.n + '</b></td>' +
      '<td class="num mono tiny">' + psFreq(c.mhz) + '</td>' +
      '<td class="tiny nowrap">' + escapeHTML(c.frs) + '</td>' +
      '<td class="tiny nowrap">' + escapeHTML(c.gmrs) + (c.handheld_only ? '<br>handhelds only' : '') + '</td>' +
      '<td class="num mono tiny">' + (c.repeater_input ? psFreq(c.repeater_input) : '&mdash;') + '</td>' +
      '<td class="tiny muted">' + escapeHTML(c.note) + '</td></tr>').join('') +
    '</tbody></table>';
}

function psMurs(rows) {
  return '<table class="data"><thead><tr><th>Ch</th><th class="num">MHz</th>' +
    '<th class="num">Bandwidth</th><th>Notes</th></tr></thead><tbody>' +
    rows.map(c => '<tr><td class="mono"><b>' + c.n + '</b></td>' +
      '<td class="num mono tiny">' + psFreq(c.mhz) + '</td>' +
      '<td class="num tiny">' + c.bandwidth_khz + ' kHz</td>' +
      '<td class="tiny muted">' + escapeHTML(c.note) + '</td></tr>').join('') +
    '</tbody></table>';
}

function psCb(rows) {
  /* Two columns of twenty: forty rows one under the other is a scroll, and
     the channel list is something people read across. */
  const half = Math.ceil(rows.length / 2);
  const col = part => '<table class="data"><thead><tr><th>Ch</th>' +
    '<th class="num">MHz</th><th>Notes</th></tr></thead><tbody>' +
    part.map(c => '<tr' + (c.law ? ' class="law"' : '') + '><td class="mono"><b>' + c.n + '</b></td>' +
      '<td class="num mono tiny">' + psFreq(c.mhz) + '</td>' +
      '<td class="tiny muted">' + escapeHTML(c.note) + '</td></tr>').join('') +
    '</tbody></table>';
  return '<div class="grid" style="grid-template-columns:1fr 1fr;gap:.8rem;align-items:start">' +
    col(rows.slice(0, half)) + col(rows.slice(half)) + '</div>';
}

/* The personal services, drawn once the channel tables arrive and again when
   the outlook does: the CB fold carries the same conditions box as 10 m,
   since 11 m sits between two amateur bands and opens with them, and that
   box is empty until the outlook is in. */
let bpPersonal = null;
api('/api/personal').then(d => { bpPersonal = d; psRender(); }).catch(() => {
  const box = document.getElementById('personal-body');
  if (box) box.innerHTML = '<p class="small muted">Could not load the channel tables.</p>';
});

/* What a score means on CB, in CB's terms: AM on the channels, SSB on 36-40.
   The amateur table talks about CW and FT8, which a CB radio has not got. */
function cbModes(score) {
  return score >= 60 ? 'Skip is in: SSB on 36-40 (call on 38 LSB) and AM will carry too'
    : score >= 38 ? 'Skip is there for SSB on 36-40; AM will struggle past the horizon'
    : score >= 18 ? 'Faint skip - SSB on 38 with patience; AM is local'
    : 'No skip: local only, a few miles by ground wave, more with SSB';
}

function cbConditions() {
  const cond = conditionsFor({name: '11 m'});
  if (!cond || !cond.now) return conditionBar({name: '11 m', high: 27.405});
  const now = Object.assign({}, cond.now, {modes: cbModes(cond.now.score)});
  return '<div class="tiny muted" style="margin-top:.6rem">The one forecast ' +
    'nobody publishes for CB, from the same physics as 10 m: when the MUF ' +
    'passes 27 MHz, or sporadic E arrives in summer, a 4 W call goes ' +
    'hundreds of miles. Legal since 2017 - the 155-mile rule went with the ' +
    'Part 95 rewrite.</div>' +
    conditionBar({name: '11 m', high: 27.405}, Object.assign({}, cond, {now}));
}

/* The GMRS machines within reach of the QTH, from the same list the
   amateur repeaters come from - TowerWitch's, or the import - told apart
   by their eight fixed outputs. A repeater is most of what the GMRS
   license buys, so the fold says where the nearest ones are. */
function gmrsLicense(d) {
  const g = d.gmrs_license;
  if (!g || !g.callsign) return '';
  if (!g.found) return '<p class="tiny muted" style="margin-top:.5rem">' + escapeHTML(g.callsign) + ': ' + escapeHTML(g.reason || 'not on record') + '</p>';
  const st = (g.status || {}).state;
  return '<p class="small" style="margin-top:.5rem">' + (g.covered_by ? escapeHTML(g.covered_by) + '\u2019s license, yours to operate under as family (95.1705(c)): ' : 'Your license: ') +
    '<b class="mono">' + escapeHTML(g.callsign) + '</b>, ' +
    (st === 'current' ? 'good until <b>' + escapeHTML(g.expires) + '</b>' + ((g.status.days || 0) < 90 ? ' <span class="pill warn">renew soon</span> <a href="https://wireless2.fcc.gov/UlsEntry/licManager/login.jsp" target="_blank" rel="noopener">renew at ULS \u2192</a>' : '') :
     st === 'expired' ? '<b>expired ' + escapeHTML(g.expires) + '</b> \u2014 no grace period on GMRS; apply again before transmitting' :
     'granted ' + escapeHTML(g.granted || '')) +
    ' <span class="tiny muted">(' + escapeHTML(g.source || '') + ')</span></p>';
}

function gmrsRepeaters(d) {
  const rows = d.gmrs_repeaters || [];
  if (!rows.length) {
    return '<p class="tiny muted" style="margin-top:.5rem">GMRS repeaters near you: none held. A RepeaterBook token of your own, under ' +
      '<b>Station</b>, fetches them with the amateur machines; failing that, RepeaterBook\u2019s GMRS section exports a CSV per state, which ' +
      'reaches ELMER through TowerWitch\u2019s data folder.</p>';
  }
  return '<div class="panel-title mt" style="margin-bottom:.3rem">GMRS repeaters within reach</div>' +
    '<table class="data"><thead><tr><th>Output</th><th>Tone</th><th>Where</th><th>Miles</th><th>Bearing</th><th>Reach</th></tr></thead><tbody>' +
    rows.map(r => '<tr><td class="mono">' + r.output.toFixed(3) + ' <span class="muted">+5</span></td><td class="mono">' + escapeHTML(String(r.tone || '\u2014')) +
      '</td><td>' + escapeHTML(r.where || r.call || '') + (r.approx ? ' ~' : '') + '</td><td class="mono">' + r.miles + '</td><td class="mono">' + r.bearing + '&deg;</td>' +
      '<td class="tiny">' + escapeHTML(r.reach || '') + '</td></tr>').join('') +
    '</tbody></table><p class="tiny muted">Transmit 5 MHz above the output. At 462 MHz the radio horizon is the reach: a handheld at head height sees a tower ' +
    'some twenty-three miles off, an antenna at twenty feet a few miles more, and 50 W buys margin inside that rather than distance past it. ' +
    'A GMRS license - a fee and a form, no exam - and the owner\u2019s say-so; an FRS radio cannot use a repeater.' +
    (d.gmrs_credit ? ' <a class="muted" href="https://www.repeaterbook.com" target="_blank" rel="noopener">' + escapeHTML(d.gmrs_credit) + '</a>' : '') + '</p>';
}

function psRender() {
  const d = bpPersonal;
  const box = document.getElementById('personal-body');
  if (!box || !d) return;
  const tables = {
    frs: () => psFrsGmrs(d.frs_gmrs), gmrs: () => psFrsGmrs(d.frs_gmrs),
    murs: () => psMurs(d.murs), cb: () => psCb(d.cb),
  };
  const heads = {
    frs: '22 channels, shared with GMRS &mdash; 47 CFR 95.563',
    gmrs: 'the same 22 plus 8 repeater inputs &mdash; 47 CFR 95.1763',
    murs: '5 channels &mdash; 47 CFR 95.2763',
    cb: '40 channels &mdash; 47 CFR 95.963',
  };
  box.innerHTML =
    d.services.map(svc =>
      '<details class="nifog-more ps-service"><summary class="small"><b>' +
        escapeHTML(svc.name) + '</b> &mdash; ' + escapeHTML(svc.long) +
        ' <span class="muted">(' + heads[svc.key] + ')</span></summary>' +
      '<div class="grid cols-2 ps-grid">' +
        '<div>' + psFacts(svc) + '</div>' +
        '<div class="nifog-band" style="margin-top:0">' + tables[svc.key]() + '</div>' +
      '</div>' + (svc.key === 'cb' ? cbConditions() : '') + (svc.key === 'gmrs' ? gmrsLicense(d) + gmrsRepeaters(d) : '') + '</details>').join('') +
    /* Said once, on the page that shows the channels, because this is where
       somebody with a dual-band handheld is looking at 462.675 and
       wondering. */
    '<div class="notice mt">' +
      '<b>Your amateur radio on these channels.</b> ' + escapeHTML(d.amateur.can) + ' ' +
      escapeHTML(d.amateur.law) +
      '<p style="margin:.5rem 0 0">' + escapeHTML(d.amateur.emergency) + '</p>' +
      '<p style="margin:.5rem 0 0">' + escapeHTML(d.amateur.judgment) + '</p>' +
    '</div>' +
    '<div class="small mt"><b>When it is an emergency, in this order:</b>' +
      '<ol class="ps-ladder">' + d.ladder.map(step =>
        '<li><b>' + escapeHTML(step.what) + '.</b> <span class="muted">' +
        escapeHTML(step.how) + '</span></li>').join('') + '</ol></div>';
}

/* ---------- the bar as a way in ----------

   Hovering a segment says what is there and whether the band is open right
   now; clicking one keeps that on screen and offers to carry the frequency
   into the antenna designer. The conditions come from the propagation feed
   already on the dashboard, matched to the band being looked at, so hovering
   costs nothing beyond the one fetch this page makes at load. */

let bpProp = null;
/* The moon and the meteor calendar, kept apart from the outlook because they
   come from a clock rather than the network: they are on the page when the
   space weather is not. */
let bpSky = null;

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
  bpSky = (d.moon || d.meteors) ? {moon: d.moon || null, meteors: d.meteors || null} : null;
  if ((bpProp || bpSky) && bpData) bpRender();       // it arrived after the first draw
  if (bpProp) psRender();                            // the CB fold's forecast
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
  return r === 'gray' ? 'the gray line\u2019s' : r === 'dark' ? 'tonight\u2019s'
                                                : 'today\u2019s';
}

function hourLabel(iso) {
  const d = new Date(iso);
  return String(d.getHours()).padStart(2, '0');
}

/* The gray line as clock times rather than a shaded hour. Both ends come from
   the same ephemeris, differing only in the height asked for: the horizon the
   operator stands on, and the D layer's own horizon 9.03 degrees further down.
   Where the sun does not set at all there is no window and this says nothing
   rather than inventing one. */
function grayWindow() {
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
  const words = {dark: 'at night', lit: 'by day', gray: 'on the gray line', twilight: 'in twilight'};
  const pers = r.persistence;
  if (pers && pers.hours) {
    parts.push('Past the reading, the curve leans on what the sondes measured at each hour over the last ' +
      (pers.days === 1 ? 'day' : pers.days + ' days') + ' (' + pers.hours + ' of the 25 hours have a record)' +
      ' \u2014 over a year that beat the model at every lead past six hours.');
  }
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
    const sky = h.regime === 'gray' ? ', gray line'
              : h.regime === 'twilight' ? ', twilight - the D layer never clears'
              : h.regime === 'dark' ? ', dark' : ', daylight';
    return '<i class="fc ' + QUALITY_CLASS(h.score) + (i === 0 ? ' now' : '') +
      (atBest ? ' peak' : '') +
      (h.regime === 'gray' ? ' gray' : h.regime === 'twilight' ? ' dusk'
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
     with the modes that stretch is good for - the strip's colors say it,
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
    ' Color is how good the hour looks; the pale bar along the foot of a ' +
    'cell is daylight, and an amber one is the gray line &mdash; sunset here, ' +
    'but not yet 80 km up, which is where the absorption is.' +
    /* The strip is hourly because the model is. The window itself is not, and
       the unit knows it to the minute: the sun leaves the ground at one time
       and the D layer 80 km up at another, and the gap is the whole event.
       Naming both makes the amber cell a thing somebody can be ready for
       rather than a color they notice afterwards. */
    grayWindow() + recordLine() + '</div>';
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
   the sun over the horizon where the operator is standing, and "gray" down to
   D_LAYER_DIP - 9.03 degrees below, where the sun has left the ground but not
   yet the D layer 80 km up. That D-layer geometry is most of the shape of the
   HF strip. Up here it is worth almost nothing: D absorption falls as 1/f^2,
   so what costs 80 m its whole daylight costs 2 m nothing measurable. The
   inversion is weather at head height, and the ground's own sunrise is the
   one that governs it - so this reads the "lit" flip and not the gray hour.
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
/* The moon, for the moonbounce crowd, who will notice its absence before
   anybody notices the aurora: where it is from here, when it rises and
   sets, how far away it is against the average (the path goes there and
   back, so the loss runs as the fourth power of the distance), how far it
   sits from the sun, and the declination - a moon low in the south has the
   galaxy behind it. All of it from a clock and the QTH; nothing fetched.
   And the meteor calendar beside it: the shower on now, or the next. */
function localClock(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return isNaN(d) ? '' : d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}
function moonBox(moon, met) {
  const parts = [];
  if (moon) {
    const where = moon.up
      ? '<b>' + Math.round(moon.altitude) + '°</b> above the horizon at a bearing of <b>' + Math.round(moon.azimuth) + '°</b>' +
        (moon.set ? ', setting at <b>' + localClock(moon.set) + '</b>' : '')
      : 'below the horizon' + (moon.rise ? ', rising at <b>' + localClock(moon.rise) + '</b>' : '');
    const dist = moon.loss_db < -0.3 ? 'near perigee, ' + (-moon.loss_db).toFixed(1) + ' dB better than the average path'
      : moon.loss_db > 0.3 ? 'near apogee, ' + moon.loss_db.toFixed(1) + ' dB down on the average path'
      : 'about an average distance, ' + Math.round(moon.distance_km / 1000) + ',000 km';
    parts.push('<b>Moonbounce.</b> The moon is ' + where + ' — ' + dist + ', declination ' +
      (moon.declination >= 0 ? '+' : '') + Math.round(moon.declination) + '°, ' + Math.round(moon.sun_separation) +
      '° from the sun, ' + escapeHTML(moon.phase.name) + '. ' +
      (moon.up ? 'The verdict is <b>' + escapeHTML(moon.verdict) + '</b>: ' + escapeHTML((moon.reasons || []).join('; ')) + '.'
               : 'Nothing to point at until it rises.') +
      ' The loss runs as the fourth power of the distance because the path goes there and back; a moon low in the south has the galaxy behind it, and the sun within fifteen degrees puts its noise in the beam.' +
      ' <a href="/eme">The EME page</a> paints who else can see it.');
  }
  if (met) {
    const line = met.now
      ? 'The <b>' + escapeHTML(met.now.name) + '</b> are on — peak ' + escapeHTML(met.now.peak) + ', ZHR about ' + met.now.zhr + '.'
      : met.next ? 'The next shower is the <b>' + escapeHTML(met.next.name) + '</b>, peaking ' + escapeHTML(met.next.peak) +
        ' (' + met.next.days + ' days), ZHR about ' + met.next.zhr + '.' : '';
    if (line) parts.push('<b>Meteor calendar.</b> ' + line + ' Random meteors are there every morning near 06:00; a shower is when it is worth staying up.');
  }
  return parts.length ? '<div class="tiny muted mt">' + parts.join('<br>') + '</div>' : '';
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
  const moon = bpSky && bpSky.moon;
  if (moon) bits.push('<span class="pill ' + ({good: 'q4', fair: 'q2', poor: 'q1', down: 'q0'}[moon.verdict] || 'q0') +
    '">Moon: ' + (moon.up ? moon.verdict + ', ' + Math.round(moon.altitude) + '° up' : 'down') + '</span>');
  const met = bpSky && bpSky.meteors;
  if (met && met.now) bits.push('<span class="pill q4">' + escapeHTML(met.now.name) + ' peak' + (met.now.days ? (met.now.days > 0 ? ' in ' + met.now.days + ' d' : ' ' + (-met.now.days) + ' d ago') : ' today') + '</span>');
  return '<div class="condbox">' +
    '<div class="condhead"><span class="panel-title" style="margin:0">' +
      'Conditions on ' + bandTag(band.name) + ' now</span>' + bits.join(' ') +
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
      'side of the Earth has turned to face the way the planet is traveling ' +
      'and sweeps the debris up head-on instead of catching it from behind. ' +
      'In midsummer those two land almost together; in December they are ' +
      'nearly two hours apart. Neither is a prediction &mdash; both are just ' +
      'when it is worth going to look.</div>' +
    moonBox(moon, met) +
    '<div class="tiny muted mt">The gray line does almost nothing for you up ' +
      'here. D-layer absorption falls as 1/f&sup2;, so what shuts 80 m all ' +
      'day costs 2 m nothing you could measure &mdash; the whole business of ' +
      'the sun setting on the ground before it sets 80 km up is an HF story. ' +
      'And line of sight is always there, at every hour: for that, the ' +
      '<a href="/lab#ant">antenna and terrain tools</a> are the ones that ' +
      'answer.</div></div>';
}

/* ---------------------------------------------------- where the band reaches */
/* The path model asked for every cell of a grid, drawn as a map with a
   viewport on it: drag to pan, the wheel or a pinch to zoom, a double tap
   to zoom in, a press to come back to the whole world. The world is the
   five-degree grid; a zoomed window asks the model for the same area at a
   finer step - half a degree and below - once the hand has stopped, so the
   edge of a skip zone is real detail and not the coarse grid stretched.
   Fetched on the band button and on a settled zoom, never polled; drawn at
   half resolution while the hand is moving and in full when it stops. The
   coast is the EME page's. */
let bpCoast = null, bpReachFor = null;
fetch('/static/maps/coast.json').then(r => r.json()).then(c => { bpCoast = c; if (bpReachFor) bpReachDraw(false); }).catch(() => {});

/* The borders, and a finer coast, each fetched the first time the zoom
   wants it and never before: countries are small and always drawn,
   states arrive at a few times in, US counties well in - a person
   estimating a null's edge against a county line has zoomed to where a
   county is a shape. "Auto" is that rule; the select overrides it. */
const bpLayers = {countries: null, states: null, counties: null, coast50: null};
const bpLayerFiles = {countries: 'borders-countries.json', states: 'borders-states.json', counties: 'borders-counties.json', coast50: 'coast-50m.json'};
function bpLayer(name) {
  if (bpLayers[name] || bpLayers[name] === false) return bpLayers[name] || null;
  bpLayers[name] = false;                          // asked for; not here yet
  fetch('/static/maps/' + bpLayerFiles[name]).then(r => r.json()).then(lines => { bpLayers[name] = lines; if (bpReachFor) bpReachDraw(false); })
    .catch(() => { bpLayers[name] = null; });
  return null;
}
function bpBorderLevel() {
  const sel = document.getElementById('bp-reach-borders');
  const mode = sel ? sel.value : 'auto';
  if (mode !== 'auto') return mode;
  return bpView.zoom >= 7 ? 'counties' : bpView.zoom >= 2.5 ? 'states' : 'countries';
}

/* A continuous ramp in the band's own color - dark where the band is shut,
   the band's hue where it is good, paling towards white at the best - so the
   eye reads a field and not a legend, and reads which band's field it is
   from the same color the band has on its button. The stops are made from
   the color: the page's background at the bottom, the hue at 70, and the
   hue lightened at the top. The legend's gradient is written from the same
   stops, so it cannot drift from the map. */
const REACH_BG = [13, 17, 23];                      // --bg
const REACH_FALLBACK = '#4ade80';                    // a band with no color: 20 m's
function reachStops(hex) {
  const c = /^#([0-9a-f]{6})$/i.test(hex || '') ? hex : REACH_FALLBACK;
  const rgb = [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));
  const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return [[0, mix(REACH_BG, rgb, 0.08)], [15, mix(REACH_BG, rgb, 0.22)], [40, mix(REACH_BG, rgb, 0.55)],
          [70, rgb], [100, mix(rgb, [255, 255, 255], 0.6)]];
}
function reachLUT(stops) {
  const lut = new Uint8ClampedArray(101 * 3);
  for (let v = 0; v <= 100; v++) {
    for (let i = 1; i < stops.length; i++) {
      const [s1, c1] = stops[i - 1], [s2, c2] = stops[i];
      if (v <= s2) {
        const t = (v - s1) / (s2 - s1);
        lut[v * 3] = c1[0] + (c2[0] - c1[0]) * t; lut[v * 3 + 1] = c1[1] + (c2[1] - c1[1]) * t; lut[v * 3 + 2] = c1[2] + (c2[2] - c1[2]) * t;
        break;
      }
    }
  }
  return lut;
}
let REACH_LUT = reachLUT(reachStops(REACH_FALLBACK));
/* The map and its legend take the band's color together. */
function reachPaint(bandName) {
  const stops = reachStops(bandColor(bandName));
  REACH_LUT = reachLUT(stops);
  const ramp = document.querySelector('#bp-reach .bp-reach-ramp');
  if (ramp) ramp.style.background = 'linear-gradient(90deg, ' +
    stops.map(([v, c]) => 'rgb(' + c.join(',') + ') ' + v + '%').join(', ') + ')';
}
const REACH_CONTOURS = [20, 40, 60, 80];        // the isolines, like a weather map's

function cubic(p0, p1, p2, p3, t) {
  return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);
}

/* The score at any point, a cubic pass across the sixteen nearest cell
   centers. The world grid wraps in longitude; a window grid clamps. */
function reachAt(d, lat, lon) {
  const fy = (d.lat0 - lat) / d.step;
  let dl = lon - d.lon0;
  if (!d.window) dl = ((dl % 360) + 360) % 360;
  const fx = dl / d.step;
  const y1 = Math.floor(fy), x1 = Math.floor(fx);
  const ty = fy - y1, tx = fx - x1;
  const c = d.cells, rows = d.rows, cols = d.cols;
  const col = d.window ? k => Math.min(cols - 1, Math.max(0, k)) : k => ((k % cols) + cols) % cols;
  const cell = (r, k) => c[Math.min(rows - 1, Math.max(0, r)) * cols + col(k)];
  const r0 = cubic(cell(y1 - 1, x1 - 1), cell(y1 - 1, x1), cell(y1 - 1, x1 + 1), cell(y1 - 1, x1 + 2), tx);
  const r1 = cubic(cell(y1, x1 - 1), cell(y1, x1), cell(y1, x1 + 1), cell(y1, x1 + 2), tx);
  const r2 = cubic(cell(y1 + 1, x1 - 1), cell(y1 + 1, x1), cell(y1 + 1, x1 + 1), cell(y1 + 1, x1 + 2), tx);
  const r3 = cubic(cell(y1 + 2, x1 - 1), cell(y1 + 2, x1), cell(y1 + 2, x1 + 1), cell(y1 + 2, x1 + 2), tx);
  return Math.max(0, Math.min(100, cubic(r0, r1, r2, r3, ty)));
}

/* Whether a window grid covers this point, with a cell to spare. */
function inWindow(w, lat, lon) {
  if (!w || !w.window) return false;
  if (lat > w.lat0 || lat < w.lat0 - (w.rows - 1) * w.step) return false;
  const dl = ((lon - w.lon0) % 360 + 360) % 360;
  return dl <= (w.cols - 1) * w.step;
}

/* The viewport: the middle of the picture and how far in it is. Zoom 1 is
   the whole world with the operator at the center. */
const bpView = {lat: 0, lon: 0, zoom: 1, dragging: false, refined: null, timer: null, band: null};

function bpReachDraw(coarse) {
  const d = bpReachFor;
  const canvas = document.getElementById('bp-reach-map');
  if (!d || !canvas) return;
  const full = {w: canvas.width, h: canvas.height};
  const scale = coarse ? 2 : 1;
  const W = full.w / scale, H = full.h / scale;
  const ctx = canvas.getContext('2d');
  const view = bpView;
  const spanLon = 360 / view.zoom, spanLat = 180 / view.zoom;
  const wrap = lon => ((lon + 180) % 360 + 360) % 360 - 180;
  const lonAt = x => wrap(view.lon - spanLon / 2 + (x + 0.5) * (spanLon / W));
  const latAt = y => view.lat + spanLat / 2 - (y + 0.5) * (spanLat / H);
  const fine = view.refined && view.refined.band === view.band ? view.refined : null;
  const img = ctx.createImageData(W, H);
  const px = img.data;
  const score = new Float32Array(W * H);
  const D2R = Math.PI / 180;
  const sd = Math.sin(d.sun.dec * D2R), cd = Math.cos(d.sun.dec * D2R);
  for (let y = 0; y < H; y++) {
    const lat = latAt(y);
    const sl = Math.sin(lat * D2R), cl = Math.cos(lat * D2R);
    for (let x = 0; x < W; x++) {
      const lon = lonAt(x);
      const v = (fine && inWindow(fine, lat, lon)) ? reachAt(fine, lat, lon) : reachAt(d, lat, lon);
      score[y * W + x] = v;
      const k = Math.round(v) * 3;
      const alt = Math.asin(sl * sd + cl * cd * Math.cos((d.sun.gha + lon) * D2R)) / D2R;
      const t = Math.max(0, Math.min(1, (alt + 12) / 18));
      const shade = 0.42 + 0.58 * t * t * (3 - 2 * t);
      const o = (y * W + x) * 4;
      px[o] = REACH_LUT[k] * shade; px[o + 1] = REACH_LUT[k + 1] * shade; px[o + 2] = REACH_LUT[k + 2] * shade; px[o + 3] = 255;
    }
  }
  /* The isolines: where the score crosses a contour between a pixel and
     its neighbour, that pixel is drawn a shade darker - a line one pixel
     wide at every threshold, the way a weather map draws its fronts. */
  if (!coarse) {
    const band = v => { let b = 0; for (const c of REACH_CONTOURS) if (v >= c) b++; return b; };
    for (let y = 0; y < H - 1; y++) {
      for (let x = 0; x < W - 1; x++) {
        const i = y * W + x, b = band(score[i]);
        if (b !== band(score[i + 1]) || b !== band(score[i + W])) {
          const o = i * 4;
          px[o] *= 0.55; px[o + 1] *= 0.55; px[o + 2] *= 0.55;
        }
      }
    }
  }
  if (scale === 1) {
    ctx.putImageData(img, 0, 0);
  } else {
    const off = document.createElement('canvas'); off.width = W; off.height = H;
    off.getContext('2d').putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(off, 0, 0, full.w, full.h);
  }
  const X = lon => (((lon - view.lon + spanLon / 2) % 360 + 360) % 360) * (full.w / spanLon);
  const Y = lat => (view.lat + spanLat / 2 - lat) * (full.h / spanLat);
  const every = view.zoom >= 8 ? 5 : view.zoom >= 3 ? 10 : 30;
  ctx.strokeStyle = 'rgba(255,255,255,.08)'; ctx.lineWidth = 1;
  for (let lon = -180; lon < 180; lon += every) { const x = X(lon); if (x >= 0 && x <= full.w) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, full.h); ctx.stroke(); } }
  for (let lat = -90 + every; lat < 90; lat += every) { const y = Y(lat); if (y >= 0 && y <= full.h) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(full.w, y); ctx.stroke(); } }
  const strokeLines = (lines, style, width) => {
    if (!lines) return;
    ctx.strokeStyle = style; ctx.lineWidth = width; ctx.lineJoin = 'round';
    const top = view.lat + spanLat / 2, bottom = view.lat - spanLat / 2;
    ctx.beginPath();
    lines.forEach(line => {
      /* a line wholly above or below the view is not drawn at all */
      const p0 = line[0];
      if (line.length < 40 && (p0[1] > top + 5 || p0[1] < bottom - 5)) return;
      let last = null;
      line.forEach(p => {
        const x = X(p[0]), y = Y(p[1]);
        if (last === null || Math.abs(x - last) > full.w / 2) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        last = x;
      });
    });
    ctx.stroke();
  };
  const level = bpBorderLevel();
  if (level !== 'none') {
    strokeLines(bpLayer('countries'), 'rgba(255,255,255,.42)', view.zoom >= 3 ? 1.1 : 0.9);
    if (level === 'states' || level === 'counties') strokeLines(bpLayer('states'), 'rgba(255,255,255,.30)', 0.9);
    if (level === 'counties') strokeLines(bpLayer('counties'), 'rgba(255,255,255,.22)', 0.8);
  }
  const coast = view.zoom >= 3 ? (bpLayer('coast50') || bpCoast) : bpCoast;
  strokeLines(coast, 'rgba(245,248,252,.65)', view.zoom >= 3 ? 1.5 : 1.2);
  if (d.qth) {
    const x = X(d.qth.lon), y = Y(d.qth.lat);
    if (x >= -20 && x <= full.w + 20 && y >= -20 && y <= full.h + 20) {
      /* "You are here" is the one thing on the map that must be found at
         once, in any band's color - so it is the attention color, the
         safety orange that means look here and nothing else on the screen. */
      const here = getComputedStyle(document.documentElement).getPropertyValue('--attention').trim() || '#ff7a00';
      ctx.save();
      ctx.shadowColor = here; ctx.shadowBlur = 14;
      ctx.strokeStyle = here; ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.arc(x, y, 7, 0, 2 * Math.PI); ctx.stroke();
      ctx.restore();
      ctx.fillStyle = here; ctx.beginPath(); ctx.arc(x, y, 2.2, 0, 2 * Math.PI); ctx.fill();
    }
  }
  const zoomEl = document.getElementById('bp-reach-zoom');
  if (zoomEl) zoomEl.textContent = view.zoom > 1.05 ? '×' + (view.zoom < 10 ? view.zoom.toFixed(1) : Math.round(view.zoom)) + (fine ? ' · ' + fine.step + '° detail' : ' · 5° grid') : '';
}

/* A settled zoom asks the model for the window at a finer step. */
async function bpRefine() {
  const d = bpReachFor;
  if (!d || bpView.zoom < 1.8) { bpView.refined = null; return; }
  const spanLon = 360 / bpView.zoom, spanLat = 180 / bpView.zoom;
  const top = Math.min(89.5, bpView.lat + spanLat * 0.6), bottom = Math.max(-89.5, bpView.lat - spanLat * 0.6);
  const left = bpView.lon - spanLon * 0.6, span = Math.min(360, spanLon * 1.2);
  const step = bpView.zoom >= 12 ? 0.25 : bpView.zoom >= 6 ? 0.5 : bpView.zoom >= 3 ? 1 : 2.5;
  const key = bpView.band, mode = bpReachMode();
  try {
    const r = await fetch('/api/bandplan/reach?' + new URLSearchParams({band: key.split('|')[0], mode: mode, top: top.toFixed(2), bottom: bottom.toFixed(2), left: left.toFixed(2), span: span.toFixed(2), step: step}), {cache: 'no-store'});
    const w = await r.json();
    if (!w.ok || bpView.band !== key || bpReachMode() !== mode) return;
    w.band = key;
    bpView.refined = w;
    bpReachDraw(false);
  } catch (e) { /* the coarse grid stands */ }
}

function bpViewSettled() {
  clearTimeout(bpView.timer);
  bpView.timer = setTimeout(() => { bpReachDraw(false); bpRefine(); }, 350);
}

function bpZoomAt(factor, cx, cy) {
  const canvas = document.getElementById('bp-reach-map');
  const rect = canvas.getBoundingClientRect();
  const fx = (cx - rect.left) / rect.width, fy = (cy - rect.top) / rect.height;
  const spanLon = 360 / bpView.zoom, spanLat = 180 / bpView.zoom;
  const lonUnder = bpView.lon - spanLon / 2 + fx * spanLon, latUnder = bpView.lat + spanLat / 2 - fy * spanLat;
  bpView.zoom = Math.max(1, Math.min(24, bpView.zoom * factor));
  const nLon = 360 / bpView.zoom, nLat = 180 / bpView.zoom;
  bpView.lon = lonUnder - (fx - 0.5) * nLon;
  bpView.lat = Math.max(-90 + nLat / 2, Math.min(90 - nLat / 2, latUnder + (fy - 0.5) * nLat));
  if (bpView.zoom <= 1.001) { bpView.lat = 0; bpView.lon = bpReachFor && bpReachFor.qth ? bpReachFor.qth.lon : 0; }
  bpReachDraw(true);
  bpViewSettled();
}

function bpReachBind() {
  const canvas = document.getElementById('bp-reach-map');
  if (!canvas || canvas.dataset.bound) return;
  canvas.dataset.bound = '1';
  const pointers = new Map();
  let pinch = null, lastTap = 0;
  canvas.addEventListener('wheel', e => { e.preventDefault(); bpZoomAt(e.deltaY < 0 ? 1.25 : 0.8, e.clientX, e.clientY); }, {passive: false});
  canvas.addEventListener('pointerdown', e => {
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = {dist: Math.hypot(a.x - b.x, a.y - b.y), zoom: bpView.zoom};
    } else if (pointers.size === 1) {
      const now = Date.now();
      if (now - lastTap < 320) { bpZoomAt(2, e.clientX, e.clientY); lastTap = 0; } else lastTap = now;
    }
  });
  canvas.addEventListener('pointermove', e => {
    if (!pointers.has(e.pointerId)) return;
    const was = pointers.get(e.pointerId);
    pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
    const rect = canvas.getBoundingClientRect();
    if (pointers.size === 2 && pinch) {
      const [a, b] = [...pointers.values()];
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      const want = Math.max(1, Math.min(24, pinch.zoom * dist / pinch.dist));
      bpZoomAt(want / bpView.zoom, (a.x + b.x) / 2, (a.y + b.y) / 2);
      return;
    }
    if (pointers.size === 1 && (e.buttons & 1 || e.pointerType === 'touch')) {
      const spanLon = 360 / bpView.zoom, spanLat = 180 / bpView.zoom;
      bpView.lon -= (e.clientX - was.x) / rect.width * spanLon;
      bpView.lat = Math.max(-90 + spanLat / 2, Math.min(90 - spanLat / 2, bpView.lat + (e.clientY - was.y) / rect.height * spanLat));
      bpView.dragging = true;
      bpReachDraw(true);
      bpViewSettled();
    }
  });
  const up = e => { pointers.delete(e.pointerId); if (pointers.size < 2) pinch = null; bpView.dragging = false; };
  canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up); canvas.addEventListener('pointerleave', up);
  document.querySelectorAll('input[name="bp-reach-mode"]').forEach(r => r.addEventListener('change', () => {
    remember('bandplan.reachmode', bpReachMode());
    const band = bpData && bpData.bands.find(b => b.name === bpBand);
    if (band) bpReach(band);
  }));
  const keptMode = recall('bandplan.reachmode', 'oneway');
  const modeEl = document.querySelector('input[name="bp-reach-mode"][value="' + keptMode + '"]');
  if (modeEl) modeEl.checked = true;
  const borders = document.getElementById('bp-reach-borders');
  if (borders) borders.addEventListener('change', () => { remember('bandplan.borders', borders.value); bpReachDraw(false); });
  if (borders) { const kept = recall('bandplan.borders', 'auto'); if ([...borders.options].some(o => o.value === kept)) borders.value = kept; }
  const reset = document.getElementById('bp-reach-reset');
  if (reset) reset.addEventListener('click', () => { bpView.zoom = 1; bpView.lat = 0; bpView.lon = bpReachFor && bpReachFor.qth ? bpReachFor.qth.lon : 0; bpView.refined = null; bpReachDraw(false); });
}

/* One way or the round trip - see propagation.reach_map. */
function bpReachMode() {
  const el = document.querySelector('input[name="bp-reach-mode"]:checked');
  return el && el.value === 'round' ? 'round' : 'oneway';
}
/* The emission - SSB, AM, FM, CW, FT8. It decides what the far end needs
   above the noise, so it decides the ground wave's reach, on 11 m the
   lawful power with it, and - since the map learned to add up a skywave
   path - how much of the sky's reach can actually be heard. The sky does
   not care what is modulated onto it; the far end's receiver does. */
const EMISSIONS = {ssb: 'SSB', am: 'AM', fm: 'FM', cw: 'CW', ft8: 'FT8'};
const CB_EMISSIONS = {am: 4, fm: 4, ssb: 12};      // 47 CFR 95.967: the watts each may run
function bpReachEmission() {
  const el = document.querySelector('input[name="bp-reach-em"]:checked');
  return el && EMISSIONS[el.value] ? el.value : 'ssb';
}
function bpSetEmission(em) {
  const r = document.querySelector('input[name="bp-reach-em"][value="' + em + '"]');
  if (r) r.checked = true;
}
/* 11 m is CB, and CB is 4 W carrier on AM or FM and 12 W PEP on SSB, with
   no CW or data. So on that band the mode is held to those three, the
   watts box is set to the ceiling for the mode and capped there, and the
   operator's own figure is kept to one side and put back on leaving. */
function bpReachLaw(band) {
  const w = document.getElementById('bp-reach-w');
  const cb = !!(band && band.personal === 'CB');
  document.querySelectorAll('input[name="bp-reach-em"]').forEach(r => { r.disabled = cb && !(r.value in CB_EMISSIONS); });
  if (cb) {
    let em = bpReachEmission();
    if (!(em in CB_EMISSIONS)) { em = 'am'; bpSetEmission(em); }
    const cap = CB_EMISSIONS[em];
    if (w) {
      if (!w.dataset.cb) { w.dataset.cb = '1'; w.dataset.was = w.value; }
      w.max = cap;
      if (+w.value > cap || w.dataset.cap !== String(cap)) w.value = cap;
      w.dataset.cap = String(cap);
    }
  } else if (w && w.dataset.cb) {
    w.max = 1500;
    if (w.dataset.was) w.value = w.dataset.was;
    delete w.dataset.cb; delete w.dataset.cap; delete w.dataset.was;
  }
}
let bpReachCache = {};
/* The operator's own antenna, for the map. The Lab remembers what was last
   designed there - kind and height - and the map opens on it, the way Make
   Contact pre-ticks the gear on the shelf; the controls on the panel change
   it for a look at another, and that choice is remembered here. Nothing is
   stored twice: the Lab's memory is read, and only the panel's own choice
   is kept by the panel. */
function bpReachAntenna() {
  const sel = document.getElementById('bp-reach-ant'), h = document.getElementById('bp-reach-h'), w = document.getElementById('bp-reach-w');
  const hd = document.getElementById('bp-reach-hd'), gnd = document.getElementById('bp-reach-gnd');
  if (!sel) return {};
  return {antenna: sel.value, height: h && h.value ? h.value : '30', watts: w && w.value ? w.value : '100',
          heading: hd && hd.value !== '' ? hd.value : '', ground: gnd ? gnd.value : 'average',
          emission: bpReachEmission()};
}
/* What the panel keeps between visits: the choices, with the operator's
   own watts rather than the CB ceiling standing in for them. */
function bpReachRemember(extra) {
  const w = document.getElementById('bp-reach-w');
  const own = bpReachAntenna();
  if (w && w.dataset.cb && w.dataset.was) own.watts = w.dataset.was;
  remember('bandplan.reach.antenna', Object.assign(own, extra || {}));
}
function bpReachSeed() {
  const sel = document.getElementById('bp-reach-ant'), h = document.getElementById('bp-reach-h'), w = document.getElementById('bp-reach-w');
  if (!sel || sel.dataset.seeded) return;
  sel.dataset.seeded = '1';
  const own = recall('bandplan.reach.antenna', null);
  const lab = recall('lab.antenna', null) || {};
  const kind = (own && own.antenna) || (lab.kind && [...sel.options].some(o => o.value === lab.kind) ? lab.kind : '') || 'dipole';
  sel.value = [...sel.options].some(o => o.value === kind) ? kind : 'dipole';
  if (h) h.value = (own && own.height) || (lab.height_ft > 0 ? Math.round(lab.height_ft) : 30);
  if (w) w.value = (own && own.watts) || (lab.watts > 0 ? Math.round(lab.watts) : 100);
  if (own && own.emission) bpSetEmission(own.emission);
  const hd = document.getElementById('bp-reach-hd'), gnd = document.getElementById('bp-reach-gnd');
  if (hd) hd.value = (own && own.heading !== undefined) ? own.heading : (lab.heading_deg >= 0 ? Math.round(lab.heading_deg) : '');
  if (gnd && own && own.ground) gnd.value = own.ground;
  /* The ground, rated rather than guessed: the soil and water surveys at the
     QTH (siteground.py), turned into the four grounds the map knows. Kept on
     the unit once rated, so it answers again without a signal. */
  const rateBtn = document.getElementById('bp-reach-gnd-rate');
  if (gnd && rateBtn && !rateBtn.dataset.wired) {
    rateBtn.dataset.wired = '1';
    rateBtn.addEventListener('click', async () => {
      rateBtn.disabled = true;
      rateBtn.textContent = 'asking the surveys...';
      try {
        const d = await (await fetch('/api/ground')).json();
        if (d.pattern && [...gnd.options].some(o => o.value === d.pattern)) {
          gnd.value = d.pattern;
          gnd.dispatchEvent(new Event('change', {bubbles: true}));
          rateBtn.textContent = 'rated: ' + (d.label || d.pattern).toLowerCase();
          rateBtn.title = (d.headline || '') + ' - more in the Lab, under Ground.';
        } else {
          rateBtn.textContent = 'rate mine';
          rateBtn.title = d.error || d.headline || 'no rating for here';
          if (typeof toast === 'function') toast('Ground not rated', d.error || d.headline || '');
        }
      } catch (e) {
        rateBtn.textContent = 'rate mine';
      } finally {
        rateBtn.disabled = false;
      }
    });
  }
  /* The NVIS switch: a low wire, and the map brought in to the one-hop
     window round the station, where NVIS lives. It is a way of asking the
     question; the answer is the critical frequency line, which says whether
     this band comes back from overhead at all. */
  const nvis = document.getElementById('bp-reach-nvis');
  if (nvis) {
    nvis.checked = !!(own && own.nvis);
    nvis.addEventListener('change', () => {
      const band = bpData && bpData.bands.find(b => b.name === bpBand);
      const extra = {nvis: nvis.checked};
      if (nvis.checked && band) {
        /* What was on the panel before the switch took it. Ticking this
           sets an inverted V a fifth of a wave up, and unticking used to
           set nothing back - so the panel kept the NVIS wire and the map
           drew the same picture either way. The whole point of the switch
           is the comparison, and there was none: a vertical and a low wire
           are 17 dB apart at the angle a hundred-kilometer hop needs, and
           the map was being asked to show that difference against itself.
           Kept in the remembered settings rather than on the element, so
           it survives a reload with the box already ticked. */
        extra.before = {antenna: sel.value, height: h ? h.value : null};
        const mhz = (band.low + band.high) / 2;
        sel.value = 'invertedv';
        if (h) h.value = Math.max(6, Math.round(0.2 * 983.571 / mhz));   // a fifth of a wavelength: where the image adds most straight up
        const qth = bpReachFor && bpReachFor.qth;
        if (qth) { bpView.zoom = 5; bpView.lat = qth.lat; bpView.lon = qth.lon; bpView.refined = null; }
      } else {
        const before = (recall('bandplan.reach.antenna', null) || {}).before;
        if (before) {
          if (before.antenna) sel.value = before.antenna;
          if (h && before.height) h.value = before.height;
        }
        extra.before = null;
      }
      bpReachRemember(extra);
      bpReachCache = {}; bpView.refined = null;
      if (band) bpReach(band);
    });
  }
  const ems = Array.from(document.querySelectorAll('input[name="bp-reach-em"]'));
  [sel, h, w, hd, gnd].concat(ems).forEach(el => el && el.addEventListener('change', () => {
    const band = bpData && bpData.bands.find(b => b.name === bpBand);
    if (el.name === 'bp-reach-em') bpReachLaw(band);    // a new mode on CB moves the ceiling
    bpReachRemember();
    bpReachCache = {}; bpView.refined = null;
    if (band) bpReach(band);
  }));
}
async function bpReach(band) {
  const box = document.getElementById('bp-reach');
  if (!box) return;
  bpReachSeed();
  bpReachLaw(band);
  const mode = bpReachMode();
  const ant = bpReachAntenna();
  const key = band.name.replace(/\s+/g, '') + '|' + mode + '|' + ant.antenna + '|' + ant.height + '|' + ant.watts + '|' + ant.emission;
  const hf = band.high <= 30;
  box.hidden = !hf;
  if (!hf) return;
  document.getElementById('bp-reach-band').innerHTML = bandTag(band.name);
  reachPaint(band.name);
  let d = bpReachCache[key];
  if (!d) {
    document.getElementById('bp-reach-when').textContent = 'working it out…';
    try {
      const r = await fetch('/api/bandplan/reach?' + new URLSearchParams(Object.assign({band: band.name.replace(/\s+/g, ''), mode: mode}, ant)), {cache: 'no-store'});
      d = await r.json();
    } catch (e) {
      document.getElementById('bp-reach-when').textContent = '';
      document.getElementById('bp-reach-note').textContent = 'no map just now';
      return;
    }
    if (!d.ok) { document.getElementById('bp-reach-note').textContent = d.error || 'no map just now'; return; }
    bpReachCache[key] = d;
  }
  if (bpBand !== band.name || bpReachMode() !== mode) return;   // the band or the mode moved on while this was fetched
  const fresh = bpView.band !== key;
  bpReachFor = d;
  bpView.band = key;
  if (fresh) {
    /* a new band keeps the viewport the hand set, but its detail is its own */
    bpView.refined = null;
    if (bpView.zoom <= 1.001) bpView.lon = d.qth ? d.qth.lon : 0;
  }
  bpReachBind();
  bpReachDraw(false);
  if (bpView.zoom >= 1.8) bpRefine();
  document.getElementById('bp-reach-when').textContent = 'at ' + hourLabel(d.at) + ':00' +
    (d.muf_here ? ' · MUF here ' + d.muf_here + ' MHz' : '') + (d.muf_source ? ' (' + d.muf_source + ')' : '');
  /* The switch reports what the antenna is, rather than what was last
     asked for. NVIS is not a mode anybody selects: an inverted V at 35 feet
     is an eighth of a wave up on 80 m and has its whole lobe overhead, and
     the same wire is a wavelength up on 10 m and works DX. So the box
     follows the height and the band, and if it ticks itself back on after
     being turned off, that is the answer - the line below names the height
     that would change it. */
  const nvisBox = document.getElementById('bp-reach-nvis');
  if (nvisBox && d.antenna) nvisBox.checked = !!d.antenna.nvis;
  /* The far end of a round trip: what the other station needs to answer -
     the gear, and in the US the license. Shown for the contact, not for the
     one-way path, because it is about the reply. */
  /* The critical frequency over the station decides NVIS, and the line says
     so whenever the antenna is a low one or the switch is on - a hole in the
     near zone is the sky's doing, not the antenna's, and it should not have
     to be guessed at. */
  const nvisWords = document.getElementById('bp-reach-nvis-words');
  if (nvisWords) {
    const low = d.antenna && d.antenna.height_wl <= 0.2;
    const on = (document.getElementById('bp-reach-nvis') || {}).checked;
    nvisWords.hidden = !(d.nvis && (low || on));
    if (d.nvis) nvisWords.innerHTML = '<b>NVIS ' + (d.nvis.open ? 'open' : 'shut') + ' on ' + escapeHTML(band.name) + ':</b> ' + escapeHTML(d.nvis.words) + '.';
  }
  /* The height's effect in numbers. The map's colors saturate over much of
     the near zone, so a wire raised from a quarter wave to a half looks the
     same shade while the model has moved it eleven decibels overhead; this
     line says so, against a dipole in free space, at three angles. */
  const gainLine = document.getElementById('bp-reach-gain');
  if (gainLine) {
    const g = d.antenna && d.antenna.gain;
    gainLine.hidden = !g;
    if (g) {
      const sgn = x => (x >= 0 ? '+' : '\u2212') + Math.abs(x).toFixed(1) + ' dB';
      const ft = Math.round(d.antenna.height_ft || 0);
      gainLine.innerHTML = '<b>This antenna at ' + ft + ' ft is ' + (g.height_wl || 0).toFixed(2) + ' of a wavelength up on ' + escapeHTML(band.name) + ':</b> ' +
        sgn(g.overhead_db) + ' straight up, ' + sgn(g.steep_db) + ' at 45\u00b0, ' + sgn(g.low_db) + ' at 20\u00b0, against a dipole in free space; ' +
        'its best angle is ' + g.best_deg + '\u00b0 at ' + sgn(g.best_db) + '. ' +
        (g.overhead_db >= 2 ? 'The ground\u2019s reflection is adding straight up: the county\u2019s height.'
         : g.overhead_db <= -4 ? 'The reflection is cancelling straight up: a DX height, with a dip over the county.'
         : 'Neither adding nor cancelling much straight up.')
        + (d.antenna.nvis
           ? ' <b>At this height on this band that is an NVIS antenna</b>, whatever the switch says - the lobe is overhead and there is no low-angle way out of it. '
             + (d.antenna.low_angle_ft
                ? 'About ' + d.antenna.low_angle_ft + ' ft is where the lobe leaves the zenith on ' + escapeHTML(band.name) + '.'
                : 'No sensible height moves the lobe off the zenith on this band.')
           : ' For NVIS on ' + escapeHTML(band.name) + ' you would come down to about ' + d.antenna.nvis_ft + ' ft.');
    }
  }
  /* Why the modes draw such different pictures. The map showed the effect
     and never said where it came from: one watt of FT8 draws what a hundred
     watts of SSB draws, which reads as a fault until somebody knows FT8
     decodes twenty-eight decibels below where SSB is readable. The figure
     was already on the page, in the mode selector's hover text, which is
     invisible on a touchscreen and unread on any. */
  const modeLine = document.getElementById('bp-reach-mode');
  if (modeLine) {
    const md = d.emission_depth;
    modeLine.hidden = !md;
    if (md) {
      const name = String(md.mode || '').toUpperCase();
      const equal = (d.watts || 0) * md.times;
      /* Whole numbers once they are big enough for a fraction to be noise:
         "631x" and not "631.0x", but "0.3 W" and not "0 W". */
      const round1 = x => x >= 10 ? Math.round(x).toLocaleString() : x.toFixed(1);
      const asWatts = round1(equal);
      const asTimes = round1(md.times);
      /* What the mode itself asks for, in the two numbers the comparison is
         made of: the slot it is copied in and how far above the noise it
         has to sit there. */
      const asks = escapeHTML(name) + ' is copied in ' + (md.bandwidth_hz >= 1000
          ? (md.bandwidth_hz / 1000).toFixed(1).replace(/\.0$/, '') + ' kHz'
          : md.bandwidth_hz + ' Hz')
        + ' and needs to sit ' + (md.snr_db >= 0 ? md.snr_db + ' dB above' : Math.abs(md.snr_db) + ' dB below')
        + ' the noise there';
      let s;
      if (md.vs_ssb_db > 0.5) {
        s = '<b>' + escapeHTML(name) + ' hears ' + md.vs_ssb_db.toFixed(1) + ' dB deeper than SSB</b> - '
          + asTimes + 'x in power. The ' + (d.watts || 0) + ' W on the panel reaches like '
          + asWatts + ' W of SSB would'
          + (equal > md.legal_watts ? ', which is past the legal limit - a mode can buy what an amplifier may not.' : '.');
      } else if (md.vs_ssb_db < -0.5) {
        s = '<b>' + escapeHTML(name) + ' needs ' + Math.abs(md.vs_ssb_db).toFixed(1) + ' dB more than SSB</b> - '
          + 'it is copied in a wider slot. The ' + (d.watts || 0) + ' W on the panel reaches like '
          + asWatts + ' W of SSB would.';
      } else {
        /* The default view, and the one most people will never change. Say
           what it is a picture of before saying what the others would be. */
        s = '<b>This map is a phone signal.</b> ' + asks
          + ', and that is what the colors are worked out from.';
      }
      const alts = Object.keys(md.others || {}).map(k =>
        k.toUpperCase() + ' hears ' + md.others[k].db.toFixed(1) + ' dB deeper ('
        + md.others[k].times.toLocaleString() + 'x the power)');
      if (alts.length) {
        s += ' The other modes are copied in different widths and need different margins: '
          + alts.join(', ') + '. Press one and the map is worked out again for it.'
          + ' The same gap on every band - it is the mode’s own, and does not move with frequency.';
      }
      modeLine.innerHTML = s;
    }
  }
  const far = document.getElementById('bp-reach-far');
  if (far) {
    const fe = d.far_end;
    far.hidden = !(mode === 'round' && fe);
    if (fe) far.innerHTML = '<b>At the far end</b>, to answer: ' + escapeHTML(fe.equipment) + '; ' + escapeHTML(fe.license_words) + '; ' + escapeHTML(fe.abroad) + '.';
  }
  const antWords = d.antenna
    ? 'Weighted for ' + escapeHTML((document.querySelector('#bp-reach-ant option:checked') || {}).textContent || d.antenna.kind) + ' ' + Math.round(d.antenna.height_ft || 0) + ' ft up - ' + (d.antenna.height_wl || 0).toFixed(2) + ' of a wavelength - over ' + escapeHTML((document.querySelector('#bp-reach-gnd option:checked') || {}).textContent || 'average ground') + (d.antenna.heading !== null && d.antenna.heading !== undefined ? ', laid at ' + Math.round(d.antenna.heading) + '°' : ', direction unknown so all round') + ': each path by the angle its first hop leaves at, the ground\'s reflection at that angle, and what the antenna puts that way. Real terrain still moves the lobes. '
    : 'The sky alone, every takeoff angle served equally, which no antenna does - pick yours above. ';
  document.getElementById('bp-reach-note').textContent = antWords +
    'A model, and labelled as one: one sonde’s reading anchoring a modelled sky, read at the midpoint of each path - the sun’s angle there, not here. ' +
    'It knows the geometry - inside the skip, one hop out to ' + d.one_hop_km + ' km, several past it, each hop paid for, the edges soft the way the layer is - and nothing of the far end’s antenna. ' +
    'Each cell is rated against its own hop’s ceiling, from the layer’s shape' + (d.nvis && d.nvis.m3000_of_layer ? ' (M(3000) ' + d.nvis.m3000_of_layer + ')' : '') + ': straight up the ceiling is the critical frequency itself, and a near hop crosses the D layer once and nearly straight, so the county is rated as the county and not as a long path. ' +
    'Ground wave to about ' + d.ground_km + ' km on ' + (EMISSIONS[d.emission] || 'SSB') + ' at ' + d.watts + ' W' + (d.emission === 'am' ? ' carrier' : '') +
    (d.watts_cap ? ' - the lawful ceiling on this band, whatever the box says (47 CFR 95.967)' : '') +
    '; the mode and the watts decide that and nothing else here. Drag to look round; the wheel, a pinch or a double tap to zoom in, and the model is asked again for that window in finer detail. What it is right about is the shape.';
}

function conditionBar(band, given) {
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
  const cond = given || conditionsFor(band);
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
        bandTag(band.name) + ' now</span>' +
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
            '<b>' + awayText(now.skip_km) + '</b>. The rating ' +
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
                ', at ' + now.ground_wave.watts + ' W' + (now.ground_wave.mode === 'am' ? ' carrier' : '') +
                ' on ' + escapeHTML(now.ground_wave.mode_label || 'SSB') + '. A horizontal antenna has almost none.'
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
      'on ' + bandTag(band.name) + ' right now</div>' +
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


/* ------------------------------------------- is it worth the effort? */
/* Four licenses, two rows of spectrum, and the width of it each may key
   up - stacked by the most a segment lets you do there. A horizontal bar
   a class, not a pie a class: the four are read against each other along
   one scale, and the megahertz are printed, because a pie hides the
   magnitude that is the whole argument. HF and VHF/UHF are separate bars
   because a Technician already holds nearly every VHF/UHF hertz; it is
   the General step that opens HF, where the world is. */
/* The same color for a mode as the band bar above uses - phone green, CW
   blue, data violet, image amber - because a reader who has just learned
   the bar's key should not have to learn a second one three inches down. */
const WORTH_COLOR = {phone: KIND_COLOR.phone || '#3fb950', cw: KIND_COLOR.cw || '#58a6ff',
                      data: KIND_COLOR.digital || '#bc8cff', image: KIND_COLOR.image || '#ffb454'};
const WORTH_NAME = {phone: 'phone', cw: 'CW', data: 'data', image: 'image'};

function worthBar(row, total, colors) {
  const W = 420, H = 18, gap = 2;
  const parts = [];
  let x = 0;
  const px = mhz => Math.max(0, mhz / total * W);
  const emissions = ['phone', 'image', 'data', 'cw'];
  emissions.forEach(k => {
    const mhz = (row.by || {})[k] || 0;
    if (!mhz) return;
    const w = px(mhz);
    parts.push(`<rect x="${x.toFixed(1)}" y="0" width="${Math.max(1, w - gap).toFixed(1)}" height="${H}" rx="2" fill="${colors[k]}"><title>${WORTH_NAME[k]}: ${mhz.toFixed(3)} MHz</title></rect>`);
    x += w;
  });
  (row.personal || []).forEach(p => {
    const w = px(p.mhz);
    parts.push(`<rect x="${x.toFixed(1)}" y="0" width="${Math.max(1.5, w - gap).toFixed(1)}" height="${H}" rx="2" fill="${colors.phone}"><title>${escapeHTML(p.label)}: ${p.mhz.toFixed(3)} MHz - voice, license-free</title></rect>`);
    x += Math.max(2, w);
  });
  parts.push(`<rect x="${x.toFixed(1)}" y="${H / 2 - 3}" width="${Math.max(0, W - x).toFixed(1)}" height="6" rx="3" fill="var(--line)"><title>not yours: ${(total - (row.mhz || 0) - (row.personal || []).reduce((a, p) => a + p.mhz, 0)).toFixed(3)} MHz</title></rect>`);
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none" role="img" aria-label="${escapeHTML(row.label)}">${parts.join('')}</svg>`;
}

function worthRender(d) {
  const box = document.getElementById('bp-worth');
  if (!box || !d) return;
  const legend = '<div class="row tiny muted" style="gap:.9rem;flex-wrap:wrap;margin:.2rem 0 .6rem">' +
    ['phone', 'image', 'data', 'cw'].map(k => `<span><i class="worth-swatch" style="background:${WORTH_COLOR[k]}"></i>${WORTH_NAME[k]}</span>`).join('') +
    '<span><i class="worth-swatch" style="background:var(--line)"></i>not yours</span>' +
    '<span class="muted">the color is the most a segment lets you do; CW is allowed wherever phone is</span></div>';
  const groups = d.groups.map(g => {
    const rows = g.rows.map(r => {
      const mine = (r.mhz || 0) + (r.personal || []).reduce((a, p) => a + p.mhz, 0);
      const pct = g.total_mhz ? Math.round(100 * mine / g.total_mhz) : 0;
      const what = r.personal && r.personal.length
        ? r.personal.map(p => p.label).join(' and ') + ' - voice'
        : ['phone', 'image', 'data', 'cw'].filter(k => (r.by || {})[k]).map(k => WORTH_NAME[k] + ' ' + r.by[k].toFixed(2)).join(', ');
      return `<tr><th scope="row">${escapeHTML(r.label)}</th><td class="worth-bar">${worthBar(r, g.total_mhz, WORTH_COLOR)}</td>` +
        `<td class="mono worth-num">${mine.toFixed(mine < 1 ? 2 : 1)} MHz <span class="muted">${r.personal && r.personal.length ? 'its own channels' : pct + '%'}</span></td><td class="tiny muted worth-what">${escapeHTML(what)}</td></tr>`;
    }).join('');
    return `<div class="worth-group"><div class="spread" style="align-items:baseline"><b>${escapeHTML(g.group)}</b> <span class="tiny muted">${g.total_mhz.toFixed(1)} MHz of amateur allocation in ${g.bands.length} bands &middot; reaches ${escapeHTML(g.reach)}</span></div>` +
      `<table class="worth">${rows}</table></div>`;
  }).join('');
  /* The power ceiling: a bar a radio, on the ham's own scale - decibels -
     because half a watt to fifteen hundred is three and a half thousand to
     one and a linear bar would show nothing but the amateur. The watts are
     printed; the decibels below 1500 W are the number an operator feels. */
  const power = (d.power || []);
  const DB_LO = 20, DB_HI = 62;                          // 0.1 W to 1500 W, in dBm
  const powerRows = power.map(r => {
    const w = Math.max(2, (r.dbm - DB_LO) / (DB_HI - DB_LO) * 420);
    /* the license family - earth tones, the strata - from palette.py */
    const CLASS_COLOR = window.CLASS_COLOR || {};
    const color = CLASS_COLOR[r.license] || CLASS_COLOR.ham || '#c9784a';
    const watts = r.watts >= 1000 ? (r.watts / 1000).toFixed(1) + ' kW' : r.watts + ' ' + r.unit;
    return `<tr class="${bpClass() === r.license || (bpClass() === 'Extra' && r.license === 'General') ? 'worth-me' : ''}"><th scope="row">${escapeHTML(r.label)}</th>` +
      `<td class="worth-bar"><svg viewBox="0 0 420 18" width="100%" height="18" preserveAspectRatio="none" role="img" aria-label="${escapeHTML(r.label)} ${watts}">` +
      `<rect x="0" y="6" width="420" height="6" rx="3" fill="var(--line)"/><rect x="0" y="0" width="${w.toFixed(1)}" height="18" rx="2" fill="${color}"><title>${escapeHTML(r.note)}</title></rect></svg></td>` +
      `<td class="mono worth-num">${watts} <span class="muted">${r.db_below ? '-' + r.db_below.toFixed(0) + ' dB' : 'the ceiling'}</span></td>` +
      `<td class="tiny muted worth-what">${escapeHTML(r.antenna)}</td></tr>`;
  }).join('');
  const powerBlock = `<div class="worth-group"><div class="spread" style="align-items:baseline"><b>Power</b> <span class="tiny muted">the most each radio may run, on a decibel scale - each 6 dB is an S-unit at the far end; the antenna rule beside it</span></div>` +
    `<table class="worth">${powerRows}</table></div>`;
  box.innerHTML = legend + groups + powerBlock +
    `<p class="tiny muted" style="margin:.6rem 0 0;max-width:84ch">The bars are to one scale within a row: the gray is what the row's whole allocation would be. ` +
    `Read across, the step that matters is the first one - from a license-free radio to a Technician, VHF and UHF go from a few channels to all of it, ` +
    `and HF from CB to ten meters with the world on it when the sun is up; the General step opens the rest of HF, and the Extra the last of every band. ` +
    `GMRS - a fee and a form, no exam - adds ${d.gmrs_mhz.toFixed(1)} MHz of UHF at 50 W with repeaters for a family, and is the one step that is not an exam. ` +
    `On power, a Technician's handheld on 2 m may run the same two or five watts as an FRS radio - and a beam on the roof, which the FRS radio may never have, is where the difference is made; the 1500 W is there when the band asks for it. ` +
    `Thirty-five questions from a pool of about four hundred, all of it in this program, is the Technician.</p>` +
    `<details class="derivation"><summary class="tiny">The same as a table</summary><table class="data tiny"><tr><th>group</th><th>license</th><th>MHz</th><th>of</th><th>by what you can do</th></tr>` +
    d.groups.map(g => g.rows.map(r => `<tr><td>${escapeHTML(g.group)}</td><td>${escapeHTML(r.label)}</td><td class="mono">${((r.mhz || 0) + (r.personal || []).reduce((a, p) => a + p.mhz, 0)).toFixed(3)}</td><td class="mono">${g.total_mhz.toFixed(3)}</td><td>${escapeHTML(r.personal && r.personal.length ? r.personal.map(p => p.label + ' ' + p.mhz.toFixed(3)).join('; ') : Object.entries(r.by || {}).map(([k, v]) => WORTH_NAME[k] + ' ' + v.toFixed(3)).join('; '))}</td></tr>`).join('')).join('') +
    `</table><table class="data tiny mt"><tr><th>radio</th><th>watts</th><th>dBm</th><th>below 1500 W</th><th>rule</th><th>antenna</th></tr>` +
    power.map(r => `<tr><td>${escapeHTML(r.label)}</td><td class="mono">${r.watts} ${escapeHTML(r.unit)}</td><td class="mono">${r.dbm}</td><td class="mono">${r.db_below} dB (${r.s_units} S-units)</td><td>${escapeHTML(r.note)}</td><td>${escapeHTML(r.antenna)}</td></tr>`).join('') +
    `</table></details>`;
  // the row of the class being read is marked, so the selector and the chart agree
  const cls = bpClass();
  box.querySelectorAll('table.worth tr').forEach(tr => tr.classList.toggle('worth-me', tr.querySelector('th').textContent === (cls === 'none' ? 'No license' : cls)));
}

let bpWorth = null;
api('/api/bandplan/allocation').then(d => { bpWorth = d; worthRender(d); }).catch(() => {});
document.getElementById('bp-class').addEventListener('change', () => { if (bpWorth) worthRender(bpWorth); });
