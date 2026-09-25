/* Drill loop: fetch a question, take one answer, show the verdict, repeat.
   The correct answer arrives only in the response to an answer, so nothing on
   the page can be inspected to cheat ahead of committing. */

const S = window.STUDY;
const card = document.getElementById('card');
const state = {
  q: null, shownAt: 0, answered: false,
  count: 0, right: 0, run: 0, recent: [],
  ladder: S.ladder || null,
  startedAt: Date.now()
};

/* The owl, and only where it is earned.
 *
 * Not on every miss. Spaced repetition works by finding what you get wrong -
 * missing is the signal the scheduler runs on, and putting a stern face on it
 * would be disapproving of the mechanism. A miss also happens dozens of times
 * an evening, and a character that appears dozens of times an evening stops
 * meaning anything by Thursday.
 *
 * What it marks instead is forgetting something you had learned: a card the
 * scheduler was holding a day or more out, answered right twice with a night
 * in between, and now gone. That is rare, it is worth a beat, and it says
 * something useful - which cards are slipping, rather than which are new. */
function lapseNote(res) {
  if (!res.lapsed) return '';
  const held = res.was_interval >= 1
    ? Math.round(res.was_interval) + ' day' + (res.was_interval >= 1.5 ? 's' : '')
    : 'a while';
  return '<div class="lapse">' +
    '<img src="/static/owl-mind.png" alt="" class="lapse-owl">' +
    '<div><b>You had this one.</b> It was scheduled ' + escapeHTML(held) +
    ' out, which means you answered it right twice with a night in between. ' +
    'It is back in the short pile now &mdash; that is the scheduler doing its ' +
    'job, not a setback.</div></div>';
}


/* ------------------------------------------------------------ run ladder */
/* The bar, the run against it, and where the last few runs broke.
 *
 * The breaks are the part worth printing. Somebody learning a pool breaks at
 * four, then six, then eight, and one evening not at all - and the number
 * going back to nought, which is all the HUD used to do, hid exactly that.
 * So the recent breaks are shown in order, the trend is named when there are
 * enough of them to name it, and the bar only ever goes up. A run that ends
 * short of the bar costs nothing: see runladder.py. */

function trendOf(breaks) {
  const kept = (breaks || []).filter(b => b);
  if (kept.length < 4) return null;
  const half = Math.floor(kept.length / 2);
  const older = kept.slice(0, half).reduce((a, b) => a + b, 0) / half;
  const newer = kept.slice(half).reduce((a, b) => a + b, 0) / (kept.length - half);
  if (newer >= older + 1) return 'rising';
  if (newer <= older - 1) return 'falling';
  return 'level';
}

function paintLadder() {
  const L = state.ladder;
  if (!L || !document.getElementById('ladder')) return;

  document.getElementById('h-run').textContent = L.run;
  document.getElementById('h-bar').textContent = L.bar;
  document.getElementById('l-best').textContent = L.best;
  document.getElementById('l-hits').textContent = L.hits;

  const fill = document.getElementById('l-fill');
  fill.style.width = Math.min(100, 100 * L.run / Math.max(1, L.bar)).toFixed(0) + '%';
  fill.className = L.run >= L.target ? 'fill-high' : L.run ? 'fill-mid' : 'fill-low';

  document.getElementById('l-goal').textContent = L.settled
    ? 'ten in a row is yours — working at ' + L.bar
    : L.to_bar === 0 ? 'next rung ' + L.bar
    : L.to_bar + ' more for ' + L.bar +
      (L.hits ? '' : ', then ' + L.target + ' is the one that counts');

  const breaks = document.getElementById('l-breaks');
  breaks.innerHTML = L.breaks.length
    ? 'broke at ' + L.breaks.map(b =>
        '<b>' + b + '</b>').join(' → ')
    : '';

  const trend = trendOf(L.breaks);
  document.getElementById('l-trend').innerHTML = trend === 'rising'
    ? '<span style="color:var(--green)">getting further each time</span>'
    : trend === 'falling'
    ? '<span class="muted">not getting as far lately</span>' : '';
}

/* What the ladder did on this answer, for the verdict. Silent on the
 * ordinary case - most answers move the run by one and that is already in
 * the HUD - and says something only when a rung is reached, a best is set,
 * or a run ends, because a note that appears on every answer is wallpaper
 * by Thursday. */
function ladderNote(L) {
  if (!L) return '';
  /* Ten in a row is announced every time it happens, not only the first:
     the bar has moved past ten by the second one, so `reached` is null
     there, and those later tens are precisely the ones that turn a lucky
     draw into having it. See _event() in runladder.py. */
  if (L.hit_target) {
    return '<div class="rung">▲ <b>' + L.target + ' in a row.</b> ' + (L.settled
      ? 'That is ' + L.hits + ' times you have had ten from ' +
        escapeHTML(S.pool_name) + ' — it is not the draw any more.'
      : 'Ten from one pool is roughly what the real paper feels like. ' +
        (L.hits_needed === 1 ? 'Once more' : L.hits_needed + ' more times') +
        ' and it counts as reliable.') + '</div>';
  }
  if (L.reached) {
    return '<div class="rung">▲ <b>' + L.reached + ' in a row.</b> ' +
      'The bar moves to ' + L.bar + '.</div>';
  }
  if (L.broke) {
    const before = L.previous_break
      ? ' Last one ended at ' + L.previous_break + '.' : '';
    return '<div class="tiny muted" style="margin-top:.35rem">' +
      'Run of ' + L.broke + ' ended.' + before +
      (L.improved ? ' <span style="color:var(--green)">Further than last time.</span>'
                  : '') + '</div>';
  }
  if (L.new_best && L.run > 1) {
    return '<div class="tiny" style="margin-top:.35rem;color:var(--amber)">' +
      'Longest run yet in ' + escapeHTML(S.pool_name) + ': ' + L.run + '.</div>';
  }
  return '';
}

/* A step on the rank ladder is the rarest thing that happens on this page,
 * and it was being thrown away: /api/answer has returned `promoted` all
 * along and nothing rendered it. */
function promotionNote(promoted) {
  if (!promoted) return '';
  return '<div class="promoted">' +
    '<div><b>' + escapeHTML(promoted.step_name) + '</b></div>' +
    '<div class="small muted">Your standing in ' + escapeHTML(promoted.class_name) +
    (promoted.next_name
      ? '. Next is ' + escapeHTML(promoted.next_name) + '.'
      : '. That is the top of this ladder.') +
    ' ELMER’s own standing, against ELMER’s own copy of the pool.</div></div>';
}

/* Somebody answering out of the network tab.
 *
 * The drill sends `order` with every question and always will - the answer
 * is a second away, for free, and the card comes back until it is actually
 * known, so there is nothing here worth defending. What there is, is
 * something worth saying. The stern owl, which the program otherwise keeps
 * for an exposure limit and a license claim, because this is the third
 * thing on the list of raised-eyebrow moments and it is a much funnier one.
 * See peeking.py. */
function wireNote(wire) {
  if (!wire) return '';
  return '<div class="wire">' +
    '<img src="/static/owl-mind.png" alt="" class="lapse-owl">' +
    '<div>' + wire.lines.map(line =>
      '<p>' + escapeHTML(line) + '</p>').join('') + '</div></div>';
}

/* Badges toast, and the toast is gone in seven seconds - which is fine for
 * "you have studied three days running" and not fine for the ones somebody
 * worked a fortnight for. So they are also written into the verdict, where
 * they stay until the next question is asked for. */
function badgeNote(list) {
  if (!list || !list.length) return '';
  return '<div class="badges">' + list.map(a =>
    '<div><span class="badge-mark">\u{1F3C5}</span> <b>' + escapeHTML(a.name) +
    '</b> <span class="small muted">' + escapeHTML(a.description) + '</span></div>'
  ).join('') + '</div>';
}

/* The sounds, in order of what they are worth. One per answer at most: a
 * rung and a badge on the same answer plays the badge, because the rarer
 * thing is the one worth hearing. Off unless the operator switched it on -
 * chime.js holds that, and every call here is a no-op while it is off. */
function sound(res) {
  if (typeof Chime === 'undefined') return;
  const L = res.ladder;
  if (res.promoted) return Chime.promoted();
  if (res.achievements && res.achievements.length) return Chime.badge();
  if (L && (L.hit_target || L.reached)) return Chime.rung(L.hit_target ? L.target : L.reached);
  if (L && L.improved) return Chime.further();
  return res.correct ? Chime.right() : Chime.wrong();
}

function hud() {
  document.getElementById('h-count').textContent = state.count;
  document.getElementById('h-acc').textContent =
    state.count ? Math.round(100 * state.right / state.count) + '%' : '-';
  paintLadder();
  if (S.rapid) {
    const left = Math.max(0, 300 - (Date.now() - state.startedAt) / 1000);
    document.getElementById('h-timer').textContent = 'contest ' + fmtDuration(left);
    if (left <= 0) finishContest();
  }
}

async function nextQuestion() {
  card.innerHTML = '<div class="muted">Loading question&hellip;</div>';
  const params = new URLSearchParams({ pool: S.pool, mode: S.mode });
  if (S.section) params.set('section', S.section);
  if (state.recent.length) params.set('exclude', state.recent.slice(-25).join(','));
  const q = await api('/api/next?' + params);
  if (q.done) {
    card.innerHTML = '<h2>Nothing left in this selection</h2><p class="muted">' +
      escapeHTML(q.reason) + '</p><a class="btn primary" href="/study/' + S.pool + '">Back to drill</a>';
    return;
  }
  state.q = q; state.answered = false; state.shownAt = Date.now();
  render();
}

function render() {
  const q = state.q;
  const seenNote = q.card
    ? 'seen ' + q.card.seen + '×, ' + Math.round(100 * q.card.correct / q.card.seen) +
      '% right' + (q.card.lapses ? ', ' + q.card.lapses + ' lapse' + (q.card.lapses > 1 ? 's' : '') : '')
    : 'new question';
  card.innerHTML =
    '<div class="quiz-context"><span class="qid">' + escapeHTML(q.question_id) + '</span> &middot; ' +
      escapeHTML(q.section) + ' ' + escapeHTML(q.section_title) +
      ' <span style="float:right">' + escapeHTML(seenNote) + '</span></div>' +
    '<div class="question-text">' + escapeHTML(q.text) + '</div>' +
    figureHTML(q.figure, q.highlight) +
    '<div class="choices">' + q.choices.map((c, i) =>
      '<button class="choice" data-i="' + i + '">' +
        '<span class="choice-key">' + 'ABCD'[i] + '</span><span>' + escapeHTML(c) + '</span>' +
      '</button>').join('') + '</div>' +
    '<div id="verdict"></div>';
  card.querySelectorAll('.choice').forEach(b =>
    b.addEventListener('click', () => answer(+b.dataset.i)));
  hud();
}

async function answer(index) {
  if (state.answered) return;
  state.answered = true;
  const q = state.q;
  const res = await postJSON('/api/answer', {
    pool: S.pool, question_id: q.question_id, chosen: index,
    order: q.order, ms: Date.now() - state.shownAt, mode: S.mode
  });

  const buttons = card.querySelectorAll('.choice');
  buttons.forEach(b => { b.disabled = true; });
  buttons[res.answer_shown].classList.add('right');
  if (!res.correct && index >= 0) buttons[index].classList.add('wrong');

  state.count++; state.right += res.correct ? 1 : 0;
  state.run = res.run; state.recent.push(q.question_id);
  if (res.ladder) state.ladder = res.ladder;
  document.getElementById('h-xp').textContent = res.total_xp;
  hud();
  showAchievements(res.achievements);
  sound(res);

  const nextDue = res.interval_days >= 1
    ? 'next review in ' + Math.round(res.interval_days) + ' day' + (res.interval_days >= 1.5 ? 's' : '')
    : 'scheduled to come back this session';
  document.getElementById('verdict').innerHTML =
    '<div class="verdict ' + (res.correct ? 'right' : 'wrong') + '">' +
      '<div class="verdict-head">' +
        (res.correct ? '<span style="color:var(--green)">&#10003; Correct</span>'
                     : '<span style="color:var(--red)">&#10007; Not quite</span>') +
        '<span class="xp">+' + res.xp + ' XP</span></div>' +
      lapseNote(res) +
      wireNote(res.wire) +
      ladderNote(res.ladder) +
      badgeNote(res.achievements) +
      promotionNote(res.promoted) +
      '<div class="small muted">' + res.explain.map(escapeHTML).join(' &middot; ') + '</div>' +
      '<div class="tiny muted" style="margin-top:.35rem">' + nextDue + '</div>' +
      explanationHTML(res.explanation, { pool: S.pool }) +
      '<button class="btn primary sm" style="margin-top:.7rem" id="next">Next question &rarr;</button>' +
    '</div>';
  document.getElementById('next').addEventListener('click', nextQuestion);
  // Contest mode keeps moving while you are right; a miss is worth stopping for.
  if (S.rapid && res.correct) setTimeout(nextQuestion, 900);
}

function reveal() {
  if (state.answered || !state.q) return;
  answer(-1);   /* counts as wrong, which is the honest thing to do */
}

function finishContest() {
  card.innerHTML = '<h2>Contest round over</h2>' +
    '<p class="muted">' + state.count + ' questions, ' + state.right + ' correct (' +
    (state.count ? Math.round(100 * state.right / state.count) : 0) + '%).</p>' +
    '<a class="btn primary" href="/study/' + S.pool + '?mode=rapid">Run it again</a> ' +
    '<a class="btn" href="/progress/' + S.pool + '">See progress</a>';
  state.startedAt = Infinity;
}

document.addEventListener('keydown', e => {
  if (isTyping(e)) return;
  const k = e.key.toLowerCase();
  if (!state.answered) {
    const byNumber = '1234'.indexOf(k);
    const byLetter = 'abcd'.indexOf(k);
    const pick = byNumber >= 0 ? byNumber : byLetter;
    if (pick >= 0) { e.preventDefault(); answer(pick); return; }
    if (k === '?') { e.preventDefault(); reveal(); return; }
  } else if (k === ' ' || k === 'enter') {
    e.preventDefault(); nextQuestion();
  }
});

/* The sound switch, put in the HUD by the page that has sounds rather than
   baked into the template, so a build without chime.js simply has no
   button instead of a dead one. */
(function mountSound() {
  const slot = document.getElementById('h-sound');
  if (slot && typeof chimeControl === 'function') slot.appendChild(chimeControl());
})();

paintLadder();
setInterval(hud, 1000);
nextQuestion();
