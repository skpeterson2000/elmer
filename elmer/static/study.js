/* Drill loop: fetch a question, take one answer, show the verdict, repeat.
   The correct answer arrives only in the response to an answer, so nothing on
   the page can be inspected to cheat ahead of committing. */

const S = window.STUDY;
const card = document.getElementById('card');
const state = {
  q: null, shownAt: 0, answered: false,
  count: 0, right: 0, run: 0, recent: [],
  startedAt: Date.now()
};

function hud() {
  document.getElementById('h-count').textContent = state.count;
  document.getElementById('h-acc').textContent =
    state.count ? Math.round(100 * state.right / state.count) + '%' : '-';
  document.getElementById('h-run').textContent = state.run;
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
    figureHTML(q.figure) +
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
  document.getElementById('h-xp').textContent = res.total_xp;
  hud();
  showAchievements(res.achievements);

  const nextDue = res.interval_days >= 1
    ? 'next review in ' + Math.round(res.interval_days) + ' day' + (res.interval_days >= 1.5 ? 's' : '')
    : 'scheduled to come back this session';
  document.getElementById('verdict').innerHTML =
    '<div class="verdict ' + (res.correct ? 'right' : 'wrong') + '">' +
      '<div class="verdict-head">' +
        (res.correct ? '<span style="color:var(--green)">&#10003; Correct</span>'
                     : '<span style="color:var(--red)">&#10007; Not quite</span>') +
        '<span class="xp">+' + res.xp + ' XP</span></div>' +
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

setInterval(hud, 1000);
nextQuestion();
