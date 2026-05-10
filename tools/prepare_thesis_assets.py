#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "output" / "figures"
KG_FIG_DIR = FIG_DIR / "knowledge_graph"
PIC_DIR = ROOT / "pictures"
TABLE_DIR = ROOT / "output" / "tables"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def draw_centered(draw: ImageDraw.ImageDraw, box, text: str, fill, fnt) -> None:
    x1, y1, x2, y2 = box
    lines = text.split("\n")
    line_boxes = [draw.textbbox((0, 0), line, font=fnt) for line in lines]
    widths = [b[2] - b[0] for b in line_boxes]
    heights = [b[3] - b[1] for b in line_boxes]
    total_h = sum(heights) + (len(lines) - 1) * 8
    y = y1 + ((y2 - y1) - total_h) / 2
    for line, w, h in zip(lines, widths, heights):
        x = x1 + ((x2 - x1) - w) / 2
        draw.text((x, y), line, fill=fill, font=fnt)
        y += h + 8


def rounded_rect(draw: ImageDraw.ImageDraw, box, fill, outline, radius=22, width=2) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw: ImageDraw.ImageDraw, start, end, fill=(74, 85, 104), width=4) -> None:
    draw.line([start, end], fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 14
    p1 = (end[0] - size * math.cos(angle - math.pi / 6), end[1] - size * math.sin(angle - math.pi / 6))
    p2 = (end[0] - size * math.cos(angle + math.pi / 6), end[1] - size * math.sin(angle + math.pi / 6))
    draw.polygon([end, p1, p2], fill=fill)


def pipeline_image(path: Path) -> None:
    img = Image.new("RGB", (1800, 980), "#f7f8fb")
    draw = ImageDraw.Draw(img)
    title_font = font(44, True)
    text_font = font(28)
    small_font = font(22)

    draw.text((80, 56), "南海区文旅资源多源数据采集与清洗流程", fill="#152238", font=title_font)
    draw.text((82, 118), "典籍、POI、评论、名录与空间锚点汇入统一的指数计算与错位识别框架", fill="#526173", font=small_font)

    boxes = [
        ("典籍语料\n53 份 / 8,991,098 字", "#e9f2ff"),
        ("文化实体关系\n8,048 实体 / 19,382 关系", "#edf7ee"),
        ("POI 与评论\n13,512 POI / 16,391 评论", "#fff4e5"),
        ("文化载体锚点\n220 总库 / 165 分析样本", "#f4ecff"),
        ("指数与空间分析\nCMI / OAI / THI / MI", "#eef6f7"),
    ]
    x0, y0, w, h, gap = 90, 280, 280, 160, 60
    for i, (label, color) in enumerate(boxes):
        x = x0 + i * (w + gap)
        rounded_rect(draw, (x, y0, x + w, y0 + h), color, "#b7c4d4")
        draw_centered(draw, (x + 12, y0 + 16, x + w - 12, y0 + h - 16), label, "#1f2937", text_font)
        if i < len(boxes) - 1:
            arrow(draw, (x + w + 8, y0 + h / 2), (x + w + gap - 10, y0 + h / 2))

    lower = [
        ("数据清洗", "OCR 校对、去重、坐标统一、类目纠正"),
        ("桥梁匹配", "载体向左接图谱，向右接 POI 与评论"),
        ("成果输出", "错位分层、核密度、镇街对比、九江专题"),
    ]
    lx, ly, lw, lh, lgap = 240, 610, 380, 150, 95
    for i, (head, body) in enumerate(lower):
        x = lx + i * (lw + lgap)
        rounded_rect(draw, (x, ly, x + lw, ly + lh), "#ffffff", "#ccd5df")
        draw.text((x + 30, ly + 28), head, fill="#253047", font=font(30, True))
        draw.text((x + 30, ly + 82), body, fill="#526173", font=small_font)
        if i < len(lower) - 1:
            arrow(draw, (x + lw + 10, ly + lh / 2), (x + lw + lgap - 12, ly + lh / 2), width=3)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def extraction_image(path: Path) -> None:
    img = Image.new("RGB", (1800, 900), "#fbfbf8")
    draw = ImageDraw.Draw(img)
    draw.text((80, 56), "实体—关系抽取、合并与入库流程", fill="#16213e", font=font(44, True))
    draw.text((82, 118), "以 LLM 抽取为起点，以证据句、去重合并与语义校验保证可复核性", fill="#526173", font=font(22))

    steps = [
        ("文本切块", "约 800 字/段\n多线程并发"),
        ("LLM 抽取", "实体、关系\n证据句"),
        ("质量控制", "方向校验\n禁用空泛关系"),
        ("同义合并", "名称规范化\n关系合规"),
        ("图谱入库", "8,048 实体\n19,382 关系"),
    ]
    x0, y0, w, h, gap = 110, 310, 260, 190, 75
    colors = ["#eaf3ff", "#eaf8ef", "#fff3df", "#f5edff", "#eaf7f7"]
    for i, (head, body) in enumerate(steps):
        x = x0 + i * (w + gap)
        rounded_rect(draw, (x, y0, x + w, y0 + h), colors[i], "#c0cad7")
        draw.text((x + 44, y0 + 36), head, fill="#1f2937", font=font(32, True))
        draw.multiline_text((x + 44, y0 + 92), body, fill="#526173", font=font(25), spacing=8)
        if i < len(steps) - 1:
            arrow(draw, (x + w + 8, y0 + h / 2), (x + w + gap - 14, y0 + h / 2))

    draw.text((110, 650), "输出成果：合并图谱总库、Neo4j 导入表、频次分档配色、典型人物与文化载体子图", fill="#253047", font=font(30, True))
    draw.text((110, 705), "用途：为 CMI 计算、载体文化记忆追溯、规划建议中的文化故事提取提供语义底座。", fill="#526173", font=font(24))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def image_grid(path: Path, title: str, images: list[tuple[Path, str]], canvas_size=(1800, 1160)) -> None:
    canvas = Image.new("RGB", canvas_size, "#f7f8fb")
    draw = ImageDraw.Draw(canvas)
    draw.text((70, 48), title, fill="#16213e", font=font(42, True))

    cols = 2
    margin_x = 70
    top = 140
    gap_x = 50
    gap_y = 72
    cell_w = (canvas_size[0] - margin_x * 2 - gap_x) // cols
    cell_h = 430
    for idx, (img_path, label) in enumerate(images):
        row = idx // cols
        col = idx % cols
        x = margin_x + col * (cell_w + gap_x)
        y = top + row * (cell_h + gap_y)
        panel = Image.open(img_path).convert("RGB")
        panel.thumbnail((cell_w, cell_h - 54), Image.LANCZOS)
        box = Image.new("RGB", (cell_w, cell_h), "#ffffff")
        bx = (cell_w - panel.width) // 2
        box.paste(panel, (bx, 0))
        ImageDraw.Draw(box).text((18, cell_h - 42), label, fill="#253047", font=font(24, True))
        box = ImageOps.expand(box, border=2, fill="#d5dde7")
        canvas.paste(box, (x, y))

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def setup_matplotlib() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 160


def poi_structure_chart(path: Path) -> None:
    setup_matplotlib()
    poi = pd.read_csv(TABLE_DIR / "poi_cleaned.csv")
    category = poi["category"].value_counts().sort_values(ascending=True)
    town = (
        poi["town"]
        .fillna("未标注")
        .replace({"nan": "未标注"})
        .value_counts()
        .reindex(["桂城街道", "里水镇", "狮山镇", "大沥镇", "丹灶镇", "西樵镇", "九江镇"])
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.4), gridspec_kw={"width_ratios": [1.2, 1]})
    axes[0].barh(category.index, category.values, color="#5B8DEF")
    axes[0].set_title("POI 类型构成（13,512 条）", fontsize=14, fontweight="bold")
    axes[0].set_xlabel("数量")
    for y, v in enumerate(category.values):
        axes[0].text(v + 35, y, f"{v:,}", va="center", fontsize=9)

    axes[1].bar(town.index, town.values, color="#66A182")
    axes[1].set_title("镇街 POI 分布", fontsize=14, fontweight="bold")
    axes[1].set_ylabel("数量")
    axes[1].tick_params(axis="x", rotation=35)
    for x, v in enumerate(town.values):
        axes[1].text(x, v + 60, f"{v:,}", ha="center", fontsize=9)

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=0.18)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def a_level_chart(path: Path) -> None:
    setup_matplotlib()
    df = pd.read_csv(TABLE_DIR / "a_level_correlation.csv")
    labels = [
        "等级-评分",
        "等级-评论量",
        "等级-正向率",
        "评分-评论量",
    ]
    x = range(len(df))
    width = 0.36
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.bar([i - width / 2 for i in x], df["pearson"], width=width, label="Pearson", color="#5B8DEF")
    ax.bar([i + width / 2 for i in x], df["spearman"], width=width, label="Spearman", color="#F2A65A")
    ax.axhline(0, color="#6b7280", linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 0.7)
    ax.set_ylabel("相关系数")
    ax.set_title("A 级景区等级与评分、评论热度的相关性（n=16）", fontsize=14, fontweight="bold")
    ax.legend(frameon=False)
    for i, row in df.iterrows():
        ax.text(i - width / 2, row["pearson"] + 0.025, f"{row['pearson']:.3f}", ha="center", fontsize=9)
        ax.text(i + width / 2, row["spearman"] + 0.025, f"{row['spearman']:.3f}", ha="center", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.18)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def correlation_heatmap(path: Path) -> None:
    setup_matplotlib()
    raw = pd.read_csv(TABLE_DIR / "potential_correlation_anchor.csv", nrows=7)
    raw = raw.rename(columns={raw.columns[0]: "metric"}).set_index("metric")
    data = raw.astype(float)
    fig, ax = plt.subplots(figsize=(8.4, 7.2))
    im = ax.imshow(data.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(data.columns)))
    ax.set_yticks(range(len(data.index)))
    ax.set_xticklabels(data.columns, rotation=35, ha="right")
    ax.set_yticklabels(data.index)
    ax.set_title("载体级指标 Pearson 相关矩阵（n=165）", fontsize=14, fontweight="bold")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data.iloc[i, j]
            color = "white" if abs(val) > 0.55 else "#1f2937"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=color, fontsize=9)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Pearson r")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    KG_FIG_DIR.mkdir(parents=True, exist_ok=True)
    pipeline_image(FIG_DIR / "thesis_data_pipeline.png")
    extraction_image(KG_FIG_DIR / "thesis_llm_extraction_pipeline.png")
    image_grid(
        KG_FIG_DIR / "thesis_kg_examples.png",
        "知识图谱全局网络与典型人物子图",
        [
            (PIC_DIR / "知识图谱总图.png", "知识图谱总图"),
            (PIC_DIR / "人物关联总图.png", "人物关联总图"),
            (PIC_DIR / "康有为周边人物.png", "康有为子图"),
            (PIC_DIR / "黄飞鸿周边人物.png", "黄飞鸿子图"),
        ],
    )
    image_grid(
        KG_FIG_DIR / "thesis_mismatch_maps.png",
        "500 m 网格错位识别：基础口径与知识图谱口径对比",
        [
            (FIG_DIR / "fig1_mismatch_map.png", "基础错位地图"),
            (FIG_DIR / "fig1_mismatch_0hop.png", "KG 0 跳口径"),
            (FIG_DIR / "fig1_mismatch_1hop.png", "KG 1 跳口径"),
            (FIG_DIR / "fig5_jiujiang_zoom.png", "九江专题放大"),
        ],
    )
    poi_structure_chart(FIG_DIR / "thesis_poi_structure.png")
    a_level_chart(FIG_DIR / "thesis_a_level_correlation.png")
    correlation_heatmap(FIG_DIR / "thesis_anchor_correlation_heatmap.png")

    # Neo4j / 子图导出原图，与正文合成图一并归入 knowledge_graph/ 便于资料包归档
    if PIC_DIR.is_dir():
        for f in PIC_DIR.glob("*.png"):
            if not f.is_file():
                continue
            dst = KG_FIG_DIR / f.name
            try:
                shutil.copy2(f, dst)
            except OSError as e:
                print("warn: skip pictures copy:", f.name, e, file=sys.stderr)


if __name__ == "__main__":
    main()
