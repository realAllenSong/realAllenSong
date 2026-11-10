#!/usr/bin/env python3
"""Render the profile status board (assets/board-{dark,light}.svg) from live GitHub data.

Runs daily in GitHub Actions. Standard library only.
"""
import datetime
import html
import json
import os
import urllib.request

LOGIN = "realAllenSong"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

# The parts that don't come from the API. Edit here.
TAGLINE = "LLM post-training researcher · AI engineer · M.S. @ Penn · AI Engineer Intern @ Millennium"
STATUS = "building · New York"
PROJECTS = [
    ("ThunderTalk", "ThunderTalk", "on-device voice toolkit for macOS"),
    ("Wemute", "wemute", "local-first file converter · files → text for LLMs"),
]
PAPERS = [
    ("Learning When to Think While Listening", "first author · under review at ICLR 2027"),
    ("SL4HOI", "first author · KDD-UC 2024"),
]
FOCUS = "post-training · agent harnesses · continual learning"

THEMES = {
    "dark": dict(bg="#0b0d10", panel="#12151a", line="#232830", fg="#e6e8eb", dim="#7d8590", acc="#f5a524", ok="#3fb950",
                 heat=["#1a1e24", "#5a3d0a", "#8f5f0d", "#c98510", "#f5a524"],
                 bars=["#f5a524", "#e6e8eb", "#7d8590", "#4b5563", "#2f3640"]),
    "light": dict(bg="#f6f3ec", panel="#fdfcf9", line="#e2dccf", fg="#1d1b17", dim="#6f695e", acc="#b06a00", ok="#1a7f37",
                  heat=["#ece7db", "#f0d49a", "#e5b354", "#cf8d12", "#9a5b00"],
                  bars=["#b06a00", "#1d1b17", "#8d867a", "#b9b2a5", "#d8d2c5"]),
}


def api(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{LOGIN}-profile")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch():
    query = """
    { user(login: "%s") {
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
          nodes { languages(first: 6, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } } }
        contributionsCollection { contributionCalendar {
          totalContributions weeks { contributionDays { date contributionCount } } } } } }""" % LOGIN
    user = api("https://api.github.com/graphql", {"query": query})["data"]["user"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    langs = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    total = sum(langs.values()) or 1
    releases, count, latest = {}, 0, ""
    for _, repo, _ in PROJECTS:
        page, tags = 1, []
        while True:
            batch = api(f"https://api.github.com/repos/{LOGIN}/{repo}/releases?per_page=100&page={page}")
            tags += batch
            if len(batch) < 100:
                break
            page += 1
        count += len(tags)
        if tags:
            releases[repo] = tags[0]["tag_name"]
            latest = max(latest, (tags[0]["published_at"] or "")[:10])
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    return dict(
        weeks=cal["weeks"],
        total=cal["totalContributions"],
        active=sum(1 for d in days if d["contributionCount"]),
        langs=sorted(((v / total, k) for k, v in langs.items()), reverse=True)[:5],
        releases=releases, release_count=count, latest=latest,
    )


def level(n):
    return 0 if n == 0 else 1 if n < 4 else 2 if n < 10 else 3 if n < 25 else 4


def render(d, t):
    W, H = 840, 468
    e = html.escape

    def text(x, y, s, fill, size=13, weight=400, anchor="start", extra=""):
        return (f'<text x="{x}" y="{y}" fill="{fill}" font-family="{MONO}" font-size="{size}" '
                f'font-weight="{weight}" text-anchor="{anchor}" xml:space="preserve" {extra}>{s}</text>')

    def span(s, fill, size=None, weight=400, dx=10):
        sz = f' font-size="{size}"' if size else ""
        return f'<tspan dx="{dx}" fill="{fill}" font-weight="{weight}"{sz}>{e(s)}</tspan>'

    def tile(x, y, w, h, label):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{t["panel"]}" stroke="{t["line"]}"/>'
                + text(x + 16, y + 24, e(label), t["dim"], 10.5, 600, extra='letter-spacing="1.5"'))

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Zhiyuan Song: status board">',
        f'<rect width="{W}" height="{H}" rx="12" fill="{t["bg"]}"/>',
        text(24, 40, "ZHIYUAN SONG" + span("/ allen", t["dim"], 14, dx=14), t["fg"], 20, 700, extra='letter-spacing="2"'),
        text(W - 24, 40, e(STATUS), t["dim"], 12, anchor="end"),
        f'<circle cx="{W - 176}" cy="36" r="4" fill="{t["ok"]}"><animate attributeName="opacity" values="1;.3;1" dur="2s" repeatCount="indefinite"/></circle>',
        text(24, 62, e(TAGLINE), t["dim"], 12),
        tile(24, 80, 388, 128, "SHIPPING"),
    ]
    y = 132
    for name, repo, blurb in PROJECTS:
        out.append(text(40, y, e(name) + span(d["releases"].get(repo, ""), t["acc"], weight=600), t["fg"], 15, 600))
        out.append(text(40, y + 20 if y == 132 else y + 18, e(blurb), t["dim"], 12))
        y += 46
    out.append(tile(428, 80, 388, 128, "RESEARCH"))
    out.append(text(444, 132, e(PAPERS[0][0]), t["fg"], 13.5, 600))
    out.append(text(444, 152, e(PAPERS[0][1]), t["dim"], 12))
    out.append(text(444, 178, e(PAPERS[1][0]) + span(PAPERS[1][1], t["dim"], 12), t["fg"], 13.5, 600))
    out.append(text(444, 196, e(FOCUS), t["acc"], 11.5))

    out.append(tile(24, 224, 792, 140, "ACTIVITY · LAST 12 MONTHS"))
    cell, gap = 10, 2.4
    for i, week in enumerate(d["weeks"][-53:]):
        for day in week["contributionDays"]:
            wd = (datetime.date.fromisoformat(day["date"]).weekday() + 1) % 7
            out.append(f'<rect x="{40 + i * (cell + gap):.1f}" y="{262 + wd * (cell + gap):.1f}" width="{cell}" '
                       f'height="{cell}" rx="2" fill="{t["heat"][level(day["contributionCount"])]}"/>')
    out.append(text(716, 286, f'{d["total"]:,}', t["fg"], 26, 700))
    out.append(text(716, 304, "contributions", t["dim"], 11.5))
    out.append(text(716, 336, str(d["active"]), t["fg"], 20, 700))
    out.append(text(716, 352, "active days", t["dim"], 11.5))

    out.append(tile(24, 380, 388, 68, "STACK"))
    x = 40.0
    for (share, _), colour in zip(d["langs"], t["bars"]):
        w = share * 356
        out.append(f'<rect x="{x:.1f}" y="414" width="{max(w - 2, 2):.1f}" height="8" rx="2" fill="{colour}"/>')
        x += w
    out.append(text(40, 440, e(" · ".join(f"{k} {s * 100:.0f}%" for s, k in d["langs"][:4])), t["dim"], 11))

    out.append(tile(428, 380, 388, 68, "RELEASES"))
    out.append(text(444, 430, str(d["release_count"]) + span(f'shipped · latest {d["latest"]}', t["dim"], 12, dx=12),
                    t["fg"], 26, 700))
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    data = fetch()
    os.makedirs("assets", exist_ok=True)
    for name, theme in THEMES.items():
        with open(f"assets/board-{name}.svg", "w") as f:
            f.write(render(data, theme) + "\n")
    print(f'{data["total"]} contributions, {data["active"]} active days, {data["release_count"]} releases')
