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
    btn.addEventListener('click', () => { bpBand = btn.dataset.band; bpRender(); }));
  /* Open on a band this class can actually use, rather than one that is
     entirely hatched out. */
  if (!bpBand || !bpData.bands.some(b => b.name === bpBand)) {
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

  /* The bar: activity in colour, privilege gaps hatched over the top. */
  const bars = band.activity.map(a => {
    const w = Math.max(0.35, pct(a.high) - pct(a.low));
    return '<i class="seg" style="left:' + pct(a.low).toFixed(3) + '%;width:' +
      w.toFixed(3) + '%;background:' + KIND_COLOUR[a.kind] + '" title="' +
      escapeHTML(a.low + (a.high !== a.low ? '–' + a.high : '') + ' MHz · ' + a.label) +
      '"></i>';
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

  const rows = band.activity.map(a => {
    const allowed = band.privileges.some(([lo, hi]) => lo <= a.low && a.high <= hi);
    return '<tr class="' + (allowed ? '' : 'denied') + '">' +
      '<td class="mono tiny">' + a.low + (a.high !== a.low ? '<br>' + a.high : '') + '</td>' +
      '<td><span class="dot" style="background:' + KIND_COLOUR[a.kind] + '"></span>' +
        escapeHTML((bpData.kinds.find(k => k[0] === a.kind) || [])[1] || a.kind) + '</td>' +
      '<td class="small">' + escapeHTML(a.label) + '</td>' +
      '<td>' + (allowed ? '<span class="pill good">yes</span>'
                        : '<span class="pill bad">no</span>') + '</td></tr>';
  }).join('');

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
        '<div><div class="panel-title">Where the activity is</div>' +
          '<table class="data"><tbody>' + rows + '</tbody></table></div>' +
      '</div>' +
    '</div>';

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
document.getElementById('bp-pdf').addEventListener('click', async () => {
  const btn = document.getElementById('bp-pdf');
  btn.disabled = true; btn.textContent = 'Building…';
  try {
    const res = await fetch('/api/bandplan/pdf', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({class: bpClass(), state: bpState(),
                            bands: bpData.bands.map(b => b.name)})});
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
  box.innerHTML =
    '<div class="panel-title">Nationwide interoperability channels</div>' +
    '<p class="tiny muted" style="margin:0 0 .5rem">Read from NIFOG version ' +
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
      '</tbody></table></div>').join('');
}).catch(() => {});
