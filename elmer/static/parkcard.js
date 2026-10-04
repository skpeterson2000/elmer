/* A park's or a summit's card: the program's own record, read out - how many
   made it, on what, when, and who was last - with the bands and hours this
   unit has seen it on the spot feed. Drawn from /api/reference.

   The POTA / SOTA page shows it for a place picked there; the Band Plan's
   reach map shows it for a tree pressed there. One card, so the two pages can
   never describe the same park two ways. Needs elmer.js (escapeHTML,
   highFtText) loaded first. */

/* The operator's units, from the page; kilometers if the page has none. */
const PARK_UNITS = (window.UNITS || {short: 'km', per_km: 1});

function parkAway(km) {
  if (km === null || km === undefined) return '—';
  return Math.round(km * PARK_UNITS.per_km);
}

function parkMonthBar(story) {
  if (!story || !story.by_month) return '';
  const max = Math.max.apply(null, story.by_month) || 1;
  const names = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  return '<div class="ac-months" title="activations by month, all years">' +
    story.by_month.map((n, i) => '<span><i style="height:' + Math.round(100 * n / max) +
      '%"></i><b>' + names[i] + '</b></span>').join('') + '</div>';
}

/* An hour of the day off the spot feed, said on the viewer's clock. */
function parkLocalHour(utcHour) {
  const d = new Date(); d.setUTCHours(utcHour, 0, 0, 0);
  return d.toLocaleTimeString([], {hour: 'numeric'});
}

/* Sets a card's box apart, in the program's color, and washes it brighter
   for a moment so the arrival is seen from further up the page. The class
   is taken off and put back so a second card in the same place washes too. */
function parkArrive(el, summit) {
  if (!el) return;
  el.classList.add('park-box');
  el.classList.toggle('summit', !!summit);
  el.classList.remove('arrive');
  void el.offsetWidth;            // a reflow, so the animation starts again
  el.classList.add('arrive');
}

function parkCard(r, box, opts) {
  opts = opts || {};
  if (!r.ok) {
    box.innerHTML = '<p class="small muted">' + escapeHTML(r.error || 'nothing found') + '</p>';
    return;
  }
  const summit = r.kind === 'summit';
  const from = r.from_here
    ? '<span class="mono">' + parkAway(r.from_here.km) + ' ' + PARK_UNITS.short + ' at ' +
      r.from_here.bearing + '&deg;</span> from ' + escapeHTML(r.from_here.qth)
    : 'set a QTH for the distance';
  const facts = [
    summit ? (r.alt_ft ? highFtText(r.alt_ft) : '') + (r.points ? ' &middot; ' + r.points + ' points' : '')
           : escapeHTML([r.type, r.agency].filter(Boolean).join(' - ')),
    escapeHTML(r.where || ''), r.grid ? '<span class="mono">' + escapeHTML(r.grid) + '</span>' : '',
    r.access ? 'access: ' + escapeHTML(r.access) : '', r.methods ? 'set up: ' + escapeHTML(r.methods) : '',
  ].filter(Boolean).join(' &middot; ');
  const modes = r.story && r.story.modes
    ? '<div class="ac-modes"><i class="phone" style="width:' + r.story.modes.phone + '%" title="phone"></i>' +
      '<i class="cw" style="width:' + r.story.modes.cw + '%" title="CW"></i>' +
      '<i class="data" style="width:' + r.story.modes.data + '%" title="data"></i></div>' +
      '<div class="tiny muted">phone &middot; CW &middot; data, by contacts made</div>'
    : '';
  /* Where people set up. On the POTA page each is a button that measures the
     printed sheet from it; anywhere else they are named, since there is no
     sheet there to measure. */
  const held = r.spots && r.spots.spots && r.spots.spots.length ? r.spots.spots : null;
  const spots = !held ? ''
    : opts.onSpot
    ? '<div class="panel-title mt" style="margin-bottom:.3rem">Where people set up</div>' +
      '<p class="tiny muted" style="margin:0 0 .4rem">' + escapeHTML(r.spots.about || '') +
      ' A press puts the spot in the “of” box above, so the printed sheet is measured from it; ~ marks one read from a map by eye.</p>' +
      '<div class="row" style="gap:.35rem;flex-wrap:wrap">' + held.map(s =>
        '<button class="btn sm ghost ac-spot" data-name="' + escapeHTML(s.short) + '" title="' +
        escapeHTML(s.kind + ' - ' + s.grid) + '">' + escapeHTML(s.short) + (s.about ? ' ~' : '') + '</button>').join('') +
      '</div>'
    : '<div class="tiny muted mt">Where people set up: ' + held.map(s =>
        escapeHTML(s.short) + (s.about ? ' ~' : '')).join(' &middot; ') + '</div>';
  /* POTA's own pages for the park and, from a spot, the activator. They
     leave ELMER for pota.app - on a full-screen unit there may be no way back
     but the window's own close - so they say so, and open beside the page
     rather than in place of it. Parks only: a summit is SOTA's. */
  const pota = 'https://pota.app/#/';
  const out = [
    !summit && r.ref ? '<a class="btn sm ghost" target="_blank" rel="noopener" href="' + pota + 'park/' +
      encodeURIComponent(r.ref) + '" title="the park’s page on pota.app - opens outside ELMER">' +
      escapeHTML(r.ref) + ' on POTA</a>' : '',
    opts.activator ? '<a class="btn sm ghost" target="_blank" rel="noopener" href="' + pota + 'profile/' +
      encodeURIComponent(opts.activator) + '" title="the activator’s profile on pota.app - opens outside ELMER">' +
      escapeHTML(opts.activator) + ' on POTA</a>' : ''
  ].filter(Boolean);
  const links = out.length
    ? '<div class="row" style="gap:.4rem;flex-wrap:wrap;margin:.1rem 0 .5rem">' + out.join('') + '</div>' : '';
  box.innerHTML =
    '<div class="prog ' + (summit ? 'prog-summit' : 'prog-park') + '">' +
    '<div class="spread" style="align-items:baseline">' +
      '<div><span class="mono ' + (summit ? 'ref-summit' : 'ref-park') + '">' + escapeHTML(r.ref) + '</span> ' +
      '<b>' + escapeHTML(r.name || '') + '</b></div>' +
      '<span class="tiny">' + from + '</span></div>' +
    '<div class="tiny muted" style="margin:.2rem 0 .5rem">' + facts + '</div>' +
    links +
    '<p class="small" style="margin:.3rem 0">' + escapeHTML(r.sentence || '') +
      (r.stale ? ' <span class="muted">(held from an earlier look; the program could not be reached)</span>' : '') + '</p>' +
    modes + parkMonthBar(r.story) +
    (r.seen
      ? '<p class="small" style="margin:.5rem 0 0">' + escapeHTML(r.seen_sentence || '') +
        (r.seen.busy_utc && r.seen.busy_utc.length
          ? ' Busiest around ' + r.seen.busy_utc.map(h => parkLocalHour(h)).join(', ') + '.' : '') + '</p>' +
        (r.seen.hints && r.seen.hints.length
          ? '<div class="tiny muted" style="margin-top:.25rem">Said on the feed: ' + r.seen.hints.slice(0, 4).map(h =>
              '“' + escapeHTML(h.text) + '”' + (h.call ? ' — ' + escapeHTML(h.call) : '') +
              (h.band ? ', ' + escapeHTML(h.band) : '')).join(' · ') + '</div>'
          : '')
      : '<p class="tiny muted" style="margin:.5rem 0 0">Bands and hours come from the spot feed, which this unit samples while it has a network; nothing seen here yet.</p>') +
    (r.story && r.story.recent && r.story.recent.length
      ? '<div class="tiny muted mt">Lately: ' + r.story.recent.map(a =>
          escapeHTML(a.date) + (a.call ? ' ' + escapeHTML(a.call) : '') + (a.qsos != null ? ' (' + a.qsos + ')' : '')).join(' &middot; ') + '</div>'
      : '') +
    spots +
    (r.website ? '<div class="tiny mt"><a href="' + escapeHTML(r.website) + '" target="_blank" rel="noopener">the place\u2019s own page</a></div>' : '') +
    '</div>';
  if (opts.onSpot) box.querySelectorAll('.ac-spot').forEach(b =>
    b.addEventListener('click', () => opts.onSpot(b.dataset.name)));
}
