from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
THESIS_02 = ROOT / "docs" / "thesis_02"
MEDIA = next(THESIS_02.glob("*_media/media"))
TABLE = ROOT / "output" / "tables" / "indices_anchors.csv"


def setup_font() -> None:
    candidates = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 160


def save(fig, name: str) -> Path:
    out = MEDIA / name
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def main() -> None:
    setup_font()
    df = pd.read_csv(TABLE, encoding="utf-8-sig")

    palette = {
        "blue": "#2F6F9F",
        "teal": "#2A9D8F",
        "gold": "#E9C46A",
        "orange": "#F4A261",
        "red": "#D95F59",
        "gray": "#6C757D",
    }

    cmi_top = df.sort_values("cmi", ascending=False).head(15).iloc[::-1]
    y = np.arange(len(cmi_top))
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.barh(y, cmi_top["cmi_freq_component"] * 0.6, color=palette["blue"], label="频次厚度贡献（0.6F）")
    ax.barh(
        y,
        cmi_top["cmi_degree_component"] * 0.4,
        left=cmi_top["cmi_freq_component"] * 0.6,
        color=palette["teal"],
        label="直接连接度贡献（0.4D）",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(cmi_top["name"], fontsize=8)
    ax.set_xlim(0, 105)
    ax.set_xlabel("CMI 综合得分")
    ax.set_title("文化记忆指数（CMI）Top 15：频次厚度与直接连接度")
    ax.grid(axis="x", color="#D9DEE2", linewidth=0.6)
    ax.legend(loc="lower left", bbox_to_anchor=(1.01, 0.02), frameon=False, fontsize=8)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    save(fig, "fig_5_2_cmi_composition.png")

    order = [0, 25, 50, 75, 100]
    oai_counts = df["oai"].value_counts().reindex(order, fill_value=0)
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    bars = ax.bar(
        [str(x) for x in order],
        oai_counts.values,
        color=[palette["gray"], palette["gold"], palette["orange"], palette["teal"], palette["blue"]],
    )
    ax.set_xlabel("OAI 分值")
    ax.set_ylabel("载体数量")
    ax.set_title("官方认证指数（OAI）分值分布")
    ax.grid(axis="y", color="#D9DEE2", linewidth=0.6)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, str(int(b.get_height())), ha="center", va="bottom", fontsize=9)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    save(fig, "fig_5_3_oai_distribution.png")

    thi_top = df.sort_values("thi", ascending=False).head(15).iloc[::-1]
    y = np.arange(len(thi_top))
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    colors = [
        palette["orange"]
        if c == "空心景点区"
        else palette["blue"]
        if c == "核心耦合区"
        else palette["teal"]
        if c == "沉睡潜力区"
        else palette["gray"]
        for c in thi_top["mi_category"]
    ]
    ax.barh(y, thi_top["thi"], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(thi_top["name"], fontsize=8)
    ax.set_xlim(0, max(100, thi_top["thi"].max() + 5))
    ax.set_xlabel("THI 综合得分")
    ax.set_title("旅游热度指数（THI）Top 15")
    ax.grid(axis="x", color="#D9DEE2", linewidth=0.6)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    save(fig, "fig_5_4_thi_top15.png")

    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    bins = np.linspace(np.floor(df["mi"].min() / 10) * 10, np.ceil(df["mi"].max() / 10) * 10, 18)
    ax.hist(df["mi"], bins=bins, color=palette["blue"], alpha=0.82, edgecolor="white")
    ax.axvline(-10, color=palette["teal"], linestyle="--", linewidth=1.5, label="沉睡潜力阈值 -10")
    ax.axvline(10, color=palette["orange"], linestyle="--", linewidth=1.5, label="空心景点阈值 10")
    ax.axvline(0, color="#333333", linestyle="-", linewidth=1.0)
    ax.set_xlabel("MI = THI - 0.5CMI - 0.5OAI")
    ax.set_ylabel("载体数量")
    ax.set_title("文化—旅游错位指数（MI）分布")
    ax.grid(axis="y", color="#D9DEE2", linewidth=0.6)
    ax.legend(frameon=False, fontsize=8)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    save(fig, "fig_5_5_mi_distribution.png")

    corr = df[["cmi", "oai", "thi", "mi", "poi_count_500m", "avg_rating_500m", "review_total_500m"]].corr(method="pearson")
    corr.index = ["CMI", "OAI", "THI", "MI", "POI(500m)", "评分(500m)", "评论(500m)"]
    corr.columns = corr.index
    fig, ax = plt.subplots(figsize=(6.6, 5.6))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index, fontsize=8)
    for i in range(corr.shape[0]):
        for j in range(corr.shape[1]):
            v = corr.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color="white" if abs(v) > 0.55 else "#222222")
    ax.set_title("载体级指标相关矩阵（Pearson, n = 165）")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_visible(False)
    save(fig, "fig_6_4_anchor_correlation_updated.png")

    summary = {
        "n": int(len(df)),
        "cmi_quantiles": {str(k): round(float(v), 2) for k, v in df["cmi"].quantile([0, 0.25, 0.5, 0.75, 1]).items()},
        "oai_counts": {str(int(k)): int(v) for k, v in oai_counts.items()},
        "thi_quantiles": {str(k): round(float(v), 2) for k, v in df["thi"].quantile([0, 0.25, 0.5, 0.75, 1]).items()},
        "mi_quantiles": {str(k): round(float(v), 2) for k, v in df["mi"].quantile([0, 0.25, 0.5, 0.75, 1]).items()},
        "category_counts": {str(k): int(v) for k, v in df["mi_category"].value_counts().items()},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
