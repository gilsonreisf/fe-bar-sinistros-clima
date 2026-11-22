#!/usr/bin/env python3
"""Migrate a deliverable's SVG arrows to the arrow contract (commit 4ef9809): a deck, a document or a docs site built
before it has markers whose refX equals the path tip and lines that end on the box border. audit_layout.py's arrow
checks (arrow-stroke-shows, arrow-tip-off-border) report every such arrow.

For each <marker> in the content files: refX = tip - 1.5 (the tip is the largest x of its path) and
orient="auto-start-reverse". For each arrow (a line or polyline with marker-end or marker-start, on the element or
inherited from an enclosing <g>): the line end is pulled back 1.5 stroke widths from the box it points at, so the tip
lands on the outer border (the box's edge, plus half its own stroke outside it). An arrow with no box within 20 units
keeps its tip where it was.

Only marker tags and line end points change. Every text node and every other attribute is left as it is.

    python3 tools/verify/migrate_markers.py <deliverable>           # dry run: the report, nothing written
    python3 tools/verify/migrate_markers.py <deliverable> --write   # apply

<deliverable> is a copy of a template (a deck, a document or a docs site), never a skill's template/. The scanned
files are the content folders (slides/, sections/, pages/). Idempotent: a second --write changes nothing. After
--write, rebuild the one-file share copy (dbx-docsites: tools/build_standalone.py) and run the deliverable's gates.
Exit 0 (done, or nothing to do), 2 (not a deliverable). The same code is in all three content skills (a parity test
keeps it so).
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

CONTENT = ("slides", "sections", "pages")
SUFFIXES = {".js", ".html", ".htm"}
SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)
MARKER_RE = re.compile(r"<marker\b([^>]*)>(.*?)</marker>", re.S)
TAG_RE = re.compile(r"<(/?)([A-Za-z][\w:-]*)\b([^>]*?)(/?)>")
REACH = 1.5          # the arrow tip sits 1.5 stroke widths past the line end
LIMIT = 20.0         # a ray with no box within this many units keeps its tip
ENDS = ("marker-end", "marker-start")


def attr(text: str, name: str, default=None):
    """An attribute of a tag's attribute text, or a CSS property of its style attribute."""
    m = re.search(r'(?<![\w-])%s="([^"]*)"' % re.escape(name), text)
    if m:
        return m.group(1)
    m = re.search(r'style="([^"]*)"', text)
    if m:
        s = re.search(r"(?:^|;)\s*%s\s*:\s*([^;]+)" % re.escape(name), m.group(1))
        if s:
            return s.group(1).strip()
    return default


def num(v, d=0.0):
    try:
        return float(str(v).replace("px", ""))
    except (TypeError, ValueError):
        return d


def css_rules(text: str):
    """(classes, body) for each rule whose last compound selector is made of classes (.content .lane .sw-flow gives
    {sw-flow}). The audit reads computed styles, so a stroke width set in the stylesheet counts."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    rules = []
    for sels, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        for sel in sels.split(","):
            parts = re.split(r"[\s>+~]+", sel.strip())
            classes = frozenset(re.findall(r"\.([\w-]+)", parts[-1])) if parts and parts[-1] else frozenset()
            if classes:
                rules.append((classes, body))
    return rules


def class_prop(rules, classes, prop: str):
    """The value the stylesheet gives prop to an element with these classes (the last matching rule wins)."""
    val = None
    for need, body in rules:
        if need <= classes:
            m = re.search(r"(?:^|;)\s*%s\s*:\s*([^;]+)" % re.escape(prop), body)
            if m:
                val = m.group(1).strip()
    return val


def own_stroke_width(a: str, rules):
    """The stroke width an element sets itself: its style, then its classes' rules, then its attribute (None when it
    sets none, so it inherits from its <g>)."""
    st = re.search(r'style="([^"]*)"', a)
    if st:
        s = re.search(r"(?:^|;)\s*stroke-width\s*:\s*([\d.]+)", st.group(1))
        if s:
            return num(s.group(1))
    cm = re.search(r'class="([^"]*)"', a)
    c = class_prop(rules, frozenset(cm.group(1).split()) if cm else frozenset(), "stroke-width")
    if c:
        return num(c)
    v = re.search(r'(?<![\w-])stroke-width="([^"]*)"', a)
    return num(v.group(1)) if v else None


def set_attr(text: str, name: str, value: str) -> str:
    """The attribute text with name set (added when absent)."""
    if re.search(r'(?<![\w-])%s="[^"]*"' % re.escape(name), text):
        return re.sub(r'(?<![\w-])%s="[^"]*"' % re.escape(name), '%s="%s"' % (name, value), text, count=1)
    return text + ' %s="%s"' % (name, value)


def marker_tip(body: str) -> float:
    """The largest x a marker's path reaches (M and L absolute, l relative), 7 when there is no path."""
    m = re.search(r'<path\b[^>]*\bd="([^"]*)"', body)
    if not m:
        return 7.0
    toks = re.findall(r"[MLlzZ]|-?[\d.]+", m.group(1))
    x = maxx = 0.0
    cmd, i = "M", 0
    while i < len(toks):
        t = toks[i]
        if re.fullmatch(r"[MLlzZ]", t):
            cmd, i = t, i + 1
            continue
        px = float(toks[i])
        i += 2
        x = px if cmd in "ML" else x + px
        maxx = max(maxx, x)
    return maxx


def ray_boxes(P, u, rects):
    """Every box the ray from P along u enters from outside: (tmin, tmax, rect, cos of the entry face)."""
    out = []
    for R in rects:
        x0, y0, x1, y1 = R[0], R[1], R[0] + R[2], R[1] + R[3]
        if x0 <= P[0] <= x1 and y0 <= P[1] <= y1:
            continue
        tmin, tmax = -math.inf, math.inf
        ax_enter = None
        for ax, (p0, d, lo, hi) in enumerate(((P[0], u[0], x0, x1), (P[1], u[1], y0, y1))):
            if abs(d) < 1e-12:
                if not lo <= p0 <= hi:
                    tmin, tmax = 1, 0
            else:
                t1, t2 = sorted(((lo - p0) / d, (hi - p0) / d))
                if t1 > tmin:
                    tmin, ax_enter = t1, ax
                tmax = min(tmax, t2)
        if tmin <= tmax and tmin >= 0 and ax_enter is not None:
            out.append((tmin, tmax, R, abs(u[ax_enter])))
    return out


def pick_box(P, u, rects, L_seg):
    """The box an arrow points at, from its ray P + t*u with its tip at t = L_seg:
    1. a box whose entry face the tip is on (within 3 units): the nearest such face. A tip already on the outer border
       sits half a box stroke short of the face, so the window covers that: a second run finds the same box;
    2. else the nearest box the ray enters beyond the tip, within LIMIT (the tip is short of it);
    3. else the box the tip has entered and not left (an arrow that overshoots into its box).
    A container the arrow only crosses on the way is none of these. Returns (t of the face, rect, cos) or None."""
    es = ray_boxes(P, u, rects)
    face = [e for e in es if abs(e[0] - L_seg) <= 3.0]
    if face:
        e = min(face, key=lambda e: abs(e[0] - L_seg))
    else:
        fwd = [e for e in es if L_seg + 3.0 < e[0] <= L_seg + LIMIT]
        if fwd:
            e = min(fwd, key=lambda e: e[0])
        else:
            inside = [e for e in es if e[0] < L_seg - 3.0 and e[1] > L_seg]
            if not inside:
                return None
            e = max(inside, key=lambda e: e[0])
    return e[0], e[2], e[3]


def line_points(tag: str, name: str):
    """The points of a line (x1 y1 x2 y2) or a polyline (points), as a list of [x, y] pairs."""
    if name == "line":
        return [[num(attr(tag, "x1")), num(attr(tag, "y1"))], [num(attr(tag, "x2")), num(attr(tag, "y2"))]]
    return [[float(a) for a in q.split(",")] for q in attr(tag, "points").split()]


def with_points(tag: str, name: str, pts) -> str:
    if name == "line":
        tag = set_attr(tag, "x1", "%g" % pts[0][0])
        tag = set_attr(tag, "y1", "%g" % pts[0][1])
        tag = set_attr(tag, "x2", "%g" % pts[1][0])
        return set_attr(tag, "y2", "%g" % pts[1][1])
    return set_attr(tag, "points", " ".join("%g,%g" % (x, y) for x, y in pts))


def arrow_fix(tag: str, name: str, which: str, mid: str, reach_old: float, rects, log: list, sw: float) -> str:
    """One end of a line: pull the vertex back 1.5 stroke widths from the tip, the tip on the box it points at. sw is
    the line's stroke width, its own or inherited from its <g>."""
    pts = line_points(tag, name)
    if which == "marker-end":
        P, V = pts[-2], pts[-1]
    else:                                        # marker-start: the tip is the first point, the ray runs back
        P, V = pts[1], pts[0]
    L = math.hypot(V[0] - P[0], V[1] - P[1])
    if L == 0:
        return tag
    u = ((V[0] - P[0]) / L, (V[1] - P[1]) / L)
    T_pt = (V[0] + reach_old * sw * u[0], V[1] + reach_old * sw * u[1])
    L_seg = math.hypot(T_pt[0] - P[0], T_pt[1] - P[1])
    hit = pick_box(P, u, rects, L_seg)
    if hit:
        t, (rx, ry, rw, rh, bsw), cos = hit
        E = (P[0] + t * u[0], P[1] + t * u[1])
        back = (bsw / 2) / max(cos, 1e-9)        # along the ray, so the normal distance to the face is bsw / 2
        tip = (E[0] - back * u[0], E[1] - back * u[1])
        kind = "box"
    else:
        tip = T_pt
        kind = "free"
    nV = (round(tip[0] - REACH * sw * u[0], 2), round(tip[1] - REACH * sw * u[1], 2))
    if abs(nV[0] - V[0]) < 0.02 and abs(nV[1] - V[1]) < 0.02:   # already in place: a rounding hair does not move it
        nV = (V[0], V[1])
    if which == "marker-end":
        pts[-1] = list(nV)
    else:
        pts[0] = list(nV)
    log.append((kind, mid, which, (round(V[0], 2), round(V[1], 2)), nV))
    return with_points(tag, name, pts)


def migrate_svg(svg: str, rules=()):
    """(the svg with its markers and arrow ends migrated, the log of each arrow end)."""
    masked = [(m.start(), m.end()) for m in MARKER_RE.finditer(svg)]

    def in_marker(pos):
        return any(a <= pos < b for a, b in masked)

    # the marker table before any edit: id -> (tip, refX)
    info = {}
    for m in MARKER_RE.finditer(svg):
        idm = re.search(r'(?<![\w-])id="([^"]*)"', m.group(1))
        if idm:
            info[idm.group(1)] = (marker_tip(m.group(2)), num(attr(m.group(1), "refX"), 0.0))
    # the boxes: every rect outside a marker; a stroked rect's stroke width counts as its outer border
    rects = []
    for m in TAG_RE.finditer(svg):
        if m.group(2) != "rect" or m.group(1) or in_marker(m.start()):
            continue
        a = m.group(3)
        x, y, w, h = (num(attr(a, k)) for k in ("x", "y", "width", "height"))
        if w <= 0 or h <= 0:
            continue
        stroked = re.search(r"stroke:(?!none)", a) is not None
        sw = own_stroke_width(a, rules)
        rects.append((x, y, w, h, (sw if sw is not None else 1.0) if stroked else 0.0))
    edits = []                                  # (start, end, replacement)
    for m in MARKER_RE.finditer(svg):
        head_end = svg.index(">", m.start()) + 1
        head = svg[m.start():head_end]
        T = marker_tip(m.group(2))
        new = set_attr(head, "refX", "%g" % (T - REACH))
        new = set_attr(new, "orient", "auto-start-reverse")
        if new != head:
            edits.append((m.start(), head_end, new))
    # the arrows: a line or polyline with marker-end or marker-start, on its own or from an enclosing <g>
    log, stack = [], [{}]
    for m in TAG_RE.finditer(svg):
        if in_marker(m.start()):
            continue
        close, name, a, selfc = m.group(1), m.group(2), m.group(3), m.group(4)
        if name == "g" and not selfc:
            if close:
                if len(stack) > 1:
                    stack.pop()
                continue
            inh = dict(stack[-1])
            for k in ENDS:
                v = attr(a, k)
                if v is not None:
                    inh[k] = v
            sw = own_stroke_width(a, rules)
            if sw is not None:
                inh["sw"] = sw
            stack.append(inh)
            continue
        if close or name not in ("line", "polyline"):
            continue
        eff = dict(stack[-1])
        for k in ENDS:
            v = attr(a, k)
            if v is not None:
                eff[k] = v
        own = own_stroke_width(a, rules)
        line_sw = own if own is not None else eff.get("sw", 1.0)
        tag = m.group(0)
        new_tag = tag
        for which in ENDS:
            ref = eff.get(which)
            ids = re.findall(r"url\(\s*[\"']?#([^\"')]+)", ref or "")
            if not ids:
                continue
            mid = ids[0]
            T_old, refx_old = info.get(mid, (7.0, 0.0))
            # the line's own marker-end, when set on the element, is read from the tag itself
            new_tag = arrow_fix(new_tag, name, which, mid, T_old - refx_old, rects, log, line_sw)
        if new_tag != tag:
            edits.append((m.start(), m.end(), new_tag))
    out = svg
    for s, e, text in sorted(edits, reverse=True):
        out = out[:s] + text + out[e:]
    return out, log


def migrate_text(src: str, rules=()):
    """(the file's text migrated, the log): every svg in it, the marker and arrow changes only."""
    total = []

    def repl(m):
        s, log = migrate_svg(m.group(0), rules)
        total.extend(log)
        return s
    return SVG_RE.sub(repl, src), total


def deliverable_files(d: Path):
    for folder in CONTENT:
        base = d / folder
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in p.parts:
                    yield p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("deliverable", type=Path, help="a copy of a template (a deck, a document or a docs site)")
    ap.add_argument("--write", action="store_true", help="apply the migration (default: a dry run, nothing written)")
    a = ap.parse_args(argv)
    d = a.deliverable.resolve()
    if not any((d / f).is_dir() for f in CONTENT) or not (d / "index.html").is_file():
        print(f"x {d} is not a DbxOffice deliverable (index.html + slides|sections|pages/)", file=sys.stderr)
        return 2
    if d.name == "template" and (d.parent / "SKILL.md").is_file():
        print("x refusing to migrate a skill baseline template/ - copy it first", file=sys.stderr)
        return 2
    sheets = sorted((d / "assets").glob("*.css")) if (d / "assets").is_dir() else []
    rules = css_rules("\n".join(s.read_text(encoding="utf-8") for s in sheets))
    changed_files = 0
    arrows = []
    for p in deliverable_files(d):
        src = p.read_text(encoding="utf-8")
        out, log = migrate_text(src, rules)
        if not log:
            continue
        arrows.extend(log)
        if out != src:
            changed_files += 1
            if a.write:
                p.write_text(out, encoding="utf-8")
        print(f"{p.relative_to(d).as_posix()}: {len(log)} arrow end(s)")
        for kind, mid, which, V, nV in log:
            print(f"   {kind:4} {mid} {which}: end {V} -> vertex {nV}")
    boxes = sum(1 for x in arrows if x[0] == "box")
    print(f"{'WROTE' if a.write else 'DRY RUN'}: {len(arrows)} arrow end(s) ({boxes} on a box, "
          f"{len(arrows) - boxes} free), {changed_files} file(s) {'changed' if a.write else 'would change'}")
    if not a.write and changed_files:
        print("nothing written: run with --write to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
