#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.colors import Normalize
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "docs" / "tasks" / "5.10"
FIG_DIR = OUT_DIR / "figures"
TABLE_DIR = ROOT / "output" / "tables"
DATA_DIR = ROOT / "data"
TASK_422 = ROOT / "docs" / "tasks" / "4.22"

TOWNS = ["桂城街道", "大沥镇", "里水镇", "狮山镇", "丹灶镇", "西樵镇", "九江镇"]
TOWN_ALIAS = {
    "桂城": "桂城街道",
    "平洲": "桂城街道",
    "大沥": "大沥镇",
    "黄岐": "大沥镇",
    "盐步": "大沥镇",
    "里水": "里水镇",
    "和顺": "里水镇",
    "狮山": "狮山镇",
    "罗村": "狮山镇",
    "小塘": "狮山镇",
    "官窑": "狮山镇",
    "丹灶": "丹灶镇",
    "金沙": "丹灶镇",
    "西樵": "西樵镇",
    "九江": "九江镇",
    "沙头": "九江镇",
}
TYPE_COLORS = {
    "不可移动文物": "#3b82f6",
    "博物馆": "#f59e0b",
    "历史文化名镇": "#7c3aed",
    "历史文化名村": "#16a34a",
    "传统村落": "#10b981",
    "历史文化街区": "#ef4444",
    "历史建筑名录": "#64748b",
    "特色古村落": "#22c55e",
    "灌溉遗产": "#06b6d4",
}


def setup_matplotlib() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150


def norm_text(text: Any) -> str:
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return ""
    text = str(text)
    text = text.replace("\n", "")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[（）()\[\]【】《》<>·、，,。.;；:：\"'“”‘’\-—_/\\]", "", text)
    for token in ["广东省", "佛山市", "南海区", "居委会", "村委会", "社区居委会"]:
        text = text.replace(token, "")
    return text


def strip_town_prefix(text: str) -> str:
    out = text
    for town in TOWNS:
        out = out.replace(norm_text(town), "")
    for alias in sorted(TOWN_ALIAS, key=len, reverse=True):
        out = out.replace(norm_text(alias), "")
    return out


def key_variants(text: Any) -> list[str]:
    key = norm_text(text)
    variants = [key]
    stripped = strip_town_prefix(key)
    if stripped and stripped != key:
        variants.append(stripped)
    return [x for x in dict.fromkeys(variants) if len(x) >= 2]


def extract_town(*texts: Any) -> str:
    joined = "".join("" if x is None else str(x) for x in texts)
    for town in TOWNS:
        if town in joined:
            return town
    for alias, town in TOWN_ALIAS.items():
        if alias in joined:
            return town
    return "未标注"


def make_circle(lng: float, lat: float, radius_m: float, steps: int = 48) -> dict:
    lat_deg = radius_m / 111_000
    lng_deg = radius_m / (111_000 * max(math.cos(math.radians(lat)), 0.2))
    coords = []
    for i in range(steps + 1):
        ang = 2 * math.pi * i / steps
        coords.append([lng + math.cos(ang) * lng_deg, lat + math.sin(ang) * lat_deg])
    return {"type": "Polygon", "coordinates": [coords]}


def polygon_from_geom(geom) -> dict:
    return mapping(geom)


def file_by_content(kind: str) -> Path:
    candidates = sorted(TASK_422.glob("*.xls*"))
    for path in candidates:
        try:
            raw = pd.read_excel(path, header=None, nrows=6)
            values = " ".join(str(x) for x in raw.fillna("").values.ravel())
        except Exception:
            continue
        if kind == "immovable" and "统计年代" in values and "文物级别" in values:
            return path
        if kind == "museum" and "备案博物馆" in values and "详细地址" in values:
            return path
        if kind == "history" and "历史文化资源名录" in values:
            return path
    raise FileNotFoundError(kind)


def load_immovable() -> list[dict]:
    path = file_by_content("immovable")
    df = pd.read_excel(path)
    rows = []
    for idx, row in df.iterrows():
        name = str(row["名称"]).strip()
        address = str(row["地址及位置"]).strip()
        town = extract_town(address, name)
        rows.append(
            {
                "record_id": f"IH_{idx + 1:04d}",
                "source_file": path.name,
                "source_type": "不可移动文物",
                "resource_class": str(row["类别"]).strip(),
                "sub_class": str(row["小类"]).strip(),
                "level": str(row["文物级别"]).strip(),
                "name": name,
                "era": str(row["统计年代"]).strip(),
                "address": address,
                "town": town,
                "target_geometry": "point",
            }
        )
    return rows


def load_museums() -> list[dict]:
    path = file_by_content("museum")
    df = pd.read_excel(path, header=None)
    df = df.iloc[2:].copy()
    rows = []
    for i, row in df.iterrows():
        if pd.isna(row[3]):
            continue
        name = str(row[3]).strip()
        town = str(row[2]).strip()
        address = str(row[5]).strip()
        rows.append(
            {
                "record_id": f"MUS_{len(rows) + 1:04d}",
                "source_file": path.name,
                "source_type": "博物馆",
                "resource_class": "展示型文化桥梁",
                "sub_class": str(row[4]).strip(),
                "level": str(row[4]).strip(),
                "name": name,
                "era": "",
                "address": address,
                "town": town,
                "target_geometry": "point",
            }
        )
    return rows


def load_historical_catalog() -> list[dict]:
    path = file_by_content("history")
    raw = pd.read_excel(path, header=None)
    rows = []
    cur_cat = ""
    cur_level = ""
    for _, row in raw.iloc[4:].iterrows():
        cat = "" if pd.isna(row[1]) else str(row[1]).replace("\n", "").strip()
        level = "" if pd.isna(row[2]) else str(row[2]).replace("\n", " ").strip()
        name = "" if pd.isna(row[3]) else str(row[3]).replace("\n", "").strip()
        if cat:
            cur_cat = cat
        if level:
            cur_level = level
        if not name:
            continue
        town = extract_town(name)
        target = "point"
        if cur_cat in ["历史文化名镇", "历史文化名村", "传统村落", "特色古村落", "灌溉遗产"]:
            target = "area"
        if cur_cat == "历史文化街区":
            target = "line_or_area"
        rows.append(
            {
                "record_id": f"HC_{len(rows) + 1:04d}",
                "source_file": path.name,
                "source_type": cur_cat,
                "resource_class": cur_cat,
                "sub_class": "",
                "level": cur_level,
                "name": name,
                "era": "",
                "address": name,
                "town": town,
                "target_geometry": target,
            }
        )
    return rows


def load_towns():
    fc = json.loads((DATA_DIR / "gis" / "nanhai_towns_real.geojson").read_text(encoding="utf-8"))
    geoms = []
    names = []
    for feat in fc["features"]:
        names.append(feat["properties"]["name"])
        geoms.append(shape(feat["geometry"]))
    tree = STRtree(geoms)
    by_name = dict(zip(names, geoms))
    return names, geoms, tree, by_name, unary_union(geoms)


def which_town(point: Point, names: list[str], geoms: list[Any], tree: STRtree) -> str:
    for idx in tree.query(point):
        if geoms[int(idx)].contains(point):
            return names[int(idx)]
    return "未标注"


def load_points() -> tuple[list[dict], list[dict]]:
    anchors = json.loads((DATA_DIR / "anchors" / "cultural_anchors.json").read_text(encoding="utf-8"))["anchors"]
    pois = json.loads((DATA_DIR / "poi" / "poi_cleaned.json").read_text(encoding="utf-8"))["pois"]
    return anchors, pois


def extract_tokens(text: Any) -> list[str]:
    if text is None:
        return []
    text = str(text).replace("\n", "")
    suffixes = [
        "社区居委会",
        "村委会",
        "社区",
        "村",
        "街区",
        "风景区",
        "景区",
        "公园",
        "书院",
        "宗祠",
        "古庙",
        "博物馆",
        "大道",
        "大街",
        "街",
        "路",
        "巷",
        "圩",
        "墟",
        "洞",
        "山",
    ]
    tokens: list[str] = []
    for suf in suffixes:
        pattern = rf"[\u4e00-\u9fa5A-Za-z0-9]{{1,12}}{suf}"
        tokens.extend(re.findall(pattern, text))
    cleaned = []
    for token in tokens:
        n = norm_text(token)
        generic_tokens = {"广东", "广东省", "佛山", "佛山市", "南海", "南海区"}
        if len(n) >= 2 and n not in generic_tokens:
            cleaned.append(n)
            stripped = strip_town_prefix(n)
            if stripped and stripped != n and len(stripped) >= 2 and stripped not in generic_tokens:
                cleaned.append(stripped)
    return sorted(set(cleaned), key=len, reverse=True)


def build_indexes(anchors: list[dict], pois: list[dict]) -> dict:
    anchor_name: dict[str, list[dict]] = defaultdict(list)
    poi_name: dict[str, list[dict]] = defaultdict(list)
    token_points: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)

    for a in anchors:
        key = norm_text(a.get("name"))
        if key:
            anchor_name[key].append(a)
        town = a.get("town") or extract_town(a.get("address"), a.get("name"))
        for token in extract_tokens(a.get("address")) + extract_tokens(a.get("name")):
            if a.get("lng") and a.get("lat"):
                try:
                    lng, lat = float(a["lng"]), float(a["lat"])
                except Exception:
                    continue
                if valid_lnglat(lng, lat):
                    token_points[(town, token)].append((lng, lat))
    for p in pois:
        key = norm_text(p.get("name"))
        if key:
            poi_name[key].append(p)
        town = p.get("town") or extract_town(p.get("address"), p.get("name"))
        for token in extract_tokens(p.get("address")) + extract_tokens(p.get("name")):
            if p.get("lng") and p.get("lat"):
                try:
                    lng, lat = float(p["lng"]), float(p["lat"])
                except Exception:
                    continue
                if valid_lnglat(lng, lat):
                    token_points[(town, token)].append((lng, lat))

    token_centroid = {}
    for key, pts in token_points.items():
        xs, ys = zip(*pts)
        token_centroid[key] = (sum(xs) / len(xs), sum(ys) / len(ys), len(pts))

    return {"anchor_name": anchor_name, "poi_name": poi_name, "token_centroid": token_centroid, "pois": pois}


def centroid_of_town(town: str, town_polys: dict[str, Any]) -> tuple[float, float]:
    geom = town_polys.get(town) or next(iter(town_polys.values()))
    p = geom.representative_point()
    return p.x, p.y


def valid_lnglat(lng: float, lat: float) -> bool:
    return math.isfinite(lng) and math.isfinite(lat) and 112.7 <= lng <= 113.4 and 22.6 <= lat <= 23.4


def choose_point(items: list[dict]) -> tuple[float, float] | None:
    for item in items:
        try:
            lng = float(item.get("lng"))
            lat = float(item.get("lat"))
            if valid_lnglat(lng, lat):
                return lng, lat
        except Exception:
            continue
    return None


def geocode_record(rec: dict, indexes: dict, town_polys: dict[str, Any]) -> dict:
    name_keys = key_variants(rec["name"])
    town = rec["town"] if rec["town"] in TOWNS else extract_town(rec["address"], rec["name"])
    rec["town"] = town

    for name_key in name_keys:
        if name_key in indexes["anchor_name"]:
            pt = choose_point(indexes["anchor_name"][name_key])
            if pt:
                rec.update(
                    {
                        "lng": round(pt[0], 6),
                        "lat": round(pt[1], 6),
                        "spatial_method": "existing_anchor_name",
                        "spatial_confidence": 0.98,
                        "matched_existing_anchor": indexes["anchor_name"][name_key][0].get("name", ""),
                        "matched_poi": "",
                    }
                )
                return rec

        if name_key in indexes["poi_name"]:
            same_town = [p for p in indexes["poi_name"][name_key] if (p.get("town") == town or town == "未标注")]
            pt = choose_point(same_town or indexes["poi_name"][name_key])
            if pt:
                rec.update(
                    {
                        "lng": round(pt[0], 6),
                        "lat": round(pt[1], 6),
                        "spatial_method": "poi_name_exact",
                        "spatial_confidence": 0.94,
                        "matched_existing_anchor": "",
                        "matched_poi": (same_town or indexes["poi_name"][name_key])[0].get("name", ""),
                    }
                )
                return rec

    # Fuzzy name contains match, mainly useful for museums and historical buildings.
    for name_key in name_keys:
        if len(name_key) >= 4:
            for key, items in indexes["anchor_name"].items():
                if len(key) >= 4 and (name_key in key or key in name_key):
                    pt = choose_point(items)
                    if pt:
                        rec.update(
                            {
                                "lng": round(pt[0], 6),
                                "lat": round(pt[1], 6),
                                "spatial_method": "existing_anchor_fuzzy",
                                "spatial_confidence": 0.88,
                                "matched_existing_anchor": items[0].get("name", ""),
                                "matched_poi": "",
                            }
                        )
                        return rec
            for key, items in indexes["poi_name"].items():
                if len(key) >= 4 and (name_key in key or key in name_key):
                    same_town = [p for p in items if (p.get("town") == town or town == "未标注")]
                    pt = choose_point(same_town or items)
                    if pt:
                        rec.update(
                            {
                                "lng": round(pt[0], 6),
                                "lat": round(pt[1], 6),
                                "spatial_method": "poi_name_fuzzy",
                                "spatial_confidence": 0.84,
                                "matched_existing_anchor": "",
                                "matched_poi": (same_town or items)[0].get("name", ""),
                            }
                        )
                        return rec

    tokens = extract_tokens(rec.get("address")) + extract_tokens(rec.get("name"))
    for token in tokens:
        for key in [(town, token), ("未标注", token)]:
            if key in indexes["token_centroid"]:
                lng, lat, n = indexes["token_centroid"][key]
                rec.update(
                    {
                        "lng": round(lng, 6),
                        "lat": round(lat, 6),
                        "spatial_method": "address_token_centroid",
                        "spatial_confidence": 0.72 if n >= 2 else 0.62,
                        "matched_existing_anchor": "",
                        "matched_poi": f"{token} ({n} points)",
                    }
                )
                return rec

    lng, lat = centroid_of_town(town, town_polys)
    rec.update(
        {
            "lng": round(lng, 6),
            "lat": round(lat, 6),
            "spatial_method": "town_representative_point",
            "spatial_confidence": 0.38,
            "matched_existing_anchor": "",
            "matched_poi": "",
        }
    )
    return rec


def duplicate_status(rec: dict, indexes: dict) -> tuple[str, str]:
    for key in key_variants(rec["name"]):
        if key in indexes["anchor_name"]:
            return "duplicate_existing_anchor", indexes["anchor_name"][key][0].get("name", "")
        if key in indexes["poi_name"]:
            return "matched_poi_only", indexes["poi_name"][key][0].get("name", "")
    return "new_candidate", ""


def to_feature(rec: dict, town_polys: dict[str, Any]) -> dict:
    props = {k: v for k, v in rec.items() if k not in {"geometry"}}
    target = rec["target_geometry"]
    town = rec.get("town")
    if rec["source_type"] == "历史文化名镇" and town in town_polys:
        geom = polygon_from_geom(town_polys[town])
        props["geometry_note"] = "town_polygon_exact"
        props["proxy_radius_m"] = 0
    elif target == "area":
        radius = 900 if rec["source_type"] == "灌溉遗产" else 420
        geom = make_circle(float(rec["lng"]), float(rec["lat"]), radius)
        props["geometry_note"] = "area_proxy_buffer"
        props["proxy_radius_m"] = radius
    elif target == "line_or_area":
        radius = 300
        geom = make_circle(float(rec["lng"]), float(rec["lat"]), radius)
        props["geometry_note"] = "street_area_proxy_buffer"
        props["proxy_radius_m"] = radius
    else:
        geom = {"type": "Point", "coordinates": [float(rec["lng"]), float(rec["lat"])]}
        props["geometry_note"] = "point"
        props["proxy_radius_m"] = 0
    return {"type": "Feature", "properties": props, "geometry": geom}


def geometry_shape(feature: dict):
    return shape(feature["geometry"])


def add_grid_coverage(features: list[dict], grid: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    grid_rows = []
    points = [Point(float(r.clng), float(r.clat)) for r in grid.itertuples()]
    for r in grid.itertuples(index=False):
        grid_rows.append(
            {
                "ix": r.ix,
                "iy": r.iy,
                "clng": r.clng,
                "clat": r.clat,
                "town": r.town,
                "official_count": 0,
                "immovable_count": 0,
                "museum_count": 0,
                "historical_area_count": 0,
                "historical_street_count": 0,
            }
        )
    geoms = [geometry_shape(f) for f in features]
    for f, geom in zip(features, geoms):
        source_type = f["properties"]["source_type"]
        for i, pt in enumerate(points):
            if geom.geom_type == "Point":
                covered = abs(pt.x - geom.x) <= 0.0032 and abs(pt.y - geom.y) <= 0.0032
            else:
                covered = geom.contains(pt)
            if not covered:
                continue
            grid_rows[i]["official_count"] += 1
            if source_type == "不可移动文物":
                grid_rows[i]["immovable_count"] += 1
            elif source_type == "博物馆":
                grid_rows[i]["museum_count"] += 1
            elif source_type == "历史文化街区":
                grid_rows[i]["historical_street_count"] += 1
            elif source_type in ["历史文化名镇", "历史文化名村", "传统村落", "特色古村落", "灌溉遗产"]:
                grid_rows[i]["historical_area_count"] += 1
    coverage = pd.DataFrame(grid_rows)
    town = coverage.groupby("town", dropna=False).agg(
        official_grids=("official_count", lambda s: int((s > 0).sum())),
        official_count_sum=("official_count", "sum"),
        immovable_count_sum=("immovable_count", "sum"),
        museum_count_sum=("museum_count", "sum"),
        historical_area_count_sum=("historical_area_count", "sum"),
        historical_street_count_sum=("historical_street_count", "sum"),
    )
    return coverage, town.reset_index()


def minmax(series: pd.Series) -> pd.Series:
    arr = np.asarray(series.fillna(0), dtype=float)
    if arr.max() - arr.min() < 1e-9:
        return pd.Series(np.zeros(len(arr)), index=series.index)
    return pd.Series((arr - arr.min()) / (arr.max() - arr.min()) * 100, index=series.index)


def build_diagnostic(grid: pd.DataFrame, coverage: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = grid.merge(coverage[["ix", "iy", "official_count"]], on=["ix", "iy"], how="left")
    merged["official_count"] = merged["official_count"].fillna(0)
    merged["C_text"] = merged["culture_1hop"].astype(float)
    merged["O_official"] = minmax(np.log1p(merged["official_count"]))
    merged["T_tourism"] = merged["tourism"].astype(float)
    merged["C_main"] = merged["C_text"] * 0.6 + merged["O_official"] * 0.4
    merged["M_revised"] = merged["T_tourism"] - merged["C_main"]

    def label(row) -> str:
        c = row["C_text"] >= 50
        o = row["O_official"] >= 50
        t = row["T_tourism"] >= 50
        if c and o and t:
            return "典籍强-官方强-旅游强"
        if c and o and not t:
            return "文化双强-旅游弱"
        if (not c) and o and not t:
            return "官方强-叙事与旅游弱"
        if c and (not o) and not t:
            return "典籍强-官方与旅游弱"
        if (not c) and (not o) and t:
            return "旅游强-文化解释弱"
        if (not c) and o and t:
            return "官方与旅游强-典籍弱"
        if c and (not o) and t:
            return "典籍与旅游强-官方弱"
        return "三维均弱或一般"

    merged["diagnostic_type"] = merged.apply(label, axis=1)
    town = (
        merged[merged["town"].isin(TOWNS)]
        .groupby("town")
        .agg(
            grid_count=("ix", "count"),
            C_text_mean=("C_text", "mean"),
            O_official_mean=("O_official", "mean"),
            T_tourism_mean=("T_tourism", "mean"),
            M_revised_mean=("M_revised", "mean"),
            official_grids=("official_count", lambda s: int((s > 0).sum())),
        )
        .reset_index()
    )
    town["town"] = pd.Categorical(town["town"], categories=TOWNS, ordered=True)
    town = town.sort_values("town")
    return merged, town


def plot_town_outlines(ax, town_polys: dict[str, Any], label: bool = True) -> None:
    union = unary_union(list(town_polys.values()))
    if union.geom_type == "Polygon":
        xs, ys = union.exterior.coords.xy
        ax.fill(xs, ys, color="#f8fafc", zorder=0)
    else:
        for poly in union.geoms:
            xs, ys = poly.exterior.coords.xy
            ax.fill(xs, ys, color="#f8fafc", zorder=0)
    for name, geom in town_polys.items():
        parts = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for poly in parts:
            xs, ys = poly.exterior.coords.xy
            ax.plot(xs, ys, color="#334155", linewidth=0.8, zorder=4)
        if label:
            p = geom.representative_point()
            ax.text(p.x, p.y, name, ha="center", va="center", fontsize=8.5, weight="bold", color="#0f172a", zorder=5)
    minx, miny, maxx, maxy = union.bounds
    ax.set_xlim(minx - 0.012, maxx + 0.012)
    ax.set_ylim(miny - 0.012, maxy + 0.012)
    ax.set_aspect(1.08)
    ax.tick_params(labelsize=8.5)
    ax.grid(True, alpha=0.12)


def draw_official_map(df: pd.DataFrame, town_polys: dict[str, Any], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 9), constrained_layout=True)
    plot_town_outlines(ax, town_polys)
    for typ, color in TYPE_COLORS.items():
        part = df[df["source_type"] == typ]
        if part.empty:
            continue
        size = 18 if typ == "不可移动文物" else 52
        marker = "o" if typ == "不可移动文物" else "s"
        ax.scatter(part["lng"], part["lat"], s=size, c=color, marker=marker, alpha=0.72, label=f"{typ} ({len(part)})", edgecolors="white", linewidths=0.25, zorder=3)
    ax.set_title("5.10 官方资源扩展空间化结果（484 文物 + 11 博物馆 + 历史文化名录）", fontsize=14, weight="bold")
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    ax.legend(loc="lower left", fontsize=8, framealpha=0.92, ncols=2)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_coverage_map(coverage: pd.DataFrame, town_polys: dict[str, Any], out: Path) -> None:
    active = coverage[coverage["official_count"] > 0].copy()
    fig, ax = plt.subplots(figsize=(10, 9), constrained_layout=True)
    plot_town_outlines(ax, town_polys)
    norm = Normalize(vmin=1, vmax=max(2, float(active["official_count"].quantile(0.98)) if not active.empty else 2))
    patches = []
    half = 0.0045 / 2
    for r in active.itertuples(index=False):
        patches.append(mpatches.Rectangle((r.clng - half, r.clat - half), 0.0045, 0.0045))
    coll = PatchCollection(patches, cmap="viridis", norm=norm, linewidth=0, alpha=0.86, zorder=2)
    if not active.empty:
        coll.set_array(active["official_count"].to_numpy())
    ax.add_collection(coll)
    cbar = fig.colorbar(coll, ax=ax, shrink=0.68, pad=0.02)
    cbar.set_label("网格覆盖的官方资源数量")
    ax.set_title("5.10 官方资源 500 m 网格覆盖强度", fontsize=14, weight="bold")
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_diagnostic(town_diag: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.6, 6.2), constrained_layout=True)
    x = np.arange(len(town_diag))
    width = 0.25
    ax.bar(x - width, town_diag["C_text_mean"], width, color="#2563eb", label="典籍/图谱 C")
    ax.bar(x, town_diag["O_official_mean"], width, color="#7c3aed", label="官方资源 O")
    ax.bar(x + width, town_diag["T_tourism_mean"], width, color="#f97316", label="旅游热度 T")
    ax.set_xticks(x)
    ax.set_xticklabels(town_diag["town"], rotation=25, ha="right")
    ax.set_ylabel("标准化均值")
    ax.set_title("典籍—官方—旅游三维诊断拆分（5.10 官方资源扩展版）", fontsize=14, weight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.18)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_geojson(features: list[dict], path: Path) -> None:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2), encoding="utf-8")


def build_expanded_anchors(existing_anchors: list[dict], official_df: pd.DataFrame, json_path: Path, csv_path: Path) -> None:
    expanded = []
    used_keys = set()
    for idx, anchor in enumerate(existing_anchors, start=1):
        item = dict(anchor)
        item.setdefault("id", f"ANC_EXISTING_{idx:04d}")
        item["anchor_source_20260510"] = "existing_cultural_anchors"
        expanded.append(item)
        used_keys.add(norm_text(item.get("name")))

    added_rows = []
    grouped = defaultdict(list)
    candidates = official_df[official_df["dedup_status"] != "duplicate_existing_anchor"].copy()
    for rec in candidates.to_dict("records"):
        key = norm_text(rec["name"])
        if key in used_keys:
            continue
        grouped[key].append(rec)

    for i, (key, rows) in enumerate(grouped.items(), start=1):
        rows = sorted(rows, key=lambda r: float(r["spatial_confidence"]), reverse=True)
        base = rows[0]
        source_types = sorted(set(r["source_type"] for r in rows))
        levels = sorted(set(str(r["level"]) for r in rows if str(r["level"]) and str(r["level"]) != "nan"))
        item = {
            "id": f"OFF_20260510_{i:04d}",
            "name": base["name"],
            "anchor_type": "官方资源扩展",
            "sub_type": "；".join(source_types),
            "era": base.get("era", ""),
            "protection_level": "；".join(levels),
            "address": base.get("address", ""),
            "town": base.get("town", ""),
            "lng": round(float(base["lng"]), 6),
            "lat": round(float(base["lat"]), 6),
            "coord_source": base["spatial_method"],
            "coord_confidence": round(float(base["spatial_confidence"]), 2),
            "source_record_ids": [r["record_id"] for r in rows],
            "source_types": source_types,
            "anchor_source_20260510": "official_resource_expansion",
        }
        expanded.append(item)
        added_rows.append(item)

    type_stats = Counter(a.get("anchor_type", "") for a in expanded)
    town_stats = Counter(a.get("town", "") for a in expanded)
    out = {
        "total": len(expanded),
        "existing_total": len(existing_anchors),
        "official_added_total": len(added_rows),
        "type_stats": dict(type_stats),
        "town_stats": dict(town_stats),
        "notes": [
            "2026-05-10 official expansion: keeps the original cultural_anchors.json intact and writes an expanded candidate library under docs/tasks/5.10.",
            "Records with duplicate_existing_anchor are not added again; official resources with the same normalized name are merged into one candidate anchor.",
            "Coordinates retain coord_source and coord_confidence; proxy coordinates require manual verification before project implementation.",
        ],
        "anchors": expanded,
    }
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(added_rows).to_csv(csv_path, index=False, encoding="utf-8-sig")


def write_report(summary: dict, table_paths: dict[str, Path], fig_paths: dict[str, Path], out: Path) -> None:
    method_counts = summary["method_counts"]
    dup_counts = summary["dup_counts"]
    type_counts = summary["type_counts"]
    town_counts = summary["town_counts"]
    lines = [
        "# 2026-05-10 官方资源扩展成果包",
        "",
        "本成果包落实 5.10 清单中的五项后续处理：484 处不可移动文物地址空间化与去重、历史文化资源名录的面/线/点分类处理、11 家博物馆补入展示型文化桥梁，以及“典籍—官方—旅游”诊断拆分。",
        "",
        "## 一、输出文件",
        "",
        "| 类型 | 文件 | 说明 |",
        "|---|---|---|",
    ]
    for label, path in table_paths.items():
        lines.append(f"| 表格/数据 | `{path.name}` | {label} |")
    for label, path in fig_paths.items():
        lines.append(f"| 图件 | `figures/{path.name}` | {label} |")
    lines.extend(
        [
            "",
            "## 二、空间化方法",
            "",
            "本轮没有把近似结果写成精确测绘成果，而是为每条资源保留 `spatial_method` 与 `spatial_confidence` 字段。空间化优先级为：现有文化锚点精确命中、POI 名称命中、名称模糊命中、地址片段/村社地名质心、镇街代表点兜底。历史文化名镇使用镇街面；历史文化名村、传统村落、特色古村落使用村社中心缓冲面；历史文化街区使用街区中心缓冲面，作为后续人工数字化前的规划分析代理。",
            "",
            "### 空间化来源统计",
            "",
            "| 方法 | 数量 |",
            "|---|---:|",
        ]
    )
    for key, value in method_counts.items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "### 去重状态", "", "| 状态 | 数量 |", "|---|---:|"])
    for key, value in dup_counts.items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "### 资源类型", "", "| 类型 | 数量 |", "|---|---:|"])
    for key, value in type_counts.items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "### 镇街分布", "", "| 镇街 | 数量 |", "|---|---:|"])
    for key, value in town_counts.items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## 三、图件",
            "",
            "![官方资源空间化结果](figures/official_resources_spatialization_20260510.png)",
            "",
            "![官方资源网格覆盖](figures/official_grid_coverage_20260510.png)",
            "",
            "![三维诊断拆分](figures/diagnostic_split_by_town_20260510.png)",
            "",
        "## 四、论文可用表述",
            "",
            f"5.10 扩展后，官方资源层不再只依赖 165 条已空间化载体，而是把 4.22 补充的 484 处不可移动文物、11 家博物馆和历史文化资源名录纳入统一底表。不可移动文物与博物馆按点状资源处理；历史文化名镇使用镇街面；历史文化名村、传统村落、特色古村落和历史文化街区在缺少官方村域或街区矢量边界时，采用“地名中心 + 缓冲面”的代理表达，并保留空间化方法和置信度字段。本轮另生成扩展锚点库 `{table_paths['扩展文化锚点库 JSON'].name}`，用于后续替换或校验 `cultural_anchors.json`。由此形成“典籍/图谱 C、官方资源 O、旅游热度 T”的三维诊断附表，可用于解释某些区域是典籍叙事不足、官方认定不足，还是旅游转化不足。",
            "",
            "需要在论文中明确：本成果属于规划分析尺度的空间代理结果，不等同于文物测绘坐标或法定保护范围；后续若用于项目落地，应以主管部门公布坐标、保护范围和人工校核边界为准。",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")


def copy_to_mirror(paths: list[Path], mirror_root: Path) -> None:
    for src in paths:
        dst = mirror_root / src.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def append_index(report_path: Path, fig_paths: dict[str, Path]) -> Path:
    index_path = OUT_DIR / "20260510.md"
    text = index_path.read_text(encoding="utf-8")
    marker = "\n## 八、5.10 官方资源扩展成果包\n"
    block = f"""{marker}
本轮已将“七、后续处理清单”转化为可复核成果包。详细说明见 `{report_path.name}`，核心输出包括：

- `official_resources_20260510.csv`：484 处不可移动文物、11 家博物馆、历史文化资源名录统一空间化与去重表；
- `official_resources_20260510.geojson`：点、镇街面和代理缓冲面统一 GeoJSON；
- `cultural_anchors_expanded_20260510.json`：原 220 条锚点 + 去重后的官方新增候选锚点库；
- `official_grid_coverage_20260510.csv`：500 m 网格官方资源覆盖统计；
- `diagnostic_split_by_town_20260510.csv`：典籍/图谱 C、官方资源 O、旅游热度 T 的镇街诊断拆分；
- `figures/official_resources_spatialization_20260510.png`、`figures/official_grid_coverage_20260510.png`、`figures/diagnostic_split_by_town_20260510.png`：论文可用图件。
"""
    if marker in text:
        text = text[: text.index(marker)] + block
    else:
        text = text.rstrip() + "\n" + block
    index_path.write_text(text, encoding="utf-8")
    return index_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 2026-05-10 official-resource expansion outputs.")
    parser.add_argument("--mirror", default="", help="Optional mirror root, e.g. ms_thesis")
    args = parser.parse_args()

    setup_matplotlib()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    names, geoms, tree, town_polys, _ = load_towns()
    anchors, pois = load_points()
    indexes = build_indexes(anchors, pois)

    records = load_immovable() + load_museums() + load_historical_catalog()
    for rec in records:
        geocode_record(rec, indexes, town_polys)
        status, matched = duplicate_status(rec, indexes)
        rec["dedup_status"] = status
        rec["dedup_match"] = matched
        rec["centroid_town"] = which_town(Point(float(rec["lng"]), float(rec["lat"])), names, geoms, tree)
        if rec["town"] == "未标注":
            rec["town"] = rec["centroid_town"]

    df = pd.DataFrame(records)
    df["spatial_confidence"] = df["spatial_confidence"].astype(float)
    df = df[
        [
            "record_id",
            "source_file",
            "source_type",
            "resource_class",
            "sub_class",
            "level",
            "name",
            "era",
            "address",
            "town",
            "target_geometry",
            "lng",
            "lat",
            "spatial_method",
            "spatial_confidence",
            "matched_existing_anchor",
            "matched_poi",
            "dedup_status",
            "dedup_match",
            "centroid_town",
        ]
    ]
    bad_coords = df[~df.apply(lambda r: valid_lnglat(float(r["lng"]), float(r["lat"])), axis=1)]
    if not bad_coords.empty:
        bad_ids = ", ".join(bad_coords["record_id"].astype(str).head(8))
        raise ValueError(f"Invalid coordinates in official resources: {bad_ids}")

    features = [to_feature(rec, town_polys) for rec in df.to_dict("records")]
    grid = pd.read_csv(TABLE_DIR / "grid_indices_kg.csv")
    coverage, town_coverage = add_grid_coverage(features, grid)
    diagnostic_grid, diagnostic_town = build_diagnostic(grid, coverage)

    table_paths = {
        "官方资源统一空间化与去重底表": OUT_DIR / "official_resources_20260510.csv",
        "官方资源 GeoJSON": OUT_DIR / "official_resources_20260510.geojson",
        "官方资源类型/镇街/方法摘要": OUT_DIR / "official_resources_summary_20260510.csv",
        "500 m 网格官方资源覆盖表": OUT_DIR / "official_grid_coverage_20260510.csv",
        "镇街官方资源覆盖摘要": OUT_DIR / "official_town_coverage_20260510.csv",
        "网格三维诊断拆分表": OUT_DIR / "diagnostic_split_grid_20260510.csv",
        "镇街三维诊断拆分表": OUT_DIR / "diagnostic_split_by_town_20260510.csv",
    }
    fig_paths = {
        "官方资源空间化图": FIG_DIR / "official_resources_spatialization_20260510.png",
        "500 m 网格官方资源覆盖图": FIG_DIR / "official_grid_coverage_20260510.png",
        "典籍—官方—旅游诊断拆分图": FIG_DIR / "diagnostic_split_by_town_20260510.png",
    }
    table_paths["扩展文化锚点库 JSON"] = OUT_DIR / "cultural_anchors_expanded_20260510.json"
    table_paths["扩展文化锚点新增项 CSV"] = OUT_DIR / "cultural_anchors_added_20260510.csv"

    df.to_csv(table_paths["官方资源统一空间化与去重底表"], index=False, encoding="utf-8-sig")
    write_geojson(features, table_paths["官方资源 GeoJSON"])
    summary_df = pd.concat(
        [
            df["source_type"].value_counts().rename_axis("item").reset_index(name="count").assign(group="source_type"),
            df["town"].value_counts().rename_axis("item").reset_index(name="count").assign(group="town"),
            df["spatial_method"].value_counts().rename_axis("item").reset_index(name="count").assign(group="spatial_method"),
            df["dedup_status"].value_counts().rename_axis("item").reset_index(name="count").assign(group="dedup_status"),
        ],
        ignore_index=True,
    )
    summary_df[["group", "item", "count"]].to_csv(table_paths["官方资源类型/镇街/方法摘要"], index=False, encoding="utf-8-sig")
    coverage.to_csv(table_paths["500 m 网格官方资源覆盖表"], index=False, encoding="utf-8-sig")
    town_coverage.to_csv(table_paths["镇街官方资源覆盖摘要"], index=False, encoding="utf-8-sig")
    diagnostic_grid.to_csv(table_paths["网格三维诊断拆分表"], index=False, encoding="utf-8-sig")
    diagnostic_town.to_csv(table_paths["镇街三维诊断拆分表"], index=False, encoding="utf-8-sig")
    build_expanded_anchors(
        anchors,
        df,
        table_paths["扩展文化锚点库 JSON"],
        table_paths["扩展文化锚点新增项 CSV"],
    )

    draw_official_map(df, town_polys, fig_paths["官方资源空间化图"])
    draw_coverage_map(coverage, town_polys, fig_paths["500 m 网格官方资源覆盖图"])
    draw_diagnostic(diagnostic_town, fig_paths["典籍—官方—旅游诊断拆分图"])

    report_path = OUT_DIR / "official_resources_20260510.md"
    write_report(
        {
            "method_counts": dict(Counter(df["spatial_method"])),
            "dup_counts": dict(Counter(df["dedup_status"])),
            "type_counts": dict(Counter(df["source_type"])),
            "town_counts": dict(Counter(df["town"])),
        },
        table_paths,
        fig_paths,
        report_path,
    )
    index_path = append_index(report_path, fig_paths)

    outputs = list(table_paths.values()) + list(fig_paths.values()) + [report_path, index_path, Path(__file__).resolve()]
    if args.mirror:
        copy_to_mirror(outputs, (ROOT / args.mirror).resolve())

    print("records", len(df))
    print("tables")
    for p in table_paths.values():
        print(p)
    print("figures")
    for p in fig_paths.values():
        print(p)
    print(report_path)


if __name__ == "__main__":
    main()
