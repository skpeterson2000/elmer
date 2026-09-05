/* The software panel: what this install is, and whether it has fallen behind.

   The page never fetches from the network itself - it reads the answer the
   background check already cached, so opening the dashboard costs nothing.
   Everything that changes the install is offered only to a browser on the
   machine itself; a phone on the LAN sees the version and nothing to press. */

function updateStatusLine(d) {
  const st = d.state, s = d.status || {};
  if (!st.checkout) {
    return ['warn', 'Not a git checkout, so it cannot update itself. ' +
                    'Run <span class="mono">./elmer.py --adopt</span> to point ' +
                    'this copy at the repository without touching your files.'];
  }
  if (s.error) return ['warn', escapeHTML(s.error)];
  if (!s.checked_at) return ['', 'Not checked yet.'];
  const when = new Date(s.checked_at * 1000).toLocaleString();
  if (s.behind) {
    return ['warn', '<b>' + s.behind + ' update' + (s.behind === 1 ? '' : 's') +
            ' waiting.</b> Checked ' + escapeHTML(when) + '.'];
  }
  return ['good', 'Up to date as of ' + escapeHTML(when) + '.'];
}

function renderUpdate(d) {
  const panel = document.getElementById('software');
  const strip = document.getElementById('update-strip');
  if (!panel) return;
  const st = d.state, s = d.status || {}, waiting = !!s.behind;
  const [tone, line] = updateStatusLine(d);

  panel.innerHTML =
    '<div class="panel-title">Software</div>' +
    '<div class="row" style="gap:.7rem;align-items:baseline">' +
      (st.head ? '<span class="pill mono">' + escapeHTML(st.head) + '</span>' : '') +
      (st.branch ? '<span class="tiny muted mono">' + escapeHTML(st.branch) + '</span>' : '') +
      (st.date ? '<span class="tiny muted">' + escapeHTML(st.date) + '</span>' : '') +
      (st.dirty ? '<span class="pill warn" title="uncommitted changes here">local changes</span>' : '') +
    '</div>' +
    (st.subject ? '<div class="small" style="margin-top:.3rem">' +
                  escapeHTML(st.subject) + '</div>' : '') +
    '<div class="small ' + (tone === 'warn' ? 'warntext' : 'muted') +
      '" style="margin-top:.5rem">' + line + '</div>' +
    (d.blocked && waiting
      ? '<div class="small warntext" style="margin-top:.3rem">Held back: ' +
        escapeHTML(d.blocked) + '</div>' : '') +
    (d.local ? updateControls(d, waiting) : '') +
    '<p class="tiny muted" style="margin:.7rem 0 0">' +
      'ELMER checks the repository it was installed from and tells you what it ' +
      'finds. It never applies an update on its own &mdash; that is always your ' +
      'press, whenever it suits you. Updating is a fast-forward, and never ' +
      'happens while there are local changes here.</p>';

  if (strip) {
    strip.innerHTML = waiting && !d.blocked
      ? '<div class="panel tight welcome"><div class="row" style="gap:.8rem">' +
          '<b>An ELMER update is waiting</b>' +
          '<span class="small muted">' + s.behind + ' commit' +
            (s.behind === 1 ? '' : 's') + ' &mdash; ' +
            escapeHTML((s.commits[0] || {}).subject || '') + '</span>' +
          (d.local ? '<button class="btn sm primary" data-update="apply" ' +
                     'style="margin-left:auto">Update now</button>' : '') +
        '</div></div>'
      : '';
  }
}

function updateControls(d, waiting) {
  /* Looking is automatic; applying never is. The only choice here is whether
     ELMER looks at all. */
  const options = [['notify', 'tell me'], ['off', 'never check']];
  return '<div class="row" style="gap:.6rem;margin-top:.7rem">' +
    '<button class="btn sm" data-update="check">Check now</button>' +
    (waiting && !d.blocked
      ? '<button class="btn sm primary" data-update="apply">Update now</button>' : '') +
    '<label class="tiny muted" style="margin-left:auto">When an update appears&nbsp;' +
      '<select id="update-policy">' + options.map(([v, label]) =>
        '<option value="' + v + '"' + (d.policy === v ? ' selected' : '') + '>' +
        label + '</option>').join('') + '</select></label>' +
    '</div>' +
    (d.status && d.status.behind && d.status.commits.length
      ? '<ul class="facts" style="margin-top:.6rem">' + d.status.commits.map(c =>
          '<li><span class="mono tiny">' + escapeHTML(c.short) + '</span> ' +
          escapeHTML(c.subject) + '</li>').join('') + '</ul>'
      : '');
}

/* The server goes away mid-request when it restarts onto the new code, so the
   page waits for it to answer again and reloads itself. On a kiosk this is the
   only thing anybody sees of an update. */
async function waitForServer(box, tries) {
  for (let n = 0; n < (tries || 60); n++) {
    await new Promise(r => setTimeout(r, 1000));
    try {
      const res = await fetch('/api/update', {cache: 'no-store'});
      if (res.ok) { location.reload(); return; }
    } catch (e) { /* still down, which is expected */ }
  }
  box.innerHTML = '<div class="panel tight welcome">ELMER updated but has not ' +
    'come back yet. Reload the page in a moment.</div>';
}

async function applyUpdate() {
  const strip = document.getElementById('update-strip');
  const panel = document.getElementById('software');
  const box = strip && strip.innerHTML ? strip : panel;
  box.innerHTML = '<div class="panel tight welcome">Updating&hellip;</div>';
  let res;
  try {
    res = await fetch('/api/update/apply', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: '{}'});
  } catch (err) {
    box.innerHTML = '<div class="panel tight welcome">Lost contact while ' +
                    'updating. Reload the page in a moment.</div>';
    return;
  }
  const d = await res.json().catch(() => ({}));
  if (!res.ok || !d.ok) {
    box.innerHTML = '<div class="panel tight welcome">Could not update: ' +
                    escapeHTML(d.message || res.status) + '</div>';
    return;
  }
  if (d.detail && d.detail.rerun_install) {
    box.innerHTML = '<div class="panel tight welcome">Updated to ' +
      escapeHTML(d.detail.to) + '. This one changed the dependencies &mdash; ' +
      'run <span class="mono">./install.sh</span> before starting ELMER again.' +
      '</div>';
  } else {
    box.innerHTML = '<div class="panel tight welcome">Updated to ' +
      escapeHTML(d.detail ? d.detail.to : '') + '. Restarting&hellip;</div>';
  }
  if (d.restarting) waitForServer(box);
}

document.addEventListener('click', async e => {
  const button = e.target.closest('[data-update]');
  if (!button) return;
  if (button.dataset.update === 'apply') return applyUpdate();
  button.disabled = true;
  button.textContent = 'Checking…';
  try {
    renderUpdate(await postJSON('/api/update/check', {}));
  } catch (err) {
    button.disabled = false;
    button.textContent = 'Check now';
  }
});

document.addEventListener('change', async e => {
  if (e.target.id !== 'update-policy') return;
  renderUpdate(await postJSON('/api/update/policy', {policy: e.target.value}));
  toast('Updates', {notify: 'ELMER will tell you when one appears, and wait',
                    off: 'ELMER will not check for updates'}[e.target.value]);
});

api('/api/update').then(renderUpdate).catch(() => {});
