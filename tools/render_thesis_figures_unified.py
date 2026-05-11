#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render a unified figure set for the thesis Markdown draft.

The script rewrites the PNG files referenced by docs/thesis_01/毕业论文_正文.md.
Map-like figures are rendered from the current tabular/GIS outputs with a
consistent visual grammar; non-map diagrams and charts use the same typography,
colors, and export resolution.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MaxNLocator
from PIL import Image, ImageDraw, ImageFont, ImageOps
from scipy.ndimage import gaussian_filter
from shapely.geometry import Point, Polygon, box, shape
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TABLES = ROOT / "output" / "tables"
FIGURES = ROOT / "output" / "figures"
GRID_FIGS = FIGURES / "grid_culture_tourism"
KG_FIGS = FIGURES / "knowledge_graph"
PICTURES = ROOT / "pictures"
PRECISE_TOWNS = DATA / "gis" / "nanhai_towns_440605_precise.geojson"
PRECISE_BOUNDARY = DATA / "gis" / "nanhai_boundary_440605_precise.geojson"

OUT_PATHS = {
    "data_pipeline": FIGURES / "thesis_data_pipeline.png",
    "llm_pipeline": KG_FIGS / "thesis_llm_extraction_pipeline.png",
    "kg_examples": KG_FIGS / "thesis_kg_examples.png",
    "poi_structure": FIGURES / "thesis_poi_structure.png",
    "scatter": GRID_FIGS / "fig2_category_scatter_20260510.png",
    "a_level": FIGURES / "thesis_a_level_correlation.png",
    "mismatch": GRID_FIGS / "thesis_mismatch_maps_20260510.png",
    "density": GRID_FIGS / "fig4_density_overlay_20260510.png",
    "town_bar": GRID_FIGS / "fig3_town_bar_20260510.png",
    "correlation": FIGURES / "thesis_anchor_correlation_heatmap.png",
    "jiujiang": GRID_FIGS / "fig5_jiujiang_zoom_20260510.png",
    "official": GRID_FIGS / "official_resources_spatialization_20260510.png",
    "official_grid": GRID_FIGS / "official_grid_coverage_20260510.png",
    "diagnostic": GRID_FIGS / "diagnostic_split_by_town_20260510.png",
}

TOWNS = ["桂城街道", "大沥镇", "里水镇", "狮山镇", "丹灶镇", "西樵镇", "九江镇"]
FONT_FAMILY = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
INK = "#26313f"
MUTED = "#637083"
LINE = "#d6dee8"
PAPER = "#ffffff"
PANEL = "#f7f8fb"
TOWN_LINE = "#8793a3"

CATEGORY_COLORS = {
    "双低空白": "#e8edf2",
    "一般地带": "#cdd6e0",
    "沉睡潜力": "#d95f59",
    "空心景点": "#4f8fd9",
    "核心耦合": "#7a4cc2",
}
MI_CATEGORY_COLORS = {
    "沉睡潜力区": "#d95f59",
    "空心景点区": "#4f8fd9",
    "核心耦合区": "#7a4cc2",
    "一般耦合区": "#9aa7b7",
}
RESOURCE_COLORS = {
    "不可移动文物": "#3366a8",
    "博物馆": "#f0a33a",
    "历史文化名镇": "#7a4cc2",
    "历史文化名村": "#2e9b60",
    "传统村落": "#35a978",
    "历史文化街区": "#d95f59",
    "历史建筑名录": "#64748b",
    "特色古村落": "#6fba44",
    "灌溉遗产": "#25a7b7",
}


def ensure_dirs() -> None:
    for p in OUT_PATHS.values():
        p.parent.mkdir(parents=True, exist_ok=True)


def setup_mpl() -> None:
    plt.rcParams["font.sans-serif"] = FONT_FAMILY
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = PAPER
    plt.rcParams["axes.facecolor"] = PAPER
    plt.rcParams["savefig.facecolor"] = PAPER
    plt.rcParams["font.size"] = 10
    plt.rcParams["axes.titlesize"] = 14
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["axes.labelcolor"] = INK
    plt.rcParams["xtick.color"] = INK
    plt.rcParams["ytick.color"] = INK


def cfont(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf") if bold else Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for fp in candidates:
        if fp.exists():
            return ImageFont.truetype(str(fp), size)
    return ImageFont.load_default()


def load_geojson(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def features_to_geoms(path: Path) -> list:
    fc = load_geojson(path)
    return [shape(feat["geometry"]) for feat in fc["features"]]


def plot_geom(ax, geom, *, facecolor="none", edgecolor=INK, linewidth=0.8, alpha=1.0, zorder=1):
    if geom.is_empty:
        return
    if geom.geom_type == "Polygon":
        x, y = geom.exterior.xy
        ax.fill(x, y, facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth, alpha=alpha, zorder=zorder)
        for ring in geom.interiors:
            rx, ry = ring.xy
            ax.fill(rx, ry, facecolor=PAPER, edgecolor=edgecolor, linewidth=linewidth * 0.5, alpha=alpha, zorder=zorder)
    elif geom.geom_type == "MultiPolygon":
        for part in geom.geoms:
            plot_geom(ax, part, facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth, alpha=alpha, zorder=zorder)
    elif geom.geom_type in ("LineString", "LinearRing"):
        x, y = geom.xy
        ax.plot(x, y, color=edgecolor, linewidth=linewidth, alpha=alpha, zorder=zorder)
    elif geom.geom_type == "MultiLineString":
        for part in geom.geoms:
            x, y = part.xy
            ax.plot(x, y, color=edgecolor, linewidth=linewidth, alpha=alpha, zorder=zorder)
    elif geom.geom_type == "GeometryCollection":
        for part in geom.geoms:
            plot_geom(ax, part, facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth, alpha=alpha, zorder=zorder)


def load_boundary_and_towns():
    towns_path = PRECISE_TOWNS if PRECISE_TOWNS.exists() else DATA / "gis" / "nanhai_towns_real.geojson"
    boundary_path = PRECISE_BOUNDARY if PRECISE_BOUNDARY.exists() else DATA / "gis" / "nanhai_boundary.geojson"
    boundary = unary_union(features_to_geoms(boundary_path))
    towns_fc = load_geojson(towns_path)
    towns = []
    for feat in towns_fc["features"]:
        name = feat["properties"].get("name") or feat["properties"].get("town") or ""
        geom = shape(feat["geometry"])
        if not geom.is_valid:
            geom = geom.buffer(0)
        towns.append((name, geom))
    if towns_path == PRECISE_TOWNS:
        boundary = unary_union([geom for _, geom in towns])
    return boundary, towns


def coord_formatter(suffix: str):
    return FuncFormatter(lambda val, _: f"{val:.2f}°{suffix}")


def add_map_axes_frame(ax, *, grid: bool = True) -> None:
    ax.tick_params(
        axis="both",
        which="major",
        direction="in",
        top=True,
        right=True,
        labeltop=False,
        labelright=False,
        length=4,
        width=0.75,
        labelsize=7.6,
        pad=3,
        colors=INK,
    )
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.xaxis.set_major_formatter(coord_formatter("E"))
    ax.yaxis.set_major_formatter(coord_formatter("N"))
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#2f3542")
        spine.set_linewidth(0.9)
    if grid:
        ax.grid(color="#e4e8ee", linewidth=0.45, linestyle="-", zorder=0)


def add_figure_frame(fig, *, linewidth: float = 1.15) -> None:
    fig.add_artist(
        mpatches.Rectangle(
            (0.012, 0.012),
            0.976,
            0.976,
            transform=fig.transFigure,
            fill=False,
            edgecolor="#111827",
            linewidth=linewidth,
            zorder=1000,
        )
    )


def save_fig(fig, path: Path, *, bbox: bool = False) -> None:
    if bbox:
        fig.savefig(path, bbox_inches="tight")
    else:
        fig.savefig(path)


def add_png_frame(path: Path, *, width: int = 6) -> None:
    with Image.open(path) as src:
        img = src.convert("RGB")
    draw = ImageDraw.Draw(img)
    inset = max(width, 4)
    draw.rectangle(
        (inset, inset, img.width - inset - 1, img.height - inset - 1),
        outline="#111827",
        width=width,
    )
    tmp = path.with_name(f"{path.stem}.framed{path.suffix}")
    img.save(tmp)
    tmp.replace(path)


def map_plate(title: str, source: str, *, figsize=(13.6, 8.2), ratios=(5.0, 1.25)):
    fig = plt.figure(figsize=figsize, dpi=220)
    gs = fig.add_gridspec(
        3,
        2,
        width_ratios=list(ratios),
        height_ratios=[0.62, 6.4, 0.44],
        left=0.045,
        right=0.965,
        top=0.955,
        bottom=0.06,
        hspace=0.0,
        wspace=0.0,
    )
    title_ax = fig.add_subplot(gs[0, :])
    map_ax = fig.add_subplot(gs[1, 0])
    legend_ax = fig.add_subplot(gs[1, 1])
    source_ax = fig.add_subplot(gs[2, :])
    for ax in (title_ax, source_ax):
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
            spine.set_color("#111827")
            spine.set_linewidth(0.9)
    title_ax.spines["bottom"].set_visible(True)
    source_ax.spines["top"].set_visible(True)
    title_ax.text(0.5, 0.5, title, ha="center", va="center", fontsize=14.5, fontweight="bold", color=INK)
    source_ax.text(0.02, 0.5, source, ha="left", va="center", fontsize=8.0, color="#5f6b7a")
    legend_ax.set_facecolor("#fbfcfe")
    legend_ax.set_xticks([])
    legend_ax.set_yticks([])
    for spine in legend_ax.spines.values():
        spine.set_visible(False)
        spine.set_color("#111827")
        spine.set_linewidth(0.9)
    legend_ax.spines["left"].set_visible(True)
    legend_ax.text(0.5, 0.94, "图例", ha="center", va="top", fontsize=13.0, fontweight="bold", color=INK)
    return fig, map_ax, legend_ax


def multi_map_plate(title: str, source: str, *, n_maps: int = 2, figsize=(14.8, 8.2)):
    fig = plt.figure(figsize=figsize, dpi=220)
    gs = fig.add_gridspec(
        3,
        n_maps + 1,
        width_ratios=[1.0] * n_maps + [0.56],
        height_ratios=[0.62, 6.4, 0.44],
        left=0.04,
        right=0.965,
        top=0.955,
        bottom=0.06,
        hspace=0.0,
        wspace=0.10,
    )
    title_ax = fig.add_subplot(gs[0, :])
    map_axes = [fig.add_subplot(gs[1, i]) for i in range(n_maps)]
    legend_ax = fig.add_subplot(gs[1, n_maps])
    source_ax = fig.add_subplot(gs[2, :])
    for ax in (title_ax, source_ax):
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
            spine.set_color("#111827")
            spine.set_linewidth(0.9)
    title_ax.spines["bottom"].set_visible(True)
    source_ax.spines["top"].set_visible(True)
    title_ax.text(0.5, 0.5, title, ha="center", va="center", fontsize=14.5, fontweight="bold", color=INK)
    source_ax.text(0.02, 0.5, source, ha="left", va="center", fontsize=8.0, color="#5f6b7a")
    legend_ax.set_facecolor("#fbfcfe")
    legend_ax.set_xticks([])
    legend_ax.set_yticks([])
    for spine in legend_ax.spines.values():
        spine.set_visible(False)
        spine.set_color("#111827")
        spine.set_linewidth(0.9)
    legend_ax.spines["left"].set_visible(True)
    legend_ax.text(0.5, 0.94, "图例", ha="center", va="top", fontsize=13.0, fontweight="bold", color=INK)
    return fig, map_axes, legend_ax


def panel_legend(ax, items, *, y=0.86, title=None, dy=0.065, marker_size=68):
    if title:
        ax.text(0.12, y, title, ha="left", va="center", fontsize=9.2, fontweight="bold", color=INK)
        y -= dy * 0.9
    for item in items:
        kind = item.get("kind", "patch")
        label = item["label"]
        color = item.get("color", "#999999")
        if kind == "line":
            ax.plot([0.12, 0.28], [y, y], color=color, linewidth=item.get("lw", 2.0), linestyle=item.get("ls", "-"), transform=ax.transAxes, clip_on=False)
        elif kind == "marker":
            ax.scatter([0.20], [y], s=item.get("size", marker_size), c=color, marker=item.get("marker", "o"), edgecolors=item.get("edgecolor", "white"), linewidths=0.7, transform=ax.transAxes, clip_on=False)
        elif kind == "star":
            ax.scatter([0.20], [y], s=item.get("size", marker_size + 30), c=color, marker="*", edgecolors="#5b4b00", linewidths=0.6, transform=ax.transAxes, clip_on=False)
        else:
            ax.add_patch(mpatches.Rectangle((0.12, y - 0.018), 0.15, 0.036, transform=ax.transAxes, facecolor=color, edgecolor=item.get("edgecolor", "#6b7280"), linewidth=0.65, clip_on=False))
        ax.text(0.34, y, label, ha="left", va="center", fontsize=8.6, color=INK, transform=ax.transAxes)
        y -= dy
    return y


def panel_separator(ax, y):
    ax.plot([0.10, 0.90], [y, y], color="#cfd6df", linewidth=0.8, linestyle="--", transform=ax.transAxes, clip_on=False)
    return y - 0.055


def panel_color_ramp(ax, y, label, cmap, *, low="低", high="高"):
    ax.text(0.12, y, label, ha="left", va="center", fontsize=9.0, fontweight="bold", color=INK, transform=ax.transAxes)
    grad = np.linspace(0, 1, 128).reshape(1, -1)
    ax.imshow(grad, extent=(0.12, 0.82, y - 0.070, y - 0.040), transform=ax.transAxes, cmap=cmap, aspect="auto", zorder=2)
    ax.add_patch(mpatches.Rectangle((0.12, y - 0.070), 0.70, 0.030, transform=ax.transAxes, fill=False, edgecolor="#6b7280", linewidth=0.6))
    ax.text(0.12, y - 0.088, low, ha="left", va="top", fontsize=7.4, color=MUTED, transform=ax.transAxes)
    ax.text(0.82, y - 0.088, high, ha="right", va="top", fontsize=7.4, color=MUTED, transform=ax.transAxes)
    return y - 0.135


def map_base(ax, *, title: str | None = None, label_towns: bool = True, extent=None):
    boundary, towns = load_boundary_and_towns()
    minx, miny, maxx, maxy = boundary.bounds
    pad_x = (maxx - minx) * 0.05
    pad_y = (maxy - miny) * 0.05
    plot_geom(ax, boundary, facecolor="#f5f7f9", edgecolor="none", linewidth=0, zorder=1)
    town_lines = unary_union([geom.boundary for _, geom in towns])
    plot_geom(ax, town_lines, facecolor="none", edgecolor=TOWN_LINE, linewidth=0.78, alpha=0.9, zorder=7)
    for name, geom in towns:
        if label_towns:
            pt = geom.representative_point()
            ax.text(pt.x, pt.y, name, ha="center", va="center", fontsize=8.0, color="#374151", zorder=30)
    plot_geom(ax, boundary, facecolor="none", edgecolor="#4b5563", linewidth=1.42, zorder=22)
    if extent is None:
        ax.set_xlim(minx - pad_x, maxx + pad_x)
        ax.set_ylim(miny - pad_y, maxy + pad_y)
    else:
        ax.set_xlim(extent[0], extent[2])
        ax.set_ylim(extent[1], extent[3])
    ax.set_aspect("equal", adjustable="box")
    if title:
        ax.text(
            0.018,
            0.982,
            title,
            ha="left",
            va="top",
            transform=ax.transAxes,
            fontsize=9.2,
            fontweight="bold",
            color=INK,
            bbox=dict(facecolor="white", edgecolor="#cbd5e1", linewidth=0.5, alpha=0.92, pad=2.0),
            zorder=80,
        )
    add_map_axes_frame(ax)
    add_north_arrow(ax)
    add_scale_bar(ax)
    return boundary


def add_north_arrow(ax):
    ax.annotate(
        "N",
        xy=(0.94, 0.88),
        xytext=(0.94, 0.79),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color=INK,
        arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=1.1, shrinkA=0, shrinkB=0),
        zorder=50,
    )


def add_scale_bar(ax, km=None):
    minx, maxx = ax.get_xlim()
    miny, maxy = ax.get_ylim()
    if km is None:
        width_km = (maxx - minx) * 111.32 * max(math.cos(math.radians((miny + maxy) / 2)), 0.2)
        km = 1 if width_km < 10 else 5
    lat = (miny + maxy) / 2
    deg = km / (111.32 * max(math.cos(math.radians(lat)), 0.2))
    x0 = minx + (maxx - minx) * 0.08
    y0 = miny + (maxy - miny) * 0.07
    ax.plot([x0, x0 + deg], [y0, y0], color=INK, linewidth=2.2, zorder=50)
    tick = (maxy - miny) * 0.008
    ax.plot([x0, x0], [y0 - tick, y0 + tick], color=INK, linewidth=1.2, zorder=50)
    ax.plot([x0 + deg, x0 + deg], [y0 - tick, y0 + tick], color=INK, linewidth=1.2, zorder=50)
    ax.text(x0 + deg / 2, y0 + tick * 1.6, f"{km} km", ha="center", va="bottom", fontsize=8.0, color=INK, zorder=50)


def grid_patches(df: pd.DataFrame, color_col: str, colors: dict[str, str], *, alpha=0.86):
    patches, facecolors = [], []
    half = 0.0045 / 2
    for row in df.itertuples(index=False):
        val = getattr(row, color_col)
        patches.append(mpatches.Rectangle((float(row.clng) - half, float(row.clat) - half), 0.0045, 0.0045))
        facecolors.append(colors.get(val, "#e5e7eb"))
    return PatchCollection(patches, facecolor=facecolors, edgecolor="none", alpha=alpha, zorder=4)


def numeric_grid_patches(df: pd.DataFrame, value_col: str, cmap, norm, *, alpha=0.9):
    patches, facecolors = [], []
    half = 0.0045 / 2
    for row in df.itertuples(index=False):
        val = float(getattr(row, value_col))
        if val <= 0:
            continue
        patches.append(mpatches.Rectangle((float(row.clng) - half, float(row.clat) - half), 0.0045, 0.0045))
        facecolors.append(cmap(norm(val)))
    return PatchCollection(patches, facecolor=facecolors, edgecolor="none", alpha=alpha, zorder=4)


def add_category_legend(ax, colors: dict[str, str], loc="lower right", title=None, ncol=1):
    handles = [mpatches.Patch(facecolor=c, edgecolor="none", label=k) for k, c in colors.items()]
    leg = ax.legend(handles=handles, loc=loc, frameon=True, framealpha=0.96, title=title, ncol=ncol, fontsize=8.5)
    leg.get_frame().set_edgecolor(LINE)
    leg.get_frame().set_linewidth(0.8)
    return leg


def title_block(draw, title: str, subtitle: str | None = None, x=72, y=50):
    draw.text((x, y), title, fill=INK, font=cfont(44, True))
    if subtitle:
        draw.text((x, y + 62), subtitle, fill=MUTED, font=cfont(23))


def draw_round(draw, box, fill, outline=LINE, radius=20, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_arrow(draw, start, end, fill=MUTED, width=4):
    draw.line([start, end], fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 15
    p1 = (end[0] - size * math.cos(angle - math.pi / 6), end[1] - size * math.sin(angle - math.pi / 6))
    p2 = (end[0] - size * math.cos(angle + math.pi / 6), end[1] - size * math.sin(angle + math.pi / 6))
    draw.polygon([end, p1, p2], fill=fill)


def centered_text(draw, box, text, font, fill=INK, spacing=7):
    x1, y1, x2, y2 = box
    lines = text.split("\n")
    bbs = [draw.textbbox((0, 0), line, font=font) for line in lines]
    heights = [bb[3] - bb[1] for bb in bbs]
    total_h = sum(heights) + spacing * (len(lines) - 1)
    y = y1 + ((y2 - y1) - total_h) / 2
    for line, bb, h in zip(lines, bbs, heights):
        w = bb[2] - bb[0]
        x = x1 + ((x2 - x1) - w) / 2
        draw.text((x, y), line, fill=fill, font=font)
        y += h + spacing


def render_data_pipeline():
    img = Image.new("RGB", (2200, 1200), PAPER)
    draw = ImageDraw.Draw(img)
    title_block(
        draw,
        "南海区文旅资源多源数据采集与清洗流程",
        "典籍、POI、评论、名录与空间锚点汇入统一的指数计算与错位识别框架",
    )
    boxes = [
        ("典籍语料\n53 份 / 8,991,098 字", "#e7f0fb"),
        ("文化实体关系\n8,048 实体 / 19,382 关系", "#e8f5ed"),
        ("POI 与评论\n13,512 POI / 16,391 评论", "#fff1dc"),
        ("文化载体锚点\n220 总库 / 165 样本", "#f0eafa"),
        ("指数与空间分析\nCMI / OAI / THI / MI", "#e8f5f5"),
    ]
    x0, y0, w, h, gap = 92, 310, 340, 185, 78
    for i, (label, color) in enumerate(boxes):
        x = x0 + i * (w + gap)
        draw_round(draw, (x, y0, x + w, y0 + h), color)
        centered_text(draw, (x + 18, y0 + 18, x + w - 18, y0 + h - 18), label, cfont(31, True))
        if i < len(boxes) - 1:
            draw_arrow(draw, (x + w + 14, y0 + h // 2), (x + w + gap - 16, y0 + h // 2))
    lower = [
        ("数据清洗", "OCR 校对、去重、坐标统一、类目纠正"),
        ("桥梁匹配", "载体向左接图谱，向右接 POI 与评论"),
        ("成果输出", "错位分层、核密度、镇街对比、专题诊断"),
    ]
    lx, ly, lw, lh, lgap = 270, 710, 460, 170, 130
    for i, (head, body) in enumerate(lower):
        x = lx + i * (lw + lgap)
        draw_round(draw, (x, ly, x + lw, ly + lh), "#fbfcfe")
        draw.text((x + 34, ly + 34), head, fill=INK, font=cfont(33, True))
        draw.text((x + 34, ly + 96), body, fill=MUTED, font=cfont(24))
        if i < len(lower) - 1:
            draw_arrow(draw, (x + lw + 16, ly + lh // 2), (x + lw + lgap - 18, ly + lh // 2), width=3)
    draw.text((74, 1092), "数据来源：data/corpus、output/tables、data/gis；制图：本研究整理。", fill="#7b8794", font=cfont(20))
    img.save(OUT_PATHS["data_pipeline"])


def render_llm_pipeline():
    img = Image.new("RGB", (2200, 1100), PAPER)
    draw = ImageDraw.Draw(img)
    title_block(draw, "实体—关系抽取、合并与入库流程", "以证据句、去重合并与语义校验保证知识图谱可复核性")
    steps = [
        ("文本切块", "约 800 字/段\n多线程并发"),
        ("LLM 抽取", "实体、关系\n证据句"),
        ("质量控制", "方向校验\n禁用空泛关系"),
        ("同义合并", "名称规范化\n关系合规"),
        ("图谱入库", "8,048 实体\n19,382 关系"),
    ]
    colors = ["#e7f0fb", "#e8f5ed", "#fff1dc", "#f0eafa", "#e8f5f5"]
    x0, y0, w, h, gap = 108, 350, 310, 210, 95
    for i, (head, body) in enumerate(steps):
        x = x0 + i * (w + gap)
        draw_round(draw, (x, y0, x + w, y0 + h), colors[i])
        draw.text((x + 42, y0 + 42), head, fill=INK, font=cfont(34, True))
        draw.multiline_text((x + 42, y0 + 105), body, fill=MUTED, font=cfont(25), spacing=8)
        if i < len(steps) - 1:
            draw_arrow(draw, (x + w + 16, y0 + h // 2), (x + w + gap - 18, y0 + h // 2))
    draw_round(draw, (180, 760, 2020, 910), "#fbfcfe")
    draw.text((230, 800), "输出成果", fill=INK, font=cfont(31, True))
    draw.text((420, 802), "合并图谱总库、Neo4j 导入表、频次分档配色、典型人物与文化载体子图", fill=MUTED, font=cfont(25))
    draw.text((74, 1002), "数据来源：data/entities_relations、output/neo4j；制图：本研究整理。", fill="#7b8794", font=cfont(20))
    img.save(OUT_PATHS["llm_pipeline"])


def render_kg_examples():
    panels = [
        (PICTURES / "知识图谱总图.png", "知识图谱总图"),
        (PICTURES / "人物关联总图.png", "人物关联总图"),
        (PICTURES / "康有为周边人物.png", "康有为子图"),
        (PICTURES / "黄飞鸿周边人物.png", "黄飞鸿子图"),
    ]
    canvas = Image.new("RGB", (2200, 1450), PAPER)
    draw = ImageDraw.Draw(canvas)
    title_block(draw, "知识图谱全局网络与典型人物子图", "全局结构与典型人物网络共同说明地方文化记忆的关系基础")
    cols, margin_x, top, gap_x, gap_y = 2, 76, 178, 54, 86
    cell_w = (2200 - margin_x * 2 - gap_x) // cols
    cell_h = 520
    for idx, (path, label) in enumerate(panels):
        row, col = divmod(idx, cols)
        x = margin_x + col * (cell_w + gap_x)
        y = top + row * (cell_h + gap_y)
        draw_round(draw, (x, y, x + cell_w, y + cell_h), "#fbfcfe")
        im = Image.open(path).convert("RGB")
        im.thumbnail((cell_w - 44, cell_h - 92), Image.LANCZOS)
        canvas.paste(im, (x + (cell_w - im.width) // 2, y + 22))
        draw.text((x + 26, y + cell_h - 56), label, fill=INK, font=cfont(25, True))
    draw.text((74, 1374), "数据来源：Neo4j 图谱导出与本研究整理。", fill="#7b8794", font=cfont(20))
    canvas.save(OUT_PATHS["kg_examples"])


def style_axes(ax, grid_axis="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines["left"].set_color(LINE)
    ax.spines["bottom"].set_color(LINE)
    ax.grid(axis=grid_axis, alpha=0.18, color="#8b98a8")


def style_legend(leg):
    if leg is None:
        return None
    leg.get_frame().set_edgecolor("#cbd5e1")
    leg.get_frame().set_linewidth(0.8)
    leg.get_frame().set_facecolor("#ffffff")
    leg.get_frame().set_alpha(0.96)
    return leg


def render_poi_structure():
    poi = pd.read_csv(TABLES / "poi_cleaned.csv")
    cat_order = [
        "公园绿地", "自然景观", "其他", "宗教场所", "人文古迹", "文化场馆",
        "休闲娱乐", "体育设施", "非遗体验", "教育研学", "特色街区",
    ]
    cats = poi["category"].value_counts().reindex(cat_order).fillna(0).astype(int)
    town_order = ["桂城街道", "里水镇", "狮山镇", "大沥镇", "丹灶镇", "西樵镇", "九江镇"]
    towns = poi["town"].value_counts().reindex(town_order).fillna(0).astype(int)
    fig = plt.figure(figsize=(13.2, 6.6), dpi=220)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.22, 1], wspace=0.28)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    bars = ax1.barh(cats.index[::-1], cats.values[::-1], color="#5b8cc0")
    ax1.set_title("POI 类型构成（13,512 条）")
    ax1.set_xlabel("数量")
    for bar in bars:
        ax1.text(bar.get_width() + 45, bar.get_y() + bar.get_height() / 2, f"{int(bar.get_width()):,}", va="center", fontsize=8)
    town_colors = ["#3c78a8", "#6fae7f", "#8b98a8", "#6b6fb3", "#d8a24a", "#c65d5b", "#9c6b45"]
    ax2.bar(towns.index, towns.values, color=town_colors)
    ax2.set_title("镇街 POI 分布")
    ax2.set_ylabel("数量")
    ax2.tick_params(axis="x", rotation=35)
    for i, v in enumerate(towns.values):
        ax2.text(i, v + 60, f"{v:,}", ha="center", fontsize=8)
    style_axes(ax1, "x")
    style_axes(ax2, "y")
    fig.suptitle("南海区旅游 POI 类型构成与镇街分布", x=0.02, y=0.98, ha="left", fontsize=16, fontweight="bold", color=INK)
    fig.text(0.02, 0.02, "数据来源：output/tables/poi_cleaned.csv；制图：本研究整理。", color="#7b8794", fontsize=8.5)
    fig.savefig(OUT_PATHS["poi_structure"], bbox_inches="tight")
    plt.close(fig)


def render_scatter():
    grid = pd.read_csv(TABLES / "grid_indices_kg.csv")
    fig, ax = plt.subplots(figsize=(10.8, 7.4), dpi=220)
    plot_order = ["双低空白", "一般地带", "沉睡潜力", "空心景点", "核心耦合"]
    for cat in plot_order:
        sub = grid[grid["category_1hop"] == cat]
        alpha = 0.16 if cat == "双低空白" else 0.72
        size = 14 if cat == "双低空白" else 24
        ax.scatter(sub["culture_1hop"], sub["tourism"], s=size, c=CATEGORY_COLORS[cat], label=cat, alpha=alpha, edgecolors="none")
    core = grid[grid["category_1hop"] == "核心耦合"].copy()
    ax.scatter(core["culture_1hop"], core["tourism"], s=95, marker="*", c="#f2c94c", edgecolors="#5b4b00", linewidths=0.6, zorder=10, label="核心耦合网格")
    ax.set_xlabel("文化厚度 C（1 跳口径）")
    ax.set_ylabel("旅游热度 T")
    ax.set_xlim(-3, 103)
    ax.set_ylim(-3, 72)
    ax.set_title("500 m 网格文化—旅游分布与错位分层")
    style_axes(ax)
    leg = ax.legend(frameon=True, ncol=2, fontsize=8.5)
    style_legend(leg)
    fig.text(0.02, 0.02, "数据来源：output/tables/grid_indices_kg.csv；制图：本研究整理。", color="#7b8794", fontsize=8.5)
    fig.savefig(OUT_PATHS["scatter"], bbox_inches="tight")
    plt.close(fig)


def render_a_level():
    df = pd.read_csv(TABLES / "a_level_correlation.csv")
    labels = ["等级—评分", "等级—评论量", "等级—正向率", "评分—评论量"]
    x = np.arange(len(df))
    width = 0.34
    fig, ax = plt.subplots(figsize=(9.6, 5.3), dpi=220)
    ax.bar(x - width / 2, df["pearson"], width=width, color="#5b8cc0", label="Pearson")
    ax.bar(x + width / 2, df["spearman"], width=width, color="#e5a44f", label="Spearman")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("相关系数")
    ax.set_ylim(0, 0.7)
    ax.set_title("A 级景区等级与评分、评论热度的相关性（n = 16）")
    for i, row in df.iterrows():
        ax.text(i - width / 2, row["pearson"] + 0.025, f"{row['pearson']:.3f}", ha="center", fontsize=8)
        ax.text(i + width / 2, row["spearman"] + 0.025, f"{row['spearman']:.3f}", ha="center", fontsize=8)
    style_axes(ax)
    style_legend(ax.legend(frameon=True))
    fig.text(0.02, 0.02, "数据来源：output/tables/a_level_correlation.csv；制图：本研究整理。", color="#7b8794", fontsize=8.5)
    fig.savefig(OUT_PATHS["a_level"], bbox_inches="tight")
    plt.close(fig)


def render_mismatch_maps():
    grid = pd.read_csv(TABLES / "grid_indices_kg.csv")
    source = "数据来源：output/tables/grid_indices_kg.csv；网格尺度：500 m；制图：本研究整理。"
    fig, axes, legend_ax = multi_map_plate("500 m 网格错位识别：基础口径与知识图谱口径对比", source, n_maps=2)
    for ax, col, title in zip(axes, ["category_0hop", "category_1hop"], ["0 跳口径", "1 跳口径"]):
        map_base(ax, title=title, label_towns=True)
        ax.add_collection(grid_patches(grid, col, CATEGORY_COLORS, alpha=0.88))
        core = grid[grid[col] == "核心耦合"]
        ax.scatter(core["clng"], core["clat"], marker="*", s=92, c="#f2c94c", edgecolors="#5b4b00", linewidths=0.5, zorder=26)
    y = panel_legend(
        legend_ax,
        [{"label": k, "color": v} for k, v in CATEGORY_COLORS.items()],
        y=0.84,
        title="网格错位类型",
        dy=0.070,
    )
    y = panel_separator(legend_ax, y - 0.02)
    panel_legend(
        legend_ax,
        [
            {"label": "核心耦合网格", "color": "#f2c94c", "kind": "star"},
            {"label": "区镇边界", "color": TOWN_LINE, "kind": "line", "lw": 1.0},
            {"label": "南海区边界", "color": "#4b5563", "kind": "line", "lw": 1.4},
        ],
        y=y,
        title="辅助要素",
        dy=0.070,
    )
    save_fig(fig, OUT_PATHS["mismatch"])
    plt.close(fig)


def points_to_density(x, y, extent, bins=260, sigma=5.5):
    minx, miny, maxx, maxy = extent
    H, _, _ = np.histogram2d(y, x, bins=[bins, bins], range=[[miny, maxy], [minx, maxx]])
    H = gaussian_filter(H, sigma=sigma)
    if H.max() > 0:
        H = H / H.max()
    return H


def render_density_overlay():
    boundary, _ = load_boundary_and_towns()
    minx, miny, maxx, maxy = boundary.bounds
    extent = (minx, miny, maxx, maxy)
    poi = pd.read_csv(TABLES / "poi_cleaned.csv")
    anchors = pd.read_csv(TABLES / "indices_anchors.csv")
    for df in (poi, anchors):
        df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    poi = poi.dropna(subset=["lng", "lat"])
    anchors = anchors.dropna(subset=["lng", "lat"])
    poi = poi[poi["lng"].between(minx, maxx) & poi["lat"].between(miny, maxy)]
    anchors = anchors[anchors["lng"].between(minx, maxx) & anchors["lat"].between(miny, maxy)]
    t = points_to_density(poi["lng"].astype(float), poi["lat"].astype(float), extent)
    c = points_to_density(anchors["lng"].astype(float), anchors["lat"].astype(float), extent, sigma=7.0)
    c_mask = np.ma.masked_less(c, 0.035)
    t_mask = np.ma.masked_less(t, 0.035)
    red_cmap = matplotlib.colors.LinearSegmentedColormap.from_list("culture_density", ["#fff7f6", "#f2a19b", "#b91c1c"])
    blue_cmap = matplotlib.colors.LinearSegmentedColormap.from_list("tourism_density", ["#f5f9ff", "#93c5fd", "#1d4ed8"])
    source = "数据来源：output/tables/poi_cleaned.csv、indices_anchors.csv；核密度为相对强度归一化结果；制图：本研究整理。"
    fig, axes, legend_ax = multi_map_plate("文化载体核密度与 POI 核密度对照", source, n_maps=2)
    for ax, data, cmap, title in [
        (axes[0], c_mask, red_cmap, "文化载体核密度"),
        (axes[1], t_mask, blue_cmap, "POI 核密度"),
    ]:
        map_base(ax, title=title, label_towns=True)
        ax.imshow(data, extent=[minx, maxx, miny, maxy], origin="lower", zorder=3, cmap=cmap, vmin=0, vmax=1, alpha=0.82)
    y = panel_color_ramp(legend_ax, 0.84, "文化载体核密度", red_cmap)
    y = panel_color_ramp(legend_ax, y, "POI 核密度", blue_cmap)
    y = panel_separator(legend_ax, y + 0.015)
    panel_legend(
        legend_ax,
        [
            {"label": "镇街边界", "color": TOWN_LINE, "kind": "line", "lw": 1.0},
            {"label": "南海区边界", "color": "#4b5563", "kind": "line", "lw": 1.4},
        ],
        y=y,
        title="辅助要素",
        dy=0.070,
    )
    save_fig(fig, OUT_PATHS["density"])
    plt.close(fig)


def render_town_bar():
    df = pd.read_csv(TABLES / "grid_town_summary_kg.csv")
    town_order = ["西樵镇", "九江镇", "丹灶镇", "桂城街道", "大沥镇", "狮山镇", "里水镇"]
    df = df.set_index("town").reindex(town_order).reset_index()
    fig = plt.figure(figsize=(13.0, 6.6), dpi=220)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1], wspace=0.28)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    x = np.arange(len(df))
    width = 0.26
    ax1.bar(x - width, df["culture_1hop_mean"], width=width, color="#d95f59", label="文化厚度 C")
    ax1.bar(x, df["tourism_mean"], width=width, color="#4f8fd9", label="旅游热度 T")
    ax1.bar(x + width, df["mismatch_1hop_mean"], width=width, color="#7a4cc2", label="错位值 M")
    ax1.axhline(0, color="#6b7280", linewidth=0.9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(df["town"], rotation=35, ha="right")
    ax1.set_ylabel("均值")
    ax1.set_title("镇街尺度 C / T / M 对比")
    style_legend(ax1.legend(frameon=True, fontsize=8.5))
    stack_cols = ["n_dormant_1hop", "n_hollow_1hop", "n_core_1hop"]
    labels = ["沉睡潜力", "空心景点", "核心耦合"]
    colors = ["#d95f59", "#4f8fd9", "#7a4cc2"]
    bottom = np.zeros(len(df))
    for col, lab, color in zip(stack_cols, labels, colors):
        ax2.bar(df["town"], df[col], bottom=bottom, color=color, label=lab)
        bottom += df[col].values
    ax2.set_title("1 跳口径重点网格计数")
    ax2.set_ylabel("网格数")
    ax2.tick_params(axis="x", rotation=35)
    style_legend(ax2.legend(frameon=True, fontsize=8.5))
    style_axes(ax1)
    style_axes(ax2)
    fig.suptitle("镇街尺度文化厚度、旅游热度与错位类型对比", x=0.02, ha="left", fontsize=16, fontweight="bold", color=INK)
    fig.text(0.02, 0.02, "数据来源：output/tables/grid_town_summary_kg.csv；制图：本研究整理。", color="#7b8794", fontsize=8.5)
    fig.savefig(OUT_PATHS["town_bar"], bbox_inches="tight")
    plt.close(fig)


def render_correlation_heatmap():
    raw = pd.read_csv(TABLES / "potential_correlation_anchor.csv", nrows=7)
    if "Unnamed: 0" in raw.columns:
        raw = raw.rename(columns={"Unnamed: 0": "metric"})
    else:
        raw = raw.rename(columns={raw.columns[0]: "metric"})
    data = raw.set_index("metric").astype(float)
    fig, ax = plt.subplots(figsize=(8.2, 7.2), dpi=220)
    im = ax.imshow(data.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_xticklabels(data.columns, rotation=35, ha="right")
    ax.set_yticklabels(data.index)
    ax.set_title("载体级指标 Pearson 相关矩阵（n = 165）")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data.iloc[i, j]
            color = "white" if abs(val) >= 0.56 else INK
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8.2, color=color)
    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04)
    cbar.set_label("Pearson r")
    fig.text(0.02, 0.02, "数据来源：output/tables/potential_correlation_anchor.csv；制图：本研究整理。", color="#7b8794", fontsize=8.5)
    fig.savefig(OUT_PATHS["correlation"], bbox_inches="tight")
    plt.close(fig)


def render_jiujiang_zoom():
    grid = pd.read_csv(TABLES / "grid_indices_kg.csv")
    anchors = pd.read_csv(TABLES / "indices_anchors.csv")
    anchors["lng"] = pd.to_numeric(anchors["lng"], errors="coerce")
    anchors["lat"] = pd.to_numeric(anchors["lat"], errors="coerce")
    anchors = anchors.dropna(subset=["lng", "lat"])
    jj_grid = grid[grid["town"] == "九江镇"].copy()
    extent = (
        jj_grid["clng"].min() - 0.015,
        jj_grid["clat"].min() - 0.015,
        jj_grid["clng"].max() + 0.015,
        jj_grid["clat"].max() + 0.015,
    )
    source = "数据来源：output/tables/grid_indices_kg.csv、indices_anchors.csv；制图：本研究整理。"
    fig, ax, legend_ax = map_plate("九江片区错位专题图", source, figsize=(12.2, 8.4), ratios=(4.8, 1.28))
    map_base(ax, title="1 跳口径网格错位与文化载体分布", label_towns=False, extent=extent)
    ax.add_collection(grid_patches(jj_grid, "category_1hop", CATEGORY_COLORS, alpha=0.88))
    jj_anchors = anchors[(anchors["lng"].between(extent[0], extent[2])) & (anchors["lat"].between(extent[1], extent[3]))]
    for cat, color in MI_CATEGORY_COLORS.items():
        sub = jj_anchors[jj_anchors["mi_category"] == cat]
        if not sub.empty:
            ax.scatter(sub["lng"], sub["lat"], s=42, c=color, edgecolors="white", linewidths=0.5, label=cat, zorder=24)
    label_names = ["九江双蒸博物馆", "吴家大院", "九江镇烟桥烟南村", "九江镇烟桥村"]
    for _, row in jj_anchors[jj_anchors["name"].isin(label_names)].iterrows():
        ax.text(
            row["lng"] + 0.002,
            row["lat"] + 0.002,
            row["name"],
            fontsize=7.2,
            color=INK,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.82, pad=1.0),
            zorder=35,
        )
    y = panel_legend(
        legend_ax,
        [{"label": k, "color": v} for k, v in CATEGORY_COLORS.items()],
        y=0.84,
        title="网格错位类型",
        dy=0.060,
    )
    y = panel_separator(legend_ax, y - 0.005)
    panel_legend(
        legend_ax,
        [{"label": k, "color": v, "kind": "marker", "size": 54} for k, v in MI_CATEGORY_COLORS.items()],
        y=y,
        title="文化载体类型",
        dy=0.060,
        marker_size=54,
    )
    save_fig(fig, OUT_PATHS["jiujiang"])
    plt.close(fig)


def render_official_resources():
    official = pd.read_csv(TABLES / "official_resources_20260510.csv")
    official["lng"] = pd.to_numeric(official["lng"], errors="coerce")
    official["lat"] = pd.to_numeric(official["lat"], errors="coerce")
    official = official.dropna(subset=["lng", "lat"])
    source = "数据来源：output/tables/official_resources_20260510.csv；共 593 条官方扩展资源；制图：本研究整理。"
    fig, ax, legend_ax = map_plate("官方资源扩展空间化结果", source, figsize=(12.0, 8.6), ratios=(4.4, 1.35))
    map_base(ax, title="官方资源点位分布", label_towns=True)
    for typ, color in RESOURCE_COLORS.items():
        sub = official[official["source_type"] == typ]
        if sub.empty:
            continue
        size = 16 if typ not in ["博物馆", "历史文化名镇"] else 38
        marker = "^" if typ == "博物馆" else "o"
        ax.scatter(sub["lng"], sub["lat"], s=size, c=color, marker=marker, alpha=0.78, edgecolors="white", linewidths=0.35, label=typ, zorder=20)
    y = panel_legend(
        legend_ax,
        [
            {"label": typ, "color": color, "kind": "marker", "marker": "^" if typ == "博物馆" else "o", "size": 56 if typ == "博物馆" else 38}
            for typ, color in RESOURCE_COLORS.items()
        ],
        y=0.84,
        title="资源类型",
        dy=0.052,
        marker_size=42,
    )
    y = panel_separator(legend_ax, y)
    panel_legend(
        legend_ax,
        [
            {"label": "镇街边界", "color": TOWN_LINE, "kind": "line", "lw": 1.0},
            {"label": "南海区边界", "color": "#4b5563", "kind": "line", "lw": 1.4},
        ],
        y=y,
        title="辅助要素",
        dy=0.060,
    )
    save_fig(fig, OUT_PATHS["official"])
    plt.close(fig)


def render_official_grid():
    official_grid = pd.read_csv(TABLES / "official_grid_coverage_20260510.csv")
    source = "数据来源：output/tables/official_grid_coverage_20260510.csv；网格尺度：500 m；制图：本研究整理。"
    fig, ax, legend_ax = map_plate("500 m 网格官方资源覆盖", source, figsize=(12.0, 8.6), ratios=(4.4, 1.35))
    map_base(ax, title="官方资源覆盖计数", label_towns=True)
    cmap = plt.get_cmap("YlGnBu")
    vals = official_grid["official_count"].astype(float)
    norm = matplotlib.colors.Normalize(vmin=1, vmax=max(vals.max(), 1))
    ax.add_collection(numeric_grid_patches(official_grid, "official_count", cmap, norm, alpha=0.88))
    y = panel_color_ramp(legend_ax, 0.84, "官方资源覆盖计数", cmap, low="1", high=f"{int(vals.max())}")
    y = panel_separator(legend_ax, y + 0.02)
    panel_legend(
        legend_ax,
        [
            {"label": "有覆盖网格", "color": cmap(norm(max(vals.max(), 1)))},
            {"label": "镇街边界", "color": TOWN_LINE, "kind": "line", "lw": 1.0},
            {"label": "南海区边界", "color": "#4b5563", "kind": "line", "lw": 1.4},
        ],
        y=y,
        title="辅助要素",
        dy=0.066,
    )
    save_fig(fig, OUT_PATHS["official_grid"])
    plt.close(fig)


def render_diagnostic():
    df = pd.read_csv(TABLES / "diagnostic_split_by_town_20260510.csv")
    town_order = ["桂城街道", "大沥镇", "里水镇", "狮山镇", "丹灶镇", "西樵镇", "九江镇"]
    df = df.set_index("town").reindex(town_order).reset_index()
    x = np.arange(len(df))
    width = 0.22
    fig, ax = plt.subplots(figsize=(12.2, 6.1), dpi=220)
    ax.bar(x - width, df["C_text_mean"], width, label="C 典籍/图谱", color="#d95f59")
    ax.bar(x, df["O_official_mean"], width, label="O 官方资源", color="#7a4cc2")
    ax.bar(x + width, df["T_tourism_mean"], width, label="T 旅游热度", color="#4f8fd9")
    ax.plot(x, df["M_revised_mean"], color="#222f3e", marker="o", linewidth=1.8, label="修正错位 M")
    ax.axhline(0, color="#6b7280", linewidth=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(df["town"])
    ax.set_ylabel("均值")
    ax.set_title("镇街典籍—官方—旅游诊断拆分")
    style_axes(ax)
    style_legend(ax.legend(ncol=4, frameon=True, loc="upper left", bbox_to_anchor=(0, 1.02)))
    fig.text(0.02, 0.02, "数据来源：output/tables/diagnostic_split_by_town_20260510.csv；制图：本研究整理。", color="#7b8794", fontsize=8.5)
    fig.savefig(OUT_PATHS["diagnostic"], bbox_inches="tight")
    plt.close(fig)


def write_style_readme():
    out = FIGURES / "thesis_figure_style_readme.md"
    out.write_text(
        "\n".join(
            [
                "# Thesis Figure Style",
                "",
                "- Font: Microsoft YaHei / SimHei fallback.",
                "- Map palette: red = culture high / tourism low, blue = tourism high / culture low, purple = coupled high values.",
                "- Map basics: outer figure frame, inner map coordinate frame, title band, legend panel, source band, N arrow and scale bar.",
                "- Export: PNG, 220 dpi, white background.",
                "- Layout reference: output/figures/thesis_gis_design_template_image2.png.",
                "- Source script: tools/render_thesis_figures_unified.py.",
            ]
        ),
        encoding="utf-8",
    )


def apply_output_frames():
    for path in OUT_PATHS.values():
        if path.exists():
            add_png_frame(path, width=4)


def main() -> None:
    ensure_dirs()
    setup_mpl()
    render_data_pipeline()
    render_llm_pipeline()
    render_kg_examples()
    render_poi_structure()
    render_scatter()
    render_a_level()
    render_mismatch_maps()
    render_density_overlay()
    render_town_bar()
    render_correlation_heatmap()
    render_jiujiang_zoom()
    render_official_resources()
    render_official_grid()
    render_diagnostic()
    apply_output_frames()
    write_style_readme()
    print("Rendered unified thesis figures:")
    for key, path in OUT_PATHS.items():
        print(f"  {key}: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
