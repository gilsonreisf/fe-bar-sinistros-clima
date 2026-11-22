#!/usr/bin/env python3
"""Browser-free static verifier for a dbx-slides deck.

Ported from the databricks-corporate-slides skill. It proves the things you
cannot eyeball and that the runtime ?audit=1 layout audit does not cover: broken
class / token / asset references, stray external URLs, tag imbalance. It runs in
milliseconds with no Chrome, so it makes a good fast pre-flight before the Chrome
load-check + ?audit=1 pass, and a good CI gate where a browser is inconvenient.
The two are complementary: this checks references and offline-ness statically;
?audit=1 measures rendered geometry (overflow, footer collisions).

The front end is adapted for dbx-slides via decksrc.py: the deck is a folder
of slides/*.js template literals ordered by slides/manifest.js, with CSS in
assets/style.css (+ assets/fonts.css) loaded from index.html.

Checks (gates unless marked INFO):
  - tag balance         <div> open==close within each active slide body
  - code backslashes    BLOCKING: no single backslash before a newline inside <pre>/<code> (a template literal swallows it)
  - external URLs        INFO by default (font CDN, live demos, video, links are
                         features); a hard gate only under --offline, which forbids
                         every external URL (fonts still fall back to bundled DM Sans)
  - token resolution     every var(--x) used resolves to a def in CSS, inline
                         markup, or the deck's JS (a genuine typo fails)
  - class resolution     INFO — classes used with no CSS rule (semantic/JS-hook or typo)
  - asset resolution     every local src/href/url(...) exists on disk (incl. fonts)
  - diagram colours      every inline content <svg> takes its colours from tokens (shared
                         with dbx-docsites/dbx-docs): colour attributes are keywords only, a
                         style colour is var(--token[,fallback]), no canvas-sized rect. Opt-out:
                         data-diagram-literal on a <rect> chip behind an official logo only
  - slide count          --expect-slides N   (active, non-`_` manifest entries)
  - keyword presence     --expect-keywords keywords.json  {slide_num:[substr,...]}
  - overflow lint        --check-overflow    flags vw/vh/vmin/vmax in CSS
  - legibility           --check-legibility  INFO — lists <16px sizes (chrome vs body)
  - composition          --composition       REVIEW — layout rhythm: the same pattern 3+ in a
                         row (bullets: 2), 5+ slides with no breather, bullet-only over
                         ~1 in 4, a bullet slide whose content reads as a richer pattern.
                         Sparse slides (quote, section, big number, ...) are exempt.

Usage:
  python3 verify_deck.py [DECK_DIR] --expect-slides 12 --check-overflow --check-legibility
  python3 verify_deck.py [DECK_DIR] --offline          # forbid the font CDN too
  python3 verify_deck.py [DECK_DIR] --expect-keywords expected.json

Exit codes: 0 all passed | 1 a check failed | 2 could not read the deck.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decksrc  # noqa: E402

XMLNS = "www.w3.org"  # SVG/XML namespaces are identifiers, never fetched


def _strip_html_comments(s: str) -> str:
    return re.sub(r"<!--.*?-->", " ", s, flags=re.S)


# ---- checks -----------------------------------------------------------------

def check_tag_balance(entries) -> tuple[bool, list[str]]:
    """<div> open==close inside each active slide body (a broken slide-wrap).
    Strips <pre>/<code> content first so a slide that *displays* HTML in a code
    sample (literal or otherwise) doesn't skew the count."""
    ok, out, bad = True, [], []
    for fn, body in entries:
        b = _strip_html_comments(body)
        b = re.sub(r"<(pre|code)\b[^>]*>.*?</\1>", " ", b, flags=re.S | re.I)
        opens = len(re.findall(r"<div\b", b, re.I))
        closes = len(re.findall(r"</div>", b, re.I))
        if opens != closes:
            ok = False
            bad.append(f"  x {fn}: <div> {opens} open vs {closes} close")
    if bad:
        out = bad
    else:
        out = [f"  ok <div> balanced in all {len(entries)} slides"]
    return ok, out


CODE_SPAN = re.compile(r"<(pre|code)\b[^>]*>(.*?)</\1>", re.S | re.I)


def check_code_backslashes(entries) -> tuple[bool, list[str]]:
    """A slide is a JS template literal, so a single backslash before a newline inside <pre>/<code> is a line
    continuation: the newline and the backslash vanish and the next line joins the current one (a shell
    command's `\\` continuations collapse into one clipped line). The fix is `\\` in the source."""
    bad = []
    for fn, body in entries:
        for m in CODE_SPAN.finditer(body):
            for n in re.finditer(r"(\\+)\r?\n", m.group(2)):
                if len(n.group(1)) % 2:
                    line = body.count("\n", 0, m.start(2) + n.start()) + 1
                    bad.append(f"  x {fn} line {line}: a single backslash ends a line inside <{m.group(1)}>; "
                               "the template literal swallows it. Write two (\\\\) for each literal backslash")
    if bad:
        return False, bad
    return True, [f"  ok no line in <pre>/<code> ends in a swallowed backslash ({len(entries)} slides)"]


def check_external_urls(markup, css_blocks, index_html, offline) -> tuple[bool, list[str]]:
    """Collect every external URL. By default these are informational — an
    dbx-slides deck legitimately reaches out (font CDN, live-demo/video
    slides, "open in new tab" links), so a stray external URL is not a defect.
    With --offline every external URL is a hard failure, which is how you verify
    a deck that must run with no network (fonts then fall back to bundled DM Sans).
    """
    external: list[str] = []

    def collect(u: str, where: str):
        if re.match(r'^(https?:)?//', u) and XMLNS not in u:
            external.append(f"{where}: {u}")

    for m in re.finditer(r'(?:src|href)=["\']([^"\']+)["\']', markup, re.I):
        collect(m.group(1), "slide")
    for label, css in css_blocks:
        for m in re.finditer(r'url\(\s*["\']?([^"\')]+)', css, re.I):
            collect(m.group(1), f"css {label}")
        for m in re.finditer(r'@import\s+["\']?([^"\';\s]+)', css, re.I):
            collect(m.group(1), f"css {label} @import")
    for m in re.finditer(r'(?:src|href)=["\']([^"\']+)["\']', _strip_html_comments(index_html), re.I):
        collect(m.group(1), "index.html")

    if not external:
        return True, ["  ok no external URLs (fully self-contained / offline-ready)"]
    if offline:
        return False, [f"  x external URL (offline mode forbids any): {h}" for h in external]
    return True, (["  i external references (need a network; will not load offline):"]
                  + [f"       {h}" for h in external]
                  + ["  i not a failure by default — run with --offline to forbid these; "
                     "fonts fall back to bundled DM Sans offline regardless"])


def check_tokens(markup, css_blocks, extra_defined) -> tuple[bool, list[str]]:
    """Every var(--x) must resolve. Custom properties in dbx-slides are
    defined in CSS, inline in slide markup (e.g. gantt stagger `--d`), or set at
    runtime by deck.js (e.g. `--laser-color`); `extra_defined` carries the latter
    two so only a genuinely undefined token (a typo) fails."""
    defined = set(extra_defined)
    for _, css in css_blocks:
        defined |= set(re.findall(r"(--[\w-]+)\s*:", css))
    # Count all references for the summary, but only a reference with NO fallback
    # can actually break: `var(--x)` falls to invalid if --x is undefined, whereas
    # `var(--x, 0s)` resolves to the fallback. So only no-fallback refs can "miss"
    # (e.g. a shared style.css keeps `var(--d,0s)` for a slide type a deck pruned).
    refs, no_fallback = set(), set()
    for src in [markup] + [css for _, css in css_blocks]:
        refs |= set(re.findall(r"var\(\s*(--[\w-]+)", src))
        no_fallback |= set(re.findall(r"var\(\s*(--[\w-]+)\s*\)", src))
    missing = sorted(no_fallback - defined)
    if missing:
        return False, [f"  x undefined token referenced: {m}" for m in missing]
    return True, [f"  ok all {len(refs)} referenced tokens resolve ({len(defined)} defined)"]


# Classes that are semantic or JS hooks by design: a slide uses them with no CSS rule of their own, so they are
# not "unstyled" (#38). `demo-multi` is the multi-demo frame's hook, `info` the info-line marker a deck can quote.
KNOWN_HOOK_CLASSES = {"demo-multi", "info"}


def check_classes(markup, css_blocks) -> tuple[bool, list[str]]:
    """Classes used in slide markup that have no CSS rule. Informational, not a
    failure: dbx-slides legitimately uses semantic/modifier/JS-hook classes
    with no dedicated rule (e.g. `.after` on a compare image, `.demo-multi`). A
    name here is worth a glance for a typo, but is not necessarily a defect."""
    defined = set()
    for _, css in css_blocks:
        defined |= set(re.findall(r"\.([A-Za-z][\w-]*)", css))
    used = set()
    for m in re.finditer(r'class=["\']([^"\']+)["\']', markup):
        used |= set(m.group(1).split())
    missing = sorted(used - defined - KNOWN_HOOK_CLASSES)
    if missing:
        return True, ([f"  i {len(missing)} class(es) used but not in any CSS rule "
                       "(semantic/JS-hook, or a typo — check):"]
                      + [f"       .{c}" for c in missing])
    return True, [f"  ok all {len(used)} classes used have a CSS rule ({len(defined)} defined)"]


def check_assets(markup, index_html, deck: Path, css_blocks) -> tuple[bool, list[str]]:
    missing = []
    for src, where in ((markup, "slide"), (_strip_html_comments(index_html), "index.html")):
        for m in re.finditer(r'(?:src|href)=["\']([^"\']+)["\']', src, re.I):
            u = m.group(1)
            if re.match(r'^(https?:)?//|^data:|^#|^mailto:', u):
                continue
            if not (deck / u).exists():
                missing.append(f"{where} -> {u}")
    for label, css in css_blocks:
        lp = deck / label
        base = lp.parent if lp.exists() else deck
        for m in re.finditer(r'url\(\s*["\']?([^"\')]+)', css, re.I):
            u = m.group(1)
            if re.match(r'^(https?:)?//|^data:|^#', u):
                continue
            if not (base / u).exists():
                missing.append(f"css {label} -> {u}")
    if missing:
        return False, [f"  x missing asset: {m}" for m in sorted(set(missing))]
    return True, ["  ok every local asset + @font-face target resolves on disk"]


_VU = re.compile(r"(?<![\w.])(\d*\.?\d+)(vw|vh|vmin|vmax)\b", re.I)


def check_overflow(css_blocks, markup="") -> tuple[bool, list[str]]:
    """Flag vw/vh/vmin/vmax in the deck CSS and in inline style="" attributes
    (slides use inline styles heavily, so scanning only stylesheets would miss a
    `<div style="width:50vw">`). Scoped to style attribute values so slide body
    text can't false-positive."""
    hits = []
    for label, css in css_blocks:
        for m in _VU.finditer(css):
            hits.append(f"{label}: {m.group(0)}")
    for sm in re.finditer(r'style=["\']([^"\']*)["\']', markup, re.I):
        for m in _VU.finditer(sm.group(1)):
            hits.append(f"inline style: {m.group(0)}")
    if hits:
        return False, [f"  x viewport unit (overflows under fixed-canvas scale): {h}" for h in hits[:40]]
    return True, ["  ok no vw/vh/vmin/vmax units in deck CSS or inline styles"]


def check_legibility(css_blocks) -> tuple[bool, list[str]]:
    """Report small font sizes. Informational, not a failure: assets/style.css
    mixes slide content with app UI chrome (toolbar, help bar, notes bar, grid
    hints) that is screen-only and legitimately below 12px, and one static file
    cannot tell them apart. Readable slide body should be >=16px authored (the
    canvas scales up); reserve <16px for eyebrow/footer/caption/source and UI."""
    tiny, chrome = [], []
    for label, css in css_blocks:
        for m in re.finditer(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", css, re.I):
            v = float(m.group(1))
            if v < 12:
                tiny.append(f"{label}: {v:g}px")
            elif v < 16:
                chrome.append(v)
    out = []
    if tiny:
        out += [f"  i below 12px (confirm UI chrome, not slide body): {t}" for t in tiny]
    else:
        out.append("  ok no font-size below 12px")
    if chrome:
        vals = ", ".join(f"{v:g}px" for v in sorted(set(chrome)))
        out.append(f"  i {len(chrome)} declaration(s) in 12-15px ({vals}) - should be "
                   "eyebrow/footer/caption/source chrome or app UI, not readable slide body")
    return True, out


NATIVE_OK = {"svg", "g", "defs", "marker", "title", "desc", "rect", "circle", "ellipse",
             "line", "polyline", "text", "tspan", "image"}


def check_native_svg(entries) -> tuple[bool, list[str]]:
    """Every <svg data-gs="native"> (architecture kit) must stay inside the subset the
    Google Slides exporter turns into native shapes; anything else (a <path> outside a
    <marker>, a gradient, foreignObject) silently degrades the export to one image."""
    out, ok, n = [], True, 0
    for label, body in entries:
        for m in re.finditer(r'<svg\b[^>]*data-gs="native"[^>]*>(.*?)</svg>', body, re.S):
            n += 1
            inner = re.sub(r"<(defs|marker)\b.*?</\1>", "", m.group(1), flags=re.S)
            bad = sorted({t for t in re.findall(r"<([a-zA-Z][\w:-]*)", inner) if t not in NATIVE_OK})
            if bad:
                ok = False
                out.append(f"x {label}: native SVG uses {', '.join('<' + b + '>' for b in bad)}")
    if ok:
        out.append(f"ok {n} native SVG diagram(s) stay inside the exportable subset")
    return ok, out



# ---- diagram colours (content SVG takes its colours from tokens) ------------
# Shared rule with dbx-docsites / dbx-docs (DIAGRAM-COLOUR-RULE, identical semantics), checked
# on the slide sources (no browser). Every inline <svg> in an active slide:
#   1. a colour presentation attribute (fill, stroke, stop-color, flood-color, lighting-color,
#      color) must be none / transparent / currentColor / inherit / url(...): attributes cannot
#      read var(), so colours live in style="";
#   2. a colour in style="" must be var(--token) or var(--token,<fallback>), or a keyword;
#      a literal #hex / rgb() / hsl() (or a named colour) fails;
#   3. no canvas rect: a rect at the origin covering >= 90% of the viewBox, with a fill that is
#      not none / transparent / var(--diagram-bg...) (a missing fill paints black) fails.
# The one opt-out is data-diagram-literal on a <rect> light chip behind an official logo: the next
# <image> (same <g> or within 300 characters) has href beginning resources/official/. Any other use
# fails; a valid one is printed as INFO. Code samples (<pre>, <code>) are not diagrams.
DIAGRAM_OPT_OUT = "data-diagram-literal"
_COLOUR_ATTRS = {"fill", "stroke", "stop-color", "color", "flood-color", "lighting-color"}
_KEYWORDS = {"none", "transparent", "currentcolor", "inherit"}
_LIT = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![\w-])|\b(?:rgba?|hsla?)\s*\(", re.I)
_TOKEN_VALUE = re.compile(r"var\(\s*--[\w-]+\s*(?:,.*)?\)", re.S)

def _token_mix(value: str) -> bool:
    """A color-mix() that mixes kit tokens only: every colour in it is a var(--token) reference, its brand fallback
    included, and no literal colour is left outside a var(). The pyramid base is one: 72% of chart-1 with ink."""
    v = value.strip()
    if not v.lower().startswith("color-mix("):
        return False
    rest = re.sub(r"var\(\s*--[\w-]+\s*(?:,[^()]*)?\)", "", v).lower()
    return not re.search(r"#|(?<!s)rgb|(?<!s)hsl|\b(red|blue|black|white)\b", rest)

_OPT_TAG = re.compile(r"<([A-Za-z][\w:-]*)\b[^>]*?\bdata-diagram-literal\b[^>]*>")
_OFFICIAL_IMG = re.compile(r"<image\b[^>]*?\bhref\s*=\s*[\"']resources/official/", re.I)
_HTML_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
              "param", "source", "track", "wbr"}


def _num(s) -> float | None:
    try:
        return float(re.sub(r"(px|%)$", "", str(s).strip()))
    except (TypeError, ValueError):
        return None


def _decls(style: str) -> list[tuple[str, str]]:
    out = []
    for part in style.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out.append((k.strip().lower(), v.strip()))
    return out


def _is_keyword(v: str) -> bool:
    return v.strip().lower() in _KEYWORDS or v.strip().lower().startswith("url(")


def _valid_opt_out_offsets(text: str) -> set[int]:
    """Offsets of the data-diagram-literal tags that meet the official-logo chip rule."""
    ok = set()
    for m in _OPT_TAG.finditer(text):
        if m.group(1).lower() == "rect" and _OFFICIAL_IMG.search(text[m.end():m.end() + 300]):
            ok.add(m.start())
    return ok


class _DiagramScan(HTMLParser):
    """Walks one slide body and records, per content <svg>, the colour findings (rules 1-3)
    and the opt-outs. Stdlib only."""

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.text = text
        self.line_starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                self.line_starts.append(i + 1)
        self.valid_opt = _valid_opt_out_offsets(text)
        self.svg_depth = 0
        self.svg_vb: tuple[float, float] | None = None
        self.svg_label = ""
        self.stack: list[str] = []
        self.svgs = 0
        self.opt_valid: list[str] = []          # INFO: valid opt-outs
        self.findings: list[tuple[str, str]] = []   # (kind, message)
        self.literals = 0
        self.canvas = 0

    def _offset(self) -> int:
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "svg" and self.svg_depth == 0:
            self.svgs += 1
            self.svg_label = a.get("aria-label", "")
            vb = a.get("viewbox", "").replace(",", " ").split()
            w, h = (_num(vb[2]), _num(vb[3])) if len(vb) == 4 else (_num(a.get("width")), _num(a.get("height")))
            self.svg_vb = (w, h) if w and h else None
        if tag == "svg":
            self.svg_depth += 1
        if self.svg_depth:
            self._element(tag, a)
        if tag not in _HTML_VOID:
            self.stack.append(tag)

    def _element(self, tag, a):
        if DIAGRAM_OPT_OUT in a:
            if self._offset() in self.valid_opt:
                self.opt_valid.append(f"<{tag}>")
                return                              # exempt this element from rules 1-3
            self.findings.append(("opt", f"{self._desc(tag, a)}: data-diagram-literal only applies to a "
                                  "chip behind an official logo (an <image> with href resources/official/)"))
        fill = a.get("fill")
        style_fill = None
        for name, value in a.items():                 # rule 1
            if name in _COLOUR_ATTRS and not _is_keyword(value):
                self.literals += 1
                suggest = f"var(--token,{value})" if _LIT.search(value) else "var(--token)"
                self.findings.append(("attr", f'{self._desc(tag, a)} {name}="{value}": a colour attribute '
                                      f'cannot read var(); move it into style="{name}:{suggest}"'))
        for prop, value in _decls(a.get("style", "")):   # rule 2
            if prop == "fill":
                style_fill = value
            if prop in _COLOUR_ATTRS and not _is_keyword(value) and not _TOKEN_VALUE.fullmatch(value) and not _token_mix(value):
                self.literals += 1
                self.findings.append(("style", f"style {prop}:{value}: a literal colour; "
                                      f"use var(--token,{value})"))
        if tag == "rect" and self.svg_vb and self._covers_canvas(a):   # rule 3
            f = style_fill if style_fill is not None else fill
            if f is None:
                f_ok, shown = False, "no fill (paints black)"
            else:
                f_ok = f.strip().lower() in ("none", "transparent") or f.strip().startswith("var(--diagram-bg")
                shown = f'fill="{f}"'
            if not f_ok:
                self.canvas += 1
                self.findings.append(("canvas", f"canvas rect ({self._desc(tag, a)} {shown}): diagrams have "
                                      "no canvas; drop the background rect (it sits on the page)"))

    def _covers_canvas(self, a) -> bool:
        vbw, vbh = self.svg_vb
        def at_origin(v, full):
            n = _num(v) if v not in (None, "") else 0.0
            return n is not None and abs(n) <= 0.02 * full
        def covers(v, full):
            if v.strip() == "100%":
                return True
            n = _num(v)
            return n is not None and n >= 0.9 * full
        return (at_origin(a.get("x"), vbw) and at_origin(a.get("y"), vbh)
                and covers(a.get("width", ""), vbw) and covers(a.get("height", ""), vbh))

    @staticmethod
    def _desc(tag, a):
        return f"<{tag}>"

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i] == tag:
                for t in self.stack[i:]:
                    if t == "svg":
                        self.svg_depth = max(0, self.svg_depth - 1)
                del self.stack[i:]
                return


def check_diagram_literals(entries) -> tuple[bool, list[str]]:
    """Every inline content <svg> in the active slides takes its colours from tokens.
    entries: [(filename, raw_body)] from decksrc.slide_entries (manifest order)."""
    out: list[str] = []
    info: list[str] = []
    svgs = n_lit = n_canvas = 0
    for k, (fn, body) in enumerate(entries, 1):
        text = decksrc.strip_notes(_strip_html_comments(body))
        text = re.sub(r"<(pre|code)\b[^>]*>.*?</\1>", lambda m: " " * len(m.group(0)), text, flags=re.S | re.I)
        scan = _DiagramScan(text)
        scan.feed(text)
        scan.close()
        svgs += scan.svgs
        n_lit += scan.literals
        n_canvas += scan.canvas
        heading = (decksrc.headings(body) or [""])[0]
        for kind, msg in scan.findings:
            where = f'slide {k} ({fn}) [svg "{scan.svg_label or heading}"]'
            out.append(f"  x {where}: {msg}")
        info += [f"  i slide {k} ({fn}): valid {DIAGRAM_OPT_OUT} on {e} (official logo chip)"
                 for e in scan.opt_valid]
    ok = not out
    summary = f"  summary: {n_lit} colour literal(s), {n_canvas} canvas rect(s) in {svgs} content SVG(s)"
    shown = out[:40] + ([f"  ... {len(out) - 40} more"] if len(out) > 40 else [])
    if ok:
        shown = [f"  ok {svgs} content SVG(s) take their colours from tokens"]
    return ok, shown + info + [summary]



def check_gslides_cmd_safe(deck: Path) -> tuple[bool, list[str]]:
    """The toolbar's Google Slides export command must not splice the deck title
    (or any runtime value) into the shell command line — `JSON.stringify` is JSON
    quoting, not shell quoting. The exporter reads the title from the extracted
    deck, so the shown command carries only a Drive-folder placeholder and no
    `--title`. Guards against a future regression (cf. the dbx-docs PR #2546
    review, which removed `--title` from the Docs toolbar command).
    """
    js = deck / "assets" / "gslides.js"
    if not js.exists():
        return True, ["  i no assets/gslides.js (deck has no Google Slides export)"]
    src = js.read_text(encoding="utf-8", errors="replace")
    # The panel builds each shown command in a `var CMD… = …;` statement (the preview and the build).
    stmts = re.findall(r"\bvar\s+CMD\w*\s*=\s*(.+?);", src, re.S)
    if not stmts:
        return False, ["  x could not find a `var CMD… = …;` export command in assets/gslides.js"]
    problems = []
    for stmt in stmts:
        if "--title" in stmt:
            problems.append("  x export command passes --title (would interpolate the untrusted "
                            "title into the shell line — the exporter reads the title)")
        if re.search(r"\+\s*(?:JSON\.stringify|ir\.title|ir\[)", stmt):
            problems.append("  x export command interpolates a runtime value into the shell line")
    if problems:
        return False, sorted(set(problems))
    return True, [f"  ok {len(stmts)} export command(s): no --title / no title interpolation"]


# ---- coral is opt-in (REVIEW only): a highlight, not the official coral ------------------------------------------
# Coral (the coral and the lava red) is an accent for the one point a title names. A coral stroke or fill on an
# element that carries no opt-in class (.accent, .hl-col) is a default accent. One REVIEW line per slide (#4).
_CORAL_VALUE = re.compile(r"var\(\s*--(?:db-coral|db-orange|db-orange-d|chart-accent|db-coral-tint)\b|#FF5F46|#FF3621|"
                          r"rgba\(\s*255\s*,\s*(?:95|54)\s*,", re.I)
_OPT_IN = {"accent", "hl-col"}
# The official elements are coral by default (the Databricks template): the subtitle, the goal cards, their labels and
# the problem icons. They are not highlights, so they are not reviewed.
_OFFICIAL_CLASSES = {"slide-sub", "goal", "g-ico", "g-lbl", "problem-card"}
_PAINT_DECL = re.compile(r"(stroke|fill|background(?:-color)?|border(?:-[a-z]+)?|box-shadow|outline)\s*:\s*([^;\"']*)", re.I)
_START_TAG = re.compile(r"<([a-zA-Z][\w:-]*)\b([^>]*)>")


def check_coral_paint(entries) -> tuple[bool, list[str]]:
    """Coral paint on an element with no opt-in class, per slide. REVIEW: a KEEP slide (the title names the one
    item) or a coral layout (its root has the class `coral`) is fine; the review asks the author to confirm."""
    out = []
    for k, (fn, body) in enumerate(entries, 1):
        b = decksrc.strip_notes(_strip_html_comments(body))
        b = re.sub(r"<(pre|code)\b[^>]*>.*?</\1>", " ", b, flags=re.S | re.I)
        root = re.search(r'class="slide((?:\s[^"]*)?)"', b)
        if root and "coral" in set(root.group(1).split()):
            continue
        # the official icon blocks (goal and problem icons) are coral by default, not highlights: not reviewed
        b = re.sub(r'<div class="(?:g-ico|ico)"[^>]*>.*?</div>', ' ', b, flags=re.S)
        hits, kinds = 0, set()
        for m in _START_TAG.finditer(b):
            attrs = m.group(2)
            cls = re.search(r'class="([^"]*)"', attrs)
            if cls and _OPT_IN & set(cls.group(1).split()):
                continue
            if _OFFICIAL_CLASSES & set(cls.group(1).split()) if cls else False:
                continue
            if re.search(r'aria-label="(Problem|Goal) icon"', attrs):
                continue
            style = re.search(r'style="([^"]*)"', attrs)
            for d in _PAINT_DECL.finditer(style.group(1) if style else ""):
                if _CORAL_VALUE.search(d.group(2)):
                    hits += 1
                    kinds.add(d.group(1).lower().split("-")[0])
            for name in ("stroke", "fill"):
                v = re.search(rf'\s{name}="([^"]*)"', attrs)
                if v and _CORAL_VALUE.search(v.group(1)):
                    hits += 1
                    kinds.add(name)
        if hits:
            out.append(f"  ! slide {k} ({fn}): {hits} coral paint(s) ({', '.join(sorted(kinds))}) with no .accent "
                       "opt-in: a neutral token, or the opt-in class if the title names this item")
    return True, out or ["  ok no coral paint without the opt-in class in the slide markup"]


# ---- composition (REVIEW only) ----------------------------------------------
# A deck renames its slide files, so a slide's pattern is read from its markup:
# first the root `.slide` modifier (cover/section/quote/...), then the first
# distinctive body class from the template catalog (README §4.1).
_ROOT_PATTERNS = [("cover", "cover"), ("section", "section"), ("statement", "statement"),
                  ("closing", "closing"), ("fullbleed", "fullbleed"), ("split", "image-split"),
                  ("video", "video"), ("demo", "demo"), ("company", "company")]
_BODY_PATTERNS = [
    ("big-number", {"bignumber-display"}),
    ("glossary", {"glossary"}),
    ("composite", {"graphics-grid"}),
    ("agenda", {"agenda-list", "toc-grid"}),
    ("metrics", {"metrics-row", "statgrid", "roi-row", "casestudy-metrics"}),
    ("chart", {"chart", "linechart", "donut-wrap", "rings", "funnel"}),
    ("process", {"gantt", "timeline", "tline", "workflow", "roadmap", "cta-steps"}),
    ("compare", {"compare", "compare-static"}),
    ("table", {"db", "matrix-container", "quad-wrap"}),
    ("diagram", {"arch-grid", "arch-kit", "lh", "medallion", "uc", "dtree"}),
    ("code", {"code-block", "terminal", "nb-wrap"}),
    ("cards", {"cardset", "flip-row", "goals", "problem-cards", "cardsplit", "exsum", "insight", "cards-row"}),
    ("logos", {"logowall-grid", "logo-showcase", "icon-lib"}),
    ("team", {"team-row"}),
    ("icon-columns", {"icon-spot"}),
]
# Deliberately sparse slides: they give the room a breather and are exempt from the
# repetition and richer-pattern rules.
SPARSE = {"cover", "section", "quote", "big-number", "statement", "closing", "fullbleed",
          "image-split"}
STRUCTURE = {"agenda"}            # neither content nor breather
BULLET_ONLY = {"bullets", "text"}

_NUM = re.compile(r"(\$\s?\d|\d(?:[\d.,]*)\s?(?:%|x\b|×|[kmb]\b|ms\b|tb\b|gb\b|pb\b|dbus?\b))", re.I)
_SEQ = re.compile(r"^\s*(step|phase|stage|week|month|day|year|q[1-4]|\d{4}|first|then|next|finally)\b", re.I)
_LAYER = re.compile(r"^\s*(\w+\s)?(layers?|tiers?|bronze|silver|gold|ingest\w*|storage|serving|consumption)\b", re.I)
_CONTRAST = [("before", "after"), ("today", "tomorrow"), ("today", "target"), ("current", "target"),
             ("as-is", "to-be"), ("legacy", "modern")]


def slide_pattern(body: str) -> str:
    b = decksrc.strip_notes(_strip_html_comments(body))
    root = re.search(r'class="slide((?:\s[^"]*)?)"', b)        # not .slide-wrap
    root_cls = set(root.group(1).split()) if root else set()
    if "bignumber-display" in b:
        return "big-number"
    if "quote" in root_cls:
        return "quote"
    for cls, name in _ROOT_PATTERNS:
        if cls in root_cls:
            return name
    used = set()
    for m in re.finditer(r'class="([^"]+)"', b):
        used |= set(m.group(1).split())
    for name, sig in _BODY_PATTERNS:
        if used & sig:
            return name
    if re.search(r"<(svg|img|table|video|iframe|canvas)\b", b, re.I):
        return "visual"
    return "bullets" if re.search(r"<(ul|ol)\b", b, re.I) else "text"


def richer_hint(body: str) -> str | None:
    """For a bullet-only slide, name the richer pattern its content looks like.
    Word cues are read only from the titles and the first words of each item:
    body prose mentions "with", "vs" or "storage" far too often to mean anything."""
    b = decksrc.strip_notes(_strip_html_comments(body))
    raw = re.findall(r"<li\b[^>]*>(.*?)</li>", b, re.S | re.I)
    items = [decksrc.visible_text(i) for i in raw]
    leads = [" ".join(i.split()[:4]).lower() for i in items]
    titles = " ".join(decksrc.headings(b)).lower()
    cues = titles + " " + " ".join(leads)
    if sum(bool(_NUM.search(i)) for i in items) >= 2:
        return "numbers -> metrics row (07/08), stat cards (43) or big number (37)"
    # a slide already on the two-column layout (05, `.cols`) is the suggested layout for a before/after
    if 'class="cols"' not in b and (
            any(re.search(rf"\b{a}\b", cues) and re.search(rf"\b{z}\b", cues) for a, z in _CONTRAST)
            or re.search(r"\b(vs\.?|versus)\b", titles)):
        return "before/after -> compare (23/24), two-column (05) or table (26)"
    if len(items) >= 3 and sum(bool(_SEQ.match(i)) for i in items) >= 3:
        return "sequence -> timeline (25) or workflow (off-workflow)"
    if sum(bool(_LAYER.match(i)) for i in leads) >= 3 or re.search(r"\b(layers|tiers)\b", titles):
        return "layers -> architecture (29/57-59) or medallion (51)"
    if 3 <= len(items) <= 5 and all(re.match(r"\s*<(strong|b)\b", i, re.I) for i in raw):
        return "parallel labelled items -> cards (21/22) or goals (off-goals-3/5)"
    return None


def check_composition(entries) -> tuple[bool, list[str]]:
    """Deck-level layout rhythm (SKILL.md *Design, graphics & fit*). REVIEW only:
    never fails, since a rule can be broken on purpose; fix a finding or keep it
    knowingly."""
    pats = [slide_pattern(body) for _, body in entries]
    out = ["  i sequence: " + " · ".join(f"{i}:{p}" for i, p in enumerate(pats, 1))]
    finds: list[str] = []
    n = len(pats)

    # 1) the same non-sparse pattern 3+ times in a row; two bullet-only slides back to back
    i = 0
    while i < n:
        j = i
        while j + 1 < n and pats[j + 1] == pats[i]:
            j += 1
        run = j - i + 1
        # 'visual' is the catch-all for custom slides, so a run of it says nothing
        if pats[i] not in SPARSE | {"visual"} and (run >= 3 or (run == 2 and pats[i] in BULLET_ONLY)):
            finds.append(f"  ! slides {i + 1}-{j + 1}: {run}x '{pats[i]}' in a row "
                         "- vary the layout")
        i = j + 1

    # 2) 5+ slides with no breather (section, quote, big number, statement, image)
    run_start = None
    for k in range(n + 1):
        if k < n and pats[k] not in SPARSE:
            run_start = k if run_start is None else run_start
            continue
        if run_start is not None and k - run_start >= 5:
            finds.append(f"  ! slides {run_start + 1}-{k}: {k - run_start} slides with no "
                         "breather - add a section, quote, big number or statement")
        run_start = None

    # 3) bullet budget: at most ~1 in 4 content slides bullet-only
    content = [p for p in pats if p not in SPARSE | STRUCTURE]
    bullets = sum(p in BULLET_ONLY for p in content)
    if len(content) >= 4 and bullets * 4 > len(content):
        finds.append(f"  ! {bullets} of {len(content)} content slides are bullet-only "
                     "(budget ~1 in 4)")

    # 4) a bullet-only slide whose content matches a richer pattern
    for k, ((fn, body), p) in enumerate(zip(entries, pats), 1):
        if p in BULLET_ONLY:
            hint = richer_hint(body)
            if hint:
                finds.append(f"  ! slide {k} ({fn}): bullet-only, content reads as {hint}")

    out += finds or ["  ok no composition findings"]
    return True, out


def check_keywords(entries, kw) -> tuple[bool, list[str]]:
    ok, out = True, []
    texts = [decksrc.visible_text(body) for _, body in entries]
    for num, words in sorted(kw.items()):
        if num < 1 or num > len(texts):
            ok = False
            out.append(f"  x slide {num}: not in deck ({len(texts)} slides)")
            continue
        low = texts[num - 1].lower()
        miss = [w for w in words if w.lower() not in low]
        if miss:
            ok = False
            out.append(f"  x slide {num}: missing {miss}")
        else:
            out.append(f"  ok slide {num}: {len(words)} keyword(s) present")
    return ok, out



# ---- unchanged template samples --------------------------------------------
# A finished deliverable must not ship a template sample as-is (e.g. a sample
# architecture diagram still showing the kit's example nodes). The template's
# samples are fingerprinted in template_samples.json (whitespace-normalised
# SHA-256 of each body); regenerate it with --write-samples after any template
# change. Samples with no visible text (a logo-only closing) and STRUCTURAL ones
# (auto-filled) are not fingerprinted, since they are meant to be reused as-is.
import hashlib  # noqa: E402

SAMPLES = Path(__file__).resolve().parent / "template_samples.json"
STRUCTURAL = set()


def _fp(body: str) -> str:
    """Fingerprint of a sample: its tag skeleton (tag names in order) plus its visible text, whitespace
    normalised. Attributes, colour literals and inline styles are ignored, so a brand pass (a hex swap, a
    logo or font change) leaves an unmodified sample flagged. Any change to copy or structure unflags it."""
    s = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    s = decksrc.strip_notes(s)
    skel = " ".join(t.lower() for t in re.findall(r"<\s*/?\s*([a-zA-Z][\w:-]*)", s))
    text = " ".join(decksrc.visible_text(body).split())
    return hashlib.sha256((skel + "\n" + text).encode("utf-8")).hexdigest()


def is_baseline(root: Path) -> bool:
    return root.name == "template" and (root.parent / "SKILL.md").is_file()


def write_samples(root: Path, entries) -> int:
    known = {_fp(b): fn for fn, b in entries
             if fn not in STRUCTURAL and decksrc.visible_text(b).strip()}
    SAMPLES.write_text(json.dumps(dict(sorted(known.items(), key=lambda kv: kv[1])), indent=1) + "\n")
    print(f"wrote {len(known)} sample fingerprint(s) to {SAMPLES.name}")
    return 0


def check_template_samples(root: Path, entries) -> tuple[bool, list[str]]:
    if is_baseline(root):
        return True, ["  i skipped: this is the skill's baseline template (the samples themselves)"]
    if not SAMPLES.is_file():
        return True, ["  i no template_samples.json next to this script - check skipped"]
    known = json.loads(SAMPLES.read_text())
    hits = [f"  x {fn}: unchanged template sample ({known[h]}) - replace its content"
            for fn, b in entries if (h := _fp(b)) in known]
    return (False, hits) if hits else (True, [f"  ok none of the {len(entries)} slides is an unchanged template sample"])



TEMPLATE_TITLE = "Databricks Presentation"
TEMPLATE_BRAND = "Databricks Template"


def check_shell_text(deck: Path) -> tuple[bool, list[str]]:
    """The deck's <title> and toolbar brand label are the deliverable's name. The template's defaults are
    left in place by a rebuild, and the <title> becomes the Google Slides file name (#32). WARN, not a failure."""
    index = deck / "index.html"
    if not index.is_file():
        return True, ["  i no index.html"]
    src = _strip_html_comments(index.read_text(encoding="utf-8", errors="replace"))
    out, warn = [], False
    m = re.search(r"<title>(.*?)</title>", src, re.S | re.I)
    if m and m.group(1).strip() == TEMPLATE_TITLE:
        warn = True
        out.append(f"  ! index.html still has the template default <title> '{TEMPLATE_TITLE}': set it to the "
                   "deliverable's name (it also names the Google export).")
    b = re.search(r'<div class="brand"[^>]*>.*?</div>', src, re.S | re.I)
    label = re.sub(r"<[^>]+>", " ", b.group(0)) if b else ""
    label = " ".join(label.split())
    if label == TEMPLATE_BRAND:
        warn = True
        out.append(f"  ! index.html still has the template default toolbar label '{TEMPLATE_BRAND}': set it to the "
                   "deliverable's name.")
    if warn:
        return False, out
    return True, ["  ok the <title> and the toolbar label are not the template defaults"]


def check_unused_resources(deck: Path) -> tuple[bool, list[str]]:
    """One INFO line: the files under resources/ that no slide, stylesheet, script or index.html names (#39).
    The template ships the whole icon and logo library; a deliverable prunes what it does not use (README §1)."""
    res = deck / "resources"
    if not res.is_dir():
        return True, []
    corpus = []
    for f in list(deck.glob("slides/*.js")) + list((deck / "assets").glob("*")) + [deck / "index.html"]:
        if f.is_file():
            corpus.append(f.read_text(encoding="utf-8", errors="replace"))
    text = "\n".join(corpus)
    unused = sorted(str(p.relative_to(deck)) for p in res.rglob("*")
                    if p.is_file() and p.name not in text and str(p.relative_to(res)) not in text)
    if not unused:
        return True, ["  ok every file under resources/ is referenced"]
    return True, [f"  i {len(unused)} file(s) under resources/ no slide or asset references (prune them, README §1): "
                  + ", ".join(unused)]


def check_orphans(root: Path) -> tuple[bool, list[str]]:
    """Every slide file must be listed in the manifest (a `_` prefix hides it). A file
    the manifest never mentions is a leftover template sample nobody pruned."""
    listed = {e.lstrip("_") for e in decksrc.manifest_entries(root)}
    files = sorted(p.name for p in (root / "slides").glob("*.js") if p.name != "manifest.js")
    orphans = [f for f in files if f not in listed]
    if orphans:
        return False, [f"  x {len(orphans)} file(s) in slides/ not in manifest.js (delete, or list with a `_` prefix):"] + \
                      [f"       {f}" for f in orphans[:20]] + (["       ..."] if len(orphans) > 20 else [])
    return True, [f"  ok all {len(files)} slides/ files are listed in manifest.js"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Browser-free static verifier for a dbx-slides deck.")
    ap.add_argument("deck", nargs="?", help="deck folder (default: auto-detect)")
    ap.add_argument("--expect-slides", type=int)
    ap.add_argument("--expect-keywords", type=Path)
    ap.add_argument("--offline", action="store_true", help="forbid ALL external URLs, including the font CDN")
    ap.add_argument("--check-overflow", action="store_true")
    ap.add_argument("--check-legibility", action="store_true")
    ap.add_argument("--composition", action="store_true",
                    help="REVIEW the layout rhythm: repeats, breathers, bullet budget, richer patterns")
    ap.add_argument("--write-samples", action="store_true",
                    help="maintainers: fingerprint the baseline template's samples into template_samples.json")
    args = ap.parse_args()

    try:
        deck = decksrc.find_deck(args.deck)
        entries = decksrc.slide_entries(deck)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2

    css_blocks = decksrc.gather_css(deck)
    index_html = (deck / "index.html").read_text(encoding="utf-8", errors="replace")
    markup = _strip_html_comments("\n".join(body for _, body in entries))

    # Custom properties defined outside the deck's CSS: inline in slide markup /
    # index.html style="" attributes, and set at runtime in the deck's JS files.
    extra_tokens = set(re.findall(r"(--[\w-]+)\s*:", markup))
    extra_tokens |= set(re.findall(r"(--[\w-]+)\s*:", _strip_html_comments(index_html)))
    for js in sorted((deck / "assets").glob("*.js")):
        extra_tokens |= set(re.findall(r"(--[\w-]+)", js.read_text(encoding="utf-8", errors="replace")))

    ok = True

    def run(title, res, blocking=True, tag=None):
        nonlocal ok
        good, lines = res
        if blocking:
            ok = ok and good
            tag = "PASS" if good else "FAIL"
        else:
            tag = tag or "INFO"
            if tag == "WARN" and good:
                tag = "PASS"
        print(f"\n[{tag}] {title}")
        for ln in lines:
            print(ln)

    print(f"Verifying deck: {deck}")
    print(f"  active slides: {len(entries)}   css blocks: {len(css_blocks)}"
          f"{'   (offline mode: external URLs forbidden)' if args.offline else ''}")

    if args.expect_slides is not None:
        good = len(entries) == args.expect_slides
        run("slide count", (good, [f"  ok {len(entries)} == {args.expect_slides}"] if good
                            else [f"  x expected {args.expect_slides}, found {len(entries)}"]))
    if args.write_samples:
        return write_samples(deck, entries)
    run("template samples", check_template_samples(deck, entries))
    run("orphan files", check_orphans(deck))
    run("slide files parse as JavaScript", decksrc.check_scripts(deck, "slides", decksrc.active_slide_files(deck)))
    run("tag balance", check_tag_balance(entries))
    run("code blocks: no swallowed backslash", check_code_backslashes(entries))
    # external URLs: informational by default (demos/video/links/CDN are features),
    # a hard gate only under --offline. The function returns ok=True unless offline.
    run("external URLs", check_external_urls(markup, css_blocks, index_html, args.offline),
        blocking=args.offline)
    run("token resolution", check_tokens(markup, css_blocks, extra_tokens))
    run("class resolution", check_classes(markup, css_blocks), blocking=False)
    run("asset resolution", check_assets(markup, index_html, deck, css_blocks))
    run("gslides export command", check_gslides_cmd_safe(deck))
    run("deck title and toolbar label", check_shell_text(deck), blocking=False, tag="WARN")
    run("unused resources", check_unused_resources(deck), blocking=False, tag="INFO")
    run("coral paint without the opt-in", check_coral_paint(entries), blocking=False, tag="REVIEW")
    run("native SVG subset", check_native_svg(entries))
    run("diagram colours", check_diagram_literals(entries))
    if args.check_overflow:
        run("overflow lint", check_overflow(css_blocks, markup))
    if args.check_legibility:
        run("legibility", check_legibility(css_blocks), blocking=False)
    if args.composition:
        run("composition", check_composition(entries), blocking=False, tag="REVIEW")
    if args.expect_keywords:
        run("keyword presence", check_keywords(entries, {int(k): v for k, v in
                                                         json.loads(args.expect_keywords.read_text()).items()}))

    print("\n" + ("OK  verification passed" if ok else "FAIL  verification failed"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
