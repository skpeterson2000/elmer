/* Mock exam: all questions held client-side (without answers), navigable in any
   order, graded server-side on submit. */

const E = window.EXAM;
let exam = null, pos = 0, answers = {}, flags = new Set(), t0 = 0, timer = null;

document.getElementById('start').addEventListener('click', async () => {
  const btn = document.getElementById('start');
  btn.disabled = true; btn.textContent = 'Building exam…';
  exam = await postJSON('/api/exam/start', { pool: E.pool });
  document.getElementById('intro').hidden = true;
  document.getElementById('running').hidden = false;
  document.getElementById('e-total').textContent = exam.total;
  t0 = Date.now();
  timer = setInterval(tick, 500);
  buildMap();
  show(0);
});

function tick() {
  const s = (Date.now() - t0) / 1000;
  const el = document.getElementById('e-timer');
  el.textContent = fmtDuration(s);
  el.style.color = s > exam.pace_minutes * 60 ? 'var(--red)' : '';
}

function buildMap() {
  const map = document.getElementById('e-map');
  map.innerHTML = exam.items.map((_, i) =>
    '<button class="qmap" data-i="' + i + '">' + (i + 1) + '</button>').join('');
  map.querySelectorAll('.qmap').forEach(b =>
    b.addEventListener('click', () => show(+b.dataset.i)));
}

function refreshMap() {
  document.querySelectorAll('.qmap').forEach((b, i) => {
    b.classList.toggle('done', answers[i] !== undefined);
    b.classList.toggle('flag', flags.has(i));
    b.classList.toggle('here', i === pos);
  });
  document.getElementById('e-done').textContent = Object.keys(answers).length;
  document.getElementById('e-flag').textContent = flags.size;
  document.getElementById('e-pos').textContent = pos + 1;
}

function show(i) {
  pos = Math.max(0, Math.min(exam.items.length - 1, i));
  const item = exam.items[pos];
  document.getElementById('e-card').innerHTML =
    '<div class="quiz-context"><span class="qid">' + escapeHTML(item.question_id) + '</span> &middot; ' +
      escapeHTML(item.section) + ' ' + escapeHTML(item.section_title) + '</div>' +
    '<div class="question-text">' + escapeHTML(item.text) + '</div>' +
    figureHTML(item.figure) +
    '<div class="choices">' + item.choices.map((c, n) =>
      '<button class="choice' + (answers[pos] === n ? ' right' : '') + '" data-n="' + n + '">' +
        '<span class="choice-key">' + 'ABCD'[n] + '</span><span>' + escapeHTML(c) + '</span>' +
      '</button>').join('') + '</div>' +
    '<button class="btn sm ghost" id="e-flagbtn" style="margin-top:.8rem">' +
      (flags.has(pos) ? '★ Flagged for review' : '☆ Flag for review') + '</button>';

  document.querySelectorAll('#e-card .choice').forEach(b =>
    b.addEventListener('click', () => { answers[pos] = +b.dataset.n; show(pos); }));
  document.getElementById('e-flagbtn').addEventListener('click', () => {
    flags.has(pos) ? flags.delete(pos) : flags.add(pos); show(pos);
  });
  refreshMap();
}

document.getElementById('e-prev').addEventListener('click', () => show(pos - 1));
document.getElementById('e-next').addEventListener('click', () => show(pos + 1));
document.getElementById('e-submit').addEventListener('click', submit);

async function submit() {
  const left = exam.items.length - Object.keys(answers).length;
  if (left && !confirm(left + ' question' + (left > 1 ? 's are' : ' is') +
      ' unanswered and will be marked wrong. Submit anyway?')) return;
  clearInterval(timer);
  const res = await postJSON('/api/exam/' + exam.exam_id + '/submit', {
    responses: answers, seconds: Math.round((Date.now() - t0) / 1000)
  });
  document.getElementById('running').hidden = true;
  renderResults(res);
  showAchievements(res.achievements);
}

function renderResults(r) {
  const box = document.getElementById('results');
  box.hidden = false;
  const missed = r.results.filter(x => !x.correct);
  box.innerHTML =
    '<div class="panel">' +
      '<div class="spread"><h1>' + (r.passed ? 'Pass' : 'Not yet') + '</h1>' +
      '<span class="pill ' + (r.passed ? 'good' : 'bad') + '">' + r.score + ' / ' + r.total +
      ' &middot; ' + r.percent + '%</span></div>' +
      '<p class="muted">' + (r.passed
        ? 'That clears the ' + r.pass_mark + '-question bar. Keep the streak going so it stays that way on exam day.'
        : 'You needed ' + r.pass_mark + '. The breakdown below shows where the marks went.') +
      ' Finished in ' + fmtDuration(r.seconds) + '. +' + r.xp + ' XP.</p>' +
      meterHTML(r.score / r.total) +
    '</div>' +

    '<div class="panel mt"><div class="panel-title">By subelement</div>' +
      '<table class="data"><tbody>' + r.breakdown.map(b =>
        '<tr><td class="mono" style="width:3.5rem">' + escapeHTML(b.code) + '</td>' +
        '<td>' + escapeHTML(b.title) + '</td>' +
        '<td class="mono" style="width:4rem">' + b.right + '/' + b.total + '</td>' +
        '<td style="width:34%">' + meterHTML(b.right / b.total, true) + '</td></tr>').join('') +
      '</tbody></table></div>' +

    (missed.length ? '<div class="panel mt"><div class="panel-title">Review the ' +
      missed.length + ' you missed</div>' + missed.map(m =>
      '<div style="border-bottom:1px solid #1c242e;padding:.7rem 0">' +
        '<div class="quiz-context"><span class="qid">' + escapeHTML(m.question_id) +
          '</span> &middot; ' + escapeHTML(m.section_title) + '</div>' +
        '<div style="margin:.3rem 0">' + escapeHTML(m.text) + '</div>' +
        '<div class="small" style="color:var(--green)">&#10003; ' + escapeHTML(m.answer_text) + '</div>' +
        (m.chosen_text ? '<div class="small" style="color:var(--red)">&#10007; you chose: ' +
          escapeHTML(m.chosen_text) + '</div>' : '<div class="small muted">left blank</div>') +
      '</div>').join('') + '</div>' : '') +

    '<div class="row mt">' +
      '<a class="btn primary" href="/study/' + E.pool + '?mode=weak">Drill the weak spots</a>' +
      '<a class="btn" href="/exam/' + E.pool + '">Another exam</a>' +
      '<a class="btn ghost" href="/progress/' + E.pool + '">Full progress</a>' +
    '</div>';
  window.scrollTo(0, 0);
}

document.addEventListener('keydown', e => {
  if (isTyping(e)) return;
  if (!exam || document.getElementById('running').hidden) return;
  const k = e.key.toLowerCase();
  const n = '1234'.indexOf(k) >= 0 ? '1234'.indexOf(k) : 'abcd'.indexOf(k);
  if (n >= 0) { answers[pos] = n; show(pos); e.preventDefault(); }
  else if (e.key === 'ArrowRight') { show(pos + 1); e.preventDefault(); }
  else if (e.key === 'ArrowLeft') { show(pos - 1); e.preventDefault(); }
  else if (k === 'f') { flags.has(pos) ? flags.delete(pos) : flags.add(pos); show(pos); }
});
