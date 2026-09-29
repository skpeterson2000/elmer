/* What calibration has done: four charts from /api/calibrate/charts - see
   calcharts.py. The live forecast as issued, month by month in the latest
   run's year, the table in force, and run by run. Each says what it shows
   in a sentence first, carries a legend, a value under the pointer, and a
   table for anybody who would rather read the numbers.

   Colors are the panel's own, set in propagation.html and validated there:
   the model bare in orange, calibrated in blue, the measured sky in the
   page's dim ink, and the three skies in gold, aqua and violet. Text never
   wears a series color; the mark beside it carries that. */
(function () {
  const body = document.getElementById('calc-body');
  if (!body) return;
  const W = 900;
  const M = {l: 46, r: 16, t: 14, b: 30};
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const SKY = {lit: 'lit (day)', gray: 'gray (twilight)', dark: 'dark (night)'};
  const f1 = x => (x === null || x === undefined || isNaN(x)) ? '–' : Number(x).toFixed(1);
  const f2 = x => (x === null || x === undefined || isNaN(x)) ? '–' : Number(x).toFixed(2);
  const signed = x => (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(2);
  const monthLabel = m => { const [y, n] = String(m).split('-'); return MONTHS[+n - 1] + ' ' + y.slice(2); };

  /* One tooltip for the panel, placed by the pointer, filled with text nodes
     built from escaped strings - the values are ours, the labels are ours,
     and still nothing is concatenated in raw. */
  const tip = document.createElement('div');
  tip.className = 'calc-tip'; tip.hidden = true;
  document.body.appendChild(tip);
  function showTip(e, html) {
    tip.innerHTML = html; tip.hidden = false;
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(window.innerWidth - w - 8, e.clientX + pad) + 'px';
    tip.style.top = Math.max(8, e.clientY - h - pad) + 'px';
  }
  function hideTip() { tip.hidden = true; }

  /* Clean axis ticks: a step of 1, 2 or 5 times a power of ten. */
  function ticks(lo, hi, want) {
    const raw = (hi - lo) / Math.max(1, want);
    const pow = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 5, 10].map(k => k * pow).find(s => s >= raw) || raw;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
    return out;
  }
  const key = (kind, color) => '<span class="calc-key-' + kind + '" style="background:' + color + '"></span>';
  const legend = items => '<div class="calc-legend tiny muted">' +
    items.map(([kind, color, label]) => '<span>' + key(kind, color) + escapeHTML(label) + '</span>').join('') + '</div>';
  const table = (head, rows) => '<details class="tiny" style="margin-top:.35rem"><summary class="muted" style="cursor:pointer">As a table</summary>' +
    '<table class="calc-table"><thead><tr>' + head.map(h => '<th>' + escapeHTML(h) + '</th>').join('') + '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + r.map(c => '<td>' + escapeHTML(String(c)) + '</td>').join('') + '</tr>').join('') + '</tbody></table></details>';
  const section = (id, title, read, svg, extra) => '<div class="calc-chart" id="' + id + '"><h3>' + escapeHTML(title) + '</h3>' +
    '<p class="small read">' + read + '</p>' + svg + (extra || '') + '</div>';
  const css = name => getComputedStyle(document.getElementById('calc-panel')).getPropertyValue(name).trim();

  /* The pointer's x in the SVG's own units. */
  function svgX(svg, e) {
    const r = svg.getBoundingClientRect();
    return (e.clientX - r.left) * (W / r.width);
  }

  // ------------------------------------------------------------- 1. live
  function live(d, runs) {
    const pts = (d.points || []).map(p => Object.assign({}, p, {time: new Date(p.t)}));
    const title = 'The live forecast, a day ahead, against the sondes';
    if (pts.length < 2) {
      return section('calc-live', title, 'The forecast log has no hours yet with both a forecast made a day or so ahead and a ' +
        'measurement to set against it. It fills in as the unit runs, an hour at a time.', '');
    }
    const H = 260, x0 = pts[0].time.getTime(), x1 = pts[pts.length - 1].time.getTime();
    const top = Math.max(...pts.map(p => Math.max(p.measured, p.forecast, p.model || 0))) * 1.08;
    const X = t => M.l + (t - x0) / Math.max(1, x1 - x0) * (W - M.l - M.r);
    const Y = v => M.t + (1 - v / top) * (H - M.t - M.b);
    const path = key => {
      let s = '', last = null;
      pts.forEach(p => {
        const v = p[key];
        if (v === null || v === undefined) { last = null; return; }
        const t = p.time.getTime();
        s += (last === null || t - last > 90 * 60000 ? 'M' : 'L') + X(t).toFixed(1) + ',' + Y(v).toFixed(1);
        last = t;
      });
      return s;
    };
    const withModel = pts.filter(p => p.model !== null && p.model !== undefined);
    const err = (list, k) => list.reduce((a, p) => a + Math.abs(p[k] - p.measured), 0) / list.length;
    const bias = (list, k) => list.reduce((a, p) => a + (p[k] - p.measured), 0) / list.length;
    const mae = err(pts, 'forecast'), b = bias(pts, 'forecast');
    let read = 'Over ' + pts.length + ' hours: the forecast issued ' + d.lead_min + '–' + d.lead_max + ' hours ahead was off by <b>' +
      f2(mae) + ' MHz</b> on average, running ' + f2(Math.abs(b)) + ' MHz ' + (b >= 0 ? 'high' : 'low') + '.';
    if (withModel.length) {
      const mm = err(withModel, 'model'), mf = err(withModel, 'forecast');
      read += ' Over the ' + withModel.length + ' of them logged with the model&rsquo;s own figure, the model before the unit&rsquo;s corrections ' +
        'was off by ' + f2(mm) + ' MHz and the forecast as issued by ' + f2(mf) + ' &mdash; the corrections ' +
        (mf < mm - 0.02 ? 'helped' : mf > mm + 0.02 ? 'cost' : 'changed little') + '.';
    } else {
      read += ' The model&rsquo;s own figure, before the unit&rsquo;s corrections, is logged from this build on, and appears here as it fills in.';
    }
    if (pts.length < 48) read += ' Only ' + pts.length + ' hours so far: read the shape, not the number.';
    const yt = ticks(0, top, 5);
    const marks = (runs || []).map(r => new Date(r.made).getTime()).filter(t => t >= x0 && t <= x1);
    let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeHTML(title) + '">';
    yt.forEach(v => { svg += '<line x1="' + M.l + '" x2="' + (W - M.r) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="' + css('--calc-grid') + '"/>' +
      '<text x="' + (M.l - 6) + '" y="' + (Y(v) + 4) + '" text-anchor="end">' + v + '</text>'; });
    svg += '<text x="4" y="' + (M.t + 4) + '">MHz</text>';
    const days = ticks(0, (x1 - x0) / 86400000, 6);
    days.forEach(dd => { const t = x0 + dd * 86400000; const lab = new Date(t).toLocaleDateString(undefined, {month: 'short', day: 'numeric'});
      svg += '<text x="' + X(t) + '" y="' + (H - 8) + '" text-anchor="middle">' + escapeHTML(lab) + '</text>'; });
    marks.forEach(t => { svg += '<line x1="' + X(t) + '" x2="' + X(t) + '" y1="' + M.t + '" y2="' + (H - M.b) + '" stroke="' + css('--calc-axis') + '"/>' +
      '<text x="' + (X(t) + 3) + '" y="' + (M.t + 10) + '">calibrated</text>'; });
    svg += '<path d="' + path('measured') + '" fill="none" stroke="' + css('--calc-meas') + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
    if (withModel.length) svg += '<path d="' + path('model') + '" fill="none" stroke="' + css('--calc-bare') + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
    svg += '<path d="' + path('forecast') + '" fill="none" stroke="' + css('--calc-cal') + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
    svg += '<line class="calc-cross" x1="0" x2="0" y1="' + M.t + '" y2="' + (H - M.b) + '" stroke="' + css('--calc-axis') + '" visibility="hidden"/>';
    svg += '<rect class="calc-hit" x="' + M.l + '" y="' + M.t + '" width="' + (W - M.l - M.r) + '" height="' + (H - M.t - M.b) + '" fill="transparent"/></svg>';
    const items = [['line', css('--calc-meas'), 'measured by the sondes'], ['line', css('--calc-cal'), 'the forecast as issued']];
    if (withModel.length) items.push(['line', css('--calc-bare'), 'the model, before the unit’s corrections']);
    const rows = pts.map(p => [p.time.toLocaleString(undefined, {month: 'short', day: 'numeric', hour: '2-digit'}), f1(p.measured), f1(p.forecast),
      p.model === null || p.model === undefined ? '–' : f1(p.model), p.lead + ' h', p.regime || '']);
    live._pts = pts; live._X = X;
    return section('calc-live', title, read, svg, legend(items) +
      table(['hour', 'measured', 'forecast', 'model', 'lead', 'sky'], rows));
  }
  function liveHover(root) {
    const box = root.querySelector('#calc-live svg');
    if (!box || !live._pts) return;
    const cross = box.querySelector('.calc-cross');
    box.addEventListener('pointermove', e => {
      const x = svgX(box, e), pts = live._pts;
      let best = pts[0], bd = Infinity;
      pts.forEach(p => { const dd = Math.abs(live._X(p.time.getTime()) - x); if (dd < bd) { bd = dd; best = p; } });
      const bx = live._X(best.time.getTime());
      cross.setAttribute('x1', bx); cross.setAttribute('x2', bx); cross.setAttribute('visibility', 'visible');
      const k = c => '<span class="k" style="background:' + css(c) + '"></span>';
      showTip(e, '<div class="muted">' + escapeHTML(best.time.toLocaleString(undefined, {weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})) +
        ' &middot; ' + escapeHTML(best.regime || '') + '</div>' +
        '<div>' + k('--calc-meas') + '<b>' + f1(best.measured) + ' MHz</b> measured</div>' +
        '<div>' + k('--calc-cal') + '<b>' + f1(best.forecast) + ' MHz</b> forecast, ' + best.lead + ' h ahead</div>' +
        (best.model !== null && best.model !== undefined ? '<div>' + k('--calc-bare') + '<b>' + f1(best.model) + ' MHz</b> the model alone</div>' : ''));
    });
    box.addEventListener('pointerleave', () => { cross.setAttribute('visibility', 'hidden'); hideTip(); });
  }

  // ----------------------------------------------------------- 2. months
  function months(run) {
    const title = 'The latest run’s year, month by month — the model alone';
    if (!run) return section('calc-months', title, 'No calibration run has been kept yet. Run one above and its year appears here.', '');
    const ms = Object.keys(run.bare.by_month || {}).sort();
    const rows = ms.map(m => {
      const b = run.bare.by_month[m] || {}, c = (run.cal.by_month || {})[m] || {};
      return {m: m, bare: (b.all || {}).mae, cal: (c.all || {}).mae, same: (b.persistence || {}).mae, n: (b.all || {}).n};
    }).filter(r => r.bare !== undefined && r.cal !== undefined);
    const better = rows.filter(r => r.cal < r.bare - 0.05).length, worse = rows.filter(r => r.cal > r.bare + 0.05).length;
    const beaten = rows.filter(r => r.same !== undefined && r.same < Math.min(r.bare, r.cal)).length;
    const read = 'The run replayed ' + escapeHTML(run.start) + ' to ' + escapeHTML(run.end) + ' blind, hour by hour, forecasting 6 to 24 hours ahead. ' +
      'Calibration lowered the model&rsquo;s average error in <b>' + better + '</b> of ' + rows.length + ' months, left ' +
      (rows.length - better - worse) + ' unchanged and raised it in ' + worse + '. ' +
      '&ldquo;Same as yesterday&rdquo; &mdash; the hour&rsquo;s measurement a day before &mdash; beat the model in <b>' + beaten + '</b> of ' + rows.length +
      '. The live forecast leans on exactly that, which this replay does not.';
    const H = 240, top = Math.max(...rows.map(r => Math.max(r.bare, r.cal, r.same || 0))) * 1.12;
    const slot = (W - M.l - M.r) / rows.length, bw = Math.min(18, slot / 3);
    const Y = v => M.t + (1 - v / top) * (H - M.t - M.b);
    const bar = (x, v, color, i, kind) => {
      const y = Y(v), h = (H - M.b) - y, r = Math.min(4, h);
      return '<path data-i="' + i + '" data-k="' + kind + '" fill="' + color + '" d="M' + x + ',' + (H - M.b) + 'V' + (y + r) +
        'Q' + x + ',' + y + ' ' + (x + r) + ',' + y + 'H' + (x + bw - r) + 'Q' + (x + bw) + ',' + y + ' ' + (x + bw) + ',' + (y + r) + 'V' + (H - M.b) + 'Z"/>';
    };
    let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeHTML(title) + '">';
    ticks(0, top, 4).forEach(v => { svg += '<line x1="' + M.l + '" x2="' + (W - M.r) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="' + css('--calc-grid') + '"/>' +
      '<text x="' + (M.l - 6) + '" y="' + (Y(v) + 4) + '" text-anchor="end">' + v + '</text>'; });
    svg += '<text x="4" y="' + (M.t + 4) + '">MHz</text>';
    rows.forEach((r, i) => {
      const cx = M.l + slot * (i + 0.5);
      svg += bar(cx - bw - 1, r.bare, css('--calc-bare'), i, 'm') + bar(cx + 1, r.cal, css('--calc-cal'), i, 'm');
      if (r.same !== undefined) svg += '<line x1="' + (cx - bw - 4) + '" x2="' + (cx + bw + 4) + '" y1="' + Y(r.same) + '" y2="' + Y(r.same) +
        '" stroke="' + css('--calc-meas') + '" stroke-width="2" stroke-linecap="round"/>';
      svg += '<text x="' + cx + '" y="' + (H - 10) + '" text-anchor="middle">' + escapeHTML(monthLabel(r.m)) + '</text>';
      svg += '<rect data-i="' + i + '" data-k="m" x="' + (cx - slot / 2) + '" y="' + M.t + '" width="' + slot + '" height="' + (H - M.t - M.b) + '" fill="transparent"/>';
    });
    svg += '</svg>';
    months._rows = rows;
    return section('calc-months', title, read, svg,
      legend([['bar', css('--calc-bare'), 'the model bare'], ['bar', css('--calc-cal'), 'with the run’s table'],
              ['line', css('--calc-meas'), '“same as yesterday”']]) +
      table(['month', 'bare (MHz)', 'calibrated', 'same as yesterday', 'hours'],
            rows.map(r => [monthLabel(r.m), f2(r.bare), f2(r.cal), f2(r.same), r.n || ''])));
  }

  // ------------------------------------------------------------- 3. table
  function tableChart(t) {
    const title = 'What calibration decided — the table in force';
    const ms = Object.keys((t && t.months) || {}).sort();
    if (!ms.length) return section('calc-table', title, 'This unit has no calibration table yet.', '');
    const cells = [];
    ms.forEach(m => Object.keys(SKY).forEach(sky => { const c = t.months[m][sky]; if (c) cells.push(Object.assign({m: m, sky: sky}, c)); }));
    /* The fit's own flags (forecastlog.fit_calibration): applied, or `small` -
       hours enough and the effect under ten percent - or neither, too few
       hours to believe. */
    const applied = cells.filter(c => c.applied).length, near = cells.filter(c => !c.applied && c.small).length;
    const few = cells.length - applied - near;
    const read = 'Each dot is what the sondes read against the model for one month and one sky, over a year: above the line the sky ran higher ' +
      'than the model. <b>' + applied + '</b> of ' + cells.length + ' were applied (filled). The rest are hollow and left at 1.0: ' + near +
      ' were within ten percent of the model, which the fit does not act on, and ' + few + ' had too few hours to believe.';
    const H = 240, vals = cells.map(c => c.measured || c.factor || 1);
    const lo = Math.min(0.8, ...vals) - 0.05, hi = Math.max(1.2, ...vals) + 0.05;
    const Y = v => M.t + (hi - v) / (hi - lo) * (H - M.t - M.b);
    const slot = (W - M.l - M.r) / 12;
    const off = {lit: -9, gray: 0, dark: 9};
    let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeHTML(title) + '">';
    ticks(lo, hi, 5).forEach(v => { svg += '<line x1="' + M.l + '" x2="' + (W - M.r) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="' +
      (Math.abs(v - 1) < 1e-6 ? css('--calc-axis') : css('--calc-grid')) + '"/><text x="' + (M.l - 6) + '" y="' + (Y(v) + 4) + '" text-anchor="end">' +
      (Math.abs(v - 1) < 1e-6 ? '1.0' : v.toFixed(1)) + '</text>'; });
    svg += '<text x="4" y="' + (M.t + 4) + '">× model</text>';
    MONTHS.forEach((name, i) => { svg += '<text x="' + (M.l + slot * (i + 0.5)) + '" y="' + (H - 10) + '" text-anchor="middle">' + name + '</text>'; });
    cells.forEach((c, i) => {
      const x = M.l + slot * (+c.m - 0.5) + off[c.sky], y = Y(c.measured || c.factor || 1), col = css('--calc-' + c.sky);
      svg += c.applied
        ? '<circle cx="' + x + '" cy="' + y + '" r="5" fill="' + col + '" stroke="' + css('--panel') + '" stroke-width="2"/>'
        : '<circle cx="' + x + '" cy="' + y + '" r="4.5" fill="' + css('--panel') + '" stroke="' + col + '" stroke-width="2"/>';
      svg += '<circle data-i="' + i + '" cx="' + x + '" cy="' + y + '" r="12" fill="transparent"/>';
    });
    svg += '</svg>';
    tableChart._cells = cells;
    return section('calc-table', title, read, svg,
      legend([['dot', css('--calc-lit'), SKY.lit], ['dot', css('--calc-gray'), SKY.gray], ['dot', css('--calc-dark'), SKY.dark]]) +
      '<div class="tiny muted" style="margin-top:.2rem">Filled: applied. Hollow: read, and not applied.</div>' +
      table(['month', 'sky', 'sondes ÷ model', 'applied as', 'hours', 'why not'], cells.map(c => [MONTHS[+c.m - 1], c.sky, f2(c.measured), c.applied ? '×' + f2(c.factor) : '1.0 (not applied)', c.n,
        c.applied ? '' : c.small ? 'within 10%' : 'too few hours'])));
  }
  function tableHover(root) {
    const box = root.querySelector('#calc-table svg');
    if (!box) return;
    box.addEventListener('pointermove', e => {
      const hit = e.target.closest('[data-i]');
      if (!hit) { hideTip(); return; }
      const c = tableChart._cells[+hit.dataset.i];
      showTip(e, '<div class="muted">' + MONTHS[+c.m - 1] + ' &middot; ' + escapeHTML(SKY[c.sky]) + '</div>' +
        '<div>The sondes read <b>' + f2(c.measured) + '×</b> the model, over ' + c.n + ' hours</div>' +
        '<div>' + (c.applied ? 'Applied as <b>×' + f2(c.factor) + '</b>' + (c.bounded ? ', held to the bounds' : '')
          : 'Not applied: ' + (c.small ? 'within ten percent of the model' : 'too few hours to believe')) + '</div>');
    });
    box.addEventListener('pointerleave', hideTip);
  }

  // -------------------------------------------------------------- 4. runs
  function runsChart(runs) {
    const title = 'Run by run — the 24-hour forecast’s error';
    if (!runs || !runs.length) return section('calc-runs', title, 'No calibration run has been kept yet.', '');
    const rs = runs.map(r => ({made: r.made, start: r.start, end: r.end, build: r.build,
      bare: r.bare.lead24 || {}, cal: r.cal.lead24 || {}, held: r.held ? (r.held.lead24 || {}) : null}))
      .filter(r => r.bare.mae !== undefined && r.cal.mae !== undefined);
    const last = rs[rs.length - 1];
    const moved = Math.max(...rs.map(r => Math.abs(r.cal.mae - r.bare.mae)));
    const read = 'Across ' + rs.length + ' run' + (rs.length === 1 ? '' : 's') + ', the table moved the 24-hour forecast&rsquo;s error by at most <b>' + f2(moved) +
      ' MHz</b>. What it does change is the bias: in the latest, from ' + signed(last.bare.bias) + ' to ' + signed(last.cal.bias) +
      ' MHz. A single factor for a month and a sky can shift the whole month up or down; it cannot follow a sky that swings both ways within it.';
    const vals = [].concat(...rs.map(r => [r.bare.mae, r.cal.mae, r.held && r.held.mae].filter(v => v !== undefined && v !== null)));
    const lo = Math.min(...vals) - 0.1, hi = Math.max(...vals) + 0.1;
    const L = 170, rowH = 30, H = M.t + rowH * rs.length + M.b;
    const X = v => L + (v - lo) / (hi - lo) * (W - L - M.r);
    let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + escapeHTML(title) + '">';
    ticks(lo, hi, 5).forEach(v => { svg += '<line x1="' + X(v) + '" x2="' + X(v) + '" y1="' + M.t + '" y2="' + (H - M.b) + '" stroke="' + css('--calc-grid') + '"/>' +
      '<text x="' + X(v) + '" y="' + (H - 10) + '" text-anchor="middle">' + v.toFixed(2) + '</text>'; });
    svg += '<text x="0" y="' + (H - 10) + '">error, MHz</text>';
    rs.forEach((r, i) => {
      // the time too: two runs a few hours apart share a date
      const y = M.t + rowH * (i + 0.5), label = new Date(r.made).toLocaleString(undefined, {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}) +
        ' · ' + Math.round((new Date(r.end) - new Date(r.start)) / 86400000) + ' days';
      svg += '<text x="0" y="' + (y + 4) + '">' + escapeHTML(label) + '</text>';
      svg += '<line x1="' + X(r.bare.mae) + '" x2="' + X(r.cal.mae) + '" y1="' + y + '" y2="' + y + '" stroke="' + css('--calc-axis') + '" stroke-width="2"/>';
      if (r.held && r.held.mae !== undefined) svg += '<circle cx="' + X(r.held.mae) + '" cy="' + y + '" r="4.5" fill="' + css('--panel') + '" stroke="' + css('--calc-cal') + '" stroke-width="2"/>';
      svg += '<circle cx="' + X(r.bare.mae) + '" cy="' + y + '" r="5" fill="' + css('--calc-bare') + '" stroke="' + css('--panel') + '" stroke-width="2"/>';
      svg += '<circle cx="' + X(r.cal.mae) + '" cy="' + y + '" r="5" fill="' + css('--calc-cal') + '" stroke="' + css('--panel') + '" stroke-width="2"/>';
      svg += '<rect data-i="' + i + '" x="0" y="' + (y - rowH / 2) + '" width="' + W + '" height="' + rowH + '" fill="transparent"/>';
    });
    svg += '</svg>';
    runsChart._rs = rs;
    return section('calc-runs', title, read, svg,
      legend([['dot', css('--calc-bare'), 'the model bare'], ['dot', css('--calc-cal'), 'with the table it fitted'],
              ['dot', 'transparent;box-shadow:inset 0 0 0 2px ' + css('--calc-cal'), 'with the table already in force']]) +
      table(['run', 'span', 'bare error', 'bare bias', 'new error', 'new bias', 'in-force error'],
            rs.map(r => [new Date(r.made).toLocaleString(undefined, {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'}),
              r.start + ' to ' + r.end, f2(r.bare.mae), signed(r.bare.bias), f2(r.cal.mae), signed(r.cal.bias),
              r.held && r.held.mae !== undefined ? f2(r.held.mae) : '–'])));
  }
  function hoverRows(root, id, text) {
    const box = root.querySelector('#' + id + ' svg');
    if (!box) return;
    box.addEventListener('pointermove', e => { const hit = e.target.closest('[data-i]'); if (!hit) { hideTip(); return; } showTip(e, text(+hit.dataset.i)); });
    box.addEventListener('pointerleave', hideTip);
  }

  // --------------------------------------------------------------- load
  async function load() {
    let d;
    try { d = await api('/api/calibrate/charts'); }
    catch (e) { body.innerHTML = '<span class="small muted">The charts could not be fetched just now.</span>'; return; }
    if (!d.ok) { body.innerHTML = '<span class="small muted">' + escapeHTML(d.error || 'The charts could not be worked out.') + '</span>'; return; }
    body.innerHTML = live(d.live || {}, d.runs) + months(d.latest) + tableChart(d.table) + runsChart(d.runs);
    liveHover(body);
    tableHover(body);
    const k = c => '<span class="k" style="background:' + css(c) + '"></span>';
    hoverRows(body, 'calc-months', i => { const r = months._rows[i]; return '<div class="muted">' + escapeHTML(monthLabel(r.m)) + ' &middot; ' + (r.n || '') + ' hours</div>' +
      '<div>' + k('--calc-bare') + '<b>' + f2(r.bare) + ' MHz</b> bare</div><div>' + k('--calc-cal') + '<b>' + f2(r.cal) + ' MHz</b> calibrated</div>' +
      (r.same !== undefined ? '<div>' + k('--calc-meas') + '<b>' + f2(r.same) + ' MHz</b> same as yesterday</div>' : ''); });
    hoverRows(body, 'calc-runs', i => { const r = runsChart._rs[i]; return '<div class="muted">' + escapeHTML(r.start + ' to ' + r.end) + ' &middot; build ' + escapeHTML(r.build) + '</div>' +
      '<div>' + k('--calc-bare') + '<b>' + f2(r.bare.mae) + ' MHz</b> bare, bias ' + signed(r.bare.bias) + '</div>' +
      '<div>' + k('--calc-cal') + '<b>' + f2(r.cal.mae) + ' MHz</b> new table, bias ' + signed(r.cal.bias) + '</div>' +
      (r.held && r.held.mae !== undefined ? '<div>' + k('--calc-cal') + '<b>' + f2(r.held.mae) + ' MHz</b> the table in force, bias ' + signed(r.held.bias) + '</div>' : ''); });
  }
  window.calchartsLoad = load;
  load();
})();
