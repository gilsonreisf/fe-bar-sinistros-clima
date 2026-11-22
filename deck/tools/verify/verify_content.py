#!/usr/bin/env python3
"""Copy-fidelity gate for a dbx-slides deck: the deliverable's copy vs. the user's brief.

Reads the copy through decksrc.py (the same extraction the other gates use) and checks it against the brief: what the
user said must survive, and what the agent invented or rewrote. Speaker notes never show on a slide, so they are not copy.

    python3 tools/verify/verify_content.py [--source brief.md] [DECK_DIR]
    python3 tools/verify/verify_content.py --compare BEFORE AFTER

--compare checks a rebuild against what it replaces (#33). Each side is a deck folder (rendered headless in Chrome: the
visible text of every slide, its speaker notes and its links; the template's chrome is left out), a .json inventory
({"text": "...", "links": [...]}), or a markdown file (converted to plain text, its links read from [text](url)). The two
copies are compared as multisets of words and of links, so the order does not matter. Exit 0 when identical, 1 with the
words and links that differ (or a title or toolbar label that differs) listed, 2 when a side cannot be read.

The copy it checks against is the deliverable's own brief.md: save the user's copy there unchanged. An explicit --source
must be that same copy (same text), so a brief of another deliverable cannot pass. No brief.md is an error (exit 2).

HARD (exit 1): a required item from the brief is missing or changed. Required items are headings, table cells, quoted
lines (2+ words), code lines (verbatim), numbers and literal dates/times/versions (equivalent forms match: 7,234,567 ~
7.2M ~ $7.2M; 40% ~ 40 percent), `must_include` items, and qualifiers ("illustrative", "estimated", ...) attached to a
figure in the brief.

REVIEW (exit 0): brief sentences that were dropped or reworded, deck sentences with no 5-gram from the brief (invented
copy), and figures in the deck the brief does not contain. Show these to the user; they are judgment calls. A sentence
that appears word for word in the copy (or the brief) is carried: it is never a REVIEW item, whatever its 5-grams say (#34).

Brief format: markdown or plain text. Front matter `must_include:` (a YAML list) and a fenced ```must_include block add
required strings. Generator notes go in HTML comments (`<!-- ... -->`), or between `<!-- verify:ignore -->` and
`<!-- verify:resume -->`, or under a heading that starts with Notes, Instructions, Generator, Delivery requirements,
Required or Layout: those are not copy.

Exit codes: 0 no HARD item (or --compare: the copies match) | 1 a HARD item (or --compare: they differ) | 2 could not read
the deck or the brief, or the deliverable has no brief.md / --source is not that brief.
Stdlib only, Python 3.9+.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import math
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decksrc  # noqa: E402

# ==== FRONT END (the only part that differs between the three skills' copies) ====

def find_root(arg):
    """An explicit folder must be a deck; only with no argument do we auto-detect."""
    if arg:
        p = Path(arg).resolve()
        if (p / "index.html").is_file() and (p / "slides" / "manifest.js").is_file():
            return p
        raise SystemExit(f"x {arg} is not a deck (no index.html + slides/manifest.js)")
    return decksrc.find_deck(None)


def front_units(root):
    """[(label, html)] for every active slide's copy. Speaker notes and HTML comments are not copy."""
    out = []
    for fn, body in decksrc.slide_entries(root):
        body = decksrc.strip_notes(re.sub(r"<!--.*?-->", " ", body, flags=re.S))
        out.append((fn, re.sub(r"\\([\\`$])", r"\1", body)))
    return out


# The visible copy of a rendered deck: every slide's text, its speaker notes (hidden in the view, copy for the
# rebuild check) and its links. The template's chrome is left out: the toolbar and menus, the footer and page number,
# the overview hints, the notes bar, the speaker view, the export panels and the demo frame's bar.
_COPY_JS = """(() => {
  const CHROME = '.foot,.pageno,.slide-checkbox,.slide-idx,.demo-bar,.laser-dot,.progress,.help,.grid-hint,.toolbar,.menu,#notesBar,#gsPanel,.presenter,script,style';
  const words = [], links = [];
  document.querySelectorAll('#deck .slide-wrap').forEach(s => {
    const w = document.createTreeWalker(s, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (!(n.parentElement && n.parentElement.closest(CHROME))) words.push(n.textContent);
    }
    s.querySelectorAll('a[href]').forEach(a => { if (!a.closest(CHROME)) links.push(a.getAttribute('href')); });
  });
  return JSON.stringify({ text: words.join(' '), links: links });
})()"""


def rendered_copy(folder):
    """(text, links) of a deck folder as Chrome renders it (the DOM after the deck's scripts ran). Needs headless Chrome
    (CHROME or CHROME_BIN, or a Chrome on the usual paths): the copy the reader gets, not the slide sources."""
    import audit_layout as al  # the sibling runner: the stdlib DevTools client
    binary = al.find_chrome()
    if not binary:
        raise SystemExit("Chrome not found: set CHROME to a Chrome or Chromium binary (--compare renders each deck)")
    entry = (Path(folder) / "index.html").resolve()
    if not entry.is_file():
        raise SystemExit(f"x {folder} has no index.html")
    chrome = al.Chrome(binary)
    try:
        target = chrome.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        session = chrome.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        chrome.call("Page.enable", {}, session)
        chrome.call("Emulation.setDeviceMetricsOverride",
                    {"width": 1280, "height": 720, "deviceScaleFactor": 1, "mobile": False}, session)
        chrome.call("Page.navigate", {"url": entry.as_uri()}, session)
        # The slides load one script after another: wait until every listed slide is in the DOM and the copy stops
        # changing between two reads (a read taken part-way counts fewer words).
        expected = len(decksrc.slide_entries(Path(folder).resolve()))
        deadline = time.time() + al.WAIT_S
        last = None
        while True:
            count = chrome.call("Runtime.evaluate", {"expression": "document.querySelectorAll('#deck .slide-wrap').length",
                                                     "returnByValue": True}, session).get("result", {}).get("value", 0)
            if count >= expected:
                data = json.loads(chrome.call("Runtime.evaluate", {"expression": _COPY_JS, "returnByValue": True},
                                              session)["result"]["value"])
                if last is not None and data == last:
                    return data["text"], data["links"]
                last = data
            if time.time() > deadline:
                raise SystemExit(f"x {folder}: the deck did not render within {al.WAIT_S} s")
            time.sleep(0.3)
    finally:
        chrome.close()


def copy_of(arg):
    """(text, links) of one side of --compare: a deck folder (rendered), a .json inventory or a markdown file."""
    p = Path(arg)
    if p.is_dir():
        return rendered_copy(p)
    if not p.is_file():
        raise SystemExit(f"x {arg} is neither a deck folder nor a file")
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("text", ""), list(data.get("links", []))
    if p.suffix.lower() in (".md", ".markdown"):
        return _md_text(p.read_text(encoding="utf-8", errors="replace"))
    return p.read_text(encoding="utf-8", errors="replace"), []


# ==== CORE (identical in all three skills; tests/test_verify_content_* checks this) ====
# Copy-fidelity model. The brief (markdown or plain text) is the user's copy. The
# deliverable is compared with it through the front end's units(). HARD = a required
# item from the brief is missing; REVIEW = a judgment the agent must show the user.

TYPO = {
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'", 0x2032: "'",
    0x201C: '"', 0x201D: '"', 0x201E: '"', 0x201F: '"', 0x2033: '"',
    0x00A0: " ", 0x202F: " ", 0x2007: " ", 0x2008: " ", 0x2009: " ", 0x2002: " ", 0x2003: " ",
    0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-", 0x2015: "-", 0x2212: "-",
    0x2026: "...", 0x200B: None, 0x200C: None, 0x200D: None, 0x2060: None, 0xFEFF: None,
}
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[A-Z0-9])")
MIN_SENT_TOKENS = 6          # sentences shorter than this are labels, not prose
GRAM = 5
BOILERPLATE = re.compile(r"©|all rights reserved|\bdatabricks, inc\b|copyright", re.I)
QUALS = {
    "illustrative": r"illustrat", "representative": r"representativ", "estimated": r"estimat",
    "projected": r"projected", "indicative": r"indicativ", "hypothetical": r"hypothetic",
    "approximate": r"approximat", "typical": r"typical", "simulated": r"simulat", "sample": r"\bsample\b",
}
QUAL_RE = {k: re.compile(r"\b" + v, re.I) for k, v in QUALS.items()}
IGNORE_HEAD = re.compile(
    r"^(notes?\b|instructions?\b|generator|for the (skill|generator|agent)\b|delivery requirements\b"
    r"|required\b|layout\b|author notes?\b|speaker notes?\b)", re.I)
# navigation and generated headings that a generator adds on purpose; never reported as invented
STRUCTURAL_HEADS = {"table of contents", "contents", "on this page", "in this guide", "navigation", "previous",
                    "next", "outline", "skip to content", "footnotes", "references"}
URL_RE = re.compile(r"\b(?:https?://|www\.)\S+")
LIT_RE = re.compile(
    r"(?<![\w.])(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?Z?)?|\d{1,2}:\d{2}(?::\d{2})?|\d+(?:\.\d+){2,})(?![\w.])")
NUM_RE = re.compile(
    r"(?<![\w.,])[$€£]?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<suf>\s?%|\s?(?i:percent)\b|\s?(?i:thousand|million|billion|trillion)\b|\s?(?i:bn|mn)\b"
    r"|[KMBT](?![A-Za-z])|k(?![A-Za-z]))?")
MULT = {"K": 1e3, "k": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
WORD_MULT = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12, "bn": 1e9, "mn": 1e6}
BLOCK_TAG = re.compile(
    r"</?(?:p|div|li|ul|ol|h[1-6]|tr|td|th|table|thead|tbody|caption|figcaption|figure|section|pre"
    r"|blockquote|dt|dd|dl|nav|text|header|footer|article|aside|label|button|option|summary|details"
    r"|hr|br|svg|g|title|desc)\b[^>]*>", re.I)
NUM_PREFIX = re.compile(r"^\s*(?:§\s*)?\d+[a-z]?(?:\.\d+)*\s*(?:[.:)]|[-–—])\s+|^\s*§\s*\d+[a-z]?\s*")
HEAD_LABEL = re.compile(r"^\s*(?:\*\*)?(?:heading|title)(?:\*\*)?\s*:\s*(.+?)\s*$", re.I)
LABEL_LINE = re.compile(r"^\s*[A-Z][A-Za-z /&()'-]{0,40}:\s")  # "Audience: ...", a new item
QUOTE_RE = re.compile(r"\"([^\"]+?)\"|“([^”]+?)”")


def typo(s):
    return s.translate(TYPO)


def norm(s):
    """Matching form for prose: typography folded, case-folded, dash spacing and whitespace collapsed."""
    s = typo(_html.unescape(s)).lower()
    s = re.sub(r"\s*-\s*", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s):
    """Word tokens. A spaced dash is a token of its own (a rewritten dash breaks the 5-grams around it);
    hyphens inside words are ignored, so 'time-travel' and 'time travel' match."""
    s = typo(_html.unescape(s)).lower()
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)  # 7,234,567 -> 7234567
    s = re.sub(r"\s-\s", " \u2014 ", s)
    return re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+|\u2014", s)


def grams(toks):
    return {tuple(toks[i:i + GRAM]) for i in range(len(toks) - GRAM + 1)}


def sentences(text):
    return [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]


@dataclass(frozen=True)
class Num:
    v: float
    sig: int
    pct: bool
    text: str


def parse_nums(s):
    """Every figure in s as a Num. Literal forms (dates, times, versions) are handled separately."""
    s = URL_RE.sub(" ", s)
    s = LIT_RE.sub(" ", s)
    out = []
    for m in NUM_RE.finditer(s):
        raw = m.group("num").replace(",", "")
        digits = re.sub(r"\D", "", m.group("num")).lstrip("0")
        sig = max(1, len(digits))
        suf = (m.group("suf") or "").strip()
        pct = suf.startswith("%") or suf.lower().startswith("percent")
        mult = MULT.get(suf) or WORD_MULT.get(suf.lower(), 1.0)
        out.append(Num(float(raw) * mult, sig, pct, m.group(0).strip()))
    return out


def _round_sig(x, n):
    if x == 0:
        return 0.0
    d = math.floor(math.log10(abs(x)))
    return round(x, -(d - n + 1))


def _close(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def num_match(src, dst):
    """Equivalent forms match: 7,234,567 ~ 7.2M ~ $7.2M; 40% ~ 40 percent. A source '%' needs a
    percent sign in the deliverable; a bare source number accepts either form."""
    if src.pct and not dst.pct:
        return False
    if _close(src.v, dst.v):
        return True
    if dst.sig >= 2 and _close(_round_sig(src.v, dst.sig), dst.v):
        return True
    if src.sig >= 2 and _close(_round_sig(dst.v, src.sig), src.v):
        return True
    return False


def quals_in(text):
    return {k for k, rx in QUAL_RE.items() if rx.search(text)}


def plain(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)
    s = s.replace("`", "")
    return re.sub(r"\s+", " ", s).strip()


# Tags that only style words inside a line (glued). Every other inline tag (span, img, ...) is a boundary,
# because side-by-side spans are separate items (a gantt's labels, a row of KPI numbers).
TEXT_LEVEL_TAGS = {"strong", "em", "b", "i", "u", "s", "del", "ins", "code", "a", "tspan", "sup", "sub",
                   "mark", "kbd", "abbr", "q", "cite", "var", "time", "wbr"}


def html_blocks(frag):
    """Visible text of a fragment as blocks (one per block-level element; inline tags glue)."""
    s = re.sub(r"<!--.*?-->", " ", frag, flags=re.S)
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = BLOCK_TAG.sub("\n", s)
    s = re.sub(r"</?([a-zA-Z][\w-]*)\b[^>]*>",
               lambda m: "" if m.group(1).lower() in TEXT_LEVEL_TAGS else " ", s)
    out = []
    for ln in _html.unescape(s).split("\n"):
        t = re.sub(r"\s+", " ", ln).strip()
        if t:
            out.append(t)
    return out


@dataclass
class Item:
    kind: str                 # heading | prose | cell | quote | code | must | literal
    text: str
    where: str                # brief line, e.g. "L42"
    quals: frozenset = frozenset()
    raw: str = ""             # the brief's own text before a label was stripped (used for matching)


@dataclass
class Brief:
    path: str
    headings: list = field(default_factory=list)
    prose: list = field(default_factory=list)     # sentences (prose, list items, blockquotes)
    cells: list = field(default_factory=list)     # table body cells (row labels and values): HARD
    headers: list = field(default_factory=list)   # table header cells: REVIEW (charts and cards drop them)
    quotes: list = field(default_factory=list)    # quoted spans of 2+ words, blockquotes
    code: list = field(default_factory=list)      # Items, one per code line (6+ non-space chars)
    must: list = field(default_factory=list)      # must_include items (front matter or fenced block)
    literals: list = field(default_factory=list)  # dates, times, versions
    nums: list = field(default_factory=list)      # (Num, quals, where, in_table)
    global_quals: set = field(default_factory=set)
    lists: list = field(default_factory=list)     # the prose items of each list in the brief, one list per entry
    corpus_text: str = ""

    def all_copy_text(self):
        return " ".join((i.raw or i.text) for group in (self.headings, self.prose, self.cells, self.quotes)
                        for i in group)


def _front_matter(lines):
    """Returns (must, copy) from a YAML-ish front matter block; no YAML library needed."""
    must, copy, key = [], [], None
    for ln in lines:
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", ln)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if key == "must_include":
                if val.startswith("["):
                    must += [v.strip().strip("\"'") for v in val.strip("[]").split(",") if v.strip()]
                continue
            if key in ("title", "subtitle", "tagline") and val:
                copy.append(val.strip("\"'"))
            continue
        mi = re.match(r"^\s*-\s+(.*)$", ln)
        if mi and key == "must_include":
            must.append(mi.group(1).strip().strip("\"'"))
    return [m for m in must if m], [c for c in copy if c]


def parse_brief(raw, path="brief"):
    b = Brief(path=path)
    raw = raw.replace("\r\n", "\n")
    lines = raw.split("\n")
    if lines and lines[0].strip() == "---":
        end = next((k for k in range(1, len(lines)) if lines[k].strip() == "---"), None)
        if end is not None:
            must, copy = _front_matter(lines[1:end])
            for m in must:
                b.must.append(Item("must", m, "front matter"))
            for c in copy:
                b.must.append(Item("must", c, "front matter"))
            lines = [""] * (end + 1) + lines[end + 1:]
    # Keep verify markers; drop every other HTML comment (generator notes live there).
    body = re.sub(r"<!--(?!\s*verify:(?:ignore|resume)\s*-->)(.*?)-->", " ", "\n".join(lines), flags=re.S)
    lines = body.split("\n")

    ignore_marker = False
    ignore_head = None            # heading level of an ignored heading section
    in_code, fence, code_buf, code_at, fence_info = False, None, [], 0, ""
    para, para_at = [], 0
    para_is_item = False          # the paragraph being read is a list item
    cur_list = None               # the prose items of the list being read (None: not in a list)
    table_caption = frozenset()
    last_nonblank = ""
    in_table = False
    header_seen = False
    header_quals = frozenset()

    def flush_para():
        nonlocal para, para_is_item, cur_list
        if para:
            n0 = len(b.prose)
            text = plain(" ".join(para))
            for sent in sentences(text):
                _add_prose(b, sent, f"L{para_at}", False)
            if para_is_item:
                if cur_list is None:
                    cur_list = []
                    b.lists.append(cur_list)
                cur_list.extend(b.prose[n0:])
            para = []
        para_is_item = False

    for idx, ln in enumerate(lines, 1):
        if re.fullmatch(r"\s*<!--\s*verify:ignore\s*-->\s*", ln):
            flush_para(); ignore_marker = True; continue
        if re.fullmatch(r"\s*<!--\s*verify:resume\s*-->\s*", ln):
            ignore_marker = False; continue
        if in_code:
            if re.match(r"^\s*" + re.escape(fence) + r"\s*$", ln):
                in_code = False
                if not (ignore_marker or ignore_head):
                    for cl in code_buf:
                        if fence_info == "must_include":
                            if cl.strip():
                                b.must.append(Item("must", cl.strip().strip("-* ").strip("\"'"), f"L{code_at}"))
                            continue
                        compact = re.sub(r"\s+", "", cl)
                        if len(compact) >= 6:
                            b.code.append(Item("code", cl.rstrip(), f"L{code_at}"))
                code_buf = []
            else:
                code_buf.append(ln)
            continue
        fm = re.match(r"^\s*(```|~~~)\s*(\S*)", ln)
        if fm:
            flush_para(); in_code, fence, code_at = True, fm.group(1), idx
            fence_info = fm.group(2).lower()
            continue
        hm = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", ln)
        if hm:
            flush_para()
            level, title = len(hm.group(1)), plain(hm.group(2))
            if ignore_head is not None and level <= ignore_head:
                ignore_head = None
            if IGNORE_HEAD.match(title):
                ignore_head = level
                continue
            if ignore_marker or ignore_head is not None:
                continue
            cur_list = None
            text = NUM_PREFIX.sub("", title).strip()
            if text:
                b.headings.append(Item("heading", text, f"L{idx}"))
                for n in parse_nums(text):
                    b.nums.append((n, quals_in(text), f"L{idx}", False))
            continue
        if ignore_marker or ignore_head is not None:
            continue
        if ln.strip().startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue  # separator row
            flush_para()
            cur_list = None
            if not in_table:
                table_caption = frozenset(quals_in(last_nonblank))
                in_table = True
                header_seen = False
                header_quals = frozenset()
            is_header = not header_seen
            header_seen = True
            if is_header:
                header_quals = frozenset(quals_in(ln))
            row_quals = frozenset(quals_in(ln)) | table_caption | header_quals
            for c in cells:
                t = plain(c)
                if not t or re.fullmatch(r"[-–—\s]+", t):
                    continue
                if is_header:
                    b.headers.append(Item("header", t, f"L{idx}", row_quals))
                    continue
                b.cells.append(Item("cell", t, f"L{idx}", row_quals))
                for n in parse_nums(t):
                    b.nums.append((n, set(row_quals), f"L{idx}", True))
            last_nonblank = ln
            continue
        in_table = False
        if not ln.strip():
            flush_para(); last_nonblank = ""; continue
        bq = re.match(r"^\s*>\s?(.*)$", ln)
        lm = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$", ln)
        if bq:
            flush_para()
            text = plain(bq.group(1))
            if text:
                _add_prose(b, text, f"L{idx}", True)
            last_nonblank = ln
            continue
        hl = HEAD_LABEL.match(ln)
        if hl:
            flush_para()
            text = plain(hl.group(1))
            if text:
                b.headings.append(Item("heading", text, f"L{idx}"))
                for n in parse_nums(text):
                    b.nums.append((n, quals_in(text), f"L{idx}", False))
            last_nonblank = ln
            continue
        if lm:
            flush_para()
            para, para_at, para_is_item = [lm.group(1)], idx, True
        else:
            if para and LABEL_LINE.match(ln):
                flush_para()
            if not para:
                para_at = idx
                cur_list = None   # a paragraph that is not a list item ends the list
            para.append(ln.strip())
            # a short line with no closing punctuation is a label or a list-like line, not a wrapped sentence
            if len(ln.strip()) < 60 and not re.search(r"[.!?:;,\"”]$", ln.strip()):
                flush_para()
        last_nonblank = ln
    flush_para()

    _finish_quotes(b)
    seen = set()
    for it in b.prose + b.cells + b.headings + b.quotes:   # required literal forms (dates, times, versions)
        for m in LIT_RE.finditer(it.text):
            if (m.group(1), it.where) not in seen:
                seen.add((m.group(1), it.where))
                b.literals.append(Item("literal", m.group(1), it.where, it.quals))
    b.corpus_text = b.all_copy_text()
    return b


LABEL_STRIP = re.compile(r"^\s*(?:\*\*)?([A-Z][\w&'/.()-]*(?:\s[\w&'/.()-]+){0,3})(?:\*\*)?:\s+(?=\S)")


def _strip_label(text):
    """'Subtitle: Point-in-time ...' -> 'Point-in-time ...'. A short label is a caption the deliverable shows as
    a separate element, so only the value is checked as copy."""
    m = LABEL_STRIP.match(text)
    if m and len(tokens(text[m.end():])) >= 3:
        return text[m.end():]
    return text


def _add_prose(b, text, where, is_quote):
    text = text.strip()
    if not text:
        return
    raw = text
    if not is_quote:
        text = _strip_label(text)
    quals = frozenset(quals_in(text))
    if is_quote:
        b.quotes.append(Item("quote", text, where, quals))
    if not is_quote or len(tokens(text)) >= MIN_SENT_TOKENS:
        b.prose.append(Item("prose", text, where, quals, raw))
    if re.search(r"\b(all|every|each)\b[^.]{0,60}\b(numbers?|figures?|values?|metrics?|data|charts?|stats?)\b",
                 text, re.I):
        b.global_quals |= quals_in(text)
    for n in parse_nums(text):
        b.nums.append((n, set(quals), where, False))


def _finish_quotes(b):
    """Quoted spans of 2+ words in running copy are required verbatim (blockquotes already are)."""
    seen = {q.text for q in b.quotes}
    for it in b.prose:
        for m in QUOTE_RE.finditer(it.text):
            q = (m.group(1) or m.group(2) or "").strip()
            if len(q.split()) >= 2 and q not in seen:
                seen.add(q)
                b.quotes.append(Item("quote", q, it.where, it.quals))


# ---- deliverable side ------------------------------------------------------

@dataclass
class Unit:
    label: str
    blocks: list          # every visible block, code included (matching)
    prose: list           # visible blocks outside <pre> (sentence checks)
    text: str
    raw: str
    nums: list
    quals: set
    heads: list = field(default_factory=list)   # h1-h4 texts, for the invented-heading check


PRE_RE = re.compile(r"<pre\b.*?</pre>", re.S | re.I)
HEAD_RE = re.compile(r"<h([1-4])\b[^>]*>(.*?)</h\1>", re.S | re.I)


def build_units(pairs):
    """pairs: [(label, html_fragment)] from the front end -> [Unit]."""
    out = []
    for label, frag in pairs:
        blocks = html_blocks(frag)
        prose = html_blocks(PRE_RE.sub(" ", frag))
        joined = " ".join(blocks)
        heads = [NUM_PREFIX.sub("", " ".join(html_blocks(m.group(2)))).strip() for m in HEAD_RE.finditer(frag)]
        out.append(Unit(label, blocks, prose, norm(joined), typo(_html.unescape(joined)),
                        parse_nums(" ".join(prose)), quals_in(joined), [h for h in heads if h]))
    return out


def check(brief, units):
    hard, review = [], []
    all_text = " ".join(u.text for u in units)
    flat_nows_code = re.sub(r"\s+", "", " ".join(u.raw for u in units))
    dgrams_per_block = []
    dgrams = set()
    for u in units:
        for blk in u.blocks:
            dgrams_per_block.append(tokens(blk))
        # 5-grams across element boundaries too: a sentence split over two boxes is still carried
        dgrams |= grams(tokens(" ".join(u.blocks)))
    for toks in dgrams_per_block:
        dgrams |= grams(toks)
    bgrams = set()
    for it in brief.prose + brief.cells + brief.headings + brief.quotes:
        bgrams |= grams(tokens(it.raw or it.text))

    def has(text):
        """Whole-word containment of a brief string in the deliverable's copy (typography and case folded)."""
        return re.search(r"(?<!\w)" + re.escape(norm(text)) + r"(?!\w)", all_text) is not None

    # headings, cells, quotes, must_include, literals: whole-word match in the deliverable
    for it in brief.headings:
        if not has(it.text):
            hard.append(("missing heading", it.text, it.where))
    for it in brief.headers:
        if not has(it.text):
            review.append(("table header not shown (charts and cards often drop it)", it.text, it.where))
    for it in brief.cells:
        if has(it.text):
            continue
        nums = parse_nums(it.text)
        if nums and all(any(num_match(n, d) for u in units for d in u.nums) for n in nums):
            continue
        hard.append(("missing table cell", it.text, it.where))
    for it in brief.quotes:
        if len(it.text.split()) < 2:
            continue
        if not has(it.text):
            hard.append(("missing quoted line", it.text, it.where))
    for it in brief.must:
        if not has(it.text):
            hard.append(("missing must_include item", it.text, it.where))
    for it in brief.literals:
        if not has(it.text):
            hard.append(("missing literal (date, time or version)", it.text, it.where))
    for it in brief.code:
        if re.sub(r"\s+", "", it.text) not in flat_nows_code:
            hard.append(("code line not verbatim", it.text.strip(), it.where))

    # numbers and their qualifiers
    seen_num = set()
    for n, quals, where, in_table in brief.nums:
        key = (n.v, n.sig, n.pct, where)
        if key in seen_num:
            continue
        seen_num.add(key)
        hits = [u for u in units if any(num_match(n, d) for d in u.nums)]
        if not hits:
            if n.sig <= 1 and not in_table and not n.pct:
                review.append(("single-digit figure missing", n.text, where))
            else:
                hard.append(("missing number", n.text, where))
            continue
        if quals and not any(q in u.quals for u in hits for q in quals):
            hard.append((f"qualifier ({'/'.join(sorted(quals))}) dropped from a figure", n.text, where))
    if brief.global_quals and not any(q in u.quals for u in units for q in brief.global_quals):
        hard.append((f"qualifier ({'/'.join(sorted(brief.global_quals))}) for all figures appears nowhere",
                     "all figures", "brief"))

    # REVIEW: brief sentences not carried over (dropped or reworded). Labels (no closing full stop:
    # diagram labels, "Key: value" lines) are split across boxes in a deck, so they are checked word by word.
    dwords = set()
    for toks in dgrams_per_block:
        dwords |= set(toks)
    # the brief's own sentences and the copy, as one normalised string each: a sentence found word for word is carried (#34)
    bverb = norm(" ".join(it.text for it in brief.prose + brief.cells + brief.headings + brief.quotes))
    for it in brief.prose:
        toks = tokens(it.text)
        if len(toks) < MIN_SENT_TOKENS:
            continue
        if has(it.text):
            continue
        if not re.search(r"[.!?][\"”']?$", it.text.strip()):
            missing = [t for t in toks if t not in dwords and t != "\u2014"]
            if not missing:
                continue
            share = 1 - len(missing) / len([t for t in toks if t != "\u2014"])
            kind = "label partly carried" if share >= 0.6 else "label not carried"
            review.append((f"{kind} (words not found: {' '.join(missing[:8])})", it.text, it.where))
            continue
        g = grams(toks)
        carried = len(g & dgrams)
        if carried == 0:
            review.append(("source sentence not carried (dropped or rewritten)", it.text, it.where))
        elif carried < len(g):
            review.append((f"source sentence partly carried ({carried}/{len(g)} 5-grams, reworded)", it.text, it.where))

    # HARD: a whole list of the brief that reached the deliverable with none of its items (the round-3 and
    # round-4 docs sites dropped the brief's "Key points" list; each item alone is only a REVIEW, so it passed)
    def carried(it):
        toks = tokens(it.text)
        if not re.search(r"[.!?][\"”']?$", it.text.strip()):
            words = [t for t in toks if t != "\u2014"]
            return bool(words) and sum(t in dwords for t in words) / len(words) >= 0.6
        return bool(grams(toks) & dgrams)
    for group in brief.lists:
        items = [it for it in group if len(tokens(it.text)) >= MIN_SENT_TOKENS]
        if len(items) >= 2 and not any(carried(it) for it in items):
            hard.append((f"list dropped (none of its {len(items)} items is in the deliverable)", items[0].text,
                         items[0].where))

    # REVIEW: deliverable headings with a word the brief never uses (invented headings)
    bwords = set()
    for it in brief.prose + brief.cells + brief.headings + brief.quotes + brief.headers:
        bwords |= set(tokens(it.raw or it.text))
    bnorm = norm(brief.corpus_text)
    for u in units:
        for h in u.heads:
            toks = [t for t in tokens(h) if t != "\u2014"]
            in_brief = re.search(r"(?<!\w)" + re.escape(norm(h)) + r"(?!\w)", bnorm) is not None
            if norm(h) in STRUCTURAL_HEADS:
                continue
            if toks and not in_brief and any(t not in bwords for t in toks):
                review.append(("deliverable heading not in the brief (invented?)", h, u.label))

    # REVIEW: deliverable sentences that share no 5-gram with the brief (invented copy)
    for u in units:
        for blk in u.prose:
            if BOILERPLATE.search(blk):
                continue
            for sent in sentences(blk):
                toks = tokens(sent)
                if len(toks) < MIN_SENT_TOKENS or sum(t.isalpha() for t in toks) < MIN_SENT_TOKENS:
                    continue  # too short, or figures only (a gantt's month row)
                g = grams(toks)
                if g and not (g & bgrams) and norm(sent) not in bverb:
                    review.append(("deliverable sentence with no 5-gram in the brief (invented?)", sent, u.label))
        # REVIEW: figures in the deliverable prose that the brief does not contain
    for u in units:
        for blk in u.prose:
            if BOILERPLATE.search(blk) or len(tokens(blk)) < MIN_SENT_TOKENS:
                continue
            for d in parse_nums(blk):
                if d.sig < 2 and not d.pct:
                    continue
                if not any(num_match(n, d) for n, *_ in brief.nums):
                    review.append(("figure in the deliverable not in the brief", d.text, u.label))
    return hard, review


# ==== COMPARE (--compare BEFORE AFTER): two copies as multisets of words and links (#33) ====

def _md_text(raw):
    """A markdown source as plain copy: (text, links). Front matter, generator comments, fences, heading, list and
    table markup go; the words of every line and each [text](url) link's target are kept."""
    raw = raw.replace("\r\n", "\n")
    raw = re.sub(r"\A---\n.*?\n---\n", "", raw, count=1, flags=re.S)
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    raw = re.sub(r"!\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) + " ", raw)
    links = []

    def take(m):
        links.append(m.group(2))
        return m.group(1)
    raw = re.sub(r"\[([^\]]+)\]\(([^)\s]*)[^)]*\)", take, raw)
    out = []
    for ln in raw.split("\n"):
        if ln.strip().startswith(("```", "~~~")) or re.fullmatch(r"\s*\|?[\s:|-]*-[\s:|-]*\|?\s*", ln):
            continue
        ln = re.sub(r"^\s{0,3}#{1,6}\s+", "", ln)
        ln = re.sub(r"^\s*>\s?", "", ln)
        ln = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", ln)
        out.append(plain(ln.replace("|", " ")))
    return "\n".join(out), links


def _tally(c):
    return ", ".join(f"{w} x{n}" if n > 1 else w for w, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:120])


def labels_of(arg):
    """(title, toolbar label) of a folder's index.html, or None for a file. Reported on their own line by --compare:
    a rebuild that changes the title or the label is shown, not counted as a change in the words."""
    folder = Path(arg)
    page = folder / "index.html"
    if not folder.is_dir() or not page.is_file():
        return None
    text = page.read_text(encoding="utf-8", errors="replace")
    title = re.search(r"<title>([^<]*)</title>", text)
    label = (re.search(r'id="brandSite">([^<]*)<', text)
             or re.search(r'<div class="brand">(?:(?!</div>).)*?alt="[^"]*">([^<]*)</div>', text, re.S))
    return (title.group(1).strip() if title else None, label.group(1).strip() if label else None)


def compare(before, after):
    """Exit 0 when the two copies have the same words, links, title and toolbar label; 1 with the difference listed (a title or label that differs too), 2 when one cannot be read."""
    try:
        bt, bl = copy_of(before)
        at, al = copy_of(after)
    except (SystemExit, OSError, ValueError, KeyError) as e:
        print(e, file=sys.stderr)
        return 2
    bw, aw = Counter(tokens(bt)), Counter(tokens(at))
    bL, aL = Counter(bl), Counter(al)
    miss, extra, lmiss, lextra = bw - aw, aw - bw, bL - aL, aL - bL
    print("verify_content --compare")
    print(f"  before: {before} ({sum(bw.values())} words, {sum(bL.values())} links)")
    print(f"  after:  {after} ({sum(aw.values())} words, {sum(aL.values())} links)")
    lb, la = labels_of(before), labels_of(after)
    labels_differ = lb is not None and la is not None and lb != la
    if lb is not None and la is not None:
        if not labels_differ:
            print("  labels: title and toolbar label the same in both copies")
        else:
            print(f"  labels differ: title {lb[0]!r} -> {la[0]!r}; toolbar label {lb[1]!r} -> {la[1]!r}")
    if not (miss or extra or lmiss or lextra or labels_differ):
        print("\nidentical: the same words and links in both copies (exit 0)")
        return 0
    print(f"\nDIFFERENT: {sum(miss.values())} word(s) missing from after, {sum(extra.values())} added in after, "
          f"{sum(lmiss.values())} link(s) missing, {sum(lextra.values())} added"
          + ("; the title or toolbar label differs" if labels_differ else "") + " (exit 1)")
    if miss:
        print(f"  missing from after: {_tally(miss)}")
    if extra:
        print(f"  added in after:     {_tally(extra)}")
    if lmiss:
        print("  links missing from after: " + ", ".join(sorted(lmiss.elements())))
    if lextra:
        print("  links added in after:     " + ", ".join(sorted(lextra.elements())))
    return 1


BRIEF_NAME = "brief.md"


def _copy_text(path):
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def brief_for(root, source=None):
    """The user's copy that the copy gates check `root` against: (path or None, problem or None).

    The deliverable's own brief.md is the default and the copy the deliverable is checked against. A brief kept
    elsewhere may belong to another deliverable or be a stale copy, and a pass against it proves nothing here. An
    explicit --source is accepted only when it is that same copy (same text; line endings do not count).
    No brief.md and no --source gives (None, None): there is no user copy to check against.
    """
    own = Path(root) / BRIEF_NAME
    if source is None:
        return (own if own.is_file() else None), None
    src = Path(source)
    if not own.is_file():
        return None, (f"no {BRIEF_NAME} in {root}: save the user's copy as {BRIEF_NAME}, unchanged "
                      f"(cp <their file> {BRIEF_NAME}). --source {source} is not the deliverable's copy.")
    if not src.is_file():
        return None, f"cannot read {source}"
    if src.resolve() == own.resolve():
        return own, None
    if _copy_text(src) != _copy_text(own):
        return None, (f"--source {source} differs from {own}: the deliverable's {BRIEF_NAME} is the copy it is "
                      f"checked against. Copy the user's file over it (cp {source} {own}), or drop --source.")
    return own, None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Copy-fidelity gate: deliverable copy vs. the user's brief.")
    ap.add_argument("root", nargs="?", help="deliverable folder (default: auto-detect)")
    ap.add_argument("--source", type=Path, help=f"the user's brief (default: the deliverable's {BRIEF_NAME}; "
                                                "an explicit file must have the same text)")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                    help="compare two copies (site folders, .json inventories or .md files) by their words and links; "
                         "use it when rebuilding a deliverable (exit 0 identical, 1 different)")
    args = ap.parse_args(argv)
    if args.compare:
        return compare(*args.compare)
    try:
        root = find_root(args.root)
        pairs = front_units(root)
    except (SystemExit, OSError) as e:
        print(e, file=sys.stderr)
        return 2
    source, problem = brief_for(root, args.source)
    if source is None and problem is None:
        problem = (f"no {BRIEF_NAME} in {root}: save the user's copy as {BRIEF_NAME}, unchanged "
                   f"(cp <their file> {BRIEF_NAME}). The copy gate checks the deliverable against that file only.")
    if problem:
        print(problem, file=sys.stderr)
        return 2
    try:
        raw = source.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(e, file=sys.stderr)
        return 2
    brief = parse_brief(raw, str(source))
    units = build_units(pairs)
    hard, review = check(brief, units)

    n_req = (len(brief.headings) + len(brief.cells) + len(brief.quotes) + len(brief.must)
             + len(brief.code) + len(brief.literals) + len(brief.nums))
    print(f"verify_content: {root}")
    print(f"  brief: {source}  units: {len(units)}  required items: {n_req} "
          f"(headings {len(brief.headings)}, cells {len(brief.cells)}, quotes {len(brief.quotes)}, "
          f"must_include {len(brief.must)}, code lines {len(brief.code)}, figures {len(brief.nums)})")
    if hard:
        print(f"\n=== HARD ({len(hard)}): copy from the brief is missing or changed ===")
        for kind, text, where in hard:
            print(f"  [{kind}] {text[:140]}  ({where})")
    if review:
        kinds = {}
        for kind, _, _ in review:
            key = re.sub(r" \(.*", "", kind)
            kinds[key] = kinds.get(key, 0) + 1
        print(f"\n=== REVIEW ({len(review)}): show these to the user ===")
        print("  by kind: " + "; ".join(f"{n} {k}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])))
        for kind, text, where in review:
            print(f"  [{kind}] {text[:160]}  ({where})")
    print(f"\nverify_content: {len(hard)} hard, {len(review)} review. "
          "Never edit the user's copy to pass; fix HARD, and report every REVIEW item.")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
