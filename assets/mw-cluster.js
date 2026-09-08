/*! MineralWatch · shared marker clustering for the Leaflet maps
 *  Requires Leaflet 1.9 and Leaflet.markercluster 1.5, loaded before this file.
 *
 *    const cl = MW.clusterGroup({radius:40, noun:"sites"}).addTo(map);
 *    cl.addLayers(markers);
 *
 *  Every marker declares its category through three Leaflet options:
 *    mwCat    category key          (one donut slice per key)
 *    mwCol    CSS colour            (slice colour)
 *    mwLabel  human-readable label  (hover breakdown)
 *  Markers should also set `bubblingMouseEvents:false` so that clicking one of them
 *  inside an exploded cluster does not count as a map click (which would fold the
 *  cluster back and close the popup).
 *
 *  Overlapping markers collapse into a small donut chart (count in the middle,
 *  slices by category). Hover lists the breakdown; click explodes the cluster
 *  into its markers (spiderfy), click again folds it back. Very large clusters
 *  zoom to their bounds instead, until they are small enough to explode.
 */
(function (global) {
  "use strict";
  var L = global.L;
  if (!L || !L.markerClusterGroup) {
    console.warn("mw-cluster.js: Leaflet.markercluster must be loaded first");
    return;
  }

  /* ---------- styles (injected once) ---------- */
  var css = [
    ".mw-cluster{background:none;border:0;cursor:pointer}",
    ".mw-cluster svg{display:block;overflow:visible;transition:transform .16s ease-out;filter:drop-shadow(0 2px 6px rgba(0,0,0,.45))}",
    ".mw-cluster:hover svg,.mw-cluster:focus-visible svg{transform:scale(1.08)}",
    ".mw-cluster text{font:700 12px/1 system-ui,-apple-system,'Segoe UI',Inter,sans-serif;letter-spacing:.01em;pointer-events:none}",
    ".leaflet-tooltip.mw-ctip{background:var(--card,#1a222c);color:var(--txt,#e6edf3);border:1px solid var(--line,#2b3644);" +
      "border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.4);padding:8px 10px;font-size:.72rem;line-height:1.5;white-space:nowrap}",
    ".leaflet-tooltip-top.mw-ctip::before{border-top-color:var(--card,#1a222c)}",
    ".mw-ctip b{display:block;font-size:.8rem;margin-bottom:4px}",
    ".mw-ctip span{display:flex;align-items:center;gap:6px}",
    ".mw-ctip span i{display:inline-block;width:8px;height:8px;border-radius:50%;flex:none}",
    ".mw-ctip span em{font-style:normal;margin-left:auto;padding-left:14px;color:var(--muted,#8b98a5);font-variant-numeric:tabular-nums}",
    ".mw-ctip small{display:block;margin-top:5px;color:var(--muted,#8b98a5);font-size:.66rem}"
  ].join("\n");
  var style = document.createElement("style");
  style.setAttribute("data-mw-cluster", "");
  style.textContent = css;
  document.head.appendChild(style);

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  /* ---------- category tally ---------- */
  function tally(cluster, order) {
    var kids = cluster.getAllChildMarkers(), by = {}, keys = [];
    for (var i = 0; i < kids.length; i++) {
      var o = kids[i].options || {}, k = o.mwCat == null ? "_" : String(o.mwCat);
      if (!by[k]) {
        by[k] = { key: k, n: 0, col: o.mwCol || "#8b98a5", label: o.mwLabel || "" };
        keys.push(k);
      }
      by[k].n++;
    }
    if (order && order.length) {
      var rank = {};
      order.forEach(function (k, i) { rank[String(k)] = i; });
      keys.sort(function (a, b) {
        var ra = rank[a] == null ? 1e9 : rank[a], rb = rank[b] == null ? 1e9 : rank[b];
        return ra - rb;
      });
    }
    return { n: kids.length, cats: keys.map(function (k) { return by[k]; }) };
  }

  /* ---------- donut icon ---------- */
  function arcPath(c, r, a0, a1) {           // angles in radians, 0 = 12 o'clock, clockwise
    var x0 = c + r * Math.sin(a0), y0 = c - r * Math.cos(a0),
        x1 = c + r * Math.sin(a1), y1 = c - r * Math.cos(a1),
        large = (a1 - a0) > Math.PI ? 1 : 0;
    return "M" + x0.toFixed(2) + " " + y0.toFixed(2) +
           " A" + r + " " + r + " 0 " + large + " 1 " + x1.toFixed(2) + " " + y1.toFixed(2);
  }

  function sizeFor(n) { return n < 10 ? 36 : n < 25 ? 42 : n < 60 ? 48 : 54; }

  function donutIcon(cluster, opts) {
    var t = tally(cluster, opts.order), n = t.n, size = sizeFor(n),
        sw = Math.max(5, Math.round(size * 0.15)),
        c = size / 2, r = c - sw / 2 - 1.5, TAU = Math.PI * 2, ring = "";

    if (t.cats.length === 1) {
      ring = '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="none" stroke="' +
             t.cats[0].col + '" stroke-width="' + sw + '"/>';
    } else {
      var gap = Math.min(2.4 / r, TAU / t.cats.length * 0.3), a = 0;  // ~2.4px between slices
      t.cats.forEach(function (k) {
        var span = k.n / n * TAU,
            a0 = a + gap / 2,
            a1 = Math.max(a + span - gap / 2, a0 + 1.2 / r);          // keep tiny slices visible
        ring += '<path d="' + arcPath(c, r, a0, a1) + '" fill="none" stroke="' + k.col +
                '" stroke-width="' + sw + '"/>';
        a += span;
      });
    }

    var html =
      '<svg width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '" aria-hidden="true">' +
        '<circle cx="' + c + '" cy="' + c + '" r="' + (c - 0.5) + '" fill="' + opts.bg + '" fill-opacity=".92"/>' +
        ring +
        '<text x="' + c + '" y="' + c + '" dy=".36em" text-anchor="middle" fill="' + opts.txt + '"' +
          (n >= 100 ? ' font-size="11"' : '') + '>' + n + '</text>' +
      '</svg>';

    return L.divIcon({ html: html, className: "mw-cluster", iconSize: [size, size], tooltipAnchor: [0, -(c + 4)] });
  }

  /* ---------- hover breakdown ---------- */
  function tipHtml(cluster, opts) {
    var t = tally(cluster, opts.order),
        html = "<b>" + t.n + " " + opts.noun + "</b>";
    t.cats.forEach(function (k) {
      html += '<span><i style="background:' + k.col + '"></i>' + (k.label || k.key) + "<em>" + k.n + "</em></span>";
    });
    html += "<small>" + (t.n > opts.explodeMax ? opts.hintZoom : opts.hintExplode) + "</small>";
    return html;
  }

  /* ---------- factory ---------- */
  function clusterGroup(opts) {
    opts = L.extend({
      radius: 40,                 // px – markers closer than this collapse together
      noun: "sites",
      order: null,                // category keys in display order (default: first seen)
      explodeMax: 40,             // bigger clusters zoom to bounds instead of spiderfying
      hintExplode: "Click to expand",
      hintZoom: "Click to zoom in",
      bg: cssVar("--bg", "#0d1117"),
      txt: cssVar("--txt", "#e6edf3"),
      legColor: cssVar("--muted", "#8b98a5")
    }, opts || {});

    var g = L.markerClusterGroup(L.extend({
      maxClusterRadius: opts.radius,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: false,
      spiderfyOnMaxZoom: false,
      spiderfyOnEveryZoom: false,
      spiderfyDistanceMultiplier: 1.15,
      spiderLegPolylineOptions: { weight: 1, color: opts.legColor, opacity: .6, interactive: false },
      iconCreateFunction: function (c) { return donutIcon(c, opts); }
    }, opts.cluster || {}));

    function canZoom(c) {
      var map = g._map;
      if (!map || map.getZoom() >= map.getMaxZoom()) return false;
      var b = c.getBounds();
      return !b.getSouthWest().equals(b.getNorthEast());   // all stacked on one point: nothing to gain
    }

    g.on("clusterclick clusterkeypress", function (e) {
      if (e.type === "clusterkeypress" && e.originalEvent && e.originalEvent.keyCode !== 13) return;
      var c = e.layer;
      c.closeTooltip();
      if (g._spiderfied === c) { c.unspiderfy(); return; }
      if (c.getChildCount() > opts.explodeMax && canZoom(c)) c.zoomToBounds({ padding: [24, 24] });
      else c.spiderfy();
    });

    g.on("clustermouseover", function (e) {
      var c = e.layer;
      if (!c.getTooltip()) {
        c.bindTooltip(function () { return tipHtml(c, opts); },
                      { direction: "top", className: "mw-ctip", opacity: 1 });
      }
      if (g._spiderfied !== c) c.openTooltip();
    });

    // The dashboards arm wheel-zoom on the first click on the map. Markers no longer
    // bubble their clicks (see header), so mirror that behaviour for marker/cluster clicks.
    g.on("click clusterclick", function () {
      var map = g._map;
      if (map && map.scrollWheelZoom && !map.scrollWheelZoom.enabled()) map.scrollWheelZoom.enable();
    });

    return g;
  }

  global.MW = global.MW || {};
  global.MW.clusterGroup = clusterGroup;
})(window);
