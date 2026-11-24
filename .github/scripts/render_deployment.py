#!/usr/bin/env python3
"""Render a deployment diagram SVG: zones -> hosts -> artifacts, labelled paths.

"Where the software actually runs." The layout is authored in JSON (explicit
coordinates and waypoints on the 4px grid), never auto-routed: auto-routing is
what produces the diagonal slants and label collisions the editorial rules
forbid, and it makes the output non-deterministic in practice.

Source shape (see examples/wayne-deployment.json):

{
  "title": "wayne OpenWrt deployment",
  "subtitle": "...",
  "zones": [{"id","label","x","y","w","h"}],
  "nodes": [{"id","zone","x","y","w","tag","name","replicas?","artifacts":[{"name","version"}]}],
  "paths": [{"from","to","points":[[x,y],...],"label","kind":"link|muted|accent","dash":bool}],
  "legend": [{"swatch":"chip|accent-line|muted-line","label"}]
}

  python3 render_deployment.py --src examples/wayne-deployment.json --out docs/diagrams/deploy.svg
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import svgkit as k  # noqa: E402

BUDGET = {"zones": 3, "nodes": 6, "chips": 9, "paths": 8, "accents": 2}
CHIP_H = 24
NODE_PAD = 12
LABEL_W_PAD = 6


def build_defs(th, needs_accent, needs_link):
    defs = ["<defs>"]
    marker = ('<marker id="{i}" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">'
              '<polygon points="0 0, 8 3, 0 6" fill="{c}"/></marker>')
    defs.append(marker.format(i="arrow", c=th["muted"]))
    defs.append(marker.format(i="arrow-link", c=th["link"]))
    if needs_accent:
        defs.append(marker.format(i="arrow-accent", c=th["accent"]))
    defs.append("</defs>")
    return "".join(defs)


def polyline(points, stroke, dash, marker):
    pts = " ".join(f"{k.snap(x)},{k.snap(y)}" for x, y in points)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<polyline points="{pts}" fill="none" stroke="{stroke}" stroke-width="1.4"'
            f'{d} marker-end="url(#{marker})"/>')


def path_label(points, label, th, color, at=None):
    """Label sits at the midpoint segment, on a paper mask so it never bleeds
    through the stroke. `label_at` overrides the midpoint when the geometry
    leaves no room - the author knows where the gap is."""
    if at:
        cx, cy = at
    else:
        mid = len(points) // 2
        (x1, y1), (x2, y2) = points[max(mid - 1, 0)], points[min(mid, len(points) - 1)]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    w = len(label) * 5.4 + LABEL_W_PAD * 2
    rect = k.rect(cx - w / 2, cy - 8, w, 17, theme=th, fill=th["paper"])
    txt = k.text(cx, cy + 4, label, theme=th, size=9, font="mono", fill=color, anchor="middle")
    return rect + txt


def render(src: dict, theme: str) -> str:
    th = k.THEMES[theme]
    nodes = src["nodes"]
    paths = src.get("paths", [])
    zones = src.get("zones", [])

    accents = sum(1 for p in paths if p.get("kind") == "accent")
    accents += sum(1 for n in nodes if n.get("accent"))
    needs_accent = accents > 0

    width = k.snap(src.get("width", 960))
    height = k.snap(src.get("height", 620))

    out = [build_defs(th, needs_accent, True)]
    out.append(k.rect(0, 0, width, height, theme=th, fill=th["paper"]))

    for z in zones:  # zones paint first, everything else over them
        out.append(f'<rect x="{k.snap(z["x"])}" y="{k.snap(z["y"])}" width="{k.snap(z["w"])}" '
                   f'height="{k.snap(z["h"])}" rx="8" fill="{th["ink"]}" fill-opacity="0.02" '
                   f'stroke="{th["ink"]}" stroke-opacity="0.20" stroke-width="1" '
                   f'stroke-dasharray="4,4"/>')
        zw = len(z["label"]) * 6 + 12
        out.append(k.rect(z["x"] + 12, z["y"] - 8, zw, 16, theme=th, fill=th["paper"]))
        out.append(k.text(z["x"] + 18, z["y"] + 4, z["label"].upper(), theme=th, size=8,
                          font="mono", weight=500, fill=th["muted"], tracking="1.4"))

    for p in paths:  # paths before nodes so arrowheads land on the box edge
        kind = p.get("kind", "muted")
        stroke = {"link": th["link"], "accent": th["accent"]}.get(kind, th["muted"])
        marker = {"link": "arrow-link", "accent": "arrow-accent"}.get(kind, "arrow")
        out.append(polyline(p["points"], stroke, "5,4" if p.get("dash") else None, marker))
        if p.get("label"):
            out.append(path_label(p["points"], p["label"], th, stroke, p.get("label_at")))

    index = {n["id"]: n for n in nodes}
    for n in nodes:
        accent = bool(n.get("accent"))
        fill = th["accent-tint"] if accent else th["paper"]
        stroke = th["accent"] if accent else th["ink"]
        out.append(k.rect(n["x"], n["y"], n["w"], n["h"], theme=th, fill=fill, stroke=stroke,
                          stroke_width=1.2 if accent else 1, radius=6))
        tag = n.get("tag", "HOST")
        tw = len(tag) * 5.6 + 10
        out.append(k.rect(n["x"], n["y"], tw, 14, theme=th, fill=th["ink"],
                          stroke=th["ink"], radius=2))
        out.append(k.text(n["x"] + 5, n["y"] + 10, tag, theme=th, size=7, font="mono",
                          weight=500, fill=th["paper"], tracking="1.2"))
        out.append(k.text(n["x"] + NODE_PAD, n["y"] + 31, n["name"], theme=th, size=13,
                          weight=600, fill=th["ink"]))
        if n.get("replicas"):
            bx = n["x"] + n["w"] - 26
            out.append(k.rect(bx, n["y"] + 5, 22, 12, theme=th, fill=th["ink"], stroke=th["ink"], radius=2))
            out.append(k.text(bx + 11, n["y"] + 14, n["replicas"], theme=th, size=7, font="mono",
                              fill=th["paper"], anchor="middle"))
        cy = n["y"] + 40
        for a in n.get("artifacts", []):
            # ONE rect. An earlier version painted a solid `ink` rect and then a
            # 5%-opacity rect on top: the translucent fill composited over solid
            # ink, so the chip went black in light mode and white in dark mode and
            # ate its own label. Contrast has to come from fill-opacity alone.
            out.append(f'<rect x="{k.snap(n["x"] + NODE_PAD)}" y="{k.snap(cy)}" '
                       f'width="{k.snap(n["w"] - 2 * NODE_PAD)}" height="{CHIP_H}" rx="4" '
                       f'fill="{th["ink"]}" fill-opacity="0.06" stroke="{th["rule-solid"]}" '
                       f'stroke-width="1"/>')
            out.append(k.text(n["x"] + NODE_PAD + 8, cy + 17, a["name"], theme=th, size=12, fill=th["ink"]))
            if a.get("version"):
                out.append(k.text(n["x"] + n["w"] - NODE_PAD - 8, cy + 17, a["version"], theme=th,
                                  size=9, font="mono", fill=th["muted"], anchor="end"))
            cy += CHIP_H + 8

    ly = height - 30
    out.append(k.line(24, ly - 18, width - 24, ly - 18, theme=th))
    lx = 24
    for item in src.get("legend", []):
        sw = item.get("swatch", "chip")
        if sw == "chip":
            out.append(f'<rect x="{lx}" y="{k.snap(ly - 9)}" width="26" height="14" rx="4" '
                       f'fill="{th["ink"]}" fill-opacity="0.05" stroke="{th["muted"]}"/>')
            lx += 34
        else:
            color = th["accent"] if sw == "accent-line" else th["link"] if sw == "link-line" else th["muted"]
            dash = ' stroke-dasharray="5,4"' if item.get("dash") else ""
            out.append(f'<line x1="{lx}" y1="{k.snap(ly - 2)}" x2="{lx + 26}" y2="{k.snap(ly - 2)}" '
                       f'stroke="{color}" stroke-width="1.4"{dash}/>')
            lx += 34
        out.append(k.text(lx, ly + 2, item["label"], theme=th, size=9, font="mono", fill=th["muted"]))
        lx += len(item["label"]) * 5.6 + 24

    counts = {"zones": len(zones), "nodes": len(nodes),
              "chips": sum(len(n.get("artifacts", [])) for n in nodes),
              "paths": len(paths), "accents": accents}
    over = [f"{kk} {v}>{BUDGET[kk]}" for kk, v in counts.items() if v > BUDGET[kk]]
    if over:
        out.append(k.text(24, height - 10, "over budget: " + ", ".join(over), theme=th, size=9,
                          font="mono", fill=th["accent"]))

    desc = (f"Deployment: {len(zones)} zones, {len(nodes)} hosts, "
            f"{counts['chips']} artifacts, {counts['paths']} labelled paths.")
    body = "\n  ".join(out)
    return k.frame(width, height, "  " + body, theme=theme, title_text=src.get("title", "Deployment"),
                   eyebrow_text="deployment · repo-docs-pipeline", slug=src.get("slug", "deployment"),
                   desc=desc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    a = ap.parse_args()
    src = json.load(open(a.src, encoding="utf-8"))
    k.write(a.out, render(src, a.theme))
    print(f"{a.out}: {len(src['zones'])} zones, {len(src['nodes'])} nodes, "
          f"{len(src.get('paths', []))} paths")


if __name__ == "__main__":
    main()
