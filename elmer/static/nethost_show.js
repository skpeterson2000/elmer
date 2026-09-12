/* The host's hand on every screen: the show controls on the net control page.

   Everything here talks to /api/net/show and its verbs; the tables learn of
   it on their next check-in, within the second. The page polls the show once
   a second alongside the board, so a notice that has timed out disappears
   from the pending list as it disappears from the room. */

(() => {
  const $ = id => document.getElementById(id);
  const esc = s => { const d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; };
  async function post(path, body) {
    const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
                                 body: JSON.stringify(body || {})});
    return {ok: r.ok, data: await r.json().catch(() => ({}))};
  }

  const DECK_WORDS = {history: 'history', quotes: 'quotes', hams: 'famous hams', technique: 'on the air',
                      equipment: 'the gear', standings: 'standings', sponsor: 'sponsors', notice: 'notices',
                      join: 'join code', programme: 'programme'};
  let view = null;

  /* ---------------------------------------------------------- announce */
  $('sh-send').addEventListener('click', async () => {
    const text = $('sh-text').value.trim();
    if (!text) { $('sh-text').focus(); return; }
    const target = $('sh-target').value;               // "" | unit | unit|seat
    const [unit, seat] = target ? target.split('|') : ['', ''];
    const w = $('sh-weight').value;
    const body = {text, unit: unit || null, seat: seat || null,
                  weight: w === 'notice' ? 'notice' : 'urgent'};
    if (w === 'repeat') { body.repeat = 60; body.seconds = 20; }
    const r = await post('/api/net/announce', body);
    if (r.ok) { $('sh-text').value = ''; refresh(); }
  });
  $('sh-text').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('sh-send').click(); }
  });
  $('sh-attention').addEventListener('click', async () => {
    const held = view && view.attention;
    if (held) { await post('/api/net/attention', {release: true}); }
    else {
      const text = $('sh-text').value.trim();
      await post('/api/net/attention', {text: text || 'One moment - eyes up front.'});
    }
    refresh();
  });

  function paintPending(v) {
    const box = $('sh-pending');
    const items = v.announcements || [];
    box.innerHTML = items.length
      ? items.map(a => `<div class="ann ${a.weight}${a.showing ? '' : ' off'}">
          <span class="to">${a.seat ? 'seat ' + esc(a.seat) : (a.unit ? 'table' : 'all')}${a.repeat ? ' · every ' + Math.round(a.repeat) + 's' : ''}</span>
          <span>${esc(a.text)}</span>
          <button class="x" data-clear="${a.id}" title="clear">&times;</button></div>`).join('') +
        (items.length > 1 ? '<div><button class="btn sm ghost" data-clear="all">Clear all</button></div>' : '')
      : '';
    $('sh-attention').textContent = v.attention ? '✋ Release the room' : '✋ Attention';
    $('sh-attention').classList.toggle('primary', !!v.attention);
  }
  $('sh-pending').addEventListener('click', async e => {
    const b = e.target.closest('[data-clear]');
    if (!b) return;
    await post('/api/net/announce/clear', b.dataset.clear === 'all' ? {all: true} : {id: +b.dataset.clear});
    refresh();
  });

  function paintTargets(v) {
    const sel = $('sh-target');
    const keep = sel.value;
    const units = (v.units || []).filter(u => !u.simulated);
    let html = '<option value="">Everyone</option>';
    units.forEach(u => {
      html += `<optgroup label="${esc(u.name)}"><option value="${esc(u.id)}|">the whole table</option>` +
        ((v.seats || {})[u.id] || []).map(n => `<option value="${esc(u.id)}|${esc(n)}">${esc(n)}</option>`).join('') +
        '</optgroup>';
    });
    if (sel.innerHTML !== html) { sel.innerHTML = html; sel.value = keep; }
  }

  /* -------------------------------------------------------------- mode */
  $('sh-modes').addEventListener('click', async e => {
    const b = e.target.closest('[data-mode]');
    if (!b) return;
    // Playing starts the hall conducting on the difficulty and clock the
    // round controls show; the other two stop it and score an open question.
    await post('/api/net/show/mode', {mode: b.dataset.mode,
      difficulty: document.getElementById('difficulty').value,
      seconds: parseFloat(document.getElementById('seconds').value) || null});
    refresh();
  });
  function paintConducting(v) {
    const c = v.conducting;
    const b = document.querySelector('#sh-modes [data-mode="play"]');
    b.textContent = c && c.running
      ? 'Playing \u00b7 ' + (c.state === 'waiting' ? (c.waiting_for || 'waiting') : c.state)
      : 'Playing';
  }

  /* -------------------------------------------------------------- deck */
  function paintDeck(v) {
    const box = $('sh-deck');
    const keys = [...(v.decks || []), ...(v.kinds || [])];
    const html = keys.map(k => `<label class="${v.deck[k] ? 'on' : ''}"><input type="checkbox" data-deck="${k}" ${v.deck[k] ? 'checked' : ''}>${esc(DECK_WORDS[k] || k)}</label>`).join('');
    if (box.dataset.html !== html) { box.dataset.html = html; box.innerHTML = html; }
    if (document.activeElement !== $('sh-dwell')) $('sh-dwell').value = Math.round(v.dwell || 12);
    const card = v.card;
    $('sh-seeing').textContent = v.attention ? 'every table is held on your message'
      : card ? 'the room is seeing: ' + (card.kind === 'trivia' ? (DECK_WORDS[card.deck] || card.deck) + ' - ' + (card.text || '').slice(0, 60) + '…'
                                       : card.kind + (card.name ? ' - ' + card.name : card.title ? ' - ' + card.title : ''))
      : (v.round_open ? 'a question is up' : v.mode === 'play' ? 'playing' : 'nothing between rounds - turn a deck on');
  }
  $('sh-deck').addEventListener('change', async e => {
    const cb = e.target.closest('[data-deck]');
    if (!cb) return;
    await post('/api/net/deck', {deck: {[cb.dataset.deck]: cb.checked}});
    refresh();
  });
  $('sh-dwell').addEventListener('change', async () => {
    await post('/api/net/deck', {dwell: parseFloat($('sh-dwell').value) || 12});
    refresh();
  });

  /* ------------------------------------------------------------- focus */
  $('sh-focus').addEventListener('click', async () => {
    await post('/api/net/focus', {section: $('sh-section').value.trim(),
                                  minutes: parseFloat($('sh-minutes').value) || null,
                                  text: $('sh-focus-text').value.trim()});
    refresh();
  });
  $('sh-unfocus').addEventListener('click', async () => { await post('/api/net/focus', {clear: true}); refresh(); });

  function paintWeak(v) {
    const box = $('sh-weak');
    box.className = 'small weak';
    const weak = v.weak || [];
    const f = v.focus;
    box.innerHTML =
      (f ? `<div style="margin-bottom:.3rem">Focus: <b style="color:var(--amber)">${esc(f.section || '')} ${esc(f.title || '')}</b>` +
           (f.remaining != null ? ` · ${Math.ceil(f.remaining / 60)} min left` : '') + '</div>' : '') +
      (weak.length
        ? 'Tonight the room is missing most on: ' + weak.map(w =>
            `<span class="w">${esc(w.section)} <b>${Math.round(w.miss * 100)}%</b> <span style="color:var(--dim)">of ${w.answers}</span>
               <button data-focus="${esc(w.section)}" title="${esc(w.title)}">focus</button>
               <button data-ask="${esc(w.section)}">ask one</button></span>`).join('')
        : '<span style="color:var(--dimmer)">No section has enough answers yet to call weak.</span>');
  }
  $('sh-weak').addEventListener('click', async e => {
    const f = e.target.closest('[data-focus]'), a = e.target.closest('[data-ask]');
    if (f) { $('sh-section').value = f.dataset.focus; $('sh-focus').click(); }
    if (a) {
      await post('/api/net/round', {difficulty: view && view.difficulty, section: a.dataset.ask,
                                    seconds: parseFloat(document.getElementById('seconds').value) || 30});
    }
  });

  /* ------------------------------------------------ sponsors and notices */
  function paintItems(v) {
    $('sh-sponsors').innerHTML = (v.sponsors || []).length
      ? v.sponsors.map(s => `<div class="it">${s.file ? `<img src="/api/net/asset/${encodeURIComponent(s.file)}" alt="">` : ''}
          <b>${esc(s.name)}</b> <span style="color:var(--dim)">${esc(s.blurb || '')}</span>
          ${s.weight > 1 ? `<span class="small" style="color:var(--dimmer)">×${s.weight}</span>` : ''}
          <button class="x" data-sponsor="${s.id}" title="remove">&times;</button></div>`).join('')
      : '<div class="empty">none yet</div>';
    $('sh-notices').innerHTML = (v.notices || []).length
      ? v.notices.map(n => `<div class="it"><b>${esc(n.title)}</b> <span style="color:var(--dim)">${esc(n.text || '')}</span>
          <button class="x" data-notice="${n.id}" title="remove">&times;</button></div>`).join('')
      : '<div class="empty">none yet</div>';
  }
  $('sh-sponsors').addEventListener('click', async e => {
    const b = e.target.closest('[data-sponsor]');
    if (b && confirm('Remove this sponsor’s card?')) { await post('/api/net/sponsor', {remove: +b.dataset.sponsor}); refresh(); }
  });
  $('sh-notices').addEventListener('click', async e => {
    const b = e.target.closest('[data-notice]');
    if (b) { await post('/api/net/notice', {remove: +b.dataset.notice}); refresh(); }
  });
  $('sh-sponsor-form').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    const r = await fetch('/api/net/sponsor', {method: 'POST', body: fd});
    if (r.ok) { form.reset(); refresh(); }
    else { const d = await r.json().catch(() => ({})); alert(d.message || d.error || 'Could not add the sponsor.'); }
  });
  $('sh-notice-form').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.target, fd = new FormData(form);
    const r = await post('/api/net/notice', {title: fd.get('title'), text: fd.get('text'), url: fd.get('url')});
    if (r.ok) { form.reset(); refresh(); }
  });

  /* --------------------------------------------------------- programme */
  let steps = null;                    // the host's working copy
  function paintProgramme(v) {
    const kinds = v.step_kinds || {};
    const sel = $('sh-step-kind');
    if (!sel.options.length) {
      sel.innerHTML = Object.entries(kinds).map(([k, label]) => `<option value="${k}">${esc(label)}</option>`).join('');
    }
    if (steps === null) steps = (v.steps || []).map(s => ({...s}));
    const p = v.programme || {};
    $('sh-steps').innerHTML = steps.map((s, i) => {
      const n = i + 1;
      const cls = n === p.step ? 'now' : (n < p.step ? 'done' : '');
      const detail = [s.rounds ? s.rounds + ' rounds' : '', s.minutes ? s.minutes + ' min' : '',
                      s.difficulty || '', s.section || '', s.text ? '“' + s.text + '”' : ''].filter(Boolean).join(' · ');
      return `<li class="${cls}"><span>${esc(s.label)}${detail ? ` <span style="color:var(--dim)">${esc(detail)}</span>` : ''}</span>
        <button class="x" data-step="${i}" title="remove">&times;</button></li>`;
    }).join('') || '<li class="empty" style="list-style:none;margin-left:-1.4rem">No programme yet - add steps, or fill in a club evening.</li>';
    $('sh-prog-now').textContent = p.of
      ? (p.now ? `Now: ${p.now}` + (p.next ? ` · next: ${p.next}` : ' · last step') : `${p.of} steps, not started`)
      : '';
    $('sh-next').disabled = !steps.length;
  }
  async function saveProgramme() {
    await post('/api/net/programme', {steps});
    steps = null;
    refresh();
  }
  $('sh-step-add').addEventListener('click', () => {
    const kind = $('sh-step-kind').value, n = parseFloat($('sh-step-n').value), text = $('sh-step-text').value.trim();
    const step = {kind};
    if (kind === 'rounds') { if (n) step.rounds = n; step.difficulty = document.getElementById('difficulty').value; }
    if (kind === 'intermission' && n) step.minutes = n;
    if (kind === 'study') { step.section = text.toUpperCase(); if (n) step.minutes = n; }
    else if (text) step.text = text;
    steps = steps || [];
    steps.push(step);
    $('sh-step-text').value = ''; $('sh-step-n').value = '';
    saveProgramme();
  });
  $('sh-steps').addEventListener('click', e => {
    const b = e.target.closest('[data-step]');
    if (!b) return;
    steps.splice(+b.dataset.step, 1);
    saveProgramme();
  });
  $('sh-prog-club').addEventListener('click', () => {
    const d = document.getElementById('difficulty').value;
    steps = [
      {kind: 'intermission', minutes: 5, text: 'Welcome - find a table and scan its code.'},
      {kind: 'rounds', rounds: 12, difficulty: d},
      {kind: 'study', section: '', minutes: 10, text: 'Ten minutes on what the room missed.'},
      {kind: 'rounds', rounds: 12, difficulty: d},
      {kind: 'announce', text: 'Club membership and coming events - see the notices on screen.'},
      {kind: 'shootout', difficulty: d},
      {kind: 'certificates'},
      {kind: 'thanks'},
    ];
    saveProgramme();
  });
  $('sh-prog-clear').addEventListener('click', () => { steps = []; saveProgramme(); });
  $('sh-next').addEventListener('click', async () => {
    const r = await post('/api/net/programme/next', {});
    if (!r.ok) alert(r.data.message || r.data.error || 'Could not step the programme.');
    refresh();
  });

  /* -------------------------------------------------------------- poll */
  async function refresh() {
    let r;
    try { r = await fetch('/api/net/show'); } catch (e) { return; }
    if (!r.ok) return;
    view = await r.json();
    document.querySelectorAll('#sh-modes [data-mode]').forEach(b => b.classList.toggle('on', b.dataset.mode === view.mode));
    paintConducting(view);
    paintPending(view);
    paintTargets(view);
    paintDeck(view);
    paintWeak(view);
    paintItems(view);
    paintProgramme(view);
  }
  refresh();
  setInterval(refresh, 1000);
})();
