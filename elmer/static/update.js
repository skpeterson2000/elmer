/* The software panel: what this install is, and whether it has fallen behind.

   The page never fetches from the network itself - it reads the answer the
   background check already cached, so opening the dashboard costs nothing.
   Everything that changes the install is offered only to a browser on the
   machine itself; a phone on the LAN sees the version and nothing to press. */

function updateStatusLine(d) {
  const st = d.state, s = d.status || {};
  if (!st.checkout) {
    return ['warn', 'This copy was downloaded rather than cloned, so it has ' +
                    'no link back to where ELMER comes from and cannot update ' +
                    'itself. Run <span class="mono">./install.sh --connect</span> ' +
                    'to give it one - it asks first and overwrites nothing.'];
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
    (d.local ? '<div class="row" style="gap:.6rem;margin-top:.6rem;align-items:center">' +
        '<button class="btn sm" data-report="1">Report a problem</button>' +
        '<span class="tiny muted">Writes a file with the versions, the recent ' +
        'errors and the tail of the log &mdash; with your callsign, QTH and ' +
        'network addresses taken out. Nothing is sent until you press send.</span>' +
      '</div><div id="report-out"></div>' +
      /* Mail home: the unit's own outgoing-mail settings, and the weekly
         field report, which is off until switched on and says what it
         carries. Both local-only, like the report. */
      '<details class="derivation" id="mail-fold"><summary class="tiny muted" ' +
        'style="cursor:pointer">Mail home &mdash; reports to the project</summary>' +
        '<div id="mail-out" class="tiny muted" style="margin:.4rem 0">Loading&hellip;</div>' +
      '</details>' +
      /* The log itself, for a screen with no terminal behind it. Loaded when
         opened, warnings and errors first, because that is what somebody
         standing at a kiosk that just said "reference e-3f9a" wants. */
      '<details class="derivation" id="log-fold"><summary class="tiny muted" ' +
        'style="cursor:pointer">Recent log</summary>' +
        '<div class="row" style="gap:.5rem;margin:.4rem 0;align-items:center">' +
          '<button class="btn sm ghost" data-log="WARNING">Warnings and errors</button>' +
          '<button class="btn sm ghost" data-log="ALL">Everything recent</button>' +
          '<input id="log-ref" class="mono" placeholder="reference, e.g. e-3f9a" ' +
            'style="width:12rem;padding:.3rem .5rem;border-radius:7px;border:1px solid var(--line-2);background:var(--panel);color:var(--text)">' +
          '<button class="btn sm ghost" data-log="REF">Find it</button>' +
        '</div><pre id="log-out" class="tiny" style="max-height:18rem;overflow:auto;white-space:pre-wrap;margin:0"></pre>' +
      '</details>' : '') +
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
  // A redraw during an update - somebody pressing Check now while it runs -
  // would otherwise hand back a fresh button that looks pressable and is not.
  applyButtons(updating);
}

function updateControls(d, waiting) {
  /* Looking is automatic; applying never is. The only choice here is whether
     ELMER looks at all. */
  const options = [['notify', 'tell me'], ['off', 'never check']];
  return '<div class="row" style="gap:.6rem;margin-top:.7rem">' +
    '<button class="btn sm" data-update="check">Check now</button>' +
    '<button class="btn sm" data-selfcheck="run" ' +
      'title="run the same checks as ./elmer.py --doctor">Check this install</button>' +
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

/* The same press is offered in two places - the strip across the top and the
   panel below it - and applying replaces only the one the operator happened
   to press. Left alone the other one stays lit and still says "Update now",
   which is an invitation to press it again while the first fast-forward is
   still running. So being busy belongs to the action rather than to whichever
   button carried it, and both are told. */
function applyButtons(busy) {
  document.querySelectorAll('[data-update="apply"]').forEach(b => {
    b.disabled = busy;
    b.textContent = busy ? 'Updating…' : 'Update now';
  });
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

/* A second press before the first repaints would start a second
   fast-forward, and git's index lock turns that into a failure message about
   a running git process - which reads as ELMER breaking rather than as the
   operator pressing twice. */
let updating = false;

async function applyUpdate() {
  if (updating) return;
  updating = true;
  applyButtons(true);
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
    // Contact lost is not the same as refused: the update may well have
    // landed, so this does not offer the press again.
    box.innerHTML = '<div class="panel tight welcome">Lost contact while ' +
                    'updating. Reload the page in a moment.</div>';
    return;
  }
  const d = await res.json().catch(() => ({}));
  if (!res.ok || !d.ok) {
    // Refused, and nothing has changed - so the press comes back, because
    // holding a machine that has not moved is worse than saying no.
    updating = false;
    applyButtons(false);
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


/* Writing a report is a local action with a file as its only result. It is
   deliberately not a "send" button: what leaves this machine is the
   operator's decision, made after reading the thing. */
document.addEventListener('click', async e => {
  const btn = e.target.closest('[data-report]');
  if (!btn) return;
  const out = document.getElementById('report-out');
  btn.disabled = true;
  if (out) out.innerHTML = '<p class="tiny muted">Writing...</p>';
  try {
    const d = await api('/api/report', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({station: false}),
    });
    if (out) out.innerHTML =
      '<p class="tiny" style="margin:.5rem 0 .2rem">Written to <span class="mono">' +
        escapeHTML(d.path) + '</span>' +
        (d.redacted ? ' &mdash; callsign, QTH and network addresses removed.' : '') +
        (d.contact ? (d.mail
            ? ' <button class="btn sm" data-report-send="1">Send it to ' + escapeHTML(d.contact) + '</button>'
            : ' Send it to <span class="mono">' + escapeHTML(d.contact) +
              '</span> if you would like somebody to look at it &mdash; or set up ' +
              'mail below and the button appears here.') : '') +
        '<span id="report-sent"></span>' +
      '</p>' +
      '<details><summary class="tiny muted" style="cursor:pointer">' +
        'Read it before you send it</summary>' +
        '<pre class="tiny" style="max-height:16rem;overflow:auto;white-space:pre-wrap">' +
        escapeHTML(d.text.slice(0, 20000)) + '</pre></details>';
  } catch (err) {
    if (out) out.innerHTML = '<p class="tiny warntext">Could not write a report.</p>';
  }
  btn.disabled = false;
});

/* The press that sends: writes the report again (so what goes is what was
   just read) and mails it through the unit's own settings. */
document.addEventListener('click', async e => {
  const btn = e.target.closest('[data-report-send]');
  if (!btn) return;
  btn.disabled = true;
  const said = document.getElementById('report-sent');
  try {
    const d = await api('/api/report', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({station: false, send: true}),
    });
    if (said) said.innerHTML = d.sent
      ? ' <span style="color:var(--green)">Sent.</span>'
      : ' <span class="warntext">Not sent: ' + escapeHTML(d.detail || '') + '</span>';
  } catch (err) {
    if (said) said.innerHTML = ' <span class="warntext">Could not send.</span>';
  }
  btn.disabled = false;
});

/* ---- mail home: the outgoing-mail settings and the weekly field report */
async function renderMail() {
  const box = document.getElementById('mail-out');
  if (!box) return;
  let m, f;
  try {
    [m, f] = await Promise.all([api('/api/mail'), api('/api/fieldreport')]);
  } catch (err) { box.textContent = 'Could not read the mail settings.'; return; }
  const s = f.settings || {};
  const last = s.last_result;
  box.innerHTML =
    '<p class="tiny" style="margin:.2rem 0 .5rem;color:var(--text)">Reports go to <span class="mono">' +
      escapeHTML(m.contact) + '</span>, through your own outgoing mail server &mdash; the ' +
      'host, port and login you would give any mail program. ELMER carries no mail account; ' +
      'these are kept in <span class="mono">data/mail.json</span> on this unit only.</p>' +
    '<div class="row" style="gap:.4rem;flex-wrap:wrap;align-items:center">' +
      '<input class="mono" id="mail-host" placeholder="smtp.example.com" value="' + escapeHTML(m.host || '') + '" style="width:12rem">' +
      '<input class="mono" id="mail-port" placeholder="587" value="' + escapeHTML(m.port || '') + '" style="width:4.5rem">' +
      '<select id="mail-sec">' + ['starttls', 'ssl', 'none'].map(x =>
        '<option value="' + x + '"' + ((m.security || 'starttls') === x ? ' selected' : '') + '>' + x + '</option>').join('') + '</select>' +
      '<input class="mono" id="mail-user" placeholder="login" value="' + escapeHTML(m.user || '') + '" style="width:12rem">' +
      '<input class="mono" id="mail-pass" type="password" placeholder="' + (m.has_password ? 'password (kept)' : 'password') + '" style="width:10rem">' +
      '<input class="mono" id="mail-from" placeholder="from: you@example.com" value="' + escapeHTML(m.sender || '') + '" style="width:14rem">' +
      '<button class="btn sm" id="mail-save">Save</button>' +
      '<button class="btn sm ghost" id="mail-test"' + (m.configured ? '' : ' disabled') + '>Send a test</button>' +
      (m.configured ? '<button class="btn sm ghost" id="mail-forget">Forget</button>' : '') +
      '<span id="mail-said"></span>' +
    '</div>' +
    '<div style="margin-top:.8rem;border-top:1px solid var(--line);padding-top:.6rem">' +
      '<label class="tiny" style="display:flex;gap:.5rem;align-items:flex-start;cursor:pointer;color:var(--text)">' +
        '<input type="checkbox" id="fr-optin"' + (s.opt_in ? ' checked' : '') + ' style="margin-top:.2rem">' +
        '<span><b>Send a weekly field report.</b> ' + escapeHTML(f.what) + '</span></label>' +
      '<div class="row" style="gap:.5rem;margin-top:.5rem;align-items:center;flex-wrap:wrap">' +
        '<button class="btn sm ghost" id="fr-preview">Read what it would send</button>' +
        '<button class="btn sm ghost" id="fr-send"' + (m.configured ? '' : ' disabled') + '>Send one now</button>' +
        '<span class="tiny muted">' +
          (s.last_sent ? 'last sent ' + new Date(s.last_sent * 1000).toLocaleString() : 'none sent yet') +
          (last && !last.sent ? ' &middot; <span class="warntext">last attempt: ' + escapeHTML(last.detail || '') + '</span>' : '') +
        '</span>' +
      '</div>' +
      '<div id="fr-out"></div>' +
    '</div>';

  const said = document.getElementById('mail-said');
  document.getElementById('mail-save').onclick = async () => {
    await api('/api/mail', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({host: document.getElementById('mail-host').value,
                            port: document.getElementById('mail-port').value,
                            security: document.getElementById('mail-sec').value,
                            user: document.getElementById('mail-user').value,
                            password: document.getElementById('mail-pass').value,
                            sender: document.getElementById('mail-from').value})});
    renderMail();
  };
  document.getElementById('mail-test').onclick = async () => {
    said.textContent = 'sending…';
    const r = await api('/api/mail/test', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
    said.innerHTML = r.sent ? '<span style="color:var(--green)">sent to ' + escapeHTML(r.to) + '</span>'
                            : '<span class="warntext">' + escapeHTML(r.detail || 'not sent') + '</span>';
  };
  const forget = document.getElementById('mail-forget');
  if (forget) forget.onclick = async () => {
    if (!confirm('Forget the mail settings on this unit?')) return;
    await api('/api/mail', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({forget: true})});
    renderMail();
  };
  document.getElementById('fr-optin').onchange = async e => {
    await api('/api/fieldreport', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                   body: JSON.stringify({opt_in: e.target.checked})});
    renderMail();
  };
  const show = r => {
    const out = document.getElementById('fr-out');
    const text = (r.result && r.result.text) || (r.latest && r.latest.text) || '';
    out.innerHTML = (r.result ? '<p class="tiny" style="margin:.4rem 0 0">' +
        (r.result.sent ? '<span style="color:var(--green)">Sent.</span>'
                       : '<span class="warntext">Not sent: ' + escapeHTML(r.result.detail || '') + '</span>') +
        ' Written to <span class="mono">' + escapeHTML(r.result.path) + '</span></p>' : '') +
      '<pre class="tiny" style="max-height:18rem;overflow:auto;white-space:pre-wrap;margin-top:.4rem">' +
        escapeHTML(text.slice(0, 20000)) + '</pre>';
  };
  document.getElementById('fr-preview').onclick = async () => {
    show(await api('/api/fieldreport', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({preview: true})}));
  };
  document.getElementById('fr-send').onclick = async () => {
    show(await api('/api/fieldreport', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({send: true})}));
    renderMail();
  };
}
document.addEventListener('toggle', e => {
  if (e.target && e.target.id === 'mail-fold' && e.target.open) renderMail();
}, true);

document.addEventListener('click', async e => {
  const btn = e.target.closest('[data-log]');
  if (!btn) return;
  const out = document.getElementById('log-out');
  const mode = btn.dataset.log;
  let q = '/api/log?lines=400';
  if (mode === 'WARNING') q += '&level=WARNING';
  if (mode === 'REF') {
    const ref = (document.getElementById('log-ref').value || '').trim();
    if (!ref) { out.textContent = 'Type the reference the page showed.'; return; }
    q += '&ref=' + encodeURIComponent(ref);
  }
  out.textContent = 'Reading…';
  try {
    const d = await api(q);
    out.textContent = d.lines.length ? d.lines.join('\n')
      : (mode === 'REF' ? 'Nothing under that reference in the last 400 lines.'
                        : 'Nothing at that level in the last 400 lines.');
    out.scrollTop = out.scrollHeight;
  } catch (err) { out.textContent = 'Could not read the log from here - it is at data/elmer.log.'; }
});

/* ------------------------------------------------------------ self-check */
/* The same checks --doctor runs, for somebody who is not at a terminal - and
   on a kiosk there is no terminal to be at. It reports; it does not repair.
   Where something is wrong it says what to do about it rather than offering a
   button that claims to have done it. */

function checkRow(c) {
  const tone = c.state === 'ok' ? 'ok' : (c.state === 'warn' ? 'warn' : 'bad');
  const mark = c.state === 'ok' ? '✓' : (c.state === 'warn' ? '!' : '×');
  return '<li class="check ' + tone + '"><span class="mark">' + mark + '</span>' +
         '<b>' + escapeHTML(c.label) + '</b>' +
         (c.detail ? '<span>' + escapeHTML(c.detail) + '</span>' : '') + '</li>';
}

function renderSelfCheck(d) {
  const box = document.getElementById('selfcheck');
  if (!box) return;
  const bad = d.counts.FAIL || 0, warn = d.counts.warn || 0;
  const verdict = bad
    ? '<b class="bad">' + bad + ' fault' + (bad === 1 ? '' : 's') + ' found</b>'
    : (warn ? '<b class="warn">' + warn + ' thing' + (warn === 1 ? '' : 's') +
              ' worth a look</b>'
            : '<b class="ok">Everything checks out</b>');
  box.innerHTML =
    '<div class="panel"><div class="panel-title">Self-check</div>' +
    '<p class="tiny muted">' + verdict + ' &mdash; ' + d.checks.length +
      ' checks. This looks; it does not change anything.</p>' +
    '<ul class="checks">' + d.checks.map(checkRow).join('') + '</ul>' +
    (bad || warn
      ? '<p class="tiny muted">Anything that needs putting back is done from a ' +
        'terminal, on purpose: <span class="mono">./install.sh --repair</span> ' +
        'restores changed files from the repository, which throws those edits ' +
        'away and cannot be undone.</p>'
      : '') +
    '<div class="row" style="margin-top:.7rem">' +
      '<button class="btn sm" data-selfcheck="run">Check again</button></div>' +
    '</div>';
}

async function runSelfCheck(btn) {
  const box = document.getElementById('selfcheck');
  if (btn) { btn.disabled = true; btn.textContent = 'Checking…'; }
  else if (box) box.innerHTML = '<div class="panel"><p class="tiny muted">Checking…</p></div>';
  try {
    renderSelfCheck(await api('/api/doctor'));
  } catch (e) {
    if (box) box.innerHTML = '<div class="panel"><p class="tiny bad">' +
      'The self-check could not run. Details are in data/elmer.log.</p></div>';
  }
}

document.addEventListener('click', e => {
  const b = e.target.closest('[data-selfcheck]');
  if (b) runSelfCheck(b);
});

/* ------------------------------------------------------- other ELMERs here */
/* A unit on its own has no way of knowing the shack Pi is up, or that four
   tables are already playing. Saying so is most of the value; what to do about
   it is the rest.

   It says how many and not who. A hall with nine units in it would put nine
   names, nine addresses and nine version strings on the dashboard, and none of
   them answers the only question the operator has, which is what this unit
   should do about the others. There are three answers, and this panel is those
   three:

     Independently  run a tournament for the players in front of this unit
     Host           run a net from here for everyone who reports in
     Table          take a table under a net somebody else is running

   The tournaments themselves are named, because that is the one choice here
   that needs a name on it: Technician in this corner, General in that one,
   Extra in the next room, and a unit joining has to say which. Nothing is
   started on a neighbour's say-so - the roles are offered on this screen and
   taken by somebody pressing one. */

let peersQuiet = false;          // "not now" lasts until the page is reloaded
let peerState = {};

function peerHeadline(n) {
  return n === 1 ? 'Another ELMER is on the network.'
                 : n + ' other ELMERs are on the network.';
}

/* What is going on out there, in one line. */
function peerStanding(d) {
  const s = d.summary || {}, me = d.me || {}, nets = s.nets || [];
  if (me.hosting) {
    const u = me.units || 0;
    return 'This unit is running <b>' + escapeHTML(me.name || 'a net') + '</b>' +
      (u ? ', with ' + u + ' table' + (u === 1 ? '' : 's') + ' reporting in.' : '.');
  }
  if (me.table_of) {
    return 'This unit is a table in <b>' +
      escapeHTML(me.table_in || 'somebody else’s net') + '</b>.';
  }
  if (nets.length > 1) {
    return nets.length + ' nets are running out there. A table can only be in one.';
  }
  if (nets.length) {
    return '<b>' + escapeHTML(nets[0].name) + '</b> is running out there, and ' +
           'this unit can take a table in it.';
  }
  if (s.playing) return 'A tournament is running out there, on its own table.';
  return 'Nobody is playing. A tournament takes two minutes and somebody to start it.';
}

function netButton(n) {
  // How big it already is, inside the button: two of these sit side by side,
  // and a table count floating between them belongs to neither.
  const tables = n.units
    ? ' <span class="count">&middot; ' + n.units + ' table' +
      (n.units === 1 ? '' : 's') + '</span>' : '';
  return '<button class="btn sm" data-role="table" data-net="' +
    escapeHTML(n.url) + '">Join ' + escapeHTML(n.name) + tables + '</button>';
}

/* The picker that names a net before it is opened. Three tournaments on one
   network are told apart by their material, so it is chosen here rather than
   left until the first round. */
function hostPicker(d) {
  const opts = (d.difficulties || []).map(
    ([key, label]) => '<option value="' + escapeHTML(key) + '">' +
                      escapeHTML(label) + '</option>').join('');
  return '<span class="row" style="gap:.4rem">' +
    '<button class="btn sm primary" data-role="host">Host</button>' +
    (opts ? '<select class="btn sm" id="host-difficulty">' + opts + '</select>' : '') +
    '</span>';
}

function roleRow(head, what) {
  return '<li class="role">' + head +
         '<span class="tiny muted">' + what + '</span></li>';
}

function currentRole(what) {
  return '<span class="pill good">' + what + '</span>';
}

function renderPeers(d) {
  const box = document.getElementById('peers');
  if (!box) return;
  // The panel redraws on a timer, and a redraw that forgets which tournament
  // the operator had just picked is worse than no redraw at all.
  const picked = (document.getElementById('host-difficulty') || {}).value;
  const s = d.summary || {}, me = d.me || {}, nets = s.nets || [];
  if (peersQuiet || !s.count) { box.innerHTML = ''; return; }
  // Nothing is "current" on a unit with no tournament running on it.
  const now = me.hosting ? 'host'
            : me.table_of ? 'table'
            : me.playing_here ? 'alone' : '';

  const rows = [
    roleRow(now === 'alone' ? currentRole('Independently')
              : '<button class="btn sm" data-role="alone">Independently</button>',
            'Run a tournament on this unit for the players in front of it, and ' +
            'leave the others to themselves.' +
            (now === 'alone' ? ' <b>This is what it is doing now.</b>' : '')),
    roleRow(now === 'host' ? currentRole('Host') : hostPicker(d),
            'Run a net from here: this unit sets the question and keeps the ' +
            'leaderboard, and every unit that joins it answers the same one.' +
            (now === 'host'
              ? ' <b>This is what it is doing now.</b> ' +
                '<a href="/net">Back to net control &rarr;</a>' : '')),
    roleRow(now === 'table' ? currentRole('Table')
              : (nets.length
                  ? '<span class="row" style="gap:.4rem">' +
                    nets.map(netButton).join('') + '</span>'
                  : '<span class="pill">Table</span>'),
            'Keep this unit’s own players and its own screen, and hand the ' +
            'scores to whoever is running the net.' +
            (now === 'table' ? ' <b>This is what it is doing now.</b>'
              : nets.length ? ''
              : ' <b>Nothing to join yet</b> — a table becomes possible the ' +
                'moment one of them opens a net.')),
  ];

  box.innerHTML =
    '<div class="panel"><div class="panel-title">' + peerHeadline(s.count) + '</div>' +
    '<p class="tiny">' + peerStanding(d) +
      (s.with_fix ? ' One of them has a GPS fix, which this unit will use if it ' +
                    'has none of its own.' : '') +
    '</p>' +
    '<p class="tiny muted">A tournament here can be run three ways:</p>' +
    '<ul class="roles">' + rows.join('') + '</ul>' +
    '<div class="row" style="gap:.5rem;margin-top:.6rem">' +
      '<a class="btn sm ghost" href="/net/board">Big board</a>' +
      '<button class="btn sm ghost" data-peers="hide">Not now</button>' +
    '</div></div>';

  const pick = document.getElementById('host-difficulty');
  if (pick && picked) pick.value = picked;
}

/* Taking a role. Each one is this unit's own decision about itself: nothing
   here reaches out and changes what a neighbour is doing. */
async function takeRole(role, netUrl) {
  if (role === 'host') {
    const pick = document.getElementById('host-difficulty');
    location.href = '/net' + (pick ? '?difficulty=' + encodeURIComponent(pick.value) : '');
    return;
  }
  const me = peerState.me || {};
  // Going independent while running a hall closes the net under everybody in
  // it. A tournament other people are in is not something to end on one
  // mis-aimed press.
  if (role === 'alone' && me.hosting &&
      !confirm('Close the net? Tables in it will find it gone and carry on ' +
               'by themselves.')) return;
  try {
    if (role === 'alone') {
      await postJSON('/api/party/net', { join: false });
      await postJSON('/api/net/end', {});
    } else if (role === 'table') {
      if (!netUrl) return;
      await postJSON('/api/party/net', { url: netUrl });
    }
  } catch (e) { return; }               // api() has already said so on screen
  location.href = '/party/1';
}

async function pollPeers() {
  try {
    peerState = await api('/api/peers');
    renderPeers(peerState);
  } catch (e) { /* quiet */ }
}

document.addEventListener('click', e => {
  if (e.target.closest('[data-peers="hide"]')) {
    peersQuiet = true;
    const box = document.getElementById('peers');
    if (box) box.innerHTML = '';
    return;
  }
  const b = e.target.closest('[data-role]');
  if (b) takeRole(b.getAttribute('data-role'), b.getAttribute('data-net'));
});

pollPeers();
setInterval(pollPeers, 20000);
