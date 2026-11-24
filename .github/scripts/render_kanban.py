#!/usr/bin/env python3
"""Render a roadmap kanban SVG from a README roadmap section (or a JSON file).

Follows the type conventions: 240px columns with 32px gutters, column fill
instead of borders, a rectangular (rx=2, never a pill) WIP chip carrying n/limit
on in-process columns and a bare n on the queue/terminal columns, rx=6 cards
56px tall with a muted "ID · state" sublabel, and the four card states —
default, blocked, waiting, done. A board has no connectors: it is a state
census, not a flow.

Source shapes, because real roadmaps use both:
    | M1 | Kernel boots + serial console | 100% |          state from the cell
    - **M8-S4 — Wi-Fi. ⏳ Blocked at PHY detection.** ...   state from the title

Deterministic: source order is preserved, nothing is sorted or sampled.

  python3 render_kanban.py --src README.md --section Roadmap --out docs/diagrams/roadmap.svg
  python3 render_kanban.py --src docs/data/roadmap.json --out roadmap.svg --theme dark
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import svgkit as k  # noqa: E402

# (key, label, wip limit). `None` = bare count: a queue has no limit, and
# nothing is constrained by holding more finished work.
COLS = [
    ("done", "Done", None),
    ("doing", "Active", 2),
    ("blocked", "Blocked", 2),
    ("next", "Next", None),
]
STATE_OF_COL = {"done": "done", "doing": "default", "blocked": "blocked", "next": "waiting"}

COL_W, GUTTER, PAD = 240, 32, 24
CARD_H, CARD_GAP = 56, 12
MAX_PER_COL, MAX_CARDS = 4, 12
ACCENT_BUDGET = 2

TABLE = re.compile(r"^\|\s*(?P<id>[A-Za-z]{1,4}\d*[A-Za-z0-9\u2605\-]*)\s*\|\s*(?P<title>[^|]{3,90}?)\s*\|\s*(?P<tail>[^|]*)\|")
BULLET = re.compile(r"^\s*[-*]\s+\*\*(?P<id>[A-Za-z]{1,4}\d*[A-Za-z0-9\u2605\-]*)\s*[:\u2014\u2013-]\s*(?P<title>[^*]{3,90}?)[.:]?\*\*\s*(?P<tail>.*)$")
HEAD = re.compile(r"^(?P<level>#{2,4})\s+(?P<h>.+?)\s*$")
STATE_TAIL = re.compile(r"(?i)\s*[\u2014\u2013-]?\s*(closed|pending|blocked|active|current focus|answered|partially verified|in progress|complete|done|\u2705|\u23f3|\u25b6|\U0001f52e|\u2605)[^.]*\.?\s*$")
STATE_WORD = re.compile(r"(?i)\b(closed|pending|blocked|active|current focus|answered|partially verified|in progress|complete)\b")

DONE = re.compile(r"✅|\bclosed\b|\banswered\b|\bcomplete[d]?\b|\bdone\b|100\s?%", re.I)
DOING = re.compile(r"▶|🔄|\bactive\b|current focus|in progress", re.I)
BLOCKED = re.compile(r"blocked|⛔", re.I)
LATER = re.compile(r"🔮|\bfuture\b|\bparked\b|post-v1", re.I)

SHORT_CELL = 24  # a table cell is a state field; a sentence of prose is not


def classify(state_text: str, heading: str) -> str:
    """State comes from the milestone's own marker, not from its narrative.

    Scanning the whole line misfiles real roadmaps: 'A completed recovery
    extraction is not sufficient evidence' reads as *done*. Only the bold title
    counts, plus a short table cell ('100%') - never a full sentence."""
    t = state_text or ""
    if BLOCKED.search(t):
        return "blocked"
    if LATER.search(t):
        return "later"
    if DONE.search(t):
        return "done"
    if DOING.search(t):
        return "doing"
    h = heading or ""
    if LATER.search(h):
        return "later"
    if DONE.search(h):
        return "done"
    return "next"


def meta_of(text: str) -> str:
    pct = re.search(r"(\d{1,3})\s?%", text)
    if pct:
        return f"{pct.group(1)}%"
    if "✅" in text:
        return "closed"
    if "▶" in text:
        return "active"
    if "⏳" in text:
        return "blocked" if "blocked" in text.lower() else "pending"
    if "🔮" in text:
        return "later"
    return ""


def from_markdown(path: str, section: str | None) -> dict[str, list[dict]]:
    """Walk the roadmap section and let each line's own marker set its column.

    Closeout subsections repeat milestones that already appear in the summary
    table; dedupe by id (first occurrence wins) is what keeps those from
    double-listing, not a section blacklist."""
    cols: dict[str, list[dict]] = {c: [] for c, _, _ in COLS}
    seen: set[str] = set()
    inside = section is None
    section_level = 0
    heading = ""
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        h = HEAD.match(line)
        if h:
            lvl, heading = len(h.group("level")), h.group("h")
            if section and (heading or "").lower().startswith(section.lower()):
                inside, section_level = True, lvl
            elif inside and lvl <= section_level and not heading.lower().startswith(section.lower()):
                inside = False
            continue
        if not inside:
            continue
        m = TABLE.match(line) or BULLET.match(line)
        if not m:
            continue
        ident = m.group("id").strip()
        if ident in seen:  # same milestone quoted later in closeout notes
            continue
        raw_title = m.group("title").strip()
        tail = m.group("tail")
        # The state marker usually lives INSIDE the bold title ("⏳ Pending",
        # "✅ Partially verified"), so classify on title+short-cell and clean
        # the marker out of the displayed label afterwards.
        cell = tail if len(tail.strip()) <= SHORT_CELL else ""
        col = classify(raw_title + " " + cell, heading)
        if col == "later":
            continue
        title = STATE_TAIL.sub("", raw_title).replace("**", "").replace("`", "")
        title = re.sub(r"\s*\(([^)]*)\)\s*$", "", title).strip(" .:\u2014-\u2605")
        word = STATE_WORD.search(raw_title)
        meta = meta_of(raw_title + " " + cell) or (word.group(1).lower() if word else "")
        seen.add(ident)
        cols[col].append({"id": ident, "title": title, "meta": meta})
    return cols


def from_json(path: str) -> dict[str, list[dict]]:
    data = json.load(open(path, encoding="utf-8"))
    cols: dict[str, list[dict]] = {c: [] for c, _, _ in COLS}
    items = data["items"] if isinstance(data, dict) else data
    for it in items:
        col = it.get("column", "next")
        if col in cols:
            cols[col].append({"id": it.get("id", ""), "title": it.get("title", ""),
                              "meta": it.get("meta", "")})
    return cols


def card_style(state: str, th) -> tuple[str, str, str, str]:
    """(fill, stroke, dash, fill-opacity) for the four card states."""
    if state == "blocked":
        return th["accent"], th["accent"], "4,4", "0.05"
    if state == "waiting":
        return th["ink"], th["ink"], "4,3", "0.02"
    if state == "done":
        return th["ink"], th["muted"], "", "0.05"
    return th["paper"], th["ink"], "", "1"


def render(cols, theme, title_text, subtitle) -> str:
    th = k.THEMES[theme]
    width = k.snap(PAD * 2 + COL_W * len(COLS) + GUTTER * (len(COLS) - 1))
    total = sum(len(v) for v in cols.values())

    # Accent budget is 2: one over-limit chip, one blocked card.
    over_limit = [key for key, _, lim in COLS if lim and len(cols[key]) > lim]
    blocked_focal = bool(cols["blocked"]) and len(over_limit) < ACCENT_BUDGET

    shown = {key: cards[:MAX_PER_COL] for key, cards in cols.items()}
    rows = max([len(v) for v in shown.values()] + [1])
    board_top = 152
    height = k.snap(board_top + rows * (CARD_H + CARD_GAP) + 96)

    out: list[str] = []
    if subtitle:
        out.append(k.text(PAD, 96, subtitle, theme=th, size=12, fill=th["muted"]))

    for ci, (key, label, limit) in enumerate(COLS):
        cards = shown[key]
        x = PAD + ci * (COL_W + GUTTER)
        state = STATE_OF_COL[key]

        out.append(f'<rect x="{k.snap(x)}" y="{k.snap(board_top - 44)}" width="{COL_W}" '
                   f'height="{k.snap(height - board_top + 16)}" rx="6" fill="{th["ink"]}" fill-opacity="0.02"/>')
        out.append(k.text(x + 12, board_top - 24, label, theme=th, size=12, weight=600))

        over = bool(limit and len(cols[key]) > limit)
        chip = f"{len(cols[key])}/{limit}" if limit else f"{len(cols[key])}"
        cw = k.snap(len(chip) * 6 + 12)
        cx = x + COL_W - 12 - cw
        out.append(f'<rect x="{k.snap(cx)}" y="{k.snap(board_top - 34)}" width="{cw}" height="16" rx="2" '
                   f'fill="none" stroke="{th["accent"] if over else th["rule"]}" stroke-width="1"/>')
        out.append(k.text(cx + cw / 2, board_top - 22, chip, theme=th, size=8, font="mono",
                          weight=500, fill=th["accent"] if over else th["muted"], anchor="middle"))
        out.append(k.line(x + 8, board_top - 10, x + COL_W - 8, board_top - 10, theme=th))

        for i, card in enumerate(cards):
            y = board_top + i * (CARD_H + CARD_GAP)
            focal = state == "blocked" and blocked_focal and i == 0
            fill, stroke, dash, op = card_style(state, th)
            out.append(f'<rect x="{k.snap(x + 8)}" y="{k.snap(y)}" width="{COL_W - 16}" height="{CARD_H}" rx="6" '
                       f'fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="1"'
                       + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
            if state == "blocked":  # 4px accent bar on the left edge
                out.append(f'<rect x="{k.snap(x + 8)}" y="{k.snap(y)}" width="4" height="{CARD_H}" '
                           f'rx="2" fill="{th["accent"]}"/>')
            out.append(k.text(x + 22, y + 24, card["title"][:30], theme=th, size=12, weight=600))
            sub = " · ".join(p for p in (card["id"], card["meta"]) if p)
            if sub:
                out.append(k.text(x + 22, y + 42, sub, theme=th, size=9, font="mono", fill=th["soft"]))
        if len(cols[key]) > MAX_PER_COL:
            out.append(k.text(x + 22, board_top + MAX_PER_COL * (CARD_H + CARD_GAP) + 2,
                              f"+{len(cols[key]) - MAX_PER_COL} more", theme=th, size=9,
                              font="mono", fill=th["muted"]))

    ly = height - 40
    out.append(k.line(PAD, ly - 18, width - PAD, ly - 18, theme=th))
    lx = PAD
    for label, state in (("default", "default"), ("blocked", "blocked"),
                         ("waiting", "waiting"), ("done", "done")):
        fill, stroke, dash, op = card_style(state, th)
        out.append(f'<rect x="{k.snap(lx)}" y="{k.snap(ly - 7)}" width="18" height="14" rx="4" fill="{fill}" '
                   f'fill-opacity="{op}" stroke="{stroke}" stroke-width="1"'
                   + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
        out.append(k.text(lx + 24, ly + 4, label, theme=th, size=9, font="mono", fill=th["muted"]))
        lx += k.snap(24 + len(label) * 6 + 26)

    if total > MAX_CARDS:
        out.append(k.text(width - PAD, height - 10, f"{total} items - over the 12-card budget",
                          theme=th, size=9, font="mono", fill=th["soft"], anchor="end"))

    desc = ("Roadmap board: " + ", ".join(f"{len(cols[key])} {label.lower()}"
            for key, label, _ in COLS) + ".")
    body = "\n  ".join(out)
    return k.frame(width, height, "  " + body, theme=theme, title_text=title_text,
                   eyebrow_text="kanban · repo-docs-pipeline", slug="roadmap", desc=desc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--section", help="markdown heading to start from (prefix match)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--title", default="Roadmap")
    ap.add_argument("--subtitle", default="")
    a = ap.parse_args()
    cols = from_json(a.src) if a.src.endswith(".json") else from_markdown(a.src, a.section)
    k.write(a.out, render(cols, a.theme, a.title, a.subtitle))
    print(f"{a.out}: " + ", ".join(f"{key}={len(v)}" for key, v in cols.items()))


if __name__ == "__main__":
    main()
