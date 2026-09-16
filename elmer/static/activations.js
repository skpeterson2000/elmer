/* Parks and summits: what is near, what counts, and what this operator has.

   Nothing here reaches the network on its own. The references are whatever
   has already been fetched and held, and fetching more is a press - it is
   thirty-odd requests to somebody else's servers and the better part of a
   minute, and a page that spends that the moment it is opened is a page
   nobody can open quietly. */

let acData = null;

/* The page and the filter have to count in the same thing. Asking somebody for
   a range in miles and answering in kilometres is the sort of mismatch that
   makes a reader distrust every other number on the page, and rightly. The
   server sends kilometres - it is what everything is computed in - and the
   unit is the operator's, from the gear. */
const AC_UNITS = (window.UNITS || {short: 'km', per_km: 1});

/* How old the held list is, said only when it is worth saying.
 *
 * A park that was there last month is almost certainly still there, so this
 * is not rot - it is that the lists move at the edges: POTA adds references
 * continually and retires a few, and SOTA associations revise summit lists at
 * their own pace. A reminder, never a refusal: stale data in the field beats
 * no data in the field, and the unit reading this in a valley cannot act on
 * it anyway. */
function acAge(cover) {
  if (!cover || cover.oldest_days === null || cover.oldest_days === undefined) {
    return '';
  }
  const days = cover.oldest_days;
  if (!cover.stale) {
    return days < 1 ? ', fetched today'
         : ', fetched ' + days + ' day' + (days === 1 ? '' : 's') + ' ago';
  }
  return ', <span style="color:var(--amber)">fetched ' + days + ' days ago ' +
         '&mdash; worth refreshing when there is a signal</span>';
}

function acAway(km) {
  /* Just the number. The unit is on the column heading, the way it is on
     the printed sheet - in a column this narrow "13 mi" wraps onto two lines
     and the table turns into a thicket. */
  if (km === null || km === undefined) return '\u2014';
  return Math.round(km * AC_UNITS.per_km);
}

function acPlace(row) {
  const summit = row.kind === 'summit';
  /* The reference carries the colour because the reference is the thing that
     says which programme a row belongs to - K-1234 is a park, W0M/xx-123 is a
     summit, and the two lists sit side by side where a glance can cross
     between them. Colouring the identifier means a row read out of the wrong
     column is visible as one. */
  return '<tr>' +
    '<td class="mono ' + (summit ? 'ref-summit' : 'ref-park') + '">' +
      '<a href="#ac-pick-panel" class="ac-ref" data-ref="' + escapeHTML(row.ref) + '">' +
      escapeHTML(row.ref) + '</a></td>' +
    '<td>' + escapeHTML(row.name) + '</td>' +
    '<td class="mono">' + acAway(row.km) + '</td>' +
    '<td class="mono">' + row.bearing + '&deg;</td>' +
    '<td class="tiny muted">' + (summit
      ? (row.alt_m ? row.alt_m + ' m' : '') +
        (row.points ? ' &middot; ' + row.points + ' pt' : '')
      : escapeHTML(row.where || '')) + '</td>' +
    '</tr>';
}

function acNear(d) {
  const box = document.getElementById('ac-near');
  const cover = document.getElementById('ac-cover');
  const note = document.getElementById('ac-note');
  if (!d.located) {
    cover.textContent = '';
    note.innerHTML = 'ELMER does not know where you are yet, and every answer ' +
      'here is an answer about a place. Set a QTH on the ' +
      '<a href="/propagation">propagation page</a> &mdash; a grid square is ' +
      'enough.';
    box.innerHTML = '';
    return;
  }
  const parks = d.parks || [], summits = d.summits || [];
  const held = d.held || {parks: 0, summits: 0};
  cover.textContent = 'from ' + d.qth;

  /* Nothing held and nothing near are different answers, and saying the
     second when the truth is the first is how a program loses somebody. */
  if (!d.coverage.known) {
    note.innerHTML = d.coverage.areas
      ? '<b>Nothing held for here.</b> ELMER has prepared somewhere else &mdash; ' +
        'the nearest is about ' + d.coverage.nearest_km + ' km away, which is ' +
        'not this. Fetch this area while there is a signal.'
      : '<b>Nothing held yet.</b> Fetch the parks and summits within ' +
        d.radius_km + ' km while there is a signal, and they are yours from ' +
        'then on &mdash; including in a valley with no bars, which is where ' +
        'they are wanted.';
    box.innerHTML = '';
    return;
  }
  const band = d.band || {};
  note.innerHTML = '<b>' + held.parks + ' park' + (held.parks === 1 ? '' : 's') +
    '</b> and <b>' + held.summits + ' summit' + (held.summits === 1 ? '' : 's') +
    '</b> between ' + acAway(band.inner_km || 0) + ' and ' + acAway(band.outer_km || d.radius_km) + ' ' + AC_UNITS.short +
    ' of ' + escapeHTML(d.qth) +
    acAge(d.coverage) +
    (band.note ? ' <span style="color:var(--amber)">' + escapeHTML(band.note) + '</span>' : '') +
    '. The nearest of each are below, ' +
    'and the distances are straight lines, which a road is not: reckon on more.';

  const table = (rows, total) => rows.length
    ? '<table class="data"><tr><th>Reference</th><th>Name</th>' +
        '<th>Away (' + AC_UNITS.short + ')</th>' +
      '<th>Bearing</th><th></th></tr>' + rows.map(acPlace).join('') + '</table>' +
      (total > rows.length
        ? '<p class="tiny muted">and ' + (total - rows.length) + ' more.</p>'
        : '')
    : '<p class="tiny muted">None held within the radius.</p>';
  box.innerHTML =
    '<div class="grid cols-2" style="gap:1.2rem">' +
      '<div class="prog prog-park">' +
        '<div class="panel-title">Parks</div>' +
        table(parks, held.parks) + '</div>' +
      '<div class="prog prog-summit">' +
        '<div class="panel-title">Summits</div>' +
        table(summits, held.summits) + '</div>' +
    '</div>';
}

function acRules(d) {
  const box = document.getElementById('ac-rules');
  box.innerHTML = (d.programs || []).map(p =>
    '<div>' +
      '<div class="panel-title" style="margin:0">' + escapeHTML(p.name) + '</div>' +
      '<p class="small" style="margin:.4rem 0"><b>' + p.qualifies +
        ' QSOs.</b> ' + escapeHTML(p.qualifies_note) + '</p>' +
      '<ul class="facts tiny muted" style="padding-left:1rem;line-height:1.5">' +
        '<li><b>Where:</b> ' + escapeHTML(p.where) + '</li>' +
        '<li><b>Power:</b> ' + escapeHTML(p.power) + '</li>' +
        '<li><b>Repeaters:</b> ' + (p.repeaters ? 'count' : 'do not count') +
          '. Satellites ' + (p.satellites ? 'do' : 'do not') + '.</li>' +
        '<li><b>Spotting:</b> ' + escapeHTML(p.self_spot) + '</li>' +
        '<li><b>Again:</b> ' + escapeHTML(p.again) + '</li>' +
      '</ul>' +
      '<p class="tiny muted" style="margin:.3rem 0 0">' +
        escapeHTML(p.source) + ' &middot; read ' + escapeHTML(p.read) + '</p>' +
    '</div>').join('');
}

/* Whose land it is: what the regulations say, each with its citation, and
   the edition it was read from - so an operator relying on it can check it
   and can see how old this copy is. */
function acLand(d) {
  const box = document.getElementById('ac-land');
  const land = d.land || {};
  if (!box || !(land.rules || []).length) return;
  box.innerHTML = land.rules.map(r =>
    '<div style="margin:.5rem 0 .8rem">' +
      '<div class="small"><b>' + escapeHTML(r.who) + '</b></div>' +
      '<p class="tiny muted" style="margin:.2rem 0;max-width:80ch;line-height:1.5">' +
        escapeHTML(r.what) + '</p>' +
      '<div class="tiny mono muted">' + escapeHTML(r.cite) + '</div>' +
    '</div>').join('') +
    '<p class="tiny muted" style="margin:.6rem 0 0">' + escapeHTML(land.source) +
      ' &middot; read ' + escapeHTML(land.read) + '</p>';
}

/* Worst news first: the one that stops the trip is the one that changes what
   somebody packs, and there is no point burying it under three that are fine. */
const AC_RANK = {forbidden: 0, 'no credit': 1, counts: 2};

function acVerdicts() {
  const box = document.getElementById('ac-verdicts');
  if (!acData) return;
  const ticked = Array.from(
    document.querySelectorAll('#ac-gear input:checked')).map(el => el.value);
  if (!ticked.length) {
    box.innerHTML = '<p class="tiny muted">Tick what you would take.</p>';
    return;
  }
  box.innerHTML = (acData.programs || []).map(p => {
    const rows = ticked
      .filter(k => acData.gear[k])
      .map(k => ({key: k, v: acData.gear[k][p.key], note: acData.gear[k].note}))
      .sort((a, b) => (AC_RANK[a.v] ?? 3) - (AC_RANK[b.v] ?? 3));
    const tone = v => v === 'forbidden' ? 'var(--red)'
                    : v === 'no credit' ? 'var(--amber)' : 'var(--green)';
    return '<div style="margin-top:.7rem">' +
      '<b class="small">' + escapeHTML(p.name) + '</b>' +
      rows.map(r =>
        '<div class="small" style="border-left:2px solid ' + tone(r.v) +
          ';padding:.2rem .6rem;margin-top:.3rem">' +
          '<b style="color:' + tone(r.v) + '">' + escapeHTML(r.v) + '</b> &mdash; ' +
          escapeHTML(r.note) + '</div>').join('') +
      '</div>';
  }).join('');
}

/* The awards half. A callsign leaving this unit for somebody else's server is
   the operator's decision, so the panel says what it would send, to whom, and
   what comes back - and then waits. */
function acAwards() {
  const box = document.getElementById('ac-awards');
  if (!box) return;
  if (!window.CALLSIGN) {
    box.innerHTML = '<p class="small muted">No callsign on this unit, so there ' +
      'is nothing to look up.</p>';
    return;
  }
  if (window.POTA_ASKED !== true) {
    box.innerHTML =
      '<p class="small">ELMER can show what <b>' + escapeHTML(window.CALLSIGN) +
        '</b> has done in POTA. It would send that callsign to ' +
        '<span class="mono">api.pota.app</span> and keep what comes back: the ' +
        'awards and the counts. The name, the town and the avatar the endpoint ' +
        'also returns are thrown away, and nothing else about this unit is ' +
        'sent.</p>' +
      '<div class="row" style="gap:.5rem">' +
        '<button class="btn sm primary" data-pota="yes">Look it up</button>' +
        '<button class="btn sm ghost" data-pota="no">No thanks</button>' +
      '</div>';
    return;
  }
  box.innerHTML = '<p class="tiny muted">Asking POTA&hellip;</p>';
  api('/api/pota/' + encodeURIComponent(window.CALLSIGN)).then(d => {
    if (!d.ok && !d.found) {
      box.innerHTML = '<p class="small muted">' +
        escapeHTML(window.CALLSIGN) + ' has no POTA record, which is not a ' +
        'fault &mdash; most licensees have never chased a park.</p>';
      return;
    }
    if (!d.ok) {
      box.innerHTML = '<p class="small" style="color:var(--amber)">' +
        escapeHTML(d.error || 'POTA could not be reached') + '</p>';
      return;
    }
    const a = d.activator || {}, h = d.hunter || {};
    box.innerHTML =
      (d.stale ? '<p class="tiny" style="color:var(--amber)">Held from an ' +
        'earlier look &mdash; POTA could not be reached just now.</p>' : '') +
      '<div class="row" style="gap:1.4rem;flex-wrap:wrap">' +
        '<span>Activator <b>' + a.activations + '</b> activations, <b>' +
          a.parks + '</b> parks, <b>' + a.qsos + '</b> QSOs</span>' +
        '<span>Hunter <b>' + h.parks + '</b> parks, <b>' + h.qsos +
          '</b> QSOs</span>' +
      '</div>' +
      ((d.awards || []).length
        ? '<table class="data mt"><tr><th>Award</th><th>Granted</th></tr>' +
          d.awards.map(w => '<tr><td>' + escapeHTML(w.name) + '</td>' +
            '<td class="mono">' + escapeHTML(w.granted) + '</td></tr>').join('') +
          '</table>'
        : '<p class="tiny muted mt">No awards on the record yet.</p>');
  }).catch(() => {
    box.innerHTML = '<p class="small muted">POTA could not be reached.</p>';
  });
}

document.addEventListener('click', async e => {
  const said = e.target.closest('[data-pota]');
  if (said) {
    window.POTA_ASKED = said.dataset.pota === 'yes';
    await postJSON('/api/settings', {pota: window.POTA_ASKED}).catch(() => {});
    if (window.POTA_ASKED) acAwards();
    else document.getElementById('ac-awards').innerHTML =
      '<p class="small muted">Left alone. Nothing has been sent anywhere.</p>';
    return;
  }
  const sheet = e.target.closest('#ac-print');
  if (sheet) {
    /* Straight to the PDF, in the page. A full-screen browser has no
       downloads folder anybody can reach, so the shelf is where it goes and
       the shelf is inside ELMER - see prints.py. */
    const what = document.getElementById('ac-print-what').value;
    const say = document.getElementById('ac-fetch-say');
    const inner = document.getElementById('ac-inner').value;
    const outer = document.getElementById('ac-outer').value;
    /* Empty means here. Anything typed is resolved on the server, which
       already accepts a town, a grid square or coordinates and does the first
       two without touching the network. */
    const from = document.getElementById('ac-from').value.trim();
    sheet.disabled = true;
    const was = sheet.textContent;
    sheet.textContent = 'Printing…';
    try {
      const res = await fetch('/api/activations/print', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({want: what, inner: inner,
                              outer: outer, from: from})});
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        say.innerHTML = '<span style="color:var(--amber)">' +
          escapeHTML(d.error || 'nothing to print yet') + '</span>';
        sheet.disabled = false; sheet.textContent = was;
        return;
      }
      location.href = d.view;
    } catch (err) {
      say.innerHTML = '<span style="color:var(--amber)">could not build the ' +
        'sheet &mdash; see data/elmer.log</span>';
      sheet.disabled = false; sheet.textContent = was;
    }
    return;
  }

  const go = e.target.closest('#ac-fetch');
  if (!go) return;
  const say = document.getElementById('ac-fetch-say');
  go.disabled = true;
  say.textContent = 'asking POTA and SOTA - this takes most of a minute…';
  try {
    const d = await postJSON('/api/activations/prepare', {});
    say.textContent = d.ok
      ? d.area.parks + ' parks and ' + d.area.summits + ' summits held.'
      : (d.error || 'could not fetch');
  } catch (err) {
    say.textContent = 'could not fetch just now.';
  }
  go.disabled = false;
  acLoad();
});

document.addEventListener('change', e => {
  if (e.target.closest('#ac-gear')) acVerdicts();
});

async function acLoad() {
  const q = new URLSearchParams({
    inner: (document.getElementById('ac-inner') || {}).value || 0,
    outer: (document.getElementById('ac-outer') || {}).value || 50,
    from: ((document.getElementById('ac-from') || {}).value || '').trim()});
  try {
    acData = await api('/api/activations?' + q);
  } catch (e) { return; }
  acNear(acData);
  acRules(acData);
  acLand(acData);
  acVerdicts();
}

if (document.getElementById('ac-near')) {
  acLoad();
  acAwards();
  /* The band and the place it is around drive the list as they change -
     a moment after the typing stops, so a town is looked up once. */
  let acBandTimer = null;
  ['ac-inner', 'ac-outer', 'ac-from'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => { clearTimeout(acBandTimer); acBandTimer = setTimeout(acLoad, id === 'ac-from' ? 700 : 250); });
  });
}


/* ---------------------------------------------------- one place, picked */
/* The programme's own record of a park or a summit, read out: how many
   made it, on what, when, and who was last. Fetched while there is a signal
   and held on disk after, the same bargain as the lists. The spots inside it
   are ELMER's own, from data/landmarks.json, and each is a button that sets
   the "of" box on this page to it - so "mile 55" is one press, not a search. */
function acMonthBar(story) {
  if (!story || !story.by_month) return '';
  const max = Math.max.apply(null, story.by_month) || 1;
  const names = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  return '<div class="ac-months" title="activations by month, all years">' +
    story.by_month.map((n, i) => '<span><i style="height:' + Math.round(100 * n / max) +
      '%"></i><b>' + names[i] + '</b></span>').join('') + '</div>';
}

function acCard(r) {
  const box = document.getElementById('ac-pick-card');
  if (!r.ok) {
    box.innerHTML = '<p class="small muted">' + escapeHTML(r.error || 'nothing found') + '</p>';
    return;
  }
  const summit = r.kind === 'summit';
  const from = r.from_here
    ? '<span class="mono">' + acAway(r.from_here.km) + ' ' + AC_UNITS.short + ' at ' +
      r.from_here.bearing + '&deg;</span> from ' + escapeHTML(r.from_here.qth)
    : 'set a QTH for the distance';
  const facts = [
    summit ? (r.alt_ft ? r.alt_ft + ' ft' : '') + (r.points ? ' &middot; ' + r.points + ' points' : '')
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
  const spots = r.spots && r.spots.spots && r.spots.spots.length
    ? '<div class="panel-title mt" style="margin-bottom:.3rem">Where people set up</div>' +
      '<p class="tiny muted" style="margin:0 0 .4rem">' + escapeHTML(r.spots.about || '') +
      ' A press puts the spot in the “of” box above, so the printed sheet is measured from it; ~ marks one read from a map by eye.</p>' +
      '<div class="row" style="gap:.35rem;flex-wrap:wrap">' + r.spots.spots.map(s =>
        '<button class="btn sm ghost ac-spot" data-name="' + escapeHTML(s.short) + '" title="' +
        escapeHTML(s.kind + ' - ' + s.grid) + '">' + escapeHTML(s.short) + (s.about ? ' ~' : '') + '</button>').join('') +
      '</div>'
    : '';
  box.innerHTML =
    '<div class="prog ' + (summit ? 'prog-summit' : 'prog-park') + '">' +
    '<div class="spread" style="align-items:baseline">' +
      '<div><span class="mono ' + (summit ? 'ref-summit' : 'ref-park') + '">' + escapeHTML(r.ref) + '</span> ' +
      '<b>' + escapeHTML(r.name || '') + '</b></div>' +
      '<span class="tiny">' + from + '</span></div>' +
    '<div class="tiny muted" style="margin:.2rem 0 .5rem">' + facts + '</div>' +
    '<p class="small" style="margin:.3rem 0">' + escapeHTML(r.sentence || '') +
      (r.stale ? ' <span class="muted">(held from an earlier look; the programme could not be reached)</span>' : '') + '</p>' +
    modes + acMonthBar(r.story) +
    (r.seen
      ? '<p class="small" style="margin:.5rem 0 0">' + escapeHTML(r.seen_sentence || '') +
        (r.seen.busy_utc && r.seen.busy_utc.length
          ? ' Busiest around ' + r.seen.busy_utc.map(h => acLocalHour(h)).join(', ') + '.' : '') + '</p>' +
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
  box.querySelectorAll('.ac-spot').forEach(b => b.addEventListener('click', () => {
    const from = document.getElementById('ac-from');
    if (!from) return;
    from.value = b.dataset.name;
    const hint = document.getElementById('ac-from-hint');
    if (hint) hint.textContent = 'the printed sheet is measured from ' + b.dataset.name;
    toast('Sheet from ' + b.dataset.name, 'Print nearest measures from there now');
  }));
}

async function acPickRef(ref) {
  const hint = document.getElementById('ac-pick-hint');
  hint.textContent = 'asking the programme\u2026';
  document.getElementById('ac-pick-matches').hidden = true;
  try {
    acCard(await api('/api/reference?ref=' + encodeURIComponent(ref)));
    hint.textContent = '';
  } catch (e) {
    hint.textContent = 'could not look that up';
  }
}

async function acPick() {
  const text = document.getElementById('ac-pick').value.trim();
  if (!text) return;
  if (/^[A-Z0-9]{1,3}-\d{3,6}$/i.test(text) || /^[A-Z0-9]+\/[A-Z]{2}-\d{3}$/i.test(text)) {
    acPickRef(text.toUpperCase());
    return;
  }
  const hint = document.getElementById('ac-pick-hint');
  const list = document.getElementById('ac-pick-matches');
  let d;
  try { d = await api('/api/reference?q=' + encodeURIComponent(text)); } catch (e) { d = {matches: []}; }
  const m = d.matches || [];
  if (!m.length) {
    hint.textContent = 'nothing held by that name - a reference works anywhere, and "Fetch what is near" brings the state parks and summits in';
    list.hidden = true;
    return;
  }
  if (m.length === 1) { acPickRef(m[0].ref); return; }
  hint.textContent = m.length + ' held - pick one';
  list.hidden = false;
  list.innerHTML = m.map(r => '<button class="btn sm ghost ac-match" data-ref="' + escapeHTML(r.ref) + '">' +
    '<span class="mono ' + (r.kind === 'summit' ? 'ref-summit' : 'ref-park') + '">' + escapeHTML(r.ref) + '</span> ' +
    escapeHTML(r.name) + (r.activations ? ' <span class="tiny muted">' + r.activations + ' act.</span>' : '') + '</button>').join(' ');
  list.querySelectorAll('.ac-match').forEach(b => b.addEventListener('click', () => acPickRef(b.dataset.ref)));
}

document.getElementById('ac-pick-go').addEventListener('click', acPick);
document.getElementById('ac-pick').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); acPick(); } });
document.addEventListener('click', e => {
  const a = e.target.closest('.ac-ref');
  if (!a) return;
  document.getElementById('ac-pick').value = a.dataset.ref;
  acPickRef(a.dataset.ref);
});

/* An hour of the day off the spot feed, said on the viewer's clock. */
function acLocalHour(utcHour) {
  const d = new Date(); d.setUTCHours(utcHour, 0, 0, 0);
  return d.toLocaleTimeString([], {hour: 'numeric'});
}
