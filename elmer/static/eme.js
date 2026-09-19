/* The moon's window, painted on the Earth.

   The server hands over the moon's hour angle, declination and distance at
   every quarter hour of the next day, and the sun's beside it. Everything on
   the map is then one line of trigonometry per pixel - is the moon above the
   horizon here, and how far - which is cheap enough to redo on every move of
   the slider, even on a Pi. The far end's opening and closing times are the
   one thing asked of the server again, because they are worked out finer
   than the track. */

const EME_W = 720, EME_H = 360;
const D2R = Math.PI / 180;
let emeData = null, emeCoast = null, emeIndex = 0, emeFar = null;

initPlace('q-place', {onPick: place => { if (place) saveAndGo(place); }});

async function saveAndGo(place) {
  await saveQTH(place);
  window.QTH = place;
  toast('QTH set', place.short + ' · ' + place.grid);
  loadEME();
}

function clock(iso) {
  const d = new Date(iso);
  return isNaN(d) ? '' : d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}
function dayClock(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const today = new Date().toDateString() === d.toDateString();
  return (today ? '' : d.toLocaleDateString([], {weekday: 'short'}) + ' ') + clock(iso);
}

/* The altitude of a body at (lat, lon) given its Greenwich hour angle and
   declination - the same line the server uses for the sun. */
function altitudeAt(lat, lon, gha, dec) {
  const latR = lat * D2R, decR = dec * D2R, lha = (gha + lon) * D2R;
  const s = Math.sin(latR) * Math.sin(decR) + Math.cos(latR) * Math.cos(decR) * Math.cos(lha);
  return Math.asin(Math.max(-1, Math.min(1, s))) / D2R;
}

function paintMap() {
  const canvas = document.getElementById('eme-map');
  if (!canvas || !emeData) return;
  const ctx = canvas.getContext('2d');
  const s = emeData.track[emeIndex];
  const home = emeData.located ? altitudeAt(emeData.lat, emeData.lon, s.gha, s.dec) : null;
  const img = ctx.createImageData(EME_W, EME_H);
  const px = img.data;
  const sin8 = Math.sin(8 * D2R), sin20 = Math.sin(20 * D2R);
  const sinHome = home === null ? -1 : Math.sin(home * D2R);
  const sd = Math.sin(s.dec * D2R), cd = Math.cos(s.dec * D2R);
  const ssd = Math.sin(s.sun_dec * D2R), csd = Math.cos(s.sun_dec * D2R);
  for (let y = 0; y < EME_H; y++) {
    const lat = 90 - (y + 0.5) * (180 / EME_H), latR = lat * D2R;
    const sl = Math.sin(latR), cl = Math.cos(latR);
    for (let x = 0; x < EME_W; x++) {
      const lon = (x + 0.5) * (360 / EME_W) - 180;
      const moon = sl * sd + cl * cd * Math.cos((s.gha + lon) * D2R);
      const night = (sl * ssd + cl * csd * Math.cos((s.sun_gha + lon) * D2R)) < 0;
      let r = 58, g = 66, b = 80;                       // moon down: grey
      if (moon > 0) {
        if (sinHome <= 0) { r = 57; g = 160; b = 170; }   // they see it, you do not
        else {
          const low = Math.min(moon, sinHome);
          if (low >= sin20) { r = 63; g = 185; b = 80; }
          else if (low >= sin8) { r = 255; g = 180; b = 84; }
          else { r = 160; g = 70; b = 70; }
        }
      }
      const shade = night ? 0.55 : 1.0;
      const i = (y * EME_W + x) * 4;
      px[i] = r * shade; px[i + 1] = g * shade; px[i + 2] = b * shade; px[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);

  // graticule
  ctx.strokeStyle = 'rgba(255,255,255,.10)';
  ctx.lineWidth = 1;
  for (let lon = -150; lon <= 150; lon += 30) {
    const x = (lon + 180) * 2;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, EME_H); ctx.stroke();
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    const y = (90 - lat) * 2;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(EME_W, y); ctx.stroke();
  }
  ctx.strokeStyle = 'rgba(255,255,255,.25)';
  ctx.beginPath(); ctx.moveTo(0, EME_H / 2); ctx.lineTo(EME_W, EME_H / 2); ctx.stroke();

  // the coast
  if (emeCoast) {
    ctx.strokeStyle = 'rgba(235,240,245,.75)';
    ctx.lineWidth = 1;
    emeCoast.forEach(line => {
      ctx.beginPath();
      line.forEach((p, n) => {
        const x = (p[0] + 180) * 2, y = (90 - p[1]) * 2;
        if (n) ctx.lineTo(x, y); else ctx.moveTo(x, y);
      });
      ctx.stroke();
    });
  }

  // the sub-solar and sub-lunar points, and the stations
  const mark = (lat, lon, glyph, colour) => {
    const x = (((lon + 180) % 360 + 360) % 360) * 2, y = (90 - lat) * 2;
    ctx.font = '18px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillText(glyph, x + 1, y + 1);
    ctx.fillStyle = colour; ctx.fillText(glyph, x, y);
  };
  /* Colour on this map means a sky condition and nothing else; a glyph
     means a thing. The far end used to be drawn in the cyan the key gives
     to "they see it, you do not", so the marker for a place you had just
     clicked looked like it was reporting a condition. The two stations are
     the same pale ink now and the shape tells them apart: a circle for you,
     a diamond for them. */
  mark(s.sun_dec, -s.sun_gha, '☀', '#ffd66b');
  mark(s.dec, -s.gha, '☽', '#f3f6ff');
  if (emeData.located) mark(emeData.lat, emeData.lon, '◯', '#ffffff');
  if (emeFar) mark(emeFar.lat, emeFar.lon, '◆', '#dbe4f0');

  document.getElementById('eme-clock').textContent = dayClock(s.t) +
    (home === null ? '' : ' · moon ' + (home > 0 ? Math.round(home) + '° up' : 'down') + ' at your QTH');
}

function paintVerdict(d) {
  const box = document.getElementById('eme-verdict');
  const stats = document.getElementById('eme-stats');
  if (!d.located) {
    box.innerHTML = '<span class="muted">ELMER does not know where you are yet. The map still shows who can see the moon; ' +
      'set a QTH - a grid square is enough - and it will say what that means from your end.</span>';
    stats.innerHTML = '';
    return;
  }
  const m = d.moon;
  const cls = {good: 'q4', fair: 'q2', poor: 'q1', down: 'q0'}[m.verdict] || 'q0';
  box.innerHTML = '<div class="row"><span class="pill ' + cls + '">' + escapeHTML(m.verdict) + '</span> ' +
    '<span>' + (m.up
      ? 'The moon is <b>' + Math.round(m.altitude) + '&deg;</b> up at a bearing of <b>' + Math.round(m.azimuth) + '&deg;</b> from ' +
        escapeHTML(d.qth) + (m.set ? ', setting at <b>' + dayClock(m.set) + '</b>' : '') + '. ' +
        escapeHTML((m.reasons || []).join('; ')) + '.'
      : 'The moon is below your horizon' + (m.rise ? '; it rises at <b>' + dayClock(m.rise) + '</b>' : '') +
        '. Nothing to point at until then - but the map shows where its window is now, and the slider where it will be.') +
    '</span></div>';
  const tile = (label, value, note) => '<div class="panel"><div class="tiny muted">' + label + '</div>' +
    '<div class="mono" style="font-size:1.25rem">' + value + '</div><div class="tiny muted">' + note + '</div></div>';
  stats.innerHTML =
    tile('Rise / set', (m.rise ? dayClock(m.rise) : '&mdash;') + ' / ' + (m.set ? dayClock(m.set) : '&mdash;'), 'your clock, the next of each') +
    tile('Distance', Math.round(m.distance_km / 1000) + ',000 km',
         m.loss_db < -0.3 ? (-m.loss_db).toFixed(1) + ' dB better than average - near perigee'
         : m.loss_db > 0.3 ? m.loss_db.toFixed(1) + ' dB worse than average - near apogee' : 'about average') +
    tile('Declination', (m.declination >= 0 ? '+' : '') + m.declination.toFixed(0) + '&deg;',
         m.declination < -15 ? 'low in the south; a noisier sky behind it' : m.declination > 15 ? 'high; a quiet sky behind it' : 'middling') +
    tile('From the sun', Math.round(m.sun_separation) + '&deg;',
         m.sun_separation < 15 ? 'sun noise in the beam' : m.sun_separation < 30 ? 'close enough to notice' : 'well clear') +
    /* The phase, always - it is the sun separation seen from the other
       side: a new moon is beside the sun and up by day, a full moon is
       opposite it and up all night, and a quarter moon is the one you
       can work at dusk with the sun below the horizon. */
    tile('Phase', escapeHTML(m.phase.name), Math.round(m.phase.lit * 100) + '% lit · ' +
         (m.phase.name === 'new' ? 'beside the sun, up by day - hard to find and noisy'
          : m.phase.name === 'full' ? 'opposite the sun, up all night'
          : /quarter/.test(m.phase.name) ? 'half a sky from the sun - up at dusk or dawn'
          : /waxing/.test(m.phase.name) ? 'evening moon, setting after the sun' : 'morning moon, rising after midnight'));
}

function paintMeteors(met) {
  const el = document.getElementById('eme-meteors');
  if (!met) { el.textContent = ''; return; }
  let html = '';
  if (met.now) html += '<p style="margin:.2rem 0"><b>The ' + escapeHTML(met.now.name) + ' are on</b> &mdash; peak ' +
    escapeHTML(met.now.peak) + ', ZHR about ' + met.now.zhr + '. MSK144 on 50.260 and 144.360; mornings are best, when the Earth&rsquo;s leading edge faces the stream.</p>';
  if (met.next) html += '<p style="margin:.2rem 0">Next: the <b>' + escapeHTML(met.next.name) + '</b>, peaking ' +
    escapeHTML(met.next.peak) + ' (' + met.next.days + ' days), ZHR about ' + met.next.zhr + '.</p>';
  html += '<p class="tiny" style="margin:.4rem 0 0">Random meteors are there every morning near 06:00 local, enough for a 6 m contact with patience; a shower is when it is worth staying up for 2 m.</p>';
  el.innerHTML = html;
}

function paintFar(far, qth) {
  const el = document.getElementById('eme-far');
  if (!far) { el.hidden = true; return; }
  el.hidden = false;
  const where = far.lat.toFixed(1) + '°, ' + far.lon.toFixed(1) + '°';
  const spans = far.windows || [];
  el.innerHTML = '<b>' + where + '</b> &mdash; the moon is ' +
    (far.altitude > 0 ? Math.round(far.altitude) + '&deg; up there now' : 'down there now') + '. ' +
    (spans.length
      ? 'Both ends see it ' + spans.map(w => '<b>' + dayClock(w[0]) + '&ndash;' + dayClock(w[1]) + '</b>').join(' and ') + ' (your clock).'
      : 'No common window with ' + escapeHTML(qth || 'your QTH') + ' in the next day.');
}

async function loadEME(far) {
  let url = '/api/eme';
  if (far) url += '?lat2=' + far.lat.toFixed(2) + '&lon2=' + far.lon.toFixed(2);
  let d;
  try { d = await api(url); } catch (e) {
    document.getElementById('eme-verdict').innerHTML = '<span class="muted">' + escapeHTML(String(e)) + '</span>';
    return;
  }
  emeData = d;
  paintVerdict(d);
  paintMeteors(d.meteors);
  emeFar = d.far || null;
  paintFar(emeFar, d.qth);
  document.getElementById('eme-slider').max = d.track.length - 1;
  paintMap();
}

document.getElementById('eme-slider').addEventListener('input', e => { emeIndex = +e.target.value; paintMap(); });
document.getElementById('eme-now').addEventListener('click', () => {
  document.getElementById('eme-slider').value = 0; emeIndex = 0; loadEME(emeFar);
});
document.getElementById('eme-map').addEventListener('click', e => {
  const c = e.currentTarget, r = c.getBoundingClientRect();
  const lon = (e.clientX - r.left) / r.width * 360 - 180;
  const lat = 90 - (e.clientY - r.top) / r.height * 180;
  if (!emeData || !emeData.located) { toast('Set a QTH first', 'a window needs both ends'); return; }
  loadEME({lat, lon});
});

fetch('/static/maps/coast.json').then(r => r.json()).then(c => { emeCoast = c; paintMap(); }).catch(() => {});
loadEME();
