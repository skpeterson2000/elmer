/* Who is playing.

   One ELMER in a house gets shared the way a radio does, so the top bar names
   whoever is at it and switching is one press. There is nothing to log into:
   picking a name is a choice, not a sign-in. Removing somebody is the one thing
   that needs to be done at the unit itself, because it destroys their work. */

let whoData = null;

const WHO_GAP = 8;          // between the chip and the menu below it

/* Put the menu under the chip and wholly on the screen.

   The top bar wraps, so the chip is not always in the same place - on a narrow
   window it can sit near the left edge, and a menu hung off its right edge went
   off the side of the screen with nothing readable left. So it is measured and
   clamped every time it opens, rather than trusted to a fixed corner. */
function placeWhoMenu() {
  const menu = document.getElementById('who-menu');
  const button = document.getElementById('who-btn');
  if (!menu || !button || menu.hidden) return;
  const chip = button.getBoundingClientRect();
  const width = menu.offsetWidth;
  const margin = 8;
  let left = chip.right - width;                       // right edges aligned
  left = Math.min(left, window.innerWidth - width - margin);
  left = Math.max(margin, left);
  let top = chip.bottom + WHO_GAP;
  const height = menu.offsetHeight;
  if (top + height > window.innerHeight - margin) {
    // No room below - sit above the chip instead, and failing that, as high
    // as it can while staying under the top of the window.
    top = Math.max(margin, Math.min(chip.top - WHO_GAP - height,
                                    window.innerHeight - height - margin));
  }
  menu.style.left = Math.round(left) + 'px';
  menu.style.top = Math.round(top) + 'px';
}

function openWhoMenu(open) {
  const menu = document.getElementById('who-menu');
  if (!menu) return;
  menu.hidden = !open;
  if (open) placeWhoMenu();
}

window.addEventListener('resize', placeWhoMenu);
window.addEventListener('scroll', placeWhoMenu, {passive: true});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') openWhoMenu(false);
});

function whoRow(u, current) {
  return '<button class="who-row' + (u.id === current ? ' on' : '') + '" ' +
         'data-user="' + u.id + '">' +
    '<span class="who-row-name">' + escapeHTML(u.display_name) + '</span>' +
    (u.licensed ? '<span class="pill info tiny">licensed</span>' : '') +
    (u.id === current ? '<span class="tiny muted">playing</span>' : '') +
    '</button>';
}

function renderWho(d) {
  whoData = d;
  const menu = document.getElementById('who-menu');
  const name = document.querySelector('.who-name');
  const mark = document.querySelector('.who-mark');
  if (name) name.textContent = d.display_name;
  if (mark) mark.textContent = d.display_name.slice(0, 2).toUpperCase();
  if (!menu) return;

  const me = d.users.find(u => u.id === d.current) || {};
  const wasOpen = !menu.hidden;
  menu.innerHTML =
    '<div class="who-head">Who is at the radio?</div>' +
    d.users.map(u => whoRow(u, d.current)).join('') +
    '<div class="who-sep"></div>' +
    '<form class="who-add" id="who-add">' +
      '<input name="name" placeholder="name" maxlength="40" required>' +
      '<input name="callsign" placeholder="callsign (if any)" maxlength="10" class="mono">' +
      '<button class="btn sm primary" type="submit">Add</button>' +
    '</form>' +
    '<div class="tiny muted who-note">A callsign here means ELMER calls you by ' +
      'it instead of your name. You can add one later from the band plan.</div>' +
    '<div class="who-sep"></div>' +
    '<div class="who-actions">' +
      '<button class="btn sm ghost" data-who="rename">Rename ' +
        escapeHTML(me.name || me.display_name || 'this user') + '</button>' +
      (d.local && d.users.length > 1
        ? '<button class="btn sm ghost danger" data-who="remove">Remove&hellip;</button>'
        : '') +
    '</div>';
  if (wasOpen) placeWhoMenu();          // its height just changed
}

async function switchUser(id) {
  renderWho(await postJSON('/api/users/switch', {id: id}));
  location.reload();          // every number on the page belongs to somebody
}

document.addEventListener('click', async e => {
  const toggle = e.target.closest('#who-btn');
  const menu = document.getElementById('who-menu');
  if (!menu) return;
  if (toggle) {
    if (!menu.hidden) { openWhoMenu(false); return; }
    if (!whoData) renderWho(await api('/api/users'));
    openWhoMenu(true);          // measured once it has something in it
    return;
  }
  const row = e.target.closest('.who-row');
  if (row) {
    const id = +row.dataset.user;
    if (whoData && id === whoData.current) { openWhoMenu(false); return; }
    return switchUser(id);
  }
  const action = e.target.closest('[data-who]');
  if (action) {
    if (action.dataset.who === 'rename') {
      const me = whoData.users.find(u => u.id === whoData.current) || {};
      const name = prompt('What should ELMER call you?', me.name || '');
      if (name) renderWho(await postJSON('/api/users/rename', {name: name}));
      return;
    }
    if (action.dataset.who === 'remove') {
      const me = whoData.users.find(u => u.id === whoData.current) || {};
      if (!confirm('Remove ' + me.display_name + ' from this ELMER?\n\n' +
                   'Their progress, titles, notes and streak go with them, ' +
                   'and it cannot be undone.')) return;
      const res = await fetch('/api/users/remove', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: me.id})});
      const d = await res.json().catch(() => ({}));
      if (!res.ok) { alert(d.message || 'Could not remove that user.'); return; }
      location.reload();
      return;
    }
  }
  if (!menu.hidden && !e.target.closest('.who')) openWhoMenu(false);
});

document.addEventListener('submit', async e => {
  if (e.target.id !== 'who-add') return;
  e.preventDefault();
  const form = e.target;
  const body = {name: form.name.value, callsign: form.callsign.value};
  const res = await fetch('/api/users/add', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)});
  const d = await res.json().catch(() => ({}));
  if (!res.ok) { alert(d.message || 'Could not add that user.'); return; }
  location.reload();
});

/* ---------- the shack: everyone on this unit, side by side ---------- */

function renderShack(d) {
  const panel = document.getElementById('shack');
  if (!panel) return;
  const board = d.board || [];
  if (board.length < 2) return;        // a scoreboard of one is just a mirror
  panel.hidden = false;
  panel.innerHTML =
    '<div class="panel-title">The shack &mdash; everyone on this unit</div>' +
    '<table class="data shack"><thead><tr>' +
      '<th>Who</th><th>Amateur</th><th>Commercial</th>' +
      '<th class="num">This week</th><th class="num">Answered</th>' +
      '<th class="num">Right</th><th class="num">Streak</th><th class="num">XP</th>' +
    '</tr></thead><tbody>' +
    board.map(r =>
      '<tr' + (r.is_you ? ' class="you"' : '') + '>' +
        '<td><b>' + escapeHTML(r.name) + '</b>' +
          (r.licensed ? ' <span class="pill info tiny">licensed</span>' : '') +
          (r.is_you ? ' <span class="tiny muted">you</span>' : '') + '</td>' +
        '<td class="small">' + escapeHTML(r.titles.amateur || '&mdash;') + '</td>' +
        '<td class="small">' + escapeHTML(r.titles.commercial || '&mdash;') + '</td>' +
        '<td class="num mono">' + r.week + '</td>' +
        '<td class="num mono">' + r.answered + '</td>' +
        '<td class="num mono">' + (r.answered ? pct(r.accuracy) : '&mdash;') + '</td>' +
        '<td class="num mono">' + r.streak + 'd</td>' +
        '<td class="num mono">' + r.xp.toLocaleString() + '</td>' +
      '</tr>').join('') +
    '</tbody></table>' +
    '<p class="tiny muted" style="margin:.6rem 0 0">Sorted by questions answered ' +
      'this week, because that is the thing anybody can do something about today.</p>';
}

if (document.getElementById('shack')) {
  api('/api/scoreboard').then(renderShack).catch(() => {});
}

/* "Open every pool anyway" - the gate is a kindness to a beginner, not a
   ruling about what a licensed operator may read. */
document.addEventListener('click', async e => {
  const btn = e.target.closest('[data-open-pools]');
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = 'Opening…';
  try {
    await postJSON('/api/pool-gate', {open: true});
    location.reload();
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Open every pool anyway';
  }
});
