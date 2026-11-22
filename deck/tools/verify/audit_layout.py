#!/usr/bin/env python3
"""Run this template's layout and clearance audits in headless Chrome, at the pinned sizes and in print.

    python3 tools/verify/audit_layout.py            # from the deliverable folder (the one with index.html)
    python3 tools/verify/audit_layout.py --json out.json

It opens index.html?audit=1 in each configuration below, waits until the engine has written its findings
(<div id="__audit_clearance__">, and <div id="__audit__"> where the engine has a layout audit), reads both lists and
prints them. It exits 1 when any configuration has a finding, and 2 when it cannot run (no Chrome, no page).

Why a runner and not --dump-dom: --dump-dom has no print emulation, and the window size is only what
--window-size says. Here each configuration sets the viewport (Emulation.setDeviceMetricsOverride) and the media type
(Emulation.setEmulatedMedia), over the Chrome DevTools protocol. The protocol client below is stdlib only (a minimal
WebSocket client), so nothing is installed. Chrome is found from $CHROME or $CHROME_BIN, the Chrome or Chromium app on
macOS, or the usual names on PATH.

The layout audit (__audit__) is not kept by every engine: dbx-docsites has none, and its clearance audit is its layout
gate. The findings are never changed here; the runner only reads what the engine reports.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))   # this folder: migrate_viewboxes.py
from migrate_viewboxes import suggestion  # noqa: E402  (the clearance hint for a known template icon)

KIND = "slides"          # slides | docs | docsites (set in each template's copy of this file)

# Each configuration: (name, viewport width, height, page query, media type or None). The pinned sizes are 1440x900
# and 1280x720; docsites adds a phone width, dark mode, and print in its two forms (the page, and the whole guide).
CONFIGS = {
    "slides": [
        ("screen 1440x900", 1440, 900, "", None),
        ("screen 1280x720", 1280, 720, "", None),
        ("print", 1440, 900, "", "print"),
    ],
    "docs": [
        ("screen 1440x900", 1440, 900, "", None),
        ("screen 1280x720", 1280, 720, "", None),
        ("print", 1440, 900, "", "print"),
    ],
    "docsites": [
        ("screen 1440x900", 1440, 900, "", None),
        ("screen 1280x720", 1280, 720, "", None),
        ("phone 390x844", 390, 844, "", None),
        ("dark 1440x900", 1440, 900, "theme=dark", None),
        ("print 1440x900", 1440, 900, "", "print"),
        ("print whole guide", 1440, 900, "print=all", "print"),
    ],
}
WAIT_S = 90

NODE_READ = ("(() => { const q = id => { const n = document.getElementById(id); return n ? n.textContent : null; };"
             " return JSON.stringify({ audit: q('__audit__'), clearance: q('__audit_clearance__') }); })()")
NODE_READY = "!!document.getElementById('__audit_clearance__')"


def find_chrome():
    for var in ("CHROME", "CHROME_BIN"):
        if os.environ.get(var):
            return os.environ[var]
    for app in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium"):
        if os.path.exists(app):
            return app
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


class WebSocket:
    """The client end of a WebSocket, just enough for the DevTools protocol (text frames, masked, stdlib only)."""

    def __init__(self, url: str):
        p = urlparse(url)
        self.sock = socket.create_connection((p.hostname, p.port), timeout=WAIT_S)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(("GET %s HTTP/1.1\r\nHost: %s:%s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
                           % (p.path, p.hostname, p.port, key)).encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1)
            if not chunk:
                raise RuntimeError("the DevTools socket closed during the handshake")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise RuntimeError("the DevTools handshake failed: " + head[:120].decode(errors="replace"))
        self.buf = b""

    def send(self, text: str) -> None:
        data, mask = text.encode(), os.urandom(4)
        n = len(data)
        head = bytearray([0x81])
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack("!H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack("!Q", n)
        self.sock.sendall(bytes(head) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _take(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise RuntimeError("the DevTools socket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self) -> str:
        message = b""
        while True:
            b1, b2 = self._take(2)
            fin, op, n = b1 & 0x80, b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._take(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._take(8))[0]
            payload = self._take(n)                # the server does not mask its frames
            if op == 0x8:
                raise RuntimeError("the DevTools socket was closed by Chrome")
            if op in (0x0, 0x1):
                message += payload
                if fin:
                    return message.decode("utf-8")


class Chrome:
    def __init__(self, binary: str):
        self.profile = Path(tempfile.mkdtemp(prefix="audit-layout-"))
        self.proc = subprocess.Popen([binary, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
                                      "--no-default-browser-check", "--allow-file-access-from-files",
                                      "--remote-debugging-port=0", "--user-data-dir=" + str(self.profile),
                                      "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = self.profile / "DevToolsActivePort"
        deadline = time.time() + 30
        while time.time() < deadline and not port_file.exists():
            time.sleep(0.1)
        if not port_file.exists():
            self.close()
            raise RuntimeError("Chrome did not open a DevTools port")
        port = port_file.read_text().split("\n")[0].strip()
        with urllib.request.urlopen("http://127.0.0.1:%s/json/version" % port, timeout=30) as r:
            self.ws = WebSocket(json.load(r)["webSocketDebuggerUrl"])
        self.next_id = 0
        self.pending = []

    def call(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        self.next_id += 1
        msg = {"id": self.next_id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send(json.dumps(msg))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("id") == self.next_id:
                if "error" in reply:
                    raise RuntimeError("%s: %s" % (method, reply["error"].get("message")))
                return reply.get("result", {})

    def close(self) -> None:
        try:
            self.ws.sock.close()
        except Exception:  # noqa: BLE001  closing a socket that is already gone
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


ARCH_JS = r"""(() => {
  const CLEAR = 3, TOL = 1.0, TIP_TOL = 0.3, CONTRAST = 3;
  const findings = [], notes = [];
  const num = v => parseFloat(v) || 0;
  const inDefs = el => el.closest('defs,marker,clipPath,mask,pattern,symbol');
  const skip = el => el.closest('[data-audit-skip~="diagram"],[data-audit-skip~="all"]');
  const dseg = (px, py, a, b) => {
    const dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy;
    const t = L === 0 ? 0 : Math.max(0, Math.min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / L));
    return Math.hypot(px - (a[0] + t * dx), py - (a[1] + t * dy));
  };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const rgb = s => { const m = /rgba?\(([^)]+)\)/.exec(s || ''); if (!m) return null; const p = m[1].split(/[ ,\/]+/).map(Number); return p.length >= 3 ? p : null; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  // marker: T (tip x of the pointed path) and refX
  const markerInfo = id => {
    const mk = document.getElementById(id); if (!mk) return null;
    const p = mk.querySelector('path'); const d = p ? p.getAttribute('d') : '';
    const tok = d.match(/[MLlzZ]|-?[\d.]+/g) || []; let cmd = 'M', x = 0, maxX = 0, i = 0;
    while (i < tok.length) { const t = tok[i]; if (/^[MLlzZ]$/.test(t)) { cmd = t; i++; continue; }
      const px = parseFloat(tok[i]); i += 2; x = cmd === 'l' ? x + px : px; if (x > maxX) maxX = x; }
    return { T: maxX, refX: num(mk.getAttribute('refX')) };
  };
  const endOf = (el, which) => { const v = el.getAttribute(which) || getComputedStyle(el).getPropertyValue(which); const m = v && /url\(["']?#([^"')]+)["']?\)/.exec(v); return m ? m[1] : null; };
  const pathsOf = el => {
    if (el.tagName.toLowerCase() === 'line') return [[[num(el.getAttribute('x1')), num(el.getAttribute('y1'))], [num(el.getAttribute('x2')), num(el.getAttribute('y2'))]]];
    const pts = el.getAttribute('points').trim().split(/\s+/).map(q => q.split(',').map(Number));
    const out = []; for (let i = 0; i + 1 < pts.length; i++) out.push([pts[i], pts[i + 1]]); return out;
  };
  // 1. arrow tips (every svg): the stroke ends under the head, and the tip touches the outer border it points at
  document.querySelectorAll('svg').forEach((svg, si) => {
    if (skip(svg)) return;
    const label = (svg.getAttribute('aria-label') || ('svg ' + (si + 1))).slice(0, 40);
    const rects = [...svg.querySelectorAll('rect')].filter(r => !inDefs(r)).map(r => ({ x: num(r.getAttribute('x')), y: num(r.getAttribute('y')), w: num(r.getAttribute('width')), h: num(r.getAttribute('height')), el: r }));
    svg.querySelectorAll('line,polyline').forEach(el => {
      if (inDefs(el)) return;
      const sw = parseFloat(getComputedStyle(el).strokeWidth) || num(el.getAttribute('stroke-width')) || 1;
      const segs = pathsOf(el);
      ['marker-end', 'marker-start'].forEach(which => {
        const id = endOf(el, which); if (!id) return;
        const mi = markerInfo(id); if (!mi) return;
        const reach = mi.T - mi.refX;                               // tip distance past the vertex, in stroke widths
        const seg = which === 'marker-end' ? segs[segs.length - 1] : segs[0];
        const V = which === 'marker-end' ? seg[1] : seg[0], O = which === 'marker-end' ? seg[0] : seg[1];
        const L = Math.hypot(V[0] - O[0], V[1] - O[1]) || 1;
        const u = [(V[0] - O[0]) / L, (V[1] - O[1]) / L];           // from the other end toward the vertex
        const sign = 1;                                             // the tip lies beyond the vertex, away from the line (both ends)
        const tip = [V[0] + sign * reach * sw * u[0], V[1] + sign * reach * sw * u[1]];
        if (reach < 1 - 0.01) findings.push({ page: label, kind: 'arrow-stroke-shows', detail: 'marker ' + id + ' tip is ' + reach.toFixed(2) + ' stroke widths past the line end: the stroke shows beside the head' });
        // the face the arrow runs into: the first rect face the ray from the tip meets within 20 units
        let hit = null;
        rects.forEach(q => {
          const x0 = q.x, x1 = q.x + q.w, y0 = q.y, y1 = q.y + q.h;
          if (tip[0] > x0 && tip[0] < x1 && tip[1] > y0 && tip[1] < y1) { hit = hit || { inside: q }; return; }
          let tin = -Infinity, tout = Infinity, face = null;
          [[u[0], tip[0], x0, x1, -1, 0], [u[1], tip[1], y0, y1, 0, -1]].forEach(([uu, pp, a0, a1, nx, ny]) => {
            if (Math.abs(uu) < 1e-9) { if (pp < a0 || pp > a1) tin = Infinity; return; }
            const ta = (a0 - pp) / uu, tb = (a1 - pp) / uu;
            const lo = Math.min(ta, tb), hi = Math.max(ta, tb);
            const nrm = ta < tb ? [nx, ny] : [-nx, -ny];
            if (lo > tin) { tin = lo; face = { q, nrm, axis: nx ? 'x' : 'y', value: nx ? (uu > 0 ? a0 : a1) : (uu > 0 ? a0 : a1) }; }
            tout = Math.min(tout, hi);
          });
          if (tin <= tout && tin >= 0 && tin <= 20 && face && (!hit || hit.t === undefined || tin < hit.t)) hit = { q, t: tin, face };
        });
        const insideBoth = hit && hit.inside && O[0] > hit.inside.x && O[0] < hit.inside.x + hit.inside.w && O[1] > hit.inside.y && O[1] < hit.inside.y + hit.inside.h;
        if (hit && hit.inside && !insideBoth) findings.push({ page: label, kind: 'arrow-tip-off-border', detail: 'marker ' + id + ' at (' + tip[0].toFixed(2) + ', ' + tip[1].toFixed(2) + ') tip is inside the box ' + [hit.inside.x, hit.inside.y, hit.inside.w, hit.inside.h].join('/') });
        else if (hit && hit.face) {
          const f = hit.face, sw_box = /stroke:(?!none)/.test(f.q.el.getAttribute('style') || '') ? (parseFloat(getComputedStyle(f.q.el).strokeWidth) || 1) : 0;
          const normal = f.axis === 'x' ? Math.abs(tip[0] - f.value) : Math.abs(tip[1] - f.value);
          if (Math.abs(normal - sw_box / 2) > TIP_TOL) findings.push({ page: label, kind: 'arrow-tip-off-border', detail: 'marker ' + id + ' at (' + tip[0].toFixed(2) + ', ' + tip[1].toFixed(2) + ') tip is ' + (normal > sw_box / 2 ? 'short of' : 'under') + ' its box border by ' + Math.abs(normal - sw_box / 2).toFixed(2) });
        }
      });
    });
  });
  // 2. step badges (architecture diagrams): size, clearance, centre in the gap between the two boxes, contrast
  document.querySelectorAll('svg[data-arch-check]').forEach((svg, si) => {
    if (skip(svg)) return;
    const label = (svg.getAttribute('aria-label') || ('svg ' + (si + 1))).slice(0, 40);
    const rects = [...svg.querySelectorAll('rect')].filter(r => !inDefs(r)).map(r => ({ x: num(r.getAttribute('x')), y: num(r.getAttribute('y')), w: num(r.getAttribute('width')), h: num(r.getAttribute('height')), el: r }));
    const edges = rects.flatMap(q => [[q.x, q.y, q.x + q.w, q.y], [q.x + q.w, q.y, q.x + q.w, q.y + q.h], [q.x, q.y + q.h, q.x + q.w, q.y + q.h], [q.x, q.y, q.x, q.y + q.h]]);
    const segs = [];
    svg.querySelectorAll('line,polyline').forEach(el => {
      if (inDefs(el)) return;
      const sw = parseFloat(getComputedStyle(el).strokeWidth) || num(el.getAttribute('stroke-width')) || 1;
      const ps = pathsOf(el);
      ps.forEach((s, i) => {
        let a = s[0], b = s[1];
        const last = i === ps.length - 1, first = i === 0;
        const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, u = [(b[0] - a[0]) / L, (b[1] - a[1]) / L];
        const ext = (which) => { const id = endOf(el, which); const mi = id && markerInfo(id); return mi ? (mi.T - mi.refX) * sw : 0; };
        if (last) { const e = ext('marker-end'); b = [b[0] + u[0] * e, b[1] + u[1] * e]; }
        if (first) { const e = ext('marker-start'); a = [a[0] - u[0] * e, a[1] - u[1] * e]; }
        segs.push({ a, b, sw, head: !!(endOf(el, 'marker-end') || endOf(el, 'marker-start')) });
      });
    });
    const badges = [];
    svg.querySelectorAll('circle').forEach(c => {
      if (inDefs(c)) return;
      const cx = num(c.getAttribute('cx')), cy = num(c.getAttribute('cy')), r = num(c.getAttribute('r'));
      const t = [...svg.querySelectorAll('text')].find(t => /^\d$/.test(t.textContent.trim()) && Math.abs(num(t.getAttribute('x')) - cx) < 0.5 && Math.abs(num(t.getAttribute('y')) - cy) < 8);
      if (t) badges.push({ c, t, cx, cy, r });
    });
    const sizes = [...new Set(badges.map(b => b.r))];
    if (sizes.length > 1) findings.push({ page: label, kind: 'badge-size', detail: 'badges differ in size: ' + sizes.join(', ') });
    badges.forEach(b => {
      const name = 'step ' + b.t.textContent.trim() + ' at (' + b.cx.toFixed(1) + ', ' + b.cy.toFixed(1) + ')';
      // clearance from every box and container edge
      const clear = Math.min(...edges.map(e => dseg(b.cx, b.cy, [e[0], e[1]], [e[2], e[3]]))) - b.r;
      if (clear < CLEAR - TOL) findings.push({ page: label, kind: 'badge-clearance', detail: name + ' is ' + clear.toFixed(1) + ' from the nearest edge (need ' + CLEAR + ')' });
      // contrast with the surface under it
      const surf = rects.filter(q => q.x < b.cx && b.cx < q.x + q.w && q.y < b.cy && b.cy < q.y + q.h).sort((p, q) => p.w * p.h - q.w * q.h)[0];
      let page = null; for (let e = svg; e && !page; e = e.parentElement) { const v = rgb(getComputedStyle(e).backgroundColor); if (v && (v.length < 4 || v[3] > 0)) page = v; }
      const bf = rgb(getComputedStyle(b.c).fill), sf = surf ? rgb(getComputedStyle(surf.el).fill) : (page || [255, 255, 255]);
      if (bf && sf && ratio(bf, sf) < CONTRAST) findings.push({ page: label, kind: 'badge-contrast', detail: name + ' fill ' + ratio(bf, sf).toFixed(2) + ':1 against its surface (need ' + CONTRAST + ':1)' });
      // the connector it labels
      let best = null;
      segs.forEach(s => { const d = dseg(b.cx, b.cy, s.a, s.b); if (!best || d < best.d) best = { d, s }; });
      if (!best || best.d > b.r + 14) return;
      if (best.d - b.r < 2) { findings.push({ page: label, kind: 'badge-on-connector', detail: name + ' sits on its line' }); return; }
      const s = best.s, horiz = Math.abs(s.a[1] - s.b[1]) < 0.01, vert = Math.abs(s.a[0] - s.b[0]) < 0.01;
      if (!horiz && !vert) return;
      const k = horiz ? 0 : 1, fixed = horiz ? s.a[1] : s.a[0];
      const along = horiz ? b.cx : b.cy;
      const lo = Math.min(s.a[k], s.b[k]), hi = Math.max(s.a[k], s.b[k]);
      const edgeOn = p => rects.some(q => { const a0 = k ? q.y : q.x, a1 = k ? q.y + q.h : q.x + q.w, o0 = k ? q.x : q.y, o1 = k ? q.x + q.w : q.y + q.h;
        return (Math.abs(p - a0) <= 1 || Math.abs(p - a1) <= 1) && o0 - 1 <= fixed && fixed <= o1 + 1; });
      if (!edgeOn(lo) && !edgeOn(hi)) return;
      if (!edgeOn(lo) || !edgeOn(hi)) { notes.push({ page: label, kind: 'badge-open', detail: name + ': one end of its connector is not on a box' }); return; }
      const cuts = [];
      rects.forEach(q => { const a0 = k ? q.y : q.x, a1 = k ? q.y + q.h : q.x + q.w, o0 = k ? q.x : q.y, o1 = k ? q.x + q.w : q.y + q.h;
        if (o0 < fixed && fixed < o1) [a0, a1].forEach(e => { if (lo + 0.01 < e && e < hi - 0.01) cuts.push(e); }); });
      const need = b.r + CLEAR, loOk = lo + need, hiOk = hi - need, M = (lo + hi) / 2;
      if (loOk > hiOk + 1e-9) { findings.push({ page: label, kind: 'badge-tight', detail: name + ': the gap between its boxes is ' + (hi - lo).toFixed(1) + ', too small for the badge and its clearance' }); return; }
      const forb = cuts.map(e => [e - need, e + need]);
      const cand = [M, loOk, hiOk, ...forb.flat()].filter(p => p >= loOk - 1e-9 && p <= hiOk + 1e-9 && forb.every(([x, y]) => !(p > x + 1e-9 && p < y - 1e-9)));
      if (!cand.length) { findings.push({ page: label, kind: 'badge-tight', detail: name + ': no clear place between the container edges' }); return; }
      const want = cand.reduce((p, q) => (Math.abs(q - M) < Math.abs(p - M) - 1e-9 ? q : p));
      notes.push({ page: label, kind: 'badge-measure', detail: name + ': gap ' + lo.toFixed(1) + '..' + hi.toFixed(1) + ' centre ' + M.toFixed(1) + ', badge ' + along.toFixed(1) + ' (expected ' + want.toFixed(1) + '), clearance ' + clear.toFixed(1) });
      if (Math.abs(along - want) > TOL) findings.push({ page: label, kind: 'badge-off-centre', detail: name + ' is ' + (along - want).toFixed(1) + ' off its centre position ' + want.toFixed(1) });
    });
  });
  return JSON.stringify({ findings, notes });
})()"""



def read_page(chrome: Chrome, session: str, url: str, width: int, height: int, media: str | None) -> dict:
    chrome.call("Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 600}, session)
    chrome.call("Emulation.setEmulatedMedia", {"media": media or ""}, session)
    chrome.call("Page.navigate", {"url": url}, session)
    deadline = time.time() + WAIT_S
    while True:
        try:
            if chrome.call("Runtime.evaluate", {"expression": NODE_READY, "returnByValue": True},
                           session).get("result", {}).get("value") is True:
                break
        except RuntimeError:
            pass                                    # the page is still loading
        if time.time() > deadline:
            raise RuntimeError("no __audit_clearance__ node after %d s: %s" % (WAIT_S, url))
        time.sleep(0.2)
    value = chrome.call("Runtime.evaluate", {"expression": NODE_READ, "returnByValue": True},
                        session)["result"]["value"]
    nodes = json.loads(value)
    diagram = json.loads(chrome.call("Runtime.evaluate", {"expression": ARCH_JS, "returnByValue": True},
                                     session)["result"]["value"])
    return {"audit": None if nodes["audit"] is None else json.loads(nodes["audit"]),
            "clearance": json.loads(nodes["clearance"] or "[]"),
            "diagram": diagram["findings"], "diagram_notes": diagram["notes"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                    help="the deliverable folder (default: the folder above tools/)")
    ap.add_argument("--json", type=Path, help="also write every configuration's findings to this file")
    args = ap.parse_args()
    entry = (args.root / "index.html").resolve()
    if not entry.is_file():
        print("no index.html in %s" % args.root, file=sys.stderr)
        return 2
    binary = find_chrome()
    if not binary:
        print("Chrome not found: set CHROME to a Chrome or Chromium binary", file=sys.stderr)
        return 2
    chrome = Chrome(binary)
    results, failed = {}, 0
    try:
        target = chrome.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        session = chrome.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        chrome.call("Page.enable", {}, session)
        for name, w, h, query, media in CONFIGS[KIND]:
            url = entry.as_uri() + "?audit=1" + ("&" + query if query else "")
            try:
                got = read_page(chrome, session, url, w, h, media)
            except RuntimeError as e:
                print("[ERROR] %s: %s" % (name, e))
                results[name] = {"error": str(e)}
                failed += 1
                continue
            results[name] = got
            layout = got["audit"] or []
            clear = got["clearance"] + got["diagram"]
            for note in got["diagram_notes"]:
                print("[NOTE] %s: %s %s" % (name, note["page"], note["detail"]))
            if not clear and not layout:
                print("[PASS] %s: no findings" % name)
                continue
            failed += 1
            print("[FAIL] %s: %d layout, %d clearance" % (name, len(layout), len(clear)))
            for f in layout + clear:
                where = f.get("title") or f.get("page") or ""
                print("  %s %s: %s %s" % (f.get("index", f.get("page", "?")), where, f.get("kind"), f.get("detail", "")))
                if suggestion(f.get("icon")):
                    print("      -> " + suggestion(f.get("icon")))
    finally:
        chrome.close()
    if KIND == "docsites":
        print("(dbx-docsites has no layout __audit__ node: the clearance audit is its layout gate)")
    if args.json:
        args.json.write_text(json.dumps(results, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
