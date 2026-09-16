/* The window that is ELMER's own, and what closing it would end.

   On Windows, ELMER opens in a window of its own and stops when that window
   closes (see elmer/window.py). By the time it has closed nothing can be
   said, so the saying is done here, ahead of time: this page knows it is
   that window, asks the server every few seconds how many people are on
   the unit - at this table, and at the other tables of a net this unit is
   running - and while there are any, says so across the top and arms the
   browser's own leave-page question, which is the one dialogue a page is
   allowed at the moment of closing. With nobody on it, nothing is said and
   the window closes like any other.

   Which window is the window: the launcher opens the first page with
   elmer_window=1 on the URL, and that is remembered in sessionStorage -
   which belongs to this window alone and follows it from page to page -
   and taken off the URL, so it is not copied into a link. */
(function () {
  const KEY = 'elmer_window';
  try {
    const url = new URL(location.href);
    if (url.searchParams.get(KEY) === '1') {
      sessionStorage.setItem(KEY, '1');
      url.searchParams.delete(KEY);
      history.replaceState(null, '', url.pathname + (url.search || '') + url.hash);
    }
    if (sessionStorage.getItem(KEY) !== '1') return;
  } catch (e) { return; }

  let people = 0;
  let banner = null;

  function say(d) {
    people = d.total || 0;
    if (!people) { if (banner) banner.hidden = true; return; }
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'window-people';
      banner.setAttribute('role', 'status');
      banner.style.cssText = 'position:sticky;top:0;z-index:60;padding:.45rem .9rem;' +
        'background:#7a4b00;color:#fff;font-size:.9rem;text-align:center';
      document.body.insertBefore(banner, document.body.firstChild);
    }
    const parts = [];
    if (d.here) parts.push(d.here + (d.here === 1 ? ' person' : ' people') + ' at this table');
    if (d.others) parts.push(d.others + (d.others === 1 ? ' person' : ' people') + ' at ' +
                             d.tables + (d.tables === 1 ? ' other table' : ' other tables') + ' of the net');
    banner.textContent = parts.join(' and ') + (people === 1 ? ' is' : ' are') +
      ' playing on this unit from another device. Stopping ELMER ends their game.';
    banner.hidden = false;
  }

  async function look() {
    try {
      const r = await fetch('/api/people', {cache: 'no-store'});
      if (r.ok) say(await r.json());
    } catch (e) { /* the server is what would be gone; nothing to say */ }
  }
  look();
  setInterval(look, 8000);

  /* The one question a page may ask as it closes. The text is the
     browser's, not ours - every browser insists on that - so the words
     are in the banner above, where they can be read first. */
  window.addEventListener('beforeunload', function (e) {
    if (!people) return;
    e.preventDefault();
    e.returnValue = '';
    return '';
  });
})();
