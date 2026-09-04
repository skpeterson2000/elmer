/* Live band-conditions dashboard. */

const grid = document.getElementById('p-grid');

function ratingPill(rating, score) {
  const cls = score >= 3 ? 'good' : score === 2 ? 'warn' : 'bad';
  return '<span class="pill ' + cls + '">' + escapeHTML(rating) + '</span>';
}

function kClass(k) { return k >= 5 ? 'bad' : k >= 4 ? 'warn' : 'good'; }

async function load(force) {
  let d;
  try {
    d = await api('/api/propagation' + (force ? '?force=1' : ''));
  } catch (e) {
    document.getElementById('p-verdict').innerHTML =
      '<span class="muted">Space weather is unavailable &mdash; no network route to hamqsl.com.</span>';
    return;
  }
  if (!d.ok) {
    document.getElementById('p-verdict').innerHTML = '<span class="muted">' + escapeHTML(d.error) + '</span>';
    return;
  }

  document.getElementById('p-updated').textContent =
    'updated ' + d.updated + (d.cached ? ' (cached)' : '') + ' — source ' + d.source;
  document.getElementById('p-verdict').innerHTML =
    '<div class="row"><span class="pill ' + kClass(d.k_index) + '">' +
    escapeHTML(d.geomag || 'field') + '</span>' +
    '<span class="pill info">noise ' + escapeHTML(d.noise || 'n/a') + '</span>' +
    '<span class="pill">' + (d.located ? (d.is_day ? 'daylight at your QTH' : 'darkness at your QTH')
                                       : (d.is_day ? 'assuming daylight - no QTH set' : 'assuming darkness - no QTH set')) +
    '</span></div>' +
    '<p style="margin:.6rem 0 0">' + escapeHTML(d.verdict) + '</p>';

  const stats = [
    ['Solar flux', d.sfi, 'SFI 10.7 cm'],
    ['K index', d.k_index, 'geomagnetic, 0-9'],
    ['A index', d.a_index, 'daily average'],
    ['Sunspots', d.sunspots, 'visible count'],
    ['Est. MUF', d.muf + ' MHz', 'single 3000 km hop'],
    ['Est. foF2', d.fof2 + ' MHz', 'vertical critical freq'],
    ['Solar wind', Math.round(d.solar_wind) + ' km/s', 'particle speed'],
    ['X-ray', d.xray || 'n/a', 'flare background'],
  ];
  document.getElementById('p-stats').innerHTML = stats.map(([label, value, note]) =>
    '<div class="panel stat"><span class="stat-label">' + label + '</span>' +
    '<span class="stat-value">' + escapeHTML(String(value)) + '</span>' +
    '<span class="stat-note">' + note + '</span></div>').join('');

  document.getElementById('p-bands').innerHTML = d.bands.map(b =>
    '<div class="band-row">' +
      '<span class="band-name">' + b.band + '</span>' +
      ratingPill(b.rating, b.score) +
      '<span class="band-note">' + escapeHTML(b.note) + '</span>' +
    '</div>').join('');

  document.getElementById('p-vhf').innerHTML = Object.entries(d.vhf).map(([k, v]) =>
    '<div class="band-row" style="grid-template-columns:1fr auto">' +
      '<span class="small">' + escapeHTML(k.replace('/', ' — ').replace(/_/g, ' ')) + '</span>' +
      '<span class="pill ' + (/closed/i.test(v) ? '' : 'good') + '">' + escapeHTML(v) + '</span>' +
    '</div>').join('');

  if (d.elevation !== null) {
    document.getElementById('p-qth').innerHTML =
      'Sun is <b>' + d.elevation + '&deg;</b> ' + (d.elevation >= 0 ? 'above' : 'below') +
      ' your horizon, so ELMER is using the <b>' + (d.is_day ? 'daytime' : 'night-time') +
      '</b> band ratings and a MUF of <b>' + d.muf + ' MHz</b>.' +
      (Math.abs(d.elevation) < 8 ? ' You are near the grey line — watch the low bands.' : '');
  }

  document.querySelectorAll('[data-live]').forEach(el => {
    const v = d[el.dataset.live];
    el.textContent = v === undefined || v === null ? '—' : v;
  });
}

document.getElementById('p-refresh').addEventListener('click', () => load(true));
document.getElementById('p-save').addEventListener('click', async () => {
  const loc = gridToLatLon(grid.value);
  if (!loc) { toast('Not a grid square', 'Use a Maidenhead locator such as EM79 or EM79wp'); return; }
  await postJSON('/api/settings', { location: loc });
  toast('QTH set', loc.grid + ' → ' + loc.lat + ', ' + loc.lon);
  load(true);
});
grid.addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('p-save').click(); });

load(false);
setInterval(() => load(false), 5 * 60 * 1000);
