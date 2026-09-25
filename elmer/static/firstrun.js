/* The first-run tour, and the reason it exists.

   The Commission's amateur file is a couple of hundred megabytes by the time
   it is read in, and it used to be started by somebody typing their callsign -
   which put the download on the critical path of the one question a new
   licensee most wants answered. It is started with the program now, so by the
   time anyone asks, the answer is a local query.

   That leaves a few minutes on a fresh unit where the file is on its way. This
   is what fills them: a short pass through what the program does, in the
   program's own screenshots, with the real progress underneath it. Not a
   spinner and not a lie - the bar is the bytes, and when the file lands the
   card says so and stands down.

   It is skippable at every moment. Nobody is held here. */

const TOUR = [
  ['drill.png', 'Answer questions',
   'Every question from the current US pools, with an explanation on each one. ' +
   'What you get wrong comes back sooner; what you have cold comes back later.'],
  ['dashboard.png', 'Watch it move',
   'Standing is earned inside the class it names, and mock exams are built to ' +
   'the real blueprint. The estimate is honest about how little it knows early on.'],
  ['propagation.png', 'What the bands are doing',
   'Live space weather read against the ionosondes, for your own location - ' +
   'not a green light somebody else is looking at.'],
  ['lab.png', 'Work out the station',
   'Antenna heights, takeoff angles, feedline loss, RF exposure. The numbers ' +
   'follow the sliders, so you can see what changing something actually costs.'],
  ['cw.png', 'Learn the code',
   'Koch method at full speed, one character at a time, with the shape drawn ' +
   'until you can hear it without. Short sessions that end where they should.'],
  ['library.png', 'Keep the paperwork',
   'The guide, the rules, your own documents - searchable, and on the unit, ' +
   'so none of it needs a network at a field site.'],
  ['party.png', 'And do it with other people',
   'A table of phones around one screen, a net across units, and games that ' +
   'are really drills wearing a better hat.'],
];

const SLIDE_MS = 6500;

function bytesWord(n) {
  if (!n) return '';
  const mb = n / (1024 * 1024);
  return mb >= 1 ? mb.toFixed(mb < 10 ? 1 : 0) + ' MB' : Math.round(n / 1024) + ' KB';
}

(function () {
  const box = document.getElementById('firstrun');
  if (!box) return;
  const shot = document.getElementById('fr-shot');
  const head = document.getElementById('fr-head');
  const text = document.getElementById('fr-text');
  const dots = document.getElementById('fr-dots');
  const note = document.getElementById('fr-note');
  const bar = document.getElementById('fr-bar');
  const skip = document.getElementById('fr-skip');
  let at = -1, timer = null, watching = null;

  dots.innerHTML = TOUR.map((_, i) => '<span class="fr-dot" data-i="' + i + '"></span>').join('');

  function show(i) {
    at = (i + TOUR.length) % TOUR.length;
    const [file, title, body] = TOUR[at];
    /* The image is swapped only once the new one has arrived, so a slow card
       shows the last picture a moment longer instead of flashing empty. */
    const next = new Image();
    next.onload = () => { shot.src = next.src; shot.alt = title; };
    next.onerror = () => { shot.removeAttribute('src'); shot.alt = title; };
    next.src = '/guide/shot/' + encodeURIComponent(file);
    head.textContent = title;
    text.textContent = body;
    dots.querySelectorAll('.fr-dot').forEach((d, j) =>
      d.classList.toggle('on', j === at));
  }

  function start() {
    if (timer) clearInterval(timer);
    timer = setInterval(() => show(at + 1), SLIDE_MS);
  }

  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
    if (watching) { clearInterval(watching); watching = null; }
  }

  /* The bar is the bytes, and then the rows. Both are real; neither is a
     guess dressed up as one. Where the server gives no total - no
     Content-Length on the response - the bar says so rather than inventing a
     percentage. */
  async function look() {
    let d;
    try { d = await api('/api/uls'); } catch (e) { return; }
    const got = (d && d.amateur) || {};
    if (got.have) {
      note.innerHTML = '<b>The FCC’s amateur file is here.</b> ' +
        (got.have.rows ? got.have.rows.toLocaleString() + ' licenses, dated ' +
         escapeHTML(got.have.dated || '') + '. ' : '') +
        'Callsign lookups are a local query from now on — no network needed.';
      bar.style.width = '100%';
      bar.classList.add('done');
      stop();
      /* The tour stays up; it is the file that was the reason for hurrying,
         not the tour. Whoever is reading can finish reading. */
      start();
      return;
    }
    const p = got.progress;
    if (!p) {
      note.textContent = got.fetching
        ? 'Fetching the FCC’s amateur file…'
        : 'The FCC’s amateur file is not on this unit yet.';
      return;
    }
    if (p.phase === 'downloading') {
      const pct = p.total ? Math.min(100, Math.round(100 * p.bytes / p.total)) : null;
      bar.style.width = (pct === null ? 8 : pct) + '%';
      note.textContent = 'Fetching the FCC’s amateur file — ' +
        bytesWord(p.bytes) + (p.total ? ' of ' + bytesWord(p.total) : '') + '.';
    } else if (p.phase === 'reading') {
      bar.style.width = '100%';
      note.textContent = 'Reading it in — ' +
        (p.rows ? p.rows.toLocaleString() + ' licenses so far.' : 'just started.');
    }
  }

  skip.addEventListener('click', () => {
    stop();
    box.hidden = true;
    try { localStorage.setItem('elmer.tour.skipped', '1'); } catch (e) {}
  });
  dots.addEventListener('click', e => {
    const dot = e.target.closest('.fr-dot');
    if (!dot) return;
    show(+dot.dataset.i);
    start();                       // a press restarts the clock on this slide
  });
  box.addEventListener('mouseenter', () => { if (timer) { clearInterval(timer); timer = null; } });
  box.addEventListener('mouseleave', () => { if (!timer) start(); });

  show(0);
  start();
  look();
  watching = setInterval(look, 2000);
})();
