/* Live band-conditions dashboard. */

const qthPicker = initPlace('q-place', {onPick: place => { if (place) saveAndReload(place); }});

async function saveAndReload(place) {
  await saveQTH(place);
  window.QTH = place;
  toast('QTH set', place.short + ' · ' + place.grid +
        ' — the path tool in the Lab uses this too');
  load(true);
}

function ratingPill(rating, score) {
  const cls = score >= 3 ? 'good' : score === 2 ? 'warn' : 'bad';
  return '<span class="pill ' + cls + '">' + escapeHTML(rating) + '</span>';
}

function kClass(k) { return k >= 5 ? 'bad' : k >= 4 ? 'warn' : 'good'; }

/* Kept in step with propagation.CALIBRATION_KM, for the "nothing in range" line. */
const PROP_CAL_KM = 5000;

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
    '<span class="pill' + (d.regime === 'grey' ? ' good' : '') + '">' +
    (d.located
      ? {lit: 'daylight at your QTH', grey: 'grey line at your QTH',
         dark: 'darkness at your QTH',
         twilight: 'twilight at your QTH - no true grey line'}[d.regime]
      : (d.is_day ? 'assuming daylight - no QTH set'
                  : 'assuming darkness - no QTH set')) +
    '</span></div>' +
    '<p style="margin:.6rem 0 0">' + escapeHTML(d.verdict) + '</p>';

  /* Where the MUF and foF2 came from. These two are the only numbers on the
     page that are not simply read off a feed, and until they said so the same
     foF2 appeared here as 2.9 and in the Lab as 5.8 with nothing to explain
     which was which. The Lab quotes one sonde's reading; this is the model
     that sonde has corrected, at your sun angle rather than at its own, so
     the two are close but not identical and both are now labelled. */
  const cal = d.calibration;
  const measured = d.muf_source !== 'modelled' && cal;
  const provenance = !cal
    ? 'modelled &mdash; no sonde in range'
    : d.muf_source === 'bounded'
      ? 'sonde disagrees with the model by more than it is allowed to; held partway'
      : cal.stations + ' sonde' + (cal.stations === 1 ? '' : 's') +
        ', nearest ' + cal.nearest_km + ' km';

  const stats = [
    ['Solar flux', d.sfi, 'SFI 10.7 cm'],
    ['K index', d.k_index, 'geomagnetic, 0-9'],
    ['A index', d.a_index, 'daily average'],
    ['Sunspots', d.sunspots, 'visible count'],
    [(measured ? 'MUF' : 'Est. MUF'), d.muf + ' MHz', provenance],
    [(measured ? 'foF2' : 'Est. foF2'), d.fof2 + ' MHz', provenance],
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
      '</b> band ratings and a MUF of <b>' + d.muf + ' MHz</b>' +
      (cal ? ', which is the model corrected to meet <b>' + cal.stations + '</b> ionosonde' +
             (cal.stations === 1 ? '' : 's') + ' &mdash; nearest <b>' +
             escapeHTML(cal.nearest) + '</b>, ' + cal.nearest_km + ' km away, reading foF2 ' +
             cal.measured_fof2 + ' MHz ' + cal.age_minutes + ' min ago. ' +
             'Each reading is compared with what the model says at <i>that station\'s</i> ' +
             'sun angle, so the correction travels without carrying the station\'s daylight with it.'
          : '. No ionosonde within ' + Math.round(PROP_CAL_KM) + ' km, so that figure is ' +
            'the plain model.') +
      /* The grey line is a state the model names, not a caption fired by a
         threshold that agreed with nothing else on the page. It runs from your
         sunset to the D layer's, which is the stretch over which this page's
         own absorption figure falls to zero. */
      (d.regime === 'grey'
        ? ' <b>You are on the grey line.</b> The sun has set here but not on ' +
          'the D layer 80 km up, so absorption is collapsing while the F ' +
          'layer stays ionised - this is the hour 160 and 80 reach furthest, ' +
          'and it closes when the sun is nine degrees down.'
        : d.regime === 'twilight'
          ? ' <b>Twilight, not a grey line.</b> The sun is below your horizon ' +
            'but it will not get below the D layer\'s tonight - at this ' +
            'latitude and season it stays lit 80 km up until it comes back ' +
            'round, so absorption never reaches zero and the low bands never ' +
            'get the hour they get further south.'
        : d.regime === 'lit' && d.elevation < 4
          ? ' The sun is low; the grey line is not far off.'
          : '');
  }

  document.querySelectorAll('[data-live]').forEach(el => {
    const v = d[el.dataset.live];
    el.textContent = v === undefined || v === null ? '—' : v;
  });
}

document.getElementById('p-refresh').addEventListener('click', () => load(true));

document.getElementById('q-save').addEventListener('click', async () => {
  if (!qthPicker) return;
  if (!qthPicker.get()) await qthPicker.lookup();
  const place = qthPicker.get();
  if (!place) { toast('Not found', 'Try a grid square, coordinates, or add a state'); return; }
  saveAndReload(place);
});

const locateBtn = document.getElementById('q-locate');
if (locateBtn) {
  locationAvailable().then(ok => { if (ok) locateBtn.hidden = false; });
  locateBtn.addEventListener('click', async () => {
    locateBtn.textContent = 'Locating…';
    try {
      const place = await locateMe();
      document.getElementById('q-place').value = place.short;
      qthPicker.set(place, true);
      saveAndReload(place);
    } catch (e) {
      toast('Could not locate you',
            (e && e.message ? e.message + '. ' : '') +
            'Type a place name or grid square instead.');
    }
    locateBtn.textContent = 'Locate me';
  });
}

load(false);
setInterval(() => load(false), 5 * 60 * 1000);
