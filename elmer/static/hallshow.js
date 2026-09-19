/* The hall's show, drawn the same way on every screen.

   Net control decides what the room sees between questions - a trivia card,
   a sponsor, the standings, the club's notice, a study focus - and what the
   host has to say to it. The table screen, the phones and the board all
   receive the same `show` object and draw it with these, so a card looks the
   same on a phone in the back row as on the board at the front, and an
   announcement is one thing said in one voice.

   Nothing here fetches anything but a sponsor's image, and that from the
   master unit's own address. */

(function () {
  const esc = s => { const d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; };

  const DECK_WORDS = {history: 'A little history', quotes: 'In their words', hams: 'Famous hams',
                      technique: 'On the air', equipment: 'The gear'};

  /* One card, as HTML. `opts.master` is where sponsor images live; `opts.join`
     is the HTML for this unit's own join panel, for the join card; `opts.small`
     draws for a phone. */
  function cardHTML(card, opts) {
    opts = opts || {};
    if (!card) return '';
    const k = card.kind;
    if (k === 'trivia') {
      return `<div class="hs-card hs-trivia">
        <div class="hs-kicker">${esc(DECK_WORDS[card.deck] || card.deck || 'Did you know')}</div>
        <p class="hs-text">${esc(card.text)}</p>
        ${card.about ? `<div class="hs-about">${esc(card.about)}</div>` : ''}
      </div>`;
    }
    if (k === 'sponsor') {
      const img = card.file && opts.master
        ? `<img class="hs-sponsor-img" src="${esc(opts.master)}/api/net/asset/${encodeURIComponent(card.file)}" alt="">`
        : '';
      return `<div class="hs-card hs-sponsor">
        <div class="hs-kicker">Presented with thanks to</div>
        ${img}
        <div class="hs-sponsor-name">${esc(card.name)}</div>
        ${card.blurb ? `<p class="hs-text hs-blurb">${esc(card.blurb)}</p>` : ''}
        ${card.url ? `<div class="hs-about">${esc(card.url)}</div>` : ''}
      </div>`;
    }
    if (k === 'house' && card.honour) {
      /* The honorary card: this table's unit is a supporter's, and ELMER's
         own card becomes theirs for the dwell. */
      return `<div class="hs-card hs-sponsor">
        <div class="hs-kicker">With thanks</div>
        <div class="hs-sponsor-name">${esc(card.honour)}</div>
        <p class="hs-text">${esc(card.text)}</p>
        <div class="hs-about">${esc(card.name)} &middot; ${esc(card.url)}</div>
      </div>`;
    }
    if (k === 'thanks') {
      /* The roll: the evening's sponsors and the supporters in the room. */
      const names = [...(card.sponsors || []), ...(card.supporters || [])];
      const shown = names.slice(0, 8);
      return `<div class="hs-card hs-sponsor">
        <div class="hs-kicker">With thanks to</div>
        <div class="hs-sponsor-name">${esc(shown.join(' \u00b7 '))}</div>
        ${names.length > shown.length ? `<div class="hs-about" style="text-align:center">and ${names.length - shown.length} more</div>` : ''}
        <p class="hs-text hs-blurb">${(card.sponsors || []).length ? 'The evening&rsquo;s sponsors, and ' : ''}the people whose cup of coffee keeps ELMER free for the community.</p>
      </div>`;
    }
    if (k === 'house') {
      /* ELMER's own card: the icon, one line, where to find it. */
      const img = card.image
        ? `<img class="hs-house-img" src="${esc((opts.master || '') + card.image)}" alt="ELMER">` : '';
      return `<div class="hs-card hs-house">
        <div class="hs-kicker">This is</div>
        <div class="hs-house-row">${img}<div>
          <div class="hs-sponsor-name" style="text-align:left">${esc(card.name)}</div>
          <p class="hs-text">${esc(card.text)}</p>
          ${card.url ? `<div class="hs-about">${esc(card.url)} &middot; free for noncommercial use</div>` : ''}
        </div></div>
      </div>`;
    }
    if (k === 'notice') {
      return `<div class="hs-card hs-notice">
        <div class="hs-kicker">Notice</div>
        <div class="hs-title">${esc(card.title)}</div>
        ${card.text ? `<p class="hs-text">${esc(card.text)}</p>` : ''}
        ${card.url ? `<div class="hs-about">${esc(card.url)}</div>` : ''}
      </div>`;
    }
    if (k === 'standings') {
      const rows = (card.rows || []);
      return `<div class="hs-card hs-standings">
        <div class="hs-kicker">Standings</div>
        ${rows.length ? `<table class="hs-table">${rows.map((r, i) =>
          `<tr><td class="hs-n">${i + 1}</td><td>${esc(r.name)}</td>
               <td class="hs-pts">${r.score}${r.gained ? `<span class="hs-gain">+${r.gained}</span>` : ''}</td></tr>`).join('')}</table>`
          : '<p class="hs-text">No points on the board yet.</p>'}
      </div>`;
    }
    if (k === 'join') {
      return `<div class="hs-card hs-join">
        <div class="hs-kicker">Walk up and play</div>
        ${opts.join || '<p class="hs-text">Scan the code on any table to join.</p>'}
      </div>`;
    }
    if (k === 'programme') {
      return `<div class="hs-card hs-programme">
        <div class="hs-kicker">Tonight</div>
        <ol class="hs-steps">${(card.steps || []).map((s, i) =>
          `<li class="${i + 1 === card.step ? 'now' : (i + 1 < card.step ? 'done' : '')}">${esc(s)}</li>`).join('')}</ol>
        ${card.next ? `<div class="hs-about">Next: ${esc(card.next)}</div>` : ''}
      </div>`;
    }
    if (k === 'focus') {
      const f = card.focus || {};
      return `<div class="hs-card hs-focus">
        <div class="hs-kicker">Study</div>
        <div class="hs-title">${f.section ? esc(f.section) + ' &mdash; ' : ''}${esc(f.title || '')}</div>
        ${f.text ? `<p class="hs-text">${esc(f.text)}</p>` : ''}
        ${f.remaining != null ? `<div class="hs-about">${Math.ceil(f.remaining / 60)} min left</div>` : ''}
      </div>`;
    }
    return '';
  }

  /* The word a screen sends up with its check-in, so the host can see the
     room: what this screen is showing right now. */
  function showingWord(card) { return card ? 'card:' + card.kind : 'idle'; }

  /* The clocks: the programme step's, small in the corner, and the run-up
     to a question, over everything.

     Both arrive as seconds remaining, read on the master and carried to
     this screen a poll or two later - so a reading is always a little
     stale, and by an amount that varies. Each reading is turned into a
     deadline on this screen's own clock and the earliest deadline seen for
     the same countdown is kept, because staleness only ever makes a reading
     read long. Then the words are drawn from the local clock every tenth of
     a second, so three, two, one land on the second and not on the poll.

     The run-up is the same five seconds on every screen in the room, and it
     is why they are there: a question that appears from nowhere after ten
     minutes of intermission has gone to whoever happened to be looking, and
     "my time was taken" is a fair complaint. "Get ready" until three seconds
     are left, then three, two, one. */
  const clocks = {stepKey: null, stepAt: 0, leadKey: null, leadAt: 0, timer: null};

  function mmss(sec) {
    sec = Math.max(0, Math.ceil(sec));
    const m = Math.floor(sec / 60), s = sec % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  function take(show) {
    const p = show && show.programme;
    if (p && p.remaining != null && show.mode !== 'play') {
      const key = 'step' + p.step;
      const at = performance.now() + p.remaining * 1000;
      if (clocks.stepKey !== key || at < clocks.stepAt) { clocks.stepKey = key; clocks.stepAt = at; }
      clocks.stepWord = p.kind === 'study' ? 'Study' : (p.now || 'Intermission');
    } else {
      clocks.stepKey = null;
    }
    const li = show && show.lead_in;
    if (li && li.remaining != null) {
      const key = 'lead' + li.at;
      const at = performance.now() + li.remaining * 1000;
      if (clocks.leadKey !== key || at < clocks.leadAt) { clocks.leadKey = key; clocks.leadAt = at; }
      clocks.leadWord = li.first ? 'Game starts in' : 'Next round in';
    } else {
      clocks.leadKey = null;
    }
    const want = !!(clocks.stepKey || clocks.leadKey);
    if (want && !clocks.timer) clocks.timer = setInterval(drawClocks, 100);
    if (!want && clocks.timer) { clearInterval(clocks.timer); clocks.timer = null; }
    drawClocks();
  }

  function drawClocks() {
    let clock = document.getElementById('hs-clock');
    if (!clock) {
      clock = document.createElement('div');
      clock.id = 'hs-clock';
      document.body.appendChild(clock);
    }
    let lead = document.getElementById('hs-leadin');
    if (!lead) {
      lead = document.createElement('div');
      lead.id = 'hs-leadin';
      document.body.appendChild(lead);
    }
    const now = performance.now();
    // The corner clock steps out of the way while the run-up has the
    // screen: it would read 0:04 beside a three, which is two clocks.
    if (clocks.stepKey && !clocks.leadKey) {
      const left = (clocks.stepAt - now) / 1000;
      const html = `<span class="k">${esc(clocks.stepWord)}</span>${mmss(left)}`;
      if (clock.innerHTML !== html) clock.innerHTML = html;
      clock.classList.toggle('soon', left <= 60);
      clock.hidden = false;
    } else {
      clock.hidden = true;
    }
    if (clocks.leadKey) {
      const left = (clocks.leadAt - now) / 1000;
      /* A long run-up - the host said "Playing in 60 s" - gets a clock with
         words on it, so a room in intermission can see the game coming.
         The last ten seconds are the run-up as it always was. */
      const word = left > 10 ? (clocks.leadWord || 'Starts in') + ' ' + mmss(left)
                 : left > 3 ? 'Get ready!' : left > 0 ? String(Math.ceil(left)) : 'Go!';
      const cls = left > 10 ? 'hs-word hs-clock' : left > 3 ? 'hs-word' : 'hs-word hs-num';
      if (lead.dataset.word !== word) {
        lead.dataset.word = word;
        lead.innerHTML = `<div class="${cls}">${word}</div>`;
      }
      lead.hidden = false;
      document.body.classList.add('hs-leadin-on');
    } else {
      lead.hidden = true;
      lead.dataset.word = '';
      document.body.classList.remove('hs-leadin-on');
    }
  }

  /* Announcements and attention, laid over whatever the screen is doing.
     Urgent ones are red and stay; notices are amber and time out by
     themselves on the server side, so this draws what it is given. */
  /* A message keyed from net control. It arrives as an ordinary
     announcement with a `cw` on it - see /api/net/ping - so the words go up
     the way any notice does and the code is in the air at the same moment.
     Once per announcement, because the overlay is painted on every poll;
     and only where there is a keyer, which is every screen that shows the
     hall. Twenty words a minute on 1020 Hz, the same as everything else
     this program keys, so the hall sounds like one station. */
  const sounded = new Set();
  function keyAloud(anns) {
    if (typeof player === 'undefined' || typeof CODE === 'undefined') return;
    anns.forEach(a => {
      if (!a.cw || sounded.has(a.id)) return;
      sounded.add(a.id);
      const words = String(a.cw).split(' ')
        .map(w => [...w].map(c => ({char: c, code: CODE[c] || ''})).filter(x => x.code))
        .filter(w => w.length);
      if (!words.length) return;
      const dit = 1200 / 20;
      try {
        if (typeof holdTone === 'function') holdTone(1020);
        player.send(words, {dit: dit, dah: 3 * dit, symbol_gap: dit,
                            char_gap: 3 * dit, word_gap: 7 * dit},
                    null, () => { if (typeof holdTone === 'function') holdTone(null); });
      } catch (e) { /* no audio here; the words are on the screen */ }
    });
  }

  function overlay(show) {
    take(show);
    keyAloud((show && show.announcements) || []);
    let box = document.getElementById('hs-overlay');
    if (!box) {
      box = document.createElement('div');
      box.id = 'hs-overlay';
      document.body.appendChild(box);
    }
    const att = show && show.attention;
    const anns = (show && show.announcements) || [];
    const key = (att ? 'A' + att.at + att.text : '') + '|' + anns.map(a => a.id + (a.mine ? 'm' : '')).join(',');
    if (box.dataset.key === key) return;
    box.dataset.key = key;
    document.body.classList.toggle('hs-held', !!att);
    box.innerHTML =
      (att ? `<div class="hs-attention"><div class="hs-kicker">One moment</div><p>${esc(att.text)}</p></div>` : '') +
      anns.map(a => `<div class="hs-ann ${a.weight}${a.mine ? ' mine' : ''}">
          <span class="hs-ann-k">${a.weight === 'urgent' ? 'Attention' : (a.mine ? 'For you' : 'Notice')}</span>
          <span class="hs-ann-t">${esc(a.text)}</span></div>`).join('');
  }

  window.hallShow = {cardHTML, overlay, showingWord, mmss};
})();
