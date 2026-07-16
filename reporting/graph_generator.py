# ============================================================
# ProctorAI — reporting/graph_generator.py
#
# CHANGES:
#   1. All new event types added to EVENT_COLORS (no more grey
#      fallback for Gaze Away, Keyboard, etc.)
#   2. risk_timeline_chart() — line chart of score over time.
#   3. events_bar_chart() includes all event types.
# ============================================================

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from utils.helpers import get_logger, ensure_dir
from config.settings import REPORTS_DIR
from core.events.event_types import EVENT_COLORS

logger = get_logger("GraphGenerator")


class GraphGenerator:
    """Creates bar charts, gauge charts, and risk timeline PNGs."""

    def __init__(self):
        ensure_dir(REPORTS_DIR)
        plt.rcParams.update({
            "figure.facecolor": "#1e293b",
            "axes.facecolor":   "#1e293b",
            "axes.labelcolor":  "#e2e8f0",
            "xtick.color":      "#e2e8f0",
            "ytick.color":      "#e2e8f0",
            "text.color":       "#e2e8f0",
            "grid.color":       "#334155",
        })
        logger.info("GraphGenerator ready.")

    def events_bar_chart(self, counts: dict, session_id: str) -> str:
        data = {k: v for k, v in counts.items() if v > 0}
        if not data:
            data = {"No Events": 0}
        labels = list(data.keys())
        values = list(data.values())
        colors = [EVENT_COLORS.get(l, "#64748b") for l in labels]

        fig, ax = plt.subplots(figsize=(7, max(3, len(labels) * 0.7)))
        bars = ax.barh(labels, values, color=colors, height=0.55, edgecolor="none")
        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                    str(val), va="center", ha="left", fontsize=10,
                    fontweight="bold", color="#e2e8f0")

        ax.set_xlabel("Number of Events", labelpad=8)
        ax.set_title("Suspicious Events Summary", pad=12, fontsize=13, fontweight="bold")
        ax.set_xlim(0, max(values or [1]) + 2)
        ax.grid(axis="x", linewidth=0.5, alpha=0.4)
        ax.spines[:].set_visible(False)
        plt.tight_layout()
        path = os.path.join(REPORTS_DIR, f"{session_id}_events.png")
        plt.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Events bar chart → {path}")
        return path

    def risk_gauge_chart(self, score: int, label: str, session_id: str) -> str:
        import numpy as np
        fig, ax = plt.subplots(figsize=(4, 2.5), subplot_kw={"projection": "polar"})
        fig.patch.set_facecolor("#1e293b")
        ax.set_facecolor("#1e293b")
        theta = np.linspace(0, np.pi, 200)
        ax.plot(theta, [1]*200, color="#334155", linewidth=14, solid_capstyle="butt")
        for t_s, t_e, col in [(0, np.pi*0.35,"#22c55e"),(np.pi*0.35,np.pi*0.6,"#f59e0b"),
                               (np.pi*0.6,np.pi*0.8,"#ef4444"),(np.pi*0.8,np.pi,"#dc2626")]:
            ts = np.linspace(t_s, t_e, 100)
            ax.plot(ts, [1]*100, color=col, linewidth=14, solid_capstyle="butt", alpha=0.35)
        pct  = min(score/100, 1.0)
        fill = np.linspace(0, np.pi*pct, 200)
        col  = ("#dc2626" if label in ("Suspicious","Critical") else
                "#f59e0b" if label=="Moderate" else "#22c55e")
        ax.plot(fill, [1]*200, color=col, linewidth=14, solid_capstyle="butt")
        ax.set_ylim(0,1.4); ax.set_theta_zero_location("W"); ax.set_theta_direction(-1)
        ax.axis("off")
        ax.text(np.pi/2, 0.05, str(score), ha="center", va="center",
                fontsize=26, fontweight="bold", color=col, transform=ax.transData)
        ax.text(np.pi/2, -0.35, label, ha="center", va="center",
                fontsize=11, color="#94a3b8", transform=ax.transData)
        plt.tight_layout()
        path = os.path.join(REPORTS_DIR, f"{session_id}_gauge.png")
        plt.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return path

    def risk_timeline_chart(self, timeline: list, session_id: str):
        if not timeline or len(timeline) < 2:
            return None
        import numpy as np
        xs = [t["elapsed_sec"]/60 for t in timeline]
        ys = [t["score"] for t in timeline]
        fig, ax = plt.subplots(figsize=(7, 2.8))
        ax.plot(xs, ys, color="#00d4ff", linewidth=2)
        ax.fill_between(xs, ys, alpha=0.15, color="#00d4ff")
        ax.axhline(20, color="#22c55e", linewidth=0.8, linestyle="--", alpha=0.5, label="Low")
        ax.axhline(50, color="#f59e0b", linewidth=0.8, linestyle="--", alpha=0.5, label="Moderate")
        ax.axhline(80, color="#ef4444", linewidth=0.8, linestyle="--", alpha=0.5, label="High")
        ax.set_xlabel("Time (minutes)", labelpad=6)
        ax.set_ylabel("Risk Score", labelpad=6)
        ax.set_title("Risk Score Over Time", pad=10, fontsize=12, fontweight="bold")
        ax.set_ylim(0, max(max(ys)*1.1, 100))
        ax.grid(alpha=0.3, linewidth=0.5)
        ax.spines[:].set_visible(False)
        ax.legend(fontsize=8, loc="upper left")
        plt.tight_layout()
        path = os.path.join(REPORTS_DIR, f"{session_id}_timeline.png")
        plt.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return path
