"""以 500 米 × 500 米 网格为单位，计算南海区的文化—旅游三项指标。

动机：
  旧版 build_indices.py 只以 165 条文化载体为样本，样本过少且忽略了 13,512 个 POI
  本身携带的空间分布信息。本脚本把整个南海区切成 500 m 网格，让每一格独立参与
  文化/旅游/错位三项度量，从而把分析样本量从 165 提升到 2,000+ 个有效网格。

三个度量（每一格都会得到一组值）：
  1) 文化厚度 C：格内典籍被提到的总次数 + 格内文化载体的官方认证加权之和，
     先各自取 log(1+x) 压缩，再 Min-Max 归一到 0–100，权重 0.6/0.4 合并。
  2) 旅游热度 T：格内 POI 数、POI 平均评分、POI 周边评论总数，分别归一后
     以 0.45/0.20/0.35 权重合并为 0–100。
  3) 错位 M = T − C，区间 [−100, 100]。
     M < 0：文化厚但旅游冷（沉睡）；M > 0：旅游热但文化薄（空心）。

输入（仅使用仓库既有数据）：
  data/anchors/cultural_anchors.json
  data/entities/entities.json          (含 mentions 字段)
  data/poi/poi_cleaned.json
  data/reviews/review_summary_merged.json
  data/gis/nanhai_boundary.geojson     (南海区外边界，用于区内过滤)
  data/gis/nanhai_towns_real.geojson   (7 个镇街的 OSM 真实行政边界)

输出：
  output/tables/grid_indices.csv          网格级三项指标全表（区内所有网格）
  output/tables/grid_town_summary.csv     按镇街汇总
  output/tables/grid_overview.json        运行摘要
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)


GRID_SIZE_DEG = 0.0045


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def minmax(arr, lo=0.0, hi=100.0):
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return arr
    finite = arr[np.isfinite(arr)]
    if finite.size == 0 or finite.max() - finite.min() < 1e-9:
        return np.full_like(arr, (lo + hi) / 2)
    vmin, vmax = finite.min(), finite.max()
    out = lo + (arr - vmin) / (vmax - vmin) * (hi - lo)
    return np.clip(out, lo, hi)


def oai_weight(anchor: dict) -> float:
    """文化载体的官方认证加权分（累加进文化厚度的第二项原始值）。"""
    lv = (anchor.get("protection_level") or "") + "|" + (anchor.get("anchor_type") or "")
    if any(k in lv for k in ["全国重点", "国家级", "中国历史文化名镇"]):
        return 4.0
    if any(k in lv for k in ["省级", "广东省"]):
        return 3.0
    if "市级" in lv:
        return 2.0
    if "区级" in lv:
        return 1.0
    if "名村" in lv or "文化景观" in lv or "圩市" in lv:
        return 2.0
    return 1.0


def anchor_cmi_raw(name: str, entities: list[dict]) -> float:
    """文化载体在典籍中的总提及数（按名称包含匹配）。"""
    if not name or len(name) < 2:
        return 0.0
    key = name
    for ch in "（）()[]【】 ":
        key = key.replace(ch, "")
    if len(key) < 2:
        return 0.0
    total = 0.0
    for e in entities:
        en = e.get("name", "")
        if not en:
            continue
        if key in en or en in name:
            total += float(e.get("mentions", 0) or 0)
    return total


def grid_of(lng: float, lat: float, lng0: float, lat0: float, step: float) -> tuple[int, int]:
    ix = int((lng - lng0) / step)
    iy = int((lat - lat0) / step)
    return ix, iy


def main():
    print("[1/6] 读取原始数据 ...")
    anchors = load_json(DATA / "anchors" / "cultural_anchors.json")["anchors"]
    # 老版 data/entities/entities.json 已被 merged_entities.json 取代
    ent_path = DATA / "entities" / "entities.json"
    if not ent_path.exists():
        ent_path = DATA / "entities_relations" / "merged_entities.json"
    entities = load_json(ent_path)["entities"]
    pois = load_json(DATA / "poi" / "poi_cleaned.json")["pois"]
    reviews = load_json(DATA / "reviews" / "review_summary_merged.json")
    review_idx = {r.get("name"): r for r in reviews}
    boundary_fc = load_json(DATA / "gis" / "nanhai_boundary.geojson")
    towns_fc = load_json(DATA / "gis" / "nanhai_towns_real.geojson")

    print(f"     anchors={len(anchors)}  entities={len(entities)}  pois={len(pois)}  reviews={len(reviews)}")

    print("[2/6] 构建南海区边界与 7 个镇街真实行政边界 ...")
    boundary_geom = None
    for feat in boundary_fc["features"]:
        g = shape(feat["geometry"])
        boundary_geom = g if boundary_geom is None else boundary_geom.union(g)

    town_geoms = []
    town_names = []
    for feat in towns_fc["features"]:
        town_names.append(feat["properties"].get("name", "未知"))
        town_geoms.append(shape(feat["geometry"]))
    town_tree = STRtree(town_geoms)

    def which_town(pt: Point) -> str:
        cands = town_tree.query(pt)
        for idx in cands:
            if town_geoms[int(idx)].contains(pt):
                return town_names[int(idx)]
        return "未标注"

    print("[3/6] 计算每条文化载体的典籍提及数（耗时最长）...")
    anchor_mentions = []
    for i, a in enumerate(anchors):
        m = anchor_cmi_raw(a.get("name") or "", entities)
        anchor_mentions.append(m)
        if (i + 1) % 50 == 0:
            print(f"     已处理 {i + 1}/{len(anchors)} 条载体")

    print("[4/6] 切网格并把点落格 ...")
    minx, miny, maxx, maxy = boundary_geom.bounds
    lng0 = math.floor(minx * 1000) / 1000
    lat0 = math.floor(miny * 1000) / 1000
    lng1 = math.ceil(maxx * 1000) / 1000
    lat1 = math.ceil(maxy * 1000) / 1000
    step = GRID_SIZE_DEG
    nx = int(math.ceil((lng1 - lng0) / step))
    ny = int(math.ceil((lat1 - lat0) / step))
    print(f"     网格起点 ({lng0:.3f}, {lat0:.3f}) 尺寸 {nx} × {ny} = {nx * ny} 格（外包框）")

    grids: dict[tuple[int, int], dict] = defaultdict(lambda: {
        "anchor_count": 0,
        "anchor_names": [],
        "mentions_sum": 0.0,
        "oai_sum": 0.0,
        "poi_count": 0,
        "rating_sum": 0.0,
        "rating_n": 0,
        "review_total": 0,
    })

    for a, m in zip(anchors, anchor_mentions):
        lng, lat = a.get("lng"), a.get("lat")
        if lng is None or lat is None:
            continue
        try:
            lngf, latf = float(lng), float(lat)
        except Exception:
            continue
        if not (math.isfinite(lngf) and math.isfinite(latf)):
            continue
        if not (lng0 <= lngf <= lng1 and lat0 <= latf <= lat1):
            continue
        ix, iy = grid_of(lngf, latf, lng0, lat0, step)
        g = grids[(ix, iy)]
        g["anchor_count"] += 1
        if len(g["anchor_names"]) < 6:
            g["anchor_names"].append(a.get("name") or "")
        g["mentions_sum"] += m
        g["oai_sum"] += oai_weight(a)

    for p in pois:
        lng, lat = p.get("lng"), p.get("lat")
        if lng is None or lat is None:
            continue
        try:
            lngf, latf = float(lng), float(lat)
        except Exception:
            continue
        if not (math.isfinite(lngf) and math.isfinite(latf)):
            continue
        if not (lng0 <= lngf <= lng1 and lat0 <= latf <= lat1):
            continue
        ix, iy = grid_of(lngf, latf, lng0, lat0, step)
        g = grids[(ix, iy)]
        g["poi_count"] += 1
        r = p.get("rating")
        try:
            rf = float(r) if r not in (None, "") else 0.0
        except Exception:
            rf = 0.0
        if rf > 0:
            g["rating_sum"] += rf
            g["rating_n"] += 1
        rv = review_idx.get(p.get("name", ""))
        if rv:
            g["review_total"] += int(rv.get("total_count", 0) or 0)

    print(f"     有点网格 {len(grids)} 个（仅此类格的 C/T 可能 > 0）")

    print("[5/6] 枚举区内所有网格并计算三项指标 ...")
    empty_tpl = {
        "anchor_count": 0, "anchor_names": [], "mentions_sum": 0.0,
        "oai_sum": 0.0, "poi_count": 0, "rating_sum": 0.0,
        "rating_n": 0, "review_total": 0,
    }

    cells = []
    for ix in range(nx):
        for iy in range(ny):
            clng = lng0 + (ix + 0.5) * step
            clat = lat0 + (iy + 0.5) * step
            pt = Point(clng, clat)
            if not boundary_geom.contains(pt):
                continue
            g = grids.get((ix, iy), empty_tpl)
            town = which_town(pt)
            cells.append({
                "ix": ix,
                "iy": iy,
                "clng": round(clng, 6),
                "clat": round(clat, 6),
                "town": town,
                "anchor_count": g["anchor_count"],
                "anchor_names": "|".join(g["anchor_names"]) if g["anchor_names"] else "",
                "mentions_sum": g["mentions_sum"],
                "oai_sum": g["oai_sum"],
                "poi_count": g["poi_count"],
                "avg_rating": round(g["rating_sum"] / g["rating_n"], 2) if g["rating_n"] else 0.0,
                "review_total": g["review_total"],
            })

    n_with_anchor = sum(1 for c in cells if c["anchor_count"] > 0)
    n_with_poi = sum(1 for c in cells if c["poi_count"] > 0)
    print(f"     区内网格共 {len(cells)} 个；含载体 {n_with_anchor} 个；含 POI {n_with_poi} 个")

    m_log = np.array([math.log1p(c["mentions_sum"]) for c in cells])
    oai_log = np.array([math.log1p(c["oai_sum"]) for c in cells])
    poi_log = np.array([math.log1p(c["poi_count"]) for c in cells])
    rating_arr = np.array([c["avg_rating"] for c in cells])
    rev_log = np.array([math.log1p(c["review_total"]) for c in cells])

    c_part1 = minmax(m_log)
    c_part2 = minmax(oai_log)
    C = 0.6 * c_part1 + 0.4 * c_part2

    t_part1 = minmax(poi_log)
    t_part2 = minmax(rating_arr)
    t_part3 = minmax(rev_log)
    T = 0.45 * t_part1 + 0.20 * t_part2 + 0.35 * t_part3

    M = T - C

    for i, c in enumerate(cells):
        c["culture"] = round(float(C[i]), 2)
        c["tourism"] = round(float(T[i]), 2)
        c["mismatch"] = round(float(M[i]), 2)

    def label_of(culture, tourism, mismatch):
        if culture >= 50 and tourism >= 50:
            return "核心耦合"
        if culture >= 50:
            return "沉睡潜力"
        if tourism >= 50:
            return "空心景点"
        if culture < 25 and tourism < 25:
            return "双低空白"
        return "一般地带"

    for c in cells:
        c["category"] = label_of(c["culture"], c["tourism"], c["mismatch"])

    print("[6/6] 写出结果文件 ...")
    headers = [
        "ix", "iy", "clng", "clat", "town",
        "anchor_count", "anchor_names", "mentions_sum", "oai_sum",
        "poi_count", "avg_rating", "review_total",
        "culture", "tourism", "mismatch", "category",
    ]
    with (OUT / "grid_indices.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for c in cells:
            w.writerow({h: c.get(h, "") for h in headers})

    town_agg = defaultdict(lambda: {
        "grid_count": 0, "c_sum": 0.0, "t_sum": 0.0, "m_sum": 0.0,
        "poi_sum": 0, "anchor_sum": 0, "mentions_sum": 0.0,
        "cat_count": defaultdict(int),
    })
    for c in cells:
        t = c["town"]
        ta = town_agg[t]
        ta["grid_count"] += 1
        ta["c_sum"] += c["culture"]
        ta["t_sum"] += c["tourism"]
        ta["m_sum"] += c["mismatch"]
        ta["poi_sum"] += c["poi_count"]
        ta["anchor_sum"] += c["anchor_count"]
        ta["mentions_sum"] += c["mentions_sum"]
        ta["cat_count"][c["category"]] += 1

    town_rows = []
    for t, s in town_agg.items():
        n = s["grid_count"]
        town_rows.append({
            "town": t,
            "grid_count": n,
            "anchor_total": s["anchor_sum"],
            "poi_total": s["poi_sum"],
            "mentions_total": int(s["mentions_sum"]),
            "culture_mean": round(s["c_sum"] / n, 2) if n else 0,
            "tourism_mean": round(s["t_sum"] / n, 2) if n else 0,
            "mismatch_mean": round(s["m_sum"] / n, 2) if n else 0,
            "n_dormant": s["cat_count"].get("沉睡潜力", 0),
            "n_hollow": s["cat_count"].get("空心景点", 0),
            "n_core": s["cat_count"].get("核心耦合", 0),
        })
    town_rows.sort(key=lambda x: -x["grid_count"])
    with (OUT / "grid_town_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(town_rows[0].keys()))
        w.writeheader()
        w.writerows(town_rows)

    cat_count = defaultdict(int)
    for c in cells:
        cat_count[c["category"]] += 1

    dormant_top = sorted([c for c in cells if c["category"] == "沉睡潜力"],
                          key=lambda x: x["mismatch"])[:10]
    hollow_top = sorted([c for c in cells if c["category"] == "空心景点"],
                         key=lambda x: -x["mismatch"])[:10]

    def pct(arr, qs=(0, 25, 50, 75, 100)):
        return {f"p{q}": round(float(np.percentile(arr, q)), 2) for q in qs}

    def brief(c):
        return {k: c[k] for k in ["ix", "iy", "town", "anchor_count", "poi_count",
                                      "culture", "tourism", "mismatch"]} | \
               {"anchor_names": c["anchor_names"]}

    overview = {
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "grid_size_m": 500,
        "n_cells_total": len(cells),
        "n_cells_with_anchor": n_with_anchor,
        "n_cells_with_poi": n_with_poi,
        "weights": {
            "culture": {"mentions_log1p": 0.6, "oai_log1p": 0.4},
            "tourism": {"poi_count_log1p": 0.45, "avg_rating": 0.20, "review_total_log1p": 0.35},
        },
        "thresholds": {
            "core_coupling": "culture>=50 AND tourism>=50 AND |M|<=15",
            "dormant_potential": "culture>=50 AND M<-15",
            "hollow_attraction": "tourism>=50 AND M>15",
            "double_low_blank": "culture<25 AND tourism<25",
            "general": "其余情形",
        },
        "culture_quantiles": pct([c["culture"] for c in cells]),
        "tourism_quantiles": pct([c["tourism"] for c in cells]),
        "mismatch_quantiles": pct([c["mismatch"] for c in cells]),
        "category_counts": dict(cat_count),
        "dormant_top10": [brief(c) for c in dormant_top],
        "hollow_top10": [brief(c) for c in hollow_top],
    }
    with (OUT / "grid_overview.json").open("w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)

    print("\n========= 汇总 =========")
    print(f"区内网格数: {len(cells)}")
    print(f"含文化载体: {n_with_anchor}")
    print(f"含 POI:     {n_with_poi}")
    print(f"分层计数:   {dict(cat_count)}")
    print("已生成：grid_indices.csv, grid_town_summary.csv, grid_overview.json")


if __name__ == "__main__":
    main()
