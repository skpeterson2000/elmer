/* Calibrate my forecast: start it, watch it, read what it found.

   Five minutes is a long time to look at a bar. So the screen alternates two
   things: the findings, one a month, as the run passes each month of the
   year ("October: the model ran 11.2 MHz under by day - the winter anomaly");
   and a card from the decks - history, a quotation, a ham people have heard
   of - each up for as long as it takes to read. Neither costs anything: the
   run is a thread on the server and this page polls a status line every two
   seconds.

   A card stands for five seconds plus a third of a second a word, counting
   the attribution with the text. A fixed twelve seconds cut a long quotation
   off halfway and left a short one standing long after it was read. One tap
   on the card holds it there; a second tap moves on to the next, and the
   timing starts again from that card. */
(() => {
  const choices = document.getElementById('cal-choices');
  if (!choices) return;
  const starts = Array.from(choices.querySelectorAll('[data-cal-days]'));
  const stop = document.getElementById('cal-stop');
  const state = document.getElementById('cal-state');
  const stage = document.getElementById('cal-stage');
  const bar = document.getElementById('cal-bar');
  const progress = document.getElementById('cal-progress');
  const findings = document.getElementById('cal-findings');
  const result = document.getElementById('cal-result');
  const cardText = document.getElementById('cal-card-text');
  const cardAbout = document.getElementById('cal-card-about');
  const cardDeck = document.getElementById('cal-card-deck');
  const card = document.getElementById('cal-card');
  const cardHint = document.getElementById('cal-card-hint');
  let poll = null, cardTimer = null, lastCard = '', deckIndex = 0, shownFindings = 0;
  let cardsOn = false, cardHeld = false, cardAsked = 0;
  const CARD_BASE_S = 5, CARD_PER_WORD_S = 0.33;
  const DECKS = ['history', 'quotes', 'hams', 'history', 'hams'];
  const DECK_NAMES = {history: 'From the history of the art', quotes: 'Somebody said', hams: 'Hams you have heard of'};

  /* How long a card stands: the words on it, the attribution included. */
  function readingMs(c) {
    const words = ((c.text || '') + ' ' + (c.about || '')).split(/\s+/).filter(Boolean).length;
    return Math.round((CARD_BASE_S + CARD_PER_WORD_S * words) * 1000);
  }

  function hint() {
    if (cardHint) cardHint.textContent = cardHeld ? 'Held. Tap for the next card.' : 'Tap to hold this card.';
    if (card) card.setAttribute('aria-pressed', cardHeld ? 'true' : 'false');
  }

  function schedule(ms) {
    clearTimeout(cardTimer);
    cardTimer = cardsOn && !cardHeld ? setTimeout(nextCard, ms) : null;
  }

  async function nextCard() {
    clearTimeout(cardTimer); cardTimer = null;
    const deck = DECKS[deckIndex++ % DECKS.length];
    const asked = ++cardAsked;
    try {
      const c = await api('/api/cards?deck=' + deck + '&avoid=' + encodeURIComponent(lastCard));
      if (asked !== cardAsked || !cardsOn) return;     // a newer card was asked for, or the run ended
      lastCard = c.text;
      cardDeck.textContent = DECK_NAMES[c.deck] || '';
      cardText.innerHTML = c.deck === 'hams' ? '<b>' + escapeHTML(c.text) + '</b>' : '“' + escapeHTML(c.text) + '”';
      cardAbout.textContent = c.deck === 'hams' ? c.about : '— ' + c.about;
      schedule(readingMs(c));
    } catch (e) {
      // The card is a courtesy: try another after the shortest stand.
      if (asked === cardAsked) schedule(CARD_BASE_S * 1000);
    }
  }

  function startCards() {
    if (cardsOn) return;
    cardsOn = true; cardHeld = false; hint();
    nextCard();
  }

  function stopCards() {
    cardsOn = false; cardHeld = false;
    clearTimeout(cardTimer); cardTimer = null;
    hint();
  }

  /* One tap holds the card; a second moves on to the next. */
  function tapCard() {
    if (!cardsOn) return;
    if (!cardHeld) {
      cardHeld = true;
      clearTimeout(cardTimer); cardTimer = null;
      hint();
    } else {
      cardHeld = false; hint();
      nextCard();
    }
  }
  if (card) {
    card.addEventListener('click', tapCard);
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); tapCard(); }
    });
  }

  function paint(s) {
    const running = ['queued', 'fetching', 'running', 'checking'].includes(s.state);
    starts.forEach(b => { b.disabled = running; });
    stop.hidden = !running;
    stage.hidden = !running && s.state !== 'done' && s.state !== 'failed' && s.state !== 'stopped';
    const pct = Math.round((s.fraction || 0) * 100);
    bar.style.width = pct + '%';
    const mins = Math.round((s.elapsed_s || 0) / 60);
    const span = s.days >= 300 ? 'the year' : s.days >= 150 ? 'the half-year' : s.days >= 60 ? 'the quarter' : 'the last ' + s.days + ' days';
    const phase = s.state === 'fetching' ? 'Fetching ' + span + ' from the sondes, GFZ and SWPC…'
      : s.state === 'running' ? 'Forecasting ' + span + ' blind, hour by hour (pass 1 of ' + (s.passes || 2) + ')'
      : s.state === 'checking' ? (s.passes === 3 && s.pass === 2
          ? 'Running ' + span + ' again with the calibration in force (pass 2 of 3)'
          : 'Running ' + span + ' again with the new correction on (pass ' + (s.pass || 2) + ' of ' + (s.passes || 2) + ')')
      : s.state === 'done' ? 'Done.' : s.state === 'failed' ? 'Could not finish.' : s.state === 'stopped' ? 'Stopped.' : 'Starting…';
    progress.textContent = phase + (running && s.hours_total ? ' — ' + s.hours_done + ' of ' + s.hours_total + ' hours' : '') +
      (mins ? ' — ' + mins + ' min' : '');
    state.textContent = running ? 'Calibrating for ' + (s.place || 'your QTH') + '…'
      : s.state === 'failed' ? (s.error || 'failed') : '';
    const list = s.findings || [];
    if (list.length > shownFindings) {
      for (let i = shownFindings; i < list.length; i++) {
        const li = document.createElement('li'); li.textContent = list[i].text; findings.appendChild(li);
      }
      shownFindings = list.length;
      findings.scrollTop = findings.scrollHeight;
    }
    if (s.state === 'done' && s.result) paintResult(s.result);
    // A run just finished while watched: the charts below have a new run.
    if (s.state === 'done' && poll && typeof calchartsLoad === 'function') calchartsLoad();
    if (!running) {
      clearInterval(poll); poll = null;
      stopCards();
    }
  }

  /* Which months the held table knows and from which run each came - the
     honest reading of a table built up from runs of different depths. */
  function coverageLine(table) {
    const byRun = {};
    Object.entries(table.months || {}).forEach(([m, entry]) => {
      const key = (entry._made || table.made || '').slice(0, 10) + '|' + (entry._days || table.days || '');
      (byRun[key] = byRun[key] || []).push(m);
    });
    const names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const runs = Object.entries(byRun).map(([key, months]) => {
      const [made, days] = key.split('|');
      const depth = days >= 300 ? 'comprehensive' : days >= 150 ? 'normal' : days >= 60 ? 'quick' : days + '-day';
      return months.map(m => names[parseInt(m, 10)]).join(', ') + ' from a ' + depth + ' run on ' +
        new Date(made).toLocaleDateString();
    });
    const applied = Object.values(table.months || {}).reduce((n, m) =>
      n + Object.values(m).filter(c => c && typeof c === 'object' && c.applied).length, 0);
    return 'Calibrated against ' + (table.stations || []).join(', ') + ': ' + runs.join('; ') + '. ' +
      (applied ? applied + ' month-and-sky corrections in use.' : 'Nothing found worth correcting - the model fits this sky.') +
      ' Run it again any time.';
  }

  function paintResult(r) {
    /* Three numbers where there are three: the bare model, the calibration
       the unit was already using, and the table just fitted - each over the
       same span. Two used to be all a run showed, so it could never say
       whether the calibration in force had helped. */
    const b = r.before || {}, a = r.after || {}, h = r.held || null;
    const lead = (x, k) => (((x || {}).by_lead || {})[k] || {}).mae;
    const l = k => lead(b, k), la = k => lead(a, k), lh = k => lead(h, k);
    const cell = v => (v != null ? v.toFixed(2) : '—');
    const months = Object.keys(a.by_month || {});
    const rows = months.map(m => {
      const bm = (b.by_month || {})[m] || {}, am = (a.by_month || {})[m] || {};
      const hm = h ? ((h.by_month || {})[m] || {}) : null;
      return '<tr><td class="mono">' + escapeHTML(m) + '</td><td class="mono">' + cell(bm.mae) + '</td>' +
        (hm ? '<td class="mono">' + cell(hm.mae) + '</td>' : '') +
        '<td class="mono"><b>' + cell(am.mae) + '</b></td><td class="mono muted">' + cell(am.persistence) + '</td></tr>';
    }).join('');
    const p = (b.persistence_24h || {}).mae;
    result.hidden = false;
    result.innerHTML =
      '<div class="panel-title" style="margin:0 0 .3rem">What the calibration bought</div>' +
      '<p class="small">Over the span, the 24-hour forecast’s error against the sondes: the bare model <b>' +
      (l('24') != null ? l('24').toFixed(2) : '?') + '</b>' +
      (h ? ', the calibration in force' + (r.held_made ? ' (from ' + escapeHTML(new Date(r.held_made).toLocaleDateString()) + ')' : '') +
           ' <b>' + (lh('24') != null ? lh('24').toFixed(2) : '?') + '</b>' : '') +
      ', the new table <b>' + (la('24') != null ? la('24').toFixed(2) : '?') +
      ' MHz</b>' + (p != null ? '; “the same as this hour yesterday” manages ' + p.toFixed(2) + '.' : '.') +
      ' The band plan’s 24-hour strips use the correction from now on, and say so.</p>' +
      '<table class="facts small"><tr><th>Month</th><th>Bare model</th>' + (h ? '<th>In force</th>' : '') + '<th>New table</th><th>Yesterday-as-forecast</th></tr>' + rows + '</table>' +
      '<p class="tiny muted" style="margin:.5rem 0 0">Mean error in MHz of the model’s own hours (6–24 h ahead). ' +
      'Measured against ' + (b.sondes_voting || '?') + ' sondes voting on average, over ' + (b.hours_with_reading || '?') +
      ' hours with a reading in reach. ' + escapeHTML((r.table || {}).acknowledgement || '') + '</p>';
  }

  async function tick() {
    try { paint(await api('/api/calibrate/status')); } catch (e) { /* try again next tick */ }
  }

  choices.addEventListener('click', async e => {
    const btn = e.target.closest('[data-cal-days]');
    if (!btn) return;
    starts.forEach(b => { b.disabled = true; });
    findings.innerHTML = ''; shownFindings = 0; result.hidden = true;
    try {
      const s = await postJSON('/api/calibrate', {days: parseInt(btn.dataset.calDays, 10)});
      stage.hidden = false;
      paint(s);
      if (!poll) poll = setInterval(tick, 2000);
      startCards();
    } catch (err) { starts.forEach(b => { b.disabled = false; }); }
  });
  stop.addEventListener('click', async () => { try { await postJSON('/api/calibrate/stop', {}); } catch (e) {} });

  /* On load: a run already going (page reopened), or a table already held. */
  api('/api/calibrate/status').then(s => {
    if (['queued', 'fetching', 'running', 'checking'].includes(s.state)) {
      stage.hidden = false; paint(s);
      poll = setInterval(tick, 2000); startCards();
    } else if (s.table && s.table.months) {
      state.innerHTML = coverageLine(s.table);
    }
  }).catch(() => {});
})();
