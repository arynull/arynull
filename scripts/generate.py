#!/usr/bin/env python3
"""Generate arynull's GitHub profile card in the GitAscii style
(Igorcbraz/GitAscii): near-black widget panels, lime "+" corner marks,
ASCII avatar, neofetch terminal panel, top-languages bar, skills chips,
static contribution grid. Self-hosted, stdlib-only, refreshed by
.github/workflows/cards.yml.
"""
from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date

USER = "arynull"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

FEATURED = ["mantrap", "brushpass", "fresheyes", "spendfence", "logline", "factor", "Instareel"]
SKILLS = ["Python", "TypeScript", "JavaScript", "FastAPI", "Docker", "PostgreSQL", "Redis", "React"]

# GitAscii palette
BG = "#060606"
PANEL_BORDER = "#252525"
LIME = "#c5ff4a"
INK = "#e5e5e5"
MUTED = "#7a7a7a"
AMBER = "#ffb800"
BLUE = "#58a6ff"
NUMBLUE = "#79c0ff"
LEADER = "#484f58"
RULE = "#3d444d"
VALUE = "#c9d1d9"

MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
SANS = "'Inter Tight',system-ui,-apple-system,sans-serif"

LANG_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "HTML": "#e34c26", "CSS": "#563d7c", "Hack": "#878787", "Shell": "#89e051",
    "Dockerfile": "#384d54", "Vue": "#41b883",
}


# ---------------------------------------------------------------- http

def _req(path: str, data: bytes | None = None) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "arynull-profile-card",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(API + path, data=data, headers=headers)


def rest(path: str):
    try:
        with urllib.request.urlopen(_req(path), timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def graphql(query: str) -> dict:
    payload = json.dumps({"query": query}).encode()
    with urllib.request.urlopen(_req("/graphql", data=payload), timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body["data"]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- data

def fetch_data() -> dict:
    q = """{
      user(login: "%s") {
        contributionsCollection {
          contributionCalendar { totalContributions weeks { contributionDays { contributionCount } } }
        }
        repositories(first: 100, ownerAffiliations: OWNER) {
          totalCount
          nodes { stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } } } }
        }
      }
    }""" % USER
    g = graphql(q)["user"]
    repos = g["repositories"]["nodes"]
    lang_bytes: dict[str, int] = {}
    lang_color: dict[str, str] = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            lang_bytes[n] = lang_bytes.get(n, 0) + e["size"]
            if e["node"]["color"]:
                lang_color[n] = e["node"]["color"]
    total = sum(lang_bytes.values()) or 1
    langs = []
    for n, s in sorted(lang_bytes.items(), key=lambda kv: -kv[1])[:5]:
        langs.append((n, s / total * 100, lang_color.get(n, LANG_COLORS.get(n, "#8b949e"))))
    user = rest(f"/users/{USER}")
    created = date.fromisoformat(user["created_at"][:10])
    today = date.today()
    months = (today.year - created.year) * 12 + (today.month - created.month)
    uptime = f"{months // 12} years, {months % 12} months" if months >= 12 else f"{months} months"
    weeks = [[d["contributionCount"] for d in w["contributionDays"]] for w in
             g["contributionsCollection"]["contributionCalendar"]["weeks"]]
    return {
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": user.get("public_repos", 0),
        "contrib": g["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "followers": user.get("followers", 0),
        "uptime": uptime,
        "joined": created.strftime("%b %Y"),
        "langs": langs,
        "weeks": weeks,
    }


# ---------------------------------------------------------------- svg helpers

def panel_open(x: int, y: int, w: int, h: int) -> list[str]:
    """GitAscii widget chrome: bordered panel + lime '+' corner marks."""
    return [
        f'<g transform="translate({x},{y})">',
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{BG}" stroke="{PANEL_BORDER}" stroke-width="1"/>',
        f'<text x="6" y="14" font-family="{MONO}" font-size="10" fill="{LIME}">+</text>',
        f'<text x="{w - 14}" y="14" font-family="{MONO}" font-size="10" fill="{LIME}">+</text>',
    ]


def section_title(x: int, y: int, title: str) -> str:
    return (f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="11" font-weight="500" '
            f'fill="{MUTED}" letter-spacing="2">[ {esc(title.upper())} ]</text>')


def term_row(x: int, y: int, label: str, value: str, width: int = 46,
             value_color: str = VALUE) -> str:
    dots = max(2, width - len(label) - len(value))
    return (f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="14">'
            f'<tspan fill="{AMBER}">. {esc(label)}:</tspan>'
            f'<tspan fill="{LEADER}"> {"." * dots} </tspan>'
            f'<tspan fill="{value_color}">{esc(value)}</tspan></text>')


def term_rule(x: int, y: int, title: str, width: int = 36) -> str:
    side = max(4, (width - len(title) - 2) // 2)
    rest = max(4, width - side - len(title) - 2)
    return (f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="14">'
            f'<tspan fill="{RULE}">{"─" * side} </tspan>'
            f'<tspan fill="{BLUE}">{esc(title)}</tspan>'
            f'<tspan fill="{RULE}"> {"─" * rest}</tspan></text>')


# ---------------------------------------------------------------- widgets

def header() -> list[str]:
    p = panel_open(0, 0, 800, 90)
    p.append(f'<text x="24" y="44" font-family="{MONO}" font-size="28" font-weight="300" fill="{INK}">arynull</text>')
    p.append(f'<text x="24" y="72" font-family="{MONO}" font-size="14" fill="{LIME}">software engineer</text>')
    p.append(f'<text x="776" y="44" text-anchor="end" font-family="{SANS}" font-size="12" fill="{MUTED}">[ Tehran, IR ]</text>')
    p.append("</g>")
    return p


def avatar_panel() -> list[str]:
    """Lime ASCII portrait, GitAscii style: density chars '.', '*', '#'."""
    with open(os.path.join(OUT, "avatar.json"), encoding="utf-8") as f:
        data = json.load(f)
    cols, rows = data["cols"], data["rows"]
    p = panel_open(0, 106, 280, 280)
    fs = 9
    adv = fs * 0.6
    step = 248 / rows
    x0 = 16 + (248 - cols * adv) / 2
    for r in range(rows):
        chars = []
        for c in range(cols):
            g = data["grays"][r][c]
            ch = "#" if g >= 185 else ("*" if g >= 110 else ("." if g >= 35 else " "))
            chars.append(ch)
        p.append(f'<text x="{x0:.1f}" y="{16 + 8 + r * step:.1f}" font-family="{MONO}" '
                 f'font-size="{fs}" fill="{LIME}" xml:space="preserve">{esc("".join(chars))}</text>')
    p.append("</g>")
    return p


def terminal_panel(d: dict) -> list[str]:
    x0, w = 296, 504
    p = panel_open(x0, 106, w, 280)
    x, y0, st = 24, 30, 18
    p.append(term_rule(x, y0, "arynull@github")); y = y0 + st
    p.append(term_row(x, y, "Uptime", d["uptime"])); y += st
    p.append(term_row(x, y, "Focus", "devtools · security · automation")); y += st
    p.append(term_row(x, y, "Languages", ", ".join(n for n, _, _ in d["langs"]))); y += st
    p.append(term_row(x, y, "Joined", d["joined"])); y += st + 4
    p.append(term_rule(x, y, "Contact")); y += st
    p.append(term_row(x, y, "Telegram", "@SameOldAryan")); y += st
    p.append(term_row(x, y, "Instagram", "@th3.rayan")); y += st
    p.append(term_row(x, y, "GitHub", "github.com/arynull")); y += st + 4
    p.append(term_rule(x, y, "GitHub Stats")); y += st
    # two-up stats with blue numbers
    def stat_pair(y, l1, v1, l2, v2):
        return (f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="14">'
                f'<tspan fill="{AMBER}">. {l1}:</tspan><tspan fill="{LEADER}"> ...... </tspan>'
                f'<tspan fill="{NUMBLUE}">{v1}</tspan>'
                f'<tspan fill="{RULE}">   |   </tspan>'
                f'<tspan fill="{AMBER}">. {l2}:</tspan><tspan fill="{LEADER}"> ...... </tspan>'
                f'<tspan fill="{NUMBLUE}">{v2}</tspan></text>')
    p.append(stat_pair(y, "Repos", f'{d["repos"]:,}', "Stars", f'{d["stars"]:,}')); y += st
    p.append(stat_pair(y, "Contrib", f'{d["contrib"]:,}', "Followers", f'{d["followers"]:,}'))
    p.append("</g>")
    return p


def languages_panel(d: dict) -> list[str]:
    x0, w, h = 0, 504, 140
    p = panel_open(x0, 400, w, h)
    p.append(section_title(24, 32, "Top Languages"))
    # stacked proportional bar
    bx, bw, by, bh = 24, w - 48, 52, 8
    xx = bx
    for _, pct, color in d["langs"]:
        seg = bw * pct / 100
        p.append(f'<rect x="{xx:.1f}" y="{by}" width="{max(2, seg):.1f}" height="{bh}" fill="{esc(color)}" rx="2"/>')
        xx += seg
    # legend, two columns
    lx = [24, 260]
    ly = [84, 108, 132]
    for i, (name, pct, color) in enumerate(d["langs"]):
        cx, cy = lx[i % 2], ly[i // 2]
        p.append(f'<circle cx="{cx}" cy="{cy - 4}" r="4" fill="{esc(color)}"/>')
        p.append(f'<text x="{cx + 12}" y="{cy}" font-family="{SANS}" font-size="12" fill="{INK}">'
                 f'{esc(name)}<tspan fill="{MUTED}">  {pct:.1f}%</tspan></text>')
    p.append("</g>")
    return p


def skills_panel() -> list[str]:
    x0, w, h = 520, 280, 140
    p = panel_open(x0, 400, w, h)
    p.append(section_title(24, 32, "Technologies & Skills"))
    cw, chh, gap = 72, 26, 10
    for i, s in enumerate(SKILLS):
        col, row = i % 3, i // 3
        cx = 24 + col * (cw + gap)
        cy = 48 + row * (chh + gap)
        p.append(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{chh}" fill="{BG}" stroke="{PANEL_BORDER}"/>')
        p.append(f'<text x="{cx + cw / 2:.0f}" y="{cy + 17}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="10" fill="{INK}">{esc(s)}</text>')
    p.append("</g>")
    return p


def contributions_panel(d: dict) -> list[str]:
    x0, y0, w, h = 0, 554, 800, 228
    p = panel_open(x0, y0, w, h)
    p.append(section_title(24, 32, "Contributions"))
    weeks = d["weeks"][-53:]
    cell, gap, step = 11, 3, 14
    gx, gy = 24, 58
    mx = max((c for wk in weeks for c in wk), default=1)
    def color(c):
        if c == 0:
            return "#161b22"
        q = c / mx
        if q < 0.25:
            return "#01311f"
        if q < 0.5:
            return "#034525"
        if q < 0.75:
            return "#0f6d31"
        return "#00c647"
    for wi, wk in enumerate(weeks):
        for di, c in enumerate(wk[:7]):
            p.append(f'<rect x="{gx + wi * step}" y="{gy + di * step}" width="{cell}" height="{cell}" '
                     f'fill="{color(c)}" rx="2"/>')
    # Less → More legend
    lx = w - 150
    p.append(f'<text x="{lx}" y="{gy + 7 * step + 22}" font-family="{SANS}" font-size="11" fill="{MUTED}">Less</text>')
    for i, col in enumerate(["#161b22", "#01311f", "#034525", "#0f6d31", "#00c647"]):
        p.append(f'<rect x="{lx + 38 + i * 14}" y="{gy + 7 * step + 13}" width="11" height="11" fill="{col}" rx="2"/>')
    p.append(f'<text x="{lx + 116}" y="{gy + 7 * step + 22}" font-family="{SANS}" font-size="11" fill="{MUTED}">More</text>')
    p.append("</g>")
    return p


# ---------------------------------------------------------------- main

def main() -> int:
    try:
        data = fetch_data()
    except Exception as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 1
    w, h = 800, 782
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">',
         f'<rect width="{w}" height="{h}" fill="{BG}"/>']
    p += header()
    p += avatar_panel()
    p += terminal_panel(data)
    p += languages_panel(data)
    p += skills_panel()
    p += contributions_panel(data)
    p.append("</svg>")
    path = os.path.join(OUT, "profile.svg")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(p) + "\n")
    os.replace(tmp, path)
    print("wrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
