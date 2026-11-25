#!/usr/bin/env python3
"""Draw the README charts from results/leaderboard-comparison.csv (written by scripts/score.py).

    python3 scripts/chart.py

Writes three charts to results/charts/, each in a light and a dark version:
  cost-vs-score   pass rate against cost per attempt, with the cost-score frontier
  ranking         mean of 3 per harness with its 95% bootstrap interval
  consistency     share of tasks solved in all three attempts, in some, and in none
"""
import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "charts"
OURS = "codeaf senior-dev"
FONT = "Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

THEMES = {
    "light": dict(bg="#ffffff", ink="#1f2328", ink2="#59636e", muted="#8c959f", grid="#eaeef2",
                  axis="#d0d7de", dot="#afb8c1", accent="#1f6feb", accent_soft="#ddf4ff",
                  band="#f6f8fa", seq=("#1f6feb", "#80b3ff", "#eaeef2")),
    "dark": dict(bg="#0d1117", ink="#e6edf3", ink2="#9198a1", muted="#6e7681", grid="#1c2128",
                 axis="#30363d", dot="#545d68", accent="#4493f8", accent_soft="#102540",
                 band="#151b23", seq=("#4493f8", "#1f4f99", "#262c36")),
}

rows = list(csv.DictReader(open(ROOT / "results" / "leaderboard-comparison.csv")))
for r in rows:
    for k in ("mean_of_3_pct", "pass_at_3_pct", "all_3_pct", "cost_per_task_usd", "ci95_low_pct", "ci95_high_pct"):
        r[k] = float(r[k])


def svg(w, h, t, body, title, desc):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'font-family="{FONT}" role="img" aria-labelledby="t d">'
            f'<title id="t">{title}</title><desc id="d">{desc}</desc>'
            f'<rect width="{w}" height="{h}" rx="12" fill="{t["bg"]}"/>' + "".join(body) + "</svg>\n")


def text(x, y, s, size=12, fill="#000", anchor="start", weight=400, extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" {extra}>{s}</text>')


def header(t, title, sub, x=32):
    return [text(x, 38, title, 17, t["ink"], weight=600), text(x, 60, sub, 12.5, t["ink2"])]


def cost_vs_score(t):
    W, H, L, R, T, B = 880, 540, 72, 40, 96, 64
    x0, x1, y0, y1 = 0.020, 0.060, 60, 90
    X = lambda c: L + (c - x0) / (x1 - x0) * (W - L - R)
    Y = lambda p: T + (y1 - p) / (y1 - y0) * (H - T - B)
    o = header(t, "Pass rate against cost",
               "Terminal-Bench 2.1 · DeepSeek-V4.1-Flash, high effort · 87 tasks × 3 attempts · up and to the left is better")
    ours = next(r for r in rows if r["harness"] == OURS)
    ox, oy = X(ours["cost_per_task_usd"]), Y(ours["mean_of_3_pct"])
    # region codeaf dominates: every point there costs more and scores lower
    o.append(f'<rect x="{ox:.1f}" y="{oy:.1f}" width="{W-R-ox:.1f}" height="{H-B-oy:.1f}" fill="{t["accent_soft"]}" opacity="0.55"/>')
    o.append(text(W - R - 10, oy + 18, "costs more and scores lower than codeaf", 11, t["accent"], "end", 500))
    for p in range(y0, y1 + 1, 5):
        o.append(f'<line x1="{L}" x2="{W-R}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="{t["grid"]}"/>')
        o.append(text(L - 10, Y(p) + 4, f"{p}%", 11, t["muted"], "end"))
    c = x0
    while c <= x1 + 1e-9:
        o.append(f'<line x1="{X(c):.1f}" x2="{X(c):.1f}" y1="{H-B}" y2="{H-B+5}" stroke="{t["axis"]}"/>')
        o.append(text(X(c), H - B + 20, f"${c:.3f}", 11, t["muted"], "middle"))
        c += 0.005
    o.append(f'<line x1="{L}" x2="{W-R}" y1="{H-B}" y2="{H-B}" stroke="{t["axis"]}"/>')
    o.append(text((L + W - R) / 2, H - 16, "Cost per attempt (USD)", 12, t["ink2"], "middle"))
    o.append(text(20, (T + H - B) / 2, "Mean pass rate of 3 attempts", 12, t["ink2"], "middle",
                  extra=f'transform="rotate(-90 20 {(T + H - B) / 2})"'))
    # frontier of the other harnesses: cheapest first, keep each one that beats every cheaper one
    others = sorted((r for r in rows if r["harness"] != OURS), key=lambda r: (r["cost_per_task_usd"], -r["mean_of_3_pct"]))
    front, best = [], -1
    for r in others:
        if r["mean_of_3_pct"] > best:
            front.append(r); best = r["mean_of_3_pct"]
    d = ""
    for i, r in enumerate(front):
        x, y = X(r["cost_per_task_usd"]), Y(r["mean_of_3_pct"])
        d += (f"M{x:.1f} {y:.1f}" if i == 0 else f" H{x:.1f} V{y:.1f}")
    d += f" H{W-R}"
    o.append(f'<path d="{d}" fill="none" stroke="{t["muted"]}" stroke-width="1.5" stroke-dasharray="4 4"/>')
    fx, fy = X(front[-1]["cost_per_task_usd"]), Y(front[-1]["mean_of_3_pct"])
    o.append(text(W - R - 4, fy + 16, "best cost-score trade-off of the other harnesses", 10.5, t["muted"], "end"))
    off = {"kimi-code": (9, -8), "grok-build": (-9, 15, "end"), "codex": (-9, -9, "end"), "opencode": (9, -9),
           "claude-code": (-2, -11, "middle"), "fx": (9, 4), "deepseek-harness": (-9, 14, "end"), "pi": (-9, 15, "end"),
           "qwen-code": (-9, 14, "end"), "mini-swe-agent": (9, 13), "openclaw": (9, 4), "hermes": (-9, 4, "end")}
    for r in others:
        x, y = X(r["cost_per_task_usd"]), Y(r["mean_of_3_pct"])
        tip = f'{r["harness"]}: {r["mean_of_3_pct"]}% at ${r["cost_per_task_usd"]:.4f} per attempt'
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{t["dot"]}" stroke="{t["bg"]}" stroke-width="2"><title>{tip}</title></circle>')
        dx, dy, *a = off.get(r["harness"], (9, 4))
        o.append(text(x + dx, y + dy, r["harness"], 11, t["ink2"], a[0] if a else "start"))
    o.append(f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="8" fill="{t["accent"]}" stroke="{t["bg"]}" stroke-width="2.5">'
             f'<title>{OURS}: {ours["mean_of_3_pct"]}% at ${ours["cost_per_task_usd"]:.4f} per attempt</title></circle>')
    o.append(text(ox + 13, oy - 6, OURS, 13, t["ink"], weight=600))
    o.append(text(ox + 13, oy + 10, f'{ours["mean_of_3_pct"]}% · ${ours["cost_per_task_usd"]:.4f}', 11.5, t["accent"], weight=600))
    return svg(W, H, t, o, "Pass rate against cost per attempt",
               "Scatter of 13 harnesses; codeaf senior-dev scores highest at the lowest cost.")


def ranking(t):
    rs = sorted(rows, key=lambda r: (-r["mean_of_3_pct"], r["cost_per_task_usd"]))
    W, L, R, T, RH = 880, 168, 92, 104, 30
    H = T + RH * len(rs) + 52
    x0, x1 = 50, 95
    X = lambda p: L + (p - x0) / (x1 - x0) * (W - L - R)
    o = header(t, "Mean pass rate of 3 attempts",
               "With the 95% interval from resampling the 87 tasks. Overlapping intervals mean the order may change on a rerun.")
    o.append(f'<circle cx="34" cy="83" r="4.5" fill="{t["ink2"]}"/>')
    o.append(text(44, 87, "mean of 3", 11.5, t["ink2"]))
    o.append(f'<line x1="118" x2="150" y1="83" y2="83" stroke="{t["muted"]}" stroke-width="2" stroke-linecap="round"/>')
    o.append(text(158, 87, "95% interval", 11.5, t["ink2"]))
    top, bot = T - 6, T + RH * len(rs)
    for p in range(x0, x1 + 1, 5):
        o.append(f'<line x1="{X(p):.1f}" x2="{X(p):.1f}" y1="{top}" y2="{bot}" stroke="{t["grid"]}"/>')
        o.append(text(X(p), bot + 20, f"{p}%", 11, t["muted"], "middle"))
    ours = next(r for r in rs if r["harness"] == OURS)
    o.append(f'<line x1="{X(ours["mean_of_3_pct"]):.1f}" x2="{X(ours["mean_of_3_pct"]):.1f}" y1="{top}" y2="{bot}" '
             f'stroke="{t["accent"]}" stroke-width="1" stroke-dasharray="3 3" opacity="0.6"/>')
    for i, r in enumerate(rs):
        cy = T + RH * i + RH / 2
        me = r["harness"] == OURS
        col = t["accent"] if me else t["ink2"]
        if me:
            o.append(f'<rect x="16" y="{cy-RH/2+2:.1f}" width="{W-32}" height="{RH-4}" rx="6" fill="{t["accent_soft"]}" opacity="0.6"/>')
        o.append(text(L - 16, cy + 4, r["harness"], 12, t["ink"] if me else t["ink2"], "end", 600 if me else 400))
        o.append(f'<line x1="{X(r["ci95_low_pct"]):.1f}" x2="{X(r["ci95_high_pct"]):.1f}" y1="{cy:.1f}" y2="{cy:.1f}" '
                 f'stroke="{t["accent"] if me else t["muted"]}" stroke-width="2" stroke-linecap="round" opacity="{1 if me else 0.7}"/>')
        tip = f'{r["harness"]}: {r["mean_of_3_pct"]}% (95% interval {r["ci95_low_pct"]}–{r["ci95_high_pct"]}%)'
        o.append(f'<circle cx="{X(r["mean_of_3_pct"]):.1f}" cy="{cy:.1f}" r="{6 if me else 5}" fill="{col}" '
                 f'stroke="{t["bg"]}" stroke-width="2"><title>{tip}</title></circle>')
        o.append(text(W - R + 18, cy + 4, f'{r["mean_of_3_pct"]:.1f}%', 12, t["ink"] if me else t["ink2"], "start", 600 if me else 400))
    return svg(W, H, t, o, "Mean pass rate of 3 attempts per harness",
               "Ranked dot chart with 95% bootstrap intervals; codeaf senior-dev is first at 82.0%.")


def consistency(t):
    rs = sorted(rows, key=lambda r: (-r["all_3_pct"], -r["pass_at_3_pct"]))
    W, L, R, T, RH = 880, 168, 40, 112, 30
    H = T + RH * len(rs) + 48
    X = lambda p: L + p / 100 * (W - L - R)
    o = header(t, "How reliably each harness solves a task",
               "Share of the 87 tasks solved in all 3 attempts, in 1 or 2, and in none. Sorted by all 3.")
    keys = [("solved all 3 times", t["seq"][0]), ("solved 1 or 2 times", t["seq"][1]), ("never solved", t["seq"][2])]
    lx = 32
    for name, col in keys:
        o.append(f'<rect x="{lx}" y="76" width="12" height="12" rx="3" fill="{col}"/>')
        o.append(text(lx + 18, 86, name, 11.5, t["ink2"]))
        lx += 34 + len(name) * 6.4
    for p in range(0, 101, 25):
        o.append(text(X(p), T + RH * len(rs) + 20, f"{p}%", 11, t["muted"], "middle"))
    for i, r in enumerate(rs):
        cy = T + RH * i + RH / 2
        me = r["harness"] == OURS
        if me:
            o.append(f'<rect x="16" y="{cy-RH/2+1:.1f}" width="{W-32}" height="{RH-2}" rx="6" fill="{t["accent_soft"]}" opacity="0.6"/>')
        o.append(text(L - 16, cy + 4, r["harness"], 12, t["ink"] if me else t["ink2"], "end", 600 if me else 400))
        segs = [r["all_3_pct"], r["pass_at_3_pct"] - r["all_3_pct"], 100 - r["pass_at_3_pct"]]
        x = L
        for j, (v, (name, col)) in enumerate(zip(segs, keys)):
            w = X(v) - L
            gap = 2 if j < 2 else 0
            o.append(f'<rect x="{x:.1f}" y="{cy-9:.1f}" width="{max(w-gap,0):.1f}" height="18" rx="4" fill="{col}">'
                     f'<title>{r["harness"]}: {name} {v:.1f}% of tasks</title></rect>')
            if j == 0:
                o.append(text(x + 8, cy + 4, f"{v:.1f}%", 11, "#ffffff", weight=600))
            x += w
    return svg(W, H, t, o, "Consistency across three attempts",
               "Stacked bars per harness; codeaf senior-dev solves the most tasks in all three attempts.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("cost-vs-score", cost_vs_score), ("ranking", ranking), ("consistency", consistency)):
        for mode, t in THEMES.items():
            (OUT / f"{name}-{mode}.svg").write_text(fn(t))
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
