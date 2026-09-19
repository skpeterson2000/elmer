/* Getting a message out: the list an Elmer would recite, in order, for where
   the operator is standing and what they actually brought.

   The page asks the server rather than reasoning here, because the reasoning
   is about privileges and geography and belongs where it can be read. */

const RO_TONE = {
  'good': 'var(--green)', 'worth trying': 'var(--amber)',
  'long shot': '#8b98a5', 'the rule': 'var(--red)',
};

function roGear() {
  return Array.from(document.querySelectorAll('#ro-gear input:checked'))
    .map(el => el.value);
}

function roCard(w) {
  const tone = RO_TONE[w.odds] || '#8b98a5';
  let html = '<div class="panel" style="margin-bottom:.8rem;border-left:3px solid ' +
    tone + '">' +
    '<div class="spread" style="align-items:baseline">' +
      '<b>' + escapeHTML(w.title) + '</b>' +
      '<span class="tiny mono" style="color:' + tone + '">' +
        escapeHTML(w.odds) + '</span>' +
    '</div>' +
    '<p class="tiny muted" style="margin:.2rem 0 .5rem">Needs: ' +
      escapeHTML(w.needs) + '</p>' +
    '<p style="margin:.3rem 0">' + escapeHTML(w.do) + '</p>' +
    /* The emergency card carries the order to try things in - an Elmer's
       order, not the rule's, which permits any means and ranks none. */
    (w.ladder ? '<ol class="ps-ladder small">' + w.ladder.map(step =>
        '<li><b>' + escapeHTML(step.what) + '.</b> <span class="muted">' +
        escapeHTML(step.how) + '</span></li>').join('') + '</ol>' : '') +
    '<p class="tiny muted" style="margin:.4rem 0 0">' + escapeHTML(w.why) + '</p>';
  if (w.rows && w.rows.length > 1) {
    html += '<table class="data rep-table" style="margin-top:.6rem"><tr>' +
      '<th>Output</th><th>Call</th><th>Where</th><th>Distance</th>' +
      '<th>Bearing</th><th>Tone</th></tr>';
    w.rows.forEach(r => {
      html += '<tr><td class="mono">' + r.output.toFixed(3) + '</td>' +
        '<td class="mono">' + escapeHTML(r.call) + '</td>' +
        '<td>' + escapeHTML(r.where || '') + (r.approx ? ' ~' : '') + '</td>' +
        '<td>' + r.miles + ' mi</td><td>' + r.bearing + '&deg;</td>' +
        '<td class="mono">' + (r.tone ? escapeHTML(String(r.tone)) : '&mdash;') +
        '</td></tr>';
    });
    html += '</table>';
  }
  return html + '</div>';
}

/* Reaching somewhere in particular: the path from here to there and the
   approach, on one card above the list. The server works it out; this
   lays it out in the order somebody would read it - how far and which
   way, what is between, which bands carry it, then what to do. */
const RO_SUN = {lit: 'in daylight', grey: 'on the grey line', dark: 'in the dark',
                twilight: 'in twilight'};

function roPathCard(d) {
  const sight = d.sight || {};
  const bands = (d.sky && d.sky.bands) || [];
  const carry = bands.filter(b => b.works);
  const shut = bands.filter(b => !b.works);
  const steps = (d.approach || []).map(a => {
    const tone = RO_TONE[a.odds] || '#8b98a5';
    return '<li style="margin:.35rem 0"><b>' + escapeHTML(a.band || 'Anything') +
      (a.how ? ' <span class="muted">by ' + escapeHTML(a.how) + '</span>' : '') + '</b>' +
      ' <span class="tiny mono" style="color:' + tone + '">' + escapeHTML(a.odds) + '</span>' +
      '<div class="small">' + escapeHTML(a.mode) + '</div>' +
      (a.antenna ? '<div class="tiny muted">Antenna: ' + escapeHTML(a.antenna) + '</div>' : '') +
      (a.why ? '<div class="tiny muted">' + escapeHTML(a.why) + '</div>' : '') + '</li>';
  }).join('');
  return '<div class="panel" style="border-left:3px solid var(--amber)">' +
    '<div class="spread" style="align-items:baseline;flex-wrap:wrap;gap:.4rem">' +
      '<b>Reaching ' + escapeHTML(d.to.short || '') + '</b>' +
      '<span class="tiny mono muted">' + (d.to.grid && d.to.kind !== 'grid' ? escapeHTML(d.to.grid) + ' &middot; ' : '') +
        d.miles + ' mi / ' + d.km + ' km &middot; bearing ' + d.bearing + '&deg; (back ' + d.back_bearing + '&deg;)</span>' +
    '</div>' +
    '<p class="small" style="margin:.4rem 0">' +
      'Here ' + (RO_SUN[d.from.sun] || d.from.sun) + ', there ' + (RO_SUN[d.to.sun] || d.to.sun) + '. ' +
      escapeHTML(sight.verdict || '') + (sight.terrain ? ' <span class="tiny muted">(terrain: ' + escapeHTML(sight.source || '') + ')</span>' : '') +
    '</p>' +
    (d.km > 80
      ? '<p class="small" style="margin:.3rem 0">' +
        (d.sky.blind
          ? 'No ionosonde reading in hand, so ELMER cannot say what the sky is doing for this path.'
          : (carry.length
              ? 'The ionosphere carries it now on <b>' + carry.map(b => escapeHTML(b.band) +
                  (b.hops > 1 ? ' (' + b.hops + ' hops)' : '')).join(', ') + '</b>' +
                (shut.length ? '; not ' + shut.slice(0, 4).map(b => escapeHTML(b.band)).join(', ') +
                  (shut[0] && shut[0].why ? ' &mdash; ' + escapeHTML(shut[0].why) : '') : '') + '.'
              : 'No band carries it by the numbers just now' +
                (shut[0] && shut[0].why ? ' &mdash; ' + escapeHTML(shut[0].why) : '') + '.')) +
        ' <span class="tiny muted">Read at ' + escapeHTML(d.sky.read_at) +
        (d.sky.fof2 ? '; foF2 ' + d.sky.fof2 + ' MHz' : '') + (d.sky.muf ? ', MUF ' + d.sky.muf : '') + '.</span></p>'
      : '') +
    (d.when ? '<p class="small" style="margin:.3rem 0"><b>When:</b> ' + escapeHTML(d.when) + '</p>' : '') +
    '<div id="ro-link"></div>' +
    '<div class="panel-title" style="margin-top:.6rem">The approach</div>' +
    '<ol style="margin:.2rem 0 0;padding-left:1.2rem">' + steps + '</ol>' +
    roLadder(d.ladder) +
    '<p class="tiny muted" style="margin:.5rem 0 0">This is what the numbers say. The band that ' +
    'carries it is the science; working it is the art - call, listen a full minute, move, try again.</p>' +
    '</div>';
}

/* The same path, three ways: with no licence, as a Technician, as a
   General - each with the radio that class would have in hand. Side by
   side, so the distance between the rungs shows. */
function roLadder(l) {
  if (!l || !l.rungs) return '';
  const cols = l.rungs.map(r => {
    const mine = l.yours && r.key === l.yours;
    const ways = r.ways.length
      ? '<ul style="margin:.25rem 0 0;padding-left:1rem">' + r.ways.map(w =>
          '<li class="small">' + bandTag(w.band) + ' <span class="muted">by ' + escapeHTML(w.how) + '</span> ' +
          '<span class="tiny mono" style="color:' + (RO_TONE[w.odds] || '#8b98a5') + '">' + escapeHTML(w.odds) + '</span>' +
          (w.mode ? '<div class="tiny muted">' + escapeHTML(w.mode) + (/CW only/.test(w.mode) ? ' &middot; <a href="/cw#today">learn the code &rarr;</a>' : '') + '</div>' : '') + '</li>').join('') + '</ul>'
      : '<div class="small muted" style="margin-top:.25rem">nothing, right now</div>';
    return '<div style="padding:.5rem;border-radius:8px;border:1px solid ' + (mine ? 'var(--amber)' : 'var(--line)') + '">' +
      '<b>' + escapeHTML(r.label) + '</b>' + (mine ? ' <span class="tiny mono" style="color:var(--amber)">you</span>' : '') +
      '<div class="tiny muted">with ' + escapeHTML(r.radio) + '</div>' + ways +
      '<div class="tiny" style="margin-top:.3rem">' + escapeHTML(r.verdict) + '</div>' +
      (r.far_end ? '<div class="tiny muted" style="margin-top:.2rem">Far end: ' + escapeHTML(r.far_end) + '</div>' : '') + '</div>';
  }).join('');
  return '<div class="panel-title" style="margin-top:.8rem">Right now, without a phone - by licence</div>' +
    '<div class="grid cols-3" style="gap:.5rem">' + cols + '</div>' +
    (l.step.length ? '<p class="small" style="margin:.4rem 0 0">' + l.step.map(escapeHTML).join('; ') + '.</p>' : '') +
    (l.two_way ? '<p class="small" style="margin:.3rem 0 0"><b>Two-way:</b> ' + escapeHTML(l.two_way) + '</p>' : '') +
    '<p class="tiny muted" style="margin:.3rem 0 0">Each column assumes the radio that licence would have in hand, whatever is ticked above; the approach above is for what you actually have.</p>';
}

async function roPath() {
  const box = document.getElementById('ro-path');
  const to = document.getElementById('ro-to').value.trim();
  const clear = document.getElementById('ro-to-clear');
  if (!to) { box.innerHTML = ''; clear.hidden = true; return; }
  box.innerHTML = '<p class="tiny muted">Working out the path...</p>';
  let d;
  try {
    d = await api('/api/path-to?' + new URLSearchParams({
      to: to, gear: roGear().join(','),
      license: document.getElementById('ro-class').value}));
  } catch (e) {
    box.innerHTML = '<p class="tiny" style="color:var(--red)">Could not work that out just now.</p>';
    return;
  }
  clear.hidden = false;
  if (!d.ok) {
    box.innerHTML = '<p class="tiny" style="color:var(--amber)">' + escapeHTML(d.note || '') + '</p>';
    return;
  }
  box.innerHTML = roPathCard(d);
  try { localStorage.setItem('elmer_reach_to', to); } catch (e) {}
  roLink(to, d);
}

/* The same path by the numbers on VHF and UHF: a radio off the shelf at
   each end, a band, a mode and the noise of the site, and the budget
   along the ground between - what leaves, what the path costs, what
   arrives, what the receiver needs, the margin, and the odds that margin
   buys once real paths' scatter is allowed for. The sight verdict above
   says whether the ground clears; this says what it costs when it does
   not, which is the difference between a handheld and a base rig. */
const RO_GEAR_RADIO = {vhf_ssb: 'base', mobile_vhf: 'mobile', ht: 'ht'};
let roLinkState = null;
function roLinkSeed() {
  if (roLinkState) return roLinkState;
  let kept = null;
  try { kept = JSON.parse(localStorage.getItem('elmer_reach_link') || 'null'); } catch (e) {}
  const gear = roGear();
  const mine = ['vhf_ssb', 'mobile_vhf', 'ht'].find(g => gear.includes(g));
  roLinkState = Object.assign({band: '2m', mode: 'fm', here: mine ? RO_GEAR_RADIO[mine] : 'ht', there: null, site: 'residential'}, kept || {});
  if (!kept && mine) roLinkState.here = RO_GEAR_RADIO[mine];
  return roLinkState;
}
function roLinkRemember() {
  try { localStorage.setItem('elmer_reach_link', JSON.stringify(roLinkState)); } catch (e) {}
}
/* The path as a picture: the ground along it, the line between the two
   antennas sagging with the earth's bulge, the first Fresnel zone as a
   band about the line, and the worst of the ground marked. The vertical
   is stretched - metres against kilometres - and says so. A hover reads
   the ground, the line and the clearance at that point. */
const RO_FT = m => Math.round(m * 3.28084);
function roProfileSVG(d) {
  const pts = d.profile || [];
  if (pts.length < 3) return '';
  const W = 640, H = 220, L = 52, R = 14, T = 14, B = 30;
  const km = pts[pts.length - 1].km || 1;
  const ha = d.here.height_m, hb = d.there.height_m;
  /* The scale is the ground's and the line's: the Fresnel zone on 2 m is
     hundreds of feet wide at a few miles and would flatten every hill to a
     ripple if it set the picture. It is shown out to most of the relief
     and runs off the top and bottom where it must - which is itself the
     point: the signal wants a zone that wide clear, and the ground is in it. */
  const lows = pts.map(p => Math.min(p.ground, p.line));
  const highs = pts.map(p => Math.max(p.ground, p.line));
  let y0 = Math.min(...lows), y1 = Math.max(...highs, pts[0].ground + ha, pts[pts.length - 1].ground + hb);
  const relief = Math.max(10, y1 - y0);
  const room = Math.min(Math.max(...pts.map(p => p.r1)), relief * 0.8);
  y0 -= Math.max(room, relief * 0.12); y1 += Math.max(room, relief * 0.12);
  const x = k => L + (k / km) * (W - L - R);
  const y = m => T + (1 - (m - y0) / (y1 - y0)) * (H - T - B);
  const ground = 'M' + x(0) + ',' + y(pts[0].ground) + pts.slice(1).map(p => 'L' + x(p.km).toFixed(1) + ',' + y(p.ground).toFixed(1)).join('') +
    'L' + x(km).toFixed(1) + ',' + (H - B) + 'L' + x(0) + ',' + (H - B) + 'Z';
  const line = pts.map((p, i) => (i ? 'L' : 'M') + x(p.km).toFixed(1) + ',' + y(p.line).toFixed(1)).join('');
  const zone = pts.map((p, i) => (i ? 'L' : 'M') + x(p.km).toFixed(1) + ',' + y(p.line + p.r1).toFixed(1)).join('') +
    pts.slice().reverse().map(p => 'L' + x(p.km).toFixed(1) + ',' + y(p.line - p.r1).toFixed(1)).join('') + 'Z';
  const worst = d.loss && d.loss.worst;
  const wp = worst ? pts.reduce((b, p) => Math.abs(p.km - worst.km) < Math.abs(b.km - worst.km) ? p : b, pts[0]) : null;
  const intrudes = worst && worst.above_line_m > 0;
  /* A few y ticks in feet, because that is how antenna height is sold and
     printed; x ticks along the ground in whatever the operator reads, because
     how far away the far end is standing is the question this preference is
     for. The chart used to be in miles whoever was looking at it. */
  const ticks = [];
  const span = y1 - y0, stepM = span > 600 ? 200 : span > 300 ? 100 : span > 120 ? 50 : span > 40 ? 20 : 10;
  for (let m = Math.ceil(y0 / stepM) * stepM; m <= y1; m += stepM) ticks.push(m);
  const far = away(km, 2), xs = [];
  const stepFar = far > 60 ? 20 : far > 25 ? 10 : far > 12 ? 5 : far > 5 ? 2 : 1;
  for (let d = 0; d <= far + 1e-6; d += stepFar) xs.push(d);
  const perKm = unitSystem().per_km;
  const halo = ' stroke="var(--panel, #161b22)" stroke-width="3" paint-order="stroke" stroke-linejoin="round"';
  return '<div class="ro-profile" style="position:relative;margin:.4rem 0">' +
    '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto;display:block" role="img" aria-label="the ground along the path, the line between the antennas and the first Fresnel zone">' +
      '<defs><clipPath id="ro-prof-clip"><rect x="' + L + '" y="' + T + '" width="' + (W - L - R) + '" height="' + (H - T - B) + '"/></clipPath></defs>' +
      ticks.map(m => '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y(m).toFixed(1) + '" y2="' + y(m).toFixed(1) + '" stroke="var(--line)" stroke-width="1"/>' +
        '<text x="' + (L - 6) + '" y="' + (y(m) + 3.5).toFixed(1) + '" text-anchor="end" font-size="10" fill="var(--muted)" font-family="ui-monospace, monospace">' + RO_FT(m).toLocaleString() + '</text>').join('') +
      xs.map(d => '<text x="' + x(d / perKm).toFixed(1) + '" y="' + (H - B + 14) + '" text-anchor="middle" font-size="10" fill="var(--muted)" font-family="ui-monospace, monospace">' + d + '</text>').join('') +
      '<text x="' + (W - R) + '" y="' + (H - B + 26) + '" text-anchor="end" font-size="10" fill="var(--muted)">' + unitSystem().long + ' &middot; height in feet, the vertical stretched</text>' +
      '<g clip-path="url(#ro-prof-clip)">' +
      '<path d="' + zone + '" fill="var(--amber)" fill-opacity=".16" stroke="var(--amber)" stroke-opacity=".5" stroke-width="1" stroke-dasharray="4 3"/>' +
      '<path d="' + ground + '" fill="#8b98a5" fill-opacity=".38" stroke="var(--dimmer)" stroke-width="1"/>' +
      '<path d="' + line + '" fill="none" stroke="var(--amber)" stroke-width="2" stroke-linejoin="round"/>' +
      '</g>' +
      '<line x1="' + x(0) + '" x2="' + x(0) + '" y1="' + y(pts[0].ground).toFixed(1) + '" y2="' + y(pts[0].ground + ha).toFixed(1) + '" stroke="var(--text)" stroke-width="2"/>' +
      '<line x1="' + x(km) + '" x2="' + x(km) + '" y1="' + y(pts[pts.length - 1].ground).toFixed(1) + '" y2="' + y(pts[pts.length - 1].ground + hb).toFixed(1) + '" stroke="var(--text)" stroke-width="2"/>' +
      '<text x="' + (x(0) + 4) + '" y="' + (T + 10) + '" font-size="10" fill="var(--text)">you</text>' +
      '<text x="' + (x(km) - 4) + '" y="' + (T + 10) + '" text-anchor="end" font-size="10" fill="var(--text)">them</text>' +
      (wp ? '<circle cx="' + x(wp.km).toFixed(1) + '" cy="' + y(wp.ground).toFixed(1) + '" r="4.5" fill="' + (intrudes ? 'var(--red)' : 'var(--green)') + '" stroke="var(--bg, #0d1117)" stroke-width="2"/>' +
        '<text x="' + x(wp.km).toFixed(1) + '" y="' + (y(Math.max(wp.ground, wp.line)) - 9).toFixed(1) + '" text-anchor="' + (wp.km < km * 0.15 ? 'start' : wp.km > km * 0.85 ? 'end' : 'middle') + '" font-size="10" fill="var(--text)"' + halo + '>' +
          (intrudes ? RO_FT(worst.above_line_m) + ' ft above the line' : RO_FT(-worst.above_line_m) + ' ft clear at the tightest') + '</text>' : '') +
      '<line id="ro-prof-x" x1="0" x2="0" y1="' + T + '" y2="' + (H - B) + '" stroke="var(--text)" stroke-width="1" stroke-dasharray="3 3" opacity="0"/>' +
      '<text id="ro-prof-read" x="' + (L + 6) + '" y="' + (H - B - 6) + '" font-size="10" fill="var(--text)" font-family="ui-monospace, monospace"' + halo + '></text>' +
      '<rect id="ro-prof-hit" x="' + L + '" y="' + T + '" width="' + (W - L - R) + '" height="' + (H - T - B) + '" fill="transparent" style="cursor:crosshair"/>' +
    '</svg>' +
    '<div class="tiny muted" style="display:flex;gap:1rem;flex-wrap:wrap"><span><i style="display:inline-block;width:14px;height:0;border-top:2px solid var(--amber);vertical-align:middle"></i> the line between the antennas, sagging with the earth</span>' +
      '<span><i style="display:inline-block;width:14px;height:8px;background:var(--amber);opacity:.3;vertical-align:middle"></i> the first Fresnel zone - the signal wants most of it clear</span>' +
      '<span><i style="display:inline-block;width:14px;height:8px;background:#8b98a5;opacity:.5;vertical-align:middle"></i> the ground</span></div>' +
    '</div>';
}
function roProfileBind(d) {
  const hit = document.getElementById('ro-prof-hit'), xl = document.getElementById('ro-prof-x'), read = document.getElementById('ro-prof-read');
  if (!hit || !xl || !read) return;
  const pts = d.profile, svg = hit.ownerSVGElement;
  const km = pts[pts.length - 1].km || 1, L = +hit.getAttribute('x'), Wp = +hit.getAttribute('width');
  const show = e => {
    const r = svg.getBoundingClientRect();
    const fx = (e.clientX - r.left) / r.width * 640;
    const k = Math.max(0, Math.min(km, (fx - L) / Wp * km));
    const p = pts.reduce((b, q) => Math.abs(q.km - k) < Math.abs(b.km - k) ? q : b, pts[0]);
    xl.setAttribute('x1', fx.toFixed(1)); xl.setAttribute('x2', fx.toFixed(1)); xl.setAttribute('opacity', '1');
    const clear = p.line - p.ground;
    read.textContent = awayText(p.km, 1) + ' · ground ' + RO_FT(p.ground).toLocaleString() + ' ft · line ' + RO_FT(p.line).toLocaleString() + ' ft · ' +
      (clear >= 0 ? RO_FT(clear) + ' ft clear' : RO_FT(-clear) + ' ft in the way') + (p.r1 ? ' · zone ±' + RO_FT(p.r1) + ' ft' : '');
  };
  hit.addEventListener('mousemove', show);
  hit.addEventListener('touchmove', e => { if (e.touches[0]) show(e.touches[0]); }, {passive: true});
  hit.addEventListener('mouseleave', () => { xl.setAttribute('opacity', '0'); read.textContent = ''; });
}

async function roLink(to, path) {
  const box = document.getElementById('ro-link');
  if (!box || !to) return;
  const st = roLinkSeed();
  box.innerHTML = '<div class="panel-title" style="margin-top:.6rem">By the numbers</div><p class="tiny muted">Adding up the path...</p>';
  let d;
  try {
    d = await api('/api/path-link?' + new URLSearchParams({to: to, band: st.band, mode: st.mode, here: st.here, there: st.there || st.here, site: st.site}));
  } catch (e) { box.innerHTML = ''; return; }
  if (!d.ok) { box.innerHTML = ''; return; }
  const sel = (id, list, value, title) => '<select class="btn sm" id="' + id + '" title="' + escapeHTML(title) + '">' +
    list.map(o => '<option value="' + escapeHTML(o.key) + '"' + (o.key === value ? ' selected' : '') + '>' + escapeHTML(o.label) + '</option>').join('') + '</select>';
  /* An HF band answers with the ionosphere, not with the terrain.
     The band list used to stop at 6 m, so a selector that offered nothing
     below it read as a tool that had given up - while the page computed the
     HF answer in full, four lines higher up, in a panel nobody had been
     pointed at. Choosing 20 m now gets that answer here, said as numbers,
     and says which kind of answer it is. Running a ground-wave budget on
     20 m over a thousand miles would print a confident 0% for a path that
     is wide open, which is worse than declining to answer. */
  if (d.kind === 'sky') {
    const works = !!d.works;
    const pct = Math.max(0, Math.min(100, d.score == null ? (works ? 60 : 0) : d.score));
    const colour = works ? (pct >= 70 ? 'var(--green)' : 'var(--amber)') : 'var(--red)';
    box.innerHTML =
      '<div class="panel-title" style="margin-top:.6rem">By the numbers</div>' +
      '<div class="row" style="flex-wrap:wrap;gap:.5rem;align-items:center;margin:.3rem 0">' +
        sel('ro-link-band', d.bands, d.band, 'the band') +
      '</div>' +
      '<div class="spread" style="align-items:baseline;flex-wrap:wrap;gap:.4rem">' +
        '<b>' + escapeHTML(d.band) + ', ' + d.miles + ' miles</b>' +
        '<span class="tiny mono" style="color:' + colour + '">' +
          escapeHTML(d.label || (works ? 'open' : 'closed')) + '</span>' +
      '</div>' +
      '<div class="meter thin" style="margin:.3rem 0"><i class="' +
        (pct >= 60 ? 'fill-high' : pct >= 35 ? 'fill-mid' : 'fill-low') +
        '" style="width:' + pct + '%"></i></div>' +
      '<p class="small" style="margin:.3rem 0">' +
        (works
          ? 'The ionosphere carries this path on ' + escapeHTML(d.band) + ' right now, ' +
            escapeHTML(d.how || 'by skywave') + '.'
          : escapeHTML(d.why || 'This band does not come back from the ionosphere on this path just now.')) +
      '</p>' +
      '<table class="data tiny" style="margin:.3rem 0">' +
        '<tr><th>critical frequency</th><th>MUF along the path</th><th>one hop reaches</th></tr>' +
        '<tr><td class="mono">' + (d.fof2 == null ? '?' : d.fof2 + ' MHz') + '</td>' +
        '<td class="mono">' + (d.muf == null ? '?' : d.muf + ' MHz') + '</td>' +
        '<td class="mono">' + (d.one_hop_km == null ? '?' : d.one_hop_km + ' km') + '</td></tr>' +
      '</table>' +
      '<p class="tiny muted" style="margin:.2rem 0 0">This is the sky, not the ground. ' +
        'On these bands the signal leaves at an angle, turns in the ionosphere and comes ' +
        'down again, so the terrain between you is not the path and there is no line of ' +
        'sight to draw. Read at the middle of the path, where a hop is reflected - the ' +
        'same reading the bands line above runs on. Pick 6 m or higher for a link budget ' +
        'along the ground.</p>';
    const pick = document.getElementById('ro-link-band');
    if (pick) pick.addEventListener('change', () => {
      roLinkState.band = pick.value; roLinkRemember(); roLink(to, path);
    });
    return;
  }
  const tone = RO_TONE[d.verdict === 'likely' ? 'good' : d.verdict === 'no' ? 'the rule' : d.verdict] || '#8b98a5';
  const pct = Math.round(100 * d.odds);
  const leg = (name, l) => '<tr><td>' + name + '</td><td class="mono">' + l.leaves_dbm + '</td><td class="mono">' + l.arrives_dbm + '</td><td class="mono">' + l.needed_dbm + '</td><td class="mono">' + (l.margin_db >= 0 ? '+' : '') + l.margin_db + ' dB</td><td class="mono">' + Math.round(100 * l.odds) + '%</td></tr>';
  const loss = d.loss || {};
  box.innerHTML =
    '<div class="panel-title" style="margin-top:.6rem">By the numbers</div>' +
    '<div class="row" style="flex-wrap:wrap;gap:.5rem;align-items:center;margin:.3rem 0">' +
      '<span class="tiny muted">You</span>' + sel('ro-link-here', d.shelf, d.here.key, 'the radio and antenna at your end, off the shelf - the next entry down the list is the next thing to buy') +
      '<span class="tiny muted">them</span>' + sel('ro-link-there', d.shelf, d.there.key, 'the radio at the far end') +
      sel('ro-link-band', d.bands, d.band, 'the band') +
      sel('ro-link-mode', d.modes, d.mode, 'the mode: what the receiver needs above the noise - FM the most, FT8 the least') +
      sel('ro-link-site', d.sites, d.site, 'the noise where the receiving end is: a residential street is well above a receiver\'s own noise at 2 m') +
    '</div>' +
    '<div class="spread" style="align-items:baseline;flex-wrap:wrap;gap:.4rem">' +
      '<b>' + escapeHTML(d.band_label) + ' ' + escapeHTML(d.mode_label) + ', ' + d.miles + ' miles</b>' +
      '<span class="tiny mono" style="color:' + tone + '">' + pct + '% &middot; ' + escapeHTML(d.verdict) + '</span>' +
    '</div>' +
    '<div class="meter thin" style="margin:.3rem 0"><i class="' + (pct >= 60 ? 'fill-high' : pct >= 35 ? 'fill-mid' : 'fill-low') + '" style="width:' + pct + '%"></i></div>' +
    '<p class="small" style="margin:.3rem 0">' + escapeHTML(d.words) + '</p>' +
    roProfileSVG(d) +
    '<table class="data tiny" style="margin:.3rem 0"><tr><th></th><th>leaves</th><th>arrives</th><th>needs</th><th>margin</th><th>odds</th></tr>' +
      leg('you, heard there', d.forward) + leg('them, heard here', d.back) + '</table>' +
    '<p class="tiny muted" style="margin:.2rem 0">dBm throughout. The path: free space ' + loss.free_space_db + ' dB' +
      (loss.diffraction_db >= 0.5 ? ', over the ground ' + loss.diffraction_db + ' dB more' : '') +
      ', two low antennas over the ground ' + loss.plane_earth_db + ' dB - the greater account is paid, ' + loss.total_db + ' dB' +
      (loss.worst && loss.worst.above_line_m > 0 ? '; the ground stands ' + loss.worst.above_line_m + ' m above the line ' + loss.worst.km + ' km along, against a Fresnel zone ' + loss.worst.fresnel_m + ' m wide there' : '') +
      (d.terrain ? '. Terrain: ' + escapeHTML(d.source || '') : '. The ground was not asked - a flat earth with its bulge, and real ground can only cost more') + '.</p>' +
    (d.step_up ? '<p class="small" style="margin:.3rem 0"><b>The step up:</b> ' + escapeHTML(d.step_up.words) + '</p>' : '') +
    (d.beyond ? '<p class="tiny" style="color:var(--amber);margin:.2rem 0">Past a couple of hundred kilometres the weather decides - tropospheric bending and ducts - and this model does not do weather.</p>' : '') +
    '<p class="tiny muted" style="margin:.2rem 0 .4rem">A teaching-grade model: the terrain between, the heights, the gains, the watts and the mode. It knows nothing of the trees in either yard or the building the far end is standing behind, which is why the answer is odds and not a promise.</p>';
  roProfileBind(d);
  ['here', 'there', 'band', 'mode', 'site'].forEach(k => {
    const el = document.getElementById('ro-link-' + k);
    if (el) el.addEventListener('change', () => { roLinkState[k] = el.value; roLinkRemember(); roLink(to, path); });
  });
}

async function roAsk() {
  const box = document.getElementById('ro-out');
  const where = document.getElementById('ro-where');
  box.innerHTML = '<p class="tiny muted">Working it out...</p>';
  let d;
  try {
    d = await api('/api/ways-out?' + new URLSearchParams({
      gear: roGear().join(','),
      license: document.getElementById('ro-class').value,
    }));
  } catch (e) {
    box.innerHTML = '<p class="tiny" style="color:var(--red)">Could not work ' +
      'that out just now.</p>';
    return;
  }

  /* No position is not "you have not ticked anything" - it is a different
     problem with a different fix, and saying the wrong one leaves somebody
     ticking boxes that were never the issue. */
  if (d.located === false) {
    where.textContent = '';
    box.innerHTML = '<p class="tiny" style="color:var(--amber)">' +
      escapeHTML(d.note) + '</p>';
    return;
  }

  where.innerHTML = 'From <b>' + escapeHTML(d.qth || 'the QTH on file') + '</b>' +
    (d.qth_source === 'gps' ? ' <span class="mono">(GPS)</span>' : '') +
    ', ' + ({lit: 'in daylight', grey: 'on the grey line', dark: 'after dark',
             twilight: 'in twilight that will not clear'}[d.sun]
            || 'in daylight') + '. ' +
    (d.coverage && d.coverage.known
      ? 'ELMER knows the repeaters around here.'
      : 'ELMER has no repeater list for this area &mdash; TowerWitch can look ' +
        'it up, and ELMER reads what it writes.');

  roLaw(d.monitoring);

  if (!d.ways.length) {
    box.innerHTML = '<p class="tiny muted">Tick something you have, and this ' +
      'fills in.</p>';
    return;
  }
  box.innerHTML = d.ways.map(roCard).join('') +
    '<p class="tiny muted">' + escapeHTML(d.note) + '</p>';
  roTrack(d.track || []);
}

/* The track. The next step is the open one; done steps fold to a line with
   their date; the ones beyond the next are there to be read, not pressed
   out of order - but nothing stops it, because the order is advice. */
function roTrack(steps) {
  const list = document.getElementById('ro-track');
  const say = document.getElementById('ro-track-say');
  if (!list) return;
  const done = steps.filter(s => s.done).length;
  say.textContent = steps.length ? done + ' of ' + steps.length + ' done' : '';
  list.innerHTML = steps.map(s =>
    '<li class="ro-step' + (s.done ? ' done' : '') + (s.next ? ' next' : '') + '">' +
      '<div class="spread" style="align-items:baseline;gap:.6rem">' +
        '<b>' + escapeHTML(s.title) + '</b>' +
        '<button class="btn sm ' + (s.done ? 'ghost' : 'primary') + ' ro-mark" data-step="' + escapeHTML(s.key) +
          '" data-done="' + (s.done ? '1' : '') + '">' + (s.done ? 'done ' + escapeHTML(s.done) : 'Done') + '</button>' +
      '</div>' +
      (s.done ? '' :
        '<p class="small" style="margin:.3rem 0">' + escapeHTML(s.how) +
          (s.link ? ' <a class="tiny" href="' + escapeHTML(s.link) + '">&rarr;</a>' : '') + '</p>' +
        '<p class="tiny" style="margin:.2rem 0"><b>You know it worked:</b> <span class="muted">' + escapeHTML(s.know) + '</span></p>' +
        (s.stuck ? '<p class="tiny" style="margin:.2rem 0"><b>If not:</b> <span class="muted">' + escapeHTML(s.stuck) + '</span></p>' : '')) +
    '</li>').join('');
  list.querySelectorAll('.ro-mark').forEach(b => b.addEventListener('click', async () => {
    const undo = b.dataset.done === '1';
    try {
      await postJSON('/api/track', {step: b.dataset.step, done: !undo});
      if (!undo) toast('Marked', 'the date is kept with it');
      roAsk();
    } catch (e) { toast('Could not save that', 'see data/elmer.log'); }
  }));
}

/* What the law says about listening, beside the frequencies rather than on a
   page of its own - this is where somebody is looking at what they could
   tune, and it is the moment the question is live.

   Every claim shows its citation and links the statute, because the statute
   is the answer and this is a pointer to it. Where the state was guessed
   rather than looked up, that is said before anything is read off it: a
   jurisdiction named wrongly makes every line under it wrong too. */
function roLaw(m) {
  const box = document.getElementById('ro-law');
  if (!box) return;
  if (!m) { box.hidden = true; return; }
  box.hidden = false;

  const where = m.where || {};
  const place = m.known
    ? '<b>' + escapeHTML(m.name) + '</b>'
    : 'here';
  const sure = where.sure
    ? ''
    : '<p class="tiny" style="color:var(--amber);margin:.2rem 0 .5rem">' +
      'ELMER is not certain which state this is &mdash; ' +
      escapeHTML(where.how || '') + ' If that is wrong, so is everything ' +
      'below it.</p>';

  const laws = (m.statutes || []).map(law =>
    '<div class="law">' +
      '<div class="law-cite"><a href="' + escapeHTML(law.url) + '">' +
        escapeHTML(law.cite) + '</a>' +
        (law.checked === 'primary' ? ''
          : ' <span class="tiny muted">(not yet read against the ' +
            'official text)</span>') +
      '</div>' +
      (law.title ? '<div class="tiny muted">' + escapeHTML(law.title) +
                   '</div>' : '') +
      (law.quote ? '<blockquote class="law-quote">' +
                   escapeHTML(law.quote) + '</blockquote>' : '') +
      '<p class="tiny">' + escapeHTML(law.reading) + '</p>' +
    '</div>').join('');

  const federal = (m.federal || []).map(f =>
    '<li><b>' + escapeHTML(f.point) + '</b> ' + escapeHTML(f.why) +
    ' <a class="tiny" href="' + escapeHTML(f.url) + '">' +
    escapeHTML(f.cite) + '</a></li>').join('');

  box.innerHTML =
    '<div class="panel-title">Before you listen &mdash; ' + place + '</div>' +
    sure +
    (m.do_this
      ? '<p class="law-do">' + escapeHTML(m.do_this) + '</p>' : '') +
    '<p class="small">' + escapeHTML(m.reading) + '</p>' +
    (m.look_here
      ? '<p class="tiny"><a href="' + escapeHTML(m.look_here) + '">Look it ' +
        'up for this state &rarr;</a></p>' : '') +
    laws +
    '<details class="derivation"><summary>Everywhere in the US</summary>' +
      '<ul class="tiny law-fed">' + federal + '</ul>' +
      '<p class="tiny muted">ELMER points at the law; it does not state it. ' +
      'The statute is what governs, and it is linked above.</p>' +
    '</details>';
}

document.getElementById('ro-go').addEventListener('click', roAsk);
document.querySelectorAll('#ro-gear input').forEach(
  el => el.addEventListener('change', roAsk));
roAsk();

/* The destination: worked out on the press or on Enter, cleared with the
   button, and remembered on this browser so a place somebody keeps trying
   to reach is there next time. Gear and class changes re-ask it too, since
   the approach depends on both. */
document.getElementById('ro-to-go').addEventListener('click', roPath);
document.getElementById('ro-to').addEventListener('keydown', e => { if (e.key === 'Enter') roPath(); });
document.getElementById('ro-to-clear').addEventListener('click', () => {
  document.getElementById('ro-to').value = '';
  try { localStorage.removeItem('elmer_reach_to'); } catch (e) {}
  roPath();
});
document.querySelectorAll('#ro-gear input, #ro-class').forEach(
  el => el.addEventListener('change', () => { if (document.getElementById('ro-to').value.trim()) roPath(); }));
try {
  const kept = localStorage.getItem('elmer_reach_to');
  if (kept) { document.getElementById('ro-to').value = kept; roPath(); }
} catch (e) {}
