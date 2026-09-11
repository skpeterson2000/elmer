/* Parks and summits: what is near, what counts, and what this operator has.

   Nothing here reaches the network on its own. The references are whatever
   has already been fetched and held, and fetching more is a press - it is
   thirty-odd requests to somebody else's servers and the better part of a
   minute, and a page that spends that the moment it is opened is a page
   nobody can open quietly. */

let acData = null;

function acPlace(row) {
  const summit = row.kind === 'summit';
  /* The reference carries the colour because the reference is the thing that
     says which programme a row belongs to - K-1234 is a park, W0M/xx-123 is a
     summit, and the two lists sit side by side where a glance can cross
     between them. Colouring the identifier means a row read out of the wrong
     column is visible as one. */
  return '<tr>' +
    '<td class="mono ' + (summit ? 'ref-summit' : 'ref-park') + '">' +
      escapeHTML(row.ref) + '</td>' +
    '<td>' + escapeHTML(row.name) + '</td>' +
    '<td class="mono">' + row.km + ' km</td>' +
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
  note.innerHTML = '<b>' + held.parks + ' park' + (held.parks === 1 ? '' : 's') +
    '</b> and <b>' + held.summits + ' summit' + (held.summits === 1 ? '' : 's') +
    '</b> held within ' + d.radius_km + ' km. The nearest of each are below, ' +
    'and the distances are straight lines, which a road is not: reckon on more.';

  const table = (rows, total) => rows.length
    ? '<table class="data"><tr><th>Reference</th><th>Name</th><th>Away</th>' +
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
  try {
    acData = await api('/api/activations');
  } catch (e) { return; }
  acNear(acData);
  acRules(acData);
  acVerdicts();
}

if (document.getElementById('ac-near')) {
  acLoad();
  acAwards();
}
