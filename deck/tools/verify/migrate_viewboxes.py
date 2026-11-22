#!/usr/bin/env python3
"""Rewrite the icon viewBoxes that a deliverable built before the 0.8.0 clearance fixes carries.

The clearance rule asks an icon drawn on a 24-unit grid to sit 8 units or more inside its viewBox. Three template
icons were fixed for it in 0.8.0 (the viewBox grew by the margin). A deliverable built earlier keeps the old values,
and the clearance audit flags them. This rewrites only those icon viewBoxes, each to its fixed value, and only on an
<svg> that carries the template icon's marker (its aria-label or class). Nothing else in a file changes.

    python3 tools/verify/migrate_viewboxes.py <deliverable> [--dry-run]

<deliverable> is a copy of a template (a deck, a document or a docs site), never a skill's template/. Run it from
anywhere. Idempotent: a second run finds nothing to change. Exit 0 (done, or nothing to do), 1 (a file could not be
read), 2 (not a deliverable). The same code is in all three content skills (a parity test keeps it so).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# (old viewBox, fixed viewBox, the marker that says the svg is that template icon). From the 0.8.0 fix commit 445a52e:
# problem cards (slides/36-problem.js, and the feature cards of 22-cards-cool.js) and the Unity tiles (off-unity.js).
MIGRATIONS = (
    ("-1 -1 26 26", "-5 -5 34 34", 'aria-label="Problem icon"'),
    ("0 0 24 24", "-5 -5 34 34", 'aria-label="Feature icon"'),
    ("-4 -4 32 32", "-6 -6 36 36", 'class="uc-ico"'),
)
OLD_VIEWBOXES = frozenset(old for old, _, _ in MIGRATIONS)
SVG_TAG = re.compile(r"<svg\b[^>]*>")
SUFFIXES = {".js", ".html", ".htm"}
SKIP_DIRS = {"tools", "brand", "resources", "__pycache__"}


def suggestion(icon: dict | None) -> str | None:
    """The line the clearance audit adds to a finding inside an svg that is a known template icon (its viewBox, and
    its aria-label or class, match one MIGRATIONS entry). None for any other svg."""
    if not icon:
        return None
    for old, _, marker in MIGRATIONS:
        name, value = marker.split('="', 1)[0], marker.split('="', 1)[1].rstrip('"')
        if icon.get("viewBox") != old:
            continue
        if (name == "aria-label" and icon.get("label") == value) or (name == "class" and value in icon.get("cls", "").split()):
            return ('this svg is a known template icon with its pre-0.8.0 viewBox "%s": run '
                    "python3 tools/verify/migrate_viewboxes.py <deliverable>" % old)
    return None


def migrate_text(text: str) -> tuple[str, dict]:
    """The text with the known icon viewBoxes fixed, and {(old, new, marker): count} of what changed."""
    counts: dict = {}

    def fix(m: re.Match) -> str:
        tag = m.group(0)
        for old, new, marker in MIGRATIONS:
            if marker in tag and 'viewBox="%s"' % old in tag:
                tag = tag.replace('viewBox="%s"' % old, 'viewBox="%s"' % new, 1)
                counts[(old, new, marker)] = counts.get((old, new, marker), 0) + 1
        return tag

    return SVG_TAG.sub(fix, text), counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("deliverable", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    a = ap.parse_args(argv)
    d = a.deliverable.resolve()
    if not (d / "index.html").is_file() or not any((d / k).is_dir() for k in ("slides", "sections", "pages")):
        print(f"x {d} is not a DbxOffice deliverable (index.html + slides|sections|pages/)", file=sys.stderr)
        return 2
    if d.name == "template" and (d.parent / "SKILL.md").is_file():
        print("x refusing to migrate a skill baseline template/ - copy it first", file=sys.stderr)
        return 2
    total, files = 0, 0
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d)
        if not p.is_file() or p.suffix.lower() not in SUFFIXES or SKIP_DIRS & set(rel.parts):
            continue
        try:
            raw = p.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"x {rel.as_posix()}: {e}", file=sys.stderr)
            return 1
        new, counts = migrate_text(text)
        if not counts:
            continue
        for (old, fixed, marker), k in sorted(counts.items()):
            print(f"  {rel.as_posix()}: {k} x viewBox \"{old}\" -> \"{fixed}\" ({marker})")
        total += sum(counts.values())
        files += 1
        if not a.dry_run:
            p.write_bytes(new.encode("utf-8"))      # bytes: the line endings of the file are kept
    if total:
        print(f"{'would migrate' if a.dry_run else 'migrated'} {total} icon viewBox(es) in {files} file(s)")
    else:
        print("nothing to migrate: no known template icon viewBox")
    return 0


if __name__ == "__main__":
    sys.exit(main())
