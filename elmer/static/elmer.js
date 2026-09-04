/* Shared helpers: JSON calls, achievement toasts, meter colouring. */

/* Anything that goes wrong in the browser gets shipped to the server log, so
   a page that "just sits there" leaves a trace in data/elmer.log instead of
   only in a console nobody has open. */
function reportError(kind, message, extra) {
  try {
    navigator.sendBeacon
      ? navigator.sendBeacon('/api/client-error', new Blob(
          [JSON.stringify(Object.assign({ kind, message, page: location.pathname }, extra || {}))],
          { type: 'application/json' }))
      : fetch('/api/client-error', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(Object.assign({ kind, message, page: location.pathname }, extra || {}))
        });
  } catch (e) { /* reporting must never itself break the page */ }
}

window.addEventListener('error', e => {
  reportError('js-error', e.message, { line: e.lineno, stack: e.error && e.error.stack });
  banner('Something went wrong on this page. Details are in data/elmer.log.');
});
window.addEventListener('unhandledrejection', e => {
  const r = e.reason;
  reportError('promise-rejection', r && r.message ? r.message : String(r),
              { stack: r && r.stack });
});

/* A visible failure beats a page that silently stays on "Loading…". */
function banner(text) {
  let el = document.getElementById('elmer-banner');
  if (!el) {
    el = document.createElement('div');
    el.id = 'elmer-banner';
    el.className = 'errbar';
    document.body.prepend(el);
  }
  el.textContent = text;
}

async function api(url, options) {
  let res;
  try {
    res = await fetch(url, Object.assign({
      headers: { 'Content-Type': 'application/json' }
    }, options || {}));
  } catch (err) {
    reportError('network', 'fetch failed for ' + url + ': ' + err.message);
    banner('Lost contact with the ELMER server. Is it still running?');
    throw err;
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    reportError('http', url + ' -> ' + res.status, { stack: body.slice(0, 500) });
    banner('The server returned ' + res.status + ' for ' + url + '.');
    throw new Error(url + ' -> ' + res.status);
  }
  return res.json();
}

function postJSON(url, body) {
  return api(url, { method: 'POST', body: JSON.stringify(body) });
}

function toast(title, text, ms) {
  const box = document.getElementById('toaster');
  if (!box) return;
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = '<b></b><span></span>';
  el.querySelector('b').textContent = title;
  el.querySelector('span').textContent = text || '';
  box.appendChild(el);
  setTimeout(() => el.remove(), ms || 5200);
}

function showAchievements(list) {
  (list || []).forEach(a => toast('🏅 ' + a.name, a.description, 7000));
}

/* Mastery colour bands: red below 50%, amber to 80%, green above. */
function fillClass(value) {
  return value >= 0.8 ? 'fill-high' : value >= 0.5 ? 'fill-mid' : 'fill-low';
}

function meterHTML(value, thin) {
  const pct = Math.max(0, Math.min(1, value || 0)) * 100;
  return '<div class="meter' + (thin ? ' thin' : '') + '"><i class="' +
         fillClass(value) + '" style="width:' + pct.toFixed(1) + '%"></i></div>';
}

function pct(value, digits) {
  return (100 * (value || 0)).toFixed(digits === undefined ? 0 : digits) + '%';
}

function escapeHTML(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : s;
  return d.innerHTML;
}

function fmtDuration(seconds) {
  const m = Math.floor(seconds / 60), s = Math.floor(seconds % 60);
  return m + ':' + String(s).padStart(2, '0');
}

/* Render a figure: SVGs go in an <object> so they stay crisp and selectable. */
function figureHTML(url) {
  if (!url) return '';
  const tag = url.endsWith('.svg')
    ? '<object type="image/svg+xml" data="' + url + '"></object>'
    : '<img src="' + url + '" alt="pool diagram">';
  return '<div class="figure-wrap">' + tag + '</div>';
}

/* Maidenhead locator -> latitude/longitude at the centre of the square. */
function gridToLatLon(loc) {
  const g = (loc || '').trim().toUpperCase();
  if (!/^[A-R]{2}[0-9]{2}([A-X]{2})?$/.test(g)) return null;
  let lon = (g.charCodeAt(0) - 65) * 20 - 180 + (+g[2]) * 2;
  let lat = (g.charCodeAt(1) - 65) * 10 - 90 + (+g[3]);
  if (g.length === 6) {
    lon += (g.charCodeAt(4) - 65) * (2 / 24) + (1 / 24);
    lat += (g.charCodeAt(5) - 65) * (1 / 24) + (0.5 / 24);
  } else {
    lon += 1; lat += 0.5;
  }
  return { lat: +lat.toFixed(4), lon: +lon.toFixed(4), grid: g };
}


/* ---------------------------------------------------------------- explain */
/* One renderer for the explanation block, shared by the pool browser and the
   drill screen, so the two can never drift apart. */

function explanationHTML(x, opts) {
  opts = opts || {};
  if (!x) return '';
  const parts = [];

  if (x.why) {
    parts.push(sect('Why this is the answer', '<p>' + escapeHTML(x.why) + '</p>' +
      (x.watch_out ? '<p class="watchout">Watch out: ' + escapeHTML(x.watch_out) + '</p>' : '')));
  }

  if (x.concept) {
    let body = x.concept.note ? '<p>' + escapeHTML(x.concept.note) + '</p>' : '';
    if (x.concept.key_facts && x.concept.key_facts.length) {
      body += '<ul class="facts">' + x.concept.key_facts
        .map(f => '<li>' + escapeHTML(f) + '</li>').join('') + '</ul>';
    }
    if (x.concept.lab) {
      body += '<a class="btn sm ghost" href="/lab#' + x.concept.lab + '">Try it in the Lab &rarr;</a>';
    }
    parts.push(sect('Concept &mdash; ' + escapeHTML(x.section) + ' ' +
                    escapeHTML(trim(x.section_title, 90)), body));
  }

  (x.rules || []).forEach(r => {
    const blocks = r.blocks.map(b => b.indexOf(' | ') >= 0
      ? '<div class="rulerow">' + escapeHTML(b) + '</div>'
      : '<p>' + escapeHTML(b) + '</p>').join('');
    parts.push(sect('FCC rule ' + escapeHTML(r.citation) + ' &mdash; ' + escapeHTML(r.title),
      blocks + (r.truncated ? '<p class="muted tiny">(rule continues)</p>' : '') +
      '<a class="tiny" href="' + r.url + '" target="_blank" rel="noopener">read the full section on eCFR &rarr;</a>'));
  });

  if (!parts.length && !opts.alwaysNote) {
    parts.push(sect('Syllabus', '<p class="muted">No written explanation yet for this one. ' +
      'It sits in <b>' + escapeHTML(x.section) + '</b> &mdash; ' +
      escapeHTML(trim(x.section_title, 140)) + '. Add your own reasoning below and it ' +
      'will show here every time this question comes round.</p>'));
  }

  parts.push(noteEditor(x, opts));
  return '<div class="explain">' + parts.join('') + '</div>';

  function sect(head, body) {
    return '<div class="explain-sect"><div class="explain-head">' + head + '</div>' + body + '</div>';
  }
}

function trim(s, n) {
  s = s || '';
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

function noteEditor(x, opts) {
  const id = 'note-' + x.question_id;
  return '<div class="explain-sect note-sect">' +
    '<div class="explain-head">Your note' +
      (x.user_note ? '' : ' <span class="muted tiny">&mdash; optional</span>') + '</div>' +
    '<textarea class="notebox" id="' + id + '" rows="2" ' +
      'placeholder="What made this click? In your own words it sticks better. Ctrl+Enter saves, Esc returns the keyboard to the drill."' +
      ' data-pool="' + escapeHTML(opts.pool || '') + '" data-q="' + escapeHTML(x.question_id) + '">' +
      escapeHTML(x.user_note || '') + '</textarea>' +
    '<div class="row"><button class="btn sm" data-save="' + id + '">Save note</button>' +
      '<span class="tiny muted" id="' + id + '-status"></span></div>' +
    '</div>';
}

async function saveNote(box) {
  const status = document.getElementById(box.id + '-status');
  try {
    await postJSON('/api/note', {
      pool: box.dataset.pool, question_id: box.dataset.q, body: box.value
    });
    if (status) {
      status.textContent = box.value.trim() ? 'saved' : 'cleared';
      setTimeout(() => { status.textContent = ''; }, 2500);
    }
  } catch (err) {
    if (status) status.textContent = 'could not save';
  }
}

/* Delegated so it works for content rendered at any time. */
document.addEventListener('click', e => {
  const target = e.target.closest('[data-save]');
  if (target) saveNote(document.getElementById(target.dataset.save));
});

/* Inside a note box: Ctrl/Cmd+Enter saves, Escape hands the keyboard back to
   the page shortcuts. Everything else, including the space bar, is just text. */
document.addEventListener('keydown', e => {
  const box = e.target;
  if (!box || !box.classList || !box.classList.contains('notebox')) return;
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    saveNote(box);
  } else if (e.key === 'Escape') {
    saveNote(box);
    box.blur();
  }
});

/* True when the user is typing into a field, so page-level keyboard shortcuts
   stay out of the way. Without this, a space typed into the note box triggers
   "next question" instead of a space. */
function isTyping(event) {
  const el = event.target;
  if (!el) return false;
  const tag = (el.tagName || '').toUpperCase();
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' ||
         el.isContentEditable === true;
}
