/* Band plan: colour by activity, shade what your licence class may not use. */

const KIND_COLOUR = {
  cw: '#58a6ff', digital: '#bc8cff', phone: '#3fb950', image: '#ffb454',
  beacon: '#f85149', satellite: '#39d3d8', repeater: '#ff8f3f',
  simplex: '#c9d13a', calling: '#ffffff', special: '#8b98a5',
};

let bpData = null, bpRegional = null, bpBand = null;

function bpClass() { return document.getElementById('bp-class').value; }
function bpState() { return document.getElementById('bp-state').value; }

async function bpLoad() {
  bpData = await api('/api/bandplan?class=' + encodeURIComponent(bpClass()));
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
      /* In the address, so a band can be linked to and comes back on reload. */
      history.replaceState(null, '', '#' + bpBand.replace(/\s+/g, ''));
      bpRender();
    }));
  /* Open on the band asked for, else on one this class can actually use
     rather than one that is entirely hatched out. */
  const asked = decodeURIComponent(location.hash.slice(1)).toLowerCase();
  const linked = asked && bpData.bands.find(
    b => b.name.replace(/\s+/g, '').toLowerCase() === asked.replace(/\s+/g, ''));
  if (linked) {
    bpBand = linked.name;
  } else if (!bpBand || !bpData.bands.some(b => b.name === bpBand)) {
    const usable = bpData.bands.find(b => b.privileges.length);
    bpBand = (usable || bpData.bands[0]).name;
  }
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
      '<div class="bandscale"><span>' + band.low + '</span><span>' + band.high + '</span></div>' +
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
  await postJSON('/api/settings', {licence_class: bpClass()}).catch(() => {});
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
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url; a.download = 'band-card.pdf';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast('One-page chart ready', 'Print it and pin it up');
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
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url; a.download = 'band-plan.pdf';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast('Band chart ready', 'Print it and pin it up');
  } catch (e) { toast('Could not build the chart', 'See data/elmer.log'); }
  btn.disabled = false; btn.textContent = 'Download chart (PDF)';
});

bpLoad();

/* Callsign lookup: the licence knows the class, so the operator need not. */
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

api('/api/propagation').then(d => { bpProp = d.ok ? d : null; }).catch(() => {});

function conditionsFor(band) {
  if (!bpProp) return null;
  const key = band.name.replace(/\s+/g, '');
  return (bpProp.bands || []).find(b => b.band === key) || null;
}

function segMiddle(a) {
  return a.high > a.low ? (a.low + a.high) / 2 : a.low;
}

/* The intention to carry across, read from what the segment is for. */

function segCardHTML(a, band, forPick) {
  const cond = conditionsFor(band);
  const you = a.you || {state: 'no'};
  const range = a.high > a.low ? a.low + '–' + a.high : String(a.low);
  const rate = cond
    ? '<div class="small"><b>' + escapeHTML(cond.rating) + '</b> on ' +
      escapeHTML(band.name) + ' right now' +
      (cond.note ? ' — ' + escapeHTML(cond.note) : '') + '</div>' +
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
