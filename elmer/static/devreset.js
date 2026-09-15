/* DEVELOPMENT ONLY. Delete this file, the Developer panel in tools.html, and
   the /api/dev/reset routes in app.py to take it out.

   Two presses, and the second one carries the count the first was shown. A
   page left open while somebody fetched a day's worth of parks would
   otherwise take them on a press meant for an empty unit. */
(function () {
  const look = document.getElementById('dev-look');
  if (!look) return;
  const say = document.getElementById('dev-say');
  const list = document.getElementById('dev-list');

  look.addEventListener('click', async () => {
    look.disabled = true;
    say.textContent = 'looking…';
    let d;
    try {
      d = await (await fetch('/api/dev/reset')).json();
    } catch (e) {
      d = {ok: false, error: 'could not ask'};
    }
    look.disabled = false;
    if (!d.ok) {
      say.innerHTML = '<span style="color:var(--amber)">' +
        escapeHTML(d.error || 'no') + '</span>';
      return;
    }
    if (!d.count) {
      say.textContent = 'nothing to take - this unit is already fresh.';
      list.hidden = true;
      return;
    }
    say.textContent = '';
    list.hidden = false;
    list.innerHTML =
      '<p class="small mt"><b>' + d.count + ' thing' +
      (d.count === 1 ? '' : 's') + ' would go:</b></p>' +
      '<ul class="tiny" style="columns:2">' +
      d.items.map(i => '<li class="mono">' + escapeHTML(i) + '</li>').join('') +
      '</ul>' +
      '<div class="row"><button class="btn sm danger" id="dev-go" ' +
      'data-count="' + d.count + '">Reset this unit</button>' +
      '<button class="btn sm ghost" id="dev-no">Leave it alone</button></div>';
  });

  document.addEventListener('click', async e => {
    if (e.target.closest('#dev-no')) {
      list.hidden = true;
      say.textContent = 'left alone.';
      return;
    }
    const go = e.target.closest('#dev-go');
    if (!go) return;
    go.disabled = true;
    go.textContent = 'Resetting…';
    let d;
    try {
      const res = await fetch('/api/dev/reset', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({count: Number(go.dataset.count)})});
      d = await res.json();
    } catch (err) {
      d = {ok: false, error: 'could not reset'};
    }
    if (!d.ok) {
      list.hidden = true;
      say.innerHTML = '<span style="color:var(--amber)">' +
        escapeHTML(d.error || 'no') + '</span>';
      return;
    }
    /* ELMER restarts to do it - the running server holds the database and
       the log, so the clean happens on the way back up. Wait for it, then
       the dashboard: a fresh unit's first run. */
    list.hidden = true;
    say.textContent = 'ELMER is restarting to reset itself…';
    for (let n = 0; n < 90; n++) {
      await new Promise(r => setTimeout(r, 1000));
      try {
        const res = await fetch('/api/update', {cache: 'no-store'});
        if (res.ok) { location.href = '/'; return; }
      } catch (e) { /* still down, which is expected */ }
    }
    say.innerHTML = '<span style="color:var(--amber)">ELMER has not come back yet - ' +
      'start it again from the Start Menu or the terminal.</span>';
  });
})();
