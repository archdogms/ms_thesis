# -*- coding: utf-8 -*-
"""分析模块统一数据源：优先 LLM 清洗 POI、qwen 合并实体、评论汇总。"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

# code/analysis -> project root
_BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(_BASE, "data")
DB_DIR = os.path.join(DATA_DIR, "database")
OUTPUT_DIR = os.path.join(_BASE, "output")
TABLES_DIR = os.path.join(OUTPUT_DIR, "tables")
QWEN_DIR = os.path.join(OUTPUT_DIR, "qwen_extraction")

POI_LLM_CSV = os.path.join(TABLES_DIR, "poi_llm_cleaned.csv")
POI_CLEANED_JSON = os.path.join(DATA_DIR, "poi", "poi_cleaned.json")
POI_DB_JSON = os.path.join(DB_DIR, "poi_cleaned.json")
MERGED_ENTITIES = os.path.join(QWEN_DIR, "merged_entities.json")
CULTURE_ENTITIES = os.path.join(DB_DIR, "culture_entities.json")
REVIEW_SUMMARY_CSV = os.path.join(TABLES_DIR, "review_summary_merged.csv")


def load_pois_list() -> list[dict]:
    """
    优先 output/tables/poi_llm_cleaned.csv（与评论匹配、LLM 类别一致），
    否则 data/poi/poi_cleaned.json。
    返回与原 json 中单条 POI 结构兼容的 dict 列表（含 town, lng, lat, name, category 等）。
    """
    if os.path.isfile(POI_LLM_CSV):
        pois = []
        with open(POI_LLM_CSV, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    lng = float(row.get("lng") or 0)
                    lat = float(row.get("lat") or 0)
                except (TypeError, ValueError):
                    continue
                if lng <= 0 or lat <= 0:
                    continue
                pois.append(
                    {
                        "id": row.get("id", ""),
                        "name": row.get("name", ""),
                        "category": row.get("category", ""),
                        "original_type": row.get("original_type", ""),
                        "address": row.get("address", ""),
                        "town": row.get("town", "未知"),
                        "lng": lng,
                        "lat": lat,
                        "rating": row.get("rating", ""),
                        "source": row.get("source", ""),
                        "has_nonheritage": row.get("has_nonheritage", "").upper() == "TRUE",
                        "has_cultural_anchor": row.get("has_cultural_anchor", "").upper()
                        == "TRUE",
                        "nonheritage_match": (row.get("nonheritage_match") or "").split(
                            ";"
                        )
                        if row.get("nonheritage_match")
                        else [],
                        "cultural_anchors": (row.get("cultural_anchors") or "").split(";")
                        if row.get("cultural_anchors")
                        else [],
                        "query_type": row.get("query_type", ""),
                    }
                )
        return pois

    poi_path = POI_DB_JSON if os.path.isfile(POI_DB_JSON) else POI_CLEANED_JSON
    with open(poi_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("pois", []))


def culture_mentions_by_town(towns: list[str]) -> dict[str, int]:
    """
    镇街名 -> 典籍/图谱侧「文化强度」用于耦合 C 中 0.4 权重。
    优先 culture_entities.json（含 sources）；否则用 merged_entities.json（按 name/description 命中镇街关键词）。
    """
    culture_town_map: dict[str, int] = defaultdict(int)

    if os.path.isfile(CULTURE_ENTITIES):
        with open(CULTURE_ENTITIES, "r", encoding="utf-8") as f:
            entities_data = json.load(f)
        for e in entities_data.get("entities", []):
            for town in towns:
                short = town.replace("街道", "").replace("镇", "")
                for src in e.get("sources", []):
                    if short in src or town in src:
                        culture_town_map[town] += int(e.get("mentions", 1))
                        break
                else:
                    if short in (e.get("name") or "") or town in (e.get("name") or ""):
                        culture_town_map[town] += int(e.get("mentions", 1))
        return dict(culture_town_map)

    if not os.path.isfile(MERGED_ENTITIES):
        return dict(culture_town_map)

    with open(MERGED_ENTITIES, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 长镇名优先，减少「里」等误配
    ordered = sorted(towns, key=len, reverse=True)
    for e in data.get("entities", []):
        mentions = int(e.get("mentions", 1) or 1)
        blob = f"{e.get('name', '')}\n{e.get('description', '')}"
        for town in ordered:
            short = town.replace("街道", "").replace("镇", "")
            if town in blob or (len(short) >= 2 and short in blob):
                culture_town_map[town] += mentions
                break

    return dict(culture_town_map)


def review_total_by_town(pois: list[dict]) -> dict[str, int]:
    """按 POI 名称关联 review_summary_merged.csv 的 total_count，再按镇街求和。"""
    if not os.path.isfile(REVIEW_SUMMARY_CSV):
        return {}
    rev_by_name: dict[str, int] = {}
    with open(REVIEW_SUMMARY_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            try:
                rev_by_name[name] = int(float(row.get("total_count") or 0))
            except (TypeError, ValueError):
                rev_by_name[name] = 0

    by_town: dict[str, int] = defaultdict(int)
    for p in pois:
        t = p.get("town", "未知")
        nm = (p.get("name") or "").strip()
        by_town[t] += rev_by_name.get(nm, 0)
    return dict(by_town)
