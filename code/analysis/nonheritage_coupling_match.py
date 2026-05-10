#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
非遗中间件耦合分析 —— 数据驱动版
以非遗项目为中间件，通过 *name* 模糊匹配连接知识图谱实体和POI，
输出三张表：非遗-实体匹配、非遗-POI匹配、耦合汇总。
"""

import os
import re
import json
import csv
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(BASE_DIR, "..", "..")
ENTITY_PATH = os.path.join(ROOT_DIR, "output", "qwen_extraction", "merged_entities.json")
POI_PATH = os.path.join(ROOT_DIR, "output", "tables", "poi_llm_cleaned.csv")
NH_PATH = os.path.join(ROOT_DIR, "data", "gis", "nanhai_nonheritage_full90.json")
OUT_DIR = os.path.join(ROOT_DIR, "output", "tables")

PLACE_NAMES_LONG = [
    "百西村头村", "松塘村", "西联村", "下东村", "北村",
    "叶问宗支", "同乐堂", "平地黄氏", "鲁岗谢家",
    "西樵山", "官窑",
]

PLACE_NAMES_SHORT = [
    "广东", "佛山", "南海", "大沥", "里水", "九江", "西樵", "桂城",
    "丹灶", "狮山", "松塘", "仙岗", "盐步", "石石肯", "民乐",
    "鲁岗", "平洲", "叠滘", "黄岐", "赤山", "三山", "万石",
    "赤坎", "简村", "苏村", "狮中", "麦边", "南海区",
]

TECH_SUFFIXES = [
    "制作技艺", "酿制技艺", "织造技艺", "编织技艺",
    "酿造技艺", "腌制技艺", "锻造技艺",
]

MIN_KEYWORD_LEN = 2


def _strip_places(text: str) -> str:
    """去掉泛化地名，长地名优先"""
    for pn in PLACE_NAMES_LONG:
        text = text.replace(pn, "")
    for pn in PLACE_NAMES_SHORT:
        text = text.replace(pn, "")
    return text.strip()


def extract_keywords(raw_name: str) -> list[str]:
    """
    从非遗原始名称中提取主体关键词。
    规则：
      1. 如果有括号，括号外为 prefix，括号内为 inner
      2. 去掉泛化地名（长地名优先避免残留）
      3. 对较长的技艺名称额外提取短关键词（去掉通用后缀）
      4. 保留长度 >= 2 的关键词
    例: "狮舞（广东醒狮）" → ["狮舞", "醒狮"]
        "藤编（大沥）"     → ["藤编"]
        "松塘村孔子诞"     → ["孔子诞"]
    """
    m = re.match(r'^(.+?)[\(（](.+?)[\)）]$', raw_name)
    if m:
        prefix = m.group(1).strip()
        inner = m.group(2).strip()
    else:
        prefix = raw_name.strip()
        inner = ""

    keywords = set()

    cleaned_prefix = _strip_places(prefix)
    if len(cleaned_prefix) >= MIN_KEYWORD_LEN:
        keywords.add(cleaned_prefix)

    if inner:
        cleaned_inner = _strip_places(inner)
        if len(cleaned_inner) >= MIN_KEYWORD_LEN:
            keywords.add(cleaned_inner)

    for kw in list(keywords):
        for suffix in TECH_SUFFIXES:
            if kw.endswith(suffix) and len(kw) > len(suffix) + 1:
                short = kw[: -len(suffix)]
                if len(short) >= MIN_KEYWORD_LEN:
                    keywords.add(short)

    if not keywords:
        keywords.add(prefix)

    return sorted(keywords)


def load_entities():
    with open(ENTITY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["entities"]


def load_pois():
    pois = []
    with open(POI_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pois.append(row)
    return pois


def load_nonheritage():
    with open(NH_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


def match_entities(keywords, entities):
    """对每个关键词做 *kw* 匹配，返回匹配到的实体列表"""
    matched = []
    for ent in entities:
        ent_name = ent["name"]
        for kw in keywords:
            if kw in ent_name or ent_name in kw:
                matched.append(ent)
                break
    return matched


def match_pois(keywords, pois):
    """对每个关键词做 *kw* 匹配，返回匹配到的POI列表"""
    matched = []
    for poi in pois:
        poi_name = poi["name"]
        for kw in keywords:
            if kw in poi_name or poi_name in kw:
                matched.append(poi)
                break
    return matched


def main():
    print("=" * 70)
    print("非遗中间件耦合分析（数据驱动 *name* 匹配）")
    print("=" * 70)

    entities = load_entities()
    pois = load_pois()
    nh_items = load_nonheritage()

    print(f"实体总数: {len(entities)}")
    print(f"POI总数: {len(pois)}")
    print(f"非遗项目数: {len(nh_items)}")
    print()

    # ── 1. 清洗非遗名称 ──
    nh_cleaned = []
    for item in nh_items:
        kws = extract_keywords(item["name"])
        nh_cleaned.append({
            "raw_name": item["name"],
            "keywords": kws,
            "level": item["level"],
            "category": item["category"],
            "town": item["town"],
        })

    print("非遗名称清洗示例:")
    for nc in nh_cleaned[:10]:
        print(f"  {nc['raw_name']:30s} → {nc['keywords']}")
    print()

    # ── 2. 非遗 ↔ 实体 匹配 ──
    nh_entity_rows = []
    for nc in nh_cleaned:
        matched = match_entities(nc["keywords"], entities)
        total_mentions = sum(e.get("mentions", 0) for e in matched)
        nh_entity_rows.append({
            "nonheritage": nc["raw_name"],
            "level": nc["level"],
            "category": nc["category"],
            "town": nc["town"],
            "keywords": "|".join(nc["keywords"]),
            "entity_match_count": len(matched),
            "total_mentions": total_mentions,
            "matched_entities": "|".join(
                f"{e['name']}({e.get('mentions',0)})"
                for e in sorted(matched, key=lambda x: x.get("mentions", 0), reverse=True)
            ),
        })

    # ── 3. 非遗 ↔ POI 匹配 ──
    nh_poi_rows = []
    for nc in nh_cleaned:
        matched = match_pois(nc["keywords"], pois)
        nh_poi_rows.append({
            "nonheritage": nc["raw_name"],
            "level": nc["level"],
            "category": nc["category"],
            "town": nc["town"],
            "keywords": "|".join(nc["keywords"]),
            "poi_match_count": len(matched),
            "matched_pois": "|".join(
                f"{p['name']}@{p.get('town','')}"
                for p in matched[:20]
            ),
        })

    # ── 4. 耦合汇总表 ──
    coupling_rows = []
    for i, nc in enumerate(nh_cleaned):
        ent_row = nh_entity_rows[i]
        poi_row = nh_poi_rows[i]

        ent_count = ent_row["entity_match_count"]
        poi_count = poi_row["poi_match_count"]
        total_mentions = ent_row["total_mentions"]

        if ent_count > 0 and poi_count > 0:
            coupling_type = "双向耦合"
        elif ent_count > 0:
            coupling_type = "仅实体匹配"
        elif poi_count > 0:
            coupling_type = "仅POI匹配"
        else:
            coupling_type = "无匹配"

        coupling_rows.append({
            "nonheritage": nc["raw_name"],
            "level": nc["level"],
            "category": nc["category"],
            "town": nc["town"],
            "keywords": "|".join(nc["keywords"]),
            "entity_match_count": ent_count,
            "total_mentions": total_mentions,
            "poi_match_count": poi_count,
            "coupling_type": coupling_type,
        })

    # ── 输出统计 ──
    type_counts = defaultdict(int)
    for r in coupling_rows:
        type_counts[r["coupling_type"]] += 1

    print("耦合类型统计:")
    for ct in ["双向耦合", "仅实体匹配", "仅POI匹配", "无匹配"]:
        print(f"  {ct}: {type_counts[ct]}")
    print()

    print("TOP-15 实体匹配（按 total_mentions 排序）:")
    sorted_by_mentions = sorted(nh_entity_rows, key=lambda x: x["total_mentions"], reverse=True)
    for r in sorted_by_mentions[:15]:
        print(f"  {r['nonheritage']:30s} | 实体数={r['entity_match_count']:3d} | mentions={r['total_mentions']:5d} | {r['matched_entities'][:80]}")
    print()

    print("TOP-15 POI匹配:")
    sorted_by_poi = sorted(nh_poi_rows, key=lambda x: x["poi_match_count"], reverse=True)
    for r in sorted_by_poi[:15]:
        print(f"  {r['nonheritage']:30s} | POI数={r['poi_match_count']:3d} | {r['matched_pois'][:80]}")
    print()

    # ── 写CSV ──
    os.makedirs(OUT_DIR, exist_ok=True)

    def write_csv(path, rows, fieldnames):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"已写入: {path}  ({len(rows)} 行)")

    write_csv(
        os.path.join(OUT_DIR, "nh_entity_match.csv"),
        sorted(nh_entity_rows, key=lambda x: x["total_mentions"], reverse=True),
        ["nonheritage", "level", "category", "town", "keywords",
         "entity_match_count", "total_mentions", "matched_entities"],
    )

    write_csv(
        os.path.join(OUT_DIR, "nh_poi_match.csv"),
        sorted(nh_poi_rows, key=lambda x: x["poi_match_count"], reverse=True),
        ["nonheritage", "level", "category", "town", "keywords",
         "poi_match_count", "matched_pois"],
    )

    write_csv(
        os.path.join(OUT_DIR, "nh_coupling_summary.csv"),
        sorted(coupling_rows, key=lambda x: (x["total_mentions"] + x["poi_match_count"]), reverse=True),
        ["nonheritage", "level", "category", "town", "keywords",
         "entity_match_count", "total_mentions", "poi_match_count", "coupling_type"],
    )

    # ── JSON 详细结果 ──
    detail = {
        "description": "非遗中间件耦合分析结果",
        "method": "以非遗项目为中间件，清洗名称后提取主体关键词，对实体和POI做 *name* contains 匹配",
        "stats": {
            "nonheritage_count": len(nh_items),
            "entity_count": len(entities),
            "poi_count": len(pois),
            "coupling_type_stats": dict(type_counts),
        },
        "coupling": coupling_rows,
    }
    json_path = os.path.join(OUT_DIR, "nh_coupling_detail.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False, indent=2)
    print(f"已写入: {json_path}")

    print("\n完成!")


if __name__ == "__main__":
    main()
