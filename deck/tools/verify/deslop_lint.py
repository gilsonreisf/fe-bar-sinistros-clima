#!/usr/bin/env python3
"""De-slop / brand-voice lint for a dbx-slides deck.

Ported from the databricks-corporate-slides skill. The HARD/REVIEW rule tables
are verbatim (they are architecture-independent regex tables); only the front
end changed — instead of regexing <section>s out of one .html file, it reads the
active slides from slides/manifest.js and pulls each DECK.slide(`...`) body via
decksrc.py. See that module for the extraction.

It flags the AI "tells" that make a deck read as machine-generated or off-brand,
using only slide-VISIBLE copy (speaker notes and HTML comments are stripped).
Exits non-zero if any HARD tell is present, so it can gate a build.

    python3 deslop_lint.py --source brief.md [DECK_DIR]
    python3 deslop_lint.py [DECK_DIR]     # DECK_DIR defaults to the deck it lives in

HARD tells are mechanical and should always be fixed. REVIEW tells are judgment
calls (reported, never blocking). A hyphen in a number range (6-7x, Feb-May) is
NOT an em dash and is not flagged.

The user's copy is the deliverable's own brief.md by default. An explicit --source must have the same
text as that brief.md (exit 2 otherwise): a brief of another deliverable would downgrade this one's agent
sentences to REVIEW.

--source BRIEF: a HARD tell inside a sentence that the user's brief already contains is user copy.
It becomes REVIEW ("keep, do not rewrite"), so a lint can never be satisfied by editing the user's words.
Agent-written text stays HARD. The test is the sentence around the match: at least 80% of its 5-grams
appear in the brief (sentences under 4 words must match the brief exactly).

Exit codes: 0 clean or review-only | 1 a HARD tell is present | 2 could not read, or --source is not
the deliverable's brief.md.
"""
from __future__ import annotations

import argparse
import html as _html
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decksrc  # noqa: E402
import verify_content as vc  # noqa: E402  (brief parsing and matching, shared with the copy gate)

HARD = {
    "em dash": re.compile(r"—|&mdash;"),
    # Covers the emoji blocks (supplementary pictographs 1F000-1FAFF incl. flags,
    # misc technical 2300-23FF like ⏱⌚⏰, misc symbols 2600-26FF, dingbats
    # 2700-27BF, misc symbols & arrows 2B00-2BFF like ⭐). Deliberately EXCLUDES
    # the functional glyphs the template uses as real UI and are not emoji: the
    # check/cross dingbats U+2713-2718 (✓✔✕✖✗✘), arrows U+2190-21FF (↑→↻), and
    # geometric shapes U+25A0-25FF (▶▲▼) — none of which are in the ranges below.
    "emoji (brand uses none, ever)": re.compile(
        "[\U0001F000-\U0001FAFF"
        "\U00002300-\U000023FF\U00002600-\U000026FF"
        "\U00002700-\U00002712\U00002719-\U000027BF\U00002B00-\U00002BFF]️?"),
    "forbidden filler": re.compile(
        r"\b(unlock(?:s|ed|ing)?|leverag(?:e|es|ed|ing)|delv(?:e|es|ed|ing)|game[- ]?changers?|"
        r"revolutionary|next-?generation|best-in-class|seamless(?:ly)?|synerg\w*|cutting-edge|"
        r"turnkey)\b", re.I),
    "leftover template scaffolding": re.compile(
        r"PATTERN:|={6,}|Your (title|subtitle|content)\b|goes here|Lorem ipsum|"
        r"swap only the text|Replace this|\[\[.*?\]\]|"
        # dbx-slides template defaults that must be swapped before shipping
        r"A single headline claim|Section Title\b|\bAuthor Name\b|"
        r"Your content goes here|"
        # the official corporate layouts' own placeholder lines (off-*.js), kept so the layouts match the template
        r"This spot is great for|Your visual here|Default bulleted list style|Table Header \d|\bYour Name\b|"
        r"you@databricks\.com", re.I),
}
REVIEW = {
    "slogan-fat": re.compile(
        r"the whole game|that.?s the door|that.?s it\b|changes everything|"
        r"the \w+ that grows|not your grandfather", re.I),
    "empty intensifier": re.compile(r"\b(really|simply|actually|literally|genuinely)\b", re.I),
    "significance inflation": re.compile(
        r"\b(transformative|paradigm shift|pivotal|groundbreaking|supercharge)\b", re.I),
}



REVIEW_EM_DASH = re.compile(r"—|&mdash;")
SUBLIKE = re.compile(r"sub|eyebrow|kicker|lede|deck-line", re.I)


def repeated_subtitles(body: str) -> list[str]:
    """Subtitles or eyebrows (a class with sub/eyebrow/kicker/lede) whose text repeats a heading on the same slide.
    A sample subtitle copied from the title is a template flaw: the slide says the same thing twice."""
    import html as _html
    def norm(t):
        t = _html.unescape(re.sub(r"<[^>]+>", " ", t))
        return re.sub(r"\s+", " ", t).strip().casefold().rstrip(".:")
    heads = {norm(m) for m in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", body, re.S)} - {""}
    out = []
    for m in re.finditer(r'<(p|div|span|small|h[4-6])\b[^>]*class="([^"]*)"[^>]*>(.*?)</\1>', body, re.S):
        if SUBLIKE.search(m.group(2)) and norm(m.group(3)) in heads:
            out.append(norm(m.group(3)))
    return out


_H3 = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.S | re.I)
_SVG_TEXT = re.compile(r"<text\b[^>]*>.*?</text>", re.S | re.I)


def h3_titles(body: str) -> set[str]:
    """The h3 card titles of a slide (#36): a short heading on a card is a label, not a sentence, so it takes no period rule."""
    out = set()
    for raw in _H3.findall(decksrc.strip_notes(re.sub(r"<!--.*?-->", " ", body, flags=re.S))):
        t = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()
        if t:
            out.add(t)
    return out


# A block boundary (paragraph, list item, cell, heading, SVG label...) in the visible text. visible_text() runs a
# section into one line, so a step title, a heading or a diagram label ran into the text beside it and the sentence
# around a tell no longer matched the brief: the user's own em dashes stayed HARD (round-4 comparison, all three
# skills). The mark is not whitespace, so it survives the collapse; a sentence never crosses it.
BLOCK = "\u241e"
_BLOCK_TAG = re.compile(r"</?(?:p|li|h[1-6]|div|td|th|tr|caption|figcaption|pre|blockquote|section|ul|ol|dt|dd|"
                        r"table|thead|tbody|text|br|hr)\b[^>]*>", re.I)


def _mark_blocks(fragment: str) -> str:
    # Speaker notes go first: marking turns the notes <div> into a block mark, so visible_text() could no longer
    # find the note and the notes were linted as slide copy (false HARD em dashes in every deck with notes).
    fragment = decksrc.strip_notes(re.sub(r"<!--.*?-->", " ", fragment, flags=re.S))
    return _BLOCK_TAG.sub(" " + BLOCK + " ", fragment)


def _sentence_at(text: str, pos: int) -> str:
    """The sentence of `text` that contains character `pos`, within its block."""
    left = max(text.rfind(c, 0, pos) for c in ".!?" + BLOCK) + 1
    ends = [i for i in (text.find(c, pos) for c in ".!?" + BLOCK) if i != -1]
    end = min(ends) if ends else len(text)
    if end < len(text) and text[end] != BLOCK:
        end += 1
    return text[left:end].replace(BLOCK, " ").strip()


def _user_text(sent: str) -> str:
    """A sentence as the brief would hold it: a leading number ("2", "2.", "2 —", "§2") is numbering, and the
    brief's headings lose it too (verify_content.parse_brief), so it is dropped before any match."""
    return vc.NUM_PREFIX.sub("", sent, count=1).strip()


def _is_user_copy(text: str, pos: int, brief) -> bool:
    """True when the sentence around `pos` is (mostly) the user's own copy from the brief."""
    sent = _user_text(_sentence_at(text, pos))
    toks = vc.tokens(sent)
    if len(toks) < 4:
        return vc.norm(sent) in brief.norm
    g = vc.grams(toks)
    if not g:                      # too short for a 5-gram (a label split over two lines): verbatim in the brief
        return vc.norm(sent) in brief.norm
    return len(g & brief.grams) / len(g) >= 0.8


def main() -> int:
    ap = argparse.ArgumentParser(description="Flag AI slop / off-brand tells in a dbx-slides deck.")
    ap.add_argument("deck", nargs="?", help="deck folder (default: auto-detect)")
    ap.add_argument("--source", type=Path, help="the user's brief: tells inside its copy become REVIEW")
    args = ap.parse_args()
    try:
        deck = decksrc.find_deck(args.deck)
        entries = decksrc.slide_entries(deck)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    # The deliverable's own brief.md is the user's copy: the default, so the lint can't fail the user's words just
    # because the flag was left out (the round-4 generators ran it bare). An explicit --source must be that same
    # copy: a brief of another deliverable would turn this deliverable's agent sentences into REVIEW.
    source, problem = vc.brief_for(deck, args.source)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    if source is not None and args.source is None:
        print(f"deslop: using {source} as the user's copy", file=sys.stderr)
    brief = None
    if source:
        try:
            brief = vc.parse_brief(source.read_text(encoding="utf-8", errors="replace"), str(source))
        except OSError as e:
            print(e, file=sys.stderr)
            return 2
        brief.norm = vc.norm(brief.corpus_text)
        brief.grams = set().union(*(vc.grams(vc.tokens(i.text)) for i in
                                    brief.prose + brief.cells + brief.headings + brief.quotes), set())

    findings: list[tuple[str, str, str, str]] = []  # (severity, label, tell, snippet)
    titles: list[tuple[str, str]] = []              # (label, title text)

    card_titles: set[tuple[str, str]] = set()     # (label, text) of every h3 card title (#36)
    for fn, body in entries:
        card_titles |= {(fn, t) for t in h3_titles(body)}
        for t in decksrc.headings(body):
            titles.append((fn, t))
        for rep in repeated_subtitles(body):
            findings.append(("HARD", fn, "subtitle repeats the title", rep[:80]))
        # An em dash inside an SVG <text> label is a REVIEW, not a HARD tell (#36): the label is a diagram
        # annotation the author can set in a dash-free form; the em-dash rule still runs on every other copy.
        text = decksrc.visible_text(_mark_blocks(body))
        # the diagram labels, on their own: their em dashes are REVIEW (#36); every other tell still reads them
        labels = decksrc.visible_text(_mark_blocks(" ".join(_SVG_TEXT.findall(body))))
        dashes_in_labels = list(REVIEW_EM_DASH.finditer(labels))
        if dashes_in_labels:
            findings.append(("REVIEW", fn, "em dash in a diagram label (review, not hard)", dashes_in_labels[0].group(0)))
        # HARD em dashes read the copy outside the diagram labels; the text they are judged in is the same string
        copy_text = decksrc.visible_text(_mark_blocks(_SVG_TEXT.sub(" ", body)))
        for sev, table in (("HARD", HARD), ("REVIEW", REVIEW)):
            for tell, rx in table.items():
                scan = copy_text if tell == "em dash" else text
                hits = list(rx.finditer(scan))
                if not hits:
                    continue
                if sev == "HARD" and brief is not None:
                    agent = [h for h in hits if not _is_user_copy(scan, h.start(), brief)]
                    kept = len(hits) - len(agent)
                    if agent:
                        findings.append(("HARD", fn, tell, agent[0].group(0)))
                    if kept:
                        findings.append(("REVIEW", fn, f"user copy, keep (report, do not rewrite): {tell}",
                                         f"{kept} match(es) in the brief's own sentences"))
                    if not agent:
                        continue
                else:
                    findings.append((sev, fn, tell, hits[0].group(0)))

    # title-level tells
    for label, t in titles:
        if re.search(r",\s+not\b|\bisn.?t\b|\baren.?t\b|\bnot just\b", t, re.I):
            findings.append(("REVIEW", label, "X-not-Y title reflex", t))
        # Curt period on a short title is an AI tell. Exclude a trailing ellipsis
        # (a stylistic trailing-off, not a period) and abbreviation endings where
        # the period belongs to the word (all-caps token like AWS/ML, or Inc./Ltd.).
        words = t.split()
        if ((label, t) not in card_titles and t.endswith(".") and not t.endswith("...") and not t.endswith("…")
                and len(words) <= 4):
            last = words[-1].rstrip(".")
            if not (last.isupper() or last.lower() in
                    {"inc", "ltd", "co", "corp", "dept", "st", "ave", "etc", "vs"}):
                if brief is not None and vc.norm(_user_text(t)) in brief.norm:
                    findings.append(("REVIEW", label, "user copy, keep (report, do not rewrite): period on short title", t))
                else:
                    findings.append(("HARD", label, "period on short title", t))

    motif = 0
    leads: Counter[str] = Counter()
    for _, t in titles:
        clean = re.sub(r"[^\w. ]", "", t).strip()
        if re.match(r"^\w+( \w+)?\.\s+\w+( \w+)?\.?$", clean):
            motif += 1
        words = clean.split()
        if words:
            leads[words[0].lower()] += 1
    if motif >= 2:
        findings.append(("REVIEW", "(deck)", "repeated motif", f'{motif} titles use the "One X. One Y." shape'))
    for w, c in leads.items():
        if c >= 3:
            findings.append(("REVIEW", "(deck)", "repeated lead word", f'{c} titles start with "{w}"'))

    n = len(entries)
    if not findings:
        print(f"deslop: clean - no slop tells found across {n} slides")
        return 0

    hard = [f for f in findings if f[0] == "HARD"]
    for sev in ("HARD", "REVIEW"):
        rows = [f for f in findings if f[0] == sev]
        if rows:
            print(f"\n=== {sev} ({len(rows)}) ===")
            for _, label, tell, snippet in rows:
                print(f"[{label}] {tell}: {snippet[:80]}")
    print(f"\ndeslop: {len(hard)} hard, {len(findings) - len(hard)} review across {n} slides. "
          "Fix every HARD; review the rest (rewrites are judgment calls).")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
