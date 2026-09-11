/* Certificates: the form the host fills in before printing.

   A certificate has things on it the program cannot know - the event, who is
   hosting, the date as it should read, who signs - and one thing it knows but
   should let a person check: the winners' names, which were typed on phones.
   So the button opens a card, not a print dialog. The details are remembered
   on the unit between prints, so a club sets them once for the day; the name
   fixes are not, because they belong to these people and this print.

   Shared by net control and the table screen, which differ only in scope. */
(function () {
  const btn = document.getElementById('certs');
  const host = document.getElementById('certs-panel');
  if (!btn || !host) return;
  const scope = host.dataset.scope || 'table';

  const esc = s => { const d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; };
  const api = async (path, body) => {
    const r = await fetch(path, body ? {method: 'POST', headers: {'Content-Type': 'application/json'},
                                        body: JSON.stringify(body)} : {});
    return {ok: r.ok, status: r.status, data: await r.json().catch(() => ({}))};
  };

  function field(id, label, value, hint, attrs) {
    return '<div class="cf"><label for="' + id + '">' + label + '</label>' +
      '<input id="' + id + '" value="' + esc(value) + '" ' + (attrs || '') + '>' +
      (hint ? '<div class="cf-hint">' + hint + '</div>' : '') + '</div>';
  }

  async function open() {
    btn.disabled = true;
    const r = await api('/api/tournament/certificates/preview?scope=' + scope);
    btn.disabled = false;
    const d = r.data.details || {}, awards = r.data.awards || [], game = r.data.game || {};
    const PLACE = {1: 'First', 2: 'Second', 3: 'Third'};
    host.innerHTML = `
      <div class="card certs-card">
        <div class="certs-head"><b>Certificates</b>
          <span class="tiny muted">${awards.length ? esc(game.label || '') + ' - ' + awards.length + ' to award' : 'nobody to award yet'}</span>
          <button class="btn sm ghost" id="certs-close" style="margin-left:auto">Close</button></div>
        <div class="certs-grid">
          ${field('cf-event', 'Event', d.event, 'As it should read across the top: "Hamfest", "Club Night", "Field Day".')}
          ${field('cf-club', 'Hosted by', d.club, 'The club or organisation, under the event. Leave blank if the event says it.')}
          ${field('cf-when', 'Date, as it should read', d.when, 'Any wording: "Saturday 17 July 2027", or just "July 2027".')}
          ${field('cf-where', 'Place', d.where, 'Town and state. Starts from the station’s QTH.')}
          ${field('cf-net', 'Net control, for the signature line', d.net_control, 'Printed under the line, so they only have to sign.')}
          ${field('cf-signer', 'Club or event signatory', d.club_signer, 'An officer’s name, or leave it for whoever signs.')}
        </div>
        <div class="cf" style="margin-top:.4rem"><label>Placings to print</label>
          <select id="cf-places" class="btn">${[1, 2, 3].map(n => '<option value="' + n + '"' + (n === (d.places || 3) ? ' selected' : '') + '>' + (n === 1 ? 'First only' : 'First to ' + PLACE[n].toLowerCase()) + '</option>').join('')}</select></div>
        ${awards.length ? `<div class="certs-names"><div class="tiny muted" style="margin:.6rem 0 .3rem">The names as they will print. These are what the players asked for; fix a spelling here, not on the wall.</div>
          ${awards.map(a => `<div class="cf cf-name"><label>${PLACE[a.place] || a.place} place</label>
            <input data-place="${a.place}" value="${esc(a.name)}" maxlength="48">
            <div class="cf-hint">${esc((a.lines || []).slice(0, 2).join(' · '))}</div></div>`).join('')}</div>` : ''}
        <div class="row" style="gap:.5rem;margin-top:.8rem;align-items:center">
          <button class="btn primary" id="certs-print" ${awards.length ? '' : 'disabled'}>Print certificates</button>
          <span class="tiny muted">One page per placing, on the Printouts shelf. The event details are kept for the next print.</span>
        </div>
        <div class="tiny muted" id="certs-msg" style="margin-top:.4rem"></div>
      </div>`;
    host.hidden = false;
    host.scrollIntoView({block: 'nearest'});
    document.getElementById('certs-close').addEventListener('click', () => { host.hidden = true; host.innerHTML = ''; });
    const print = document.getElementById('certs-print');
    if (print) print.addEventListener('click', async () => {
      const names = {};
      document.querySelectorAll('#certs-panel [data-place]').forEach(i => { names[i.dataset.place] = i.value; });
      const body = {scope, names,
        event: document.getElementById('cf-event').value,
        club: document.getElementById('cf-club').value,
        when: document.getElementById('cf-when').value,
        where: document.getElementById('cf-where').value,
        net_control: document.getElementById('cf-net').value,
        club_signer: document.getElementById('cf-signer').value,
        places: +document.getElementById('cf-places').value};
      print.disabled = true; print.textContent = 'Building…';
      const r = await api('/api/tournament/certificates', body);
      if (r.ok && r.data.view) { location.href = r.data.view; return; }
      print.disabled = false; print.textContent = 'Print certificates';
      document.getElementById('certs-msg').textContent = r.data.message || r.data.error || 'Could not build the certificates.';
    });
  }

  btn.addEventListener('click', () => { if (host.hidden) open(); else { host.hidden = true; host.innerHTML = ''; } });
})();
