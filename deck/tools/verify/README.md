# Verify tools — browser-free gates

Two pure-Python, no-dependency gates that check a deck *without launching a
browser*. They run in milliseconds, so they make a good fast pre-flight before
the Chrome load-check + `?audit=1` layout audit, and a good CI gate where a
browser is inconvenient. They are complementary to `?audit=1`, not a replacement:
`?audit=1` measures *rendered geometry* (overflow, footer collisions) and needs
Chrome; these check *references, offline-ness, and copy* statically.

Both were ported from the `databricks-corporate-slides` skill and adapted to
dbx-slides's architecture (a folder of `slides/*.js` `DECK.slide(\`…\`)`
template literals ordered by `slides/manifest.js`, styled by `assets/style.css`
+ `assets/fonts.css`). The one adaptation point is the front end, in
`decksrc.py`; the rule tables and checks are otherwise faithful to the originals.

```
tools/verify/
├── decksrc.py          shared extractor: manifest order → active slide bodies + CSS
├── deslop_lint.py      brand-voice / anti-slop gate (--source keeps the user's copy)
├── verify_content.py   copy-fidelity gate: the deck vs. the user's brief (--source); --compare for a rebuild
├── audit_layout.py     layout + clearance audits in headless Chrome (1440x900, 1280x720, print)
└── verify_deck.py      static reference + offline verifier (Phase 2)
```

Run them from the deck folder (the deck argument is optional — they auto-detect
the deck root that contains `index.html` + `slides/manifest.js`):

```bash
python3 tools/verify/deslop_lint.py
python3 tools/verify/verify_deck.py --check-overflow --check-legibility
python3 tools/verify/audit_layout.py
```

## audit_layout.py — the layout and clearance audits, in headless Chrome

Opens `index.html?audit=1` in each configuration below and reads both audit lists: `#__audit__` (the layout list:
overflow, text across the footer, clipped text, text over text, table frames) and `#__audit_clearance__` (visible
spacing: a box, label or diagram edge closer than 8 px to its neighbour, frame or edge). Prints every finding; exit 0
when every list is empty, 1 on any finding, 2 when there is no Chrome or no `index.html`. Standard library only.

| Configuration | Viewport | Media |
|---|---|---|
| screen 1440x900 | 1440 x 900 (the harness size) | screen |
| screen 1280x720 | 1280 x 720 | screen |
| print | 1440 x 900 | print (`@media print`) |

Why a runner and not `--dump-dom`: dump-dom cannot emulate print, and the numbers move with the window size. Here
each configuration pins the viewport and the media type over the DevTools protocol, and the findings are read only
when the page has settled: the fonts are loaded, the animations have finished, and two measurements in a row agree.
Chrome is found from `CHROME` (or `CHROME_BIN`), the macOS Chrome app, or `chrome`/`chromium` on PATH. Options:
`--root DIR` (another deck folder), `--json FILE` (every configuration's findings).

## deslop_lint.py — brand-voice gate

Extracts **slide-visible** copy (speaker notes and HTML comments are stripped)
and flags the AI "tells" that make a deck read as machine-generated or off-brand.
Exits non-zero on any **HARD** tell, so it can gate a build.

- **HARD (block):** em dashes (`—`/`&mdash;`); any emoji (the functional check/cross
  marks `✓✔✕✖✗✘` used in tables/code are allowed); forbidden filler (unlock,
  leverage, delve, game-changer, revolutionary, next-generation, best-in-class,
  seamless, synergy, cutting-edge, turnkey); leftover template scaffolding
  (`goes here`, `Author Name`, `Section Title`, `A single headline claim`, `Lorem
  ipsum`, `======`, `PATTERN:`, …); the official layouts' own placeholder lines (`This spot is great
  for`, `Your visual here`, `Default bulleted list style`, `Table Header 1`, `Your Name`,
  `you@databricks.com`), so a cover, closing or divider left with its sample text fails; a period on a
  short title (≤4 words).
- **REVIEW (report, never block):** slogan-fat phrasing, empty intensifiers,
  significance inflation, the "X, not Y" title reflex, a repeated "One X. One Y."
  motif, and the same lead word starting ≥3 titles.

A hyphen in a number range (`6-7x`, `Feb-May`) is not an em dash and is not flagged.

Exit codes: `0` clean or review-only · `1` a HARD tell is present · `2` unreadable.

## verify_deck.py — static verifier

Proves the things you cannot eyeball and that `?audit=1` does not cover.

- **Gates (fail the build):** **template samples** (no active slide may be an unchanged
  template sample, e.g. a sample diagram still showing the kit's example nodes; fingerprints
  in `template_samples.json`, skipped on the baseline itself; maintainers regenerate them
  with `verify_deck.py --write-samples` from `template/` after changing a sample); **orphan files**
  (every `slides/*.js` is listed in `manifest.js`, `_`-hidden counts, so unpruned samples fail); tag balance (`<div>` open==close per slide); **code backslashes** (no single `\` before a newline inside `<pre>`/`<code>`: the template literal swallows it, write `\\`); **slide files parse as JavaScript** (a browser-free scan: every string, template literal and bracket closes, `decksrc.js_problem`); token
  resolution (every `var(--x)` resolves to a def in CSS, inline markup, or the
  deck's JS); asset resolution (every local `src`/`href`/`url(...)` exists on disk,
  including `@font-face` fonts); **gslides export command** (the toolbar's Google
  Slides export command in `assets/gslides.js` must stay a static string literal —
  no `--title`, no title interpolation — so the free-text title is never spliced
  into a shell line); **native SVG subset** (every `<svg data-gs="native">` — the
  architecture kit — uses only rect / circle / line / polyline / text / image, so the
  Google Slides export stays native instead of falling back to one image); **diagram colours** (shared with dbx-docsites/dbx-docs: colour attributes are keywords only, a style colour is `var(--token[,fallback])`, no canvas-sized rect; the opt-out is `data-diagram-literal` on a `<rect>` chip before an `resources/official/` image); optional `--expect-slides N`, `--expect-keywords`,
  `--check-overflow` (flags `vw/vh/vmin/vmax`).
- **Review (`--composition`, never fails):** reads each slide's pattern from its
  markup (root `.slide` modifier, then the first distinctive catalog class, so
  renamed files still classify) and prints the sequence, then flags: the same
  pattern 3+ times in a row (2 for bullet-only); 5+ slides with no breather
  (section, quote, big number, statement, full-bleed, split); bullet-only slides
  over ~1 in 4 content slides; and a bullet-only slide whose items read as a richer
  pattern (2+ figures → metrics, before/after → compare, 3+ step/phase leads →
  timeline, 2+ layer words → architecture, 3–5 `<strong>`-led items → cards).
  Sparse patterns are exempt from the repeat and richer-pattern rules.
- **Informational (never fail):** class resolution (classes used with no CSS rule —
  a typo, or a legitimate semantic/JS-hook class; `demo-multi` and `info` are known hooks); legibility (font sizes <16px —
  since `style.css` mixes slide content with app UI chrome that is legitimately
  small); **external URLs**; and **unused resources** (one line naming every file under `resources/` that no
  slide, asset or `index.html` references: prune them).
- **WARN (never fails the build, shown until fixed):** the `<title>` or the toolbar brand label still holds the
  template default (`Databricks Presentation`, `Databricks Template`). The title becomes the Google Slides file name.
- **REVIEW (never fails):** coral paint (a stroke, fill or border in the coral or lava token) on an element with no
  `.accent` or `.hl-col` opt-in class, one line per slide. A KEEP slide, where the title names the item, is fine:
  confirm it.

### External URLs and offline mode

Unlike `databricks-corporate-slides`, a dbx-slides deck **legitimately reaches
out**: the Google Fonts CDN, live-demo/video slides, and "open in new tab" links are
features. So external URLs are **informational by default** (listed, with a note that
they won't load offline). Pass **`--offline`** to make *any* external URL a hard
failure — that is how you verify a deck meant to run with no network. The deck's
fonts fall back to the bundled DM Sans / DM Mono (`resources/fonts/`, wired in
`assets/fonts.css`) whether online or off, so an offline deck still renders in brand
type after you remove the CDN `<link>`.

Exit codes: `0` all gates passed · `1` a gate failed · `2` unreadable.

## verify_content.py --compare: the same copy before and after a rebuild

`python3 tools/verify/verify_content.py --compare OLD NEW` renders both folders in headless Chrome (set `CHROME`
if it is not found; each deck is rendered once its slides are all in the DOM). The copy is the visible text of every
slide, its speaker notes (they are copy for a rebuild) and its links; the template's chrome (toolbar, menus, footer,
overview hints, the notes bar, the speaker view, export panels) is left out. The two copies are compared as multisets
of words and of links, so the order does not matter. Exit 0 when identical; exit 1 lists the words and links that
only one side has. Each side may also be a `.json` inventory (`{"text": "...", "links": [...]}`) or a markdown file
(its plain text, its links read from `[text](url)`): `--compare source.md DECK` checks a deck against its markdown
source.

## verify_content.py: copy-fidelity gate (run it whenever the user supplied copy)

Checks the deck's visible copy against the user's brief, so generators cannot quietly reword,
drop, or invent slide copy while every other gate passes. Speaker notes are not slide copy and
are not checked. Stdlib only, Python 3.9+.

```bash
python3 tools/verify/verify_content.py                  # run from the deck folder: checks against its brief.md
python3 tools/verify/verify_content.py DECK_DIR
```

The copy it checks against is the deck's own `brief.md`: save the user's copy there unchanged
(`cp <their file> brief.md`). With no `brief.md` the gate exits 2. `--source` may name the same file;
a different file with different text also exits 2, because a gate run against another brief says
nothing about this deck.

**HARD (exit 1): the brief's item is missing or changed**

- slide headings and titles (numbering such as `3 —` is ignored; case is ignored);
- table body cells: row labels and values (equivalent numbers match, see below);
- quoted lines of 2+ words, and blockquotes, verbatim (typography folded: curly quotes, nbsp,
  dashes; so an em dash rewritten to a colon **is** a change);
- code lines verbatim, whitespace ignored;
- numbers: `7,234,567` is matched by `7.2M`, `$7.2M`, `7.2 million`; `40%` by `40 percent`;
  a single-digit figure outside a table is REVIEW only;
- literal dates, times and versions;
- qualifiers: a figure the brief marks `(illustrative)`, `estimated`, `representative`, `projected`,
  `indicative`, `hypothetical`, `approximate`, `typical`, `simulated` or `sample` must keep one of
  them on the same slide (a table's header counts for its rows). "All numbers are illustrative" in
  the brief must appear somewhere in the deck;
- a list in the brief (two or more items of sentence length) of which none reaches the deck: the
  items alone are only REVIEW, so a dropped list is HARD;
- `must_include` items (front matter list, or a fenced ```` ```must_include ```` block).

**REVIEW (exit 0): show these to the user, do not "fix" the user's copy**

- brief sentences dropped or reworded (labels such as `Subtitle: …` are checked word by word);
- slide sentences and headings with no 5-gram (or, for headings, no word) from the brief:
  invented copy, such as a derived card heading or a takeaway line the generator added;
- a table's header row not shown (a chart, a gantt or a card grid often drops it; the row labels
  and values are still HARD);
- figures in the slide copy that the brief does not contain.

**Writing the brief.** Markdown or plain text. Put slide copy in the brief; put generator notes
(render as a chart, speaker notes are the agent's own words, layout choices) in HTML comments
(`<!-- … -->`), between `<!-- verify:ignore -->` and `<!-- verify:resume -->`, or under a heading
that starts with `Notes`, `Instructions`, `Generator`, `Delivery requirements`, `Required` or
`Layout`. Those are not copy.

**Precision on real data.** Run on the round-3 comparison output with a copy-only brief: the four
HARD headings and quoted labels were real changes (the `(illustrative)` dropped from a heading, em
dashes rewritten to colons and parentheses). Four more HARD lines were quadrant position labels that
the brief took from the SCRIPT's prose, not from the deck's copy; the deck does not show them, so a
real brief should leave them out. REVIEW lists the derived card headings, the invented takeaway and
gantt lines, and the reworded bullets; most entries are judgment calls worth showing, with some noise
from chart header rows.

## deslop_lint.py --source: keep the user's copy

`deslop_lint.py --source brief.md` checks the same voice rules, but a HARD tell inside a sentence
the brief already contains becomes REVIEW (`user copy, keep (report, do not rewrite)`). The test is
the sentence around the match: at least 80% of its 5-grams in the brief. Text the agent wrote stays
HARD. Never edit the user's words to pass the lint; report them.

A sentence never runs across a block boundary (paragraph, list item, table cell, heading, label), so
an em dash in the user's copy is matched against its own sentence even when the page puts it beside
other text. Without `--source`, the lint uses the deck's own `brief.md` when it exists, and says so
on stderr. An explicit `--source` must have the same text as that `brief.md` (exit 2 otherwise).

## Tests

From the skill folder:

```bash
python3 -m pytest tests/test_verify_content_slides.py
```

It covers the matcher, the brief parser, every HARD and REVIEW rule, the `--source` behaviour of
deslop, and that the copy gate's core is identical in the three skills.

## Note: the baseline template is *not* expected to pass these

`template/` is a gallery of editable sample slides, so it deliberately contains
placeholder copy (`goes here`, `Author Name`, `Section Title`) and sample prose —
`deslop_lint.py` will report those as HARD tells by design. Run the gates on a
**finished deck** (placeholders swapped for real content), not on the raw template.
`verify_deck.py`'s own gates (tags/tokens/assets) *do* pass on the template.

## Migrate icon viewBoxes (0.8.0 clearance rule)

A deliverable built before the 0.8.0 clearance fixes can carry an old icon viewBox that the audit now flags (the audit's finding names the element and says so). `python3 tools/verify/migrate_viewboxes.py <deliverable>` rewrites only the known template icon viewBoxes to their fixed values, prints what changed, and is idempotent (`--dry-run` reports only). Nothing else in a file changes.
