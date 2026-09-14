/* Fetch ahead, quietly. While a player is reading, the screen gets ready
   for what comes next: the next question's figure, the next tee's picture,
   and - while the clubhouse counts down - everything the round will show
   or say. One at a time, never twice, so a Pi hands each file out once to
   each phone and the reading is never interrupted by a fetch. */
(function () {
  const done = new Set();
  const queue = [];
  let busy = false;

  function next() {
    if (busy || !queue.length) return;
    busy = true;
    const url = queue.shift();
    const finish = () => { busy = false; setTimeout(next, 120); };
    try {
      if (/\.(jpg|jpeg|png|gif|webp)$/i.test(url)) {
        const img = new Image();
        img.onload = img.onerror = finish;
        img.src = url;
      } else {
        fetch(url, {cache: 'force-cache'}).then(r => r.blob()).then(finish, finish);
      }
    } catch (e) { finish(); }
  }

  function warm(urls) {
    (urls || []).forEach(u => { if (u && !done.has(u)) { done.add(u); queue.push(u); } });
    next();
  }

  /* Everything a round will show, fetched once the room is in the
     clubhouse or on the course. */
  let assetsAsked = false;
  async function warmRound() {
    if (assetsAsked) return;
    assetsAsked = true;
    try {
      const r = await fetch('/api/party/golf-assets');
      const d = await r.json();
      warm(d.urls || []);
    } catch (e) { assetsAsked = false; }
  }

  window.Warm = {warm: warm, round: warmRound};
})();
