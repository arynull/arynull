#!/usr/bin/env python3
"""Regenerate the custom SVG stat cards for rayanalpha's GitHub profile.

Run:  GITHUB_TOKEN=... python scripts/generate.py
Writes SVGs into assets/cards/. Safe to run daily from GitHub Actions.
Only stdlib is used so it also runs on a bare runner.
"""
from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date

USER = "rayanalpha"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "cards")

FEATURED = [
    "mantrap",
    "brushpass",
    "fresheyes",
    "spendfence",
    "logline",
    "factor",
    "Instareel",
]

BG = "#0a0a0a"
BORDER = "rgba(255,255,255,0.08)"
MUTED = "#737373"
TEXT = "#e5e5e5"
GRAYS = ["#d4d4d4", "#a3a3a3", "#808080", "#636363", "#525252"]


# ---------------------------------------------------------------- http helpers

def _req(path: str, method: str | None = None, data: bytes | None = None) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "rayanalpha-profile-cards",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    kw = {"method": method} if method else {}
    return urllib.request.Request(API + path, data=data, headers=headers, **kw)


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


# ---------------------------------------------------------------- svg helpers

def esc(s) -> str:
    return html.escape(str(s), quote=True)


def wrap(text: str, width: int) -> list[str]:
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if len(nxt) <= width:
            cur = nxt
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def defs_common() -> str:
    return """<defs>
    <linearGradient id="acc" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#4a4a4a"/><stop offset="1" stop-color="#262626"/>
    </linearGradient>
    <linearGradient id="panelg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#121212"/><stop offset="1" stop-color="#0a0a0a"/>
    </linearGradient>
  </defs>"""


def rank_gray(i: int, n: int) -> str:
    """Monochrome shade by rank: brightest first, fading to dark gray."""
    if n <= 1:
        return "#d4d4d4"
    v = int(212 - i * (212 - 63) / (n - 1))
    return f"#{v:02x}{v:02x}{v:02x}"


def card_open(w: int, h: int, title: str, emoji: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">',
        defs_common(),
        f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="16" fill="url(#panelg)" stroke="{BORDER}" stroke-width="1"/>',
        f'<rect x="1" y="1" width="{w - 2}" height="5" rx="2.5" fill="url(#acc)" opacity="0.9"/>',
        f'<text x="28" y="42" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13" '
        f'letter-spacing="3" fill="{MUTED}">{emoji}  {esc(title).upper()}</text>',
    ]


def write_svg(name: str, parts: list[str]) -> None:
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")
    os.replace(tmp, path)
    print("wrote", path)


# ---------------------------------------------------------------- data

def fetch_data() -> dict:
    user = rest(f"/users/{USER}")
    q = """{
      user(login: "%s") {
        contributionsCollection {
          contributionCalendar { totalContributions weeks { contributionDays { contributionCount } } }
        }
        repositories(first: 100, ownerAffiliations: OWNER, orderBy: {field: STARGAZERS, direction: DESC}) {
          totalCount
          nodes { name stargazerCount forkCount url languages(first: 20, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } }
        }
        pullRequests(first: 1) { totalCount }
        issues(first: 1) { totalCount }
      }
    }""" % USER
    g = graphql(q)["user"]
    cal = g["contributionsCollection"]["contributionCalendar"]

    repos = [r for r in g["repositories"]["nodes"]]
    lang_bytes: dict[str, int] = {}
    lang_color: dict[str, str] = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            lang_bytes[n] = lang_bytes.get(n, 0) + e["size"]
            lang_color[n] = e["node"]["color"] or "#8b949e"

    featured = []
    for name in FEATURED:
        info = rest(f"/repos/{USER}/{name}")
        if not info:
            continue
        rel = rest(f"/repos/{USER}/{name}/releases/latest")
        featured.append({
            "name": info["name"],
            "desc": info.get("description") or "",
            "lang": (info.get("language") or ""),
            "lang_color": lang_color.get(info.get("language") or "", "#8b949e"),
            "stars": info.get("stargazers_count", 0),
            "forks": info.get("forks_count", 0),
            "url": info.get("html_url", ""),
            "tag": (rel or {}).get("tag_name", ""),
        })

    years = max(1, date.today().year - 2020)
    return {
        "followers": user.get("followers", 0),
        "public_repos": user.get("public_repos", 0),
        "stars": sum(r["stargazerCount"] for r in repos),
        "forks": sum(r["forkCount"] for r in repos),
        "contrib": cal["totalContributions"],
        "prs": g["pullRequests"]["totalCount"],
        "issues": g["issues"]["totalCount"],
        "years": years,
        "weeks": [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal["weeks"]][-12:],
        "langs": sorted(lang_bytes.items(), key=lambda kv: -kv[1])[:8],
        "lang_color": lang_color,
        "featured": featured,
        "total_bytes": sum(lang_bytes.values()) or 1,
    }


# ---------------------------------------------------------------- cards

def overview_card(d: dict) -> None:
    w, h = 800, 196
    p = card_open(w, h, "GitHub Overview", "")
    stats = [
        ("★", f"{d['stars']:,}", "TOTAL STARS"),
        ("⑂", f"{d['forks']:,}", "FORKS"),
        ("▤", f"{d['public_repos']:,}", "PUBLIC REPOS"),
        ("◈", f"{d['contrib']:,}", "CONTRIBUTIONS / YR"),
        ("◐", f"{d['years']}", "YEARS ON GITHUB"),
    ]
    n = len(stats)
    cell = (w - 56) / n
    for i, (glyph, val, label) in enumerate(stats):
        x = 28 + cell * i + cell / 2
        p.append(f'<text x="{x:.0f}" y="96" text-anchor="middle" font-family="ui-monospace,Menlo,Consolas,monospace" '
                 f'font-size="15" fill="{GRAYS[i % len(GRAYS)]}">{glyph}</text>')
        p.append(f'<text x="{x:.0f}" y="132" text-anchor="middle" font-family="ui-monospace,Menlo,Consolas,monospace" '
                 f'font-size="30" font-weight="700" fill="{TEXT}">{esc(val)}</text>')
        p.append(f'<text x="{x:.0f}" y="158" text-anchor="middle" font-family="ui-monospace,Menlo,Consolas,monospace" '
                 f'font-size="10.5" letter-spacing="1.5" fill="{MUTED}">{label}</text>')
        if i < n - 1:
            sx = 28 + cell * (i + 1)
            p.append(f'<line x1="{sx:.0f}" y1="80" x2="{sx:.0f}" y2="160" stroke="{BORDER}" stroke-width="1"/>')
    p.append("</svg>")
    write_svg("overview.svg", p)


def languages_card(d: dict) -> None:
    rows = d["langs"]
    rh, top = 34, 66
    h = top + len(rows) * rh + 26
    w = 800
    p = card_open(w, h, "Top Languages", "")
    bar_x, bar_w = 210, w - 210 - 90
    for i, (name, size) in enumerate(rows):
        y = top + i * rh
        pct = size / d["total_bytes"] * 100
        bw = max(4, bar_w * pct / 100)
        color = rank_gray(i, len(rows))
        p.append(f'<circle cx="40" cy="{y + 6}" r="6" fill="{color}"/>')
        p.append(f'<text x="56" y="{y + 11}" font-family="ui-monospace,Menlo,Consolas,monospace" font-size="13.5" fill="{TEXT}">{esc(name)}</text>')
        p.append(f'<rect x="{bar_x}" y="{y}" width="{bar_w}" height="12" rx="6" fill="#1a1a1a"/>')
        p.append(f'<rect x="{bar_x}" y="{y}" width="{bw:.0f}" height="12" rx="6" fill="{color}"/>')
        p.append(f'<text x="{w - 28}" y="{y + 11}" text-anchor="end" font-family="ui-monospace,Menlo,Consolas,monospace" '
                 f'font-size="12.5" fill="{MUTED}">{pct:.1f}%</text>')
    p.append("</svg>")
    write_svg("languages.svg", p)


def rhythm_card(d: dict) -> None:
    weeks = d["weeks"]
    w, h = 800, 226
    p = card_open(w, h, "Contribution Rhythm · last 12 weeks", "")
    base_y, max_h, left, gap = 190, 100, 60, 56
    peak = max(weeks) or 1
    for i, v in enumerate(weeks):
        bh = max(6, max_h * v / peak)
        x = left + i * gap
        op = 0.25 + 0.75 * (v / peak)
        p.append(f'<rect x="{x}" y="{base_y - bh:.0f}" width="34" height="{bh:.0f}" rx="7" fill="#d4d4d4" opacity="{op:.2f}"/>')
        p.append(f'<text x="{x + 17}" y="{base_y + 20}" text-anchor="middle" font-family="ui-monospace,Menlo,Consolas,monospace" '
                 f'font-size="11" fill="{MUTED}">W{i + 1}</text>')
        p.append(f'<text x="{x + 17}" y="{base_y - bh - 8:.0f}" text-anchor="middle" font-family="ui-monospace,Menlo,Consolas,monospace" '
                 f'font-size="11" font-weight="700" fill="{TEXT}">{v}</text>')
    p.append("</svg>")
    write_svg("rhythm.svg", p)


def project_cards(d: dict) -> None:
    w, h = 400, 168
    for f in d["featured"]:
        p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">',
             defs_common(),
             f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="url(#panelg)" stroke="{BORDER}"/>',
             f'<rect x="20" y="1" width="{w - 40}" height="2" fill="#2e2e2e"/>',
             f'<text x="22" y="44" font-family="ui-monospace,Menlo,Consolas,monospace" font-size="19" font-weight="700" fill="{TEXT}">{esc(f["name"])}</text>']
        if f["tag"]:
            p.append(f'<rect x="{w - 24 - len(f["tag"]) * 8.4 - 18}" y="24" width="{len(f["tag"]) * 8.4 + 18:.0f}" height="22" rx="11" '
                     f'fill="none" stroke="#525252" stroke-width="1"/>')
            p.append(f'<text x="{w - 24 - (len(f["tag"]) * 8.4 + 18) / 2:.0f}" y="40" text-anchor="middle" '
                     f'font-family="ui-monospace,Menlo,Consolas,monospace" font-size="11.5" fill="#a3a3a3">{esc(f["tag"])}</text>')
        for j, line in enumerate(wrap(f["desc"], 46)):
            p.append(f'<text x="22" y="{72 + j * 20}" font-family="ui-monospace,Menlo,Consolas,monospace" '
                     f'font-size="12.5" fill="{MUTED}">{esc(line)}</text>')
        fy = h - 24
        p.append(f'<circle cx="30" cy="{fy - 4}" r="6" fill="#737373"/>')
        p.append(f'<text x="44" y="{fy}" font-family="ui-monospace,Menlo,Consolas,monospace" font-size="12.5" fill="{TEXT}">{esc(f["lang"])}</text>')
        p.append(f'<text x="{w - 96}" y="{fy}" font-family="ui-monospace,Menlo,Consolas,monospace" font-size="12.5" fill="#d4d4d4">★ {f["stars"]}</text>')
        p.append(f'<text x="{w - 28}" y="{fy}" text-anchor="end" font-family="ui-monospace,Menlo,Consolas,monospace" font-size="12.5" fill="{MUTED}">⑂ {f["forks"]}</text>')
        p.append("</svg>")
        write_svg(f"projects/{f['name']}.svg", p)

    # "more" card
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">',
         defs_common(),
         f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="none" stroke="{BORDER}" stroke-width="1.5" stroke-dasharray="8 6"/>',
         f'<text x="{w / 2:.0f}" y="{h / 2 - 4:.0f}" text-anchor="middle" font-family="ui-monospace,Menlo,Consolas,monospace" '
         f'font-size="20" font-weight="700" fill="#e5e5e5">+ explore all repos →</text>',
         f'<text x="{w / 2:.0f}" y="{h / 2 + 24:.0f}" text-anchor="middle" font-family="ui-monospace,Menlo,Consolas,monospace" '
         f'font-size="12.5" fill="{MUTED}">github.com/{USER}?tab=repositories</text>',
         "</svg>"]
    write_svg("projects/more.svg", p)


def main() -> int:
    try:
        data = fetch_data()
    except Exception as e:  # never wipe good cards on a transient API failure
        print(f"fetch failed, keeping existing cards: {e}", file=sys.stderr)
        return 1
    overview_card(data)
    languages_card(data)
    rhythm_card(data)
    project_cards(data)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
