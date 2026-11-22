/* ============================================================================
 * GOOGLE SLIDES EXPORT — extractor (browser side)
 * ----------------------------------------------------------------------------
 * Produces a structured Intermediate Representation (IR) of the deck by reading
 * the browser's OWN computed layout — real positions, colours, fonts, text runs
 * and rasterised graphics. It is NOT a screenshot: text stays real text and
 * boxes stay real shapes. The IR is consumed by tools/gslides/export_gslides.py,
 * which builds a NATIVE Google Slides deck (editable text boxes, shapes, images)
 * via the Slides API.
 *
 * Two entry points share this one code path:
 *   • The toolbar button  → window.exportGoogleSlidesIR()  (downloads deck.gslides.json)
 *   • Headless Chrome      → open index.html?gslides=dump ; the IR lands in a
 *     <textarea id="__gsir__"> for the Python driver to read via --dump-dom.
 *
 * Coordinate space: every measurement is normalised back to the deck's 1280×720
 * design units. The Python side maps that 1:1 onto a 16:9 Slides page.
 * ========================================================================== */
(function () {
  'use strict';

  var DESIGN_W = 1280, DESIGN_H = 720;
  var nativeSeq = 0;   // one group id per native SVG diagram (see extractNativeSvg)

  // Inline (phrasing) tags whose text belongs to their parent's text block
  // rather than forming a block of their own.
  var INLINE_TAGS = { SPAN: 1, B: 1, STRONG: 1, I: 1, EM: 1, A: 1, U: 1, S: 1,
    SMALL: 1, CODE: 1, MARK: 1, SUB: 1, SUP: 1, BR: 1, WBR: 1, LABEL: 1,
    ABBR: 1, TIME: 1, KBD: 1, SAMP: 1, VAR: 1, Q: 1, CITE: 1, DFN: 1, BDI: 1 };

  function isInlineTag(el) { return !!INLINE_TAGS[el.tagName]; }
  // A decorative mark drawn as SVG in the browser (ticks, crosses, arrows, play
  // triangles) carries its Unicode character in data-glyph. Slides can't draw an
  // SVG inside a native table or text box, so the mark is exported as that character.
  function glyphOf(el) {
    return el && el.nodeType === 1 && el.tagName.toLowerCase() === 'svg' ? (el.getAttribute('data-glyph') || null) : null;
  }

  // ---- colour helpers ------------------------------------------------------
  // A brand token from :root (so a re-themed deck exports in its own colours),
  // or the Databricks default when the token is missing or not a 6-digit hex.
  function tokenHex(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return /^#[0-9a-f]{6}$/i.test(v) ? v.toUpperCase() : fallback;
  }

  function parseColor(str) {
    // returns { hex:'#rrggbb', a:0..1 } or null for fully transparent/none
    if (!str) return null;
    var m = str.match(/rgba?\(([^)]+)\)/i), p;
    if (m) {
      p = m[1].split(',').map(function (x) { return parseFloat(x.trim()); });
    } else {
      // Chrome reports a colour-mix() (a heatmap tint, a sequential step) as color(srgb r g b [/ a]) with
      // channels in 0..1. Without this the fill was dropped and the cell or legend swatch came out unshaded.
      var s = str.match(/^color\(\s*srgb\s+([^)]+)\)$/i);
      if (!s) return null;
      var parts = s[1].split('/');
      var ch = parts[0].trim().split(/\s+/).map(function (x) { return parseFloat(x) * 255; });
      var alpha = parts[1] !== undefined ? parseFloat(parts[1]) / (/%/.test(parts[1]) ? 100 : 1) : 1;
      p = [ch[0], ch[1], ch[2], alpha];
    }
    var a = p.length > 3 ? p[3] : 1;
    if (a === 0) return null;
    function hx(n) { n = Math.max(0, Math.min(255, Math.round(n))); return ('0' + n.toString(16)).slice(-2); }
    return { hex: '#' + hx(p[0]) + hx(p[1]) + hx(p[2]), a: a };
  }

  function hexToRgb(hex) {
    hex = (hex || '#000000').replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(function (c) { return c + c; }).join('');
    return { r: parseInt(hex.slice(0, 2), 16), g: parseInt(hex.slice(2, 4), 16), b: parseInt(hex.slice(4, 6), 16) };
  }
  function rgbToHex(o) {
    function h(n) { n = Math.max(0, Math.min(255, Math.round(n))); return ('0' + n.toString(16)).slice(-2); }
    return '#' + h(o.r) + h(o.g) + h(o.b);
  }

  // ---- geometry helpers ----------------------------------------------------
  // Rect of `el` in design-px, relative to the slide origin, undoing the CSS
  // transform scale applied to the stage.
  function rectOf(el, slideRect, scale) {
    var r = el.getBoundingClientRect();
    return {
      x: (r.left - slideRect.left) / scale,
      y: (r.top - slideRect.top) / scale,
      w: r.width / scale,
      h: r.height / scale
    };
  }

  // The width slack a one-line text takes (8% of its box, at least 6 px; see the caller), capped at the room the box has
  // to grow before the slide's edge on the side it grows toward. A 1120 px title grew to 1209.6 px and ran 10 px past
  // the 1280 px slide. The cap is the slide only: a card's edge is not a limit, since a line that is already full
  // needs its slack to stay on one line in Slides, and the glyphs of a card's text stay inside the card.
  function slackWithin(box, align, slideWidth) {
    var want = Math.max(box.w * 0.08, 6);
    var roomR = Math.max(0, slideWidth - (box.x + box.w)), roomL = Math.max(0, box.x);
    if (align === 'CENTER') return Math.min(want, 2 * Math.min(roomR, roomL));
    if (align === 'END') return Math.min(want, roomL);
    return Math.min(want, roomR);
  }

  function visible(el, cs) {
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (parseFloat(cs.opacity) === 0) return false;
    var r = el.getBoundingClientRect();
    if (r.width < 0.5 || r.height < 0.5) return false;
    return true;
  }

  // Copy the SVG presentation styles the browser resolved (from CSS classes and
  // custom properties) onto the clone as inline attributes, walking both trees
  // in lockstep so a serialised SVG renders identically off-page.
  var SVG_PRESENT = ['fill', 'fill-opacity', 'stroke', 'stroke-width',
    'stroke-dasharray', 'stroke-dashoffset', 'stroke-linecap', 'stroke-linejoin',
    'stroke-opacity', 'opacity', 'stop-color', 'stop-opacity',
    'font-family', 'font-size', 'font-weight', 'text-anchor', 'letter-spacing',
    'transform', 'transform-origin'];
  function inlineSvgStyles(src, clone) {
    if (src.nodeType === 1) {
      var cs = getComputedStyle(src);
      var decl = '';
      for (var i = 0; i < SVG_PRESENT.length; i++) {
        var p = SVG_PRESENT[i];
        var v = cs.getPropertyValue(p);
        // fill/stroke 'none' is meaningful (e.g. donut segments are stroke-only
        // with fill:none) — keep it, or the clone defaults to solid black.
        var keepNone = (p === 'fill' || p === 'stroke');
        if (v && (keepNone || (v !== 'none' && v !== 'normal' && v !== 'auto'))) {
          decl += p + ':' + v + ';';
        }
      }
      // Append the RESOLVED declarations AFTER any authored inline style so they
      // win the cascade. The source often colours strokes with a custom property
      // (e.g. style="stroke:var(--db-blue)"); off-page that var is undefined, so
      // if the authored value came last it would resolve to stroke:none and the
      // whole graphic (donut ring, chart line…) would rasterise blank.
      if (decl) clone.setAttribute('style', (clone.getAttribute('style') || '') + ';' + decl);
    }
    var sc = src.children || [], cc = clone.children || [];
    for (var j = 0; j < sc.length && j < cc.length; j++) inlineSvgStyles(sc[j], cc[j]);
  }

  // Alt text for an image element, so the exporter can name it (a --no-images placeholder
  // reads "Figure omitted from this export: <alt>"): img alt, else aria-label, else the
  // svg <title>. Empty when the author gave none.
  function altOf(node) {
    if (!node) return '';
    var a = (node.getAttribute && (node.getAttribute('alt') || node.getAttribute('aria-label'))) || '';
    if (!a && node.querySelector) { var t = node.querySelector('title'); if (t) a = t.textContent || ''; }
    return String(a).replace(/\s+/g, ' ').trim();
  }

  // ---- rasterisation (img / svg / canvas → PNG data URL) -------------------
  function rasterize(el, cssW, cssH) {
    var scaleUp = 2; // render at 2× for crisp images
    try {
      if (el.tagName === 'CANVAS') return el.toDataURL('image/png');

      var cv = document.createElement('canvas');
      cv.width = Math.max(1, Math.round(cssW * scaleUp));
      cv.height = Math.max(1, Math.round(cssH * scaleUp));
      var ctx = cv.getContext('2d');

      if (el.tagName === 'IMG') {
        // Draw the already-decoded image element (works for png/jpg/gif/svg-img
        // because it's same-origin under file://). SVG <img> often reports
        // naturalWidth 0, so scale to the CSS box regardless.
        if (!el.complete) return null;
        ctx.drawImage(el, 0, 0, cv.width, cv.height);
        return cv.toDataURL('image/png');
      }

      if (el.tagName === 'svg' || el.tagName === 'SVG' || (el.namespaceURI && el.namespaceURI.indexOf('svg') >= 0)) {
        // Serialise the live SVG (inherits computed geometry) and paint it.
        // CSS-class/var styling (stroke colours, dash arrays) is lost on
        // serialisation, so inline the computed presentation styles first —
        // otherwise everything falls back to black fill.
        var clone = el.cloneNode(true);
        inlineSvgStyles(el, clone);
        if (!clone.getAttribute('xmlns')) clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        clone.setAttribute('width', cssW);
        clone.setAttribute('height', cssH);
        var xml = new XMLSerializer().serializeToString(clone);
        var svg64 = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(xml)));
        // Synchronous draw is impossible for a data-URL <img>; caller handles
        // svg via the async path (rasterizeAsync). This branch is a fallback.
        return { deferred: svg64, w: cv.width, h: cv.height };
      }
    } catch (e) { /* tainted canvas or serialise failure → skip image */ }
    return null;
  }

  // Async rasterise (needed for inline <svg> and any element we paint via an
  // <img> data URL). Resolves to a PNG data URL or null.
  function rasterizeAsync(el, cssW, cssH) {
    return new Promise(function (resolve) {
      var sync = rasterize(el, cssW, cssH);
      if (typeof sync === 'string') return resolve(sync);
      if (!sync || !sync.deferred) return resolve(null);
      var img = new Image();
      img.onload = function () {
        try {
          var cv = document.createElement('canvas');
          cv.width = sync.w; cv.height = sync.h;
          cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height);
          resolve(cv.toDataURL('image/png'));
        } catch (e) { resolve(null); }
      };
      img.onerror = function () { resolve(null); };
      img.src = sync.deferred;
    });
  }

  // Paint a detached, style-inlined <svg> clone to a PNG data URL (2x, like rasterize).
  function rasterizeMarkup(clone, cssW, cssH) {
    return new Promise(function (resolve) {
      try {
        clone.setAttribute('width', cssW);
        clone.setAttribute('height', cssH);
        if (!clone.getAttribute('xmlns')) clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        var xml = new XMLSerializer().serializeToString(clone);
        var img = new Image();
        img.onload = function () {
          try {
            var cv = document.createElement('canvas');
            cv.width = Math.max(1, Math.round(cssW * 2)); cv.height = Math.max(1, Math.round(cssH * 2));
            cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height);
            resolve(cv.toDataURL('image/png'));
          } catch (e) { resolve(null); }
        };
        img.onerror = function () { resolve(null); };
        img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(xml)));
      } catch (e) { resolve(null); }
    });
  }

  // ---- text-run extraction -------------------------------------------------
  // Collect styled runs from a text-leaf block: each descendant text node
  // becomes a run carrying its nearest element's computed style.
  // Line-breaking, block-level display types: a box of this kind starts on its
  // own line, so two text nodes under DIFFERENT such boxes are on different
  // lines. (inline / inline-block flow inline and are deliberately absent.)
  var LINE_BREAKING = { block: 1, flex: 1, grid: 1, 'list-item': 1, table: 1,
    'table-row': 1, 'table-caption': 1, 'flow-root': 1 };

  function collectRuns(block) {
    var runs = [];
    var prevOwner = null;                // line box the previous text run lived in
    // The nearest ancestor (up to the leaf) that puts this text on its own line:
    // a block-level box, or a flex/grid ITEM whose container stacks its items
    // (column direction, or wrapping). Two text nodes with DIFFERENT owners sit
    // on separate lines and get a break between them — e.g. a card's bare title
    // text node vs its display:block <small> subtitle, or a flex-column donut
    // centre's "4%" vs "aphantasia". Text that merely soft-wraps keeps ONE owner
    // (its paragraph), so Slides is free to re-wrap it — we never harden that.
    function lineOwner(node) {
      var el = node.parentElement;
      while (el && el !== block.parentElement) {
        if (el === block) return block;                 // reached the leaf itself
        var pe = el.parentElement;
        var pd = pe ? getComputedStyle(pe).display : '';
        if (pd === 'flex' || pd === 'inline-flex') {
          // el is a flex ITEM. Chrome BLOCKIFIES a flex item's own `display`
          // (a row's inline <b> reports 'block'), so its display can't be
          // trusted — the container's axis decides: a column (or a wrapping
          // row) puts items on their own lines; a plain row keeps them on one.
          var fpc = getComputedStyle(pe);
          if ((fpc.flexDirection || '').indexOf('column') === 0 ||
              (fpc.flexWrap || '').indexOf('wrap') === 0) return el;
        } else if (pd === 'grid' || pd === 'inline-grid') {
          return el;                                    // grid item → its own cell/line
        } else if (LINE_BREAKING[getComputedStyle(el).display]) {
          return el;                                    // real block-level box in normal flow
        }
        el = pe;
      }
      return block;
    }
    function walk(node) {
      if (node.nodeType === 3) { // text
        var pe = node.parentElement;
        var cs = getComputedStyle(pe);
        // `white-space: pre | pre-wrap` keeps every space AND newline (code
        // blocks, terminals); `pre-line` keeps newlines but collapses runs of
        // spaces; everything else collapses all whitespace to single spaces.
        var ws = cs.whiteSpace || 'normal';
        var pre = ws.indexOf('pre') === 0;
        var t = pre
          ? (ws === 'pre-line' ? node.nodeValue.replace(/[ \t\f]+/g, ' ')
                               : node.nodeValue.replace(/\r\n?/g, '\n'))
          : node.nodeValue.replace(/\s+/g, ' ');
        if (!t) return;
        // Whitespace-only text node: the browser keeps it only as an inter-word
        // space between inline content. Between flex/grid items, or adjacent to a
        // block-level sibling (e.g. the newline between two <li> in a list leaf),
        // it collapses to nothing — drop it so it can't become a blank bullet.
        // In a pre context every space and newline is significant — never drop.
        if (!pre && !node.nodeValue.trim()) {
          var par = node.parentElement;
          // the layout whitespace inside an icon's svg (between its tags) is not text: it would add a space to the cell
          if (par && par.closest && par.closest('svg')) return;
          var pdw = par ? getComputedStyle(par).display : '';
          var blockSib = function (sib) {
            return sib && sib.nodeType === 1 && !isInlineTag(sib) &&
                   !/^inline/.test(getComputedStyle(sib).display);
          };
          if (pdw === 'flex' || pdw === 'inline-flex' || pdw === 'grid' || pdw === 'inline-grid' ||
              blockSib(node.previousElementSibling) || blockSib(node.nextElementSibling)) return;
        }
        // New line box than the previous run? Insert a hard break so stacked
        // pieces don't concatenate onto one line ("...salesSynthetic · 156 wks").
        var owner = lineOwner(node);
        if (prevOwner && owner !== prevOwner) runs.push({ text: '\n', br: true });
        prevOwner = owner;
        // List membership: text under an <li> within this leaf becomes a NATIVE
        // Slides bullet (the drawn ::before dot is suppressed for such <li>). Carry
        // the ordered flag and nesting level so the driver picks glyph + indent.
        var li = pe.closest ? pe.closest('li') : null;
        var inList = li && block.contains(li);
        var listLevel = 0, ordered = false;
        // A list item whose marker the CSS removes (list-style: none, with the bullet drawn as its own element) is
        // a list item for the spacing only: a native bullet on top of the drawn one doubled every dot.
        var bullet = !!inList && getComputedStyle(li).listStyleType !== 'none';
        if (inList) {
          ordered = !!li.closest('ol');
          for (var lp = li; lp && lp !== block.parentElement; lp = lp.parentElement) {
            if (lp.tagName === 'UL' || lp.tagName === 'OL') listLevel++;
          }
          listLevel = Math.max(0, listLevel - 1);
        }
        var col = parseColor(cs.color) || { hex: '#000000' };
        // Gradient-clipped text renders transparent; fall back to a visible ink.
        if ((cs.webkitTextFillColor && parseColor(cs.webkitTextFillColor) === null) ||
            cs.webkitBackgroundClip === 'text' || cs.backgroundClip === 'text') {
          col = parseColor(cs.color) || { hex: tokenHex('--db-orange', '#FF3621') };
          if (col.a < 0.05) col = { hex: tokenHex('--db-orange', '#FF3621'), a: 1 };
        }
        var props = {
          size: pxToPt(parseFloat(cs.fontSize)),
          font: primaryFont(cs.fontFamily),
          // <sup> / <sub> (vertical-align super | sub) → Slides' baseline offset
          baselineOffset: cs.verticalAlign === 'super' ? 'SUPERSCRIPT' : (cs.verticalAlign === 'sub' ? 'SUBSCRIPT' : 'NONE'),
          bold: (parseInt(cs.fontWeight, 10) || 400) >= 600,
          italic: cs.fontStyle === 'italic',
          color: col.hex,
          letterSpacing: parseFloat(cs.letterSpacing) || 0,
          upper: cs.textTransform === 'uppercase',
          list: !!inList,
          bullet: bullet,
          ordered: ordered,
          listLevel: listLevel
        };
        var pushRun = function (txt) {
          var r = { text: txt };
          for (var k in props) r[k] = props[k];
          runs.push(r);
        };
        // A pre text node can span several lines; split it so each line becomes
        // its own paragraph (hard break between), preserving blank lines.
        if (pre && t.indexOf('\n') >= 0) {
          var segs = t.split('\n');
          for (var si = 0; si < segs.length; si++) {
            if (si > 0) runs.push({ text: '\n', br: true });
            if (segs[si] !== '') pushRun(segs[si]);
          }
        } else {
          pushRun(t);
        }
      } else if (node.nodeType === 1) {
        if (node.tagName === 'BR') { runs.push({ text: '\n', br: true }); return; }
        var gl = glyphOf(node);
        if (gl) {
          var gpe = getComputedStyle(node.parentElement), gcs = getComputedStyle(node);
          var gcol = parseColor(gcs.color) || { hex: '#000000' };
          // The play triangle sits in a flex gap in the browser; keep the space Slides needs.
          // Marks DM Sans lacks get a Google symbol font (Slides serves it); arrows keep the
          // brand font. U+FE0E asks for text presentation so ▶ and ↔ don't turn into emoji.
          var gSym = /[\u2713\u2715\u25d0\u25b6]/.test(gl);
          runs.push({ text: gl + '\uFE0E' + (gl === '\u25b6' ? ' ' : ''), size: pxToPt(parseFloat(gpe.fontSize)),
                      // arrows too: DM Sans has no ↑↓; an explicit symbol face keeps the run's advance (Slides' fallback overlapped)
                      font: (gSym || /[\u2190-\u21ff]/.test(gl)) ? 'Noto Sans Symbols 2' : primaryFont(gpe.fontFamily),
                      bold: (parseInt(gpe.fontWeight, 10) || 400) >= 600, italic: false, color: gcol.hex,
                      letterSpacing: 0, upper: false, list: false, ordered: false, listLevel: 0 });
          return;
        }
        var cs2 = getComputedStyle(node);
        if (cs2.display === 'none' || cs2.visibility === 'hidden') return;
        for (var i = 0; i < node.childNodes.length; i++) walk(node.childNodes[i]);
      }
    }
    for (var i = 0; i < block.childNodes.length; i++) walk(block.childNodes[i]);
    // apply uppercase transform to run text
    runs.forEach(function (r) { if (r.upper && r.text) r.text = r.text.toUpperCase(); });
    return runs;
  }

  // The first family of the stack, as Slides knows it (it has the Google Fonts). A
  // generic first entry falls back to the deck's own --font / --mono family.
  function rootFamily(token, dflt) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(token) || '';
    return v.split(',')[0].replace(/["']/g, '').trim() || dflt;
  }
  // Families Google Slides serves. A brand face outside this list (GitLab Mono, a
  // customer's serif) is replaced by the closest hosted one, so Slides and PowerPoint
  // never fall back to an arbitrary serif or sans. The map is reported as IR
  // `fontSubstitutions` (requested → used) so --preview can show it.
  var GOOGLE_HOSTED = ['DM Sans', 'DM Mono', 'Inter', 'Roboto', 'Roboto Mono', 'Open Sans', 'Lato',
    'Source Sans 3', 'Source Code Pro', 'JetBrains Mono', 'IBM Plex Mono', 'Noto Sans Mono',
    'Noto Sans Symbols 2', 'Fira Code', 'Space Mono'];
  var FONT_SUBS = {};
  function hostedName(name) {
    for (var i = 0; i < GOOGLE_HOSTED.length; i++) if (GOOGLE_HOSTED[i].toLowerCase() === name.toLowerCase()) return GOOGLE_HOSTED[i];
    return null;
  }
  function primaryFont(family) {
    var parts = (family || '').split(',').map(function (x) { return x.replace(/["']/g, '').trim(); }).filter(Boolean);
    var first = parts[0] || '';
    var generic = /^(ui-monospace|monospace|sans-serif|serif|system-ui|-apple-system|BlinkMacSystemFont)$/i;
    var mono = /mono|code|console|courier|menlo|consolas/i.test(first);
    var want = first, fallbacks = parts.slice(1);
    if (!first || generic.test(first)) {
      want = mono ? rootFamily('--mono', 'DM Mono') : rootFamily('--font', 'DM Sans');
      fallbacks = [];
    }
    var used = hostedName(want);
    if (!used) {
      for (var i = 0; i < fallbacks.length && !used; i++) used = hostedName(fallbacks[i]);
    }
    if (!used) used = mono || /mono/i.test(want) ? 'Roboto Mono' : 'Inter';
    if (used !== want) FONT_SUBS[want] = used;
    return used;
  }

  function pxToPt(px) { return Math.round(px * 0.5625 * 100) / 100; }

  // The space a table cell's text must clear for the icons above it: the bottom of the lowest icon (image, svg or
  // canvas, not a glyph) that ends above the text's first line. Returns the gap from the cell's content top (its
  // padding and top border excluded) to the text, in pt; 0 when no icon sits above the text, or no text is there.
  function cellLeadPt(cellEl, cellRect, slideRect, scale, tableEl) {
    var icons = [].filter.call(cellEl.querySelectorAll('img, svg, canvas'), function (g) {
      return !glyphOf(g) && g.closest('table') === tableEl && visible(g, getComputedStyle(g));
    });
    if (!icons.length) return 0;
    var txt = textNodeRect(cellEl, slideRect, scale);
    if (!txt) return 0;
    var iconBottom = -Infinity;
    icons.forEach(function (g) { var ir = rectOf(g, slideRect, scale); iconBottom = Math.max(iconBottom, ir.y + ir.h); });
    if (iconBottom > txt.y + 1) return 0;            // an icon beside or below the text is not a lead
    var cs = getComputedStyle(cellEl);
    var contentTop = cellRect.y + (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.paddingTop) || 0);
    return Math.max(0, pxToPt(txt.y - contentTop));
  }

  // Does the element hold its own text with only inline children?
  function isTextLeaf(el) {
    var cs0 = getComputedStyle(el);
    var disp = cs0.display;
    // A UL/OL whose items carry only inline content is kept as ONE text leaf, so
    // it exports as a single NATIVE bulleted list (its <li> become paragraphs,
    // bulleted together and editable in Slides) rather than N separate boxes. If
    // any <li> holds block/flex content (an icon tile, a nested list, a card),
    // fall through and recurse — each item still gets its own native bullet.
    if (el.tagName === 'UL' || el.tagName === 'OL') {
      var simpleList = true, sawItem = false;
      for (var li = el.firstElementChild; li; li = li.nextElementSibling) {
        var lics = getComputedStyle(li);
        if (lics.display === 'none' || lics.visibility === 'hidden') continue;
        if (li.tagName !== 'LI') { simpleList = false; break; }
        sawItem = true;
        for (var ch = li.firstElementChild; ch; ch = ch.nextElementSibling) {
          if (!ch.textContent.trim()) continue;
          var chd = getComputedStyle(ch).display;
          if (!isInlineTag(ch) && chd !== 'inline' && chd !== 'inline-block') { simpleList = false; break; }
        }
        if (!simpleList) break;
      }
      if (sawItem && simpleList) return true;
    }
    // A flex/grid container that SPREADS its children apart (space-between /
    // -around / -evenly — e.g. the footer: copyright left, page-number right)
    // must not merge them into one text box.
    if (disp === 'flex' || disp === 'inline-flex' || disp === 'grid' || disp === 'inline-grid') {
      if (/space-(between|around|evenly)/.test(cs0.justifyContent)) return false;
      // A flex-ROW or grid that lays text-bearing children out as side-by-side
      // columns (e.g. a gantt month header Jan|Feb|Mar…) must not merge them
      // into one centred run — recurse so each column becomes its own positioned
      // text box. Guarded to when there is no bare text node directly in the
      // container (recursion would drop that) and 2+ element children carry text,
      // so a flex row like a legend "swatch + label + value" stays one block.
      var isRow = (disp === 'grid' || disp === 'inline-grid') || !/column/.test(cs0.flexDirection || '');
      if (isRow) {
        var bareText = false, textKids = 0;
        for (var q = 0; q < el.childNodes.length; q++) {
          var k = el.childNodes[q];
          if (k.nodeType === 3 && k.nodeValue.trim()) bareText = true;
          else if (k.nodeType === 1 && k.textContent.trim()) {
            var kcs = getComputedStyle(k);
            if (kcs.display !== 'none' && kcs.visibility !== 'hidden') textKids++;
          }
        }
        if (!bareText && textKids >= 2) return false;
      }
    }
    var hasText = false, hasBlockChild = false;
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3 && n.nodeValue.trim()) hasText = true;
      else if (n.nodeType === 1 && glyphOf(n)) hasText = true;
      else if (n.nodeType === 1) {
        // A child taken out of normal flow (absolute/fixed positioning) carries
        // its text somewhere else on the slide (e.g. a chart's value chip sits
        // above its bar) — recurse so it becomes its own correctly-placed box.
        var cn = getComputedStyle(n);
        if (cn.position === 'absolute' || cn.position === 'fixed') return false;
        if (isInlineTag(n)) {
          if (n.textContent.trim()) hasText = true;
        } else {
          var d = cn.display;
          if (d === 'inline' || d === 'inline-block') { if (n.textContent.trim()) hasText = true; }
          else if (n.textContent.trim()) hasBlockChild = true;
        }
      }
    }
    return hasText && !hasBlockChild;
  }

  // Horizontal + vertical alignment of the text WITHIN el — honouring flex/grid
  // centring (justify-content / align-items), not just text-align, so a
  // flex-centred number lands centred rather than top-left.
  function alignmentOf(el, cs) {
    var disp = cs.display, h = 'START', v = 'MIDDLE';
    var tok = { start: 'START', center: 'CENTER', end: 'END' };
    function pick(v) { return /center/.test(v) ? 'center' : (/(flex-end|end|right)/.test(v) ? 'end' : 'start'); }
    if (disp === 'flex' || disp === 'inline-flex') {
      var col = (cs.flexDirection || '').indexOf('column') === 0;
      var main = pick(cs.justifyContent || ''), cross = pick(cs.alignItems || '');
      h = tok[col ? cross : main];
      v = { start: 'TOP', center: 'MIDDLE', end: 'BOTTOM' }[col ? main : cross];
    } else {
      var a = cs.textAlign;
      h = a === 'center' ? 'CENTER' : ((a === 'right' || a === 'end') ? 'END' : (a === 'justify' ? 'JUSTIFIED' : 'START'));
    }
    return { h: h, v: v || 'MIDDLE' };
  }

  // Tight bounding box of just the TEXT NODES inside el (via Range), in design
  // px relative to the slide. Excludes leading images/inline blocks (e.g. the
  // footer's brand mark), so a text box lands on the text — not on top of the
  // icon that precedes it. Returns null if el has no rendered text.
  function textNodeRect(el, slideRect, scale) {
    var range = document.createRange();
    var L = Infinity, T = Infinity, R = -Infinity, B = -Infinity, found = false;
    function walk(n) {
      if (n.nodeType === 3) {
        if (!n.nodeValue.trim()) return;
        range.selectNodeContents(n);
        var rects = range.getClientRects();
        for (var i = 0; i < rects.length; i++) {
          var r = rects[i];
          if (r.width < 0.1 && r.height < 0.1) continue;
          found = true;
          L = Math.min(L, r.left); T = Math.min(T, r.top);
          R = Math.max(R, r.right); B = Math.max(B, r.bottom);
        }
      } else if (n.nodeType === 1) {
        var cs = getComputedStyle(n);
        if (cs.display === 'none' || cs.visibility === 'hidden') return;
        // a glyph icon (an svg with data-glyph, e.g. the ▶ of a run button) is part of the text's measure
        if (glyphOf(n)) {
          var gr = n.getBoundingClientRect();
          if (gr.width >= 0.1 || gr.height >= 0.1) {
            found = true;
            L = Math.min(L, gr.left); T = Math.min(T, gr.top);
            R = Math.max(R, gr.right); B = Math.max(B, gr.bottom);
          }
          return;
        }
        for (var c = 0; c < n.childNodes.length; c++) walk(n.childNodes[c]);
      }
    }
    walk(el);
    if (!found) return null;
    return { x: (L - slideRect.left) / scale, y: (T - slideRect.top) / scale,
             w: (R - L) / scale, h: (B - T) / scale };
  }

  // Slides presets the extractor can emit for a clip-path polygon (IR field `shape`). Google draws a
  // preset at its DEFAULT adjust values, and the API cannot change them, so the HTML polygon must be
  // that same shape: CHEVRON and HOME_PLATE point 0.5*min(w,h) deep; RIGHT_ARROW has a shaft over the
  // middle half of its height and a head 0.5*min(w,h) long. Vertices in px from the box's top-left.
  var SLIDES_PRESETS = {
    CHEVRON: function (w, h) { var d = Math.min(w, h) / 2; return [[0, 0], [w - d, 0], [w, h / 2], [w - d, h], [0, h], [d, h / 2]]; },
    HOME_PLATE: function (w, h) { var d = Math.min(w, h) / 2; return [[0, 0], [w - d, 0], [w, h / 2], [w - d, h], [0, h]]; },
    RIGHT_ARROW: function (w, h) {
      var hb = w - Math.min(w, h) / 2;
      return [[0, h * 0.25], [hb, h * 0.25], [hb, 0], [w, h / 2], [hb, h], [hb, h * 0.75], [0, h * 0.75]];
    }
  };
  var SLIDES_PRESET_BY_SIDES = { 5: 'HOME_PLATE', 6: 'CHEVRON', 7: 'RIGHT_ARROW' };

  // A clip-path polygon() that is one of SLIDES_PRESETS, vertex for vertex (order-free, 1px). Returns
  // { shape, clip } (clip = the polygon in slide design px), { shape: null, mismatch } for a polygon of
  // a preset's size that is not that preset (drawn as a rectangle, and reported), or null.
  function clipShape(cs, rr) {
    var m = /^polygon\((.*)\)$/.exec(cs.clipPath || '');
    if (!m) return null;
    var body = m[1].replace(/calc\(([^)]*)\)/g, function (c) { return c.replace(/\s+/g, ''); });
    var pts = body.split(',').map(function (pair) {
      var t = pair.trim().split(/\s+/);
      if (t.length !== 2) return null;
      // computed values keep calc(100% - Npx) as written: evaluate the two forms the deck uses
      function ln(tok, base) {
        var c = /^calc\(\s*(-?[\d.]+)%\s*([+-])\s*([\d.]+)px\s*\)$/.exec(tok);
        if (c) { var v = parseFloat(c[1]) / 100 * base; return c[2] === '-' ? v - parseFloat(c[3]) : v + parseFloat(c[3]); }
        var f = parseFloat(tok) || 0; return /%$/.test(tok) ? f / 100 * base : f;
      }
      return [ln(t[0], rr.w), ln(t[1], rr.h)];
    });
    if (pts.some(function (p) { return !p; })) return null;
    var name = SLIDES_PRESET_BY_SIDES[pts.length];
    if (!name) return null;
    var want = SLIDES_PRESETS[name](rr.w, rr.h);
    var same = want.every(function (e) {
      return pts.some(function (a) { return Math.abs(a[0] - e[0]) < 1 && Math.abs(a[1] - e[1]) < 1; });
    });
    if (!same) return { shape: null, mismatch: pts.length + '-point clip-path matches no Slides preset (' + name + ' needs its default proportions)' };
    return { shape: name, clip: pts.map(function (p) { return [rr.x + p[0], rr.y + p[1]]; }) };
  }

  // The accent edge drawn by an inset box-shadow on one side ("inset 0 5px 0 0 colour" is the top):
  // {w, c} for that side, or null. Computed styles serialise the colour and offsets in either order.
  function insetAccent(str, side) {
    if (!str || str === 'none') return null;
    var parts = str.split(/,(?![^(]*\))/);
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i].replace(/^\s+|\s+$/g, '');
      if (!/(^|\s)inset(\s|$)/.test(part)) continue;
      var colM = part.match(/(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})/);
      var nums = part.replace(/(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})/, ' ').match(/-?[\d.]+(?=px)/g);
      if (!colM || !nums || nums.length < 4) continue;
      var x = parseFloat(nums[0]), y = parseFloat(nums[1]), blur = parseFloat(nums[2]), spread = parseFloat(nums[3]);
      if (blur !== 0 || spread !== 0) continue;
      var w = side === 'top' ? y : side === 'bottom' ? -y : side === 'left' ? x : -x;
      var c = parseColor(colM[1]);
      if (w > 0 && c && (side === 'top' || side === 'bottom' ? x === 0 : y === 0)) return { w: w, c: c };
    }
    return null;
  }
  // First outer box-shadow of a computed box-shadow string, as the IR `shadow`
  // ({blur, dx, dy} design px, color hex, alpha). Null when there is none.
  function parseShadow(str) {
    if (!str || str === 'none') return null;
    var first = str.split(/,(?![^(]*\))/)[0].replace(/^\s+|\s+$/g, '');
    if (/^inset/.test(first)) return null;
    var m = first.match(/(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})\s+(-?[\d.]+)px\s+(-?[\d.]+)px\s*(-?[\d.]+)?px?/) ||
            first.match(/(-?[\d.]+)px\s+(-?[\d.]+)px\s+(-?[\d.]+)?px?\s+(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})/);
    if (!m) return null;
    var colStr = /^[-\d.]/.test(m[1]) ? m[4] : m[1];
    var nums = /^[-\d.]/.test(m[1]) ? [m[1], m[2], m[3]] : [m[2], m[3], m[4]];
    var c = parseColor(colStr) || { hex: '#000000', a: 0.15 };
    var alpha = c.a == null ? 1 : c.a;
    if (!(alpha > 0)) return null;
    return { blur: parseFloat(nums[2]) || 0, dx: parseFloat(nums[0]) || 0, dy: parseFloat(nums[1]) || 0,
             color: c.hex, alpha: alpha };
  }

  // Axis-aligned linear-gradient() → N solid rects whose fillAlpha follows the gradient
  // (native shapes: Slides can't fill with a gradient, and a full-slide PNG would be
  // flattened onto the background by the exporter, hiding the photo under a scrim).
  // Returns null for diagonal or unparseable gradients (the PNG path handles those).
  function gradientStrips(bgCss, x, y, w, h) {
    var g = (bgCss || '').match(/linear-gradient\((.*)\)\s*$/);
    if (!g) return null;
    var parts = g[1].split(/,(?![^(]*\))/).map(function (t) { return t.trim(); });
    var ang = 180;
    if (/deg$/.test(parts[0])) ang = parseFloat(parts.shift());
    else if (/^to /.test(parts[0])) { var dirs = { 'to top': 0, 'to right': 90, 'to bottom': 180, 'to left': 270 }; ang = dirs[parts.shift()]; }
    ang = ((ang % 360) + 360) % 360;
    if ([0, 90, 180, 270].indexOf(ang) < 0) return null;
    var stops = [];
    parts.forEach(function (t) {
      var sm = t.match(/^(.*?)\s+(-?[\d.]+)%$/), col = sm ? sm[1] : t, pc = parseColor(col);
      if (pc) stops.push({ r: parseInt(pc.hex.slice(1, 3), 16), g: parseInt(pc.hex.slice(3, 5), 16),
                           b: parseInt(pc.hex.slice(5, 7), 16), a: pc.a == null ? 1 : pc.a, p: sm ? parseFloat(sm[2]) / 100 : null });
    });
    if (stops.length < 2) return null;
    if (stops[0].p == null) stops[0].p = 0;
    if (stops[stops.length - 1].p == null) stops[stops.length - 1].p = 1;
    for (var i = 1; i < stops.length - 1; i++) if (stops[i].p == null) stops[i].p = i / (stops.length - 1);
    var N = 32, out = [], horiz = ang === 90 || ang === 270;
    for (var k = 0; k < N; k++) {
      var t = (k + 0.5) / N;
      if (ang === 270 || ang === 0) t = 1 - t;      // gradient runs right→left / bottom→top
      var a = stops[0], b = stops[stops.length - 1];
      for (var j = 0; j < stops.length - 1; j++) {
        if (t >= stops[j].p && t <= stops[j + 1].p) { a = stops[j]; b = stops[j + 1]; break; }
      }
      var f = b.p === a.p ? 0 : Math.min(1, Math.max(0, (t - a.p) / (b.p - a.p)));
      var R = Math.round(a.r + (b.r - a.r) * f), G = Math.round(a.g + (b.g - a.g) * f), B = Math.round(a.b + (b.b - a.b) * f);
      var A = a.a + (b.a - a.a) * f;
      if (A <= 0.001) continue;
      var hex = '#' + [R, G, B].map(function (v) { return ('0' + v.toString(16)).slice(-2); }).join('');
      var rx = horiz ? x + k * w / N : x, ry = horiz ? y : y + k * h / N;
      out.push({ type: 'rect', x: rx, y: ry, w: horiz ? w / N : w, h: horiz ? h : h / N,
                 fill: hex, fillAlpha: A, radius: 0, ellipse: false, border: null });
    }
    return out;
  }

  // A CSS linear-gradient() painted onto a canvas, sized to the box (2x). Used for
  // gradient-only boxes (overlays, scrims) that Slides can't fill natively.
  // Angle and colour stops are read from the computed background-image; an
  // unparseable gradient resolves to null (the box is then skipped, not flattened).
  function paintGradient(bgCss, cssW, cssH) {
    return new Promise(function (resolve) {
      try {
        var g = bgCss.match(/linear-gradient\((.*)\)\s*$/);
        if (!g) return resolve(null);
        var parts = g[1].split(/,(?![^(]*\))/).map(function (x) { return x.trim(); });
        var ang = 180;
        if (/deg$/.test(parts[0])) { ang = parseFloat(parts.shift()); }
        else if (/^to /.test(parts[0])) {
          var dirs = { 'to top': 0, 'to right': 90, 'to bottom': 180, 'to left': 270 };
          ang = dirs[parts.shift()] || 180;
        }
        var stops = [];
        parts.forEach(function (ptxt, i) {
          var sm = ptxt.match(/^(.*?)\s+(-?[\d.]+)%$/);
          var col = sm ? sm[1] : ptxt, pos = sm ? parseFloat(sm[2]) / 100 : null;
          var pc = parseColor(col);
          if (!pc) return;
          stops.push({ c: 'rgba(' + parseInt(pc.hex.slice(1,3),16) + ',' + parseInt(pc.hex.slice(3,5),16) + ',' +
                          parseInt(pc.hex.slice(5,7),16) + ',' + (pc.a == null ? 1 : pc.a) + ')', p: pos });
        });
        if (stops.length < 2) return resolve(null);
        if (stops[0].p == null) stops[0].p = 0;
        if (stops[stops.length - 1].p == null) stops[stops.length - 1].p = 1;
        for (var i = 1; i < stops.length - 1; i++) if (stops[i].p == null) stops[i].p = i / (stops.length - 1);
        var W = Math.max(1, Math.round(cssW * 2)), H = Math.max(1, Math.round(cssH * 2));
        var cv = document.createElement('canvas'); cv.width = W; cv.height = H;
        var ctx = cv.getContext('2d');
        // CSS gradient line for angle a through the box centre
        var a = ang * Math.PI / 180, sx = Math.sin(a), sy = -Math.cos(a);
        var half = (Math.abs(W * sx) + Math.abs(H * sy)) / 2;
        var cx = W / 2, cy = H / 2;
        var lg = ctx.createLinearGradient(cx - sx * half, cy - sy * half, cx + sx * half, cy + sy * half);
        stops.forEach(function (st) { lg.addColorStop(Math.min(1, Math.max(0, st.p)), st.c); });
        ctx.fillStyle = lg; ctx.fillRect(0, 0, W, H);
        resolve(cv.toDataURL('image/png'));
      } catch (e) { resolve(null); }
    });
  }

  // First url(...) or first colour of a computed background-image, if any.
  function bgImage(cs) {
    var bi = cs.backgroundImage;
    if (!bi || bi === 'none') return null;
    var u = bi.match(/url\(["']?([^"')]+)["']?\)/);
    if (u) return { url: u[1] };
    var c = bi.match(/rgba?\([^)]+\)/); // gradient → approximate with first colour
    if (c) { var pc = parseColor(c[0]); if (pc) return { color: pc.hex, alpha: pc.a }; }
    return null;
  }

  // ---- table extraction ----------------------------------------------------
  // An HTML <table> becomes a NATIVE Google Slides table (createTable), not a
  // scatter of floating text boxes + border bars. We read the browser's own
  // grid geometry (column widths, row heights), per-cell text runs, the
  // composited cell background, and the resolved per-edge borders — everything
  // the Slides table API needs to rebuild an editable table.
  var BORDER_SIDES = [['Top', 'top'], ['Right', 'right'], ['Bottom', 'bottom'], ['Left', 'left']];

  // The opaque colour a cell actually shows: composite every background layer
  // from the cell up to the table (cell fill, zebra row fill, header fill…)
  // over the slide's own background. Returns null when no layer paints anything
  // (a plain row → the slide background shows through, so we leave it unfilled).
  function compositeCellBg(cellEl, tableEl, slideBgHex) {
    var layers = [];                    // top-most (cell) first
    var node = cellEl;
    while (node) {
      var c = parseColor(getComputedStyle(node).backgroundColor);
      if (c) layers.push(c);
      if (node === tableEl) break;
      node = node.parentElement;
    }
    if (!layers.length) return null;
    var base = hexToRgb(slideBgHex || '#ffffff');
    for (var i = layers.length - 1; i >= 0; i--) {   // composite bottom-up
      var lc = hexToRgb(layers[i].hex), a = layers[i].a;
      base = { r: lc.r * a + base.r * (1 - a),
               g: lc.g * a + base.g * (1 - a),
               b: lc.b * a + base.b * (1 - a) };
    }
    return rgbToHex(base);
  }

  // Resolved (post-collapse) borders of one cell, one entry per painted edge.
  function cellBorders(cellEl, cs) {
    var out = [];
    for (var i = 0; i < BORDER_SIDES.length; i++) {
      var w = parseFloat(cs['border' + BORDER_SIDES[i][0] + 'Width']) || 0;
      var col = parseColor(cs['border' + BORDER_SIDES[i][0] + 'Color']);
      if (w > 0.3 && col) out.push({ side: BORDER_SIDES[i][1], color: col.hex, weight: w, alpha: col.a });
    }
    return out;
  }

  function extractTable(tableEl, slideRect, scale, slideBgHex) {
    var tr = rectOf(tableEl, slideRect, scale);
    var domRows = tableEl.rows;                 // excludes any nested table's rows
    var nRows = domRows.length;
    if (!nRows) return null;

    // Place cells on a grid, honouring colspan/rowspan.
    var occupied = {};                          // "r,c" -> true
    var cells = [], nCols = 0;
    for (var r = 0; r < nRows; r++) {
      var rowCells = domRows[r].cells, c = 0;
      for (var k = 0; k < rowCells.length; k++) {
        while (occupied[r + ',' + c]) c++;
        var cellEl = rowCells[k];
        var cspan = parseInt(cellEl.getAttribute('colspan'), 10) || 1;
        var rspan = parseInt(cellEl.getAttribute('rowspan'), 10) || 1;
        for (var dr = 0; dr < rspan; dr++)
          for (var dc = 0; dc < cspan; dc++) occupied[(r + dr) + ',' + (c + dc)] = true;
        cells.push({ el: cellEl, row: r, col: c, rowSpan: rspan, colSpan: cspan });
        c += cspan;
        if (c > nCols) nCols = c;
      }
    }
    if (!nCols) return null;

    var colWidths = new Array(nCols).fill(0);
    var rowHeights = new Array(nRows).fill(0);
    var outCells = [];
    for (var ci = 0; ci < cells.length; ci++) {
      var cell = cells[ci], el = cell.el;
      var cs = getComputedStyle(el);
      var cr = rectOf(el, slideRect, scale);
      if (cell.colSpan === 1) colWidths[cell.col] = Math.max(colWidths[cell.col], cr.w);
      if (cell.rowSpan === 1) rowHeights[cell.row] = Math.max(rowHeights[cell.row], cr.h);

      var fsz = parseFloat(cs.fontSize) || 16;
      var lh = parseFloat(cs.lineHeight);
      var runs = collectRuns(el);
      // An icon above the cell's text: the exporter draws the icon over the cell (a Slides cell holds text only), so the
      // text needs the space the icon and its margin take. The leading line break carries that space (pt); the
      // exporter makes the blank first line that tall, so the text starts below the icon as in the HTML.
      var lead = cellLeadPt(el, cr, slideRect, scale, tableEl);
      if (lead > 0 && runs.length) {
        if (runs[0].br) runs[0].leadPt = lead;                       // the HTML's own <br> after the icon
        else runs.unshift({ text: '\n', br: true, leadPt: lead });
      }
      outCells.push({
        row: cell.row, col: cell.col, rowSpan: cell.rowSpan, colSpan: cell.colSpan,
        fill: compositeCellBg(el, tableEl, slideBgHex), fillAlpha: 1,
        align: alignmentOf(el, cs).h,
        // the HTML cell's own vertical-align (a journey or a summary table is top-aligned); the browser default is middle
        valign: cs.verticalAlign === 'top' ? 'TOP' : (cs.verticalAlign === 'bottom' ? 'BOTTOM' : 'MIDDLE'),
        lineHeightPct: isNaN(lh) ? 120 : Math.round(lh / fsz * 100),
        borders: cellBorders(el, cs),
        runs: runs
      });
    }
    // Fallback for any col/row only covered by a span (keeps totals sane).
    for (var q = 0; q < nCols; q++) if (!colWidths[q]) colWidths[q] = tr.w / nCols;
    for (var p = 0; p < nRows; p++) if (!rowHeights[p]) rowHeights[p] = tr.h / nRows;

    return {
      type: 'table', x: tr.x, y: tr.y, w: tr.w, h: tr.h,
      rows: nRows, cols: nCols,
      colWidths: colWidths, rowHeights: rowHeights,
      cells: outCells
    };
  }

  // ---- main walk -----------------------------------------------------------
  function extractSlide(slideEl, tasks) {
    var slideRect = slideEl.getBoundingClientRect();
    var scale = slideRect.width / DESIGN_W;
    var els = [];

    var slideCS = getComputedStyle(slideEl);
    var bg = parseColor(slideCS.backgroundColor);
    // dark slides use gradients → background-color may be transparent; sniff the
    // gradient's first colour, else fall back to the class-implied navy.
    if (!bg && slideCS.backgroundImage && slideCS.backgroundImage !== 'none') {
      bg = parseColor(slideCS.backgroundImage) || null;
    }
    if (!bg) {
      if (slideEl.classList.contains('dark') || slideEl.classList.contains('cover') ||
          slideEl.classList.contains('section')) bg = { hex: tokenHex('--db-navy', '#1B3139'), a: 1 };
    }

    // Box of an absolutely/fixed-positioned ::before/::after in design px, or
    // null. Its containing block is the nearest positioned ancestor's padding
    // box (the host itself when it is position:relative, as these decorations
    // are). getComputedStyle resolves a positioned pseudo's width/height/offsets
    // to used px, so left+right with width:auto still yields a real width.
    function pseudoBox(el, pcs) {
      var cbEl = el;
      if (pcs.position === 'fixed') cbEl = slideEl;
      else while (cbEl && cbEl !== slideEl && getComputedStyle(cbEl).position === 'static') cbEl = cbEl.parentElement;
      if (!cbEl) cbEl = slideEl;
      // Work entirely in DESIGN px: the containing block via rectOf (screen →
      // design), and the pseudo's own offsets/size, which getComputedStyle
      // already returns in design px (pre-transform). Mixing the two spaces
      // would shift and mis-size the decoration by the export's scale factor.
      var hd = rectOf(cbEl, slideRect, scale), hcs = getComputedStyle(cbEl);
      var bl = parseFloat(hcs.borderLeftWidth) || 0, bt = parseFloat(hcs.borderTopWidth) || 0,
          br = parseFloat(hcs.borderRightWidth) || 0, bb = parseFloat(hcs.borderBottomWidth) || 0;
      var cbL = hd.x + bl, cbT = hd.y + bt, cbW = hd.w - bl - br, cbH = hd.h - bt - bb;
      var w = parseFloat(pcs.width), h = parseFloat(pcs.height);
      var L = pcs.left, R = pcs.right, T = pcs.top, B = pcs.bottom;
      if (pcs.boxSizing === 'content-box') {
        if (!isNaN(w)) w += (parseFloat(pcs.paddingLeft) || 0) + (parseFloat(pcs.paddingRight) || 0) +
                            (parseFloat(pcs.borderLeftWidth) || 0) + (parseFloat(pcs.borderRightWidth) || 0);
        if (!isNaN(h)) h += (parseFloat(pcs.paddingTop) || 0) + (parseFloat(pcs.paddingBottom) || 0) +
                            (parseFloat(pcs.borderTopWidth) || 0) + (parseFloat(pcs.borderBottomWidth) || 0);
      }
      if (isNaN(w) && L !== 'auto' && R !== 'auto') w = cbW - parseFloat(L) - parseFloat(R);
      if (isNaN(h) && T !== 'auto' && B !== 'auto') h = cbH - parseFloat(T) - parseFloat(B);
      if (isNaN(w) || isNaN(h)) return null;
      var x = L !== 'auto' ? cbL + parseFloat(L) : (R !== 'auto' ? cbL + cbW - parseFloat(R) - w : cbL);
      var y = T !== 'auto' ? cbT + parseFloat(T) : (B !== 'auto' ? cbT + cbH - parseFloat(B) - h : cbT);
      // A transform moves the box too: translate(-50%,-50%) centres a handle on its left/top point, and
      // translateY(-50%) centres an arrow. getComputedStyle gives the matrix in px (before the slide scale).
      var tm = /^matrix\(([^)]+)\)$/.exec(pcs.transform || '');
      if (tm) { var mv = tm[1].split(',').map(parseFloat); x += mv[4] || 0; y += mv[5] || 0; }
      return { x: x, y: y, w: w, h: h, wPx: w, hPx: h };   // all design px, slide-relative
    }

    // Emit the paintable ::before/::after pseudo-elements of `el`. These are
    // invisible to the DOM walk yet carry real decoration: a timeline's
    // connector line (.step::after), a bulleted list's dot (li::before), corner
    // ribbons, accent underlines. Only absolutely/fixed-positioned ones (whose
    // geometry resolves reliably) are emitted — as a shape (fill/border) and/or
    // a text run for literal string content.
    function emitPseudos(el) {
      // A list item's marker pseudo (the custom ::before dot in ul.bullets) is
      // rebuilt as a NATIVE Slides bullet on the paragraph — don't also draw it.
      if (el.tagName === 'LI') return;
      ['::before', '::after'].forEach(function (which) {
        var pcs = getComputedStyle(el, which);
        var content = pcs.content;
        if (!content || content === 'none' || content === 'normal') return;
        if (pcs.display === 'none' || pcs.visibility === 'hidden' || parseFloat(pcs.opacity) === 0) return;
        if (pcs.position !== 'absolute' && pcs.position !== 'fixed') return;  // reliable geometry only
        var box = pseudoBox(el, pcs);
        if (!box) return;
        // A drawn arrow (CSS mask, see style.css GLYPH-FREE MARKS) becomes its character.
        var maskSrc = pcs.maskImage || pcs.webkitMaskImage || '';
        var arrow = /M3(%20| )12h17/.test(maskSrc) ? '\u2192' : (/M2(%20| )12h20/.test(maskSrc) ? '\u2194' : null);
        if (arrow === '\u2194') {
          // a double arrow (the compare slider's handle) is a native LEFT_RIGHT_ARROW shape: a glyph here came out as a
          // broken picture in the PowerPoint copy (the font has no such mark), while the shape is the same in both
          var hcol = parseColor(pcs.backgroundColor) || { hex: '#000000' };
          els.push({ type: 'rect', x: box.x, y: box.y + box.h * 0.25, w: box.w, h: box.h * 0.5, shape: 'LEFT_RIGHT_ARROW',
                     fill: hcol.hex, fillAlpha: hcol.a, radius: 0, ellipse: false, border: null });
          return;
        }
        if (arrow) {
          var acol = parseColor(pcs.backgroundColor) || { hex: '#000000' };
          els.push({ type: 'text', x: box.x, y: box.y, w: box.w || 10, h: box.h || 10,
                     align: 'CENTER', valign: 'MIDDLE', oneLine: true, fontPx: box.wPx, lineHeightPct: 100,
                     runs: [{ text: arrow, size: pxToPt(box.wPx), font: primaryFont(getComputedStyle(el).fontFamily),
                              bold: true, italic: false, color: acol.hex }] });
          return;
        }
        var fill = parseColor(pcs.backgroundColor);
        var SIDES = [['Top', 'top'], ['Right', 'right'], ['Bottom', 'bottom'], ['Left', 'left']];
        var present = [];
        for (var i = 0; i < SIDES.length; i++) {
          var bw = parseFloat(pcs['border' + SIDES[i][0] + 'Width']) || 0;
          var bc = parseColor(pcs['border' + SIDES[i][0] + 'Color']);
          if (bw > 0.3 && bc) present.push({ w: bw, c: bc });
        }
        var uniform = present.length === 4 && present.every(function (e) {
          return e.c.hex === present[0].c.hex && Math.abs(e.w - present[0].w) < 0.6;
        });
        var border = uniform ? { color: present[0].c.hex, weight: present[0].w, alpha: present[0].c.a } : null;
        var radStr = pcs.borderTopLeftRadius || '0px';
        var ellipse = false, radPx = 0;
        if (radStr.indexOf('%') >= 0) ellipse = parseFloat(radStr) >= 40;   // e.g. 50% → circle/pill
        else { radPx = parseFloat(radStr) || 0; ellipse = radPx > 0 && radPx * 2 >= Math.min(box.wPx, box.hPx) - 1; }
        if ((fill || border) && box.w >= 0.3 && box.h >= 0.3) {
          // a clip-path on the pseudo (the block arrows of the medallion and architecture slides) is
          // its shape: without it the fill came out as a square
          var shapeP = clipShape(pcs, box);
          els.push({ type: 'rect', x: box.x, y: box.y, w: box.w, h: box.h,
                     shape: shapeP && shapeP.shape, clip: shapeP && shapeP.clip, clipMismatch: shapeP && shapeP.mismatch,
                     fill: fill ? fill.hex : null, fillAlpha: fill ? fill.a : 0,
                     radius: radPx, ellipse: ellipse, border: border });
        }
        var m = content.match(/^["'](.*)["']$/);   // literal string content only (skip counter/attr/url)
        if (m && m[1].trim()) {
          var col = parseColor(pcs.color) || { hex: '#000000' };
          var fpx = parseFloat(pcs.fontSize) || 16;
          els.push({ type: 'text', x: box.x, y: box.y, w: box.w || 10, h: box.h || 10,
                     align: pcs.textAlign === 'center' ? 'CENTER' : 'START', valign: 'MIDDLE',
                     oneLine: true, fontPx: fpx, lineHeightPct: 120,
                     runs: [{ text: m[1], size: pxToPt(fpx), font: primaryFont(pcs.fontFamily),
                              bold: (parseInt(pcs.fontWeight, 10) || 400) >= 600,
                              italic: pcs.fontStyle === 'italic', color: col.hex }] });
        }
      });
    }

    // ---- native SVG diagrams ------------------------------------------------
    // An inline <svg data-gs="native"> (the architecture-diagram kit) is NOT
    // rasterised: each drawable becomes its own editable Slides object — rect /
    // circle → shape (fill, outline, dash), line / polyline → native line with
    // arrowheads (from marker-start / marker-end), text → text box (one per
    // <text>, or per x-positioned <tspan>), <image> → image. Everything from one
    // SVG shares a `group` id so the driver can group it. The supported subset is
    // checked first; anything else (a <path>, <foreignObject>, a gradient…) makes
    // the whole SVG fall back to the single-image rasterisation.
    var NATIVE_TAGS = { svg: 1, g: 1, defs: 1, marker: 1, title: 1, desc: 1, rect: 1, circle: 1,
      ellipse: 1, line: 1, polyline: 1, text: 1, tspan: 1, image: 1 };
    function extractNativeSvg(svg) {
      var all = svg.querySelectorAll('*');
      for (var i = 0; i < all.length; i++) {
        var tn = all[i].tagName.toLowerCase();
        if (all[i].closest('defs, marker')) continue;   // marker shapes (arrowheads) never export
        // A filled area (<path data-gs-area>, a line chart's fill) has no native form:
        // it goes out as ONE picture of just that path, under the native lines and dots.
        if (tn === 'path' && all[i].hasAttribute('data-gs-area')) continue;
        if (!NATIVE_TAGS[tn]) {
          if (window.console) console.warn('gslides: <' + tn + '> in a data-gs="native" SVG; rasterising it instead');
          return false;
        }
      }
      var group = 'svg' + (++nativeSeq);
      // Filled areas: a picture of the SVG with only that element left (same box and
      // viewBox, so it lands exactly under the native chart). Pushed first = drawn first.
      var areaEls = svg.querySelectorAll('path[data-gs-area]');
      for (var ai = 0; ai < areaEls.length; ai++) {
        (function (areaEl) {
          var box = rectOf(svg, slideRect, scale);
          var idx = Array.prototype.indexOf.call(svg.querySelectorAll('*'), areaEl);
          var clone = svg.cloneNode(true);
          inlineSvgStyles(svg, clone);                       // resolve CSS/print styles first
          var keep = clone.querySelectorAll('*')[idx];
          Array.prototype.slice.call(clone.childNodes).forEach(function (c) {
            if (c.nodeType === 1 && c !== keep && !(keep && c.contains(keep)) &&
                c.tagName.toLowerCase() !== 'defs') clone.removeChild(c);
          });
          var idxEl = els.length;
          els.push({ type: 'image', x: box.x, y: box.y, w: box.w, h: box.h, data: null, group: group, alt: altOf(svg) });
          tasks.push(rasterizeMarkup(clone, box.w, box.h).then(function (d) { els[idxEl].data = d; }));
        })(areaEls[ai]);
      }
      function k(node) {                         // user unit → design px for this node
        var m = node.getScreenCTM();
        return m ? Math.sqrt(m.a * m.a + m.b * m.b) / scale : 1;
      }
      function pt(node, x, y) {
        var p = new DOMPoint(x, y).matrixTransform(node.getScreenCTM());
        return { x: (p.x - slideRect.left) / scale, y: (p.y - slideRect.top) / scale };
      }
      function stroke(node, cs) {
        var c = cs.stroke && cs.stroke !== 'none' ? parseColor(cs.stroke) : null;
        var sw = parseFloat(cs.strokeWidth);
        if (!c || !(sw > 0)) return null;
        var da = cs.strokeDasharray && cs.strokeDasharray !== 'none' ? cs.strokeDasharray : null;
        var dash = 'SOLID';
        if (da) dash = (parseFloat(da) || 0) <= sw * 1.5 ? 'DOT' : 'DASH';
        return { color: c.hex, alpha: c.a * (parseFloat(cs.strokeOpacity) || 1), weight: sw * k(node), dash: dash };
      }
      function marker(node, which) {
        var v = node.getAttribute(which) || getComputedStyle(node).getPropertyValue(which);
        return v && v !== 'none' ? 'FILL_ARROW' : 'NONE';
      }
      // The arrowhead is drawn from the tip, which sits (T - refX) x stroke-width past the line end (the marker is placed
      // 1.5 stroke widths behind its tip, so the stroke ends under the head). Slides draws the head at the line end, so the
      // exported line runs out to the tip. Returns the distance in svg units (0 when there is no marker).
      function markerReach(node, which) {
        var v = node.getAttribute(which) || getComputedStyle(node).getPropertyValue(which);
        var m = v && /url\(["']?#([^"')]+)["']?\)/.exec(v);
        var mk = m && document.getElementById(m[1]);
        if (!mk) return 0;
        var pathEl = mk.querySelector('path'), d = pathEl ? pathEl.getAttribute('d') : '';
        var tokens = d.match(/[MLlzZ]|-?[\d.]+/g) || [], cmd = 'M', nums = [], x = 0, maxX = 0, i = 0;
        while (i < tokens.length) {
          var t = tokens[i];
          if (/^[MLlzZ]$/.test(t)) { cmd = t; i++; continue; }
          var px = parseFloat(tokens[i]), py = parseFloat(tokens[i + 1]); i += 2;
          if (cmd === 'l') { x += px; } else { x = px; }
          if (x > maxX) maxX = x;
        }
        var refX = parseFloat(mk.getAttribute('refX')) || 0;
        var sw = parseFloat(node.getAttribute('stroke-width')) || 1;
        return Math.max(0, maxX - refX) * sw;
      }
      function textRuns(nodes, cs0, kk) {
        var runs = [];
        nodes.forEach(function (n) {
          var t = (n.textContent || '').replace(/\s+/g, ' ');
          if (!t) return;
          var cs = n.nodeType === 1 ? getComputedStyle(n) : cs0;
          var col = parseColor(cs.fill) || { hex: '#000000' };
          runs.push({ text: t, size: pxToPt(parseFloat(cs.fontSize) * kk), font: primaryFont(cs.fontFamily),
                      bold: (parseInt(cs.fontWeight, 10) || 400) >= 600, italic: cs.fontStyle === 'italic',
                      color: col.hex });
        });
        if (runs.length) {                       // trim the outer edges of the chunk only
          runs[0].text = runs[0].text.replace(/^\s+/, '');
          runs[runs.length - 1].text = runs[runs.length - 1].text.replace(/\s+$/, '');
        }
        return runs.filter(function (r) { return r.text; });
      }
      function emitText(node) {
        var cs = getComputedStyle(node), kk = k(node);
        // Split into chunks at every <tspan> that is placed on its own: an absolute x, or a relative dx / dy
        // offset (a step number nudged 8 px before its title). Each chunk is measured where the browser drew
        // it and gets its own text box, so "1" and "Publish table" are not run together into "1Publish table".
        var chunks = [], cur = [];
        Array.prototype.forEach.call(node.childNodes, function (c) {
          var placed = c.nodeType === 1 && c.tagName.toLowerCase() === 'tspan' &&
            (c.hasAttribute('x') || c.hasAttribute('dx') || c.hasAttribute('dy'));
          if (placed && cur.length) {
            chunks.push(cur); cur = [];
          }
          if (c.nodeType === 1 || (c.nodeType === 3 && c.textContent.trim())) cur.push(c);
        });
        if (cur.length) chunks.push(cur);
        chunks.forEach(function (nodes) {
          var runs = textRuns(nodes, cs, kk);
          if (!runs.length) return;
          var r;
          if (chunks.length === 1) {
            r = rectOf(node, slideRect, scale);
          } else if (nodes.some(function (n) { return n.nodeType === 3; })) {
            var rg = document.createRange();         // bare text in a split <text>: measure its glyphs
            rg.setStartBefore(nodes[0]); rg.setEndAfter(nodes[nodes.length - 1]);
            var b = rg.getBoundingClientRect();
            r = { x: (b.left - slideRect.left) / scale, y: (b.top - slideRect.top) / scale, w: b.width / scale, h: b.height / scale };
          } else {
            var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
            nodes.forEach(function (n) {
              var b = n.getBoundingClientRect();
              x0 = Math.min(x0, b.left); y0 = Math.min(y0, b.top); x1 = Math.max(x1, b.right); y1 = Math.max(y1, b.bottom);
            });
            r = { x: (x0 - slideRect.left) / scale, y: (y0 - slideRect.top) / scale, w: (x1 - x0) / scale, h: (y1 - y0) / scale };
          }
          var anchor = getComputedStyle(nodes[0].nodeType === 1 ? nodes[0] : node).textAnchor || cs.textAnchor;
          var fpx = parseFloat(cs.fontSize) * kk;
          // Every SVG <text> is one line: give it slack for Slides' wider metrics, or a
          // tick such as "100" wraps into "10" over "0". Grown from its anchor.
          var dsw = Math.max(r.w * 0.1, 8), rw = Math.max(r.w, 4), rx = r.x;
          if (anchor === 'middle') rx -= dsw / 2; else if (anchor === 'end') rx -= dsw;
          rw += dsw;
          els.push({ type: 'text', x: rx, y: r.y, w: rw, h: Math.max(r.h, fpx * 1.2),
                     align: anchor === 'middle' ? 'CENTER' : (anchor === 'end' ? 'END' : 'START'),
                     valign: 'MIDDLE', oneLine: true, fontPx: fpx, lineHeightPct: 100,
                     runs: runs, group: group });
        });
      }
      var walker = document.createTreeWalker(svg, NodeFilter.SHOW_ELEMENT);
      for (var node = walker.nextNode(); node; node = walker.nextNode()) {
        var tn = node.tagName.toLowerCase();
        if (node.closest('defs, marker')) continue;
        if (tn === 'tspan') continue;            // handled by its <text>
        var cs = getComputedStyle(node);
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
        if (tn === 'rect' || tn === 'circle' || tn === 'ellipse') {
          var rr = rectOf(node, slideRect, scale);
          var f = parseColor(cs.fill);
          var st = stroke(node, cs);
          if (!f && !st) continue;
          els.push({ type: 'rect', x: rr.x, y: rr.y, w: rr.w, h: rr.h,
                     fill: f ? f.hex : null, fillAlpha: f ? f.a * (parseFloat(cs.fillOpacity) || 1) : 0,
                     radius: tn === 'rect' ? (parseFloat(node.getAttribute('rx')) || 0) * k(node) : 0,
                     ellipse: tn !== 'rect', border: st, native: true, group: group });
        } else if (tn === 'line' || tn === 'polyline') {
          var stl = stroke(node, cs);
          if (!stl) continue;
          var raw = [];
          if (tn === 'line') {
            raw = [{ x: +node.getAttribute('x1'), y: +node.getAttribute('y1') },
                   { x: +node.getAttribute('x2'), y: +node.getAttribute('y2') }];
          } else {
            var pl = node.points;
            for (var pi = 0; pi < pl.numberOfItems; pi++) raw.push({ x: pl.getItem(pi).x, y: pl.getItem(pi).y });
          }
          if (raw.length >= 2) {                 // run the line out to each arrow tip (see markerReach)
            var eb = markerReach(node, 'marker-end'), sb = markerReach(node, 'marker-start');
            var a = raw[raw.length - 2], b = raw[raw.length - 1], L = Math.hypot(b.x - a.x, b.y - a.y) || 1;
            if (eb) { raw[raw.length - 1] = { x: b.x + (b.x - a.x) / L * eb, y: b.y + (b.y - a.y) / L * eb }; }
            a = raw[1]; b = raw[0]; L = Math.hypot(b.x - a.x, b.y - a.y) || 1;
            if (sb && raw.length >= 2) { raw[0] = { x: b.x + (b.x - a.x) / L * sb, y: b.y + (b.y - a.y) / L * sb }; }
          }
          var pts = raw.map(function (q) { return pt(node, q.x, q.y); });
          for (var si = 0; si + 1 < pts.length; si++) {
            els.push({ type: 'line', x1: pts[si].x, y1: pts[si].y, x2: pts[si + 1].x, y2: pts[si + 1].y,
                       color: stl.color, alpha: stl.alpha, weight: stl.weight, dash: stl.dash,
                       startArrow: si === 0 ? marker(node, 'marker-start') : 'NONE',
                       endArrow: si + 2 === pts.length ? marker(node, 'marker-end') : 'NONE',
                       group: group });
          }
        } else if (tn === 'text') {
          emitText(node);
        } else if (tn === 'image') {
          var ir = rectOf(node, slideRect, scale);
          var href = node.getAttribute('href') || node.getAttribute('xlink:href');
          if (href) els.push({ type: 'image', x: ir.x, y: ir.y, w: ir.w, h: ir.h, src: href, data: null, group: group, alt: altOf(node) });
        }
      }
      return true;
    }

    // An inset() clip-path (the compare slider's "before" pane) hides part of a
    // subtree; Slides has no clipping, so trim what was emitted for it to the
    // visible box: shapes are cut, file images get a crop (the exporter renders
    // only the visible slice), text and inline images whose centre is hidden are
    // dropped.
    function clipOf(el, cs) {
      var m = /^inset\(([^)]*)\)/.exec(cs.clipPath || '');
      if (!m) return null;
      var box = rectOf(el, slideRect, scale);
      // computed insets may be px or % (the slider's calc(100% - var(--pos)))
      var v = m[1].trim().split(/\s+/), side = [box.h, box.w, box.h, box.w];
      function len(tok, i) { var f = parseFloat(tok) || 0; return /%$/.test(tok) ? f / 100 * side[i] : f / 1; }
      var t = len(v[0], 0), r = v.length > 1 ? len(v[1], 1) : len(v[0], 1),
          b = v.length > 2 ? len(v[2], 2) : t, l = v.length > 3 ? len(v[3], 3) : r;
      return { x: box.x + l, y: box.y + t, r: box.x + box.w - r, b: box.y + box.h - b };
    }
    function applyClip(from, c) {
      for (var i = els.length - 1; i >= from; i--) {
        var e = els[i];
        if (e.type === 'line') {
          var mx = (e.x1 + e.x2) / 2, my = (e.y1 + e.y2) / 2;
          if (mx < c.x || mx > c.r || my < c.y || my > c.b) els.splice(i, 1);
          continue;
        }
        var cx = e.x + e.w / 2, cy = e.y + e.h / 2;
        if (e.type === 'rect') {
          var x0 = Math.max(e.x, c.x), y0 = Math.max(e.y, c.y);
          var x1 = Math.min(e.x + e.w, c.r), y1 = Math.min(e.y + e.h, c.b);
          if (x1 - x0 < 0.5 || y1 - y0 < 0.5) { els.splice(i, 1); continue; }
          e.x = x0; e.y = y0; e.w = x1 - x0; e.h = y1 - y0;
        } else if (e.type === 'image' && e.src) {
          var ix0 = Math.max(e.x, c.x), iy0 = Math.max(e.y, c.y);
          var ix1 = Math.min(e.x + e.w, c.r), iy1 = Math.min(e.y + e.h, c.b);
          if (ix1 - ix0 < 1 || iy1 - iy0 < 1) { els.splice(i, 1); continue; }
          if (ix1 - ix0 < e.w - 0.5 || iy1 - iy0 < e.h - 0.5) {
            e.crop = { l: (ix0 - e.x) / e.w, t: (iy0 - e.y) / e.h,
                       r: (e.x + e.w - ix1) / e.w, b: (e.y + e.h - iy1) / e.h, fw: e.w, fh: e.h };
            e.x = ix0; e.y = iy0; e.w = ix1 - ix0; e.h = iy1 - iy0;
          }
        } else if (cx < c.x || cx > c.r || cy < c.y || cy > c.b) {
          els.splice(i, 1);
        }
      }
    }

    // An icon or picture (img, inline svg, canvas) as one picture over its own box. Its pseudo-elements go with it.
    function emitGraphic(el) {
      var cs = getComputedStyle(el);
      var gr = rectOf(el, slideRect, scale);
      if (el.tagName === 'IMG') {
        // File-loaded images taint the canvas under file://, so we can't
        // reliably base64 them here — carry the source path and let the
        // Python side read the bytes from disk (and convert SVG→PNG).
        // A CSS filter (greyscale logo walls, faded images) travels as `filter`: a file://
        // canvas is tainted, so the exporter applies it to the file's pixels.
        var imgFilter = cs.filter && cs.filter !== 'none' ? cs.filter : null;
        els.push({ type: 'image', x: gr.x, y: gr.y, w: gr.w, h: gr.h,
                   src: el.getAttribute('src'), data: null, alt: altOf(el), filter: imgFilter,
                   fit: /^(cover|contain)$/.test(cs.objectFit) ? cs.objectFit : null });
      } else {
        // Inline <svg> / <canvas> (charts) rasterise cleanly via a data URL.
        var idx = els.length;
        els.push({ type: 'image', x: gr.x, y: gr.y, w: gr.w, h: gr.h, data: null, alt: altOf(el) });
        tasks.push(rasterizeAsync(el, gr.w, gr.h).then(function (d) { els[idx].data = d; }));
      }
      emitPseudos(el);    // an early exit: pseudos of a graphic are emitted here, once
    }
    // The visible icons and pictures inside a table's own cells (not in a nested table). A glyph mark (svg with
    // data-glyph) is text, already in the cell's runs, so it is left out here.
    function cellGraphics(tableEl) {
      var out = [];
      for (var r = 0; r < tableEl.rows.length; r++) {
        var row = tableEl.rows[r].cells;
        for (var c = 0; c < row.length; c++) {
          var found = row[c].querySelectorAll('img, svg, canvas');
          for (var f = 0; f < found.length; f++) {
            var g = found[f];
            if (glyphOf(g) || g.closest('table') !== tableEl) continue;
            if (g.parentElement && g.parentElement.closest('svg, canvas')) continue;   // inside another graphic
            if (!visible(g, getComputedStyle(g))) continue;
            out.push(g);
          }
        }
      }
      return out;
    }
    function walk(el) {
      var cs = getComputedStyle(el);
      if (!visible(el, cs)) return;
      if (el.classList && (el.classList.contains('slide-checkbox') ||
          el.classList.contains('slide-idx') || el.classList.contains('notes'))) return;
      // Flip cards export their resting (front) face, like the PDF.
      if (el.classList && (el.classList.contains('flip-back') || el.classList.contains('flip-hint'))) return;
      var clip = clipOf(el, cs), from = els.length;
      walkBody(el, cs);
      if (clip) applyClip(from, clip);
    }
    function walkBody(el, cs) {

      var tag = el.tagName;

      // A <table> becomes a native Slides table — emit it whole and don't
      // descend (otherwise every cell would leak out as a floating text box).
      if (tag === 'TABLE') {
        var tbl = extractTable(el, slideRect, scale, bg ? bg.hex : null);
        if (tbl) els.push(tbl);
        // A cell holds text only in Slides, so an icon or picture inside a cell is placed over the cell's box,
        // drawn after the table (so it sits on top of it).
        cellGraphics(el).forEach(emitGraphic);
        emitPseudos(el);     // these early exits skip walkBody's later emission
        return;
      }

      var isGraphic = tag === 'IMG' || tag === 'CANVAS' ||
        tag === 'svg' || (el.namespaceURI && el.namespaceURI.indexOf('/svg') >= 0 && tag === 'svg');

      if (tag === 'svg' && el.getAttribute('data-gs') === 'native' && extractNativeSvg(el)) { emitPseudos(el); return; }

      if (isGraphic) { emitGraphic(el); return; }   // do not descend into graphics

      var isSlideRoot = el === slideEl;
      var rr = rectOf(el, slideRect, scale);
      var radius = parseFloat(cs.borderTopLeftRadius) || 0;
      // A round-radius >= half the shorter side reads as a circle/pill → ELLIPSE.
      // Compare in DESIGN px (rr) — border-radius from getComputedStyle is design
      // px (pre-transform) while getBoundingClientRect is scaled, so mixing them
      // made the verdict depend on the export's window size (bars turned oval at
      // small windows). radius is already design px, so it is emitted as-is.
      var ellipse = radius > 0 && radius * 2 >= Math.min(rr.w, rr.h) - 1;

      // Background image (photo panel, full-bleed cover, etc.) — an <img> is not
      // the only way to place an image. A gradient background approximates to a
      // solid rect. (Skip on the slide root; that's handled as the page bg.)
      if (!isSlideRoot) {
        var bgi = bgImage(cs);
        if (bgi && bgi.url) {
          // a rounded background picture (an avatar: border-radius 50% with overflow hidden) keeps its mask:
          // Slides cannot clip a picture, so the exporter renders it inside the same radius
          var bgRound = null;
          if (radius > 0) bgRound = (cs.borderTopLeftRadius.indexOf('%') >= 0 || radius * 2 >= Math.min(rr.w, rr.h) - 1) ? '50%' : (radius + 'px');
          els.push({ type: 'image', x: rr.x, y: rr.y, w: rr.w, h: rr.h, src: bgi.url, data: null, round: bgRound });
        } else if (/linear-gradient\(/.test(cs.backgroundImage || '')) {
          // Every gradient is one smooth picture. Alpha strips (the old path for axis-aligned gradients) showed as
          // visible vertical bands over photos (32 strips on slide 4 in Google), and a native fill cannot carry a fade.
          // A diagonal gradient is painted to a PNG so its fade survives.
          var gIdx = els.length;
          // overlay: the picture is translucent and sits over whatever is behind it (a photo), so the exporter must not
          // flatten it onto the slide colour (that made the scrim opaque and hid the photo on the cover slides)
          els.push({ type: 'image', x: rr.x, y: rr.y, w: rr.w, h: rr.h, data: null, alt: '', overlay: true });
          tasks.push(paintGradient(cs.backgroundImage, rr.w, rr.h).then(function (d) { els[gIdx].data = d; }));
        } else if (bgi && bgi.color) {
          els.push({ type: 'rect', x: rr.x, y: rr.y, w: rr.w, h: rr.h,
                     fill: bgi.color, fillAlpha: bgi.alpha, radius: radius, ellipse: ellipse, border: null });
        }
      }

      // Fill / border box? Read ALL four border edges. A Slides shape outline is
      // uniform on every side, so we fold whatever we can into ONE native outline
      // and emit a separate bar only for edges that genuinely can't join it:
      //   • all 4 sides identical            → native outline, no bars.
      //   • 4 sides, 3 identical + 1 accent  → native outline for the 3-side
      //     frame + ONE bar for the odd edge. This is the ubiquitous "accent card"
      //     (metric / ROI / stat cards: thin grey frame + thick coloured top rule).
      //     Before this, such a card exported as a white rect + FOUR disconnected
      //     edge bars — the "weird lines" that don't meet at the rounded corners.
      //   • anything else (single rule, 2+2 split, a table cell's lone bottom
      //     rule) → per-edge bars, so no side is invented or recoloured.
      var fill = parseColor(cs.backgroundColor);
      if (bgi && bgi.url) fill = null;   // the photo covers the box; a fill rect would paint over it
      var SIDES = [['Top', 'top'], ['Right', 'right'], ['Bottom', 'bottom'], ['Left', 'left']];
      var present = [];
      for (var ei = 0; ei < SIDES.length; ei++) {
        var ew = parseFloat(cs['border' + SIDES[ei][0] + 'Width']) || 0;
        var ec = parseColor(cs['border' + SIDES[ei][0] + 'Color']);
        // The accent is drawn as an inset box-shadow (CSS: it follows the rounded corners), so the
        // inset shadow on this side is the accent edge, and it replaces the border's own width and colour.
        var acc = insetAccent(cs.boxShadow, SIDES[ei][1]);
        if (acc) { ew = acc.w; ec = acc.c; }
        if (ew > 0.3 && ec) present.push({ side: SIDES[ei][1], w: ew, c: ec });
      }
      function sameEdge(a, b) { return a.c.hex === b.c.hex && Math.abs(a.w - b.w) < 0.6; }
      // The native outline (the largest group of matching edges) and the leftover
      // "accent" edges that must stay bars. Only fold when all four edges exist,
      // so drawing a full-perimeter outline never invents a side that isn't there.
      var frame = null, barEdges = present;
      if (present.length === 4) {
        var best = present[0];
        for (var gi = 0; gi < present.length; gi++) {
          var n = present.filter(function (e) { return sameEdge(e, present[gi]); }).length;
          if (n > present.filter(function (e) { return sameEdge(e, best); }).length) best = present[gi];
        }
        if (present.filter(function (e) { return sameEdge(e, best); }).length >= 3) {
          frame = { color: best.c.hex, weight: best.w, alpha: best.c.a };
          barEdges = present.filter(function (e) { return !sameEdge(e, best); }); // 0 or 1 edge
        }
      }
      // Accent card? A fill box with exactly ONE odd "accent" edge — a thick
      // coloured top/side rule over a thin (or absent) frame: .metric /
      // .roi-item / .cta-step / .dt-node (border-top accent) and .casestudy-quote
      // (border-left accent). A single straight bar inset from the rounded
      // corners reads as a line floating over the card (the reported bug).
      // Instead draw the accent as a full-size rounded rect BEHIND the card and
      // inset the fill box on the accent side, so only a rounded strip of the
      // accent shows — it follows the card's corner radius exactly, the way the
      // CSS border curves around the corners. (Skip ellipses: the trick is for
      // rectangular cards only.)
      var accent = (fill && barEdges.length === 1 && !ellipse) ? barEdges[0] : null;
      var shadowOf = parseShadow(cs.boxShadow);
      var shapeOf = clipShape(cs, rr);
      if (!isSlideRoot && accent) {
        var awp = accent.w;                       // accent thickness, design px
        // Behind: full-bounds rounded rect painted in the accent colour.
        els.push({ type: 'rect', x: rr.x, y: rr.y, w: rr.w, h: rr.h,
                   fill: accent.c.hex, fillAlpha: accent.c.a, radius: radius, ellipse: false, border: null });
        // Front: the fill box, inset on the accent side so only the accent strip
        // peeks out. The thin frame (if any) rides on this box so the grey
        // outline traces the card body; --db-line (#DCE0E2) is faint enough that
        // the hairline where the strip meets the body reads as the border, not a
        // seam.
        var fx = rr.x, fy = rr.y, fw = rr.w, fh = rr.h;
        if (accent.side === 'top')         { fy += awp; fh -= awp; }
        else if (accent.side === 'bottom') { fh -= awp; }
        else if (accent.side === 'left')   { fx += awp; fw -= awp; }
        else if (accent.side === 'right')  { fw -= awp; }
        els.push({ type: 'rect', x: fx, y: fy, w: fw, h: fh, shadow: shadowOf,
                   fill: fill.hex, fillAlpha: fill.a, radius: radius, ellipse: false, border: frame });
      } else if (!isSlideRoot && (fill || frame)) {
        els.push({
          type: 'rect', x: rr.x, y: rr.y, w: rr.w, h: rr.h, shadow: shadowOf,
          shape: shapeOf && shapeOf.shape, clip: shapeOf && shapeOf.clip, clipMismatch: shapeOf && shapeOf.mismatch,
          fill: fill ? fill.hex : null, fillAlpha: fill ? fill.a : 0,
          radius: radius, ellipse: ellipse, border: frame
        });
      }
      // Pseudo-elements (connectors, dots) paint above this box's own background and
      // below its children, so a connector is not hidden behind the card it joins.
      emitPseudos(el);
      // Edges that couldn't fold into the native outline → one thin bar each,
      // inset from the corners by the box radius so a bar never overhangs a
      // rounded corner. (When a native frame absorbed every edge, barEdges is
      // empty; when the accent-card path handled the lone edge, it's skipped.)
      if (!isSlideRoot && !accent && barEdges.length) {
        // Border widths and radius from getComputedStyle are already in the
        // slide's own (design) px — the same space as rr — so they are NOT
        // divided by scale (matching how the box border passes its weight).
        var rad = radius || 0;
        for (var ai = 0; ai < barEdges.length; ai++) {
          var e = barEdges[ai];
          var tpx = e.w;                      // edge thickness in design px
          var ax = rr.x, ay = rr.y, aw = rr.w, ah = rr.h;
          if (e.side === 'top') { ah = tpx; ax += rad; aw -= 2 * rad; }
          else if (e.side === 'bottom') { ay = rr.y + rr.h - tpx; ah = tpx; ax += rad; aw -= 2 * rad; }
          else if (e.side === 'left') { aw = tpx; ay += rad; ah -= 2 * rad; }
          else if (e.side === 'right') { ax = rr.x + rr.w - tpx; aw = tpx; ay += rad; ah -= 2 * rad; }
          if (aw <= 0 || ah <= 0) continue;
          els.push({ type: 'rect', x: ax, y: ay, w: aw, h: ah,
                     fill: e.c.hex, fillAlpha: e.c.a, radius: 0, ellipse: false, border: null });
        }
      }

      // Text leaf?
      if (isTextLeaf(el)) {
        // Emit any images that live inside this text block (e.g. the footer's
        // small brand mark) — they'd otherwise be skipped when we stop here.
        var imgs = el.querySelectorAll('img');
        for (var ii = 0; ii < imgs.length; ii++) {
          var im = imgs[ii];
          if (!visible(im, getComputedStyle(im))) continue;
          var ig = rectOf(im, slideRect, scale);
          els.push({ type: 'image', x: ig.x, y: ig.y, w: ig.w, h: ig.h, src: im.getAttribute('src'), data: null, alt: altOf(im) });

        }
        // ...and inline graphics (an icon in a tile: <svg class="uc-ico"> beside its label). The leaf's text
        // path reads only text nodes, so an svg here would vanish without this (the Unity slide's six icons).
        var gfx = el.querySelectorAll('svg, canvas');
        for (var gi = 0; gi < gfx.length; gi++) {
          var gel = gfx[gi];
          if (glyphOf(gel)) continue;      // a glyph icon (data-glyph) is already a text character in this leaf
          if (!visible(gel, getComputedStyle(gel))) continue;
          var gg = rectOf(gel, slideRect, scale);
          var gIdx = els.length;
          els.push({ type: 'image', x: gg.x, y: gg.y, w: gg.w, h: gg.h, data: null, alt: altOf(gel) });
          (function (k, node, w, h) {   // capture this element's slot: gIdx is reassigned on each pass
            tasks.push(rasterizeAsync(node, w, h).then(function (d) { els[k].data = d; }));
          })(gIdx, gel, gg.w, gg.h);
        }
        // Decorative chips inside this text block that carry a background or
        // border but NO text (a legend's colour swatch, a status dot). We stop
        // descending at a leaf, so they'd vanish — emit them here as shapes.
        var hasDecorChip = false;
        var chips = el.querySelectorAll('*');
        for (var ci = 0; ci < chips.length; ci++) {
          var chip = chips[ci];
          if (chip.tagName === 'IMG' || chip.textContent.trim()) continue;  // img handled above; text → not a chip
          var ccs = getComputedStyle(chip);
          if (!visible(chip, ccs)) continue;
          var cfill = parseColor(ccs.backgroundColor);
          var cbw = parseFloat(ccs.borderTopWidth) || 0;
          var cbc = parseColor(ccs.borderTopColor);
          if (!cfill && !(cbw > 0.3 && cbc)) continue;                        // nothing painted → skip
          var cr = rectOf(chip, slideRect, scale);                            // design px
          var crad = parseFloat(ccs.borderTopLeftRadius) || 0;                // design px
          els.push({ type: 'rect', x: cr.x, y: cr.y, w: cr.w, h: cr.h,
                     fill: cfill ? cfill.hex : null, fillAlpha: cfill ? cfill.a : 0,
                     radius: crad,
                     ellipse: crad > 0 && crad * 2 >= Math.min(cr.w, cr.h) - 1,
                     border: (cbw > 0.3 && cbc) ? { color: cbc.hex, weight: cbw, alpha: cbc.a } : null });
          hasDecorChip = true;
        }
        var runs = collectRuns(el);
        if (runs.length && runs.some(function (r) { return r.text.trim(); })) {
          var tr = rectOf(el, slideRect, scale);
          var lh = parseFloat(cs.lineHeight);
          var fsz = parseFloat(cs.fontSize) || 16;
          // Size decisions (one-line detection + wrap slack) must reflect the
          // BIGGEST glyphs actually drawn, not the block's own font-size: a giant
          // stat <span> (e.g. 180px "92%") inside a plain <div> otherwise looks
          // small, gets a tight box and wraps the "%" onto a second line.
          var dispPx = fsz;
          for (var _r = 0; _r < runs.length; _r++) {
            if (runs[_r].br) continue;
            var _px = runs[_r].size / 0.5625;   // pt → px (inverse of pxToPt)
            if (_px > dispPx) dispPx = _px;
          }
          // white-space:nowrap / pre must never re-wrap in Slides (single-word
          // pills like an "After" badge): flag it so the driver widens the box.
          var noWrap = cs.whiteSpace === 'nowrap' || cs.whiteSpace === 'pre';
          // Emoji-only icon spots (e.g. ⏱️ 💸 🔗) don't render in Slides' fonts
          // (they tofu even in the editor). Rasterise them via Chrome, which has
          // the colour-emoji font — a general fix for any short emoji glyph.
          var txt = runs.map(function (r) { return r.text; }).join('').trim();
          var pictographic = /\p{Extended_Pictographic}/u.test(txt);
          if (pictographic && Array.from(txt).length <= 4) {
            els.push({ type: 'emoji', x: tr.x, y: tr.y, w: tr.w, h: tr.h,
                       text: txt, fontPx: fsz });
            return;
          }
          var al = alignmentOf(el, cs);
          // If the block leads with an inline image (the footer's brand mark)
          // or a decorative chip (a legend swatch), position by the actual text
          // bounds so the text lands AFTER it instead of on top of it. Otherwise
          // use the CONTENT box (element rect minus its own padding + borders):
          // text never lives in the padding, and a reserved pad — e.g. an h3's
          // padding-right that clears a corner badge — must shrink the Slides box
          // too, or the text keeps that width, stops wrapping and runs under the
          // badge. tr is the border box, so subtract the resolved edges.
          var trt;
          // A block with a graphic in it (an <img> or an inline <svg> icon above its label) takes the glyphs'
          // own extent: the block's box would centre the label on the icon (slide 86 in Google).
          if (el.querySelector('img, svg, canvas') || hasDecorChip) {
            trt = textNodeRect(el, slideRect, scale) || tr;
          } else {
            var pl = parseFloat(cs.paddingLeft) || 0, pr = parseFloat(cs.paddingRight) || 0;
            var pt = parseFloat(cs.paddingTop) || 0, pb = parseFloat(cs.paddingBottom) || 0;
            var bl = parseFloat(cs.borderLeftWidth) || 0, brw = parseFloat(cs.borderRightWidth) || 0;
            var bt = parseFloat(cs.borderTopWidth) || 0, bb = parseFloat(cs.borderBottomWidth) || 0;
            trt = { x: tr.x + (pl + bl) / scale, y: tr.y + (pt + bt) / scale,
                    w: Math.max(1, tr.w - (pl + pr + bl + brw) / scale),
                    h: Math.max(1, tr.h - (pt + pb + bt + bb) / scale) };
          }
          // Text inside a filled box (a navy callout): its measure stops 8% short of the
          // padding, so Slides' wider text wraps before it reaches the box edge.
          var inFill = false;
          for (var fp = el; fp && fp !== slideEl; fp = fp.parentElement) {
            var fpc = getComputedStyle(fp);
            if (parseColor(fpc.backgroundColor) && parseColor(fpc.backgroundColor).a > 0.5) { inFill = true; break; }
          }
          if (inFill && trt.h > 1.7 * dispPx) {
            var nw = trt.w * 0.92; if (al.h === 'CENTER') trt.x += (trt.w - nw) / 2; trt.w = nw;
          }
          var tnr = textNodeRect(el, slideRect, scale);   // the glyphs' own extent
          // A run that is one line in the HTML takes its own line box, centred on its glyphs. The block's box can be
          // far taller (a card's title above a paragraph): Slides centres the text in the box, so the text sank by
          // the difference (the 16 px drop of the card titles on 91-93 and 80, measured in the real export).
          if (tnr && cs.whiteSpace !== 'pre' && !isNaN(lh) && tnr.h > 0 && Math.round(tnr.h / lh) <= 1 && trt.h > lh * 1.5) {
            trt.y = tnr.y + tnr.h / 2 - lh / 2;
            trt.h = lh;
          }
          // A run that wraps in the HTML: the box is the glyphs' own extent (its first line's top, half the leading
          // added above, and the same below), anchored to the top. Slides centres a block's text in the block's
          // height, so a card body or a pack title (whose block is taller: padding, a label above, another font's
          // metrics) started lower than the HTML by up to 51 px. Top-anchored, the first line sits where the HTML's does.
          // A line height of "normal" (no set leading) counts as the browser's 1.2 em for the line count.
          var lineH = isNaN(lh) ? fsz * 1.2 : lh;
          var forceTop = false;
          if (tnr && cs.whiteSpace !== 'pre' && tnr.h > 0 && Math.round(tnr.h / lineH) > 1) {
            var halfLead = Math.max(0, (lineH - fsz * 1.2) / 2);
            trt.x = trt.x; trt.y = tnr.y - halfLead; trt.h = tnr.h + 2 * halfLead;
            trt.w = Math.max(trt.w, tnr.w);
            forceTop = true;
          }
          // Slack for Slides' wider metrics: a single line widens by 8% (grown from
          // its anchor) so it does not re-wrap; wrapping paragraphs keep their box.
          if (trt.h <= 1.7 * dispPx && cs.whiteSpace !== 'nowrap' && cs.whiteSpace !== 'pre') {
            var sw = slackWithin(trt, al.h, slideRect.width / scale);
            if (al.h === 'CENTER') trt.x -= sw / 2; else if (al.h === 'END') trt.x -= sw;
            trt.w += sw;
          }
          // A native bulleted list: each item's own line count and its pitch to the next item in the HTML. Slides
          // ignores paragraph spacing on bulleted paragraphs (measured), so the exporter spaces the items with line
          // spacing: pitch / lines per item (exact for the item pitch; see FIX-gslides-visual.md, section 13).
          var itemLines = null, itemPitch = null, itemFont = fsz;
          if (el.tagName === 'UL' || el.tagName === 'OL') {
            var lis = [];
            for (var lk = 0; lk < el.children.length; lk++) {
              var lc = el.children[lk];
              if (lc.tagName === 'LI' && visible(lc, getComputedStyle(lc))) lis.push(lc);
            }
            if (lis.length && runs.some(function (r) { return r.list; })) {
              // each item's OWN font and line height (the <li> is 22 px at 1.45 in a <ul> that is 16 px 'normal': using the
              // list's values gave two lines per item, and a 123% spacing that rendered 32 px apart in Google)
              var liCs = getComputedStyle(lis[0]);
              itemFont = parseFloat(liCs.fontSize) || fsz;
              var lhPx = parseFloat(liCs.lineHeight) || itemFont * 1.2;
              var rects = lis.map(function (li) { return rectOf(li, slideRect, scale); });
              itemLines = rects.map(function (r) { return Math.max(1, Math.round(r.h / lhPx)); });
              itemPitch = rects.map(function (r, k) {
                return k < rects.length - 1 ? rects[k + 1].y - r.y : r.h;
              });
            }
          }
          els.push({
            type: 'text', x: trt.x, y: trt.y, w: trt.w, h: trt.h,
            itemLines: itemLines, itemPitch: itemPitch, itemFontPx: itemFont,
            tw: tnr ? tnr.w : trt.w,
            align: al.h, valign: forceTop ? 'TOP' : al.v,
            oneLine: trt.h <= 1.7 * dispPx,
            // the HTML line count of the glyphs (what must survive into Slides): one line stays one line
            // a run with no text node (a glyph icon such as an arrow svg) is one line: never null, numbers only
            htmlLines: tnr ? Math.max(1, Math.round(tnr.h / (isNaN(lh) ? fsz * 1.2 : lh))) : 1,
            // letter-spacing (px, negative for tight titles) and the character count: Slides has no tracking,
            // so its line is wider by the tracking the HTML took out
            ls: parseFloat(cs.letterSpacing) || 0,
            // preformatted (code, terminals): leading spaces are indentation, not layout (kept as non-breaking spaces)
            pre: cs.whiteSpace.indexOf('pre') === 0,
            nch: runs.reduce(function (n, r) { return n + (r.br ? 0 : r.text.length); }, 0),
            fontPx: dispPx,
            noWrap: noWrap,
            lineHeightPct: isNaN(lh) ? 120 : Math.round(lh / fsz * 100),
            runs: runs
          });
        }
        // An inline-block ::after with a background and no text (a terminal's blinking cursor: `.js-type::after`)
        // is not absolutely positioned, so emitPseudos never sees it. It sits right after the block's last glyph.
        var acs = getComputedStyle(el, '::after');
        var acol = parseColor(acs.backgroundColor);
        if (acol && acs.display === 'inline-block' && /^(""|'')$/.test(acs.content || '') &&
            acs.position !== 'absolute' && acs.position !== 'fixed') {
          var lastTn = null, walkN = [el];
          while (walkN.length) {
            var nn = walkN.pop();
            if (nn.nodeType === 3 && nn.nodeValue.trim()) lastTn = nn;
            for (var lc = 0; nn.childNodes && lc < nn.childNodes.length; lc++) walkN.push(nn.childNodes[lc]);
          }
          if (lastTn) {
            var lr = document.createRange();
            lr.setStart(lastTn, lastTn.nodeValue.length - 1); lr.setEnd(lastTn, lastTn.nodeValue.length);
            var lrects = lr.getClientRects();
            if (lrects.length) {
              var lb = lrects[lrects.length - 1];
              var fpx = parseFloat(acs.fontSize) || parseFloat(cs.fontSize) || 16;
              var cw = 0.55 * fpx, chh = fpx;
              els.push({ type: 'rect', x: (lb.right - slideRect.left) / scale, y: (lb.top + lb.height * 0.12 - slideRect.top) / scale,
                         w: cw, h: chh, shape: null, fill: acol.hex, fillAlpha: acol.a, radius: 0, ellipse: false, border: null });
            }
          }
        }
        return; // leaf: don't descend
      }

      for (var i = 0; i < el.children.length; i++) walk(el.children[i]);
    }

    walk(slideEl);
    return { background: bg ? bg.hex : null, elements: els };
  }

  function buildIR() {
    var wraps = document.querySelectorAll('.slide-wrap');
    // The deck shows only the active slide; reveal every wrap so hidden slides
    // are laid out (and thus measurable) during extraction, then restore.
    var restore = [];
    wraps.forEach(function (w) {
      restore.push([w, w.style.display]);
      w.style.display = 'block';
    });

    // "-cool" slides only draw their charts/bars/rings/count-ups when a slide
    // becomes active — during a bulk extract that never happens, so they'd
    // measure empty or mid-animation (CSS animations don't advance reliably
    // under headless virtual-time). So drive every slide to its FINAL frame
    // DETERMINISTICALLY, exactly like the deck's PDF path: force the chart
    // end-states with CSS (no reliance on animation timing) and fire the deck's
    // beforeprint handler (count-ups, gauge rings, self-typing terminal).
    var printStyle = applyPrintStylesOnScreen();
    try { window.dispatchEvent(new Event('beforeprint')); } catch (e) {}

    return new Promise(function (resolve) {
      // brief settle for reflow/paint, then measure
      setTimeout(function () {
        var tasks = [];
        var slides = [];
        wraps.forEach(function (w) {
          if (w.classList.contains('no-print')) return;
          var s = w.querySelector('.slide');
          if (!s) return;
          var slideIR = extractSlide(s, tasks);
          // Speaker notes live in a .notes sibling of .slide (outside the slide
          // box, so the walk never sees them) — carry them to the Slides notes page.
          var notesEl = w.querySelector('.notes');
          if (notesEl) {
            var nt = (notesEl.innerText || notesEl.textContent || '').replace(/\s+\n/g, '\n').trim();
            if (nt) slideIR.notes = nt;
          }
          slides.push(slideIR);
        });
        Promise.all(tasks).then(function () {
          restore.forEach(function (r) { r[0].style.display = r[1]; });
          if (printStyle && printStyle.parentNode) printStyle.parentNode.removeChild(printStyle);
          try { window.dispatchEvent(new Event('afterprint')); } catch (e) {}
          // An image with neither a rasterised payload nor a source path could not be drawn. It is kept, so
          // the exporter draws a labelled placeholder and lists it in the run summary; dropping it silently
          // is how a whole row of icons went missing from the Slides copy.
          slides.forEach(function (s) {
            s.elements.forEach(function (e) {
              if (e.type === 'image' && !e.data && !e.src) e.undrawn = true;
            });
          });
          resolve({
            title: (document.title || 'Presentation').replace(/\s+/g, ' ').trim(),
            widthPx: DESIGN_W, heightPx: DESIGN_H,
            slides: slides,
            fontSubstitutions: FONT_SUBS
          });
        });
      }, 350);
    });
  }

  // Put every animated chart into its FINAL frame on-screen, exactly as the
  // deck's @media print block does — so the export matches the PDF. We can't
  // read the print CSS from a file:// stylesheet (SecurityError), so we inject
  // the known chart end-state declarations directly (and, best-effort, also copy
  // any readable @media print rules for http-served decks / future changes).
  function applyPrintStylesOnScreen() {
    var css =
      '.slide{animation:none!important;opacity:1!important}' +
      '.chart .bar{transform:none!important}' +
      '.chart .bar .val{opacity:1!important}' +   // cool-bar values are hover-only on screen; reveal for export
      '.gantt .g-bar,.funnel .f-stage{transform:none!important;animation:none!important}' +
      // dasharray:1 (the draw-on setup, pathLength=1) would read as a dotted line; the final frame is solid.
      '.linechart .line{stroke-dasharray:none!important;stroke-dashoffset:0!important;animation:none!important}' +
      '.linechart .area,.linechart .dot{opacity:1!important;animation:none!important}' +
      '.donut svg{opacity:1!important;transform:none!important;animation:none!important}';
    // best-effort: also lift any readable @media print rules (http-served decks)
    for (var i = 0; i < document.styleSheets.length; i++) {
      var rules;
      try { rules = document.styleSheets[i].cssRules; } catch (e) { continue; }
      if (!rules) continue;
      for (var j = 0; j < rules.length; j++) {
        var rule = rules[j];
        if (rule.type === 4 &&
            /\bprint\b/.test(rule.media.mediaText) && !/\bscreen\b/.test(rule.media.mediaText)) {
          for (var k = 0; k < rule.cssRules.length; k++) {
            var t = rule.cssRules[k].cssText;
            if (!/display\s*:\s*none/.test(t)) css += t + '\n'; // keep slides measurable
          }
        }
      }
    }
    var s = document.createElement('style');
    s.id = '__gsPrintOnScreen';
    s.textContent = css;
    document.head.appendChild(s);
    return s;
  }

  // ---- public: IR download (respecting the chosen scope) -------------------
  // Build the IR and download it as deck.gslides.json. scope "selected" keeps
  // only the slides ticked in Overview (▦); "all" keeps every slide.
  window.exportGoogleSlidesIR = function (scope) {
    var undo = [];
    if (scope === 'selected') {
      document.querySelectorAll('.slide-wrap').forEach(function (w) {
        var cb = w.querySelector('.slide-checkbox input');
        if (cb && !cb.checked && !w.classList.contains('no-print')) {
          w.classList.add('no-print'); undo.push(w);
        }
      });
      if (!document.querySelectorAll('.slide-wrap:not(.no-print)').length) {
        undo.forEach(function (w) { w.classList.remove('no-print'); });
        alert('No slides selected. Open Overview (▦) and tick the slides you want, then try again.');
        return Promise.resolve(null);
      }
    }
    return buildIR().then(function (ir) {
      undo.forEach(function (w) { w.classList.remove('no-print'); });
      var blob = new Blob([JSON.stringify(ir)], { type: 'application/json' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'deck.gslides.json';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      return ir;
    });
  };

  // ---- public: menu entries — open an export panel (no auto-download) ------
  // Google Slides and PowerPoint are separate menu entries, each with All / Selected; each opens its own panel.
  window.openGSlides = function (scope) {
    var m = document.getElementById('exportMenu');
    if (m) m.classList.remove('open');
    showPanel('gslides', scope === 'selected' ? 'selected' : 'all');
  };
  window.openPptx = function (scope) {
    var m = document.getElementById('exportMenu');
    if (m) m.classList.remove('open');
    showPanel('pptx', scope === 'selected' ? 'selected' : 'all');
  };

  // The commands of tools/gslides/export_gslides.py, static literals (the panel shows them and copies them as
  // they are): the preview shares nothing; the builds come after the user's answer to the preview's question.
  var CMD = 'python3 tools/gslides/export_gslides.py \\\n'
          + '    --ir deck.gslides.json --deck . \\\n'
          + '    --folder <YOUR_DRIVE_FOLDER_ID> --preview';
  var CMD_BUILD = 'python3 tools/gslides/export_gslides.py \\\n'
                + '    --ir deck.gslides.json --deck . \\\n'
                + '    --folder <YOUR_DRIVE_FOLDER_ID> --no-images';
  var CMD_PPTX = 'python3 tools/gslides/export_gslides.py \\\n'
               + '    --ir deck.gslides.json --deck . \\\n'
               + '    --folder <YOUR_DRIVE_FOLDER_ID> --no-images --pptx';

  // Inline stroke icons, same style as the toolbar's Export button (24 viewBox,
  // currentColor, stroke-width 2.1). No glyphs or emoji in the panel.
  function panelIcon(paths) {
    return '<svg class="gs-ico" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + paths + '</svg>';
  }
  var ICON_X = panelIcon('<path d="M6 6l12 12M18 6L6 18"/>');
  var ICON_DOWN = panelIcon('<path d="M12 3v11"/><path d="M8 10l4 4 4-4"/><path d="M5 20h14"/>');
  var ICON_CHECK = panelIcon('<path d="M5 12.5l4.5 4.5L19 7.5"/>');
  function escHtml(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  // The Overview's ticked slides (the "Export selected" choice), and the slides in the deck.
  function tickedCount() { return document.querySelectorAll('.slide-wrap .slide-checkbox input:checked').length; }
  function slideCount() { return document.querySelectorAll('.slide-wrap').length; }

  // Copy text to the clipboard. file:// is a secure context in Chrome, but the Clipboard API can still be
  // refused, so a hidden textarea and execCommand('copy') is the fallback; the button says what happened.
  function copyText(text, done, failed) {
    function legacy() {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
      document.body.appendChild(ta); ta.select();
      var ok = false; try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      ta.remove();
      return ok;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { (legacy() ? done : failed)(); });
    } else {
      (legacy() ? done : failed)();
    }
  }
  function wireCopy(btn, text) {
    btn.onclick = function () {
      function again() { setTimeout(function () { btn.textContent = 'Copy command'; }, 1800); }
      copyText(text,
        function () { btn.innerHTML = ICON_CHECK + '<span>Copied</span>'; again(); },
        function () { btn.textContent = 'Copy failed. Select the text instead.'; again(); });
    };
  }

  function showPanel(kind, scope) {
    var existing = document.getElementById('gsPanel');
    if (existing) existing.remove();
    var returnFocus = document.activeElement;
    var pptx = kind === 'pptx';
    var total = slideCount(), ticked = tickedCount();
    var none = scope === 'selected' && ticked === 0;   // nothing ticked: the steps are off, not offered
    var title = pptx ? 'Export to PowerPoint (.pptx)' : 'Export to Google Slides';
    var lead = pptx
      ? 'PowerPoint files are made through Google Slides: the deck is built in your Drive folder, then converted. The Google Slides deck stays in Drive; the .pptx is saved in <code>exports/</code> next to this deck. Pictures stay pictures, and PowerPoint substitutes fonts it doesn’t have.'
      : 'Build a <b>native, editable</b> Google Slides deck: real text, shapes &amp; images, not screenshots, in a Drive folder you choose.';
    var scopeLine = none
      ? 'No slides are ticked in Overview. Open Overview (<b>G</b>), tick the slides you want, then export again.'
      : 'Scope: <b>' + (scope === 'selected' ? ticked + ' of ' + total + ' ticked in Overview' : 'all ' + total + ' slides') + '</b>';
    var off = none ? ' disabled' : '';
    var offCls = none ? ' gs-off' : '';
    var selectedNote = scope === 'selected' && !none
      ? ' To export only the ticked slides, click <b>Download layout</b> first and ask it to export that <code>deck.gslides.json</code>.'
      : '';
    var prompt = pptx
      ? '“Use the dbx-slides skill to export this deck to PowerPoint (.pptx). Build the Google Slides version first in this Drive folder: &lt;paste your folder link&gt;.”'
      : '“Use the dbx-slides skill to export this deck to Google Slides in this Drive folder: &lt;paste your folder link&gt;.”';
    var build = pptx ? CMD_PPTX : CMD_BUILD;
    var buildText = pptx
      ? 'Then build the PowerPoint file. <code>--no-images</code> leaves each image as a labelled placeholder. To include the images, use <code>--allow-public-images</code> instead: the script shares each image publicly for the few seconds Google needs to read it, then deletes it.'
      : 'Then build. <code>--no-images</code> leaves each image as a labelled placeholder. To include the images, use <code>--allow-public-images</code> instead: the script shares each image publicly for the few seconds Google needs to read it, then deletes it. The preview above lists the images that would be shared.';
    var wrap = document.createElement('div');
    wrap.id = 'gsPanel';
    wrap.innerHTML =
      '<div class="gs-card" role="dialog" aria-modal="true" aria-labelledby="gsPanelTitle">' +
        '<button class="gs-x" type="button" title="Close" aria-label="Close">' + ICON_X + '</button>' +
        '<h3 id="gsPanelTitle">' + title + '</h3>' +
        '<p class="gs-lead">' + lead + '</p>' +
        '<div class="gs-scope">' + scopeLine + '</div>' +
        '<div class="gs-opt' + offCls + '">' +
          '<div class="gs-onum">1</div>' +
          '<div class="gs-obody">' +
            '<div class="gs-otitle">Ask your AI agent</div>' +
            '<blockquote>' + prompt + '</blockquote>' +
            '<p class="gs-sub">The agent runs the preview, so you can confirm the folder and the images, then builds the ' +
              (pptx ? 'PowerPoint file.' : 'deck.') + selectedNote + '</p>' +
          '</div>' +
        '</div>' +
        '<div class="gs-opt' + offCls + '">' +
          '<div class="gs-onum">2</div>' +
          '<div class="gs-obody">' +
            '<div class="gs-otitle">Or run it yourself</div>' +
            '<div class="gs-actions"><button class="gs-dl" type="button"' + off + '>' + ICON_DOWN +
              '<span>Download layout (deck.gslides.json)</span></button></div>' +
            '<p class="gs-sub">Save the layout in this folder, then run from it (your gcloud sign-in, Slides and Drive scopes; see <code>tools/gslides/README.md</code>).</p>' +
            '<p class="gs-step">Preview first. It shares nothing:</p>' +
            '<pre>' + escHtml(CMD) + '</pre><button class="gs-copy" type="button"' + off + '>Copy command</button>' +
            '<p class="gs-step">' + buildText + '</p>' +
            '<pre>' + escHtml(build) + '</pre><button class="gs-copy" type="button"' + off + '>Copy command</button>' +
            (pptx ? '<p class="gs-sub">The file lands in <code>exports/</code> next to this deck folder. <code>--out-dir</code> picks another folder.</p>' : '') +
          '</div>' +
        '</div>' +
        '<p class="gs-note">The <b>folder id</b> is the last part of a Drive folder URL: ' +
          'drive.google.com/drive/folders/<b>THIS&nbsp;PART</b>.</p>' +
      '</div>';
    document.body.appendChild(wrap);

    function close() {
      document.removeEventListener('keydown', onKey);
      wrap.remove();
      if (returnFocus && returnFocus.focus) returnFocus.focus();
    }
    function onKey(e) { if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onKey);
    wrap.querySelector('.gs-x').onclick = close;
    wrap.addEventListener('click', function (e) { if (e.target === wrap) close(); });
    wrap.querySelector('.gs-x').focus();

    var dl = wrap.querySelector('.gs-dl');
    dl.onclick = function () {
      dl.disabled = true; dl.querySelector('span').textContent = 'Preparing...';
      Promise.resolve(window.exportGoogleSlidesIR(scope)).then(function (ir) {
        dl.disabled = false;
        dl.innerHTML = (ir ? ICON_CHECK + '<span>Downloaded deck.gslides.json</span>'
                           : ICON_DOWN + '<span>Download layout (deck.gslides.json)</span>');
      });
    };
    var texts = [CMD, build];
    [].forEach.call(wrap.querySelectorAll('.gs-copy'), function (btn, i) { wireCopy(btn, texts[i]); });
  }

  // Panel styles (kept here so the feature is self-contained). The same rules as the Docs panel
  // (dbx-docs assets/gdocs.js): neutral ink, no coral; print hides the panel.
  var st = document.createElement('style');
  st.textContent =
    '#gsPanel{position:fixed;inset:0;background:rgba(11,18,33,.55);display:flex;' +
      'align-items:center;justify-content:center;z-index:9999;padding:20px}' +
    '#gsPanel .gs-card{background:#fff;color:var(--db-navy,#1b3139);max-width:600px;width:100%;' +
      'max-height:90vh;overflow-y:auto;border-radius:16px;padding:28px 30px;' +
      'box-shadow:0 24px 60px rgba(0,0,0,.4);font-family:var(--font,system-ui,sans-serif);position:relative}' +
    '#gsPanel h3{margin:0 0 6px;font-size:22px;font-weight:700}' +
    '#gsPanel .gs-ico{display:inline-block;vertical-align:-2px;margin-right:6px}' +
    '#gsPanel .gs-dl,#gsPanel .gs-copy{display:inline-flex;align-items:center}' +
    '#gsPanel .gs-lead{margin:0 0 14px;line-height:1.5;font-size:14px;color:var(--db-ink-soft,#5a6672)}' +
    '#gsPanel .gs-scope{font-size:12.5px;color:var(--db-ink-soft,#5a6672);background:var(--db-oat-light,#F9F7F4);border-radius:8px;' +
      'padding:8px 12px;margin-bottom:6px}' +
    '#gsPanel .gs-opt{display:flex;gap:14px;padding:12px 0;border-top:1px solid var(--db-oat-med,#e9e5dd)}' +
    '#gsPanel .gs-opt.gs-off{opacity:.45}' +
    '#gsPanel .gs-onum{flex:0 0 26px;height:26px;border-radius:50%;background:var(--db-navy,#1B3139);color:#fff;' +
      'font-weight:700;font-size:14px;display:flex;align-items:center;justify-content:center}' +
    '#gsPanel .gs-obody{flex:1;min-width:0}' +
    '#gsPanel .gs-otitle{font-weight:700;font-size:15px;margin-bottom:4px}' +
    '#gsPanel p{margin:6px 0;line-height:1.5;font-size:13.5px}' +
    '#gsPanel .gs-sub{color:var(--db-ink-soft,#5a6672);font-size:12.5px}' +
    '#gsPanel .gs-step{margin:10px 0 2px;font-weight:600;font-size:13px}' +
    '#gsPanel blockquote{margin:8px 0;padding:9px 14px;border-left:3px solid var(--db-steel,#5891AD);background:var(--db-oat-light,#F9F7F4);' +
      'border-radius:0 8px 8px 0;font-size:13.5px;color:var(--db-navy,#1b3139)}' +
    '#gsPanel pre{background:var(--db-ink-900,#0B2026);color:var(--on-db-ink-900,#E8EEF7);padding:12px 14px;border-radius:8px;' +
      'font-family:var(--mono,monospace);font-size:12px;overflow-x:auto;margin:8px 0 8px;white-space:pre}' +
    '#gsPanel code{background:var(--db-oat-med,#EEEDE9);padding:1px 5px;border-radius:4px;font-family:var(--mono,monospace);font-size:.88em}' +
    '#gsPanel .gs-note{font-size:12px;color:var(--db-ink-soft,#5a6672);margin:16px 0 0;padding-top:14px;border-top:1px solid var(--db-oat-med,#e9e5dd)}' +
    '#gsPanel .gs-actions{margin:10px 0}' +
    '#gsPanel .gs-dl{background:var(--db-navy,#1B3139);color:#fff;border:0;border-radius:8px;padding:10px 16px;' +
      'font-size:13.5px;font-weight:600;cursor:pointer;font-family:var(--font,system-ui,sans-serif)}' +
    '#gsPanel .gs-dl:hover{background:var(--db-ink-900,#0B2026)}#gsPanel .gs-dl:disabled{opacity:.7;cursor:default}' +
    '#gsPanel .gs-copy{background:none;color:var(--db-ink-soft,#5a6672);border:1px solid var(--db-line,#DCE0E2);border-radius:7px;' +
      'padding:6px 12px;font-size:12.5px;cursor:pointer;font-family:var(--font,system-ui,sans-serif)}' +
    '#gsPanel .gs-copy:hover{background:var(--db-oat-light,#F9F7F4)}#gsPanel .gs-copy:disabled{opacity:.5;cursor:default}' +
    '#gsPanel .gs-x{position:absolute;top:16px;right:18px;border:0;background:none;font-size:18px;' +
      'cursor:pointer;color:var(--db-ink-soft,#5a6672);line-height:1}' +
    '#gsPanel .gs-x:focus-visible,#gsPanel .gs-dl:focus-visible,#gsPanel .gs-copy:focus-visible{outline:2px solid var(--db-navy,#1B3139);outline-offset:2px}' +
    '@media print{#gsPanel{display:none!important}}';
  document.head.appendChild(st);

  // ---- headless dump path (?gslides=dump) ----------------------------------
  // deck.js injects the slides one script at a time, and a slide file may add its slide a little later, so the dump
  // waits until the slide count reaches the manifest's count (window.DECK_SLIDES, the names not starting with "_")
  // and stays there for 600 ms. On timeout (?dumpTimeout=ms, default 30 s) it still dumps, marked data-timed-out="1".
  // The dump carries data-loaded and data-expected; export_gslides.py and the e2e harness refuse a short one.
  function expectedSlideCount() {
    return (window.DECK_SLIDES || []).filter(function (n) { return !String(n).startsWith('_'); }).length;
  }
  function waitForSlides(then) {
    var m = /[?&]dumpTimeout=(\d+)/.exec(location.search);
    var limit = m ? Number(m[1]) : 30000;
    var start = Date.now(), last = -1, since = start;
    var iv = setInterval(function () {
      var now = Date.now();
      var have = document.querySelectorAll('.slide-wrap').length;
      var want = expectedSlideCount();
      if (have !== last) { last = have; since = now; }
      var reached = have > 0 && (want === 0 || have >= want);
      var settled = reached && now - since >= 600;
      var timedOut = now - start >= limit;
      if (settled || timedOut) {
        clearInterval(iv);
        then({ loaded: have, expected: want, timedOut: !settled });
      }
    }, 150);
  }
  function dumpForHeadless(count) {
    buildIR().then(function (ir) {
      var ta = document.createElement('textarea');
      ta.id = '__gsir__';
      // NB: set textContent, not .value — only serialised DOM text survives
      // Chrome's --dump-dom (the live .value property does not).
      ta.textContent = JSON.stringify(ir);
      ta.setAttribute('data-ready', '1');
      ta.setAttribute('data-loaded', String(count.loaded));
      ta.setAttribute('data-expected', String(count.expected));
      if (count.timedOut) ta.setAttribute('data-timed-out', '1');
      document.body.appendChild(ta);
      window.__gsirReady = true;
    });
  }

  if (/[?&]gslides=dump/.test(location.search)) {
    // Wait for the slides to be injected and stable, and the fonts ready, then dump.
    waitForSlides(function (count) {
      var go = function () { setTimeout(function () { dumpForHeadless(count); }, 300); };
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(go); else go();
    });
  }
})();
