"""基于知识图谱的 0 跳 / 1 跳口径重算文化厚度 C 与错位值 M。

与 grid_indices.py 的关键差异：
  旧版 C 只以"anchor 名字在旧 entities.json 中的 mentions"为依据，未利用
  merged_relations.json 的关系图。本脚本改用：

    每格 i 的种子实体集合 S0(i) = 
        { entity | 某 anchor 落在 i 且 anchor 匹配到 entity }
      ∪ { entity | 某 POI 落在 i 且该 POI 通过 cultural_anchors 链到 anchor，anchor 再匹到 entity }

    S1(i) = S0(i) ∪ N(S0(i))       N 为 merged_relations.json 的无向邻接算子

  C_0hop(i) 由 S0(i) 的 Σmentions 与 Σofficial_flag 合并；
  C_1hop(i) 由 S1(i) 的 Σmentions 与 Σofficial_flag 合并；
  T 与 grid_indices.py 完全一致，不重复实现。

输出：
  output/tables/grid_indices_kg.csv     每个区内网格的 C_0hop / C_1hop / T / M_0hop / M_1hop
  output/tables/grid_town_summary_kg.csv 按镇街汇总
  output/tables/grid_overview_kg.json    总览
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
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


STOP_WORDS = {
    "清代", "明代", "民国", "宋代", "元代", "唐代", "汉代", "当代",
    "南海", "南海县", "南海区", "广东", "广东省", "佛山", "佛山市",
    "文物", "非遗", "建筑", "村落", "古村", "遗址", "庙宇",
}


def build_anchor_to_entities(anchors, ent_names_set):
    """与 poi_entity_linkage.py 完全一致的包含式匹配。"""
    mapping: dict[str, set[str]] = {}
    for a in anchors:
        name = a["name"]
        hits: set[str] = set()
        if name in ent_names_set:
            hits.add(name)
        else:
            for ename in ent_names_set:
                if len(ename) < 2 or len(name) < 2:
                    continue
                if ename in name and len(ename) >= 2:
                    hits.add(ename)
                elif name in ename and len(name) >= 3:
                    hits.add(ename)
            hits = {h for h in hits if len(h) >= 2 and h not in STOP_WORDS}
        mapping[name] = hits
    return mapping


def build_graph(relations):
    g: dict[str, set[str]] = defaultdict(set)
    for r in relations:
        s, t = r.get("source"), r.get("target")
        if not s or not t or s == t:
            continue
        g[s].add(t)
        g[t].add(s)
    return g


def one_hop_expand(seeds: set[str], graph) -> set[str]:
    out = set(seeds)
    for v in seeds:
        out |= graph.get(v, set())
    return out


def grid_of(lng: float, lat: float, lng0: float, lat0: float, step: float):
    return int((lng - lng0) / step), int((lat - lat0) / step)


def main():
    print("[1/7] 读取数据 ...")
    anchors = load_json(DATA / "anchors" / "cultural_anchors.json")["anchors"]
    pois = load_json(DATA / "poi" / "poi_cleaned.json")["pois"]
    reviews = load_json(DATA / "reviews" / "review_summary_merged.json")
    review_idx = {r.get("name"): r for r in reviews}
    entities = load_json(DATA / "entities_relations" / "merged_entities.json")["entities"]
    relations = load_json(DATA / "entities_relations" / "merged_relations.json")["relations"]
    boundary_fc = load_json(DATA / "gis" / "nanhai_boundary.geojson")
    towns_fc = load_json(DATA / "gis" / "nanhai_towns_real.geojson")

    ent_by_name = {e["name"]: e for e in entities}
    ent_names_set = set(ent_by_name.keys())

    print(f"     anchors={len(anchors)}  pois={len(pois)}  entities={len(entities)}  relations={len(relations)}")

    print("[2/7] 构建 anchor -> entity 映射 + 关系邻接图 ...")
    a2e = build_anchor_to_entities(anchors, ent_names_set)
    hit = sum(1 for v in a2e.values() if v)
    print(f"     {hit}/{len(anchors)} anchor 匹到 entity（与 poi_entity_linkage 一致）")
    graph = build_graph(relations)
    print(f"     关系图节点 {len(graph)}")

    print("[3/7] 读入边界几何 ...")
    boundary_geom = None
    for feat in boundary_fc["features"]:
        g = shape(feat["geometry"])
        boundary_geom = g if boundary_geom is None else boundary_geom.union(g)
    town_names = [f["properties"].get("name", "未知") for f in towns_fc["features"]]
    town_geoms = [shape(f["geometry"]) for f in towns_fc["features"]]
    town_tree = STRtree(town_geoms)

    def which_town(pt: Point) -> str:
        cands = town_tree.query(pt)
        for idx in cands:
            if town_geoms[int(idx)].contains(pt):
                return town_names[int(idx)]
        return "未标注"

    print("[4/7] 枚举网格外包框 ...")
    minx, miny, maxx, maxy = boundary_geom.bounds
    lng0 = math.floor(minx * 1000) / 1000
    lat0 = math.floor(miny * 1000) / 1000
    lng1 = math.ceil(maxx * 1000) / 1000
    lat1 = math.ceil(maxy * 1000) / 1000
    step = GRID_SIZE_DEG
    nx = int(math.ceil((lng1 - lng0) / step))
    ny = int(math.ceil((lat1 - lat0) / step))
    print(f"     网格起点 ({lng0:.3f}, {lat0:.3f}) 尺寸 {nx} × {ny}")

    print("[5/7] 把 anchor / POI 落格并累计种子 entity 集合 ...")
    grids: dict[tuple[int, int], dict] = defaultdict(lambda: {
        "anchor_count": 0,
        "anchor_names": [],
        "seed_entities": set(),
        "poi_count": 0,
        "rating_sum": 0.0,
        "rating_n": 0,
        "review_total": 0,
    })

    for a in anchors:
        lng, lat = a.get("lng"), a.get("lat")
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
        g["seed_entities"] |= a2e.get(a.get("name", ""), set())

    for p in pois:
        lng, lat = p.get("lng"), p.get("lat")
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
        for tag in p.get("cultural_anchors") or []:
            g["seed_entities"] |= a2e.get(tag, set())
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

    print(f"     有点网格 {len(grids)} 个")

    print("[6/7] 对每格做 1 跳扩展 + 聚合 mentions / official ...")

    def agg(names: set[str]):
        mentions = 0
        official = 0
        for n in names:
            e = ent_by_name.get(n)
            if not e:
                continue
            mentions += int(e.get("mentions", 0) or 0)
            if e.get("official_label"):
                official += 1
        return mentions, official

    empty_tpl = {
        "anchor_count": 0, "anchor_names": [], "seed_entities": set(),
        "poi_count": 0, "rating_sum": 0.0, "rating_n": 0, "review_total": 0,
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
            S0 = g["seed_entities"]
            S1 = one_hop_expand(S0, graph)
            m0, o0 = agg(S0)
            m1, o1 = agg(S1)
            cells.append({
                "ix": ix, "iy": iy,
                "clng": round(clng, 6), "clat": round(clat, 6),
                "town": town,
                "anchor_count": g["anchor_count"],
                "anchor_names": "|".join(g["anchor_names"]),
                "n_entity_0hop": len(S0),
                "n_entity_1hop": len(S1),
                "mentions_0hop": m0,
                "mentions_1hop": m1,
                "official_0hop": o0,
                "official_1hop": o1,
                "poi_count": g["poi_count"],
                "avg_rating": round(g["rating_sum"] / g["rating_n"], 2) if g["rating_n"] else 0.0,
                "review_total": g["review_total"],
            })

    n_with_seed = sum(1 for c in cells if c["n_entity_0hop"] > 0)
    n_with_1hop = sum(1 for c in cells if c["n_entity_1hop"] > 0)
    print(f"     区内网格 {len(cells)}，含 0 跳种子 {n_with_seed}，含 1 跳实体 {n_with_1hop}")

    m0_log = np.array([math.log1p(c["mentions_0hop"]) for c in cells])
    m1_log = np.array([math.log1p(c["mentions_1hop"]) for c in cells])
    o0_log = np.array([math.log1p(c["official_0hop"]) for c in cells])
    o1_log = np.array([math.log1p(c["official_1hop"]) for c in cells])
    poi_log = np.array([math.log1p(c["poi_count"]) for c in cells])
    rating_arr = np.array([c["avg_rating"] for c in cells])
    rev_log = np.array([math.log1p(c["review_total"]) for c in cells])

    C0 = 0.6 * minmax(m0_log) + 0.4 * minmax(o0_log)
    C1 = 0.6 * minmax(m1_log) + 0.4 * minmax(o1_log)
    T = 0.45 * minmax(poi_log) + 0.20 * minmax(rating_arr) + 0.35 * minmax(rev_log)
    M0 = T - C0
    M1 = T - C1

    def label_of(culture, tourism, mismatch):
        # 双高即耦合（去掉 |M|<=15 的强平衡约束）
        if culture >= 50 and tourism >= 50:
            return "核心耦合"
        if culture >= 50:
            return "沉睡潜力"
        if tourism >= 50:
            return "空心景点"
        if culture < 25 and tourism < 25:
            return "双低空白"
        return "一般地带"

    for i, c in enumerate(cells):
        c["culture_0hop"] = round(float(C0[i]), 2)
        c["culture_1hop"] = round(float(C1[i]), 2)
        c["tourism"] = round(float(T[i]), 2)
        c["mismatch_0hop"] = round(float(M0[i]), 2)
        c["mismatch_1hop"] = round(float(M1[i]), 2)
        c["category_0hop"] = label_of(c["culture_0hop"], c["tourism"], c["mismatch_0hop"])
        c["category_1hop"] = label_of(c["culture_1hop"], c["tourism"], c["mismatch_1hop"])

    print("[7/7] 写出结果 ...")
    headers = [
        "ix", "iy", "clng", "clat", "town",
        "anchor_count", "anchor_names",
        "n_entity_0hop", "n_entity_1hop",
        "mentions_0hop", "mentions_1hop",
        "official_0hop", "official_1hop",
        "poi_count", "avg_rating", "review_total",
        "culture_0hop", "culture_1hop", "tourism",
        "mismatch_0hop", "mismatch_1hop",
        "category_0hop", "category_1hop",
    ]
    with (OUT / "grid_indices_kg.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for c in cells:
            w.writerow({h: c.get(h, "") for h in headers})

    town_agg: dict[str, dict] = defaultdict(lambda: {
        "grid_count": 0,
        "c0_sum": 0.0, "c1_sum": 0.0, "t_sum": 0.0,
        "m0_sum": 0.0, "m1_sum": 0.0,
        "poi_sum": 0, "anchor_sum": 0,
        "cat0": Counter(), "cat1": Counter(),
    })
    for c in cells:
        t = c["town"]
        ta = town_agg[t]
        ta["grid_count"] += 1
        ta["c0_sum"] += c["culture_0hop"]
        ta["c1_sum"] += c["culture_1hop"]
        ta["t_sum"] += c["tourism"]
        ta["m0_sum"] += c["mismatch_0hop"]
        ta["m1_sum"] += c["mismatch_1hop"]
        ta["poi_sum"] += c["poi_count"]
        ta["anchor_sum"] += c["anchor_count"]
        ta["cat0"][c["category_0hop"]] += 1
        ta["cat1"][c["category_1hop"]] += 1

    town_rows = []
    for t, s in town_agg.items():
        n = s["grid_count"]
        town_rows.append({
            "town": t,
            "grid_count": n,
            "anchor_total": s["anchor_sum"],
            "poi_total": s["poi_sum"],
            "culture_0hop_mean": round(s["c0_sum"] / n, 2) if n else 0,
            "culture_1hop_mean": round(s["c1_sum"] / n, 2) if n else 0,
            "tourism_mean": round(s["t_sum"] / n, 2) if n else 0,
            "mismatch_0hop_mean": round(s["m0_sum"] / n, 2) if n else 0,
            "mismatch_1hop_mean": round(s["m1_sum"] / n, 2) if n else 0,
            "n_dormant_0hop": s["cat0"].get("沉睡潜力", 0),
            "n_hollow_0hop": s["cat0"].get("空心景点", 0),
            "n_core_0hop": s["cat0"].get("核心耦合", 0),
            "n_dormant_1hop": s["cat1"].get("沉睡潜力", 0),
            "n_hollow_1hop": s["cat1"].get("空心景点", 0),
            "n_core_1hop": s["cat1"].get("核心耦合", 0),
        })
    town_rows.sort(key=lambda x: -x["grid_count"])
    with (OUT / "grid_town_summary_kg.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(town_rows[0].keys()))
        w.writeheader()
        w.writerows(town_rows)

    cat0_cnt = Counter(c["category_0hop"] for c in cells)
    cat1_cnt = Counter(c["category_1hop"] for c in cells)

    def pct(arr, qs=(0, 25, 50, 75, 100)):
        return {f"p{q}": round(float(np.percentile(arr, q)), 2) for q in qs}

    overview = {
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "grid_size_m": 500,
        "n_cells_total": len(cells),
        "n_cells_with_0hop_seed": n_with_seed,
        "n_cells_with_1hop_entity": n_with_1hop,
        "weights": {
            "culture": {"mentions_log1p": 0.6, "official_log1p": 0.4},
            "tourism": {"poi_count_log1p": 0.45, "avg_rating": 0.20, "review_total_log1p": 0.35},
        },
        "anchor_to_entity_hits": hit,
        "quantiles": {
            "culture_0hop": pct([c["culture_0hop"] for c in cells]),
            "culture_1hop": pct([c["culture_1hop"] for c in cells]),
            "tourism": pct([c["tourism"] for c in cells]),
            "mismatch_0hop": pct([c["mismatch_0hop"] for c in cells]),
            "mismatch_1hop": pct([c["mismatch_1hop"] for c in cells]),
        },
        "category_counts_0hop": dict(cat0_cnt),
        "category_counts_1hop": dict(cat1_cnt),
    }
    with (OUT / "grid_overview_kg.json").open("w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)

    print("\n========= 汇总 =========")
    print(f"区内网格: {len(cells)}")
    print(f"0 跳有种子: {n_with_seed}   1 跳内可达: {n_with_1hop}")
    print(f"分层 (0 跳): {dict(cat0_cnt)}")
    print(f"分层 (1 跳): {dict(cat1_cnt)}")
    print("已写入 grid_indices_kg.csv / grid_town_summary_kg.csv / grid_overview_kg.json")


if __name__ == "__main__":
    main()
