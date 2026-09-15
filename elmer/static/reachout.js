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
    '<div class="panel-title" style="margin-top:.6rem">The approach</div>' +
    '<ol style="margin:.2rem 0 0;padding-left:1.2rem">' + steps + '</ol>' +
    '<p class="tiny muted" style="margin:.5rem 0 0">This is what the numbers say. The band that ' +
    'carries it is the science; working it is the art - call, listen a full minute, move, try again.</p>' +
    '</div>';
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
