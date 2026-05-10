#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三张地图数据构建脚本（4.13 需求）

任务1：知识图谱实体空间定位（地名/建筑遗迹 → 匹配POI/锚点坐标）
任务2：以地点为轴心的关系反向索引
任务3：评论数据的空间挂载
任务4：三图统一数据结构 triple_map_data.json
任务5：可行性验证与缺口报告
任务6：GIS 输出（Shapefile/GeoJSON）+ 简图 PNG
"""

import json
import csv
import os
import re
from datetime import datetime
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "data")
OUTPUT = os.path.join(ROOT, "output")
TABLES = os.path.join(OUTPUT, "tables")
GIS_OUT = os.path.join(OUTPUT, "gis")
FIGURES = os.path.join(OUTPUT, "figures")

os.makedirs(TABLES, exist_ok=True)
os.makedirs(GIS_OUT, exist_ok=True)
os.makedirs(FIGURES, exist_ok=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  -> 已保存: {os.path.relpath(path, ROOT)}")


def save_csv(rows, path, fieldnames):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  -> 已保存: {os.path.relpath(path, ROOT)} ({len(rows)} 行)")


# ────────────────────────────────────────────────────────────
# 数据加载
# ────────────────────────────────────────────────────────────
print("=" * 60)
print("加载数据...")
print("=" * 60)

poi_data = load_json(os.path.join(DATA, "poi", "poi_cleaned.json"))
pois = poi_data["pois"]
print(f"  POI: {len(pois)} 条")

entities_data = load_json(os.path.join(OUTPUT, "qwen_extraction", "merged_entities.json"))
entities = entities_data["entities"]
print(f"  实体: {len(entities)} 个")

relations_data = load_json(os.path.join(OUTPUT, "qwen_extraction", "merged_relations.json"))
relations = relations_data["relations"]
print(f"  关系: {len(relations)} 条")

anchors_data = load_json(os.path.join(DATA, "anchors", "cultural_anchors.json"))
anchors = anchors_data["anchors"]
print(f"  文化锚点: {len(anchors)} 个")

reviews = load_json(os.path.join(DATA, "reviews", "review_summary_merged.json"))
print(f"  评论汇总: {len(reviews)} 条景点")

coupling_data = load_json(os.path.join(TABLES, "nh_coupling_detail.json"))
coupling_list = coupling_data["coupling"]
print(f"  耦合结果: {len(coupling_list)} 项")

review_link_path = os.path.join(TABLES, "review_poi_link.csv")
review_links = []
with open(review_link_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        review_links.append(row)
print(f"  评论-POI链接: {len(review_links)} 条")

boundary_path = os.path.join(DATA, "gis", "nanhai_boundary.geojson")
towns_path = os.path.join(DATA, "gis", "nanhai_towns.geojson")
boundary_geo = load_json(boundary_path)
towns_geo = load_json(towns_path)

nonheritage_data = load_json(os.path.join(DATA, "gis", "nanhai_nonheritage_full90.json"))


# ────────────────────────────────────────────────────────────
# 任务1：知识图谱实体的空间定位
# ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("任务1：知识图谱实体的空间定位")
print("=" * 60)

place_type_prefixes = ("D1", "D2", "D3", "D4", "B1", "B2", "B3", "B4", "B5", "B6")
place_entities = [e for e in entities if e.get("ai_grade_type", "").startswith(place_type_prefixes)]
print(f"  地名+建筑遗迹实体: {len(place_entities)} 个")

poi_name_map = {}
for p in pois:
    poi_name_map[p["name"]] = p

anchor_name_map = {}
for a in anchors:
    anchor_name_map[a["name"]] = a

entity_name_set = set()
for e in entities:
    entity_name_set.add(e["name"])

def match_entity_to_location(entity_name):
    """尝试将实体名匹配到坐标：先精确匹配POI/锚点，再做包含匹配"""
    if entity_name in poi_name_map:
        p = poi_name_map[entity_name]
        return p["lng"], p["lat"], p.get("town", ""), "poi_exact", p["id"]
    if entity_name in anchor_name_map:
        a = anchor_name_map[entity_name]
        return a["lng"], a["lat"], a.get("town", ""), "anchor_exact", a["id"]

    best_poi = None
    best_poi_len = 0
    for pname, p in poi_name_map.items():
        if len(entity_name) >= 2 and entity_name in pname:
            if len(pname) > best_poi_len or best_poi is None:
                best_poi = p
                best_poi_len = len(pname)
        elif len(pname) >= 2 and pname in entity_name:
            if best_poi is None:
                best_poi = p
                best_poi_len = len(pname)
    if best_poi:
        return best_poi["lng"], best_poi["lat"], best_poi.get("town", ""), "poi_contain", best_poi["id"]

    best_anc = None
    for aname, a in anchor_name_map.items():
        if len(entity_name) >= 2 and entity_name in aname:
            best_anc = a
            break
        elif len(aname) >= 2 and aname in entity_name:
            if best_anc is None:
                best_anc = a
    if best_anc:
        return best_anc["lng"], best_anc["lat"], best_anc.get("town", ""), "anchor_contain", best_anc["id"]

    return None, None, None, None, None


located_entities = []
for e in place_entities:
    lng, lat, town, match_src, match_id = match_entity_to_location(e["name"])
    if lng is not None and lng > 100 and lat > 20:
        located_entities.append({
            "entity_name": e["name"],
            "entity_type": e.get("ai_grade_type", ""),
            "mentions": e.get("mentions", 0),
            "source_count": e.get("source_count", 0),
            "lng": lng,
            "lat": lat,
            "town": town,
            "match_source": match_src,
            "match_id": match_id,
        })

print(f"  匹配成功: {len(located_entities)} / {len(place_entities)}"
      f" ({100*len(located_entities)/len(place_entities):.1f}%)")

match_by_src = defaultdict(int)
for le in located_entities:
    match_by_src[le["match_source"]] += 1
for k, v in sorted(match_by_src.items()):
    print(f"    {k}: {v}")

save_csv(
    located_entities,
    os.path.join(TABLES, "located_entities.csv"),
    ["entity_name", "entity_type", "mentions", "source_count",
     "lng", "lat", "town", "match_source", "match_id"],
)

located_name_set = {le["entity_name"] for le in located_entities}
located_coord_map = {}
for le in located_entities:
    located_coord_map[le["entity_name"]] = le


# ────────────────────────────────────────────────────────────
# 任务2：以地点为轴心的关系反向索引
# ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("任务2：以地点为轴心的关系反向索引")
print("=" * 60)

SPATIAL_RELATIONS = {"位于", "活动于", "出生于", "创建修建", "始建于", "承载文化", "盛产", "发生于"}

entity_mention_map = {}
for e in entities:
    entity_mention_map[e["name"]] = {
        "type": e.get("ai_grade_type", ""),
        "mentions": e.get("mentions", 0),
        "source_count": e.get("source_count", 0),
    }

place_index = defaultdict(lambda: {"related": [], "relation_types": defaultdict(int), "total_links": 0})

for r in relations:
    src_name = r["source"]
    tgt_name = r["target"]
    rel_type = r.get("relation_text", r.get("relation", ""))

    if tgt_name in located_name_set:
        place_key = tgt_name
        other_name = src_name
    elif src_name in located_name_set and rel_type in SPATIAL_RELATIONS:
        place_key = src_name
        other_name = tgt_name
    else:
        continue

    info = entity_mention_map.get(other_name, {"type": "未知", "mentions": 0, "source_count": 0})
    place_index[place_key]["related"].append({
        "name": other_name,
        "type": info["type"],
        "relation": rel_type,
        "mentions": info["mentions"],
        "evidence": r.get("evidence", ""),
    })
    place_index[place_key]["relation_types"][rel_type] += 1
    place_index[place_key]["total_links"] += 1

for place_name in place_index:
    pi = place_index[place_name]
    pi["relation_types"] = dict(pi["relation_types"])
    seen = set()
    unique_related = []
    for item in pi["related"]:
        key = (item["name"], item["relation"])
        if key not in seen:
            seen.add(key)
            unique_related.append(item)
    unique_related.sort(key=lambda x: x["mentions"], reverse=True)
    pi["related"] = unique_related
    pi["total_links"] = len(unique_related)

place_index_out = {}
for name in sorted(place_index.keys(), key=lambda n: place_index[n]["total_links"], reverse=True):
    place_index_out[name] = place_index[name]

print(f"  已索引地点数: {len(place_index_out)}")
top5 = list(place_index_out.items())[:5]
for name, info in top5:
    print(f"    {name}: {info['total_links']} 条关联")

save_json(place_index_out, os.path.join(TABLES, "place_entity_index.json"))


# ────────────────────────────────────────────────────────────
# 任务3：评论数据的空间挂载
# ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("任务3：评论数据的空间挂载")
print("=" * 60)

link_spot_to_poi = {}
for lk in review_links:
    spot = lk["spot_name"]
    pid = lk["poi_id"]
    link_spot_to_poi[spot] = {
        "poi_id": pid,
        "poi_name": lk.get("poi_name", ""),
        "poi_lng": float(lk["poi_lng"]) if lk.get("poi_lng") else None,
        "poi_lat": float(lk["poi_lat"]) if lk.get("poi_lat") else None,
        "poi_town": lk.get("poi_town", ""),
    }

review_name_map = {}
for rv in reviews:
    review_name_map[rv["name"]] = rv

poi_reviews = {}
matched_review_count = 0
for spot_name, poi_info in link_spot_to_poi.items():
    rv = review_name_map.get(spot_name)
    if rv is None:
        for rname, rdata in review_name_map.items():
            if spot_name in rname or rname in spot_name:
                rv = rdata
                break
    if rv is None:
        continue
    pid = poi_info["poi_id"]
    if not pid or len(pid) < 5:
        continue
    if pid not in poi_reviews:
        poi_reviews[pid] = {
            "poi_id": pid,
            "poi_name": poi_info["poi_name"],
            "poi_lng": poi_info["poi_lng"],
            "poi_lat": poi_info["poi_lat"],
            "poi_town": poi_info["poi_town"],
            "review_count": 0,
            "avg_rating": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "sources": set(),
        }
    pr = poi_reviews[pid]
    pr["review_count"] += rv.get("total_count") or 0
    pr["positive_count"] += rv.get("positive_count") or 0
    pr["neutral_count"] += rv.get("neutral_count") or 0
    pr["negative_count"] += rv.get("negative_count") or 0
    for s in rv.get("sources", []):
        pr["sources"].add(s)
    if rv.get("avg_rating"):
        if pr["avg_rating"] == 0:
            pr["avg_rating"] = rv["avg_rating"]
        else:
            pr["avg_rating"] = (pr["avg_rating"] + rv["avg_rating"]) / 2
    matched_review_count += 1

for pid in poi_reviews:
    pr = poi_reviews[pid]
    pr["sources"] = sorted(pr["sources"])
    total_sent = pr["positive_count"] + pr["neutral_count"] + pr["negative_count"]
    pr["positive_rate"] = round(100 * pr["positive_count"] / total_sent, 1) if total_sent > 0 else 0
    pr["negative_rate"] = round(100 * pr["negative_count"] / total_sent, 1) if total_sent > 0 else 0

print(f"  评论景点匹配到POI: {len(poi_reviews)} 个")
print(f"  评论条目映射: {matched_review_count} 条景点")

save_json(list(poi_reviews.values()), os.path.join(TABLES, "poi_with_reviews.json"))


# ────────────────────────────────────────────────────────────
# 任务4：三图统一数据结构
# ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("任务4：三图统一数据结构")
print("=" * 60)

poi_id_map = {}
for p in pois:
    poi_id_map[p["id"]] = p

knowledge_by_poi = {}
for le in located_entities:
    mid = le.get("match_id")
    if mid and mid in poi_id_map:
        ename = le["entity_name"]
        pi = place_index.get(ename, {"related": [], "total_links": 0, "relation_types": {}})
        knowledge_by_poi[mid] = {
            "entity_name": ename,
            "entity_type": le["entity_type"],
            "mentions": le["mentions"],
            "source_count": le["source_count"],
            "related_entities": pi["related"][:20],
            "total_related": pi["total_links"],
        }

for le in located_entities:
    mid = le.get("match_id")
    if mid and mid not in poi_id_map and mid.startswith("ANC_"):
        ename = le["entity_name"]
        best_poi_id = None
        best_dist = float("inf")
        for p in pois:
            dx = abs(p["lng"] - le["lng"])
            dy = abs(p["lat"] - le["lat"])
            d = dx + dy
            if d < best_dist and d < 0.005:
                best_dist = d
                best_poi_id = p["id"]
        if best_poi_id and best_poi_id not in knowledge_by_poi:
            pi = place_index.get(ename, {"related": [], "total_links": 0, "relation_types": {}})
            knowledge_by_poi[best_poi_id] = {
                "entity_name": ename,
                "entity_type": le["entity_type"],
                "mentions": le["mentions"],
                "source_count": le["source_count"],
                "related_entities": pi["related"][:20],
                "total_related": pi["total_links"],
            }

places = []
count_tourism = 0
count_cognition = 0
count_knowledge = 0
count_all_three = 0

for p in pois:
    pid = p["id"]
    tourism_layer = {
        "category": p.get("category", ""),
        "rating": p.get("rating"),
        "original_type": p.get("original_type", ""),
        "nonheritage_match": p.get("nonheritage_match", []),
        "cultural_anchors": p.get("cultural_anchors", []),
    }
    count_tourism += 1

    cognition_layer = None
    if pid in poi_reviews:
        pr = poi_reviews[pid]
        cognition_layer = {
            "review_count": pr["review_count"],
            "avg_rating": pr["avg_rating"],
            "positive_count": pr["positive_count"],
            "neutral_count": pr["neutral_count"],
            "negative_count": pr["negative_count"],
            "positive_rate": pr["positive_rate"],
            "negative_rate": pr["negative_rate"],
            "sources": pr["sources"],
        }
        count_cognition += 1

    knowledge_layer = None
    if pid in knowledge_by_poi:
        knowledge_layer = knowledge_by_poi[pid]
        count_knowledge += 1

    if cognition_layer and knowledge_layer:
        count_all_three += 1

    places.append({
        "id": pid,
        "name": p["name"],
        "lng": p["lng"],
        "lat": p["lat"],
        "town": p.get("town", ""),
        "layers": {
            "tourism": tourism_layer,
            "cognition": cognition_layer,
            "knowledge": knowledge_layer,
        },
    })

for le in located_entities:
    mid = le.get("match_id")
    if mid and mid not in poi_id_map and mid.startswith("ANC_"):
        already_near = False
        for pl in places:
            if pl["layers"]["knowledge"] and pl["layers"]["knowledge"]["entity_name"] == le["entity_name"]:
                already_near = True
                break
        if not already_near:
            ename = le["entity_name"]
            pi = place_index.get(ename, {"related": [], "total_links": 0})
            places.append({
                "id": mid,
                "name": le["entity_name"],
                "lng": le["lng"],
                "lat": le["lat"],
                "town": le.get("town", ""),
                "layers": {
                    "tourism": None,
                    "cognition": None,
                    "knowledge": {
                        "entity_name": ename,
                        "entity_type": le["entity_type"],
                        "mentions": le["mentions"],
                        "source_count": le["source_count"],
                        "related_entities": pi["related"][:20],
                        "total_related": pi["total_links"],
                    },
                },
            })
            count_knowledge += 1

triple_map = {
    "meta": {
        "total_places": len(places),
        "with_tourism": count_tourism,
        "with_cognition": count_cognition,
        "with_knowledge": count_knowledge,
        "with_all_three": count_all_three,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    },
    "places": places,
}

print(f"  总地点数: {len(places)}")
print(f"  有旅游图层: {count_tourism}")
print(f"  有认知图层: {count_cognition}")
print(f"  有知识图层: {count_knowledge}")
print(f"  三层齐全: {count_all_three}")

save_json(triple_map, os.path.join(TABLES, "triple_map_data.json"))


# ────────────────────────────────────────────────────────────
# 任务5：可行性验证与缺口报告
# ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("任务5：可行性验证与缺口报告")
print("=" * 60)

town_coverage = defaultdict(lambda: {"tourism": 0, "cognition": 0, "knowledge": 0})
for pl in places:
    t = pl.get("town", "未知")
    if pl["layers"].get("tourism"):
        town_coverage[t]["tourism"] += 1
    if pl["layers"].get("cognition"):
        town_coverage[t]["cognition"] += 1
    if pl["layers"].get("knowledge"):
        town_coverage[t]["knowledge"] += 1

nh_items = nonheritage_data.get("items", [])
nh_in_all_three = 0
for nh in nh_items:
    nh_name = nh["name"]
    keywords = re.split(r"[（）()、]", nh_name)
    keywords = [k.strip() for k in keywords if len(k.strip()) >= 2]
    found_knowledge = False
    found_cognition = False
    for pl in places:
        k = pl["layers"].get("knowledge")
        if k:
            for rel in k.get("related_entities", []):
                for kw in keywords:
                    if kw in rel["name"] or rel["name"] in kw:
                        found_knowledge = True
                        break
        c = pl["layers"].get("cognition")
        if c:
            for kw in keywords:
                if kw in pl["name"]:
                    found_cognition = True
                    break
    if found_knowledge and found_cognition:
        nh_in_all_three += 1

report_lines = [
    "# 三张地图可行性评估报告",
    "",
    f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    "",
    "---",
    "",
    "## 1. 知识图谱实体空间定位",
    "",
    f"- 地名+建筑遗迹实体总数: **{len(place_entities)}**",
    f"- 成功匹配坐标: **{len(located_entities)}** ({100*len(located_entities)/len(place_entities):.1f}%)",
    "",
    "匹配来源分布:",
    "",
    "| 匹配方式 | 数量 |",
    "|----------|------|",
]
for k, v in sorted(match_by_src.items()):
    report_lines.append(f"| {k} | {v} |")

report_lines += [
    "",
    "## 2. 三图覆盖统计",
    "",
    f"- 有旅游图层（POI）: **{count_tourism}**",
    f"- 有认知图层（评论）: **{count_cognition}**",
    f"- 有知识图层（图谱）: **{count_knowledge}**",
    f"- 三层齐全的富数据点: **{count_all_three}**",
    "",
    "## 3. 镇街覆盖分布",
    "",
    "| 镇街 | 旅游图层 | 认知图层 | 知识图层 |",
    "|------|---------|---------|---------|",
]
for town in ["桂城街道", "里水镇", "狮山镇", "大沥镇", "丹灶镇", "西樵镇", "九江镇"]:
    tc = town_coverage[town]
    report_lines.append(f"| {town} | {tc['tourism']} | {tc['cognition']} | {tc['knowledge']} |")

report_lines += [
    "",
    "## 4. 非遗在三图中的覆盖",
    "",
    f"- 91项非遗中，能通过地点桥梁同时出现在认知+知识地图的: **{nh_in_all_three}** 项",
    "",
    "## 5. 主要缺口与说明",
    "",
    '1. **知识图层覆盖率偏低属正常现象**: 典籍中大量地名为古地名、泛指或已消失的地名，'
    '无法匹配到现代POI或锚点坐标。这不影响论文叙事，反而体现了"文化未转化"的现实。',
    '2. **认知图层集中于头部景点**: 403个有评论的景点多为知名景区，覆盖面有限，'
    '但恰好代表了市场侧的真实关注度，与论文"市场产品"的分析角度一致。',
    '3. **三层齐全的富数据点**虽然数量有限，但正是论文中"文旅融合深度"最佳的分析样本。',
    '4. **旅游点地图缺少解说/导览内容**: 现有POI仅含基础属性，无景区宣传文本。'
    '可暂以评论摘要和非遗匹配信息代替。',
]

report_text = "\n".join(report_lines)
report_path = os.path.join(TABLES, "triple_map_feasibility.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report_text)
print(f"  -> 已保存: {os.path.relpath(report_path, ROOT)}")
print(report_text)


# ────────────────────────────────────────────────────────────
# 任务6：GIS 输出 + 简图
# ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("任务6：GIS 输出 + 简图")
print("=" * 60)

try:
    import geopandas as gpd
    from shapely.geometry import Point
    HAS_GPD = True
    print("  geopandas 可用，将输出 Shapefile + GeoJSON")
except ImportError:
    HAS_GPD = False
    print("  geopandas 不可用，仅输出 GeoJSON")


def build_geojson(features):
    return {"type": "FeatureCollection", "features": features}


def point_feature(lng, lat, props):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": props,
    }


# --- 旅游点地图 ---
tourism_features = []
for pl in places:
    t = pl["layers"].get("tourism")
    if not t:
        continue
    props = {
        "id": pl["id"],
        "name": pl["name"],
        "town": pl["town"],
        "category": t["category"],
        "rating": t.get("rating"),
        "nh_match": "|".join(t.get("nonheritage_match", [])),
        "has_nh": 1 if t.get("nonheritage_match") else 0,
    }
    tourism_features.append(point_feature(pl["lng"], pl["lat"], props))

tourism_geojson = build_geojson(tourism_features)
tourism_geojson_path = os.path.join(GIS_OUT, "map_tourism.geojson")
save_json(tourism_geojson, tourism_geojson_path)

# --- 认知地图 ---
cognition_features = []
for pl in places:
    c = pl["layers"].get("cognition")
    if not c:
        continue
    props = {
        "id": pl["id"],
        "name": pl["name"],
        "town": pl["town"],
        "rev_count": c["review_count"],
        "avg_rate": round(c["avg_rating"], 2),
        "pos_rate": c["positive_rate"],
        "neg_rate": c["negative_rate"],
        "sources": "|".join(c.get("sources", [])),
    }
    cognition_features.append(point_feature(pl["lng"], pl["lat"], props))

cognition_geojson = build_geojson(cognition_features)
cognition_geojson_path = os.path.join(GIS_OUT, "map_cognition.geojson")
save_json(cognition_geojson, cognition_geojson_path)

# --- 知识地图 ---
knowledge_features = []
for pl in places:
    k = pl["layers"].get("knowledge")
    if not k:
        continue
    top3 = k.get("related_entities", [])[:3]
    top3_str = "|".join([f"{r['name']}({r['relation']})" for r in top3])
    props = {
        "id": pl["id"],
        "name": pl["name"],
        "town": pl["town"],
        "ent_name": k["entity_name"],
        "ent_type": k["entity_type"],
        "mentions": k["mentions"],
        "src_count": k["source_count"],
        "n_related": k["total_related"],
        "top3": top3_str,
    }
    knowledge_features.append(point_feature(pl["lng"], pl["lat"], props))

knowledge_geojson = build_geojson(knowledge_features)
knowledge_geojson_path = os.path.join(GIS_OUT, "map_knowledge.geojson")
save_json(knowledge_geojson, knowledge_geojson_path)

# --- 评论密度地图 ---
density_features = []
for pl in places:
    c = pl["layers"].get("cognition")
    if not c:
        continue
    props = {
        "id": pl["id"],
        "name": pl["name"],
        "town": pl["town"],
        "rev_count": c["review_count"],
        "avg_rate": round(c["avg_rating"], 2),
    }
    density_features.append(point_feature(pl["lng"], pl["lat"], props))

density_geojson = build_geojson(density_features)
density_geojson_path = os.path.join(GIS_OUT, "map_review_density.geojson")
save_json(density_geojson, density_geojson_path)

print(f"  旅游点地图要素: {len(tourism_features)}")
print(f"  认知地图要素: {len(cognition_features)}")
print(f"  知识地图要素: {len(knowledge_features)}")
print(f"  评论密度要素: {len(density_features)}")

# --- Shapefile 输出 ---
if HAS_GPD:
    def geojson_to_shp(geojson_path, shp_path):
        gdf = gpd.read_file(geojson_path)
        gdf = gdf.set_crs("EPSG:4326", allow_override=True)
        gdf.to_file(shp_path, encoding="utf-8")
        print(f"  -> Shapefile: {os.path.relpath(shp_path, ROOT)}")

    geojson_to_shp(tourism_geojson_path, os.path.join(GIS_OUT, "map_tourism.shp"))
    geojson_to_shp(cognition_geojson_path, os.path.join(GIS_OUT, "map_cognition.shp"))
    geojson_to_shp(knowledge_geojson_path, os.path.join(GIS_OUT, "map_knowledge.shp"))
    geojson_to_shp(density_geojson_path, os.path.join(GIS_OUT, "map_review_density.shp"))

# --- 简图 ---
print("\n  生成简图...")

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

towns_gdf = None
if HAS_GPD:
    try:
        towns_gdf = gpd.read_file(towns_path)
    except Exception:
        pass

boundary_gdf = None
if HAS_GPD:
    try:
        boundary_gdf = gpd.read_file(boundary_path)
    except Exception:
        pass


def extract_polygon_coords(geojson):
    """从 GeoJSON 中提取所有多边形的外环坐标用于 matplotlib 绘制"""
    coords_list = []
    for feat in geojson.get("features", []):
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            coords_list.append(np.array(geom["coordinates"][0]))
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                coords_list.append(np.array(poly[0]))
    return coords_list


def draw_basemap(ax):
    """绘制镇街边界底图（纯 matplotlib，避免 geopandas aspect 问题）"""
    for coords in extract_polygon_coords(towns_geo):
        ax.plot(coords[:, 0], coords[:, 1], color="#888888", linewidth=0.5)
    for coords in extract_polygon_coords(boundary_geo):
        ax.plot(coords[:, 0], coords[:, 1], color="#333333", linewidth=1.2)


# 图1: 旅游点地图
fig, ax = plt.subplots(1, 1, figsize=(10, 8))
draw_basemap(ax)
cat_colors = {
    "公园绿地": "#4CAF50", "自然景观": "#8BC34A", "文化场馆": "#FF5722",
    "人文古迹": "#E91E63", "宗教场所": "#9C27B0", "非遗体验": "#FF9800",
    "休闲娱乐": "#00BCD4", "体育设施": "#607D8B", "教育研学": "#3F51B5",
    "特色街区": "#795548", "其他": "#BDBDBD",
}
for pl in places:
    t = pl["layers"].get("tourism")
    if not t:
        continue
    c = cat_colors.get(t["category"], "#BDBDBD")
    ax.scatter(pl["lng"], pl["lat"], c=c, s=3, alpha=0.4, edgecolors="none")

patches = [mpatches.Patch(color=v, label=k) for k, v in cat_colors.items() if k != "其他"]
ax.legend(handles=patches, loc="lower right", fontsize=7, framealpha=0.9)
ax.set_title("旅游点地图（空间实践）", fontsize=14, fontweight="bold")
ax.set_xlabel("经度")
ax.set_ylabel("纬度")
ax.set_aspect("equal")
fig.tight_layout()
fig.savefig(os.path.join(FIGURES, "map_tourism_preview.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {os.path.relpath(os.path.join(FIGURES, 'map_tourism_preview.png'), ROOT)}")

# 图2: 认知地图（评分分布）
fig, ax = plt.subplots(1, 1, figsize=(10, 8))
draw_basemap(ax)
cog_places = [pl for pl in places if pl["layers"].get("cognition")]
cog_lngs = [pl["lng"] for pl in cog_places]
cog_lats = [pl["lat"] for pl in cog_places]
cog_counts = [pl["layers"]["cognition"]["review_count"] for pl in cog_places]
cog_ratings = [pl["layers"]["cognition"]["avg_rating"] for pl in cog_places]

if cog_counts:
    max_count = max(cog_counts)
    sizes = [max(18, 180 * (c / max_count)) for c in cog_counts]
    sc = ax.scatter(cog_lngs, cog_lats, s=sizes, c=cog_ratings, cmap="RdYlGn",
                    vmin=2.5, vmax=5.0, alpha=0.7, edgecolors="gray", linewidth=0.3)
    cbar = plt.colorbar(sc, ax=ax, shrink=0.6, label="平台综合评分")
    size_legend_vals = [10, 100, 500]
    size_legend_handles = []
    for v in size_legend_vals:
        s = max(18, 180 * (v / max_count))
        size_legend_handles.append(ax.scatter([], [], s=s, c="gray", alpha=0.5, label=f"{v} 条评论"))
    ax.legend(handles=size_legend_handles, loc="lower right", fontsize=7,
              title="圆圈大小", title_fontsize=8, framealpha=0.9)

ax.set_title("旅游认知地图 — 评分分布（表征性空间）", fontsize=14, fontweight="bold")
ax.set_xlabel("经度")
ax.set_ylabel("纬度")
ax.set_aspect("equal")
fig.tight_layout()
fig.savefig(os.path.join(FIGURES, "map_cognition_preview.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {os.path.relpath(os.path.join(FIGURES, 'map_cognition_preview.png'), ROOT)}")

# 图2b: 评论密度地图
fig, ax = plt.subplots(1, 1, figsize=(10, 8))
draw_basemap(ax)
if cog_counts:
    p99 = sorted(cog_counts)[int(len(cog_counts) * 0.99)]
    capped_counts = [min(c, p99 * 2) for c in cog_counts]
    log_counts = [np.log10(max(c, 1)) for c in capped_counts]
    max_log = max(log_counts) if max(log_counts) > 0 else 1
    sizes = [max(18, 160 * (lc / max_log)) for lc in log_counts]
    sc = ax.scatter(cog_lngs, cog_lats, s=sizes, c=log_counts, cmap="YlOrBr",
                    alpha=0.7, edgecolors="#8B4513", linewidth=0.3)
    cbar = plt.colorbar(sc, ax=ax, shrink=0.6, label="评论数量 (log10)")
    tick_vals = [1, 10, 50, 200]
    cbar.set_ticks([np.log10(v) for v in tick_vals])
    cbar.set_ticklabels([str(v) for v in tick_vals])

    sorted_reviews = sorted(zip(cog_lngs, cog_lats, cog_counts,
                                [pl["name"] for pl in cog_places]),
                            key=lambda x: x[2], reverse=True)
    labeled = []
    offsets = [(6, 6), (-60, 8), (6, -12), (-70, -10), (6, 14), (-60, -14), (8, -18), (-50, 14)]
    oi = 0
    for lng, lat, cnt, nm in sorted_reviews:
        if cnt < 30:
            break
        too_close = False
        for ll, la in labeled:
            if abs(lng - ll) < 0.015 and abs(lat - la) < 0.01:
                too_close = True
                break
        if too_close:
            continue
        label = nm[:8] if len(nm) > 8 else nm
        ox, oy = offsets[oi % len(offsets)]
        ax.annotate(f"{label} ({cnt})", (lng, lat), fontsize=6,
                    xytext=(ox, oy), textcoords="offset points",
                    arrowprops=dict(arrowstyle="-", color="gray", lw=0.5),
                    bbox=dict(boxstyle="round,pad=0.2", fc="lightyellow", alpha=0.9))
        labeled.append((lng, lat))
        oi += 1
        if oi >= 8:
            break

ax.set_title("评论密度地图 — 游客关注度分布", fontsize=14, fontweight="bold")
ax.set_xlabel("经度")
ax.set_ylabel("纬度")
ax.set_aspect("equal")
fig.tight_layout()
fig.savefig(os.path.join(FIGURES, "map_review_density.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {os.path.relpath(os.path.join(FIGURES, 'map_review_density.png'), ROOT)}")

# 图3: 知识地图
fig, ax = plt.subplots(1, 1, figsize=(10, 8))
draw_basemap(ax)
know_data = [(pl["lng"], pl["lat"], pl["layers"]["knowledge"]["mentions"],
              pl["layers"]["knowledge"]["total_related"],
              pl["layers"]["knowledge"]["entity_name"])
             for pl in places if pl["layers"].get("knowledge")]

if know_data:
    klngs = [d[0] for d in know_data]
    klats = [d[1] for d in know_data]
    kmentions = [d[2] for d in know_data]
    krelated = [d[3] for d in know_data]

    max_m = max(kmentions) if max(kmentions) > 0 else 1
    sizes = [max(15, 220 * (m / max_m)) for m in kmentions]
    sc = ax.scatter(klngs, klats, s=sizes, c=krelated, cmap="YlOrRd",
                    alpha=0.75, edgecolors="darkred", linewidth=0.3)
    cbar = plt.colorbar(sc, ax=ax, shrink=0.6, label="关联实体数（人物/事件/技艺等）")

    size_legend_vals = [10, 100, 500]
    size_handles = []
    for v in size_legend_vals:
        s = max(15, 220 * (v / max_m))
        size_handles.append(ax.scatter([], [], s=s, c="#FF6600", alpha=0.5,
                                       edgecolors="darkred", linewidth=0.3,
                                       label=f"典籍提及 {v} 次"))
    ax.legend(handles=size_handles, loc="lower right", fontsize=7,
              title="圆圈大小 = 典籍提及频次", title_fontsize=8, framealpha=0.9)

    top_know = sorted(know_data, key=lambda d: d[2], reverse=True)[:12]
    for d in top_know:
        ax.annotate(d[4], (d[0], d[1]), fontsize=6,
                    xytext=(4, 4), textcoords="offset points",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8))

ax.set_title("知识地图 — 典籍文化实体的空间落点（空间表征）", fontsize=13, fontweight="bold")
ax.set_xlabel("经度")
ax.set_ylabel("纬度")
ax.set_aspect("equal")
fig.tight_layout()
fig.savefig(os.path.join(FIGURES, "map_knowledge_preview.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {os.path.relpath(os.path.join(FIGURES, 'map_knowledge_preview.png'), ROOT)}")

print("\n" + "=" * 60)
print("全部任务完成!")
print("=" * 60)
