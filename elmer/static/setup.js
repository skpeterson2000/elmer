/* The gear: the things somebody is asked once, gathered where they can be
   found again.
 *
 * None of this is new ground - the callsign is on the Band Plan, the QTH is on
 * the map, the name is in the account menu - and all of that stays where it
 * is, because that is where each one is wanted in the moment. What was missing
 * was a way back to them for somebody who said "later" the first time and then
 * could not remember which page had asked. A gear in the corner is where
 * everybody already looks for that.
 *
 * Each field saves through the same endpoint the page it came from uses, so
 * there is one way of setting a callsign rather than two that can disagree.
 */
(function () {
  const dlg = document.getElementById('setup');
  const gear = document.getElementById('gear-btn');
  if (!dlg || !gear) return;

  const said = document.getElementById('setup-said');
  const nameBox = document.getElementById('setup-name');
  const callBox = document.getElementById('setup-call');
  const classBox = document.getElementById('setup-class');
  const qthBox = document.getElementById('setup-qth');

  let picked = null;                      // a QTH chosen in this sitting
  let place = null;
  let me = null;                          // this account, for the name

  function say(text, bad) {
    said.textContent = text || '';
    said.style.color = bad ? 'var(--red)' : 'var(--dim)';
  }

  gear.addEventListener('click', async () => {
    say('');
    // Asked for here rather than read off the account menu, which fills its
    // list only when somebody opens it - and most people opening this will
    // never have opened that.
    try {
      const who = await api('/api/users');
      me = (who.users || []).find(u => u.id === who.current) || null;
    } catch (err) {
      me = null;                          // the name field simply will not save
    }
    if (!place) {
      // The picker is the one every other page uses, wired the first time the
      // dialog opens - before that the fields are not on screen to wire.
      place = initPlace('setup-qth', {onPick: p => { picked = p; }});
    }
    if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.show();
    nameBox.focus();
  });

  document.getElementById('setup-here').addEventListener('click', async e => {
    const btn = e.currentTarget;
    btn.disabled = true;
    const was = btn.textContent;
    btn.textContent = 'Looking…';
    try {
      const fix = await locateMe();
      picked = {lat: fix.lat, lon: fix.lon,
                grid: fix.grid || latLonToGrid(fix.lat, fix.lon),
                name: 'Here', short: 'Here', kind: 'fix'};
      document.getElementById('setup-qth-hint').innerHTML =
        '<b>Here</b> &middot; ' + escapeHTML(picked.grid) + ' &middot; ' +
        picked.lat.toFixed(4) + ', ' + picked.lon.toFixed(4);
      qthBox.value = '';
      say('position taken - press Save to keep it');
    } catch (err) {
      say(err.reason || err.message || 'no position available', true);
    } finally {
      btn.disabled = false;
      btn.textContent = was;
    }
  });

  document.getElementById('setup-save').addEventListener('click', async e => {
    const btn = e.currentTarget;
    btn.disabled = true;
    say('saving…');
    const trouble = [];
    try {
      // The name lives with the account rather than the settings, and a locked
      // account wants its password before it will answer to a new one.
      const wanted = nameBox.value.trim();
      const mine = me;
      if (wanted && mine && wanted !== (mine.name || mine.display_name)) {
        let password = '';
        if (mine.locked && typeof askPassword === 'function') {
          password = await askPassword(
            {title: 'Rename', label: 'Password for this account'}) || '';
          if (!password) throw new Error('the name needs the password');
        }
        await postJSON('/api/users/rename',
                       {id: mine.id, name: wanted, password: password})
          .catch(() => trouble.push('name'));
      }

      const body = {};
      body.callsign = callBox.value.trim().toUpperCase();
      body.license_class = classBox.value;
      if (picked) body.location = picked;
      await postJSON('/api/settings', body);

      if (trouble.length) {
        say('saved, except the ' + trouble.join(' and '), true);
        btn.disabled = false;
        return;
      }
      say('saved');
      // The top bar carries the name, the callsign and the rank, so it is
      // wrong until the page comes back.
      setTimeout(() => location.reload(), 400);
    } catch (err) {
      say(err.message || 'could not save', true);
      btn.disabled = false;
    }
  });
})();
