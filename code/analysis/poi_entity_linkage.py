"""把 POI 与文化实体四层数据串起来，并输出 0 跳 / 1 跳 / 2 跳的统计。

数据链：
  POI -- cultural_anchors 字段 --> cultural_anchors.json 中的 anchor
  anchor -- 名字包含式匹配 --> merged_entities.json 中的 entity（种子节点 E0）
  entity -- merged_relations.json 构图 --> 一跳邻居 E1、二跳邻居 E2

对每个 POI 计算：
  - n_seed         : 通过 anchor 找到的种子 entity 数
  - n_hop1         : 一跳邻居 (新增) 数
  - n_hop2         : 二跳邻居 (新增) 数
  - mentions_*     : 各层实体在典籍中的 mentions 加总
  - official_*     : 各层实体中带 official_label 的计数

聚合到 500 m 网格与 7 个 OSM 镇街，产出：
  output/tables/poi_entity_linkage.csv
  output/tables/grid_entity_linkage.csv
  output/tables/town_entity_linkage.csv
  output/tables/poi_entity_linkage_overview.json
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path

try:
    from shapely.geometry import Point, shape
except Exception as e:
    raise SystemExit("shapely required") from e

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "output" / "tables"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GRID_DEG = 0.0045
BBOX = (112.82, 22.78, 113.27, 23.23)


def load(p):
    return json.load(open(ROOT / p, encoding="utf-8"))


def build_anchor_to_entities(anchors, entities):
    """对每个 anchor 名字 a，返回匹配到的 entity 名字集合。

    规则：先精确匹配；若无，再用"包含式匹配"：entity.name 是 anchor.name 的子串
    且长度 >= 2，或 anchor.name 是 entity.name 的子串且长度 >= 3。优先保留较短
    的 entity 名字（主题词），避免"九江双蒸酒制作技艺"同时匹到几十个不相关实体。
    """
    ent_names = {e["name"] for e in entities}
    mapping: dict[str, set[str]] = {}
    for a in anchors:
        name = a["name"]
        hits: set[str] = set()
        if name in ent_names:
            hits.add(name)
        else:
            for ename in ent_names:
                if len(ename) < 2 or len(name) < 2:
                    continue
                if ename in name and len(ename) >= 2:
                    hits.add(ename)
                elif name in ename and len(name) >= 3:
                    hits.add(ename)
            hits = {h for h in hits if len(h) >= 2 and h not in {
                "清代", "明代", "民国", "宋代", "元代", "唐代", "汉代", "当代",
                "南海", "南海县", "南海区", "广东", "广东省", "佛山", "佛山市",
                "文物", "非遗", "建筑", "村落", "古村", "遗址", "庙宇",
            }}
        mapping[name] = hits
    return mapping


def build_neighbor_graph(relations):
    """构建无向邻接表：name -> set(neighbor_name)。"""
    g: dict[str, set[str]] = defaultdict(set)
    for r in relations:
        s, t = r.get("source"), r.get("target")
        if not s or not t or s == t:
            continue
        g[s].add(t)
        g[t].add(s)
    return g


def multi_hop(seeds: set[str], graph, max_hop: int = 2) -> list[set[str]]:
    """返回长度 max_hop + 1 的列表，levels[k] 是"首次在第 k 跳被访问"的节点集合。

    levels[0] = seeds; levels[1] = seeds 的邻居（扣除 seeds）; levels[2] = levels[1] 的
    邻居（扣除 seeds ∪ levels[1]）。
    """
    levels = [set(seeds)]
    visited = set(seeds)
    frontier = set(seeds)
    for _ in range(max_hop):
        next_frontier: set[str] = set()
        for v in frontier:
            for u in graph.get(v, ()):
                if u not in visited:
                    next_frontier.add(u)
        levels.append(next_frontier)
        visited |= next_frontier
        frontier = next_frontier
    return levels


def in_bbox(lng, lat):
    if lng is None or lat is None:
        return False
    if not (math.isfinite(lng) and math.isfinite(lat)):
        return False
    return BBOX[0] <= lng <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]


def grid_key(lng, lat):
    ix = int((lng - BBOX[0]) / GRID_DEG)
    iy = int((lat - BBOX[1]) / GRID_DEG)
    return ix, iy


def load_town_polys():
    gj = load("data/gis/nanhai_towns_real.geojson")
    polys = []
    for ft in gj["features"]:
        polys.append((ft["properties"]["name"], shape(ft["geometry"])))
    return polys


def which_town(pt, polys):
    for name, g in polys:
        if g.contains(pt):
            return name
    return "未标注"


def main():
    print("[1/6] 读取数据 ...")
    poi = load("data/poi/poi_cleaned.json")["pois"]
    anchors = load("data/anchors/cultural_anchors.json")["anchors"]
    entities = load("data/entities_relations/merged_entities.json")["entities"]
    relations = load("data/entities_relations/merged_relations.json")["relations"]

    ent_by_name = {e["name"]: e for e in entities}

    print("[2/6] 构建 anchor -> entity 包含式匹配 ...")
    a2e = build_anchor_to_entities(anchors, entities)
    hit = sum(1 for v in a2e.values() if v)
    total_ent_linked = sum(len(v) for v in a2e.values())
    print(f"   {hit}/{len(anchors)} anchor 匹配到至少 1 个 entity，合计 {total_ent_linked} 条 anchor-entity 映射")

    print("[3/6] 构建实体关系邻接图 ...")
    graph = build_neighbor_graph(relations)
    print(f"   图节点 {len(graph)}, 平均度 {sum(len(v) for v in graph.values())/max(1,len(graph)):.2f}")

    print("[4/6] 对每个 POI 计算 0/1/2 跳实体集合 ...")
    towns = load_town_polys()

    def layer_stats(names: set[str]) -> dict:
        mentions = 0
        official = 0
        anchor_flag = 0
        layer_cnt: Counter = Counter()
        label_cnt: Counter = Counter()
        for n in names:
            e = ent_by_name.get(n)
            if not e:
                continue
            mentions += int(e.get("mentions", 0) or 0)
            if e.get("official_label"):
                official += 1
            if e.get("is_anchor"):
                anchor_flag += 1
            if e.get("ai_layer"):
                layer_cnt[e["ai_layer"]] += 1
            if e.get("ai_grade_label"):
                label_cnt[e["ai_grade_label"]] += 1
        return {
            "n": len(names),
            "mentions": mentions,
            "official": official,
            "anchor": anchor_flag,
            "by_layer": dict(layer_cnt),
            "by_label": dict(label_cnt),
        }

    poi_rows = []
    grid_acc: dict = defaultdict(lambda: {
        "e0": set(), "e1": set(), "e2": set(),
        "poi_count": 0, "poi_with_seed": 0,
        "clng_sum": 0.0, "clat_sum": 0.0,
    })
    town_acc: dict = defaultdict(lambda: {
        "e0": set(), "e1": set(), "e2": set(),
        "poi_count": 0, "poi_with_seed": 0,
    })

    for p in poi:
        lng, lat = p.get("lng"), p.get("lat")
        if not in_bbox(lng, lat):
            continue
        tags = p.get("cultural_anchors") or []
        seeds: set[str] = set()
        for t in tags:
            seeds |= a2e.get(t, set())
        levels = multi_hop(seeds, graph, max_hop=2)
        e0 = levels[0]
        e1_new = levels[1] if len(levels) > 1 else set()
        e2_new = levels[2] if len(levels) > 2 else set()
        e1_all = e0 | e1_new
        e2_all = e1_all | e2_new

        s0 = layer_stats(e0)
        s1_new = layer_stats(e1_new)
        s2_new = layer_stats(e2_new)

        poi_rows.append({
            "poi_id": p.get("id", ""),
            "poi_name": p.get("name", ""),
            "town": p.get("town", ""),
            "lng": lng, "lat": lat,
            "n_anchor_tag": len(tags),
            "n_seed_entity": s0["n"],
            "n_hop1_new": s1_new["n"],
            "n_hop2_new": s2_new["n"],
            "mentions_0": s0["mentions"],
            "mentions_1_new": s1_new["mentions"],
            "mentions_2_new": s2_new["mentions"],
            "official_0": s0["official"],
            "official_1_new": s1_new["official"],
            "official_2_new": s2_new["official"],
        })

        # grid
        ix, iy = grid_key(lng, lat)
        clng = BBOX[0] + (ix + 0.5) * GRID_DEG
        clat = BBOX[1] + (iy + 0.5) * GRID_DEG
        pt = Point(clng, clat)
        town = which_town(pt, towns)
        g_acc = grid_acc[(ix, iy, town)]
        g_acc["e0"] |= e0
        g_acc["e1"] |= e1_all
        g_acc["e2"] |= e2_all
        g_acc["poi_count"] += 1
        if s0["n"] > 0:
            g_acc["poi_with_seed"] += 1
        g_acc["clng_sum"] += clng
        g_acc["clat_sum"] += clat

        t_acc = town_acc[town]
        t_acc["e0"] |= e0
        t_acc["e1"] |= e1_all
        t_acc["e2"] |= e2_all
        t_acc["poi_count"] += 1
        if s0["n"] > 0:
            t_acc["poi_with_seed"] += 1

    print(f"   扫描落入 bbox 的 POI: {len(poi_rows)}")

    print("[5/6] 写入 POI / 网格 / 镇街三张表 ...")
    with (OUT_DIR / "poi_entity_linkage.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(poi_rows[0].keys()))
        w.writeheader()
        w.writerows(poi_rows)

    grid_rows = []
    for (ix, iy, town), v in grid_acc.items():
        s0 = layer_stats(v["e0"])
        s1 = layer_stats(v["e1"])
        s2 = layer_stats(v["e2"])
        n = v["poi_count"]
        grid_rows.append({
            "ix": ix, "iy": iy, "town": town,
            "clng": round(v["clng_sum"] / n, 6),
            "clat": round(v["clat_sum"] / n, 6),
            "poi_count": n,
            "poi_with_seed": v["poi_with_seed"],
            "n_entity_0hop": s0["n"],
            "n_entity_within_1hop": s1["n"],
            "n_entity_within_2hop": s2["n"],
            "mentions_0hop": s0["mentions"],
            "mentions_within_1hop": s1["mentions"],
            "mentions_within_2hop": s2["mentions"],
            "official_0hop": s0["official"],
            "official_within_1hop": s1["official"],
            "official_within_2hop": s2["official"],
        })
    grid_rows.sort(key=lambda r: (r["town"], -r["n_entity_within_2hop"]))
    with (OUT_DIR / "grid_entity_linkage.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(grid_rows[0].keys()))
        w.writeheader()
        w.writerows(grid_rows)

    town_rows = []
    for town, v in town_acc.items():
        s0 = layer_stats(v["e0"])
        s1 = layer_stats(v["e1"])
        s2 = layer_stats(v["e2"])
        town_rows.append({
            "town": town,
            "poi_count": v["poi_count"],
            "poi_with_seed": v["poi_with_seed"],
            "n_entity_0hop": s0["n"],
            "n_entity_within_1hop": s1["n"],
            "n_entity_within_2hop": s2["n"],
            "mentions_0hop": s0["mentions"],
            "mentions_within_1hop": s1["mentions"],
            "mentions_within_2hop": s2["mentions"],
            "official_0hop": s0["official"],
            "official_within_1hop": s1["official"],
            "official_within_2hop": s2["official"],
            "layer_0hop": json.dumps(s0["by_layer"], ensure_ascii=False),
            "layer_within_1hop": json.dumps(s1["by_layer"], ensure_ascii=False),
            "layer_within_2hop": json.dumps(s2["by_layer"], ensure_ascii=False),
        })
    town_rows.sort(key=lambda r: -r["n_entity_within_2hop"])
    with (OUT_DIR / "town_entity_linkage.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(town_rows[0].keys()))
        w.writeheader()
        w.writerows(town_rows)

    print("[6/6] 写入总览 json ...")
    global_e0, global_e1, global_e2 = set(), set(), set()
    for v in grid_acc.values():
        global_e0 |= v["e0"]
        global_e1 |= v["e1"]
        global_e2 |= v["e2"]
    overview = {
        "poi_in_bbox": len(poi_rows),
        "poi_with_anchor_tag": sum(1 for r in poi_rows if r["n_anchor_tag"] > 0),
        "poi_with_seed_entity": sum(1 for r in poi_rows if r["n_seed_entity"] > 0),
        "anchor_total": len(anchors),
        "anchor_matched_to_entity": hit,
        "anchor_entity_mappings": total_ent_linked,
        "entities_total": len(entities),
        "relations_total": len(relations),
        "entity_graph_nodes": len(graph),
        "coverage": {
            "unique_entities_0hop": len(global_e0),
            "unique_entities_within_1hop": len(global_e1),
            "unique_entities_within_2hop": len(global_e2),
        },
        "grid_count_with_poi": len(grid_rows),
        "town_count": len(town_rows),
    }
    with (OUT_DIR / "poi_entity_linkage_overview.json").open("w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)

    print("\n=== 概览 ===")
    for k, v in overview.items():
        print(f"  {k}: {v}")

    print("\n=== 按镇排序的实体覆盖 (within_2hop) ===")
    for r in town_rows:
        print(f"  {r['town']:<10s}  POI={r['poi_count']:>5d}  "
              f"E0={r['n_entity_0hop']:>4d}  E1={r['n_entity_within_1hop']:>5d}  E2={r['n_entity_within_2hop']:>5d}  "
              f"mentions(2hop)={r['mentions_within_2hop']:>6d}")


if __name__ == "__main__":
    main()
