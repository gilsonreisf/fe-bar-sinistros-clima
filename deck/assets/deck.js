/* =========================================================================
   DATABRICKS PRESENTATION TEMPLATE — behavior
   -------------------------------------------------------------------------
   Navigation · grid overview · in-window notes · separate speaker view
   (live-synced) · demo frames · PDF export · progress bar · deep links.
   Speaker notes live inside each slide file as <div class="notes">…</div>.
   ========================================================================= */

const IS_PRESENTER = location.hash.replace(/^#/, '').split('?')[0] === 'presenter';
// Honour the OS "reduce motion" setting: count-up and self-typing jump straight
// to their final state (CSS handles the pure-CSS animations — see style.css).
const PREFERS_REDUCED = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
let wraps = [];          // populated after slides load
let current = 0;

/* =========================================================================
   SLIDE LOADING — no server, no build (works from a file:// URL)
   -------------------------------------------------------------------------
   Each slide is a slides/NN-name.js file that calls DECK.slide(`…html…`).
   slides/manifest.js lists them in order (window.DECK_SLIDES). We inject the
   scripts one after another (a <script> tag CAN load local files, unlike
   fetch), so they run in order and append to #deck.
   (If the deck was pre-assembled into one file, the slides already exist in
   the DOM and this step is skipped.)
   ========================================================================= */
window.DECK = {
  slide(html){
    const deck = document.getElementById('deck');
    if (deck) deck.insertAdjacentHTML('beforeend', html);
  }
};

function loadSlidesViaScripts(){
  return new Promise(resolve => {
    const list = (window.DECK_SLIDES || []).filter(n => !String(n).startsWith('_'));
    let i = 0;
    const next = () => {
      if (i >= list.length) return resolve(document.querySelectorAll('.slide-wrap').length);
      const s = document.createElement('script');
      s.src = 'slides/' + list[i];
      s.onload = () => { i++; next(); };
      s.onerror = () => { console.warn('Slide not found:', list[i]); i++; next(); };
      document.head.appendChild(s);
    };
    next();
  });
}

/* Read the speaker note that ships inside a slide (may be empty). */
function noteFor(i){
  const el = wraps[i] && wraps[i].querySelector('.notes');
  return el ? el.innerHTML.trim() : '';
}

function showLoadHelp(){
  document.getElementById('deck').innerHTML =
    '<div class="load-help">' +
      '<h2>No slides loaded</h2>' +
      '<p>Slides live in <code>slides/*.js</code> and are listed in <code>slides/manifest.js</code>.</p>' +
      '<p>To add one: copy an existing <code>slides/NN-name.js</code>, edit it, and add its filename to the list in <code>slides/manifest.js</code>. Then refresh.</p>' +
    '</div>';
}

/* The official footer (small stacked-layers mark + copyright bottom-left, slide
   number bottom-right) is identical on every slide, so we inject it here instead
   of hand-writing it in 50+ files. A slide opts out with class `.no-foot`; title
   and closing slides keep the footer but hide the number via CSS. If a slide
   already ships a `.foot` (older markup), we normalise it to this content. */
const BRAND_MARK = 'resources/databricks-icon.svg';
const COPYRIGHT = '©2026 Databricks, Inc. — All rights reserved';
function decorateSlide(wrap){
  const slide = wrap.querySelector('.slide');
  if (!slide || slide.dataset.decorated) return;
  slide.dataset.decorated = '1';
  if (slide.classList.contains('no-foot')) return;
  let foot = slide.querySelector('.foot');
  if (!foot){ foot = document.createElement('div'); foot.className = 'foot'; slide.appendChild(foot); }
  foot.innerHTML =
    '<span class="foot-cr"><img class="foot-mark" src="' + BRAND_MARK + '" alt=""> ' + COPYRIGHT + '</span>' +
    '<span class="pageno"></span>';
}

/* Set up everything once slides are in the DOM. */
function initDeck(){
  wraps.forEach((w, i) => {
    decorateSlide(w);
    const p = w.querySelector('.pageno');
    if (p) p.textContent = String(i + 1).padStart(2, '0');

    const cb = document.createElement('label');
    cb.className = 'slide-checkbox';
    cb.title = 'Include in “Export selected”';
    cb.innerHTML = '<input type="checkbox" checked>';
    cb.querySelector('input').addEventListener('change', updateSelection);
    cb.addEventListener('click', e => e.stopPropagation());
    w.appendChild(cb);

    const badge = document.createElement('div');
    badge.className = 'slide-idx';
    badge.textContent = i + 1;
    w.appendChild(badge);

    w.addEventListener('click', () => {
      if (document.body.classList.contains('grid-mode')) { goTo(i); toggleGrid(); }
    });
  });

  const totalEl = document.getElementById('total');
  if (totalEl) totalEl.textContent = wraps.length;
  document.getElementById('selAll')?.addEventListener('click', () => setAllSelected(true));
  document.getElementById('selNone')?.addEventListener('click', () => setAllSelected(false));
  updateSelection();

  initInteractive();

  if (IS_PRESENTER){
    buildPresenter();
  } else {
    const h = location.hash.slice(1);
    if (/^\d+$/.test(h)) current = clamp(parseInt(h, 10) - 1);   // deep link: index.html#5
    const help = document.getElementById('help');
    if (help){ help.classList.add('show'); setTimeout(() => help.classList.remove('show'), 4600); }
  }
  fitStepBadges();
  fit();
  render();
}

/* ---------- Render ------------------------------------------------------ */
function render(){
  wraps.forEach((w, i) => w.classList.toggle('active', i === current));
  const cur = document.getElementById('cur'); if (cur) cur.textContent = current + 1;
  const bar = document.querySelector('#progress span');
  if (bar) bar.style.width = ((current + 1) / wraps.length * 100) + '%';
  if (IS_PRESENTER) renderPresenter();
  else {
    renderNotesBar();
    if (!document.body.classList.contains('grid-mode')){
      runSlideEnter(wraps[current].querySelector('.slide') || wraps[current]);     // scope to the slide (skip hidden .notes)
      resetReveals(current);                                                       // flips/sliders start fresh on entry
      applyStoredInteractions(wraps[current].querySelector('.slide'), current);    // restore stateful ones (demo/video)
    }
    // NOTE: we deliberately do NOT write the current slide into the URL hash.
    // Doing so made the browser "remember" the slide across reopens/session
    // restore (and reopen a restored speaker-view popup mid-deck). The deck
    // always starts at slide 1; a deep link still works if a hash is present at
    // load (index.html#5), it just isn't auto-written as you navigate.
  }
  repositionLaser();
}
function goTo(i){ current = clamp(i); render(); broadcast(); }         // local nav → sync
function applyRemote(i){ const n = clamp(i); if (n === current) return; current = n; render(); }
function clamp(i){ return Math.max(0, Math.min(wraps.length - 1, i)); }
function next(){ if (current < wraps.length - 1) goTo(current + 1); }
function prev(){ if (current > 0) goTo(current - 1); }

/* ---------- Fit the active slide to the viewport ------------------------ */
/* Step badges (architecture kit): a badge keeps its own colour while it has 3:1 against the surface under it. Under a
   brand pack whose colour is light on a light surface, it takes the navy or the white badge, whichever contrasts more,
   and its number takes the other one. The Databricks colours always pass, so the look is unchanged. */
function fitStepBadges(){
  const parse = s => { const m = /rgba?\(([^)]+)\)/.exec(s || ''); if (!m) return null;
    const v = m[1].split(/[ ,\/]+/).map(Number); return v.length >= 3 ? v : null; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const num = v => parseFloat(v) || 0;
  document.querySelectorAll('svg[data-arch-check]').forEach(svg => {
    const rects = [...svg.querySelectorAll('rect')].filter(r => !r.closest('defs,marker')).map(r => ({
      x: num(r.getAttribute('x')), y: num(r.getAttribute('y')), w: num(r.getAttribute('width')), h: num(r.getAttribute('height')), el: r }));
    const texts = [...svg.querySelectorAll('text')].filter(t => /^\d$/.test(t.textContent.trim()));
    svg.querySelectorAll('circle').forEach(c => {
      const cx = num(c.getAttribute('cx')), cy = num(c.getAttribute('cy'));
      const t = texts.find(t => Math.abs(num(t.getAttribute('x')) - cx) < 0.5 && Math.abs(num(t.getAttribute('y')) - cy) < 8);
      if (!t) return;
      const surf = rects.filter(q => q.x < cx && cx < q.x + q.w && q.y < cy && cy < q.y + q.h)
        .sort((a, b) => a.w * a.h - b.w * b.h)[0];
      let bg = surf ? parse(getComputedStyle(surf.el).fill) : null;
      if (!bg) { for (let e = svg; e && !bg; e = e.parentElement) { const v = parse(getComputedStyle(e).backgroundColor); if (v && (v.length < 4 || v[3] > 0)) bg = v; } }
      bg = bg || [255, 255, 255];
      const cur = parse(getComputedStyle(c).fill);
      if (!cur || ratio(cur, bg) >= 3) return;
      const options = [['var(--db-navy)', 'var(--db-white,#FFFFFF)'], ['var(--db-white,#FFFFFF)', 'var(--db-navy)']];
      let best = null;
      options.forEach(([fill, text]) => {
        c.style.fill = fill; const f = parse(getComputedStyle(c).fill);
        const r = f ? ratio(f, bg) : 0;
        if (!best || r > best.r) best = { r, fill, text };
      });
      c.style.fill = best.fill; t.style.fill = best.text;
    });
  });
}

function fit(){
  const present = document.body.classList.contains('present-mode');
  const toolbarH = present ? 0 : parseInt(getComputedStyle(document.documentElement).getPropertyValue('--toolbar-h'));
  const notesH = document.body.classList.contains('show-notes')
    ? (parseInt(getComputedStyle(document.documentElement).getPropertyValue('--notes-h')) || 0) : 0;
  const availW = window.innerWidth;
  const availH = window.innerHeight - toolbarH - notesH;
  const s = Math.min(availW / 1280, availH / 720) * (present ? 1 : 0.94);
  document.documentElement.style.setProperty('--fit', s.toFixed(4));
  // The keyboard hint (#help) sits in the gutter under the slide: 8 px from the window's bottom and about 28 px tall.
  // Where the fit leaves less gutter than that (a 16:9 window), or the notes bar is open, it would cover the footer text,
  // so it is not shown then (body.no-help-room, style.css).
  const HELP_ROOM = 36;
  const gutter = (availH - 720 * s) / 2;
  document.body.classList.toggle('no-help-room', notesH > 0 || gutter < HELP_ROOM);
  repositionLaser();
}
window.addEventListener('resize', () => { if (IS_PRESENTER) refitClones(); else fit(); });

function toggleGrid(){
  document.body.classList.toggle('grid-mode');
  if (!document.body.classList.contains('grid-mode')) { fit(); render(); }
}
function fullscreen(){
  if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
  else document.exitFullscreen?.();
}

/* In fullscreen "Present" mode the toolbar hides so the audience sees only the
   slide; it slides back in on mouse movement (and hides again after a pause). */
let chromeTimer = null;
function revealChrome(){
  if (!document.body.classList.contains('present-mode')) return;
  document.body.classList.add('chrome');
  clearTimeout(chromeTimer);
  chromeTimer = setTimeout(() => document.body.classList.remove('chrome'), 2600);
}
document.addEventListener('fullscreenchange', () => {
  const on = !!document.fullscreenElement;
  document.body.classList.toggle('present-mode', on);
  document.body.classList.remove('chrome');
  if (on) revealChrome();
  if (IS_PRESENTER) refitClones(); else fit();
});
// Only reveal the toolbar when the pointer hits the very top edge of the screen
// (like the macOS menu bar), so it doesn't pop up while you move over the slide
// or a demo's controls. Esc always exits fullscreen too.
document.addEventListener('mousemove', (e) => {
  if (document.body.classList.contains('present-mode') && e.clientY <= 8) revealChrome();
});

/* ---------- In-window notes bar ----------------------------------------- */
function toggleNotes(){ document.body.classList.toggle('show-notes'); fit(); renderNotesBar(); }
function renderNotesBar(){
  const body = document.getElementById('nbBody'), num = document.getElementById('nbNum');
  if (!body) return;
  if (num) num.textContent = current + 1;
  body.innerHTML = noteFor(current) || '<em>No notes for this slide.</em>';
  const bar = document.getElementById('notesBar'); if (bar) bar.scrollTop = 0;   // long notes start at top
}

/* ---------- Overview selection ("Export selected") ------------------------
   The checkboxes on the slides pick the slides for a Selected export (PDF or Google Slides). The bar under
   the overview shows how many are ticked and has Select all / Select none; the two "Selected slides" items
   of the Export menu are off while nothing is ticked. Selection is read at export time (exportPDF and the
   Slides layout), and it never changes what a slide renders as. */
function selectionBoxes(){ return wraps.map(w => w.querySelector('.slide-checkbox input')).filter(Boolean); }
function setAllSelected(on){ selectionBoxes().forEach(cb => { cb.checked = on; }); updateSelection(); }
function updateSelection(){
  const boxes = selectionBoxes(), n = boxes.filter(cb => cb.checked).length;
  const count = document.getElementById('selCount');
  if (count) count.textContent = n + ' of ' + boxes.length + ' selected';
  ['pdfSelected', 'gsSelected', 'pptxSelected'].forEach(id => {
    const b = document.getElementById(id);
    if (!b) return;
    b.disabled = n === 0;
    b.title = n === 0 ? 'Tick at least one slide in Overview first' : '';
  });
}

/* ---------- Export dropdown --------------------------------------------- */
const menu = document.getElementById('exportMenu');
function toggleMenu(e){ e.stopPropagation(); menu.classList.toggle('open'); }
document.addEventListener('click', () => menu && menu.classList.remove('open'));
function exportPDF(mode){
  if (menu) menu.classList.remove('open');
  wraps.forEach(w => w.classList.remove('no-print'));
  if (mode === 'selected'){
    wraps.forEach(w => { if (!w.querySelector('.slide-checkbox input').checked) w.classList.add('no-print'); });
    if (wraps.every(w => w.classList.contains('no-print'))){
      alert('No slides selected. Open Overview and tick the slides you want to export.');
      return;
    }
  }
  window.print();
}
window.addEventListener('afterprint', () => wraps.forEach(w => w.classList.remove('no-print')));

/* =========================================================================
   DEMO SLIDES — launch one or many live URLs in a frame inside the slide
   -------------------------------------------------------------------------
   A launcher is any .demo-launch with data-url (+ optional data-label,
   data-mode="embed|popup"). A slide may hold several; embeddable ones become
   tabs in the frame so you can switch between demos. Single-demo slides can
   still put the URL on the slide via data-demo-url / data-demo-mode.
   ========================================================================= */
document.addEventListener('click', e => {
  const btn = e.target.closest('.demo-launch');
  if (!btn) return;
  const slide = btn.closest('.slide');
  const url  = btn.dataset.url  || slide.dataset.demoUrl;
  const mode = btn.dataset.mode || slide.dataset.demoMode || 'embed';
  if (mode === 'popup'){ window.open(url, '_blank', 'noopener'); return; }
  setDemoForSlide(slide, url);     // embed → open here AND mirror to the other window
});

function labelFromUrl(u){ try { return new URL(u).hostname.replace(/^www\./, ''); } catch(_) { return 'Demo'; } }
function embedLaunchers(slide){
  return Array.from(slide.querySelectorAll('.demo-launch'))
    .filter(b => (b.dataset.mode || slide.dataset.demoMode || 'embed') !== 'popup' && (b.dataset.url || slide.dataset.demoUrl));
}

function buildDemoFrame(slide){
  const frame = document.createElement('div');
  frame.className = 'demo-frame';
  frame.innerHTML =
    '<div class="demo-bar">' +
      '<div class="demo-tabs"></div>' +
      '<span class="demo-bar-url"></span><div style="flex:1"></div>' +
      '<button class="tbtn" data-demo-reload>⟳ Reload</button>' +
      '<a class="tbtn" data-demo-open target="_blank" rel="noopener">Open in new tab ↗</a>' +
      '<button class="tbtn" data-demo-close>✕ Close</button>' +
    '</div>' +
    '<div class="demo-views"></div>';
  slide.appendChild(frame);

  // A tab per embeddable demo when the slide offers more than one.
  const launchers = embedLaunchers(slide);
  if (launchers.length > 1){
    const tabs = frame.querySelector('.demo-tabs');
    launchers.forEach(b => {
      const u = b.dataset.url || slide.dataset.demoUrl;
      const tab = document.createElement('button');
      tab.className = 'demo-tab';
      tab.textContent = b.dataset.label || labelFromUrl(u);
      tab.dataset.url = u;
      tab.onclick = () => setDemoForSlide(slide, u);   // switching tabs mirrors too
      tabs.appendChild(tab);
    });
  }
  frame.querySelector('[data-demo-reload]').onclick = () => {
    const v = frame.querySelector('.demo-views iframe.active'); if (v) v.src = v.dataset.url;
  };
  frame.querySelector('[data-demo-close]').onclick = () => { setDemoForSlide(slide, null); };
  return frame;
}

function openDemo(slide, url, mode){
  if (!slide || !url) return;
  if (mode === 'popup'){ window.open(url, '_blank', 'noopener'); return; }

  const frame = slide.querySelector('.demo-frame') || buildDemoFrame(slide);
  frame.classList.add('active');   // show the frame BEFORE the iframe loads, so the iframe has real dimensions

  const views = frame.querySelector('.demo-views');

  // Reuse the iframe already loaded for this URL (preserves its navigation);
  // create one the first time a given demo is opened.
  let view = Array.from(views.children).find(f => f.dataset.url === url);
  if (!view){
    view = document.createElement('iframe');
    view.dataset.url = url;
    view.setAttribute('allow', 'fullscreen; clipboard-read; clipboard-write');
    views.appendChild(view);
  }
  Array.from(views.children).forEach(f => f.classList.toggle('active', f === view));

  // Load the src only once the iframe actually has size on screen. A demo opened
  // on a slide that isn't visible yet — mirrored from the other window, or restored
  // before its slide is shown — would be 0×0, and map embeds (OpenStreetMap/Leaflet)
  // measure their container just once at load, so they'd render only a corner.
  // Entering the slide re-runs openDemo (via applyStoredInteractions), which loads
  // it then, at full size. Responsive pages reflow on their own, so this only helps.
  if (!view.src && view.offsetWidth && view.offsetHeight) view.src = view.dataset.url;

  const openA = frame.querySelector('[data-demo-open]'); if (openA) openA.href = url;
  const hasTabs = frame.querySelectorAll('.demo-tab').length > 0;
  frame.querySelector('.demo-bar-url').textContent = hasTabs ? '' : url;
  frame.querySelectorAll('.demo-tab').forEach(t => t.classList.toggle('active', t.dataset.url === url));
}

/* =========================================================================
   INTERACTIVE / CREATIVE TEMPLATES
   -------------------------------------------------------------------------
   runSlideEnter() replays enter-animations each time a slide is shown;
   initInteractive() wires one-time handlers (flip cards, compare sliders).
   ========================================================================= */
function runSlideEnter(wrap){
  if (!wrap) return;
  // Stop any self-typing still running on other (now-hidden) slides so their
  // intervals don't tick in the background after you navigate away.
  document.querySelectorAll('.js-type').forEach(el => { if (el._t){ clearInterval(el._t); el._t = null; } });
  playEnter(wrap);
}
// Play every enter-animation inside a container (a real slide-wrap OR a cloned
// slide in the speaker view). Kept free of any global/side-window state so it
// can run on the presenter clones too — that's what makes charts, count-ups and
// the self-typing terminal actually appear (and finish) in the speaker view
// instead of freezing on their first frame.
function playEnter(root){
  if (!root) return;
  root.querySelectorAll('.count[data-count]').forEach(animateCount);
  // Replay any CSS enter-animation (charts, gantt, funnel, donut, line…).
  const replay = el => { el.classList.remove('play'); void el.offsetWidth; el.classList.add('play'); };
  root.querySelectorAll('.chart:not(.static), .js-enter').forEach(replay);
  // Progress rings: reset to empty, then animate the stroke to the target %.
  root.querySelectorAll('.ring[data-pct]').forEach(r => {
    r.style.transition = 'none'; r.style.strokeDashoffset = '100';
    void r.getBoundingClientRect();
    r.style.transition = ''; r.style.strokeDashoffset = String(100 - parseFloat(r.dataset.pct));
  });
  root.querySelectorAll('.js-type').forEach(typeText);
}
// Snap a gauge ring straight to its target value (no sweep) — used wherever a
// ring must show its final state without animating: the "next slide" preview
// clone and the print/PDF pass. (playEnter does the animated version.)
function ringToFinal(r){
  r.style.transition = 'none';
  r.style.strokeDashoffset = String(100 - parseFloat(r.dataset.pct));
}
function animateCount(el){
  const to = parseFloat(el.dataset.count);
  if (isNaN(to)) return;
  const dec = parseInt(el.dataset.decimals || '0', 10);
  const pre = el.dataset.prefix || '', suf = el.dataset.suffix || '';
  if (PREFERS_REDUCED){ el.textContent = pre + to.toFixed(dec) + suf; return; }
  const my = (el._countTok = (el._countTok || 0) + 1);   // supersede any loop still running on this element
  const dur = 1000, t0 = performance.now();
  function step(t){
    if (el._countTok !== my) return;                     // a newer run (re-entry) took over — stop
    const p = Math.min(1, (t - t0) / dur);
    const v = (to * (1 - Math.pow(1 - p, 3))).toFixed(dec);
    el.textContent = pre + v + suf;
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
function typeText(el){
  if (el._full == null) el._full = el.textContent;
  el.dataset.full = el._full;   // survives cloneNode (JS props don't) so a clone can be settled to full text
  const full = el._full;
  clearInterval(el._t);
  if (PREFERS_REDUCED){ el.textContent = full; return; }
  el.textContent = '';
  let i = 0;
  el._t = setInterval(() => { el.textContent = full.slice(0, ++i); if (i >= full.length) clearInterval(el._t); }, 16);
}
/* ---------- Cross-window interaction sync -------------------------------
   Flip cards and before/after sliders are real interactions, so they're kept
   in step between the main deck and the speaker view. Each interactive element
   is addressed by (slide index : kind : index-within-slide); the latest value
   lives in `interact` so a freshly-cloned speaker pane can be restored to the
   current state, and every local change is echoed to the other window.
   The main (audience) view holds the live elements; the speaker view drives
   clones that mirror them — either side can move things, last change wins. */
const interact = {};                                   // "22:flip:0" -> true, "24:compare:0" -> 62.5
function interactKey(si, kind, idx){ return si + ':' + kind + ':' + idx; }

// Apply a value where it should show in THIS window. The audience window drives
// the real slides in the deck; the speaker view shows clones, so there we drive
// only the current-slide clone (the hidden real slides are never seen — and
// touching them would double-load demo iframes / videos).
function applyInteract(si, kind, idx, val){
  interact[interactKey(si, kind, idx)] = val;                 // always store (restored on entry)
  if (!IS_PRESENTER){
    // Reveals (flip/compare/bar) mirror on any slide, but stateful media (demo
    // iframes, <video>) must not be driven on a hidden slide — that would play
    // off-screen audio or double-load an iframe. They're restored on entry via
    // applyStoredInteractions instead.
    if ((kind === 'demo' || kind === 'video') && si !== current) return;
    if (wraps[si]) applyToScope(wraps[si].querySelector('.slide'), kind, idx, val);
  } else if (si === current){
    const stage = document.getElementById('pvCurStage');
    if (stage) applyToScope(stage.querySelector('.slide'), kind, idx, val);
  }
}
function applyToScope(root, kind, idx, val){
  if (!root) return;
  if (kind === 'flip'){
    const el = root.querySelectorAll('.flip')[idx];
    if (el) el.classList.toggle('flipped', !!val);
  } else if (kind === 'compare'){
    const el = root.querySelectorAll('.compare')[idx];
    if (el) el.style.setProperty('--pos', val + '%');
  } else if (kind === 'bar'){
    const el = root.querySelectorAll('.chart .col')[idx];       // hovered bar → reveal its value in both windows
    if (el) el.classList.toggle('hovered', !!val);
  } else if (kind === 'demo'){
    if (val) openDemo(root, val, 'embed');                      // launch / switch the embedded demo
    else { const f = root.querySelector('.demo-frame'); if (f) f.classList.remove('active'); }   // close
  } else if (kind === 'video'){
    const v = root.querySelectorAll('video')[idx];
    if (v) applyVideo(v, val);
  }
}
// Mirror a <video>'s play/pause/scrub. A guard flag stops the play()/pause() we
// trigger here from echoing back out as a fresh event. Speaker-view copies are
// muted so they can follow programmatically (browsers block unmuted autoplay).
function applyVideo(v, val){
  if (!val) return;
  v._syncing = true;
  try {
    if (val.time != null && Math.abs(v.currentTime - val.time) > 0.35) v.currentTime = val.time;
    if (val.playing){ if (IS_PRESENTER) v.muted = true; const p = v.play(); if (p && p.catch) p.catch(() => {}); }
    else v.pause();
  } catch(_){}
  clearTimeout(v._syncClr);
  v._syncClr = setTimeout(() => { v._syncing = false; }, 150);
}
// A local change: apply here, then tell the other window.
function setInteract(si, kind, idx, val){
  applyInteract(si, kind, idx, val);
  post({ type: 'interact', si, kind, idx, val });
}
// Which slide does a node live on? Real slides sit in a .slide-wrap; speaker-view
// clones sit in the current/next presenter stage.
function siOf(el){
  const wrap = el.closest('.slide-wrap');
  if (wrap) return wraps.indexOf(wrap);
  if (el.closest('#pvCurStage')) return current;
  if (el.closest('#pvNextStage')) return current + 1;
  return -1;
}
// Open (url) or close (null) the embedded demo on a slide, mirrored to the other
// window. Falls back to a plain local open if the slide isn't locatable.
function setDemoForSlide(slide, url){
  const si = siOf(slide);
  if (si < 0){
    if (url) openDemo(slide, url, 'embed');
    else { const f = slide.querySelector('.demo-frame'); if (f) f.classList.remove('active'); }
    return;
  }
  setInteract(si, 'demo', 0, url || null);
}
// Reveal-style interactions (flip cards, before/after sliders) start fresh each
// time a slide is ENTERED — like the enter-animations replay — so returning to a
// slide never shows a card someone left flipped. Demos and <video> are deliberate,
// stateful actions, so they're left as-is on entry. Live changes still mirror to
// the other window; only re-entry resets. Runs per-window on its own entry, so no
// extra messaging is needed (navigation is already synced).
const REVEAL_KINDS = ['flip', 'compare', 'bar'];   // transient reveals reset on entry; demo/video persist
function resetReveals(si){
  Object.keys(interact).forEach(k => {
    const [ksi, kind] = k.split(':');
    if (+ksi === si && REVEAL_KINDS.includes(kind)) delete interact[k];
  });
  const scope = IS_PRESENTER
    ? (si === current && document.querySelector('#pvCurStage .slide'))
    : (wraps[si] && wraps[si].querySelector('.slide'));
  if (!scope) return;
  scope.querySelectorAll('.flip.flipped').forEach(f => f.classList.remove('flipped'));
  scope.querySelectorAll('.compare').forEach(c => c.style.removeProperty('--pos'));   // back to the CSS/authored default
  scope.querySelectorAll('.chart .col.hovered').forEach(c => c.classList.remove('hovered'));
}
// Reflect all stored state for a slide onto a just-built element tree (a speaker
// clone): flips, slider positions, hovered bars, an open demo, a playing video.
function applyStoredInteractions(root, si, includePersistent){
  if (includePersistent === undefined) includePersistent = true;
  Object.keys(interact).forEach(k => {
    const [ksi, kind, idx] = k.split(':');
    if (+ksi !== si) return;
    // The next-slide preview (includePersistent=false) is a passive thumbnail:
    // never launch its demos or start its video — only reflect reveal state.
    if (!includePersistent && (kind === 'demo' || kind === 'video')) return;
    applyToScope(root, kind, +idx, interact[k]);
  });
}

function initInteractive(){
  wraps.forEach((w, si) => {
    const slide = w.querySelector('.slide'); if (!slide) return;
    wireInteractions(slide, si);
  });
}
// Wire every synced interaction on a slide (the live one) or a speaker clone:
// flip cards, before/after sliders, bar-chart hover, and video transport.
function wireInteractions(root, si){
  root.querySelectorAll('.flip').forEach((f, idx) =>
    f.addEventListener('click', () => setInteract(si, 'flip', idx, !f.classList.contains('flipped'))));
  root.querySelectorAll('.compare').forEach((c, idx) => wireCompare(c, si, idx));
  root.querySelectorAll('.chart .col').forEach((col, idx) => {
    col.addEventListener('mouseenter', () => setInteract(si, 'bar', idx, true));
    col.addEventListener('mouseleave', () => setInteract(si, 'bar', idx, false));
  });
  root.querySelectorAll('video').forEach((v, idx) => wireVideo(v, si, idx));
}
// Broadcast a video's transport on play/pause/scrub (unless we're mid-apply).
function wireVideo(v, si, idx){
  const emit = () => { if (v._syncing) return; setInteract(si, 'video', idx, { playing: !v.paused, time: v.currentTime }); };
  ['play', 'pause', 'seeked'].forEach(ev => v.addEventListener(ev, emit));
}
// A before/after slider: dragging broadcasts its position. Works on both the
// real slide and a speaker-view clone — getBoundingClientRect returns the
// on-screen (post-scale) rect, so the math holds at any zoom.
function wireCompare(el, si, idx){
  const set = clientX => {
    const r = el.getBoundingClientRect();
    const p = Math.max(0, Math.min(100, (clientX - r.left) / r.width * 100));
    setInteract(si, 'compare', idx, +p.toFixed(2));
  };
  let drag = false;
  el.addEventListener('pointerdown', e => { drag = true; try { el.setPointerCapture(e.pointerId); } catch(_){} set(e.clientX); });
  el.addEventListener('pointermove', e => { if (drag) set(e.clientX); });
  el.addEventListener('pointerup',   () => { drag = false; });
  el.addEventListener('pointercancel', () => { drag = false; });
}
// Before printing, settle every slide's JS-driven reveals to their final state
// (not just the ones that were visited). CSS-driven reveals are handled by the
// @media print rules; this covers the self-typing terminal, count-ups, and
// gauge rings — across ALL slides, since a PDF renders them all at once. Visiting
// a slide afterwards simply re-runs its enter-animation, so no restore is needed.
window.addEventListener('beforeprint', () => {
  document.querySelectorAll('.js-type').forEach(el => { if (el._t) clearInterval(el._t); if (el._full != null) el.textContent = el._full; });
  document.querySelectorAll('.count[data-count]').forEach(el => {
    const to = parseFloat(el.dataset.count);
    if (!isNaN(to)) el.textContent = (el.dataset.prefix || '') + to.toFixed(parseInt(el.dataset.decimals || '0', 10)) + (el.dataset.suffix || '');
  });
  document.querySelectorAll('.ring[data-pct]').forEach(ringToFinal);
});

/* =========================================================================
   PRESENTER (SPEAKER) VIEW  +  cross-window sync
   ========================================================================= */
// Per-deck channel/key: on file:// every deck shares one origin, so an unsalted
// name would let two open decks drive each other's navigation/interactions.
const CH = 'db_deck_sync:' + location.pathname;
let bc = null; try { bc = new BroadcastChannel(CH); } catch(_) {}
let presenterWin = null;

// Send a message over every channel we have: BroadcastChannel (same-origin
// tabs) plus postMessage to the popup and/or its opener.
function post(msg){
  try { bc && bc.postMessage(msg); } catch(_){}
  try { if (presenterWin && !presenterWin.closed) presenterWin.postMessage(msg, '*'); } catch(_){}
  try { if (window.opener && !window.opener.closed) window.opener.postMessage(msg, '*'); } catch(_){}
}
// Slide navigation. localStorage is the extra fallback for a plain second tab
// (carries only the slide index — interactions and pointer ride the channels above).
function broadcast(){
  post({ type: 'state', i: current });
  try { localStorage.setItem(CH, JSON.stringify({ i: current, t: Date.now() })); } catch(_){}
}
// Everything a newly-opened window needs to catch up: slide, interactions, pointer.
function sendFullState(){
  post({ type: 'state', i: current });
  Object.keys(interact).forEach(k => {
    const [si, kind, idx] = k.split(':');
    post({ type: 'interact', si: +si, kind, idx: +idx, val: interact[k] });
  });
  post({ type: 'laser', on: laserOn });
  post({ type: 'lasercolor', color: laserColor });
}
function handleMsg(d){
  if (!d) return;
  switch (d.type){
    case 'state':      applyRemote(d.i); break;
    case 'interact':   applyInteract(d.si, d.kind, d.idx, d.val); break;
    case 'laser':      setLaser(d.on, true); break;
    case 'laserpos':   showLaserAt(d.nx, d.ny); break;
    case 'lasercolor': setLaserColor(d.color, true); break;
    case 'req':        sendFullState(); break;
  }
}
bc && (bc.onmessage = e => handleMsg(e.data));
window.addEventListener('message', e => handleMsg(e.data));
window.addEventListener('storage', e => {
  if (e.key === CH && e.newValue){ try { applyRemote(JSON.parse(e.newValue).i); } catch(_){} }
});

function openSpeaker(){
  const url = location.href.split('#')[0] + '#presenter';
  presenterWin = window.open(url, 'db_presenter', 'width=1180,height=760');
  if (!presenterWin){ alert('Popup blocked. Allow popups for this page, then click “Speaker view” again.'); return; }
  setTimeout(sendFullState, 700);
}

let pvObserver = null;
function buildPresenter(){
  document.body.classList.add('presenter-mode');
  const pv = document.createElement('div');
  pv.className = 'presenter';
  pv.innerHTML =
    '<div class="pv-topbar">' +
      '<div class="pv-timer" id="pvTimer">00:00</div>' +
      '<button class="tbtn" id="pvStart">Pause</button>' +
      '<button class="tbtn" onclick="pvReset()">Reset timer</button>' +
      '<button class="tbtn" id="pvLaserBtn" onclick="toggleLaser()"><svg class="tbtn-ico" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3"/></svg>Pointer</button>' +
      '<input type="color" id="pvLaserColor" class="laser-swatch" value="' + laserColor + '" title="Pointer color" oninput="setLaserColor(this.value)">' +
      '<div style="flex:1"></div>' +
      '<button class="tbtn" onclick="prev()">‹ Prev</button>' +
      '<span class="counter"><span id="pvCur">1</span> / <span id="pvTot"></span></span>' +
      '<button class="tbtn" onclick="next()">Next ›</button>' +
    '</div>' +
    '<div class="pv-current-wrap"><div class="pv-stage" id="pvCurStage"></div></div>' +
    '<div class="pv-side">' +
      '<div class="pv-next"><div class="pv-lbl">Next slide</div><div class="pv-stage" id="pvNextStage"></div></div>' +
      '<div class="pv-notes-wrap"><div class="pv-lbl">Speaker notes</div><div class="pv-notes" id="pvNotes"></div></div>' +
    '</div>';
  document.body.appendChild(pv);
  document.getElementById('pvTot').textContent = wraps.length;

  // Re-scale the cloned slides whenever their stages get/adjust size.
  // (Fixes the "next slide invisible" case where the stage had 0 size on first paint.)
  pvObserver = new ResizeObserver(refitClones);
  pvObserver.observe(document.getElementById('pvCurStage'));
  pvObserver.observe(document.getElementById('pvNextStage'));

  startTimer();
  post({ type: 'req' });   // ask the main deck for current slide + interactions + pointer state
  requestAnimationFrame(renderPresenter);
  // Extra refits for late layout (popup still sizing, fonts settling) — cheap insurance
  // on top of the CSS-centered fitClone so the panes never need a manual resize.
  window.addEventListener('load', refitClones);
  setTimeout(refitClones, 250);
}
function renderPresenter(){
  resetReveals(current);                    // flips/sliders start fresh on entry (matches the audience window)
  cloneInto('pvCurStage', current, true);
  cloneInto('pvNextStage', current + 1 < wraps.length ? current + 1 : -1, false);
  const notes = document.getElementById('pvNotes');
  if (notes){
    notes.innerHTML = noteFor(current) || '<span class="pv-empty">No notes for this slide.</span>';
    notes.scrollTop = 0;   // long notes always start at the top; scroll to read the rest
  }
  const c = document.getElementById('pvCur'); if (c) c.textContent = current + 1;
  repositionLaser();       // the current-slide pane just changed size/content
}
function cloneInto(stageId, idx, isCurrent){
  const stage = document.getElementById(stageId); if (!stage) return;
  // Stop any self-typing left running on the outgoing clone before we drop it,
  // so its interval doesn't keep ticking on a detached node.
  stage.querySelectorAll('.js-type').forEach(el => { if (el._t){ clearInterval(el._t); el._t = null; } });
  stage.innerHTML = '';
  if (idx < 0){ stage.innerHTML = '<div class="pv-endcap">End of deck</div>'; return; }
  const clone = wraps[idx].querySelector('.slide').cloneNode(true);
  stage.appendChild(clone);
  applyStoredInteractions(clone, idx, isCurrent);    // reflect reveals; only the current pane drives demos/video
  if (isCurrent){
    wireInteractions(clone, idx);         // let the presenter drive interactions
    playEnter(clone);                     // replay the enter-animation in step with the main window
  } else {
    settleClone(clone);                   // next-slide preview: jump straight to the finished frame
  }
  fitClone(stage);
}
// A cloned slide is a static snapshot, so its enter-animations would sit at
// frame 0 (an empty chart). Push each to its final state instead — the "next
// slide" preview shows the finished result. The #pvNextStage CSS makes it instant.
function settleClone(clone){
  clone.querySelectorAll('.chart:not(.static), .js-enter').forEach(el => el.classList.add('play'));
  clone.querySelectorAll('.ring[data-pct]').forEach(ringToFinal);
  // Count-ups: show the final value, not a mid-count frame.
  clone.querySelectorAll('.count[data-count]').forEach(el => {
    const to = parseFloat(el.dataset.count);
    if (!isNaN(to)) el.textContent = (el.dataset.prefix || '') + to.toFixed(parseInt(el.dataset.decimals || '0', 10)) + (el.dataset.suffix || '');
  });
  // Self-typing terminal: show the full text (the clone may have been taken
  // mid-type; _full is a JS prop that doesn't survive cloneNode, but data-full does).
  clone.querySelectorAll('.js-type').forEach(el => { if (el.dataset.full != null) el.textContent = el.dataset.full; });
}
function fitClone(stage, tries){
  if (!stage) return;
  const clone = stage.querySelector('.slide'); if (!clone) return;
  const w = stage.clientWidth, h = stage.clientHeight;
  if (!w || !h){                              // stage not laid out yet (popup first paint):
    if ((tries || 0) < 60) requestAnimationFrame(() => fitClone(stage, (tries || 0) + 1));
    return;                                   // retry next frame instead of bailing permanently
  }
  // Center the clone with CSS (translate) and let JS supply only the SCALE.
  // Positioning via left/top:50% means a transiently-wrong width at first paint
  // can't push the clone off-stage (where overflow:hidden would hide it). The old
  // computed-left approach broke the "next slide" pane specifically: its height is
  // fixed (CSS 210px) so it never tripped the zero-guard/retry above, and a wrong
  // first-paint width left it positioned out of view until a manual resize fired
  // the ResizeObserver.
  const s = Math.min(w / 1280, h / 720);
  clone.style.position = 'absolute';
  clone.style.left = '50%';
  clone.style.top  = '50%';
  clone.style.transformOrigin = 'center center';
  clone.style.transform = 'translate(-50%, -50%) scale(' + s + ')';
}
function refitClones(){
  fitClone(document.getElementById('pvCurStage'));
  fitClone(document.getElementById('pvNextStage'));
  repositionLaser();
}

/* --- Presenter timer ---------------------------------------------------- */
let tStart = Date.now(), tAcc = 0, tPaused = false, tInt = null;
function startTimer(){ tInt = setInterval(updTimer, 500); const b = document.getElementById('pvStart'); if (b) b.onclick = toggleTimer; updTimer(); }
function updTimer(){
  if (tPaused) return;
  const el = Math.floor((Date.now() - tStart + tAcc) / 1000);
  const t = document.getElementById('pvTimer');
  if (t) t.textContent = String(Math.floor(el / 60)).padStart(2,'0') + ':' + String(el % 60).padStart(2,'0');
}
function toggleTimer(){
  const b = document.getElementById('pvStart');
  if (tPaused){ tPaused = false; tStart = Date.now(); if (b) b.textContent = 'Pause'; }
  else { tPaused = true; tAcc += Date.now() - tStart; if (b) b.textContent = 'Resume'; }
}
function pvReset(){ tAcc = 0; tStart = Date.now(); tPaused = false; const b = document.getElementById('pvStart'); if (b) b.textContent = 'Pause'; updTimer(); }

/* =========================================================================
   LASER POINTER  —  a shared spotlight, driven from either window
   -------------------------------------------------------------------------
   Toggle with the toolbar button or the "L" key. When on, moving the cursor
   over the current slide shows a red dot there — and the same dot appears in
   the other window, mapped onto its copy of the slide. Both windows can move
   it; the main (audience) view always renders it at full size over the live
   slide, so that's the one that leads.
   ========================================================================= */
let laserOn = false;
let laserColor = getComputedStyle(document.documentElement).getPropertyValue('--db-orange').trim();  // shared pointer colour (synced across windows); starts in the deck's accent
let lastLaser = null;                       // {nx, ny} — last position, for re-placing on resize
let laserPending = null, laserRaf = 0;

function toggleLaser(){ setLaser(!laserOn); }
// Change the pointer colour, mirror it to the other window, and keep both
// colour pickers in step. A white/dark ring on the dot (see .laser-dot CSS)
// keeps it visible even when the chosen colour matches the slide behind it.
function setLaserColor(hex, remote){
  laserColor = hex;
  const rs = document.documentElement.style;
  rs.setProperty('--laser-color', hex);
  rs.setProperty('--laser-glow', hexToRgba(hex, 0.5));
  ['laserColor', 'pvLaserColor'].forEach(id => { const i = document.getElementById(id); if (i && i.value.toLowerCase() !== hex.toLowerCase()) i.value = hex; });
  if (!remote) post({ type: 'lasercolor', color: hex });
}
function hexToRgba(hex, a){
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!m) return 'rgba(0,0,0,' + a + ')';
  return 'rgba(' + parseInt(m[1], 16) + ',' + parseInt(m[2], 16) + ',' + parseInt(m[3], 16) + ',' + a + ')';
}
function setLaser(on, remote){
  laserOn = on;
  document.body.classList.toggle('laser-on', on);
  ['laserBtn', 'pvLaserBtn'].forEach(id => { const b = document.getElementById(id); if (b) b.classList.toggle('on', on); });
  if (!on){ const d = document.getElementById('laserDot'); if (d) d.style.display = 'none'; }
  if (!remote) post({ type: 'laser', on });
}
// The on-screen rect of the slide the pointer rides: the live slide in the
// deck, or the current-slide clone in the speaker view.
function laserSlideRect(){
  const el = document.querySelector(IS_PRESENTER ? '#pvCurStage .slide' : '.slide-wrap.active .slide');
  return el ? el.getBoundingClientRect() : null;
}
function laserDotEl(){
  let d = document.getElementById('laserDot');
  if (!d){ d = document.createElement('div'); d.id = 'laserDot'; d.className = 'laser-dot'; document.body.appendChild(d); }
  return d;
}
// Place the dot at normalised (0–1) slide coordinates — shared by local moves
// and remote updates, so both windows land on the same spot on the slide.
function showLaserAt(nx, ny){
  if (!laserOn) return;
  lastLaser = { nx, ny };
  const r = laserSlideRect(), d = laserDotEl();
  if (!r){ d.style.display = 'none'; return; }
  d.style.display = 'block';
  d.style.left = (r.left + nx * r.width)  + 'px';
  d.style.top  = (r.top  + ny * r.height) + 'px';
  // Size the dot as a fixed fraction of the slide, so a smaller on-screen slide
  // (the speaker-view preview) shows a proportionally smaller pointer than the
  // full-size audience slide — both cover the same spot at the same relative
  // size. 1280 is the slide's design width; transform-origin is the dot centre,
  // which sits exactly on the target point (see the -11px margin in CSS).
  d.style.transform = 'scale(' + (r.width / 1280) + ')';
}
function repositionLaser(){ if (laserOn && lastLaser) showLaserAt(lastLaser.nx, lastLaser.ny); }

function onLaserMove(e){
  if (!laserOn) return;
  laserPending = { x: e.clientX, y: e.clientY };
  if (!laserRaf) laserRaf = requestAnimationFrame(flushLaser);
}
function flushLaser(){
  laserRaf = 0; const p = laserPending; if (!p) return;
  const r = laserSlideRect(); if (!r) return;
  const nx = (p.x - r.left) / r.width, ny = (p.y - r.top) / r.height;
  if (nx < 0 || nx > 1 || ny < 0 || ny > 1) return;   // off the slide: leave the dot parked
  showLaserAt(nx, ny);
  post({ type: 'laserpos', nx, ny });
}
if (laserColor) setLaserColor(laserColor, true);   // the pointer starts in the deck's accent
document.addEventListener('mousemove', onLaserMove);
window.addEventListener('scroll', repositionLaser, true);

/* =========================================================================
   KEYBOARD
   ========================================================================= */
document.addEventListener('keydown', e => {
  if (document.body.classList.contains('grid-mode')){
    if (e.key === 'g' || e.key === 'G' || e.key === 'Escape') toggleGrid();
    return;
  }
  switch(e.key){
    case 'ArrowRight': case ' ': case 'PageDown': next(); e.preventDefault(); break;
    case 'ArrowLeft': case 'PageUp': prev(); e.preventDefault(); break;
    case 'Home': goTo(0); e.preventDefault(); break;
    case 'End': goTo(wraps.length - 1); e.preventDefault(); break;
    case 'g': case 'G': if (!IS_PRESENTER) toggleGrid(); break;
    case 'n': case 'N': if (!IS_PRESENTER) toggleNotes(); break;
    case 's': case 'S': if (!IS_PRESENTER) openSpeaker(); break;
    case 'l': case 'L': toggleLaser(); break;
    case 'f': case 'F': fullscreen(); break;
  }
});

/* =========================================================================
   LAYOUT AUDIT — catch content that overflows the slide box or collides with
   the auto-injected footer.
   -------------------------------------------------------------------------
   Opt-in ONLY: it runs when the deck is opened with `index.html?audit=1`, or
   when you call `window.__auditLayout()` from the console. It never runs during
   normal viewing, PDF export, or Google Slides export, so it can't change how a
   slide renders or affect export fidelity.
   Findings shape: [{ index, title, kind, detail, text?, more? }] where kind is one of
   'overlap-footer' | 'overflow-bottom' | 'overflow-side' | 'clipped-text' | 'overlap-text' | 'table-frame' |
   'same-as-ground' (a decorative svg shape painted in its slide's own background colour, so it cannot be seen)
   Visible spacing (the CLEARANCE AUDIT below) is NOT in this list: it has its own, __audit_clearance__.
   (text = the words to look at, more = further issues on that slide). Headless callers read
   the JSON from a hidden <div id="__audit__"> (textContent, so Chrome's
   --dump-dom picks it up); a human sees a red outline + a badge on each flagged
   slide (see body.audit-mode styles in style.css).
   A second, REVIEW-only list goes to <div id="__audit_review__">: kind
   'top-heavy' = the content stops in the top part of the slide and leaves the
   bottom empty (detail = how far down it reaches). Shown as a dashed outline.
   ========================================================================= */
const AUDIT_TOL = 1.5;                    // px slack for sub-pixel rounding
// Dark, intentionally-bleeding layouts (decorative shapes/photos reach the
// edges by design, and content is centred well clear of the footer) — the
// non-text overflow probe is skipped for these; the footer/edge text probe
// still applies.
const AUDIT_BLEED = '.cover,.section,.quote,.closing,.statement,.company,.fullbleed,.split,.video,.demo';

function auditVisible(el){
  const cs = getComputedStyle(el);
  if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0.5 && r.height > 0.5;
}
function auditTextLeaf(el){                // has its own (non-descendant) visible text
  for (const n of el.childNodes) if (n.nodeType === 3 && n.textContent.trim()) return true;
  return false;
}
function auditSlide(slide){
  const issues = [];
  const sr = slide.getBoundingClientRect();
  const foot = slide.querySelector('.foot');
  const footVisible = foot && auditVisible(foot);
  const footTop = footVisible ? foot.getBoundingClientRect().top : sr.bottom;
  // 1) Text must not cross the footer or spill past the slide edges.
  slide.querySelectorAll('*').forEach(el => {
    if (el.closest('.foot,.notes,.slide-checkbox,.slide-idx')) return;
    if (!auditTextLeaf(el) || !auditVisible(el)) return;
    const r = el.getBoundingClientRect();
    if (footVisible && r.bottom > footTop + AUDIT_TOL) issues.push({ kind:'overlap-footer', over:r.bottom - footTop });
    else if (r.bottom > sr.bottom + AUDIT_TOL)          issues.push({ kind:'overflow-bottom', over:r.bottom - sr.bottom });
    if (r.right > sr.right + AUDIT_TOL)      issues.push({ kind:'overflow-side', over:r.right - sr.right });
    else if (r.left < sr.left - AUDIT_TOL)   issues.push({ kind:'overflow-side', over:sr.left - r.left });
  });
  // 1b) A framed card (its own fill, frame or image) whose box runs into the footer while its text stays above it: a
  //     goal card that reached 18 px under the footer passed the text check (2026-10). Not on the bleed layouts; the
  //     slide, the pad and the footer's own ancestors are the frame, not a card.
  if (footVisible && !slide.matches(AUDIT_BLEED)){
    slide.querySelectorAll('*').forEach(el => {
      if (el === slide || el.matches('.pad') || el.contains(foot) || el.closest('.foot,.notes,.slide-checkbox,.slide-idx,.flip-back,svg')) return;
      if (!(el instanceof HTMLElement) || !auditVisible(el)) return;
      const cs = getComputedStyle(el);
      const framed = !/^(transparent|rgba\(0, 0, 0, 0\))$/.test(cs.backgroundColor) || cs.backgroundImage !== 'none'
        || parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.borderBottomWidth) > 0;
      if (!framed) return;
      const r = el.getBoundingClientRect();
      if (r.top >= footTop - AUDIT_TOL) return;                       // a box under the footer is not a card above it
      if (r.bottom > footTop + AUDIT_TOL) issues.push({ kind:'overlap-footer', over:r.bottom - footTop, text:auditLabel(el) });
    });
  }
  // 2) Non-text content (charts, tables, images) overflowing the padding box —
  //    scrollHeight/Width are unscaled layout px, so compare them to each other.
  //    Skipped on the bleed layouts above.
  if (!slide.matches(AUDIT_BLEED)){
    const pad = slide.querySelector('.pad');
    if (pad){
      if (pad.scrollHeight > pad.clientHeight + AUDIT_TOL) issues.push({ kind:'overflow-bottom', over:pad.scrollHeight - pad.clientHeight });
      if (pad.scrollWidth  > pad.clientWidth  + AUDIT_TOL) issues.push({ kind:'overflow-side',   over:pad.scrollWidth  - pad.clientWidth  });
      // boxes pushed past the left/top edge (scroll size only sees right/bottom spill)
      pad.querySelectorAll('*').forEach(el => {
        if (el.closest('.notes') || !auditVisible(el) || !auditPainted(el)) return;
        const r = el.getBoundingClientRect(), over = Math.max(sr.left - r.left, sr.top - r.top);
        if (over > AUDIT_TOL) issues.push({ kind:'overflow-side', over, text:auditLabel(el) });
      });
    }
  }
  // 3) Text clipped by an overflow:hidden/auto ancestor (a label wider than its bar,
  //    a table row cut by a fixed-height box), and 4) text drawn over other text
  //    (a badge on a label, stacked nodes). Neither shows up as slide overflow.
  const leaves = [];
  slide.querySelectorAll('*').forEach(el => {
    if (el.closest('.foot,.notes,.slide-checkbox,.slide-idx,.flip-back')) return;
    if (auditTextLeaf(el) && auditVisible(el)) auditLineBoxes(el).forEach(r => leaves.push([el, r]));
  });
  const clipped = new Set();
  leaves.forEach(([el, r]) => {
    if (clipped.has(el)) return;
    for (let a = el; a && a !== slide; a = a.parentElement){      // its own box clips too
      const cs = getComputedStyle(a);
      if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue;
      const ar = a.getBoundingClientRect();
      const sc = clrScrollAxes(a);                                  // a scrolling axis clips by design: only the other axis counts
      const over = Math.max(sc.x ? -Infinity : Math.max(ar.left - r.left, r.right - ar.right), sc.y ? -Infinity : Math.max(ar.top - r.top, r.bottom - ar.bottom));
      if (over > AUDIT_TOL + 1){ clipped.add(el); issues.push({ kind:'clipped-text', over, text:auditLabel(el) }); break; }
    }
  });
  for (let i = 0; i < leaves.length; i++){
    const [ea, ra] = leaves[i];
    for (let j = i + 1; j < leaves.length; j++){
      const [eb, rb] = leaves[j];
      if (ea === eb || ea.contains(eb) || eb.contains(ea)) continue;
      // a compare slide stacks its before/after panes on purpose
      const pa = ea.closest('.compare .before, .compare .after'), pb = eb.closest('.compare .before, .compare .after');
      if (pa && pb && pa !== pb) continue;
      const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
      if (w <= 3 || h <= 3) continue;
      const small = Math.min(ra.width * ra.height, rb.width * rb.height);
      if (w * h > 0.25 * small) issues.push({ kind:'overlap-text', over:Math.min(w, h),
        text:auditLabel(ea) + ' / ' + auditLabel(eb) });
    }
  }
  // 5) A table framed or sized by a rule meant for another component (a class name the two
  //    share: table.db.matrix took the quadrant's .matrix axes and square box, 2026-10).
  //    Tables draw only cell rules, never an outer frame, and size to their rows.
  slide.querySelectorAll('table.db').forEach(t => {
    if (!auditVisible(t)) return;
    const cs = getComputedStyle(t);
    const frame = ['Top', 'Right', 'Bottom', 'Left'].map(s => parseFloat(cs['border' + s + 'Width']) || 0);
    if (Math.max(...frame) > 0 || (cs.aspectRatio && cs.aspectRatio !== 'auto'))
      issues.push({ kind:'table-frame', over:Math.max(...frame), text:auditLabel(t.querySelector('th,td') || t) });
  });
  // 6) A decorative shape (an svg the slide marks aria-hidden: section and cover art, or an icon) painted in
  //    the colour of the solid background it sits on: it is invisible. The coral section motifs were --db-coral
  //    on a --db-coral ground (2026-10). Compared on computed colours, so a token that resolves to its ground in
  //    any pack is caught too. Opt out with data-audit-skip="same-as-ground" and say why.
  slide.querySelectorAll('svg[aria-hidden="true"] :is(circle,ellipse,rect,polygon,polyline,path)').forEach(el => {
    if (el.closest('[data-audit-skip~="same-as-ground"],[data-audit-skip~="all"]') || !auditVisible(el)) return;
    const cs = getComputedStyle(el), fill = auditRGB(cs.fill);
    if (!fill || fill[3] === 0 || parseFloat(cs.fillOpacity) === 0) return;
    const ground = auditGround(el, slide);
    if (!ground) return;
    if (fill[0] === ground.rgb[0] && fill[1] === ground.rgb[1] && fill[2] === ground.rgb[2])
      issues.push({ kind:'same-as-ground', over:0, detail:'fill ' + cs.fill + ' on ' + ground.css,
        text:el.tagName.toLowerCase() + (el.getAttribute('class') ? '.' + el.getAttribute('class') : '') });
  });
  return issues;
}
// The solid colour a shape is painted on: the nearest ancestor (up to the slide) with an opaque background colour.
// A button's own fill counts, not the slide's (an icon in an orange button is not on the white slide). null when the
// ground is a gradient or photo, which has no single colour to compare.
function auditGround(el, slide){
  for (let a = el.parentElement; a; a = a.parentElement){
    const cs = getComputedStyle(a);
    if (cs.backgroundImage !== 'none') return null;
    const c = auditRGB(cs.backgroundColor);
    if (c && c[3] >= 1) return { rgb:c, css:cs.backgroundColor };
    if (a === slide) break;
  }
  return null;
}
// Computed colour ("rgb(r, g, b)" or "rgba(r, g, b, a)") -> [r, g, b, a], or null (none, or not a colour).
function auditRGB(c){
  const m = /^rgba?\(\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\s*\)$/.exec(c || '');
  return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
}
// The boxes of an element's own text lines (not its block box, which can span a
// whole card under a corner badge without any glyph touching it).
function auditLineBoxes(el){
  const out = [], range = document.createRange();
  el.childNodes.forEach(n => {
    if (n.nodeType !== 3 || !n.textContent.trim()) return;
    range.selectNodeContents(n);
    for (const r of range.getClientRects()) if (r.width > 0.5 && r.height > 0.5) out.push(r);
  });
  return out;
}
function auditPainted(el){                   // draws a box/graphic of its own
  const cs = getComputedStyle(el);
  return /^(IMG|SVG|CANVAS|VIDEO|IFRAME)$/i.test(el.tagName) || cs.backgroundImage !== 'none'
    || !/^(transparent|rgba\(0, 0, 0, 0\))$/.test(cs.backgroundColor)
    || parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.borderLeftWidth) > 0;
}
function auditLabel(el){ return (el.textContent || el.getAttribute('alt') || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 40); }
/* =========================================================================
   CLEARANCE AUDIT — visible spacing. Shared rule, identical in deck.js, doc.js and site.js
   (tests/test_clearance_parity.py checks the three copies match). Opt-in with ?audit=1. It is kept apart from the
   layout audit: findings go to <div id="__audit_clearance__"> and never to __audit__, so a caller of the layout
   audit sees nothing new. It reports content that is technically apart but reads as touching: a visible box
   closer than CLR_MIN.box to its neighbour, to the inner edge of its frame or container, or to the diagram, slide
   or footer edge; and a label closer than CLR_MIN.text to the edge of its own box. Measured on the rendered page in
   CSS px at the page's own size (a slide's scale is divided out, so the numbers are its 1280-wide design px):
   boxes by getBoundingClientRect, SVG labels by their glyph ink (canvas measureText), HTML labels by their line
   boxes. A gap fails only below the minimum less CLR_SLACK, a half-pixel allowance for rounding. The minimums of an
   SVG diagram scale with the diagram: they are in its own units (a 10-unit gap is 10 units at any width), so a diagram
   shrunk to fit its box is not flagged for the shrink.
   Not measured: a rule, bar or swatch under CLR_THIN; table cells; list items; chips, badges, buttons and inline
   text; step badges (circles); connectors (lines); a chart's own value and axis labels (CLR_CHART, which the chart
   places); and pieces meant to sit flush on their neighbour or container (CLR_FLUSH: notebook cells and gutters,
   tab strips, segmented or stacked bars, gantt bars in their track, data-flush="..."). A flush piece is still a box
   for the labels inside it. Anything else opts out with data-audit-skip="clearance" (or "all") on it or an ancestor.
   A scrolling container (overflow-x auto or scroll) is not measured on its inline (x) axis, whether or not it overflows
   right now: running to the edge of a scroller is how it shows more, and the result must not depend on the width.
   Its block (y) axis is measured only while content is past it. Text that runs past the edge of a box that does not
   scroll is an overflow (not a gap): it is kind 'overflow', with the amount it runs past.
   Returns [{ kind, over, text, detail, path }] with kind 'box-gap' | 'frame-gap' | 'label-gap' | 'edge-gap' | 'overflow'; path is
   a :scope selector for the element, relative to the root, so a reviewer or a fix can find it.
   ========================================================================= */
const CLR_MIN = { box: 8, text: 8, edge: 8 };        // rendered CSS px (see the skill README, Spacing)
const CLR_SLACK = 0.5;                               // rounding allowance: a gap fails only below CLR_MIN - CLR_SLACK
const CLR_THIN = 6;                                  // a rule, bar or swatch thinner than this is not a box
const CLR_SKIP = '.notes,.foot,.page-foot,.slide-checkbox,.slide-idx,.flip-back,.rail,.toc,.toc-list,.kbd,.badge,' +
  '.chip,.pill,.tag,.legend,[class*=legend],button,input,select,textarea,[role=button],[role=tab],.code-copy,' +
  'table,thead,tbody,tfoot,tr,td,th';
const CLR_FLUSH = '.nb-bar,.nb-cell,.nb-gut,.vtab-bar,.tl-tab,.demo-tabs,[role=tablist],.seg,.stack > *,.segmented > *,' +
  '.g-bar,.track > *,[data-flush]';
const CLR_CHART = '.val,.pval,.xlabel,.axis,.tick,.ylabel';
const CLR_BLEED = '.cover,.section,.quote,.closing,.statement,.company,.fullbleed,.split,.video,.demo';
function clrRect(r){ return { x1: r.left, y1: r.top, x2: r.right, y2: r.bottom }; }
function clrW(b){ return b.x2 - b.x1; }
function clrH(b){ return b.y2 - b.y1; }
function clrPainted(c){ return !!c && c !== 'transparent' && !/^rgba\(\s*0,\s*0,\s*0,\s*0\s*\)$/.test(c); }
function clrSkipped(el, root){
  for (let n = el; n && n !== root; n = n.parentElement)
    if (n.getAttribute && /(^|\s)(clearance|all)(\s|$)/.test(n.getAttribute('data-audit-skip') || '')) return true;
  return !!el.closest(CLR_SKIP);
}
function clrLabel(el){ return (el.getAttribute && el.getAttribute('aria-label')) || (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40) || el.tagName.toLowerCase(); }
// A :scope selector that finds el again from its root (for the findings' path).
function clrPath(el, root){
  const parts = [];
  for (let n = el; n && n !== root && n.parentElement; n = n.parentElement)
    parts.unshift(n.tagName.toLowerCase() + ':nth-child(' + (Array.prototype.indexOf.call(n.parentElement.children, n) + 1) + ')');
  return parts.length ? ':scope > ' + parts.join(' > ') : ':scope';
}
// An HTML box: rendered, not inline text, with an edge of its own (a frame of two sides, a fill, a shadow or an image).
// A circle is a step badge, not a box.
function clrHtmlBox(el, S){
  const cs = getComputedStyle(el);
  if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'absolute' || cs.position === 'fixed') return null;
  const r = clrRect(el.getBoundingClientRect());
  if (clrW(r) <= 0.5 || clrH(r) <= 0.5) return null;
  const replaced = /^(IMG|SVG|CANVAS|VIDEO|IFRAME)$/.test(el.tagName);
  if (!replaced && cs.display === 'inline') return null;
  const small = Math.min(clrW(r), clrH(r));
  if (small < CLR_THIN * S) return null;
  const rad = cs.borderTopLeftRadius || '', radPx = rad.endsWith('%') ? parseFloat(rad) / 100 * small : parseFloat(rad) || 0;
  if (!replaced && Math.abs(clrW(r) - clrH(r)) < 1 && radPx >= 0.45 * small) return null;
  const bw = ['Top', 'Right', 'Bottom', 'Left'].map(s => parseFloat(cs['border' + s + 'Width']) || 0);
  const edged = bw.filter(v => v > 0).length >= 2 || clrPainted(cs.backgroundColor) || cs.backgroundImage !== 'none' || cs.boxShadow !== 'none';
  if (!edged && !replaced) return null;
  return { el, r, bw, clip: /(hidden|auto|scroll|clip)/.test(cs.overflowX + ' ' + cs.overflowY), flush: el.matches(CLR_FLUSH) };
}
function clrInner(b){ return { x1: b.r.x1 + b.bw[3], y1: b.r.y1 + b.bw[0], x2: b.r.x2 - b.bw[1], y2: b.r.y2 - b.bw[2] }; }
// The least side gap of inner box a to outer box o: { side, gap } (a negative gap means a crosses o's edge).
function clrWorst(a, o, scroll){
  const g = { left: a.x1 - o.x1, right: o.x2 - a.x2, top: a.y1 - o.y1, bottom: o.y2 - a.y2 };
  if (scroll && scroll.x){ delete g.left; delete g.right; }     // a scrolled axis is not measured
  if (scroll && scroll.y){ delete g.top; delete g.bottom; }
  let side = null, gap = Infinity;
  for (const k in g) if (g[k] < gap){ gap = g[k]; side = k; }
  return { side, gap };
}
// Gap between two boxes that sit side by side or stacked (their projections overlap); null if they overlap or are diagonal.
function clrGap(a, b, minOverlap){
  const gx = Math.max(a.x1 - b.x2, b.x1 - a.x2), gy = Math.max(a.y1 - b.y2, b.y1 - a.y2);
  if (gx >= 0 && gy < 0 && Math.min(a.y2, b.y2) - Math.max(a.y1, b.y1) >= minOverlap) return gx;
  if (gy >= 0 && gx < 0 && Math.min(a.x2, b.x2) - Math.max(a.x1, b.x1) >= minOverlap) return gy;
  return null;
}
function clrInside(outer, i, tol){ tol = tol || 0.5; return i.x1 >= outer.x1 - tol && i.y1 >= outer.y1 - tol && i.x2 <= outer.x2 + tol && i.y2 <= outer.y2 + tol; }
function clrSame(a, b){ return Math.abs(a.x1 - b.x1) < 1 && Math.abs(a.y1 - b.y1) < 1 && Math.abs(a.x2 - b.x2) < 1 && Math.abs(a.y2 - b.y2) < 1; }
// The visible text lines of an HTML element (its own text nodes, not its box).
function clrLines(el){
  const out = [], range = document.createRange();
  el.childNodes.forEach(n => {
    if (n.nodeType !== 3 || !n.textContent.trim()) return;
    range.selectNodeContents(n);
    for (const r of range.getClientRects()) if (r.width > 0.5 && r.height > 0.5) out.push(clrRect(r));
  });
  return out;
}
// The axes a box is not measured on: the inline axis (x) of any box with overflow-x auto or scroll (a scroller runs to
// its edge by design, overflowing or not), and the block axis (y) only while content is past it.
function clrScrollAxes(el){
  const cs = getComputedStyle(el);
  return { x: /auto|scroll/.test(cs.overflowX),
           y: /auto|scroll/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 1 };
}
// The settle wait (?audit=1): the findings are read once the page is final. Waits for the fonts, for every
// animation or transition to finish (an endless one, a cursor blink, is ignored), and for two checks 20 ms apart
// with the same page size. Gives up after CLR_SETTLE_MS and measures anyway.
const CLR_SETTLE_MS = 4000;
function clrSettle(done){
  const t0 = performance.now();
  let last = '', still = 0;
  const moving = () => document.getAnimations().some(a => {
    if (a.playState !== 'running' && a.playState !== 'pending') return false;
    const t = a.effect && a.effect.getComputedTiming();
    return !(t && t.endTime === Infinity);
  });
  const shape = () => { const h = document.documentElement; return [h.scrollWidth, h.scrollHeight, h.clientWidth, h.clientHeight].join(','); };
  const tick = () => {
    const fontsDone = !document.fonts || document.fonts.status === 'loaded';
    const sig = shape();
    still = fontsDone && !moving() && sig === last ? still + 1 : 0;
    last = sig;
    if (still >= 2 || performance.now() - t0 > CLR_SETTLE_MS) return done();
    setTimeout(tick, 20);
  };
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(tick); else tick();
}
// Two settled measurements (measure() returns the findings, write() reports them). A finding is reported only when
// both measurements see it, so a flicker between the two never reaches the list.
function clrKey(f){ return JSON.stringify([f.kind, f.index, f.page, f.title, f.path, f.text]); }
function clrRunSettled(measure, write){
  clrSettle(() => {
    const first = measure();
    clrSettle(() => { const again = new Set(measure().map(clrKey)); write(first.filter(f => again.has(clrKey(f)))); });
  });
}
let clrCanvas = null;
// One root (a slide, a page, a site page). S = rendered px per design px of the root.
function clrAudit(root, S){
  const out = [], rootR = clrRect(root.getBoundingClientRect());
  const need = m => m - CLR_SLACK;                   // the fail line for a minimum m
  // a finding inside an svg carries that svg's icon attributes (migrate_viewboxes.py names a known template icon)
  const add = (kind, el, text, detail, over) => {
    const sv = el.closest && el.closest('svg');
    const icon = sv ? { viewBox: sv.getAttribute('viewBox') || '', label: sv.getAttribute('aria-label') || '', cls: sv.getAttribute('class') || '' } : null;
    out.push(Object.assign({ kind, over: over || 0, text: (text || '').slice(0, 40), detail, path: clrPath(el, root) }, icon ? { icon } : {}));
  };
  const foot = root.querySelector('.foot,.page-foot');
  const footR = foot && getComputedStyle(foot).display !== 'none' ? clrRect(foot.getBoundingClientRect()) : null;
  const footTop = footR && clrW(footR) > 0.5 ? footR.y1 : null;
  const bleed = root.matches(CLR_BLEED);

  // HTML boxes (a diagram's svg counts as one box; its parts are checked below)
  const boxes = [];
  root.querySelectorAll('*').forEach(el => {
    if (el === root || (el.closest('svg') && el.tagName.toLowerCase() !== 'svg')) return;
    if (clrSkipped(el, root) || el.matches('.slide,.page,.slide-wrap')) return;
    const b = clrHtmlBox(el, S);
    if (b) boxes.push(b);
  });
  // box to box: two boxes side by side or stacked, neither inside the other; two flush pieces are meant to touch
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++){
    const a = boxes[i], b = boxes[j];
    if (a.el.contains(b.el) || b.el.contains(a.el) || (a.flush && b.flush)) continue;
    const g = clrGap(a.r, b.r, CLR_THIN * S);
    if (g !== null && g < need(CLR_MIN.box) * S) add('box-gap', a.el, clrLabel(a.el), `${(g / S).toFixed(1)}px to ${clrLabel(b.el)} (needs ${CLR_MIN.box}px)`, CLR_MIN.box - g / S);
  }
  // box to the inner edge of each visible container that holds it (a card's padding, a figure's frame)
  for (const b of boxes){
    if (b.flush) continue;                               // meant to sit on its container's edge
    for (let p = b.el.parentElement; p && p !== root && root.contains(p); p = p.parentElement){
      const c = clrHtmlBox(p, S);
      if (!c) continue;
      const w = clrWorst(b.r, clrInner(c), clrScrollAxes(p));
      if (w.gap >= need(CLR_MIN.box) * S) continue;
      if (c.clip && Math.abs(w.gap) < 0.5) continue;               // a bleed clipped to its container's corners
      add('frame-gap', b.el, clrLabel(b.el), `${(w.gap / S).toFixed(1)}px to the ${w.side} edge of ${clrLabel(p)} (needs ${CLR_MIN.box}px)`, CLR_MIN.box - w.gap / S);
      break;
    }
  }
  // label to the edge of its own box (the nearest visible box that holds its text)
  root.querySelectorAll('*').forEach(el => {
    if (el === root || clrSkipped(el, root) || el.closest('svg') || el.matches(CLR_CHART)) return;
    if (!Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim())) return;
    let c = null;
    for (let p = el; p && p !== root; p = p.parentElement){ c = clrHtmlBox(p, S); if (c) break; }
    if (!c || c.el === root || clrSkipped(c.el, root)) return;
    const inn = clrInner(c), sc = clrScrollAxes(c.el), ell = getComputedStyle(c.el).textOverflow === 'ellipsis';
    for (const l of clrLines(el)){
      const w = clrWorst(l, inn, sc);
      const placed = /absolute|fixed/.test(getComputedStyle(el).position);   // an axis title set outside its frame is an annotation
      if (w.gap < -CLR_SLACK && !ell && !placed){ add('overflow', el, clrLabel(el), `text ${(-w.gap / S).toFixed(1)}px past the ${w.side} edge of its box, which does not scroll`, CLR_MIN.text - w.gap / S); break; }
      if (w.gap >= 0 && w.gap < need(CLR_MIN.text) * S){ add('label-gap', el, clrLabel(el), `text ${(w.gap / S).toFixed(1)}px from the ${w.side} edge of its box (needs ${CLR_MIN.text}px)`, CLR_MIN.text - w.gap / S); break; }
    }
  });
  // box to the slide edge and to the footer (slides and paginated pages)
  if (!bleed){
    for (const b of boxes){
      if (b.flush) continue;
      if (root.matches('.slide')){
        const w = clrWorst(b.r, rootR);
        if (w.gap < need(CLR_MIN.edge) * S) add('edge-gap', b.el, clrLabel(b.el), `${(w.gap / S).toFixed(1)}px to the slide ${w.side} edge (needs ${CLR_MIN.edge}px)`, CLR_MIN.edge - w.gap / S);
      }
      if (footTop !== null && b.r.y1 < footTop){
        const g = (footTop - b.r.y2) / S;
        if (g < need(CLR_MIN.edge)) add('edge-gap', b.el, clrLabel(b.el), `${g.toFixed(1)}px above the footer (needs ${CLR_MIN.edge}px)`, CLR_MIN.edge - g);
      }
    }
  }

  // ---- SVG diagrams: boxes, frames, labels, the diagram's own edge
  root.querySelectorAll('svg').forEach(svg => {
    if (svg.closest('defs,symbol,marker,clipPath,pattern') || clrSkipped(svg, root)) return;
    if (clrW(clrRect(svg.getBoundingClientRect())) <= 0) return;
    let vp = clrRect(svg.getBoundingClientRect());
    const vb = svg.viewBox && svg.viewBox.baseVal, m = svg.getScreenCTM();
    // The minimums scale with the diagram: kS is the rendered px per user unit (the diagram's own scale), so a 10-unit
    // gap is 10 units whether the diagram is drawn at 780 px or shrunk to 390 px (#14). At its natural size kS is S.
    const kS = m && Math.hypot(m.a, m.b) > 0 ? Math.hypot(m.a, m.b) : S;
    if (vb && vb.width > 0 && m){
      const p1 = new DOMPoint(vb.x, vb.y).matrixTransform(m), p2 = new DOMPoint(vb.x + vb.width, vb.y + vb.height).matrixTransform(m);
      vp = { x1: Math.min(p1.x, p2.x), y1: Math.min(p1.y, p2.y), x2: Math.max(p1.x, p2.x), y2: Math.max(p1.y, p2.y) };
    }
    const NON = 'defs,marker,clipPath,mask,pattern,symbol,filter';
    const boxesS = [], texts = [];
    svg.querySelectorAll('rect,image').forEach(el => {
      if (el.closest(NON) || el.closest('[data-audit-skip~="clearance"],[data-audit-skip~="all"]')) return;
      const cs = getComputedStyle(el), img = el.tagName.toLowerCase() === 'image';
      const painted = img || (cs.fill !== 'none' && parseFloat(cs.fillOpacity) > 0) || (cs.stroke !== 'none' && parseFloat(cs.strokeWidth) > 0);
      if (!painted) return;
      const r = clrRect(el.getBoundingClientRect());
      if (clrW(r) <= 0 || clrH(r) <= 0) return;
      if (r.x1 <= vp.x1 + 1 && r.y1 <= vp.y1 + 1 && r.x2 >= vp.x2 - 1 && r.y2 >= vp.y2 - 1) return;   // a canvas
      if (r.x1 < vp.x1 - 1 || r.y1 < vp.y1 - 1 || r.x2 > vp.x2 + 1 || r.y2 > vp.y2 + 1) return;       // bleeds past the viewBox: cropped by design
      if (Math.min(clrW(r), clrH(r)) < CLR_THIN * kS) return;
      boxesS.push({ el, r, img, flush: el.matches(CLR_FLUSH), sw: cs.stroke !== 'none' ? (parseFloat(cs.strokeWidth) || 0) / 2 : 0 });
    });
    if (!clrCanvas) clrCanvas = document.createElement('canvas').getContext('2d');
    const circles = [...svg.querySelectorAll('circle,ellipse')].map(c => clrRect(c.getBoundingClientRect()));
    svg.querySelectorAll('text').forEach(t => {
      if (t.closest(NON) || !t.textContent.trim()) return;
      const r0 = clrRect(t.getBoundingClientRect());
      if (clrW(r0) <= 0) return;
      const c = { x: (r0.x1 + r0.x2) / 2, y: (r0.y1 + r0.y2) / 2 };
      if (circles.some(k => c.x >= k.x1 && c.x <= k.x2 && c.y >= k.y1 && c.y <= k.y2)) return;   // a step badge number
      let r = r0;
      try {                                             // the glyph ink: cap top to descender on the first baseline
        const cs = getComputedStyle(t), fs = parseFloat(cs.fontSize) || 12;
        if (!t.querySelector('tspan[y],tspan[dy]') && t.querySelectorAll('tspan').length < 2){
          const base = new DOMPoint(t.getStartPositionOfChar(0).x, t.getStartPositionOfChar(0).y).matrixTransform(t.getScreenCTM());
          const k = Math.hypot(t.getScreenCTM().a, t.getScreenCTM().b) || 1;   // user units to screen px (an SVG shrunk to fit)
          clrCanvas.font = `${cs.fontStyle} ${cs.fontWeight} ${fs * k}px ${cs.fontFamily}`;
          const mt = clrCanvas.measureText(t.textContent.trim());
          r = { x1: r0.x1, x2: r0.x2, y1: base.y - mt.actualBoundingBoxAscent, y2: base.y + mt.actualBoundingBoxDescent };
        }
      } catch (e) {}
      texts.push({ el: t, r, c, chart: t.matches(CLR_CHART) });
    });
    const owner = c => { let o = null; for (const b of boxesS) if (!b.img && c.x >= b.r.x1 && c.x <= b.r.x2 && c.y >= b.r.y1 && c.y <= b.r.y2 && (!o || clrW(b.r) * clrH(b.r) < clrW(o.r) * clrH(o.r))) o = b; return o; };
    const label = b => { const t = texts.find(t => t.c.x >= b.r.x1 && t.c.x <= b.r.x2 && t.c.y >= b.r.y1 && t.c.y <= b.r.y2); return t ? t.el.textContent.trim() : (b.img ? 'image' : 'box'); };
    // box to the frame that holds it (a flush piece is meant to sit on its frame's edge)
    for (let i = 0; i < boxesS.length; i++) for (let j = 0; j < boxesS.length; j++){
      if (i === j) continue;
      const a = boxesS[i], b = boxesS[j];
      if (a.flush || clrSame(a.r, b.r) || !clrInside(b.r, a.r)) continue;
      const inn = { x1: b.r.x1 + b.sw, y1: b.r.y1 + b.sw, x2: b.r.x2 - b.sw, y2: b.r.y2 - b.sw };
      const w = clrWorst(a.r, inn);
      if (w.gap < need(CLR_MIN.box) * kS) add('frame-gap', a.el, label(a), `${(w.gap / kS).toFixed(1)} units to the ${w.side} edge of its frame (needs ${CLR_MIN.box} units)`, CLR_MIN.box - w.gap / kS);
    }
    // box to box, side by side or stacked
    for (let i = 0; i < boxesS.length; i++) for (let j = i + 1; j < boxesS.length; j++){
      const a = boxesS[i], b = boxesS[j];
      if (clrSame(a.r, b.r) || clrInside(a.r, b.r) || clrInside(b.r, a.r) || (a.flush && b.flush)) continue;
      const g = clrGap(a.r, b.r, CLR_THIN * kS);
      if (g !== null && g < need(CLR_MIN.box) * kS) add('box-gap', a.el, label(a), `${(g / kS).toFixed(1)} units to a sibling box (needs ${CLR_MIN.box} units)`, CLR_MIN.box - g / kS);
    }
    // label to its own box (inside gap), and to a neighbouring box it is not aligned with
    for (const t of texts){
      if (t.chart) continue;                             // a chart's value or axis label sits where the chart puts it
      const o = owner(t.c);
      if (o){
        const w = clrWorst(t.r, { x1: o.r.x1 + o.sw, y1: o.r.y1 + o.sw, x2: o.r.x2 - o.sw, y2: o.r.y2 - o.sw });
        if (w.gap >= 0 && w.gap < need(CLR_MIN.text) * kS) add('label-gap', t.el, t.el.textContent.trim(), `${(w.gap / kS).toFixed(1)} units to the ${w.side} edge of its box (needs ${CLR_MIN.text} units)`, CLR_MIN.text - w.gap / kS);
      }
      if (!o) continue;                                  // a label on open ground is not crowding a box
      for (const b of boxesS){
        if (b === o || b.img || clrInside(b.r, t.r) || clrInside(t.r, b.r)) continue;
        if (t.c.x >= b.r.x1 && t.c.x <= b.r.x2 || t.c.y >= b.r.y1 && t.c.y <= b.r.y2) continue;   // aligned with it: an annotation
        const g = clrGap(t.r, b.r, 0);
        if (g !== null && g >= 0 && g < need(CLR_MIN.text) * kS){ add('label-gap', t.el, t.el.textContent.trim(), `${(g / kS).toFixed(1)} units to a neighbouring box (needs ${CLR_MIN.text} units)`, CLR_MIN.text - g / kS); break; }
      }
    }
    // the diagram's own edge: the viewBox
    for (const b of boxesS){
      if (b.flush) continue;
      const w = clrWorst(b.r, vp);
      if (w.gap < need(CLR_MIN.edge) * kS) add('edge-gap', b.el, label(b), `${(w.gap / kS).toFixed(1)} units to the diagram ${w.side} edge (needs ${CLR_MIN.edge} units)`, CLR_MIN.edge - w.gap / kS);
    }
  });
  return out;
}

function __auditLayout(){
  // Reveal every wrap so hidden slides are laid out (thus measurable), then
  // restore — the same trick the Google Slides export uses.
  const restore = [];
  wraps.forEach(w => { restore.push([w, w.style.display]); w.style.display = 'block'; });
  document.documentElement.classList.add('audit-final');   // animated slides in their end state
  const rank = { 'overlap-footer':5, 'table-frame':4, 'clipped-text':4, 'same-as-ground':4, 'overflow-bottom':3, 'overlap-text':2, 'overflow-side':1 };
  const findings = [];
  wraps.forEach((w, i) => {
    const slide = w.querySelector('.slide');
    if (!slide) return;
    const issues = auditSlide(slide);
    if (!issues.length) return;
    issues.sort((a, b) => (rank[b.kind] - rank[a.kind]) || (b.over - a.over));
    const h = slide.querySelector('h1,h2');
    const f = { index:i + 1, title:(h ? h.textContent.trim() : '').slice(0, 60),
                kind:issues[0].kind, detail:issues[0].detail || Math.round(issues[0].over) + 'px' };
    if (issues[0].text) f.text = issues[0].text;               // what to look at
    if (issues.length > 1) f.more = issues.length - 1;
    findings.push(f);
  });
  restore.forEach(([w, d]) => { w.style.display = d; });
  document.documentElement.classList.remove('audit-final');
  return findings;
}
window.__auditLayout = __auditLayout;

// The clearance list (the CLEARANCE AUDIT below): kept apart from the layout findings, in <div id="__audit_clearance__">.
// Each item: { index, title, kind, over, text, detail, path }. measureClearance() reads the slides; writeClearance()
// marks them (class audit-clearance) and writes the list. Both run from ?audit=1 (after the page settles, see clrRunSettled).
function measureClearance(){
  const restore = [];
  wraps.forEach(w => { restore.push([w, w.style.display]); w.style.display = 'block'; });
  document.documentElement.classList.add('audit-final');
  const findings = [];
  wraps.forEach((w, i) => {
    const slide = w.querySelector('.slide');
    if (!slide) return;
    const scale = slide.offsetWidth ? slide.getBoundingClientRect().width / slide.offsetWidth : 1;
    const h = slide.querySelector('h1,h2');
    const title = (h ? h.textContent.trim() : '').slice(0, 60);
    clrAudit(slide, scale).forEach(f => findings.push(Object.assign({ index: i + 1, title }, f)));
  });
  restore.forEach(([w, d]) => { w.style.display = d; });
  document.documentElement.classList.remove('audit-final');
  return findings;
}
function writeClearance(findings){
  const counts = new Map();
  findings.forEach(f => counts.set(f.index, (counts.get(f.index) || 0) + 1));
  wraps.forEach((w, i) => {
    const slide = w.querySelector('.slide');
    if (!slide) return;
    slide.classList.toggle('audit-clearance', counts.has(i + 1));
    if (counts.has(i + 1)) slide.setAttribute('data-clearance', counts.get(i + 1) + ' clearance');
    else slide.removeAttribute('data-clearance');
  });
let cnode = document.getElementById('__audit_clearance__');
if (!cnode){ cnode = document.createElement('div'); cnode.id = '__audit_clearance__'; cnode.hidden = true; document.body.appendChild(cnode); }
cnode.textContent = JSON.stringify(findings);
  return findings;
}
function __auditClearance(){ return writeClearance(measureClearance()); }
window.__auditClearance = __auditClearance;

// Top-heavy probe. Content reaching less than this share of the height above the
// footer reads as a half-empty slide (template bullet slides sit at ~0.55-0.62,
// visual layouts at 0.67+). Sparse/bleed layouts are short by design.
const AUDIT_FILL_MIN = 0.65;
function auditFill(slide){
  if (slide.matches(AUDIT_BLEED)) return null;
  const pad = slide.querySelector('.pad');
  if (!pad) return null;
  const sr = slide.getBoundingClientRect();
  const foot = slide.querySelector('.foot');
  const floor = foot && auditVisible(foot) ? foot.getBoundingClientRect().top : sr.bottom;
  let bottom = -Infinity;
  pad.querySelectorAll('*').forEach(el => {
    if (el.closest('.notes') || !auditVisible(el)) return;
    const cs = getComputedStyle(el);
    const painted = auditTextLeaf(el) || /^(IMG|SVG|CANVAS|VIDEO|IFRAME)$/i.test(el.tagName)
      || cs.backgroundImage !== 'none' || !/^(transparent|rgba\(0, 0, 0, 0\))$/.test(cs.backgroundColor)
      || parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.borderBottomWidth) > 0;
    if (painted) bottom = Math.max(bottom, el.getBoundingClientRect().bottom);
  });
  return bottom > sr.top ? (bottom - sr.top) / (floor - sr.top) : null;
}
function __auditReview(){
  const restore = [];
  wraps.forEach(w => { restore.push([w, w.style.display]); w.style.display = 'block'; });
  const review = [];
  document.documentElement.classList.add('audit-final');
  wraps.forEach((w, i) => {
    const slide = w.querySelector('.slide');
    const fill = slide && auditFill(slide);
    if (fill === null || fill >= AUDIT_FILL_MIN) return;
    const h = slide.querySelector('h1,h2');
    review.push({ index:i + 1, title:(h ? h.textContent.trim() : '').slice(0, 60),
                  kind:'top-heavy', detail:Math.round(fill * 100) + '%' });
  });
  restore.forEach(([w, d]) => { w.style.display = d; });
  document.documentElement.classList.remove('audit-final');
  return review;
}
window.__auditReview = __auditReview;

function auditReport(findings, review = []){
  let node = document.getElementById('__audit__');
  if (!node){ node = document.createElement('div'); node.id = '__audit__'; node.hidden = true; document.body.appendChild(node); }
  node.textContent = JSON.stringify(findings);            // read by --dump-dom
  document.body.classList.add('audit-mode');              // enable the dev overlay
  findings.forEach(f => {
    const slide = wraps[f.index - 1] && wraps[f.index - 1].querySelector('.slide');
    if (!slide) return;
    slide.classList.add('audit-flag');
    slide.setAttribute('data-audit', f.kind + ' +' + f.detail);
  });
  let rnode = document.getElementById('__audit_review__');
  if (!rnode){ rnode = document.createElement('div'); rnode.id = '__audit_review__'; rnode.hidden = true; document.body.appendChild(rnode); }
  rnode.textContent = JSON.stringify(review);
  review.forEach(f => {
    const slide = wraps[f.index - 1] && wraps[f.index - 1].querySelector('.slide');
    if (!slide || slide.classList.contains('audit-flag')) return;   // a must-fix badge wins
    slide.classList.add('audit-review');
    slide.setAttribute('data-audit', 'review: ' + f.kind + ' ' + f.detail);
  });
  return findings;
}

/* =========================================================================
   BOOTSTRAP — load slides (unless pre-bundled), then initialise
   ========================================================================= */
(async function bootstrap(){
  const existing = document.querySelectorAll('.slide-wrap');
  if (!existing.length) await loadSlidesViaScripts();   // skip if slides already inline
  wraps = Array.from(document.querySelectorAll('.slide-wrap'));
  if (!wraps.length){ showLoadHelp(); return; }
  initDeck();
  if (/[?&]audit\b/.test(location.search) && !IS_PRESENTER){
    clrSettle(() => { auditReport(__auditLayout(), __auditReview()); clrRunSettled(measureClearance, writeClearance); });
  }
})();
