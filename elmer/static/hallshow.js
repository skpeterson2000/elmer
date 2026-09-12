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

  /* Announcements and attention, laid over whatever the screen is doing.
     Urgent ones are red and stay; notices are amber and time out by
     themselves on the server side, so this draws what it is given. */
  function overlay(show) {
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

  window.hallShow = {cardHTML, overlay, showingWord};
})();
