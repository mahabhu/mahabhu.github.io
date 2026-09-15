/* Packs the career timeline vertically without ever reordering it.

   The cards alternate sides, so in plain document flow each one occupies a
   whole row and leaves a hole the height of the card opposite it. Letting the
   two sides flow independently would close those holes but scramble the order
   along the stem, which defeats the point of a timeline.

   So each card is lifted as high as it will go subject to two rules:

     1. its node must sit at least NODE_STEP below the previous card's node,
        which is what keeps the stem strictly in order; and
     2. it must clear the previous card on its own side by GAP.

   Cards are measured, not guessed, so this holds for any content. Below the
   mobile breakpoint the layout is a single column already and is left alone.
   With JS off nothing runs and the CSS flow layout renders correctly, just
   with the larger gaps. */
(function () {
  "use strict";

  var BREAKPOINT = 768;   // matches the media query in career.html
  var NODE_STEP = 34;     // px between consecutive nodes (node is 14px tall)
  var GAP_LINES = 1.55;   // gap between same-side cards, in body lines

  var timeline = document.querySelector(".timeline");
  if (!timeline) return;

  function entries() {
    return Array.prototype.filter.call(timeline.children, function (el) {
      return el.classList.contains("timeline-entry");
    });
  }

  function unpack(items) {
    timeline.classList.remove("is-packed");
    timeline.style.height = "";
    items.forEach(function (el) { el.style.top = ""; });
  }

  function layout() {
    var items = entries();
    if (!items.length) return;

    if (window.innerWidth <= BREAKPOINT) {
      unpack(items);
      return;
    }

    // Measure in the packed state: the cards are already at their final width
    // there, so heights are correct and this costs one reflow, not two.
    timeline.classList.add("is-packed");
    var heights = items.map(function (el) { return el.offsetHeight; });

    var size = parseFloat(getComputedStyle(items[0]).fontSize) || 16;
    var gap = Math.round(size * GAP_LINES);

    var tops = [];
    var bottom = 0;
    for (var i = 0; i < items.length; i++) {
      var top = 0;
      if (i >= 1) top = Math.max(top, tops[i - 1] + NODE_STEP);      // keep order
      if (i >= 2) top = Math.max(top, tops[i - 2] + heights[i - 2] + gap);
      tops.push(top);
      bottom = Math.max(bottom, top + heights[i]);
    }

    items.forEach(function (el, i) { el.style.top = tops[i] + "px"; });
    timeline.style.height = bottom + "px";
  }

  layout();

  // Re-run when anything that changes card height changes.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(layout);
  window.addEventListener("resize", function () {
    clearTimeout(layout._t);
    layout._t = setTimeout(layout, 120);
  });
  if (window.ResizeObserver) {
    var ro = new ResizeObserver(function () { layout(); });
    entries().forEach(function (el) { ro.observe(el); });
  }
})();
