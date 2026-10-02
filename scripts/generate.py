#!/usr/bin/env python3
"""Generate rayanalpha's GitHub profile card — a single monochrome ASCII
terminal card (GitAscii-style, but hand-built and self-hosted).

Run:  GITHUB_TOKEN=... python scripts/generate.py
Writes assets/profile.svg. Safe to run daily from GitHub Actions.
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
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

FEATURED = ["mantrap", "brushpass", "fresheyes", "spendfence", "logline", "factor", "Instareel"]

# --- palette: monochrome, quiet -------------------------------------------
BG = "#0a0a0a"
BORDER = "rgba(255,255,255,0.09)"
DIM = "#5c5c5c"      # labels, leaders
MID = "#8f8f8f"      # secondary text
TXT = "#d6d6d6"      # values
BRIGHT = "#f0f0f0"   # prompts, art
FAINT = "#2b2b2b"    # empty bar blocks

ASCII_NAME = [
    "                                       __      __",
    "   _________ ___  ______ _____  ____ _/ /___  / /_  ____ _",
    "  / ___/ __ `/ / / / __ `/ __ \\/ __ `/ / __ \\/ __ \\/ __ `/",
    " / /  / /_/ / /_/ / /_/ / / / / /_/ / / /_/ / / / / /_/ /",
    "/_/   \\__,_/\\__, /\\__,_/_/ /_/\\__,_/_/ .___/_/ /_/\\__,_/",
    "           /____/                   /_/",
]

MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


# ---------------------------------------------------------------- http helpers

def _req(path: str, data: bytes | None = None) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "rayanalpha-profile-card",
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
          contributionCalendar { totalContributions }
        }
        repositories(first: 100, ownerAffiliations: OWNER) {
          totalCount
          nodes { name stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name } } } }
        }
      }
    }""" % USER
    g = graphql(q)["user"]
    repos = g["repositories"]["nodes"]
    lang_bytes: dict[str, int] = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            lang_bytes[n] = lang_bytes.get(n, 0) + e["size"]
    total = sum(lang_bytes.values()) or 1
    user = rest(f"/users/{USER}")
    return {
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": user.get("public_repos", 0),
        "contrib": g["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "years": max(1, date.today().year - 2020),
        "langs": [(n, s / total * 100) for n, s in sorted(lang_bytes.items(), key=lambda kv: -kv[1])[:5]],
    }


# ---------------------------------------------------------------- the card

def leader(label: str, value: str, width: int = 62) -> str:
    dots = max(2, width - len(label) - len(value))
    return f"{label} {'.' * dots} {value}"


def profile_card(d: dict) -> None:
    w = 780
    lines: list[tuple[str, str]] = []  # (text, color)

    def se(text: str = "", color: str = TXT):
        lines.append((text, color))

    # ascii name
    for a in ASCII_NAME:
        se(a, "#a8a8a8")
    se()
    # whoami
    se("$ whoami", BRIGHT)
    se("  " + leader("role", "software engineer"), DIM)
    se("  " + leader("focus", "devtools · security · automation"), DIM)
    se("  " + leader("base", "tehran, ir — utc+3:30"), DIM)
    se()
    # stats
    se("$ stats --year", BRIGHT)
    se("  " + leader("stars", f"{d['stars']:,}"), DIM)
    se("  " + leader("repositories", f"{d['repos']:,}"), DIM)
    se("  " + leader("contributions", f"{d['contrib']:,}"), DIM)
    se("  " + leader("years on github", str(d["years"])), DIM)
    se()
    # languages (bars drawn as rects — bulletproof rendering, no font glyphs needed)
    se("$ langs --top", BRIGHT)
    for name, pct in d["langs"]:
        lines.append(("__bar__", name, pct))
    se()
    # builds
    se("$ ls ~/builds", BRIGHT)
    names = [n + "/" for n in FEATURED]
    for i in range(0, len(names), 2):
        row = "  " + names[i].ljust(36)
        if i + 1 < len(names):
            row += names[i + 1]
        se(row.rstrip(), MID)
    se()
    # contact
    se("$ cat contact.txt", BRIGHT)
    se("  " + leader("github", "rayanalpha"), DIM)
    se("  " + leader("telegram", "@SameOldAryan"), DIM)
    se("  " + leader("instagram", "@th3.rayan"), DIM)
    se()

    fs, lh, pad = 14, 24, 44
    h = pad * 2 + len(lines) * lh + 10
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">',
        "<defs>",
        '<linearGradient id="panelg" x1="0" y1="0" x2="0" y2="1">',
        '<stop offset="0" stop-color="#101010"/><stop offset="1" stop-color="#0a0a0a"/>',
        "</linearGradient>",
        "</defs>",
        f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="url(#panelg)" stroke="{BORDER}"/>',
    ]
    y = pad + 4
    chw = 8.4  # approx advance of 14px monospace
    for item in lines:
        if item[0] == "__bar__":
            _, name, pct = item
            p.append(f'<text x="{pad}" y="{y}" font-family="{MONO}" font-size="{fs}" fill="{MID}">  {esc(name):<11}</text>')
            bx = pad + (2 + 11) * chw
            bw, bh = 200, 11
            fw = max(3, bw * pct / 100)
            p.append(f'<rect x="{bx:.0f}" y="{y - 9}" width="{bw}" height="{bh}" rx="3" fill="#1e1e1e"/>')
            p.append(f'<rect x="{bx:.0f}" y="{y - 9}" width="{fw:.0f}" height="{bh}" rx="3" fill="#b5b5b5"/>')
            p.append(f'<text x="{bx + bw + 12:.0f}" y="{y}" font-family="{MONO}" font-size="{fs}" fill="{MID}">{pct:5.1f}%</text>')
            y += lh
            continue
        text, color = item
        if text.startswith("$"):
            # bright prompt, dim rest
            p.append(f'<text x="{pad}" y="{y}" font-family="{MONO}" font-size="{fs}" fill="{BRIGHT}">'
                     f'{esc(text[:1])}<tspan fill="{DIM}">{esc(text[1:])}</tspan></text>')
        else:
            p.append(f'<text x="{pad}" y="{y}" font-family="{MONO}" font-size="{fs}" fill="{color}">{esc(text)}</text>')
        y += lh
    # static cursor
    p.append(f'<text x="{pad}" y="{y}" font-family="{MONO}" font-size="{fs}" fill="{BRIGHT}">$</text>')
    p.append(f'<rect x="{pad + 14}" y="{y - 12}" width="9" height="16" fill="{BRIGHT}" opacity="0.85"/>')
    p.append("</svg>")

    path = os.path.join(OUT, "profile.svg")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(p) + "\n")
    os.replace(tmp, path)
    print("wrote", path)


def main() -> int:
    try:
        data = fetch_data()
    except Exception as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 1
    profile_card(data)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
