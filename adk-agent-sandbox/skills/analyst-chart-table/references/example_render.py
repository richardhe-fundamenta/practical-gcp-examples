# STYLE REFERENCE ONLY — not executed. The agent generates its own render code
# per SKILL.md; this shows the intended look/shape (palette, headline-as-title,
# table beneath, data.json schema).

#!/usr/bin/env python3
"""
render.py — bundled skill script. Runs INSIDE the sandbox.

Secure-by-default: emits a single PNG (annotated chart + compact table). No
JavaScript, no network, nothing for injected markup to execute. Data is read as
JSON (values are data, never concatenated into markup).

The HTML variant is intentionally minimal and assumes the HARNESS wraps it in a
sandboxed iframe + no-egress CSP. This script does not and cannot guarantee
containment — that is the harness's job.

data.json shape:
{
  "question": "Net revenue retention by region over the last 12 months",
  "x": ["2025-05", ...],                  # categories or time labels
  "series": {"NA": [..], "EMEA": [..]},   # one or more series
  "table": {"columns": [...], "rows": [[...], ...]},
  "prior": {"NA": 100.0, ...}             # optional prior-period for deltas
}
"""
import argparse, json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

INK = "#1c1814"; MUTED = "#8a837a"; ACCENT = "#b07a3c"
PALETTE = ["#b07a3c", "#5f817b", "#a85a4c", "#776a91", "#7d8a4e"]

def headline(data):
    """Most decision-relevant fact -> title. Simple heuristic; the model can
    override by passing data['headline']."""
    if data.get("headline"):
        return data["headline"]
    series = data["series"]
    # biggest last-value mover vs prior, else biggest last value
    prior = data.get("prior", {})
    best, best_d = None, -1e18
    for name, vals in series.items():
        if name in prior and prior[name]:
            d = (vals[-1] - prior[name]) / prior[name] * 100
            if abs(d) > abs(best_d): best, best_d = name, d
    if best is not None:
        dir_ = "up" if best_d >= 0 else "down"
        return f"{best} moved {dir_} {abs(best_d):.0f}% vs prior period"
    top = max(series, key=lambda k: series[k][-1])
    return f"{top} leads at {series[top][-1]:,.0f}"

def render(data, kind, out, fmt):
    x = data["x"]; series = data["series"]
    if kind == "auto":
        kind = "line" if len(x) > 4 and all(isinstance(v, str) for v in x) else "bars"

    fig = plt.figure(figsize=(9, 7.2), dpi=160)
    fig.patch.set_facecolor("#faf7f2")
    gs = fig.add_gridspec(2, 1, height_ratios=[2.4, 1], hspace=0.28)
    ax = fig.add_subplot(gs[0]); ax.set_facecolor("#faf7f2")

    if kind == "line":
        for i, (name, vals) in enumerate(series.items()):
            ax.plot(x, vals, color=PALETTE[i % len(PALETTE)], lw=2.4, label=name)
            ax.scatter([x[-1]], [vals[-1]], color=PALETTE[i % len(PALETTE)], s=28, zorder=5)
    else:
        import numpy as np
        n = len(series); w = 0.8 / max(n, 1)
        idx = np.arange(len(x))
        for i, (name, vals) in enumerate(series.items()):
            ax.bar(idx + i * w, vals, w, color=PALETTE[i % len(PALETTE)], label=name)
        ax.set_xticks(idx + 0.4 - w / 2); ax.set_xticklabels(x)

    # headline as title
    ax.set_title(headline(data), fontsize=15, fontweight="bold",
                 color=INK, loc="left", pad=14)
    ax.text(0, 1.005, data.get("question", ""), transform=ax.transAxes,
            fontsize=9, color=MUTED, va="bottom")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color("#d9d2c7")
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color="#e7e0d5", lw=0.8)
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=8, loc="upper left",
                  bbox_to_anchor=(0, -0.08), ncol=len(series))

    # compact exact-numbers table beneath
    axt = fig.add_subplot(gs[1]); axt.axis("off")
    t = data["table"]
    tbl = axt.table(cellText=[[f"{c}" for c in row] for row in t["rows"]],
                    colLabels=t["columns"], cellLoc="center", loc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1, 1.4)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#e7e0d5")
        if r == 0:
            cell.set_facecolor("#1c1814"); cell.set_text_props(color="#faf7f2", fontweight="bold")
        else:
            cell.set_facecolor("#ffffff" if r % 2 else "#f4efe7")

    so_what = data.get("so_what", "")
    if so_what:
        fig.text(0.07, 0.025, "→ " + so_what, fontsize=9, color=ACCENT, style="italic")

    if fmt == "png":
        fig.savefig(out, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"wrote {out} (png, secure default)")
    else:
        # minimal HTML embedding the PNG as base64 — NO live JS.
        # Harness still wraps this in sandboxed iframe + CSP before display.
        import base64, io
        buf = io.BytesIO(); fig.savefig(buf, format="png",
                                        bbox_inches="tight", facecolor=fig.get_facecolor())
        b64 = base64.b64encode(buf.getvalue()).decode()
        html = ('<!doctype html><meta charset=utf-8>'
                '<div style="font-family:Georgia,serif">'
                f'<img alt="chart" style="max-width:100%" '
                f'src="data:image/png;base64,{b64}"></div>')
        open(out, "w").write(html)
        print(f"wrote {out} (html, image-embedded; harness applies CSP+iframe)")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--kind", default="auto", choices=["line", "bars", "auto"])
    p.add_argument("--out", default="output.png")
    p.add_argument("--format", default="png", choices=["png", "html"])
    a = p.parse_args()
    render(json.load(open(a.data)), a.kind, a.out, a.format)
