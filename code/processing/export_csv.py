#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将所有JSON结果数据导出为CSV表格，便于查看和论文引用
"""

import json
import csv
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
BASE = os.path.join(_BASE_DIR, "data")
OUT = os.path.join(_BASE_DIR, "output", "tables")


def export_reviews():
    """导出评论数据为CSV（高德/携程爬虫结果，部分仅为评分无正文）"""
    path_json = os.path.join(BASE, "reviews", "nanhai_reviews_real.json")
    if not os.path.exists(path_json):
        print("nanhai_reviews_real.json 不存在，跳过")
        return
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("reviews", [])
    path = os.path.join(BASE, "reviews", "nanhai_reviews_real.csv")
    fields = ["spot_name", "rating", "review_text", "review_date", "source", "sentiment"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"评论CSV(高德/携程): {path} ({len(rows)}条)")


def export_review_summary():
    """导出评论汇总为CSV"""
    path_json = os.path.join(BASE, "reviews", "review_summary_real.json")
    if not os.path.exists(path_json):
        print("评论汇总JSON不存在，跳过")
        return
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    path = os.path.join(BASE, "reviews", "review_summary_real.csv")
    fields = ["name", "total_count", "text_review_count", "avg_rating",
              "positive_count", "neutral_count", "negative_count", "positive_rate", "sources"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in data:
            row["sources"] = ";".join(row.get("sources", []) if isinstance(row.get("sources"), list) else [])
            w.writerow(row)
    print(f"评论汇总CSV: {path} ({len(data)}条)")


def export_reviews_detail():
    """导出具体评论文本（来自辅助数据 携程/去哪儿/马蜂窝 xlsx 解析结果）"""
    path_json = os.path.join(BASE, "reviews", "merged_reviews_supp.json")
    if not os.path.exists(path_json):
        print("辅助数据评论 merged_reviews_supp.json 不存在，跳过评论明细表")
        return
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("reviews", [])
    path = os.path.join(OUT, "reviews_detail.csv")
    os.makedirs(OUT, exist_ok=True)
    fields = ["platform", "spot_name", "user", "text", "time", "source_note"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (r.get(k) or "") for k in fields})
    print(f"评论明细表(具体评论): {path} ({len(rows)}条)")


def build_and_export_review_summary_merged():
    """合并 高德/携程(review_summary_real) 与 辅助数据(携程/去哪儿/马蜂窝 merged_reviews_supp)，导出统一汇总表"""
    from collections import defaultdict
    merged = {}
    path_real = os.path.join(BASE, "reviews", "review_summary_real.json")
    if os.path.exists(path_real):
        with open(path_real, "r", encoding="utf-8") as f:
            for r in json.load(f):
                name = (r.get("name") or "").strip()
                if not name:
                    continue
                merged[name] = {
                    "name": name,
                    "total_count": r.get("total_count", 0),
                    "text_review_count": r.get("text_review_count", 0),
                    "avg_rating": r.get("avg_rating"),
                    "positive_count": r.get("positive_count"),
                    "neutral_count": r.get("neutral_count"),
                    "negative_count": r.get("negative_count"),
                    "positive_rate": r.get("positive_rate"),
                    "sources": list(r.get("sources") or []) if isinstance(r.get("sources"), list) else [str(r.get("sources", ""))],
                }
    path_supp = os.path.join(BASE, "reviews", "merged_reviews_supp.json")
    if os.path.exists(path_supp):
        with open(path_supp, "r", encoding="utf-8") as f:
            supp = json.load(f)
        by_spot = defaultdict(list)
        for r in supp.get("reviews", []):
            spot = (r.get("spot_name") or "").strip()
            if spot:
                by_spot[spot].append(r.get("platform", ""))
        for spot, platforms in by_spot.items():
            sources_set = set(merged[spot].get("sources", [])) if spot in merged else set()
            for p in platforms:
                if p:
                    sources_set.add(p)
            count_supp = len(by_spot[spot])
            if spot in merged:
                merged[spot]["total_count"] = merged[spot].get("total_count", 0) + count_supp
                merged[spot]["text_review_count"] = merged[spot].get("text_review_count", 0) + count_supp
                merged[spot]["sources"] = list(sources_set)
            else:
                merged[spot] = {
                    "name": spot,
                    "total_count": count_supp,
                    "text_review_count": count_supp,
                    "avg_rating": None,
                    "positive_count": None,
                    "neutral_count": None,
                    "negative_count": None,
                    "positive_rate": None,
                    "sources": list(sources_set),
                }
    out_path = os.path.join(BASE, "reviews", "review_summary_merged.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(list(merged.values()), f, ensure_ascii=False, indent=2)
    path_csv = os.path.join(OUT, "review_summary_merged.csv")
    os.makedirs(OUT, exist_ok=True)
    fields = ["name", "total_count", "text_review_count", "avg_rating",
              "positive_count", "neutral_count", "negative_count", "positive_rate", "sources"]
    with open(path_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in merged.values():
            row["sources"] = ";".join(row.get("sources", []))
            w.writerow(row)
    print(f"评论汇总(合并多平台): {path_csv} ({len(merged)}个景点，含高德/携程/去哪儿/马蜂窝)")


def export_poi():
    """导出清洗后POI为CSV（同时写 data/poi 与 output/tables，便于论文引用）"""
    with open(os.path.join(BASE, "database", "poi_cleaned.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = data["pois"]
    fields = ["id", "name", "category", "original_type", "address", "town",
              "lng", "lat", "rating", "source", "has_nonheritage", "has_cultural_anchor",
              "nonheritage_match", "cultural_anchors", "query_type"]

    def row_to_csv(r):
        out = dict(r)
        out["nonheritage_match"] = ";".join(r.get("nonheritage_match") or [])
        out["cultural_anchors"] = ";".join(r.get("cultural_anchors") or [])
        return out

    path_poi = os.path.join(BASE, "poi", "nanhai_poi_real.csv")
    os.makedirs(os.path.dirname(path_poi), exist_ok=True)
    with open(path_poi, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row_to_csv(row))
    print(f"POI CSV: {path_poi} ({len(rows)}条)")

    path_table = os.path.join(OUT, "poi_cleaned.csv")
    os.makedirs(OUT, exist_ok=True)
    with open(path_table, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row_to_csv(row))
    print(f"POI 表格(最终): {path_table} ({len(rows)}条)")


def export_entities():
    """导出文化实体为CSV"""
    with open(os.path.join(BASE, "database", "culture_entities.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = data["entities"]
    path = os.path.join(OUT, "culture_entities.csv")
    fields = ["id", "name", "type", "mentions", "confidence", "source_count", "weight", "sources"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            row["sources"] = ";".join(row.get("sources", []))
            w.writerow(row)
    print(f"实体CSV: {path} ({len(rows)}条)")


def export_experience():
    """导出体验度评分为CSV"""
    with open(os.path.join(OUT, "experience_scores.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    path = os.path.join(OUT, "experience_scores.csv")
    fields = ["name", "category", "town", "rating", "has_nonheritage",
              "total_score", "level", "score_rating", "score_review",
              "score_positive", "score_culture", "score_photos"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(data)
    print(f"体验度CSV: {path} ({len(data)}条)")


def export_coupling():
    """导出耦合分析为CSV"""
    with open(os.path.join(BASE, "database", "coupling_results.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for item in data["strong_coupling"]:
        rows.append({"status": "强耦合", "culture": item["culture_element"],
                      "scenic": item["scenic_spot"], "match_type": item["match_type"],
                      "notes": item["notes"]})
    for item in data["misalignment"]:
        rows.append({"status": "错位", "culture": item["culture_element"],
                      "scenic": item["scenic_spot"], "match_type": item["match_type"],
                      "notes": item["notes"]})
    for item in data["missing_A"]:
        rows.append({"status": "缺失A(文化未转化)", "culture": item["culture_element"],
                      "scenic": "", "match_type": item.get("level", ""),
                      "notes": item["reason"]})
    for item in data["missing_B"]:
        rows.append({"status": "缺失B(有形无魂)", "culture": "",
                      "scenic": item["scenic_spot"], "match_type": item.get("category", ""),
                      "notes": item["reason"]})

    path = os.path.join(OUT, "coupling_analysis.csv")
    fields = ["status", "culture", "scenic", "match_type", "notes"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"耦合CSV: {path} ({len(rows)}条)")


def export_spatial():
    """导出镇街空间统计为CSV"""
    with open(os.path.join(OUT, "spatial_analysis_results.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for town, stats in data["town_stats"].items():
        rows.append({
            "town": town,
            "poi_count": stats["poi_count"],
            "nh_count": stats["nh_count"],
            "total_resources": stats["total_resources"],
            "culture_density": stats["culture_density"],
            "tourism_density": stats["tourism_density"],
        })
    rows.sort(key=lambda x: -x["total_resources"])

    path = os.path.join(OUT, "spatial_town_stats.csv")
    fields = ["town", "poi_count", "nh_count", "total_resources", "culture_density", "tourism_density"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"镇街统计CSV: {path} ({len(rows)}条)")


def export_nonheritage():
    """导出非遗数据为CSV"""
    with open(os.path.join(BASE, "gis", "nanhai_nonheritage.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    path = os.path.join(OUT, "nonheritage.csv")
    fields = ["name", "level", "town", "lng", "lat", "category", "geocode_source", "geocode_address"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(data)
    print(f"非遗CSV: {path} ({len(data)}条)")


if __name__ == "__main__":
    print("=" * 50)
    print("导出所有结果数据为CSV表格")
    print("=" * 50)
    os.makedirs(OUT, exist_ok=True)
    export_reviews()
    export_review_summary()
    export_poi()
    export_reviews_detail()
    build_and_export_review_summary_merged()
    export_entities()
    export_experience()
    export_coupling()
    export_spatial()
    export_nonheritage()
    print("\n全部完成！")
