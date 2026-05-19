#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate final thesis completion tables and figures.

This script uses existing project data only. It produces:
- weight sensitivity tables and figure
- comment cultural-recognition sample table and figure
- priority ladder table
- clearer knowledge-graph figures for Chapter 4
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "output" / "tables"
PICTURES = ROOT / "pictures"
THESIS_02 = ROOT / "docs" / "thesis_02"
MEDIA = THESIS_02 / "基于大数据的佛山市南海区旅游景区文旅融合潜力研究_md转化版_media" / "media"


INK = "#26313f"
MUTED = "#667085"
PAPER = "#ffffff"
PANEL = "#fbfcfe"
LINE = "#d7dee8"

CATEGORY_ORDER = ["核心耦合区", "一般耦合区", "沉睡潜力区", "空心景点区"]
CATEGORY_COLORS = {
    "核心耦合区": "#7a4cc2",
    "一般耦合区": "#9aa7b7",
    "沉睡潜力区": "#d95f59",
    "空心景点区": "#4f8fd9",
}


def ensure_dirs() -> None:
    MEDIA.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)


def setup_mpl() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = PAPER
    plt.rcParams["savefig.facecolor"] = PAPER
    plt.rcParams["axes.facecolor"] = PAPER


def cfont(size: int, bold: bool = False):
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf") if bold else Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for fp in candidates:
        if fp.exists():
            return ImageFont.truetype(str(fp), size)
    return ImageFont.load_default()


def draw_round(draw: ImageDraw.ImageDraw, box, fill=PANEL, outline=LINE, radius=18, width=2) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def title(draw: ImageDraw.ImageDraw, main: str, sub: str | None = None) -> None:
    draw.text((78, 52), main, fill=INK, font=cfont(42, True))
    if sub:
        draw.text((80, 112), sub, fill=MUTED, font=cfont(24))


def paste_panel(canvas: Image.Image, path: Path, box, label: str) -> None:
    draw = ImageDraw.Draw(canvas)
    x0, y0, x1, y1 = box
    draw_round(draw, box)
    im = Image.open(path).convert("RGB")
    max_w = x1 - x0 - 60
    max_h = y1 - y0 - 98
    im.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    canvas.paste(im, (x0 + (x1 - x0 - im.width) // 2, y0 + 28))
    draw.text((x0 + 34, y1 - 56), label, fill=INK, font=cfont(28, True))


def render_knowledge_figures() -> None:
    overview = Image.new("RGB", (2600, 1450), PAPER)
    draw = ImageDraw.Draw(overview)
    title(draw, "知识图谱全局网络与人物关联总图", "全局网络用于观察整体结构；人物关联总图用于观察人物谱系关系")
    paste_panel(overview, PICTURES / "知识图谱总图.png", (80, 170, 1260, 1260), "知识图谱总图")
    paste_panel(overview, PICTURES / "人物关联总图.png", (1340, 170, 2520, 1260), "人物关联总图")
    draw.text((80, 1345), "数据来源：Neo4j 图谱导出与本研究整理。", fill="#7b8794", font=cfont(22))
    overview.save(MEDIA / "fig_4_2_kg_overview_final.png", quality=95)

    detail = Image.new("RGB", (2600, 2500), PAPER)
    draw = ImageDraw.Draw(detail)
    title(draw, "典型人物子图细部", "放大展示康有为与黄飞鸿两个典型人物网络，便于识读节点与关系")
    paste_panel(detail, PICTURES / "康有为周边人物.png", (95, 180, 2505, 1235), "康有为子图")
    paste_panel(detail, PICTURES / "黄飞鸿周边人物.png", (95, 1330, 2505, 2385), "黄飞鸿子图")
    draw.text((95, 2432), "数据来源：Neo4j 图谱导出与本研究整理。", fill="#7b8794", font=cfont(22))
    detail.save(MEDIA / "fig_4_3_kg_person_detail_final.png", quality=95)


def minmax(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    lo, hi = np.nanmin(arr), np.nanmax(arr)
    if abs(hi - lo) < 1e-12:
        return np.full_like(arr, 50.0, dtype=float)
    return (arr - lo) / (hi - lo) * 100.0


def label_of(cmi: float, thi: float, mi: float) -> str:
    if abs(mi) <= 10 and cmi >= 50 and thi >= 50:
        return "核心耦合区"
    if abs(mi) <= 10:
        return "一般耦合区"
    if mi < -10 and cmi > thi:
        return "沉睡潜力区"
    if mi > 10 and thi > cmi:
        return "空心景点区"
    return "一般耦合区"


def compute_thi(df: pd.DataFrame, weights: tuple[float, float, float]) -> np.ndarray:
    poi_norm = minmax(np.log1p(df["poi_count_500m"].astype(float).to_numpy()))
    rating_norm = minmax(df["avg_rating_500m"].astype(float).to_numpy())
    review_norm = minmax(np.log1p(df["review_total_500m"].astype(float).to_numpy()))
    wp, wr, wv = weights
    return wp * poi_norm + wr * rating_norm + wv * review_norm


def run_sensitivity(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenarios = [
        ("基准口径", 0.5, 0.5, (0.4, 0.2, 0.4), "CMI/OAI=0.5/0.5；THI=POI0.4+评分0.2+评论0.4"),
        ("文化侧加权", 0.7, 0.3, (0.4, 0.2, 0.4), "CMI/OAI=0.7/0.3"),
        ("官方侧加权", 0.3, 0.7, (0.4, 0.2, 0.4), "CMI/OAI=0.3/0.7"),
        ("POI导向THI", 0.5, 0.5, (0.5, 0.2, 0.3), "THI=POI0.5+评分0.2+评论0.3"),
        ("评论导向THI", 0.5, 0.5, (0.3, 0.2, 0.5), "THI=POI0.3+评分0.2+评论0.5"),
    ]
    base_cat = df["mi_category"].astype(str).to_numpy()
    rows = []
    change_rows = []
    scenario_categories: dict[str, np.ndarray] = {}
    for name, alpha, beta, thi_w, note in scenarios:
        thi = df["thi"].astype(float).to_numpy() if name in {"基准口径", "文化侧加权", "官方侧加权"} else compute_thi(df, thi_w)
        cmi = df["cmi"].astype(float).to_numpy()
        oai = df["oai"].astype(float).to_numpy()
        mi = thi - alpha * cmi - beta * oai
        cats = np.array([label_of(cmi[i], thi[i], mi[i]) for i in range(len(df))])
        scenario_categories[name] = cats
        counts = Counter(cats)
        stable = int(np.sum(cats == base_cat))
        rows.append({
            "scenario": name,
            "setting": note,
            "core": counts.get("核心耦合区", 0),
            "general": counts.get("一般耦合区", 0),
            "dormant": counts.get("沉睡潜力区", 0),
            "hollow": counts.get("空心景点区", 0),
            "same_as_baseline": stable,
            "same_ratio": round(stable / len(df) * 100, 1),
            "mi_median": round(float(np.median(mi)), 2),
        })
        if name != "基准口径":
            changed = np.where(cats != base_cat)[0]
            for idx in changed[:20]:
                change_rows.append({
                    "scenario": name,
                    "name": df.iloc[idx]["name"],
                    "town": df.iloc[idx]["town"],
                    "baseline_category": base_cat[idx],
                    "scenario_category": cats[idx],
                    "cmi": round(float(cmi[idx]), 2),
                    "oai": round(float(oai[idx]), 2),
                    "thi": round(float(thi[idx]), 2),
                    "mi": round(float(mi[idx]), 2),
                })

    summary = pd.DataFrame(rows)
    changes = pd.DataFrame(change_rows)
    summary.to_csv(TABLES / "final_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    changes.to_csv(TABLES / "final_sensitivity_changed_examples.csv", index=False, encoding="utf-8-sig")

    # Figure
    fig, ax = plt.subplots(figsize=(10.8, 5.6), dpi=220)
    x = np.arange(len(summary))
    width = 0.18
    for j, cat in enumerate(CATEGORY_ORDER):
        vals = {
            "核心耦合区": summary["core"],
            "一般耦合区": summary["general"],
            "沉睡潜力区": summary["dormant"],
            "空心景点区": summary["hollow"],
        }[cat]
        ax.bar(x + (j - 1.5) * width, vals, width, label=cat, color=CATEGORY_COLORS[cat])
    ax.set_xticks(x)
    ax.set_xticklabels(summary["scenario"], fontsize=9)
    ax.set_ylabel("载体数量")
    ax.set_title("权重敏感性检验：不同口径下错位分层数量对比")
    ax.grid(axis="y", color=LINE, linewidth=0.7, alpha=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False)
    for i, ratio in enumerate(summary["same_ratio"]):
        ax.text(i, 63.5, f"稳定 {ratio:.1f}%", ha="center", va="bottom", fontsize=8, color=MUTED)
    fig.tight_layout()
    fig.savefig(MEDIA / "fig_6_9_sensitivity_final.png", bbox_inches="tight")
    plt.close(fig)
    return summary, changes


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


KEYWORDS = [
    "历史", "文化", "非遗", "岭南", "古村", "古建筑", "祠", "祠堂", "宗祠", "书院",
    "康有为", "黄飞鸿", "叶问", "武术", "醒狮", "狮舞", "龙舟", "龙狮", "西樵山",
    "云泉仙馆", "百步云梯", "吴家大院", "平洲玉器", "玉器", "九江双蒸", "双蒸",
    "烟桥", "松塘", "仙岗", "葛洪", "传说", "民俗", "水乡", "博物馆", "展览",
    "讲解", "传统", "记忆", "文物", "庙", "道教", "理学", "书画", "南海",
    "煎堆", "鱼花", "龙舟宴", "醒狮", "粤剧", "金箔", "竹编", "香云纱",
]


def text_keywords(text: str) -> list[str]:
    if not isinstance(text, str):
        return []
    hits = [kw for kw in KEYWORDS if kw in text]
    return hits


def priority_ladder(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["name", "town", "cmi", "oai", "thi", "mi", "mi_category"]
    core = df[df["mi_category"] == "核心耦合区"].copy()
    core["tier"] = "第一梯队：优先深化型"
    core["reason"] = "文化基础与旅游热度同时较高，适合作为线路、品牌和体验深化节点"
    core = core.sort_values(["thi", "cmi"], ascending=False).head(5)

    dormant = df[(df["mi_category"] == "沉睡潜力区") & (df["cmi"] >= 60) & (df["oai"] >= 50)].copy()
    dormant["tier"] = "第二梯队：条件改善型"
    dormant["reason"] = "文化记忆与官方认证较强，但旅游热度偏低，重点补可达性、展示和停留节点"
    dormant = dormant.sort_values(["mi", "cmi"], ascending=[True, False]).head(5)

    hollow = df[(df["mi_category"] == "空心景点区") & (df["thi"] >= 45)].copy()
    hollow["tier"] = "第三梯队：文化补强型"
    hollow["reason"] = "旅游热度较高但文化识别不足，重点补地方叙事、非遗活动和解说系统"
    hollow = hollow.sort_values(["thi", "mi"], ascending=False).head(5)

    out = pd.concat([core, dormant, hollow], ignore_index=True)
    out = out[["tier", *cols, "reason"]]
    out.to_csv(TABLES / "final_priority_ladder.csv", index=False, encoding="utf-8-sig")
    return out


def comment_recognition(df: pd.DataFrame, priority: pd.DataFrame) -> pd.DataFrame:
    reviews = pd.read_csv(TABLES / "review_poi_matched.csv", encoding="utf-8-sig")
    reviews = reviews.dropna(subset=["poi_lng", "poi_lat", "text"]).copy()
    reviews["poi_lng"] = pd.to_numeric(reviews["poi_lng"], errors="coerce")
    reviews["poi_lat"] = pd.to_numeric(reviews["poi_lat"], errors="coerce")
    reviews = reviews.dropna(subset=["poi_lng", "poi_lat"])

    # Use priority anchors, then add high-review anchors if needed.
    selected_names = list(priority["name"].drop_duplicates())
    rows = []
    for _, a in df[df["name"].isin(selected_names)].iterrows():
        lat, lng = float(a["lat"]), float(a["lng"])
        nearby_idx = []
        for idx, r in reviews.iterrows():
            if haversine_km(lat, lng, float(r["poi_lat"]), float(r["poi_lng"])) <= 0.5:
                nearby_idx.append(idx)
        near = reviews.loc[nearby_idx]
        valid = int(len(near))
        hit_counter: Counter[str] = Counter()
        hit_count = 0
        for text in near["text"]:
            hits = text_keywords(str(text))
            if hits:
                hit_count += 1
                hit_counter.update(hits)
        rows.append({
            "name": a["name"],
            "town": a["town"],
            "mi_category": a["mi_category"],
            "review_n": valid,
            "culture_review_n": hit_count,
            "culture_review_ratio": round(hit_count / valid * 100, 1) if valid else 0.0,
            "top_keywords": "、".join([k for k, _ in hit_counter.most_common(6)]),
        })
    result = pd.DataFrame(rows)
    result = result.sort_values(["review_n", "culture_review_ratio"], ascending=False)
    result.to_csv(TABLES / "final_comment_cultural_recognition.csv", index=False, encoding="utf-8-sig")

    plot_df = result[result["review_n"] >= 3].head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=220)
    colors = [CATEGORY_COLORS.get(c, "#9aa7b7") for c in plot_df["mi_category"]]
    ax.barh(plot_df["name"], plot_df["culture_review_ratio"], color=colors)
    for y, (_, row) in enumerate(plot_df.iterrows()):
        ax.text(row["culture_review_ratio"] + 1, y, f"{row['culture_review_ratio']:.1f}% / n={int(row['review_n'])}", va="center", fontsize=8, color=MUTED)
    ax.set_xlim(0, min(100, max(30, float(plot_df["culture_review_ratio"].max()) + 18)))
    ax.set_xlabel("含文化关键词评论占比")
    ax.set_title("重点载体评论文化识别度抽样")
    ax.grid(axis="x", color=LINE, linewidth=0.7, alpha=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(MEDIA / "fig_6_10_comment_recognition_final.png", bbox_inches="tight")
    plt.close(fig)
    return result


def main() -> None:
    ensure_dirs()
    setup_mpl()
    df = pd.read_csv(TABLES / "indices_anchors.csv", encoding="utf-8-sig")
    numeric_cols = [
        "cmi", "oai", "thi", "mi", "poi_count_500m", "avg_rating_500m",
        "review_total_500m", "lng", "lat",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    render_knowledge_figures()
    sens, changes = run_sensitivity(df)
    priority = priority_ladder(df)
    recog = comment_recognition(df, priority)

    print("Sensitivity summary:")
    print(sens.to_string(index=False))
    print("\nPriority ladder:")
    print(priority[["tier", "name", "town", "cmi", "oai", "thi", "mi", "mi_category"]].to_string(index=False))
    print("\nComment recognition:")
    print(recog.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
