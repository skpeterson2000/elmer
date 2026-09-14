/* A question's figure, on any screen - and, when the question names a
   part, that part ringed and enlarged beside the whole figure.

   "What is component 3 in figure T-2?" is answered faster with component
   3 in front of you than with a whole schematic to hunt through, and a
   room of people on phones has thirty seconds. So the part is cut out and
   enlarged - the way a finger on the page would show it - and the whole
   figure stays beside it, because the symbol means what it means from
   what it is wired to. A question that asks *which* symbol is the answer
   gets no cut-out, whatever the map says; the server decides that.

   The cut-out is the image itself, scaled and shifted inside a window,
   which needs the image's real size - so it waits for the load. */
(function () {
  function figureBlock(q, opts) {
    if (!q || !q.figure) return '';
    const o = opts || {};
    const big = o.size || 'medium';                     // 'medium' | 'large' | 'small'
    const hl = q.highlight;
    return '<div class="figwrap figwrap-' + big + '">' +
      (hl ? '<div class="figzoom" data-box="' + hl.box.join(',') + '">' +
              '<img src="' + q.figure + '" alt="">' +
              '<span class="figpart">component ' + hl.part + '</span></div>' : '') +
      '<div class="figfull"><img src="' + q.figure + '" alt="figure"></div>' +
    '</div>';
  }

  /* Once the images have loaded: scale the cut-out so the part's box
     nearly fills the window, and shift it so the box sits in the middle. */
  function fitZooms(root) {
    (root || document).querySelectorAll('.figzoom').forEach(zoom => {
      const img = zoom.querySelector('img');
      const box = (zoom.dataset.box || '').split(',').map(Number);
      if (box.length !== 4 || !img) return;
      const fit = () => {
        const iw = img.naturalWidth, ih = img.naturalHeight;
        if (!iw || !ih) return;
        const W = zoom.clientWidth, H = zoom.clientHeight;
        const bw = box[2] * iw, bh = box[3] * ih;
        const k = Math.min(W / (bw * 1.35), H / (bh * 1.35), 6);
        const cx = (box[0] + box[2] / 2) * iw * k, cy = (box[1] + box[3] / 2) * ih * k;
        img.style.width = (iw * k) + 'px';
        img.style.height = (ih * k) + 'px';
        img.style.transform = 'translate(' + (W / 2 - cx) + 'px,' + (H / 2 - cy) + 'px)';
        zoom.classList.add('fitted');
      };
      if (img.complete && img.naturalWidth) fit(); else img.addEventListener('load', fit, {once: true});
    });
  }

  window.figureBlock = figureBlock;
  window.fitZooms = fitZooms;

  /* Every screen draws by setting innerHTML, from many places; watching
     the page for a cut-out to appear is simpler than asking each of them
     to remember. A resize refits, since the window changed size. */
  function fitNew(muts) {
    for (const m of muts) {
      for (const n of m.addedNodes) {
        if (n.nodeType !== 1) continue;
        if (n.matches && n.matches('.figzoom')) fitZooms(n.parentNode);
        else if (n.querySelector && n.querySelector('.figzoom:not(.fitted)')) fitZooms(n);
      }
    }
  }
  const start = () => {
    new MutationObserver(fitNew).observe(document.body, {childList: true, subtree: true});
    fitZooms();
    window.addEventListener('resize', () => {
      document.querySelectorAll('.figzoom').forEach(z => z.classList.remove('fitted'));
      fitZooms();
    });
  };
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})();
