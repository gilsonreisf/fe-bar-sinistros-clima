# HTML deck → native Google Slides

Turn a deck built from this template into a **real, editable Google Slides
presentation** — native text boxes, shapes and images — and drop it in a
Drive folder you choose. It is **not** a screenshot export (that is what the PDF
button already does well); text stays text and boxes stay boxes.

## How it works

The hard part of an HTML→Slides converter is CSS: rather than reimplement a
layout engine, this reuses **the browser's own**. Two stages:

1. **Extract** (`assets/gslides.js`, runs in the deck page) — walks each rendered
   slide and reads the *computed* geometry, colours, fonts and text runs, then
   emits a compact JSON **IR** (intermediate representation) in the deck's
   1280×720 design space. Filled `<div>`s become rectangles; text blocks become
   styled text runs; `<img>`s carry their source path; inline `<svg>`/`<canvas>`
   charts with arc or pie geometry (donut, rings, gauge, Harvey balls) are rasterised
   to PNG with their computed styles inlined so they survive serialisation. Bars,
   waterfall, line, gantt, funnel, timeline, roadmap, quadrant, tree and matrix are
   emitted as native shapes (see the template README, "What exports as native"). **Exception:** an
   `<svg data-gs="native">` (the architecture diagram kit, slides 57–59) is walked
   element by element and emitted as native shapes (`rect`/`circle`, dashed outlines
   included), native lines with arrowheads (`line`/`polyline` + `marker-start`/
   `marker-end`), text boxes (`text`, one per `<tspan>` that is placed by its own `x`, `dx` or `dy`) and images
   (`<image href>`), all sharing one `group` id that the driver turns into a Slides
   group. Any element outside that subset makes the SVG fall back to one image.

2. **Build** (`export_gslides.py`) — maps the IR 1:1 onto a 16:9 Slides page and
   creates matching native objects via the Slides + Drive REST APIs: shapes with
   solid fills and outlines, text boxes with per-run font/size/weight/colour and
   paragraph alignment, **native tables** (`createTable` with per-cell text,
   fills and borders), and images (uploaded to Drive, referenced, then cleaned
   up once Slides has ingested its own copy).

Images from `<img>` tags are read from disk by the Python side (Chrome taints the
canvas for `file://` images, so they can't be base64'd in-page). SVGs are
rasterised to PNG through headless Chrome (no extra dependency).

## Usage

Auth is the fe-google-tools **CLI path**: `gcloud` Application Default
Credentials with the Slides + Drive scopes and a GCP quota project. It defaults to `gcp-dev-field-eng-aiapiquota`; set `GS_QUOTA_PROJECT` to bill another project. Run
the `google-auth` skill's login once if needed.

```bash
# straight from a deck folder (extraction runs via headless Chrome for you)
python3 export_gslides.py \
  --deck /path/to/your-deck \
  --folder <DRIVE_FOLDER_ID> \
  --title "My Deck"

# or from an IR file the toolbar "Google Slides…" button downloaded — keep --deck
# too (pointing at the deck), so <img> sources resolve from <deck>/resources/
python3 export_gslides.py --ir deck.gslides.json --deck /path/to/your-deck --folder <DRIVE_FOLDER_ID>
```

It prints the presentation URL on success.

**Images are temporarily public.** Slides fetches images anonymously, so each image is
uploaded to your Drive and shared "anyone with the link" for the few seconds the build
needs, then deleted. `--preview` prints the exact question to ask the user and every image
it would share. The script needs consent (`--allow-public-images`, a y/N prompt on a
terminal, or `--no-images`). Without consent, use `--no-images`: each image is left out and
shown as a dashed, labelled placeholder frame, and the run summary lists every one. Each temp
file is tagged in Drive, and the end of every run (success, error or Ctrl-C) deletes what it
uploaded and checks again. Anything still shared exits with code **3** and prints the file
ids. `--sweep` runs that check on its own: it changes nothing and exits 3 if any temp image
from this tool is still shared.

**PowerPoint copy (`--pptx`).** After the build, the Google Slides file is exported to
`exports/<title>.pptx` next to the deck (or `--out-dir`), and the script prints what came
across as native objects and what is a picture. See *Office round trip* below.

### Options / environment

| Flag / env | Meaning |
|---|---|
| `--deck DIR` | Deck folder with `index.html` (extraction source + image root). |
| `--ir FILE` | Use a pre-extracted IR instead of running Chrome. Pair with `--deck` so images resolve. |
| `--folder ID` | Target Drive folder id (required unless `--preview`). |
| `--title` | Presentation title (defaults to the deck's `<title>`). |
| `--preview` | Print the target folder with its name and owner (one read-only Drive lookup; no writes), every image that would be shared publicly, and the question to relay to the user; then exit (no API calls). |
| `--allow-public-images` | Consent to sharing images "anyone with the link" (reader) while the build runs; they're deleted after. Give it only after the user answers yes to the `--preview` question. Without it the script asks y/N on a terminal and refuses otherwise. |
| `--no-images` | Share nothing. Each image becomes a labelled placeholder frame, and the run summary lists each one. Emoji glyphs stay as live text. |
| `--snapshot PDF` | After the build, save Google's own PDF rendering of the presentation to `PDF`, to look at what Google drew. |
| `--pptx` | Also export the finished presentation to PowerPoint and summarise it (native objects vs pictures). |
| `--out-dir DIR` | Where `--pptx` writes (default `exports/` next to the deck or IR file). An existing file of that name is kept as `<title>.<YYYYMMDD-HHMMSS>.pptx`; nothing is overwritten. |
| `--sweep` | Check Drive for temp images from this tool that are still shared "anyone with the link". Changes nothing; exits 3 if any are. Needs no deck. |
| `CHROME` | Path to Chrome/Chromium (auto-detected per OS: the macOS app, or `google-chrome`/`chromium` on PATH; set this if detection fails). |
| `GS_QUOTA_PROJECT` | The GCP quota project the export bills (default `gcp-dev-field-eng-aiapiquota`; set your own). |
| `GS_TOKEN` | Access token override (else `gcloud` ADC is used). |

## Office round trip (`--pptx`)

`--pptx` uses Drive `files.export` on the finished Google Slides file, so the PowerPoint copy
is Google's conversion of the deck, not a second renderer. What to expect:

- **Native:** text boxes, shapes, connectors, groups, native tables and speaker notes come
  across as editable PowerPoint objects. The script's inventory counts them.
- **Pictures:** every image from the deck stays a picture. A chart that Google kept as an
  image (the donut, gauge, gantt and funnel charts; any SVG or canvas chart) is a picture in
  PowerPoint too. Only native bar charts and the architecture kit's `data-gs="native"` diagrams
  are editable objects.
- **Fonts:** DM Sans and DM Mono are named in the file, but PowerPoint substitutes a font it
  does not have installed. Install the fonts, or expect the fallback face.
- **Size:** Drive refuses exports over 10 MB. For a large deck the script reports the error;
  use File > Download > Microsoft PowerPoint in Google Slides.
- **Layout:** PowerPoint lays out text itself, so line breaks can differ from the Google file.
  Check the PowerPoint file as you checked the PDF.
- **With `--no-images`** the PowerPoint file has the placeholder frames where the images were.

## What maps well, and the known limits

**Faithful:** titles/body/bullets, two- and three-column layouts, KPI/stat text,
bar charts (native rounded rects), pull quotes, section/cover/closing (dark
backgrounds, geometric graphics, logos), donut/line/gauge/funnel/gantt charts
(as crisp images), **accent cards** (metric / ROI / decision-tree nodes / case-study
quote — a thin frame on three sides plus a thick coloured top/left rule) which
export as a full-size rounded rectangle in the accent colour with the fill box
laid on top inset by the rule's thickness, so the accent shows as a rounded
header/side strip that follows the card's corner radius — not a straight bar
floating over the rounded corners, and not a white box wrapped in four
disconnected edge bars, and
**tables** — rebuilt as a real Slides table (`createTable`) with the measured
column widths / row heights, per-cell composited fills (header fill, zebra rows),
per-run text (✓/✕, bold headers) and the resolved per-edge borders (including the
matrix slide's highlighted-column rules), so the grid stays a native, editable
table rather than a scatter of floating boxes. A cell holds text only in Slides, so an icon or picture inside a
cell is placed over the cell's own box, drawn on top of the table.

**Approximated by design:**
- **Clip-path shapes** (chevrons, home plates, block arrows) become the Slides preset only when the HTML polygon
  has that preset's default geometry (`CHEVRON`/`HOME_PLATE`: point depth half the shorter side; `RIGHT_ARROW`: shaft
  over the middle half, head half the shorter side). Any other polygon is reported by the export ("matches no Slides
  preset") and drawn as a rectangle, so the template keeps its shapes on the preset geometry (see the template README).
- **Gradients** on a slide background are one smooth picture (not strips), so they are checked against the HTML like any picture.
- **Bulleted lists, PowerPoint only:** Google Slides is the target, and its first line of a list lands where the HTML's does.
  PowerPoint adds the extra space of a percentage line spacing above a list's first line, so the first line sits lower than
  the HTML's by `(line spacing % / 100 - 1) x font size x a factor for the font` (about 21 px for 180% at 22 px in Inter,
  16 px in DM Sans). The factor is measured per font. A font not yet measured is accepted anywhere in the band of the measured
  factors, and the check says it is unmeasured. A PowerPoint offset is reported as info with its measured size; a larger
  or different one is a failure.
- **SVG/canvas charts** (other than `data-gs="native"` diagrams) become images — pixel-faithful, but not re-editable as
  Slides charts (native bar charts *are* editable rectangles).
- **Animations, live-demo frames, video embeds** have no Slides equivalent — the
  static poster/frame is what carries over.
- **Text reflow**: Slides measures DM Sans up to ~15% wider than the browser. Boxes
  get inset compensation and some slack, clamped so no box leaves the slide; a
  one-line headline whose text would no longer fit is set a few percent smaller so
  it stays on one line instead of wrapping into the subtitle. Other text may still
  wrap differently by a word; tweak in Slides if needed.
- **Clipped content**: Slides has no clipping. An `inset()` clip-path (the compare
  slider's "before" pane) is applied at export: shapes are cut, file images are
  rendered as just the visible slice, and hidden text is dropped. Flip cards export
  their front face. `object-fit: cover/contain` on an `<img>` is honoured.
- **Transient errors**: HTTP 429 and 5xx from Slides/Drive are retried with backoff
  (5 retries), so a Drive hiccup no longer drops an image. A content edit
  (`batchUpdate`) is pinned to the deck's revision (`writeControl.requiredRevisionId`).
  After a 5xx or a timeout the export reads the deck back: a batch that did not land is
  sent again at the same revision, one that landed (its new objects are there) is not
  repeated, and anything it cannot tell apart stops the export and says so (delete the
  new deck, re-run). A deck edited during the export stops the run with "changed during
  the export"; nothing is rebased.
- **Inline coloured swatches** inside a text line (e.g. legend chips) are dropped
  in favour of keeping the label text intact.
