/* The dashboard's coffee card and thanks card - see elmer/supporter.py.

   A supporter is thanked, once a day, and told what the coffee meant.
   Everyone else, after ten hours of actually using ELMER, is offered the
   chance once, lightly, and then left alone for a hundred hours more.
   Neither card is a modal and neither blocks anything: a panel in the
   dashboard's flow, in the style of the update strip, that stands until
   it is put away. */

(function () {
  const box = document.getElementById('coffee');
  if (!box) return;

  function putAway(kind) {
    postJSON('/api/coffee/shown', {kind: kind}).catch(() => {});
  }

  function thanks(d) {
    box.innerHTML =
      '<div class="panel welcome">' +
        '<div class="panel-title">Thank you</div>' +
        '<p style="margin:.2rem 0 .4rem"><b>' + escapeHTML(d.title) + '</b></p>' +
        '<p class="small muted" style="margin:0">' + escapeHTML(d.line) +
          (d.others_line ? ' ' + escapeHTML(d.others_line) : '') + '</p>' +
        ((d.lines || []).length
          ? '<ul class="small" style="margin:.5rem 0 0 1.2rem">' +
              d.lines.map(l => '<li>' + escapeHTML(l) + '</li>').join('') + '</ul>'
          : '') +
      '</div>';
    putAway('thanks');
  }

  function coffee(d) {
    box.innerHTML =
      '<div class="panel welcome">' +
        '<div class="panel-title">A cup of coffee</div>' +
        '<p style="margin:.2rem 0 .6rem"><b>' + escapeHTML(d.title) + '</b> ' +
          escapeHTML(d.line) + '</p>' +
        '<div class="row" style="gap:.6rem;align-items:center;flex-wrap:wrap">' +
          '<a class="btn sm primary" id="coffee-go" href="' + escapeHTML(d.url) +
            '" target="_blank" rel="noopener">Buy the developer a coffee</a>' +
          '<button type="button" class="btn sm ghost" id="coffee-later">Thanks, not now</button>' +
          '<span class="tiny muted">' + escapeHTML(d.foot) + '</span>' +
        '</div>' +
      '</div>';
    document.getElementById('coffee-later').addEventListener('click', () => {
      putAway('coffee');
      box.innerHTML = '';
    });
    // Following the link counts as an answer too; the card stays for the
    // key that will come back.
    document.getElementById('coffee-go').addEventListener('click', () => putAway('coffee'));
  }

  api('/api/coffee').then(d => {
    if (!d || d.kind === 'thanks') return d && thanks(d);
    if (d.kind === 'coffee') coffee(d);
  }).catch(() => {});
})();
