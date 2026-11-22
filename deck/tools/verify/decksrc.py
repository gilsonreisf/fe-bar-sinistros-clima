#!/usr/bin/env python3
"""Shared source extractor for the dbx-slides verify tools.

Both gates (deslop_lint.py, verify_deck.py) were ported from the
databricks-corporate-slides skill, whose scripts assume a single .html file of
<section> slides inside a <deck-stage>. dbx-slides is different: the deck is
a *folder* whose slide markup lives inside ``DECK.slide(`...`)`` template
literals across slides/*.js, ordered by slides/manifest.js, styled by
assets/style.css (+ assets/fonts.css) and loaded from index.html.

This module is the one adaptation point. It reads a deck folder and hands the
gates exactly what they need: the active slide bodies (in manifest order) and the
deck's CSS. Once the bodies and CSS come out here, the rule tables and checks in
the two gates port with almost no change.

No third-party deps; standard library only, so it runs offline from a copied
deck folder (the tools/ tree travels with the deck, like tools/gslides/).
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path

# --- locating the deck -------------------------------------------------------

def find_deck(start: str | Path | None = None) -> Path:
    """Return the deck root (folder with index.html + slides/manifest.js).

    Looks at `start` (or cwd), then walks up, then tries the folder two levels
    above this script (deck/tools/verify/decksrc.py -> deck). Raises if none fits.
    """
    def is_deck(p: Path) -> bool:
        return (p / "index.html").is_file() and (p / "slides" / "manifest.js").is_file()

    candidates: list[Path] = []
    if start:
        candidates.append(Path(start).resolve())
    here = Path.cwd().resolve()
    candidates.append(here)
    candidates.extend(here.parents)
    candidates.append(Path(__file__).resolve().parents[2])  # deck/tools/verify -> deck

    for c in candidates:
        if c.is_dir() and is_deck(c):
            return c
    raise SystemExit(
        "x could not find a deck (need index.html + slides/manifest.js). "
        "Pass the deck folder explicitly, e.g. `verify_deck.py /path/to/deck`."
    )

# --- manifest + slide bodies -------------------------------------------------

_ENTRY_RE = re.compile(r'["\'](_?[\w./-]+\.js)["\']')
# DECK.slide(`...`) — the body is one backtick literal with no inner backticks
# (the authoring contract forbids raw ` or ${ inside slide strings).
_SLIDE_RE = re.compile(r"DECK\.slide\(\s*`(.*?)`\s*\)", re.S)


def manifest_entries(deck: Path) -> list[str]:
    """All manifest entries in order, exactly as written (may include a `_` prefix)."""
    text = (deck / "slides" / "manifest.js").read_text(encoding="utf-8", errors="replace")
    entries: list[str] = []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0]  # drop trailing line comment
        for m in _ENTRY_RE.finditer(line):
            entries.append(m.group(1))
    return entries


def active_slide_files(deck: Path) -> list[str]:
    """Active (non-`_`) slide filenames, in manifest order."""
    return [e for e in manifest_entries(deck) if not e.startswith("_")]


def slide_body(deck: Path, filename: str) -> str:
    """The raw HTML inside a slide file's DECK.slide(`...`) literal."""
    p = deck / "slides" / filename
    src = p.read_text(encoding="utf-8", errors="replace")
    m = _SLIDE_RE.search(src)
    return m.group(1) if m else ""


def slide_entries(deck: Path) -> list[tuple[str, str]]:
    """[(filename, raw_body)] for every active slide, in manifest order.

    Raises if a manifest entry has no file, so a broken manifest fails loudly.
    """
    out: list[tuple[str, str]] = []
    for fn in active_slide_files(deck):
        if not (deck / "slides" / fn).is_file():
            raise SystemExit(f"x manifest lists {fn!r} but slides/{fn} does not exist")
        out.append((fn, slide_body(deck, fn)))
    return out

# --- text extraction ---------------------------------------------------------

_DIV_TAG = re.compile(r"</?div\b[^>]*>", re.I)
_NOTES_OPEN = re.compile(r'<div\s+[^>]*class="[^"]*\bnotes\b[^"]*"[^>]*>', re.I)


def strip_notes(fragment: str) -> str:
    """Remove speaker-notes blocks — they never render on the slide (.notes is
    display:none) so they are not slide-visible copy. Walks matching <div>/</div>
    so a note containing nested <div>s is fully removed (a non-greedy regex would
    stop at the first inner </div> and leak the rest of the note into the copy)."""
    out, i = [], 0
    while True:
        m = _NOTES_OPEN.search(fragment, i)
        if not m:
            out.append(fragment[i:])
            break
        out.append(fragment[i:m.start()])
        depth, j = 1, m.end()
        for tag in _DIV_TAG.finditer(fragment, m.end()):
            depth += -1 if tag.group(0).lstrip("<").startswith("/") else 1
            if depth == 0:
                j = tag.end()
                break
        else:
            j = len(fragment)  # unbalanced note: drop to end
        i = j
    return "".join(out)


def visible_text(fragment: str) -> str:
    """Slide-visible plain text: drop HTML comments, speaker notes, script/style,
    then tags; unescape entities and collapse whitespace.

    HTML comments matter here: slide bodies open with a template comment like
    `<!-- Title Slide B — Dark -->` that contains an em dash, which would be a
    false positive for the voice gate if left in.
    """
    s = re.sub(r"<!--.*?-->", " ", fragment, flags=re.S)
    s = strip_notes(s)
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


_HEADING_RE = re.compile(r"<h([1-3])\b[^>]*>(.*?)</h\1>", re.S | re.I)


def headings(fragment: str) -> list[str]:
    """Text of every <h1>/<h2>/<h3> in a slide body (titles carry the voice
    rules that target headings). Comments/notes stripped first."""
    body = strip_notes(re.sub(r"<!--.*?-->", " ", fragment, flags=re.S))
    out = []
    for m in _HEADING_RE.finditer(body):
        t = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        if t:
            out.append(t)
    return out

# --- CSS gathering (mirrors verify_deck.py's, but rooted at index.html) -------

def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


def gather_css(deck: Path) -> list[tuple[str, str]]:
    """[(label, css_text)] from index.html inline <style> + every local linked
    stylesheet (assets/style.css, assets/fonts.css, ...). CDN <link>s are skipped
    here; the external-URL check inspects them separately.

    `label` is the stylesheet's path relative to the deck root, so callers can
    resolve url(...) against the right directory.
    """
    index = deck / "index.html"
    html = re.sub(r"<!--.*?-->", " ", index.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    blocks: list[tuple[str, str]] = [
        ("index.html <style>", _strip_css_comments(m.group(1)))
        for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", html, re.S | re.I)
    ]
    for m in re.finditer(r'<link\b[^>]*rel=["\']?stylesheet["\']?[^>]*>', html, re.I):
        h = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
        if not h:
            continue
        href = h.group(1)
        if re.match(r'^(https?:)?//|^data:', href):
            continue  # CDN / data URI — not a local stylesheet
        p = (deck / href)
        if p.is_file():
            blocks.append((href, _strip_css_comments(p.read_text(encoding="utf-8", errors="replace"))))
    # A file's own <style> (e.g. the deck-wide style in slides/01-cover.js) applies to the whole deck: read
    # it with the deck's CSS, so the class and token checks see the rules it defines.
    for fn in active_slide_files(deck):
        src_file = deck / "slides" / fn
        if not src_file.is_file():
            continue
        for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", src_file.read_text(encoding="utf-8", errors="replace"), re.S | re.I):
            blocks.append(("slides/" + fn + " <style>", _strip_css_comments(m.group(1))))
    return blocks


# --- the files parse as JavaScript ---------------------------------------------

def js_problem(src: str) -> str | None:
    """A browser-free scan of a content file: strings, template literals (with ${} nesting), comments and brackets
    must all close. None when they do, else what is left open and the line it opened on. Two slides with an
    unterminated template literal passed every static gate in the round-4 comparison; only the rendered slide count
    showed they were missing. Regular-expression literals are not recognised (content files have none)."""
    i, n, line = 0, len(src), 1
    stack: list[tuple[str, int]] = []      # (opener, line): ( [ { ` ${
    in_tpl = False
    pair = {"(": ")", "[": "]", "{": "}"}
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
        if in_tpl:
            if c == "\\":
                i += 2
                continue
            if c == "`":
                stack.pop()
                in_tpl = False
                # What follows a literal is an operator, a separator or a closing bracket. Text there means a
                # backtick inside the markup ended the literal early (a pair of them keeps the count even).
                m = re.match(r"\s*([^\s])", src[i + 1:])
                if m and m.group(1) not in ")],;.+:?}`":
                    return f"text after the template literal closed on line {line}: a stray backtick in its content"
            elif src.startswith("${", i):
                stack.append(("${", line))
                in_tpl = False
                i += 2
                continue
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                return f"comment opened on line {line} is never closed"
            line += src.count("\n", i, j)
            i = j + 2
            continue
        if c in "\"'":
            start, j = line, i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                elif src[j] == "\n":
                    return f"string opened on line {start} is never closed"
                j += 1
            if j >= n:
                return f"string opened on line {start} is never closed"
            i = j + 1
            continue
        if c == "`":
            stack.append(("`", line))
            in_tpl = True
        elif c in pair:
            stack.append((c, line))
        elif c in ")]}":
            if not stack:
                return f"'{c}' on line {line} closes nothing"
            top, at = stack.pop()
            if top == "${":
                if c != "}":
                    return f"'${{' opened on line {at} is closed by '{c}' on line {line}"
                in_tpl = True
            elif pair.get(top) != c:
                return f"'{top}' opened on line {at} is closed by '{c}' on line {line}"
        i += 1
    if stack:
        top, at = stack[-1]
        what = "template literal" if top in ("`", "${") else f"'{top}'"
        return f"{what} opened on line {at} is never closed"
    return None


def check_scripts(root: Path, folder: str, files: list[str]) -> tuple[bool, list[str]]:
    """Every active content file under root/folder parses: what js_problem() finds, per file."""
    bad = []
    for fn in files:
        p = root / folder / fn
        if p.is_file():
            msg = js_problem(p.read_text(encoding="utf-8", errors="replace"))
            if msg:
                bad.append(f"  x {folder}/{fn}: {msg}")
    return (not bad, bad or [f"  ok {len(files)} files: every string, template literal and bracket closes"])
