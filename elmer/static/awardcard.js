/* An achievement, looked at and printed.

   The Library's bottom shelf and the Lounge both show the badges a person
   holds as small plaques. Tapping one takes it down for a closer look - a
   card drawn here the way the printed page is laid out, the star, the
   name, whose it is and when - and Open builds the page as a PDF on the
   print shelf and opens it in the browser's own viewer, where the print
   button is. One never knows: an ELMER award may decorate a shack. */

(function () {
  function ensureDialog() {
    let dlg = document.getElementById('award-peek');
    if (dlg) return dlg;
    dlg = document.createElement('dialog');
    dlg.id = 'award-peek';
    dlg.className = 'award-peek';
    dlg.innerHTML =
      '<div class="award-card" id="award-card"></div>' +
      '<div class="row" style="gap:.5rem;justify-content:flex-end;margin-top:.7rem">' +
        '<span class="tiny muted" id="award-said" style="margin-right:auto"></span>' +
        '<button type="button" class="btn sm primary" id="award-open">Open the PDF &mdash; print it</button>' +
        '<button type="button" class="btn sm" id="award-close">Close</button>' +
      '</div>';
    document.body.appendChild(dlg);
    document.getElementById('award-close').addEventListener('click', () => dlg.close());
    dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
    return dlg;
  }

  /* The card, as the page is laid out: the border, the mark, the star,
     the name, whose it is, what it was for, when. */
  function cardHTML(a, who) {
    return '<div class="award-page">' +
      '<div class="award-head"><span class="award-mark">ELMER <small>radio study &amp; propagation</small></span>' +
        '<span class="award-kind">Achievement<br><small>' + escapeHTML(a.when || '') + '</small></span></div>' +
      '<div class="award-body">' +
        '<div class="award-star">&#9733;</div>' +
        '<div class="award-words">' +
          '<div class="award-name">' + escapeHTML(a.name) + '</div>' +
          '<div class="award-to">is awarded to</div>' +
          '<div class="award-who">' + escapeHTML(who || 'the operator') + '</div>' +
          '<div class="award-for">for this: ' + escapeHTML(a.description || '') + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="award-foot">A badge earned in ELMER. It marks practice, and is not a license or a claim of one.</div>' +
    '</div>';
  }

  window.showAward = function (a, who) {
    const dlg = ensureDialog();
    document.getElementById('award-card').innerHTML = cardHTML(a, who);
    document.getElementById('award-said').textContent = '';
    const open = document.getElementById('award-open');
    open.onclick = async () => {
      open.disabled = true;
      document.getElementById('award-said').textContent = 'building the page…';
      try {
        const r = await postJSON('/api/awards/print', {code: a.code});
        if (r && r.pdf) {
          document.getElementById('award-said').textContent = 'on the print shelf, and open in a new tab';
          window.open(r.pdf, '_blank', 'noopener');
        } else {
          document.getElementById('award-said').textContent = (r && r.message) || 'could not build it';
        }
      } catch (e) {
        document.getElementById('award-said').textContent = (e && (e.message || e.error)) || 'could not build it';
      }
      open.disabled = false;
    };
    if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.show();
  };

  /* Any element with data-award carries the badge as JSON; the owner's
     name is on the container. */
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-award]');
    if (!b) return;
    e.preventDefault();
    let a = null;
    try { a = JSON.parse(b.dataset.award); } catch (err) { return; }
    const box = b.closest('[data-award-who]');
    window.showAward(a, box ? box.dataset.awardWho : '');
  });
})();
