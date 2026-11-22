#!/usr/bin/env python3
# =============================================================================
# HTML DbxSlides  →  native Google Slides
# -----------------------------------------------------------------------------
# Turns a deck built from this template into a REAL Google Slides presentation:
# editable text boxes, native shapes, and images — not screenshots. It reuses
# the browser's own layout engine (via assets/gslides.js) to read exact
# positions/colours/fonts, then builds matching Slides objects through the
# Slides + Drive REST APIs.
#
# Usage:
#   python3 export_gslides.py --deck /path/to/deck-folder \
#       --folder <DRIVE_FOLDER_ID> [--title "My Deck"]
#   python3 export_gslides.py --ir deck.gslides.json --folder <ID>
#   python3 export_gslides.py --deck <folder> --folder <ID> --preview   # target + images + question
#   python3 export_gslides.py --deck <folder> --folder <ID> --no-images --pptx   # + PowerPoint copy
#   python3 export_gslides.py --sweep        # check Drive for temp images left shared (no build)
#
# Images: Slides fetches images anonymously, so each one is shared "anyone with the
# link" in Drive while the build runs, then deleted. This needs consent —
# --allow-public-images (only after the user says yes to the --preview question), or
# --no-images, which leaves every image out as a labelled placeholder frame and lists
# each one in the run summary. Temp files are tagged in Drive (appProperties), so the
# end of every run deletes what it uploaded and checks that nothing is still shared;
# --sweep runs the same check on its own. Anything still shared exits 3.
#
# --pptx: after the build, exports the Google Slides file to PowerPoint (Drive
#         files.export) into exports/ next to the deck, and prints what came across
#         as native objects and what is a picture.
#
# Auth: Application Default Credentials via gcloud (the fe-google-tools CLI path).
#       Requires the Slides + Drive scopes and a quota project (default gcp-dev-field-eng-aiapiquota;
#       override with GS_QUOTA_PROJECT).
# =============================================================================
import argparse, base64, collections, hashlib, html, json, os, re, socket, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, zipfile

QUOTA_PROJECT = os.environ.get("GS_QUOTA_PROJECT", "gcp-dev-field-eng-aiapiquota")
EMU_PER_PT = 12700
DESIGN_W, DESIGN_H = 1280.0, 720.0
INSET_LR = 91440   # Slides default text-box left/right inset (0.1")
INSET_TB = 45720   # Slides default text-box top/bottom inset (0.05")

# ---------------------------------------------------------------------------- auth
def get_token():
    tok = os.environ.get("GS_TOKEN")
    if tok:
        return tok.strip()
    try:
        out = subprocess.check_output(
            ["gcloud", "auth", "application-default", "print-access-token"],
            stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception as e:
        sys.exit("Could not get an access token via gcloud ADC. "
                 "Run the google-auth skill's login first. (%s)" % e)

TOKEN = None
def hdrs(extra=None):
    h = {"Authorization": "Bearer " + TOKEN,
         "x-goog-user-project": QUOTA_PROJECT}
    if extra:
        h.update(extra)
    return h

class UnsureWrite(RuntimeError):
    """A batchUpdate failed (5xx, or a timeout/reset once sent) after Google may already have applied it. It is never
    sent again blind: DeckWriter reads the deck back, and repeats the batch only when the revision shows that nothing
    applied, pinned to the same revision so the original and the repeat cannot both apply. What is left stops the export
    with this error, which callers must not swallow."""


class DocumentChanged(RuntimeError):
    """Google refused a pinned batchUpdate because the deck is no longer at the revision the batch was built on
    (writeControl.requiredRevisionId). Someone edited the deck during the export, or a late copy of an earlier batch
    landed first. Nothing is rebased: the export stops (no caller turns this into a skipped object or a warning)."""


def _is_precondition(err):
    """True when err is Google's refusal of a pinned write. The Docs API answers a stale requiredRevisionId with 400
    INVALID_ARGUMENT, "...does not match the latest revision." (checked live); the same match is used here, where the
    wording is not checked live, and FAILED_PRECONDITION is matched too."""
    s = " ".join(str(err).split())
    return "HTTP 400" in s and bool(_REVISION_REFUSAL.search(s))

_REVISION_REFUSAL = re.compile(r"revision.*\b(?:latest|match)\b|FAILED_PRECONDITION", re.I)


def unsure_write(method, url, why):
    """The UnsureWrite for this batchUpdate, naming the half-built file to delete."""
    m = re.search(r"/(documents|presentations)/([^/:?]+):batchUpdate", url)
    where = ("https://docs.google.com/%s/d/%s/edit" % (m.group(1)[:-1], m.group(2))) if m else "in Drive"
    return UnsureWrite("%s %s -> %s: Google may have applied this update, so it was not retried "
                       "(that could duplicate content). Delete the half-built file (%s) and run "
                       "the export again." % (method, url.split('?')[0], why, where))


def api(method, url, body=None, raw=None, ctype="application/json", binary=False):
    data = None
    headers = hdrs()
    if raw is not None:
        data = raw
        headers["Content-Type"] = ctype
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    # Always bound network calls — a stalled connection must not hang the export.
    # HTTP 429 (Slides allows ~60 writes/min/user) and transient 5xx (Drive returns
    # sporadic 500/503 under load) are retried with backoff rather than failing the
    # request, which would silently drop an image or a slide. A batchUpdate is retried
    # on 429 only: Google rejects a rate-limited request before applying it, but after a
    # 5xx the edit may already be in, and a retry would add it twice.
    write = method == "POST" and ":batchUpdate" in url
    for attempt in range(6):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                b = r.read()
                if binary:
                    return b
                return json.loads(b) if b else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if write and e.code in (500, 502, 503, 504):
                raise unsure_write(method, url, "HTTP %s %s" % (e.code, detail.strip()[:300]))
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                wait = 10 * (attempt + 1) if e.code == 429 else 2 ** (attempt + 1)
                print("    (Google returned HTTP %s, retrying in %ds ...)" % (e.code, wait), file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError("%s %s -> HTTP %s\n%s" % (method, url.split('?')[0], e.code, detail))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if write and not isinstance(getattr(e, "reason", e), (socket.gaierror, ConnectionRefusedError)):
                # a timeout or reset once the edit was sent is as unsure as a 5xx
                raise unsure_write(method, url, "network error (%s)" % e)
            raise RuntimeError("%s %s -> network error: %s" % (method, url.split('?')[0], e))

# ---------------------------------------------------------------------------- IR
def ir_from_chrome(deck_dir):
    chrome = CHROME
    index = os.path.join(os.path.abspath(deck_dir), "index.html")
    if not os.path.exists(index):
        sys.exit("No index.html in %s" % deck_dir)
    url = "file://%s?gslides=dump" % index
    # Pin a window size: the extractor normalises everything to 1280x720 design
    # units, but a fixed, generous viewport keeps the render scale stable and
    # sub-pixel rounding small across machines.
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--force-device-scale-factor=1", "--window-size=1280,800",
           "--virtual-time-budget=60000", "--dump-dom", url]
    print("Extracting layout via headless Chrome ...", file=sys.stderr)
    try:
        dom = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=90).decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        sys.exit("Headless Chrome timed out extracting the deck layout.")
    except FileNotFoundError:
        sys.exit("Could not launch Chrome at '%s'. Set the CHROME env var to your "
                 "Chrome/Chromium binary." % chrome)
    m = re.search(r'<textarea id="__gsir__"([^>]*)>(.*?)</textarea>', dom, re.S)
    if not m:
        sys.exit("Extractor did not produce IR (is assets/gslides.js loaded in index.html?).")
    # the dump waits for every slide of the manifest; a dump taken without them is a short deck, not a result
    attrs = dict(re.findall(r'(data-[\w-]+)="([^"]*)"', m.group(1)))
    loaded, expected = attrs.get("data-loaded"), attrs.get("data-expected")
    if attrs.get("data-timed-out") == "1" or (loaded and expected and int(loaded) < int(expected)):
        sys.exit("The deck's slides did not all load: %s of %s are in the page when the extractor gave up. Check the "
                 "slides/manifest.js names against the slides/ folder (a missing file), then run it again."
                 % (loaded, expected))
    return json.loads(html.unescape(m.group(2)))

# ---------------------------------------------------------------------------- colour
def rgb(hexstr):
    hexstr = (hexstr or "#000000").lstrip("#")
    if len(hexstr) == 3:
        hexstr = "".join(c * 2 for c in hexstr)
    return {"red": int(hexstr[0:2], 16) / 255.0,
            "green": int(hexstr[2:4], 16) / 255.0,
            "blue": int(hexstr[4:6], 16) / 255.0}

def solid_fill(hexstr, alpha=1.0):
    return {"solidFill": {"color": {"rgbColor": rgb(hexstr)}, "alpha": alpha}}

# ---------------------------------------------------------------------------- images
_uploaded = {}      # payload hash -> drive file id
_temp_files = []
DECK_DIR = None

def _find_chrome():
    """Resolve a Chrome/Chromium binary: $CHROME, then common per-OS names/paths."""
    import shutil
    env = os.environ.get("CHROME")
    if env:
        return env
    if sys.platform == "darwin":
        cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    else:
        cands = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]
    for c in cands:
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            p = shutil.which(c)
            if p:
                return p
    return cands[0]   # a sane default; callers surface a clear error if it can't launch

CHROME = _find_chrome()

# Headless Chrome paints the page into the window, but a screenshot can leave the foot of the window
# unpainted (transparent): the bottom 70 to 115 px of a 864 px figure went missing in about one render in
# six when two Chrome instances ran at once (the axis label of a matrix, the last line of a chart). The
# figure is therefore rendered in a window SHOT_SLACK px taller than it, and only the top w x h is kept,
# so the unpainted foot is never part of the figure. A fresh --user-data-dir (a parallel run gives each
# job one) also keeps only about 87 px of a window 81 to 199 px tall, which the same slack covers.
SHOT_SLACK = 240

def _png_keep_top_left(path, w, h):
    """Crop a PNG in place to its top-left w x h. Stdlib only; reads the 8-bit RGB/RGBA, non-interlaced
    PNGs that headless Chrome writes. Returns False (file untouched) for anything else."""
    import struct, zlib
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    pos, idat, ihdr = 8, [], None
    while pos + 8 <= len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        pos += 12 + ln
    if not ihdr:
        return False
    W0, H0, bd, ct, _cm, _fm, il = ihdr
    if bd != 8 or ct not in (2, 6) or il or w > W0 or h > H0:
        return False
    bpp = 4 if ct == 6 else 3
    stride, keep = W0 * bpp, w * bpp
    raw = zlib.decompress(b"".join(idat))
    prev, rows, p = bytearray(keep), [], 0
    for _y in range(h):
        ft = raw[p]
        src = raw[p + 1:p + 1 + keep]
        p += 1 + stride
        cur = bytearray(keep)
        for i in range(keep):
            x = src[i]
            a = cur[i - bpp] if i >= bpp else 0          # left
            b = prev[i]                                  # up
            if ft == 0:
                v = x
            elif ft == 1:
                v = x + a
            elif ft == 2:
                v = x + b
            elif ft == 3:
                v = x + ((a + b) >> 1)
            elif ft == 4:
                c = prev[i - bpp] if i >= bpp else 0    # upper left
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                v = x + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))
            else:
                return False
            cur[i] = v & 255
        rows.append(b"\x00" + bytes(cur))
        prev = cur
    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body) & 0xFFFFFFFF)
    out = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ct, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(out)
    return True

def _chrome_screenshot(chrome, html_path, w, h, out_png, flags=()):
    """Screenshot an HTML file at exactly w x h px, whatever the Chrome profile. Returns True when
    out_png was written. The window is SHOT_SLACK px taller than the figure and the top w x h is kept
    (see above), so a part of the window that Chrome did not paint is cropped away."""
    win_h = h + SHOT_SLACK
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
           "--force-device-scale-factor=1", "--window-size=%d,%d" % (w, win_h),
           "--screenshot=" + out_png, "--virtual-time-budget=4000"] + list(flags) + ["file://" + html_path]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except subprocess.TimeoutExpired:
        return False
    if not os.path.exists(out_png):
        return False
    if not _png_keep_top_left(out_png, w, h):
        # never leave a render at the wrong size: a file that cannot be cropped is dropped
        os.remove(out_png)
        return False
    return True

def _chrome_img_to_png(svg_path, w, h, crop=None, fit=None, css_filter=None, round_css=None):
    """Render any image file (SVG, webp, …) to a transparent PNG via headless
    Chrome — portable, no dependency on macOS `sips`. `fit` mirrors the element's
    object-fit; `crop` (fractions of the full box, plus its full size fw/fh) keeps
    only the visible slice of an image under a clip-path (Slides cannot crop)."""
    import tempfile
    scale = 2
    fw, fh = (crop["fw"], crop["fh"]) if crop else (w, h)
    FW, FH = max(1, int(round(fw * scale))), max(1, int(round(fh * scale)))
    W, H = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    ox = int(round((crop or {}).get("l", 0) * FW)); oy = int(round((crop or {}).get("t", 0) * FH))
    # a masked picture (an avatar) is clipped to its radius on the same div that clips the crop
    rnd_part = (";border-radius:%s" % round_css) if round_css else ""

    wrap = ('<!doctype html><meta charset="utf-8">'
            '<body style="margin:0;padding:0"><div style="width:%dpx;height:%dpx;overflow:hidden%s">'
            '<img src="file://%s" style="width:%dpx;height:%dpx;display:block;margin:%dpx 0 0 %dpx;'
            'object-fit:%s%s"></div></body>' % (W, H, rnd_part, svg_path, FW, FH, -oy, -ox, fit or "fill",
                                               (";filter:%s" % css_filter) if css_filter else ""))

    td = tempfile.mkdtemp(prefix="gs_svg_")
    hp = os.path.join(td, "w.html")
    op = os.path.join(td, "o.png")
    with open(hp, "w") as f:
        f.write(wrap)
    if not _chrome_screenshot(CHROME, hp, W, H, op, ["--default-background-color=00000000"]):
        return None
    with open(op, "rb") as f:
        return f.read()

def _chrome_emoji_to_png(ch, w, h, font_px):
    """Render an emoji glyph to a transparent PNG via headless Chrome (which has
    the OS colour-emoji font), so icon spots don't tofu in Slides' fonts."""
    import tempfile, html as _html
    scale = 3
    W, H = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    fs = max(8, int(round(font_px * scale)))
    wrap = ('<!doctype html><meta charset="utf-8">'
            '<div style="margin:0;width:%dpx;height:%dpx;display:flex;'
            'align-items:center;justify-content:center;font-size:%dpx;'
            'line-height:1;font-family:\'Apple Color Emoji\',\'Segoe UI Emoji\','
            '\'Noto Color Emoji\',sans-serif">%s</div>'
            % (W, H, fs, _html.escape(ch)))
    td = tempfile.mkdtemp(prefix="gs_emoji_")
    hp, op = os.path.join(td, "e.html"), os.path.join(td, "e.png")
    with open(hp, "w") as f:
        f.write(wrap)
    if not _chrome_screenshot(CHROME, hp, W, H, op, ["--default-background-color=00000000"]):
        return None
    if os.path.exists(op):
        with open(op, "rb") as f:
            return f.read()
    return None

# CSS filters the extractor may send on an image (the same functions CSS accepts)
_FILTER_OK = re.compile(r"^(?:\s*(?:grayscale|opacity|brightness|contrast|saturate|sepia|invert|hue-rotate)"
                        r"\([^()]*\)\s*)+$")

def _bytes_for_src(src, w, h, crop=None, fit=None, css_filter=None, round_css=None):
    """Read image bytes for an <img src> or background-image url, converting to a
    Slides-friendly format. Handles deck-relative paths and absolute file:// URLs
    (computed background-image values resolve to absolute file:// URLs)."""
    import urllib.parse
    if src.startswith("file://"):
        path = urllib.parse.unquote(urllib.parse.urlparse(src).path)
    elif os.path.isabs(src):
        path = src
    elif DECK_DIR is not None:
        path = os.path.normpath(os.path.join(DECK_DIR, src))
    else:
        return None, None
    if not os.path.exists(path):
        return None, None
    ext = os.path.splitext(path)[1].lower()
    if round_css:                               # a masked picture (an avatar): Chrome clips it to the radius
        return _chrome_img_to_png(path, w, h, crop, fit, css_filter, round_css), "image/png"
    if css_filter:                              # Chrome applies the filter to the pixels
        return _chrome_img_to_png(path, w, h, crop, fit, css_filter), "image/png"
    if ext == ".svg" or crop or fit:          # Chrome renders the slice / the object-fit
        return _chrome_img_to_png(path, w, h, crop, fit), "image/png"
    if ext in (".png", ".jpg", ".jpeg", ".gif"):
        with open(path, "rb") as f:
            return f.read(), {"png": "image/png", "jpg": "image/jpeg",
                              "jpeg": "image/jpeg", "gif": "image/gif"}[ext.lstrip(".")]
    if ext == ".webp":  # Slides can't ingest webp → render to PNG via Chrome (portable)
        return _chrome_img_to_png(path, w, h), "image/png"
    return None, None

def upload_bytes(raw, ctype, key):
    if not IMAGES_ENABLED:
        raise RuntimeError("images disabled (--no-images)")
    if key in _uploaded:
        return _uploaded[key]
    # 1) upload the bytes as a temp file tagged with this run (see upload_temp)
    fid = upload_temp(raw, ctype, "dbxo-temp-%s" % key[:10])
    # 2) share anyone-with-link reader so the Slides image fetcher can read it
    api("POST",
        "https://www.googleapis.com/drive/v3/files/%s/permissions?supportsAllDrives=true" % fid,
        body={"role": "reader", "type": "anyone"})
    _uploaded[key] = fid
    return fid

def _filter_png_bytes(raw, w, h, css_filter):
    """A PNG with a CSS filter applied, rendered by headless Chrome (returns PNG bytes or None)."""
    import tempfile
    td = tempfile.mkdtemp(prefix="gs_filt_")
    src = os.path.join(td, "in.png")
    with open(src, "wb") as f:
        f.write(raw)
    return _chrome_img_to_png(src, w, h, None, None, css_filter)

def resolve_image(el):
    """Return a Drive file id for an image element, or None if unavailable."""
    flt = el.get("filter")
    if flt and not _FILTER_OK.match(flt):
        print("  ! image filter %r is not a supported CSS filter; the picture is used unfiltered" % flt,
              file=sys.stderr)
        flt = None
    if el.get("data"):
        head, b64 = el["data"].split(",", 1)
        raw = base64.b64decode(b64)
        if flt:
            raw = _filter_png_bytes(raw, el.get("w", 100), el.get("h", 100), flt)
            if not raw:
                return None
        return upload_bytes(raw, "image/png", hashlib.sha1((el["data"] + "|" + (flt or "")).encode()).hexdigest())
    if el.get("src"):
        w = el.get("w", 100); h = el.get("h", 100)
        crop, fit = el.get("crop"), el.get("fit")
        rnd = el.get("round")
        raw, ctype = _bytes_for_src(el["src"], w, h, crop, fit, flt, rnd)
        if raw:
            key = hashlib.sha1((el["src"] + ("|svg" if el["src"].lower().endswith(".svg")
                                             else "")).encode()).hexdigest()
            # SVGs, crops, object-fit and masked renders are size-dependent → key by size too
            if el["src"].lower().endswith(".svg") or crop or fit or rnd:
                key = hashlib.sha1(("%s|%dx%d|%s|%s|%s" % (el["src"], int(w), int(h),
                                    json.dumps(crop, sort_keys=True), fit, rnd)).encode()).hexdigest()
            return upload_bytes(raw, ctype, key)
    return None

def image_url(fid):
    return "https://drive.google.com/uc?export=view&id=%s" % fid

# ------------------------------------------------------------ temporary public images
# Slides' image fetcher reads createImage URLs anonymously, so each image is uploaded to
# Drive and shared "anyone with the link" (reader) for the few seconds the build needs,
# then deleted. That needs explicit consent: --allow-public-images, given only after the
# user has answered the --preview question. --no-images uploads nothing and leaves each
# image out as a labelled placeholder frame, listed in the run summary.
#
# Every temp file is created with appProperties (dbxo_temp, and dbxo_run = this run's id),
# so it can be found again even if an upload's response was lost. The end of every real run
# (success, error or Ctrl-C) deletes this run's temp files and checks Drive once more.
# --sweep runs the check for every run. A file still shared at the end exits 3.
IMAGES_ENABLED = True
RUN_ID = "%s-%d" % (time.strftime("%Y%m%d-%H%M%S"), os.getpid())
_TEMP_USED = [False]     # an upload was attempted in this run
OMITTED = []             # {"slide", "label", "why"}: every image left out of the deck
SKIPPED = []             # (count, first error): change requests Google refused, left out

def upload_temp(raw, ctype, name):
    """Upload bytes as a temp file tagged with this run. Its id is recorded before anything
    else can fail, so the cleanup always knows it. Returns the Drive file id."""
    _TEMP_USED[0] = True
    b = "dbxo" + RUN_ID.replace("-", "")
    meta = {"name": name, "appProperties": {"dbxo_temp": "1", "dbxo_run": RUN_ID}}
    body = (("--%s\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n%s\r\n"
             "--%s\r\nContent-Type: %s\r\n\r\n") % (b, json.dumps(meta), b, ctype)).encode("utf-8") \
        + raw + ("\r\n--%s--" % b).encode("ascii")
    up = api("POST", "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
                     "&supportsAllDrives=true&fields=id",
             raw=body, ctype='multipart/related; boundary="%s"' % b)
    _temp_files.append(up["id"])
    return up["id"]

def list_public_images(ir):
    """Every distinct image the build would upload and share publicly, as display
    strings (repeats of the same file/glyph are uploaded once, so listed once)."""
    out, seen = [], set()
    for i, s in enumerate(ir["slides"], 1):
        for el in s["elements"]:
            t = el.get("type")
            if t == "image":
                if el.get("data"):
                    key, label = ("data", hashlib.sha1(el["data"].encode()).hexdigest()), \
                        "inline image (first on slide %d)" % i
                elif el.get("src"):
                    key = ("src", el["src"])
                    shown = _display_src(el["src"])
                    outside = os.path.isabs(shown) or shown == ".." or shown.startswith(".." + os.sep)
                    label = "image: %s%s" % (shown, "  <- OUTSIDE the deck folder: check it is "
                                             "meant to be shared" if outside and DECK_DIR else "")
                else:
                    continue
            elif t == "emoji":
                key, label = ("emoji", el.get("text")), "emoji glyph: %s" % el.get("text", "")
            else:
                continue
            if key not in seen:
                seen.add(key)
                out.append(label)
    return out

def _display_src(src):
    """Deck-relative path for a src (file:// URLs and absolute paths included)."""
    path = urllib.parse.unquote(urllib.parse.urlparse(src).path) if src.startswith("file://") else src
    if DECK_DIR and not os.path.isabs(path):
        path = os.path.normpath(os.path.join(DECK_DIR, path))
    if DECK_DIR and os.path.isabs(path):
        try:
            rel = os.path.relpath(path, DECK_DIR)
            if rel != ".." and not rel.startswith(".." + os.sep):  # "..assets/x" is inside
                return rel
        except ValueError:
            pass
    return path

def font_substitution_lines(subs):
    """The fonts the deck asked for that Google Slides does not host, and what is used instead."""
    return ["fonts: %s \u2192 %s (not hosted by Google)" % (req, used)
            for req, used in sorted((subs or {}).items())]

def folder_info(folder, token_env):
    """The target Drive folder's name and owner, for --preview: one read-only metadata GET. Returns
    (text, None) on success, or (None, reason) when the credentials or the call are not available."""
    tok = os.environ.get(token_env, "").strip()
    if not tok:
        try:
            tok = subprocess.check_output(["gcloud", "auth", "application-default", "print-access-token"],
                                          stderr=subprocess.DEVNULL, timeout=30).decode().strip()
        except Exception as e:
            return None, "no Google credentials (%s)" % str(e).splitlines()[0][:80]
    url = ("https://www.googleapis.com/drive/v3/files/%s?fields=name,owners(displayName,emailAddress)"
           "&supportsAllDrives=true" % urllib.parse.quote(folder))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok,
                                               "x-goog-user-project": QUOTA_PROJECT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except Exception as e:
        return None, str(e).splitlines()[0][:160]
    owners = ", ".join(o.get("emailAddress") or o.get("displayName", "?") for o in data.get("owners", [])) or "unknown"
    return "%s (owner: %s)" % (data.get("name", "?"), owners), None

def print_preview(title, folder, n_slides, images, no_images, subs=None, folder_meta=None):
    """The --preview output: the target, the fonts, every image, and the question to relay."""
    e = sys.stderr
    glyphs = [i for i in images if i.startswith("emoji glyph")]
    pics = [i for i in images if not i.startswith("emoji glyph")]
    print("Export preview", file=e)
    print("  title : %s (%d slides)" % (title, n_slides), file=e)
    print("  target: %s" % ("https://drive.google.com/drive/folders/%s" % folder if folder
                             else "(no --folder given)"), file=e)
    if folder:
        if folder_meta:
            print("  folder: %s" % folder_meta, file=e)
        else:
            print("  folder: name and owner not read (no credentials or no access); confirm the folder with the user",
                  file=e)
    for line in font_substitution_lines(subs):
        print("  " + line, file=e)
    if no_images:
        if pics:
            print("  images: left out (--no-images). Each becomes a labelled placeholder frame "
                  "and is listed in the run summary:", file=e)
            for i in pics:
                print("    - %s" % i, file=e)
        else:
            print("  images: none", file=e)
        if glyphs:
            print("  emoji : %d glyph(s) stay as live text (nothing uploaded)" % len(glyphs), file=e)
        print("  nothing will be shared publicly", file=e)
        return
    if not images:
        print("  images: none, so nothing will be shared publicly", file=e)
        return
    print("  images: %d will be uploaded to your Drive and shared \"anyone with the link\" "
          "(reader) for the duration of the build, then deleted:" % len(images), file=e)
    for i in images:
        print("    - %s" % i, file=e)
    print("  QUESTION FOR THE USER (relay it word for word, then wait for the answer):", file=e)
    print("    \"This export will briefly share %d image(s) from your deck with anyone who has the "
          "link, then delete them. Allow it? (yes / no)\"" % len(images), file=e)
    print("  yes: re-run with --allow-public-images.   no, or no answer: re-run with --no-images.",
          file=e)

def confirm_public_images(images, allow):
    """True = upload images; exits when consent is missing. Call after print_preview."""
    if not images or allow:
        return True
    if sys.stdin.isatty():
        ans = input("Temporarily share these %d image(s) publicly? [y/N] " % len(images))
        if ans.strip().lower() in ("y", "yes"):
            return True
        sys.exit("Aborted — nothing was uploaded. Re-run with --no-images to export "
                 "without images.")
    sys.exit("Refusing to share images publicly without consent. Re-run with "
             "--allow-public-images once the user has answered yes to the --preview question, "
             "or with --no-images to export without images. Nothing was uploaded.")

def drive_delete(fid):
    """Delete a temp Drive file (one retry). Returns None on success, else the error."""
    err = None
    for _ in range(2):
        try:
            api("DELETE", "https://www.googleapis.com/drive/v3/files/%s?supportsAllDrives=true" % fid)
            return None
        except Exception as e:
            if "HTTP 404" in str(e):
                return None          # already gone
            err = e
    return err

def cleanup_temp():
    """Delete every temp image this run knows about; returns the [(fid, error)] left."""
    failed = []
    for fid in _temp_files:
        err = drive_delete(fid)
        if err is not None:
            failed.append((fid, err))
    return failed

def report_cleanup(failed):
    """Loudly report temp images that could not be deleted. Returns True if any."""
    if not failed:
        return False
    e = sys.stderr
    print("\nWARNING: %d temporary image(s) could NOT be deleted (they may still be shared "
          "\"anyone with the link\"):" % len(failed), file=e)
    for fid, err in failed:
        print("  - %s  (%s)" % (fid, str(err).splitlines()[0]), file=e)
    print("Delete them now in Drive (https://drive.google.com/file/d/<id>), or run:", file=e)
    for fid, _ in failed:
        print("  curl -X DELETE -H \"Authorization: Bearer $(gcloud auth application-default "
              "print-access-token)\" -H \"x-goog-user-project: %s\" "
              "https://www.googleapis.com/drive/v3/files/%s?supportsAllDrives=true"
              % (QUOTA_PROJECT, fid), file=e)
    return True

def list_tool_files(run_id=None):
    """Temp files this tool still has in Drive: all of them, or only those of run_id."""
    q = "appProperties has { key='dbxo_temp' and value='1' } and trashed = false"
    if run_id:
        q = "appProperties has { key='dbxo_run' and value='%s' } and trashed = false" % run_id
    out, token = [], None
    while True:
        params = {"q": q, "fields": "nextPageToken,files(id,name,permissions(type,role))",
                  "pageSize": "100", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if token:
            params["pageToken"] = token
        page = api("GET", "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode(params))
        out.extend(page.get("files", []))
        token = page.get("nextPageToken")
        if not token:
            return out

def is_anyone_link(f):
    return any(p.get("type") == "anyone" for p in f.get("permissions", []))

def finish_run():
    """End of every real run, on success, error and Ctrl-C alike: delete this run's temp
    images (the ids it knows, then anything Drive still holds under this run's tag) and
    report what could not be deleted. Returns True if files may still be shared."""
    failed = cleanup_temp()
    if not _TEMP_USED[0]:
        return False
    try:
        left = list_tool_files(RUN_ID)
    except Exception as e:
        print("\nWARNING: could not check Drive for this run's temp images (%s). Run "
              "export_gslides.py --sweep before you rely on the sharing state."
              % str(e).splitlines()[0], file=sys.stderr)
        return True
    done = {fid for fid, _ in failed}
    for f in left:
        if f["id"] in done:
            continue
        err = drive_delete(f["id"])
        if err is not None:
            failed.append((f["id"], err))
    return report_cleanup(failed)

def sweep_standalone():
    """--sweep: list every temp file this tool still has in Drive and exit 3 if any is
    shared 'anyone with the link'. Changes nothing."""
    global TOKEN
    TOKEN = get_token()
    try:
        files = list_tool_files()
    except Exception as e:
        print("Sweep failed: could not list Drive files (%s)." % str(e).splitlines()[0], file=sys.stderr)
        return 1
    shared = [f for f in files if is_anyone_link(f)]
    print("Sweep: %d temp file(s) from DbxSlides exports are in Drive; %d are shared "
          "'anyone with the link'." % (len(files), len(shared)))
    for f in files:
        print("  %-7s %s  %s" % ("SHARED" if is_anyone_link(f) else "private", f["id"], f.get("name", "")))
    if shared:
        print("Delete the SHARED files in Drive (https://drive.google.com/file/d/<id>), or run:")
        for f in shared:
            print("  curl -X DELETE -H \"Authorization: Bearer $(gcloud auth application-default "
                  "print-access-token)\" -H \"x-goog-user-project: %s\" "
                  "https://www.googleapis.com/drive/v3/files/%s?supportsAllDrives=true"
                  % (QUOTA_PROJECT, f["id"]))
        return 3
    return 0

def print_omitted(names_shown=4):
    """The run summary: the images left out of the deck, grouped by slide (one line per slide
    with a count and the first few names, then a total), and every change Google refused."""
    e = sys.stderr
    if OMITTED:
        by_slide = collections.OrderedDict()
        for o in OMITTED:
            by_slide.setdefault(o["slide"], []).append(o)
        total = len(OMITTED)
        print("\nLeft out of the Slides file: %d image(s) on %d slide(s). Each is a placeholder frame; "
              "the PDF has them:" % (total, len(by_slide)), file=e)
        for slide, items in by_slide.items():
            names = []
            for o in items:
                if o["label"] not in names:
                    names.append(o["label"])
            shown = ", ".join(names[:names_shown])
            more = len(names) - names_shown
            if more > 0:
                shown += ", and %d more" % more
            n = len(items)
            reason = items[0]["why"] if len(set(o["why"] for o in items)) == 1 else "mixed reasons"
            print("  slide %s: %d image%s (%s; %s)" % (slide, n, "" if n == 1 else "s", shown, reason), file=e)
        print("  total: %d image(s) on %d slide(s)" % (total, len(by_slide)), file=e)
    for n, msg in SKIPPED:
        print("Google refused %d change(s), so they were left out: %s" % (n, msg), file=e)

# ---------------------------------------------------------------------------- build
def emu_scale(page_size):
    w = page_size["width"]["magnitude"]
    h = page_size["height"]["magnitude"]
    # magnitudes come back in EMU
    return w / DESIGN_W, h / DESIGN_H

def elem_props(page_id, x, y, w, h, sx, sy):
    return {
        "pageObjectId": page_id,
        "size": {"width": {"magnitude": max(1, w * sx), "unit": "EMU"},
                 "height": {"magnitude": max(1, h * sy), "unit": "EMU"}},
        "transform": {"scaleX": 1, "scaleY": 1,
                      "translateX": x * sx, "translateY": y * sy, "unit": "EMU"},
    }

def u16len(s):
    """Length of s in UTF-16 code units — the unit the Slides API uses for text
    indices. Python's len() counts Unicode code POINTS, so an astral character
    (emoji, e.g. 🧪) counts as 1 in Python but 2 in Slides. Using len() to size a
    style range therefore drifts every run after an emoji short by one, leaving
    the run's trailing character(s) with the default (Arial / black) style — the
    "last letter in a different font and colour" bug on emoji card titles."""
    return sum(2 if ord(c) > 0xFFFF else 1 for c in s)

def _run_style(r):
    """Slides text style for one IR run (shared by text boxes and table cells)."""
    style = {
        "bold": bool(r.get("bold")),
        "italic": bool(r.get("italic")),
        "fontFamily": r.get("font", "DM Sans"),
        "fontSize": {"magnitude": max(1, r.get("size", 12)), "unit": "PT"},
        "foregroundColor": {"opaqueColor": {"rgbColor": rgb(r.get("color", "#000000"))}},
    }
    fields = "bold,italic,fontFamily,fontSize,foregroundColor"
    return style, fields

# Design px → pt uses 0.5625 (1280 px → a 720-pt Slides page); pt → EMU is
# EMU_PER_PT. Same factor the shape-outline code uses for line weights.
def _px_weight_emu(px):
    return max(1, px) * EMU_PER_PT * 0.5625

_BORDER_POS = {"top": "TOP", "bottom": "BOTTOM", "left": "LEFT", "right": "RIGHT"}

def build_table_requests(el, page_id, sx, sy, nid):
    """Build a NATIVE Google Slides table (createTable + per-cell text, fills and
    borders) from a table IR element — the editable equivalent of the HTML table,
    not a scatter of floating text boxes."""
    tid = nid("tbl")
    R, C = el["rows"], el["cols"]
    colw = el.get("colWidths") or [el["w"] / C] * C
    rowh = el.get("rowHeights") or [el["h"] / R] * R
    tw, th = sum(colw), sum(rowh)

    reqs = [{"createTable": {"objectId": tid, "rows": R, "columns": C,
        "elementProperties": elem_props(page_id, el["x"], el["y"], tw, th, sx, sy)}}]

    # A fresh Slides table draws a light border on every edge. Clear them all
    # (transparent fill) so only the edges the HTML actually paints survive.
    reqs.append({"updateTableBorderProperties": {"objectId": tid,
        "borderPosition": "ALL",
        "tableBorderProperties": {"tableBorderFill": {"solidFill": {
            "color": {"rgbColor": rgb("#000000")}, "alpha": 0}}},
        "fields": "tableBorderFill"}})

    # Merge spanned cells before touching content (addresses use the origin cell).
    for cell in el["cells"]:
        if cell.get("rowSpan", 1) > 1 or cell.get("colSpan", 1) > 1:
            reqs.append({"mergeTableCells": {"objectId": tid, "tableRange": {
                "location": {"rowIndex": cell["row"], "columnIndex": cell["col"]},
                "rowSpan": cell["rowSpan"], "columnSpan": cell["colSpan"]}}})

    # Column widths and (minimum) row heights, matching the measured HTML grid.
    for c in range(C):
        reqs.append({"updateTableColumnProperties": {"objectId": tid,
            "columnIndices": [c],
            "tableColumnProperties": {"columnWidth": {
                "magnitude": max(1, colw[c] if c < len(colw) and colw[c] else tw / C) * sx, "unit": "EMU"}},
            "fields": "columnWidth"}})
    for r in range(R):
        reqs.append({"updateTableRowProperties": {"objectId": tid,
            "rowIndices": [r],
            "tableRowProperties": {"minRowHeight": {
                "magnitude": max(1, rowh[r] if r < len(rowh) and rowh[r] else th / R) * sy, "unit": "EMU"}},
            "fields": "minRowHeight"}})

    for cell in el["cells"]:
        loc = {"rowIndex": cell["row"], "columnIndex": cell["col"]}
        # Span the whole merged region so a merged cell's fill and OUTER edges
        # cover it all, not just the origin sub-cell. (1×1 for ordinary cells.)
        rng = {"location": loc, "rowSpan": cell.get("rowSpan", 1), "columnSpan": cell.get("colSpan", 1)}

        # cell background fill + vertical alignment
        cell_props, cf = {"contentAlignment": cell.get("valign", "MIDDLE")}, ["contentAlignment"]
        if cell.get("fill"):
            cell_props["tableCellBackgroundFill"] = solid_fill(cell["fill"], cell.get("fillAlpha", 1))
            cf.append("tableCellBackgroundFill.solidFill")
        reqs.append({"updateTableCellProperties": {"objectId": tid,
            "tableRange": rng, "tableCellProperties": cell_props, "fields": ",".join(cf)}})

        # per-edge borders (only the ones the HTML paints)
        for b in cell.get("borders", []):
            pos = _BORDER_POS.get(b["side"])
            if not pos:
                continue
            reqs.append({"updateTableBorderProperties": {"objectId": tid,
                "tableRange": rng, "borderPosition": pos,
                "tableBorderProperties": {
                    "tableBorderFill": solid_fill(b["color"], b.get("alpha", 1)),
                    "weight": {"magnitude": _px_weight_emu(b["weight"]), "unit": "EMU"},
                    "dashStyle": "SOLID"},
                "fields": "tableBorderFill,weight,dashStyle"}})

        # cell text: insert, then style each run, then paragraph alignment
        runs = [r for r in cell.get("runs", []) if r.get("text")]
        # An icon on the cell's first line, then a break: the blank first line takes the icon's height. Slides gives a
        # bare paragraph break no line height of its own, so the line gets a space sized to the icon (a 1.2 em line at
        # the cell's 92% leading); the text then starts below the icon, as the HTML's does.
        lead = next((r for r in runs if not r.get("br")), None)
        cell_line_pct = max(70, round(cell.get("lineHeightPct", 120) / 1.3))
        if runs and runs[0].get("br") and runs[0].get("leadPt") and lead:
            # the blank line's height is the lead (pt): font size x 1.213 (Slides' single line) x the line spacing
            size = runs[0]["leadPt"] / (1.213 * cell_line_pct / 100.0)
            runs = [dict(lead, text=" ", size=round(size, 2), leadSpace=True)] + runs
        text = "".join(r["text"] for r in runs)
        if not text.strip():
            continue
        reqs.append({"insertText": {"objectId": tid, "cellLocation": loc,
            "text": text, "insertionIndex": 0}})
        pos = 0
        for r in runs:
            ln = u16len(r["text"])
            if r.get("br") or (not r["text"].strip() and not r.get("leadSpace")):
                pos += ln
                continue
            style, fields = _run_style(r)
            reqs.append({"updateTextStyle": {"objectId": tid, "cellLocation": loc,
                "textRange": {"type": "FIXED_RANGE", "startIndex": pos, "endIndex": pos + ln},
                "style": style, "fields": fields}})
            pos += ln
        line_pct = cell_line_pct
        reqs.append({"updateParagraphStyle": {"objectId": tid, "cellLocation": loc,
            "textRange": {"type": "ALL"},
            "style": {"alignment": cell.get("align", "START"), "lineSpacing": line_pct},
            "fields": "alignment,lineSpacing"}})
    return reqs

# The deck's own tokens for the colours this exporter draws itself (placeholders, emoji text).
# The Databricks values are only the fallback for a token the deck does not define; main()
# reads the deck's :root from assets/style.css (see read_root_tokens).
TOKENS = {"--db-oat-light": "#F9F7F4", "--db-ink-soft": "#5A6B72", "--db-ink-900": "#0B2026"}

def read_root_tokens(deck_dir):
    """The deck's :root colour tokens from assets/style.css, as {name: #RRGGBB}. Empty if none."""
    path = os.path.join(deck_dir or "", "assets", "style.css")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", errors="replace") as f:
        css = f.read()
    m = re.search(r":root\s*\{(.*?)\}", css, re.S)
    if not m:
        return {}
    out = {}
    for name, val in re.findall(r"(--db-[\w-]+)\s*:\s*([^;]+);", m.group(1)):
        val = val.split("/*")[0].strip()
        if re.fullmatch(r"#[0-9a-fA-F]{6}", val):
            out[name] = val.upper()
    return out

def element_label(el):
    """A short name for an image element: its alt text when the extractor sends it, else its
    file name, else what kind of graphic it is."""
    if el.get("alt"):
        return " ".join(str(el["alt"]).split())[:110]
    src = el.get("src") or ""
    if not src:
        return "inline chart or diagram"
    path = urllib.parse.unquote(urllib.parse.urlparse(src).path) if src.startswith("file://") else src
    return os.path.basename(path) or src

def placeholder_requests(el, page_id, sx, sy, eid, label):
    """A framed stand-in for an image that is not in the export: a dashed, oat-filled box
    with a short note, so a reader sees the gap and what belongs there. Small boxes get
    a shorter note (or none) so the text never spills out of the frame."""
    w, h = el["w"], el["h"]
    reqs = [{"createShape": {"objectId": eid, "shapeType": "RECTANGLE",
             "elementProperties": elem_props(page_id, el["x"], el["y"], w, h, sx, sy)}},
            {"updateShapeProperties": {"objectId": eid, "shapeProperties": {
                "shapeBackgroundFill": solid_fill(TOKENS["--db-oat-light"]),
                "outline": {"outlineFill": solid_fill(TOKENS["--db-ink-soft"]),
                            "weight": {"magnitude": 1.5 * EMU_PER_PT * 0.5625, "unit": "EMU"},
                            "dashStyle": "DASH"},
                "contentAlignment": "MIDDLE",
                "autofit": {"autofitType": "NONE"}},
                "fields": "shapeBackgroundFill.solidFill,outline,contentAlignment,autofit.autofitType"}}]
    if w >= 260 and h >= 60:
        msg, size = "Figure omitted from this export: %s. See the PDF." % label, 10
    elif w >= 90 and h >= 30:
        msg, size = "Image omitted", 8
    else:
        return reqs                       # too small for words: the frame alone (and the summary)
    reqs.append({"insertText": {"objectId": eid, "text": msg, "insertionIndex": 0}})
    reqs.append({"updateTextStyle": {"objectId": eid, "textRange": {"type": "ALL"},
        "style": {"fontFamily": "DM Sans", "fontSize": {"magnitude": size, "unit": "PT"},
                  "italic": True, "foregroundColor": {"opaqueColor": {"rgbColor": rgb(TOKENS["--db-ink-soft"])}}},
        "fields": "fontFamily,fontSize,italic,foregroundColor"}})
    reqs.append({"updateParagraphStyle": {"objectId": eid, "textRange": {"type": "ALL"},
        "style": {"alignment": "CENTER"}, "fields": "alignment"}})
    return reqs

# Every ShapeType the Slides API accepts (presentations.pages.shapeType, 143 values, from the
# discovery document at slides.googleapis.com). A name outside it is refused by the API.
SHAPE_TYPES = frozenset(
    ["ARC", "ARROW_EAST", "ARROW_NORTH", "ARROW_NORTH_EAST", "BENT_ARROW", "BENT_UP_ARROW", "BEVEL", "BLOCK_ARC", "BRACE_PAIR", "BRACKET_PAIR", "CAN", "CHEVRON", "CHORD", "CLOUD", "CLOUD_CALLOUT", "CORNER", "CUBE", "CURVED_DOWN_ARROW", "CURVED_LEFT_ARROW", "CURVED_RIGHT_ARROW", "CURVED_UP_ARROW", "CUSTOM", "DECAGON", "DIAGONAL_STRIPE", "DIAMOND", "DODECAGON", "DONUT", "DOUBLE_WAVE", "DOWN_ARROW", "DOWN_ARROW_CALLOUT", "ELLIPSE", "ELLIPSE_RIBBON", "ELLIPSE_RIBBON_2", "FLOW_CHART_ALTERNATE_PROCESS", "FLOW_CHART_COLLATE", "FLOW_CHART_CONNECTOR", "FLOW_CHART_DECISION", "FLOW_CHART_DELAY", "FLOW_CHART_DISPLAY", "FLOW_CHART_DOCUMENT", "FLOW_CHART_EXTRACT", "FLOW_CHART_INPUT_OUTPUT", "FLOW_CHART_INTERNAL_STORAGE", "FLOW_CHART_MAGNETIC_DISK", "FLOW_CHART_MAGNETIC_DRUM", "FLOW_CHART_MAGNETIC_TAPE", "FLOW_CHART_MANUAL_INPUT", "FLOW_CHART_MANUAL_OPERATION", "FLOW_CHART_MERGE", "FLOW_CHART_MULTIDOCUMENT", "FLOW_CHART_OFFLINE_STORAGE", "FLOW_CHART_OFFPAGE_CONNECTOR", "FLOW_CHART_ONLINE_STORAGE", "FLOW_CHART_OR", "FLOW_CHART_PREDEFINED_PROCESS", "FLOW_CHART_PREPARATION", "FLOW_CHART_PROCESS", "FLOW_CHART_PUNCHED_CARD", "FLOW_CHART_PUNCHED_TAPE", "FLOW_CHART_SORT", "FLOW_CHART_SUMMING_JUNCTION", "FLOW_CHART_TERMINATOR", "FOLDED_CORNER", "FRAME", "HALF_FRAME", "HEART", "HEPTAGON", "HEXAGON", "HOME_PLATE", "HORIZONTAL_SCROLL", "IRREGULAR_SEAL_1", "IRREGULAR_SEAL_2", "LEFT_ARROW", "LEFT_ARROW_CALLOUT", "LEFT_BRACE", "LEFT_BRACKET", "LEFT_RIGHT_ARROW", "LEFT_RIGHT_ARROW_CALLOUT", "LEFT_RIGHT_UP_ARROW", "LEFT_UP_ARROW", "LIGHTNING_BOLT", "MATH_DIVIDE", "MATH_EQUAL", "MATH_MINUS", "MATH_MULTIPLY", "MATH_NOT_EQUAL", "MATH_PLUS", "MOON", "NOTCHED_RIGHT_ARROW", "NO_SMOKING", "OCTAGON", "PARALLELOGRAM", "PENTAGON", "PIE", "PLAQUE", "PLUS", "QUAD_ARROW", "QUAD_ARROW_CALLOUT", "RECTANGLE", "RIBBON", "RIBBON_2", "RIGHT_ARROW", "RIGHT_ARROW_CALLOUT", "RIGHT_BRACE", "RIGHT_BRACKET", "RIGHT_TRIANGLE", "ROUND_1_RECTANGLE", "ROUND_2_DIAGONAL_RECTANGLE", "ROUND_2_SAME_RECTANGLE", "ROUND_RECTANGLE", "SMILEY_FACE", "SNIP_1_RECTANGLE", "SNIP_2_DIAGONAL_RECTANGLE", "SNIP_2_SAME_RECTANGLE", "SNIP_ROUND_RECTANGLE", "SPEECH", "STARBURST", "STAR_10", "STAR_12", "STAR_16", "STAR_24", "STAR_32", "STAR_4", "STAR_5", "STAR_6", "STAR_7", "STAR_8", "STRIPED_RIGHT_ARROW", "SUN", "TEARDROP", "TEXT_BOX", "TRAPEZOID", "TRIANGLE", "TYPE_UNSPECIFIED", "UP_ARROW", "UP_ARROW_CALLOUT", "UP_DOWN_ARROW", "UTURN_ARROW", "VERTICAL_SCROLL", "WAVE", "WEDGE_ELLIPSE_CALLOUT", "WEDGE_RECTANGLE_CALLOUT", "WEDGE_ROUND_RECTANGLE_CALLOUT"])

def _num(el, key, default=0.0):
    """A numeric IR field, or the default when it is missing or null (the extractor never sends null for these, but a
    null must not crash the build: it did, on slide 68, in the round-5 export)."""
    v = el.get(key)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else float(default)

LIST_GOOGLE_BIAS = 4.8   # Google sets a list's first line this far below the HTML's (measured, every list alike)
LIST_INDENT_PT = 19   # the indent of a native bullet's text (the dot at ~6 px, the text ~34 px from the box edge)

def list_top_shift(el):
    """How far a bulleted text box moves up, in design px, so Google's first line lands where the HTML's does.
    The shift is measured on Google, the target. PowerPoint adds a percentage line spacing's extra space above a
    list's first line (about 21 px at 180% and 22 px); that is a known PowerPoint limit,
    not compensated here. 0 for text that is not a list."""
    pitch = el.get("itemPitch")
    lines = el.get("itemLines")
    if not pitch or not lines or len(pitch) != len(lines):
        return 0.0
    return LIST_GOOGLE_BIAS

def slides_text_width(el):
    """The width this run needs in Slides, in design px. The HTML measure (tw) includes its letter-spacing; Slides
    has no tracking, so a tight title (letter-spacing -0.02em) is wider by the tracking it removed."""
    return _num(el, "tw", el["w"]) - _num(el, "nch") * _num(el, "ls")

def is_single_line(el):
    """One line in the HTML: the line count is measured from the glyphs; oneLine is the box-height fallback."""
    lines = el.get("htmlLines")
    if isinstance(lines, (int, float)):
        return lines == 1
    return bool(el.get("oneLine"))

def build_slide_requests(ir_slide, page_id, sx, sy, oid, slide_no=0):
    reqs = []
    n = [0]
    def nid(p):
        n[0] += 1
        return "%s_%s%d" % (oid, p, n[0])
    groups = {}   # native-SVG diagram id -> object ids, grouped at the end

    # background
    if ir_slide.get("background"):
        reqs.append({"updatePageProperties": {
            "objectId": page_id,
            "pageProperties": {"pageBackgroundFill": solid_fill(ir_slide["background"])},
            "fields": "pageBackgroundFill.solidFill.color"}})

    for el in ir_slide["elements"]:
        if el["type"] == "emoji" and not el.get("_fid"):
            # no picture for this glyph (images left out, or it failed): keep the glyph as live
            # text, which Slides draws with the system emoji font
            el = dict(el, type="text", align="CENTER", valign="MIDDLE",
                      runs=[{"text": el["text"], "font": "DM Sans", "color": TOKENS["--db-ink-900"],
                             "size": round(el.get("fontPx", 40) * 0.5625, 1)}])
        t = el["type"]
        if t == "table":
            reqs.extend(build_table_requests(el, page_id, sx, sy, nid))
        elif t == "rect":
            eid = nid("r")
            if el.get("group"):
                groups.setdefault(el["group"], []).append(eid)
            if el.get("ellipse"):
                shape = "ELLIPSE"
            elif el.get("radius", 0) > 3 and not (
                    # Slides draws ROUND_RECTANGLE corners at 1/6 of the shorter side and the API cannot
                    # set it (the default adjust). So the closest look is chosen: a rounded rect when the HTML
                    # radius is nearer 1/6 of the shorter side than to 0, else a plain rectangle. For a
                    # native-SVG box whose radius is far smaller (rx=10 on a big zone) that over-rounds, so
                    # it is squared off as before.
                    (el.get("native") and min(el["w"], el["h"]) / 6.0 > el["radius"] * 2.5) or
                    el["radius"] < min(el["w"], el["h"]) / 12.0):
                shape = "ROUND_RECTANGLE"
            else:
                shape = "RECTANGLE"
            if el.get("shape"):
                name = str(el["shape"]).upper()
                if name in SHAPE_TYPES:
                    shape = name
                else:
                    print("  ! shape %r is not a Slides shape type; a rectangle is used" % name, file=sys.stderr)
            if el.get("clipMismatch"):
                # the HTML clip-path is not a Slides preset, so the API can only draw a rectangle here
                print("  ! slide %d: %s; drawn as a rectangle" % (slide_no, el["clipMismatch"]), file=sys.stderr)
            # Slides centres an outline on the shape's edge; the HTML border is drawn inside the box. Inset the
            # shape by half the border weight so the outline lies where the browser draws it (a 1 px card border
            # otherwise sticks half a pixel out of its box on every side).
            rx, ry, rw, rh = el["x"], el["y"], el["w"], el["h"]
            if el.get("border"):
                half = max(1, el["border"]["weight"]) / 2.0
                rx, ry, rw, rh = rx + half, ry + half, max(0.5, rw - 2 * half), max(0.5, rh - 2 * half)
            reqs.append({"createShape": {"objectId": eid, "shapeType": shape,
                "elementProperties": elem_props(page_id, rx, ry, rw, rh, sx, sy)}})
            props, fields = {}, []
            if el.get("fill"):
                props["shapeBackgroundFill"] = solid_fill(el["fill"], el.get("fillAlpha", 1))
                fields.append("shapeBackgroundFill.solidFill")
            else:
                props["shapeBackgroundFill"] = {"solidFill": {"alpha": 0}}
                fields.append("shapeBackgroundFill")
            if el.get("shadow"):
                # a CSS box-shadow the extractor could read: {"blur", "dx", "dy" (design px), "color", "alpha"}
                # Slides marks Shadow.type, transform, alignment and rotateWithShape read-only
                # (Shadow resource, presentations.pages reference), so they are not sent: the
                # writable blurRadius, color and alpha are, plus propertyState RENDERED. The
                # CSS offset (dx, dy) is therefore not carried; the blur, colour and alpha are.
                sh = el["shadow"]
                props["shadow"] = {"propertyState": "RENDERED",
                                   "blurRadius": {"magnitude": max(0.0, sh.get("blur", 0)) * 0.5625, "unit": "PT"},
                                   "color": {"rgbColor": rgb(sh.get("color", "#000000"))},
                                   "alpha": sh.get("alpha", 0.15)}
                fields.append("shadow")
            if el.get("border"):
                b = el["border"]
                # Design px → pt uses 0.5625 (1280 px → a 720-pt Slides page),
                # matching pxToPt/emu_scale — not the 0.75 screen factor.
                props["outline"] = {"outlineFill": solid_fill(b["color"], b.get("alpha", 1.0)),
                                    "weight": {"magnitude": max(1, b["weight"]) * EMU_PER_PT * 0.5625, "unit": "EMU"},
                                    "dashStyle": b.get("dash", "SOLID")}
                fields.append("outline")
            else:
                props["outline"] = {"propertyState": "NOT_RENDERED"}
                fields.append("outline.propertyState")
            reqs.append({"updateShapeProperties": {"objectId": eid,
                "shapeProperties": props, "fields": ",".join(fields)}})

        elif t == "line":
            # Native line (from a data-gs="native" SVG). A Slides line runs from the
            # top-left to the bottom-right of its box, so flip the box (negative
            # scale) for lines that run left or up; 1 EMU stands in for a zero side.
            eid = nid("l")
            if el.get("group"):
                groups.setdefault(el["group"], []).append(eid)
            dx, dy = el["x2"] - el["x1"], el["y2"] - el["y1"]
            reqs.append({"createLine": {"objectId": eid, "lineCategory": "STRAIGHT",
                "elementProperties": {
                    "pageObjectId": page_id,
                    "size": {"width": {"magnitude": max(1, abs(dx) * sx), "unit": "EMU"},
                             "height": {"magnitude": max(1, abs(dy) * sy), "unit": "EMU"}},
                    "transform": {"scaleX": -1 if dx < 0 else 1, "scaleY": -1 if dy < 0 else 1,
                                  "translateX": el["x1"] * sx, "translateY": el["y1"] * sy,
                                  "unit": "EMU"}}}})
            reqs.append({"updateLineProperties": {"objectId": eid, "lineProperties": {
                "lineFill": solid_fill(el["color"], el.get("alpha", 1.0)),
                "weight": {"magnitude": max(0.75, el.get("weight", 1) * 0.5625) * EMU_PER_PT, "unit": "EMU"},
                "dashStyle": el.get("dash", "SOLID"),
                "startArrow": el.get("startArrow", "NONE"),
                "endArrow": el.get("endArrow", "NONE")},
                "fields": "lineFill,weight,dashStyle,startArrow,endArrow"}})

        elif t == "image" and not el.get("_fid"):
            # left out (--no-images, or the upload failed): a labelled frame, and it goes in the summary
            eid = nid("ph")
            if el.get("group"):
                groups.setdefault(el["group"], []).append(eid)
            label = element_label(el)
            why = el.get("_why") or ("left out by --no-images" if not IMAGES_ENABLED else "not available")
            if el["w"] >= DESIGN_W * 0.95 and el["h"] >= DESIGN_H * 0.95:
                # a full-slide decoration: a framed box over the whole slide would hide the slide, so it is
                # left undrawn (the slide's own background stays) and the summary says so
                OMITTED.append({"slide": slide_no, "label": label,
                                "why": "full-slide decoration, not drawn (%s)" % why})
            else:
                OMITTED.append({"slide": slide_no, "label": label, "why": why})
                reqs.extend(placeholder_requests(el, page_id, sx, sy, eid, label))

        elif t == "image" or t == "emoji":
            fid = el.get("_fid")
            if not fid:
                continue
            eid = nid("i")
            if el.get("group"):
                groups.setdefault(el["group"], []).append(eid)
            reqs.append({"createImage": {"objectId": eid, "url": image_url(fid),
                "elementProperties": elem_props(page_id, el["x"], el["y"], el["w"], el["h"], sx, sy)}})

        elif t == "text":
            runs = [r for r in el["runs"] if r.get("text")]
            # a leading line break after blank text (the HTML collapses it) is an empty first paragraph in Slides, one
            # line tall: the closing block of slide 96 started 22 px low for it. Drop leading blank text and breaks.
            while runs and (runs[0].get("br") or not runs[0]["text"].strip()):
                runs = runs[1:]
            if not runs:
                continue
            if el.get("pre"):
                # code and terminals: every space is the author's indentation. Slides drops a plain leading space
                # at the start of a line, so each leading space becomes a no-break space (same width, kept).
                def _keep_indent(text):
                    return "\n".join("\u00a0" * (len(p_) - len(p_.lstrip(" "))) + p_.lstrip(" ") for p_ in text.split("\n"))
                runs = [r if r.get("br") else dict(r, text=_keep_indent(r["text"])) for r in runs]
            else:
                for i in range(1, len(runs)):
                    # the HTML indent after a line break (e.g. "Jane Doe<br> VP of Data") is not text
                    if runs[i - 1].get("br"):
                        runs[i] = dict(runs[i], text=runs[i]["text"].lstrip(" \t"))
            eid = nid("t")
            if el.get("group"):
                groups.setdefault(el["group"], []).append(eid)
            align = el.get("align", "START")
            # Slides text boxes have default internal insets (~0.1" L/R, 0.05"
            # T/B) that shift text inward AND narrow the usable width. Grow the
            # box by the inset on every side so the text content area coincides
            # with the HTML element rect.
            ix = INSET_LR / sx  # inset expressed back in design px
            iy = INSET_TB / sy
            # Slides' font metrics run a hair wider than the browser's, so text
            # that was one line (or N lines) can re-wrap and overflow (splitting
            # "92%" or a headline into the subtitle). Give the box extra width —
            # generous for single-line, modest for multi-line — anchored so the
            # text keeps its position for its alignment.
            # Scale it by font size: big display text (titles, stats) lives in
            # open space and suffers most from re-wrap, while small body text
            # must stay tight so it doesn't bleed into an adjacent column.
            big = el.get("fontPx", 16) >= 38
            if el.get("noWrap"):
                # nowrap/pre must never re-wrap — a single-word pill or code line
                # only needs to clear Slides' slightly wider metrics.
                slack = max(el["w"] * 0.5, 70)
            elif is_single_line(el):
                # a one-line run (any size) must hold its text at Slides' wider metrics (DM Sans measures 14-22%
                # wider there, and tight tracking is not in Slides): widen to the Slides width x 1.2
                # small labels get a little more headroom (1.3): a PowerPoint copy substitutes the font and wraps at 1.2
                slack = max(el["w"] * 0.35, 130) if big else max(el["w"] * 0.12, slides_text_width(el) * 1.3 - el["w"])
            else:
                # Multi-line text ALREADY wraps. Extra usable width lets those
                # lines re-flow LONGER than the HTML (fewer, wider lines), which
                # then collides with whatever the layout kept clear — e.g. a
                # card's corner number badge, or the next column. Keep the HTML
                # wrap width (slack 0) so it breaks at the same points; only big
                # display text (open space, no neighbours) keeps a little slack.
                slack = el["w"] * 0.18 if big else 0
                if not big and _num(el, "htmlLines", 1) > 1:
                    # a small paragraph that wraps in the HTML: Slides' wider glyphs need a little more width per line or
                    # the last word goes to a new line (96, 30, 46, 47, 49). Capped at 15% so the wrap points stay close.
                    slack = min(el["w"] * 0.15, max(0.0, slides_text_width(el) * 1.2 - el["w"]))
                if slack and any(o is not el and o.get("type") in ("image", "rect") and
                                 not (o["x"] <= el["x"] + 1 and o["x"] + o["w"] >= el["x"] + el["w"] - 1) and   # a card around the text is not an obstacle
                                 o["x"] < el["x"] + el["w"] + slack and o["x"] + o["w"] > el["x"] + el["w"] and
                                 o["y"] < el["y"] + el["h"] and o["y"] + o["h"] > el["y"]
                                 for o in ir_slide["elements"]):
                    # a picture or panel sits in the strip the slack would take: the HTML break stays
                    slack = 0
            if align == "CENTER":
                ox = el["x"] - ix - slack / 2
            elif align == "END":
                ox = el["x"] - ix - slack
            else:
                ox = el["x"] - ix
            bw = el["w"] + 2 * ix + slack
            # A list whose items draw their own markers (no native bullet) starts its text at the HTML's text x, with no
            # indent. A bulleted list takes LIST_INDENT_PT before its text, so the box gives that width back here: the
            # lines break where they did with the indent (the same width of text per line as before).
            if any(r.get("list") for r in runs) and not any(r.get("list") and r.get("bullet", True) for r in runs):
                bw -= LIST_INDENT_PT / 0.5625
            # The slack must never push the box off the slide: Slides does not wrap
            # past it, so a full-width title would run off the edge. Clamp to the page
            # (never narrower than the HTML box); a headline then re-wraps instead.
            edge = 6.0
            if ox < edge:
                bw -= edge - ox; ox = edge
            # a one-line display title stays inside the slide's 80 px margin (the page margin of every layout),
            # so the shrink below fits it there instead of letting it run to the page edge
            if el.get("oneLine") and big:
                bw = min(bw, DESIGN_W - 80.0 - ox)      # the margin wins; the shrink below fits the text to it
            else:
                bw = max(min(bw, DESIGN_W - edge - ox), el["w"] + 2 * ix)
            # A one-line headline whose glyphs, at Slides' wider metrics (DM Sans
            # measures up to ~15% wider there than in Chrome), no longer fit the
            # clamped box would wrap onto the line below (the subtitle). Scale just
            # that text down so it stays on one line.
            if el.get("oneLine") and big and not el.get("noWrap"):
                # Slides sets DM Sans 14-22% wider than the browser (measured on the 2026-10 snapshots)
                need, room = slides_text_width(el) * 1.2, bw - 2 * ix
                if need > room:
                    k = room / need
                    for r in el.get("runs", []):
                        r["size"] = round(r.get("size", 12) * k, 1)
            elif big and not el.get("noWrap") and _num(el, "htmlLines", 1) > 1 and el.get("tw"):
                # a display title that wraps in the HTML: Slides' wider glyphs (and no tracking) would wrap it onto
                # more lines. Scale the size so the whole text fits in the HTML's own line count at this box width.
                room = bw - 2 * ix
                lines = max(1, int(_num(el, "htmlLines", 1)))
                # the widest HTML line, with the tracking the HTML removed from its characters added back
                line_w = _num(el, "tw", el["w"]) - (_num(el, "nch") / lines) * _num(el, "ls")
                need = line_w * 1.15
                if need > room:
                    k = room / need
                    for r in el.get("runs", []):
                        r["size"] = round(r.get("size", 12) * k, 1)
            reqs.append({"createShape": {"objectId": eid, "shapeType": "TEXT_BOX",
                "elementProperties": elem_props(page_id, ox, el["y"] - iy - list_top_shift(el),
                                                bw, el["h"] + 2 * iy, sx, sy)}})
            # transparent box, no outline, vertical alignment from the source,
            # no autofit (never shrink text to fit).
            reqs.append({"updateShapeProperties": {"objectId": eid, "shapeProperties": {
                "outline": {"propertyState": "NOT_RENDERED"},
                "contentAlignment": el.get("valign", "MIDDLE"),
                "autofit": {"autofitType": "NONE"}},
                "fields": "outline.propertyState,contentAlignment,autofit.autofitType"}})
            text = "".join(r["text"] for r in runs)
            reqs.append({"insertText": {"objectId": eid, "text": text, "insertionIndex": 0}})
            # per-run styling
            pos = 0
            for r in runs:
                ln = u16len(r["text"])
                if r.get("br") or not r["text"].strip():
                    pos += ln
                    continue
                style, fields = _run_style(r)
                reqs.append({"updateTextStyle": {"objectId": eid,
                    "textRange": {"type": "FIXED_RANGE", "startIndex": pos, "endIndex": pos + ln},
                    "style": style, "fields": fields}})
                pos += ln
            # paragraph alignment + line spacing. Google Slides lineSpacing:100
            # ≈ 1.2× font (its "single"), NOT CSS line-height:1.0 — so a CSS
            # ratio must be scaled down or multi-line titles render too tall and
            # collide with what sits below them.
            line_pct = max(70, round(el.get("lineHeightPct", 120) / 1.3))
            reqs.append({"updateParagraphStyle": {"objectId": eid,
                "textRange": {"type": "ALL"},
                "style": {"alignment": align,
                          "lineSpacing": line_pct},
                "fields": "alignment,lineSpacing"}})
            # Native bullets: any paragraph whose runs came from an <li> becomes a
            # real Slides list item (editable, reflows) instead of a drawn dot. Map
            # runs -> paragraphs (split on the hard '\n' breaks), keeping each
            # paragraph's UTF-16 range and whether it is a list item.
            paras, pos = [], 0
            cur = {"start": 0, "list": False, "ordered": False, "bullet": True}
            for r in runs:
                ln = u16len(r["text"])
                if r.get("br"):
                    cur["end"] = pos
                    paras.append(cur)
                    pos += ln
                    cur = {"start": pos, "list": False, "ordered": False, "bullet": True}
                else:
                    if r.get("list"):
                        cur["list"] = True
                        cur["ordered"] = r.get("ordered", False)
                        cur["bullet"] = r.get("bullet", True)
                    pos += ln
            cur["end"] = pos
            paras.append(cur)
            # Group consecutive list paragraphs of the same kind (ordered, and bulleted or not) into one range and
            # bullet each group; indent to match the template (dot ~6px, text ~34px). An item whose marker the HTML
            # draws itself has no native bullet and no indent: its text starts where the HTML's text does.
            i = 0
            while i < len(paras):
                if not paras[i]["list"]:
                    i += 1
                    continue
                j = i
                ordered, bulleted = paras[i]["ordered"], paras[i]["bullet"]
                while (j + 1 < len(paras) and paras[j + 1]["list"] and paras[j + 1]["ordered"] == ordered
                       and paras[j + 1]["bullet"] == bulleted):
                    j += 1
                rng = {"type": "FIXED_RANGE", "startIndex": paras[i]["start"],
                       "endIndex": max(paras[i]["start"] + 1, paras[j]["end"])}
                if bulleted:
                    preset = "NUMBERED_DIGIT_ALPHA_ROMAN" if ordered else "BULLET_DISC_CIRCLE_SQUARE"
                    reqs.append({"createParagraphBullets": {"objectId": eid,
                        "textRange": rng, "bulletPreset": preset}})
                # The list's indents (the dot at 6 px, the text at 34 px). The spacing is per item below.
                indents = ({"indentStart": {"magnitude": 19, "unit": "PT"},          # LIST_INDENT_PT
                            "indentFirstLine": {"magnitude": 3.4, "unit": "PT"}} if bulleted else
                           {"indentStart": {"magnitude": 0, "unit": "PT"},
                            "indentFirstLine": {"magnitude": 0, "unit": "PT"}})
                reqs.append({"updateParagraphStyle": {"objectId": eid, "textRange": rng,
                    "style": indents, "fields": "indentStart,indentFirstLine"}})
                # Slides ignores paragraph spacing (spaceAbove / spaceBelow) on bulleted paragraphs, measured on a
                # scratch deck (FIX-gslides-visual.md, section 13), and honours line spacing. Each item therefore gets
                # line spacing = its HTML pitch / its HTML line count: the item pitch comes out exact, and a
                # one-line item in the HTML (the common case) keeps its one line. 100% in Slides is the font's
                # single line, 1.213 x the font size (measured on the same deck: 26.7 px for 22 px text).
                item_pitch = el.get("itemPitch") or []
                item_lines = el.get("itemLines") or []
                font_px = _num(el, "itemFontPx", _num(el, "fontPx", 16))
                for k_ in range(i, j + 1):
                    item_no = sum(1 for q in paras[:k_] if q["list"])
                    style = {"lineSpacing": 120}
                    if item_no < len(item_pitch) and item_no < len(item_lines) and len(item_pitch) == len(item_lines):
                        # the last item has no measured pitch to the next: it keeps the line spacing of the one before
                        src_k = item_no if item_no < len(item_pitch) - 1 or len(item_pitch) == 1 else item_no - 1
                        per_line = item_pitch[src_k] / max(1, item_lines[src_k])
                        style = {"lineSpacing": round(max(50.0, min(400.0, per_line / (font_px * 1.213) * 100.0)), 1)}
                    reqs.append({"updateParagraphStyle": {"objectId": eid, "textRange": {"type": "FIXED_RANGE",
                        "startIndex": paras[k_]["start"], "endIndex": max(paras[k_]["start"] + 1, paras[k_]["end"])},
                        "style": style, "fields": "lineSpacing"}})
                i = j + 1
    # Group each native-SVG diagram so it moves / scales as one object in Slides
    # (ungroup to edit a part; the shapes themselves stay native and editable).
    for gi, ids in enumerate(groups.values()):
        if len(ids) >= 2:
            reqs.append({"groupObjects": {"groupObjectId": "%s_g%d" % (oid, gi + 1),
                                          "childrenObjectIds": ids}})
    return reqs

def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def flatten_on(png_bytes, bg_hex, w, h):
    """Composite a transparent PNG onto a solid colour (headless Chrome). Returns PNG bytes or None.
    A transparent pixel is stored as black, and Slides blends that black into every edge, which
    draws a dark outline around shapes on a coloured slide; flattening onto the slide's own
    background removes it."""
    import tempfile, base64 as _b64
    td = tempfile.mkdtemp(prefix="gs_flat_")
    src, out, page = os.path.join(td, "in.png"), os.path.join(td, "out.png"), os.path.join(td, "f.html")
    with open(src, "wb") as f:
        f.write(png_bytes)
    W, H = max(1, int(round(w * 2))), max(1, int(round(h * 2)))
    with open(page, "w") as f:
        f.write('<!doctype html><meta charset="utf-8"><body style="margin:0;background:%s">'
                '<img src="file://%s" style="display:block;width:%dpx;height:%dpx"></body>'
                % (bg_hex, src, W, H))
    if not _chrome_screenshot(CHROME, page, W, H, out):
        return None
    with open(out, "rb") as f:
        return f.read()

def flatten_for_upload(el, bg):
    """A full-slide graphic is flattened onto the slide's colour so its edges are clean. An overlay (a gradient
    scrim, marked `overlay` by the extractor) is never flattened: it is translucent and must keep its alpha over
    the photo beneath it. Returns True when the element's data was flattened."""
    if el.get("type") != "image" or not el.get("data") or not bg or el.get("overlay"):
        return False
    if el.get("w", 0) < DESIGN_W * 0.95 or el.get("h", 0) < DESIGN_H * 0.95:
        return False
    flat = flatten_on(base64.b64decode(el["data"].split(",", 1)[1]), bg, el["w"], el["h"])
    if not flat:
        return False
    el["data"] = "data:image/png;base64," + base64.b64encode(flat).decode("ascii")
    return True

def pre_upload_images(ir):
    """Upload every image up front so Drive permissions have propagated before the Slides
    image-fetcher reads them. Stashes the Drive id on each element (`_fid`), or the reason
    it has none (`_why`), which the placeholder and the run summary report."""
    n = 0
    for s in ir["slides"]:
        bg = s.get("background")
        for el in s["elements"]:
            flatten_for_upload(el, bg)
            if el["type"] == "image":
                try:
                    el["_fid"] = resolve_image(el)
                    if el["_fid"]:
                        n += 1
                    else:
                        el["_why"] = "not found, or a format Slides cannot read"
                        print("  ! image skipped — not found/unsupported (%s)"
                              % (el.get("src") or "inline"), file=sys.stderr)
                except Exception as ex:
                    el["_fid"] = None
                    el["_why"] = "upload failed: %s" % str(ex).splitlines()[0][:200]
                    print("  ! image skipped (%s): %s" % (el.get("src") or "inline", ex), file=sys.stderr)
            elif el["type"] == "emoji":
                try:
                    raw = _chrome_emoji_to_png(el["text"], el.get("w", 40), el.get("h", 40),
                                               el.get("fontPx", 40))
                    if raw:
                        key = hashlib.sha1(("emoji|%s|%dx%d" % (el["text"], int(el.get("w", 40)),
                                                                int(el.get("h", 40)))).encode()).hexdigest()
                        el["_fid"] = upload_bytes(raw, "image/png", key)
                        if el["_fid"]:
                            n += 1
                    else:
                        el["_fid"] = None
                except Exception as ex:
                    el["_fid"] = None   # the glyph stays as text; say so
                    print("  ! emoji %r kept as text (%s)" % (el.get("text"), ex), file=sys.stderr)
    return n

def created_ids(requests):
    """The objectIds a batch creates (slides, shapes, images, lines, tables, groups). Our ids are
    deterministic, so these show whether the batch reached the deck."""
    ids = []
    for r in requests:
        for kind, body in r.items():
            if kind in ("createSlide", "createShape", "createImage", "createLine", "createTable"):
                ids.append(body["objectId"])
            elif kind == "groupObjects":
                ids.append(body["groupObjectId"])
    return ids

def deck_ids(doc):
    """Every objectId in a presentation read back, groups' children included."""
    out = set()
    def walk(elements):
        for e in elements:
            out.add(e.get("objectId"))
            if "elementGroup" in e:
                walk(e["elementGroup"].get("children", []))
    for sl in doc.get("slides", []):
        out.add(sl.get("objectId"))
        walk(sl.get("pageElements", []))
    return out

class DeckWriter:
    """Every batchUpdate of one presentation, and every read of its revision, in one place (the Slides twin of the
    dbx-docs DocWriter). Each batch carries writeControl.requiredRevisionId = the latest revision known here: seeded
    once the presentation exists, advanced from each batchUpdate response and from each read (reads ask for
    revisionId). Google applies a pinned batch only while the deck is still at that revision (otherwise 400
    FAILED_PRECONDITION), so the original of an unsure batch and its resend cannot both apply. A refused batch is never
    rebased.

    After an UnsureWrite the deck is read back once (_confirm):
      - revision still the pin: nothing has applied. The batch is sent again at the same pin (after a wait).
      - revision moved: the batch is there when every object it creates is there (the ids are unique to the batch).
        A text-only batch creates nothing, so it cannot be checked and stops; so does a partial one.
    A refusal on the pin after an UnsureWrite is read back the same way; a refusal on a normal write stops at once.
    """
    def __init__(self, pid):
        self.pid = pid
        self.url = "https://slides.googleapis.com/v1/presentations/%s" % pid
        self.rev = None

    def read(self, fields=None):
        """GET the presentation (fields: a field mask, or the whole deck when None); its revision is kept."""
        url = self.url if fields is None else "%s?fields=%s,revisionId" % (self.url, fields)
        doc = api("GET", url)
        if doc.get("revisionId"):
            self.rev = doc["revisionId"]
        return doc

    def seed(self):
        self.read("presentationId")
        if not self.rev:
            raise RuntimeError("Google did not return the revision of the presentation %s" % self.pid)

    def _send(self, pin, requests):
        try:
            resp = api("POST", self.url + ":batchUpdate",
                       body={"requests": requests, "writeControl": {"requiredRevisionId": pin}})
        except UnsureWrite:
            raise
        except RuntimeError as e:
            if _is_precondition(e):
                raise DocumentChanged("Google refused an update because the deck changed during the export (it is no "
                                      "longer at revision %s; the request was not applied and was not rebased: %s). "
                                      "Delete the half-built file (https://docs.google.com/presentation/d/%s/edit) and "
                                      "run the export again." % (pin, " ".join(str(e).split())[:600], self.pid))
            raise
        self.rev = ((resp or {}).get("writeControl") or {}).get("requiredRevisionId")
        return resp

    def _confirm(self, pin, ids):
        """'not_applied' (the revision is still the pin), 'applied' (it moved and every created object is there),
        'partial' or 'unknown' (stop). One read, which also refreshes the revision."""
        try:
            doc = self.read()
        except RuntimeError:
            return "unknown"
        if self.rev == pin:
            return "not_applied"
        if not ids:
            return "unknown"            # text-only: nothing to look for
        have = [i in deck_ids(doc) for i in ids]
        if all(have):
            return "applied"
        return "partial" if any(have) else "unknown"

    def batch(self, requests, resend=True):
        """One pinned batchUpdate; returns its response, or {} when the read-back shows it applied. resend=False
        (the one-at-a-time fallback) sends once: an UnsureWrite stops without a read."""
        ids = created_ids(requests)
        attempts = 4 if resend else 1
        unsure = None
        for attempt in range(attempts):
            if self.rev is None:
                self.seed()
            pin = self.rev
            try:
                return self._send(pin, requests)
            except DocumentChanged:
                if unsure is None:
                    raise               # a normal write refused: the deck changed during the export
                if self._confirm(pin, ids) == "applied":
                    print("    (the deck has this batch from the failed request: continuing)", file=sys.stderr)
                    return {}
                raise unsure
            except UnsureWrite as err:
                if not resend:
                    raise
                unsure = err
                state = self._confirm(pin, ids)
                if state == "applied":
                    print("    (Google answered with an error, but the deck has this batch: continuing)",
                          file=sys.stderr)
                    return {}
                if state == "not_applied" and attempt < attempts - 1:
                    wait = 5 * (attempt + 1)
                    print("    (Google answered with an error and the deck has not changed: sending the batch again "
                          "at the same revision in %ds ...)" % wait, file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise
        raise unsure

_WRITERS = {}

def writer_for(pid):
    """The DeckWriter of one presentation (one per run, so every batch of the deck shares its revision)."""
    if pid not in _WRITERS:
        _WRITERS[pid] = DeckWriter(pid)
    return _WRITERS[pid]

# A batch with a createImage that Google answers with a 400 saying it could not fetch the image is retried after these
# waits (seconds): the image was uploaded and shared a moment before Google read it. Any other 400 is final.
FETCH_RETRY_WAITS = (4, 8)
_FETCH_400 = re.compile(r"HTTP 400\b.*(?:retriev|fetch|download|read|access|load)\w*\b.*\bimage|"
                        r"image\b.*(?:could not|cannot|unable to|failed to)\s+(?:be\s+)?(?:retriev|fetch|download|read|access|load)", re.I)

def is_image_fetch_refusal(err):
    """True when err is Google's 400 that it could not fetch an image (not a 5xx, not another 400). The API error is
    several lines (the JSON body), so the search runs on the whole error with its whitespace collapsed."""
    if isinstance(err, (UnsureWrite, DocumentChanged)):
        return False
    return bool(_FETCH_400.search(" ".join(str(err).split())))

def is_bad_request(err):
    return not isinstance(err, (UnsureWrite, DocumentChanged)) and "HTTP 400" in str(err)

def log_full_error(label, err):
    """The whole API error (its JSON body too) to stderr, so export.log keeps the reason a request was refused."""
    print("    %s refused by Google:\n      %s" % (label, "\n      ".join(str(err).splitlines())), file=sys.stderr)

def _post_batch(pid, requests):
    """One batchUpdate, pinned and recovered by the deck's DeckWriter (see DeckWriter.batch)."""
    return writer_for(pid).batch(requests)

def batch_update(pid, requests, tolerate_images=True):
    """Send a batchUpdate. A 400 that says Google could not fetch an image is retried after FETCH_RETRY_WAITS; the
    last refusal keeps its full reason. Any other 400 is not retried. Any other failure is retried once after 3 s.
    Then the requests are sent one at a time, so a single bad image can't sink the whole slide. A rejected batch
    applies nothing, so none of these retries can duplicate content. A 5xx or an UnsureWrite is never retried here."""
    try:
        return _post_batch(pid, requests)
    except (UnsureWrite, DocumentChanged):
        raise                # may be applied: resending (or one at a time) would duplicate; a changed deck stops
    except RuntimeError as e:
        if is_image_fetch_refusal(e):
            last = e
            for attempt, wait in enumerate(FETCH_RETRY_WAITS, 1):
                print("  Google could not fetch an image (attempt %d of %d); retrying in %ds: %s"
                      % (attempt, len(FETCH_RETRY_WAITS) + 1, wait, " ".join(str(last).split())[:300]), file=sys.stderr)
                time.sleep(wait)
                try:
                    return _post_batch(pid, requests)
                except (UnsureWrite, DocumentChanged):
                    raise
                except RuntimeError as e2:
                    last = e2
                    if not is_image_fetch_refusal(e2):
                        break
            log_full_error("batch (image fetch, after %d retries)" % len(FETCH_RETRY_WAITS), last)
            if not tolerate_images:
                raise last
        elif is_bad_request(e):
            # any other 400 fails at once: no retry; the reason is logged in full
            log_full_error("batch", e)
            if not tolerate_images:
                raise
        else:
            time.sleep(3)  # give Drive permissions a moment, then retry the batch
            try:
                return _post_batch(pid, requests)
            except (UnsureWrite, DocumentChanged):
                raise
            except RuntimeError as e3:
                if not tolerate_images:
                    raise
                log_full_error("batch (after a retry)", e3)
    # fall back: apply individually, skipping the ones that fail (and say so in the summary)
    ok, bad, first = 0, 0, None
    for r in requests:
        try:
            writer_for(pid).batch([r], resend=False)
            ok += 1
        except (UnsureWrite, DocumentChanged):
            raise
        except RuntimeError as e:
            bad += 1
            log_full_error("request %s" % next(iter(r), "?"), e)
            first = first or str(e).splitlines()[0][:300]
    if bad:
        print("    (%d/%d requests applied, %d skipped)" % (ok, ok + bad, bad), file=sys.stderr)
        SKIPPED.append((bad, first))
    return {}


def save_snapshot(file_id, path):
    """Save Google's own PDF rendering of the new file, to look at what Google drew."""
    try:
        pdf = api("GET", "https://www.googleapis.com/drive/v3/files/%s/export?mimeType=application/pdf"
                  % file_id, binary=True)
        with open(path, "wb") as f:
            f.write(pdf)
    except (RuntimeError, OSError) as e:
        print("Snapshot failed (the file itself was built): %s" % e, file=sys.stderr)
        return
    print("Snapshot: %s (Google's PDF rendering)" % path, file=sys.stderr)

# ---------------------------------------------------------------------------- PowerPoint
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

def _natural(name):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", name)]

def keep_existing(path):
    """An export already at `path` is kept, not overwritten: it is renamed to <name>.<YYYYMMDD-HHMMSS><ext>
    (with a counter if that name is taken) and one line says so. Returns the kept path, or None."""
    if not os.path.exists(path):
        return None
    base, ext = os.path.splitext(path)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    kept = "%s.%s%s" % (base, stamp, ext)
    n = 1
    while os.path.exists(kept):
        n += 1
        kept = "%s.%s-%d%s" % (base, stamp, n, ext)
    os.rename(path, kept)
    print("Kept the existing export: %s (the new one is %s)" % (kept, path), file=sys.stderr)
    return kept

def export_pptx(file_id, title, out_dir):
    """Drive files.export: the Google Slides file as a real .pptx in out_dir. Returns its path.
    Drive refuses exports over 10 MB; that comes back as a RuntimeError the caller reports."""
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "presentation").lower()).strip("-") or "presentation"
    data = api("GET", "https://www.googleapis.com/drive/v3/files/%s/export?mimeType=%s"
               % (file_id, urllib.parse.quote(PPTX_MIME, safe="")), binary=True)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, slug + ".pptx")
    keep_existing(path)
    with open(path, "wb") as f:
        f.write(data)
    return path

def pptx_inventory(path):
    """What came across as native PowerPoint objects, and what is a picture. stdlib only."""
    from xml.etree import ElementTree as ET
    P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
    z = zipfile.ZipFile(path)
    names = z.namelist()
    slides = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=_natural)
    notes = [n for n in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)]
    inv = {"slides": len(slides), "notes": 0, "text_frames": 0, "shapes": 0, "pictures": 0,
           "connectors": 0, "groups": 0, "tables": 0, "charts": 0, "fonts": collections.Counter()}
    for n in notes:
        root = ET.fromstring(z.read(n))
        for sp in root.iter(P + "sp"):
            ph = sp.find(".//" + P + "ph")
            if ph is not None and ph.get("type") == "body" and "".join(
                    t.text or "" for t in sp.iter(A + "t")).strip():
                inv["notes"] += 1
                break
    for n in slides:
        root = ET.fromstring(z.read(n))
        for el in root.iter():
            if el.tag == P + "sp":
                if "".join(t.text or "" for t in el.iter(A + "t")).strip():
                    inv["text_frames"] += 1
                else:
                    inv["shapes"] += 1
            elif el.tag == P + "pic":
                inv["pictures"] += 1
            elif el.tag == P + "cxnSp":
                inv["connectors"] += 1
            elif el.tag == P + "grpSp":
                inv["groups"] += 1
            elif el.tag == P + "graphicFrame":
                if el.find(".//" + A + "tbl") is not None:
                    inv["tables"] += 1
                if el.find(".//" + C + "chart") is not None:
                    inv["charts"] += 1
            elif el.tag == A + "rPr":
                latin = el.find(A + "latin")
                if latin is not None and latin.get("typeface"):
                    inv["fonts"][latin.get("typeface")] += 1
    return inv

def print_pptx_summary(path, inv):
    e = sys.stderr
    print("PowerPoint file: %s (%.1f MB)" % (path, os.path.getsize(path) / 1e6), file=e)
    print("  slides %d, speaker notes on %d of %d" % (inv["slides"], inv["notes"], inv["slides"]), file=e)
    print("  native: %d text boxes, %d other shapes, %d connectors, %d groups, %d tables, %d charts"
          % (inv["text_frames"], inv["shapes"], inv["connectors"], inv["groups"], inv["tables"],
             inv["charts"]), file=e)
    print("  pictures: %d (images from the deck, and any chart Google kept as a picture)"
          % inv["pictures"], file=e)
    if inv["fonts"]:
        print("  fonts used: %s" % ", ".join("%s (%d runs)" % kv for kv in inv["fonts"].most_common(6)), file=e)
        print("  (PowerPoint substitutes a font it does not have installed)", file=e)

# ---------------------------------------------------------------------------- main
def parse_slide_list(text, n):
    """'19-24,33,90' -> {19..24, 33, 90} (1-based), checked against the deck's n slides."""
    out = set()
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        m = re.match(r"^(\d+)(?:-(\d+))?$", part)
        if not m:
            raise SystemExit("--slides: %r is not a number or a range (e.g. 19-24,33)" % part)
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        if a < 1 or b > n or a > b:
            raise SystemExit("--slides: %r is outside 1-%d" % (part, n))
        out.update(range(a, b + 1))
    if not out:
        raise SystemExit("--slides: no slides given")
    return out

def dry_run_build(ir):
    """Build the request list of every slide exactly as the real build does (same functions, the standard 16:9
    10 in page), with dummy page ids. No API call. Raises on the first slide whose requests cannot be built, and
    prints a count per slide, so a build failure shows up here, not in the export."""
    sx, sy = emu_scale({"width": {"magnitude": 9144000}, "height": {"magnitude": 5143500}})
    total = 0
    for i, s in enumerate(ir["slides"]):
        try:
            reqs = build_slide_requests(s, "dryrun_page_%d" % i, sx, sy, "dryrun_s%d" % i, slide_no=i + 1)
        except Exception as e:
            raise SystemExit("dry run: slide %d cannot be built: %s: %s" % (i + 1, type(e).__name__, e))
        for r in reqs:
            if not isinstance(r, dict) or len(r) != 1:
                raise SystemExit("dry run: slide %d has a malformed request: %r" % (i + 1, r))
        total += len(reqs)
    print("dry run: %d slides built, %d requests, no API call" % (len(ir["slides"]), total), file=sys.stderr)

def main():
    global TOKEN, DECK_DIR, IMAGES_ENABLED
    ap = argparse.ArgumentParser(description="Build a native Google Slides deck from a DbxSlides deck.")
    ap.add_argument("--deck", help="deck folder containing index.html")
    ap.add_argument("--ir", help="pre-extracted IR json (from the toolbar button)")
    ap.add_argument("--folder", help="Drive folder id to save into (required unless --preview)")
    ap.add_argument("--title", help="presentation title (defaults to deck title)")
    ap.add_argument("--slides", default="",
                    help="export only these slides, 1-based, e.g. 19-24,33,90 (for iterating on a few slides; the "
                         "full deck is the final run). Applies to the build, --dry-run and --preview")
    ap.add_argument("--dry-run", action="store_true",
                    help="build the full Slides request list for every slide, offline (no API call, no upload): any "
                         "exception in the request building fails here, not in the real export")
    ap.add_argument("--preview", action="store_true",
                    help="print the target, every image, and the question to ask the user; then exit (one read-only folder lookup; no writes)")
    ap.add_argument("--allow-public-images", action="store_true",
                    help="consent to sharing images 'anyone with the link' while the build runs (deleted after); "
                         "only after the user answered yes to the --preview question")
    ap.add_argument("--no-images", action="store_true",
                    help="share nothing: each image becomes a labelled placeholder frame, listed in the run summary")
    ap.add_argument("--snapshot", metavar="PDF",
                    help="after the build, save Google's PDF rendering of the presentation here")
    ap.add_argument("--pptx", action="store_true",
                    help="also export the finished presentation to PowerPoint (.pptx) and summarise it")
    ap.add_argument("--out-dir", help="where --pptx writes (default: exports/ next to the deck or IR file)")
    ap.add_argument("--dump-ir", metavar="FILE",
                    help="Write the layout IR (the extracted deck, JSON) to FILE, for checking its colours.")
    ap.add_argument("--sweep", action="store_true",
                    help="check Drive for temp images this tool left shared 'anyone with the link'; "
                         "changes nothing; exits 3 if any are shared")
    args = ap.parse_args()
    if args.sweep:
        sys.exit(sweep_standalone())

    if args.deck:
        DECK_DIR = os.path.abspath(args.deck)
    if args.ir:
        with open(args.ir) as f:
            ir = json.load(f)
        if DECK_DIR is None:
            DECK_DIR = os.path.dirname(os.path.abspath(args.ir))
    elif args.deck:
        ir = ir_from_chrome(args.deck)
    else:
        sys.exit("Provide --deck, --ir, or --sweep")

    if args.dump_ir:
        with open(args.dump_ir, "w", encoding="utf-8") as f:
            json.dump(ir, f, indent=1, ensure_ascii=False)
        print("IR dumped: %s" % args.dump_ir, file=sys.stderr)
    # the deck's own :root tokens (its assets/style.css); the Databricks values stay as fallbacks
    TOKENS.update(read_root_tokens(DECK_DIR))
    if args.slides:
        keep = parse_slide_list(args.slides, len(ir["slides"]))
        ir = dict(ir, slides=[sl for i, sl in enumerate(ir["slides"], 1) if i in keep])
        print("Subset: %d slides (%s)" % (len(ir["slides"]), args.slides), file=sys.stderr)
    title = args.title or ir.get("title") or "Presentation"
    n_slides = len(ir["slides"])
    images = list_public_images(ir)
    subs = ir.get("fontSubstitutions") or {}
    meta, why = folder_info(args.folder, "GS_TOKEN") if args.folder else (None, None)
    print_preview(title, args.folder, n_slides, images, args.no_images, subs, meta)
    if args.dry_run:
        dry_run_build(ir)
        return
    if args.preview:
        return
    if not args.folder:
        sys.exit("--folder <DRIVE_FOLDER_ID> is required (or use --preview).")
    if args.no_images:
        IMAGES_ENABLED = False
    confirm_public_images([] if args.no_images else images, args.allow_public_images)

    TOKEN = get_token()
    print("Building '%s' — %d slides ..." % (title, n_slides), file=sys.stderr)

    # The images are uploaded as world-readable ("anyone with link") so the Slides fetcher
    # can read them. finish_run() runs in the finally below on every exit path, so temp
    # files are deleted (and checked) even if the build fails or is interrupted.
    pid, leaked, export_failed = None, False, False
    try:
        # 0) upload all images first, then let Drive permissions propagate
        n_img = 0
        if IMAGES_ENABLED:
            print("Uploading images ...", file=sys.stderr)
            n_img = pre_upload_images(ir)
        if n_img:
            print("Uploaded %d image(s); waiting for Drive to propagate ..." % n_img, file=sys.stderr)
            time.sleep(3)

        # 1) create presentation
        pres = api("POST", "https://slides.googleapis.com/v1/presentations", body={"title": title})
        pid = pres["presentationId"]
        writer_for(pid).seed()          # every later batchUpdate of this deck is pinned to the revision read here
        page_size = pres["pageSize"]
        sx, sy = emu_scale(page_size)
        default_slide_id = pres["slides"][0]["objectId"]

        # 2) create our slides (blank), then remove the default
        create_reqs = []
        page_ids = []
        for i in range(n_slides):
            page = "slide_%d" % i
            page_ids.append(page)
            create_reqs.append({"createSlide": {"objectId": page, "insertionIndex": i,
                "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        create_reqs.append({"deleteObject": {"objectId": default_slide_id}})
        writer_for(pid).batch(create_reqs)

        # 2b) map each slide to its speaker-notes shape (created with the slide),
        #     so we can write the deck's speaker notes onto the notes page.
        notes_map = {}
        info = writer_for(pid).read("slides(objectId,slideProperties(notesPage(notesProperties(speakerNotesObjectId))))")
        for sl in info.get("slides", []):
            nid = (sl.get("slideProperties", {}).get("notesPage", {})
                     .get("notesProperties", {}).get("speakerNotesObjectId"))
            if nid:
                notes_map[sl["objectId"]] = nid

        # 3) fill each slide (own batch, resilient to a bad image)
        for i, s in enumerate(ir["slides"]):
            reqs = build_slide_requests(s, page_ids[i], sx, sy, "s%d" % i, slide_no=i + 1)
            for c in chunk(reqs, 400):
                batch_update(pid, c)
            print("  slide %d/%d" % (i + 1, n_slides), file=sys.stderr)

        # 3b) speaker notes → the notes page of each slide
        note_reqs = []
        for i, s in enumerate(ir["slides"]):
            txt = (s.get("notes") or "").strip()
            nid = notes_map.get(page_ids[i])
            if txt and nid:
                note_reqs.append({"insertText": {"objectId": nid, "text": txt, "insertionIndex": 0}})
        if note_reqs:
            print("Adding speaker notes to %d slide(s) ..." % len(note_reqs), file=sys.stderr)
            for c in chunk(note_reqs, 400):
                batch_update(pid, c)

        # 4) move into target folder
        api("PATCH",
            "https://www.googleapis.com/drive/v3/files/%s?addParents=%s&removeParents=root&supportsAllDrives=true"
            % (pid, args.folder),
            body={})
    except BaseException:
        if pid:
            print("\nThe run stopped before it finished. A part-built presentation may exist: "
                  "https://docs.google.com/presentation/d/%s/edit (delete it, then run again)." % pid,
                  file=sys.stderr)
        raise
    finally:
        # 5) delete the temp images and check Drive for any still shared — on every exit path
        leaked = finish_run()

    url = "https://docs.google.com/presentation/d/%s/edit" % pid
    print_omitted()
    print(url)
    if args.snapshot:
        save_snapshot(pid, args.snapshot)
    if args.pptx:
        out_dir = args.out_dir or os.path.join(DECK_DIR or os.getcwd(), "exports")
        try:
            path = export_pptx(pid, title, out_dir)
            print(path)
            print_pptx_summary(path, pptx_inventory(path))
        except (RuntimeError, OSError, zipfile.BadZipFile) as e:
            export_failed = True
            print("PowerPoint export failed (the Google Slides file is fine): %s\n"
                  "  Drive refuses exports over 10 MB. For a large deck, open the Google Slides file "
                  "and use File > Download > Microsoft PowerPoint." % str(e).splitlines()[0], file=sys.stderr)
    if leaked:
        sys.exit(3)
    if export_failed:
        sys.exit(4)
    return url

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrupted. Temp images from this run were deleted where possible; "
                 "run export_gslides.py --sweep to check.")
    except UnsureWrite as e:
        sys.exit("x %s" % e)
    except RuntimeError as e:
        sys.exit("x %s" % e)
