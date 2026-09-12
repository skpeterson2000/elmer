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
