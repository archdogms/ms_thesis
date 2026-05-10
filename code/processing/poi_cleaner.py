#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
POI数据清洗与标准化工具（三源融合版）
融合高德API + Shapefile + 百度API三个数据源，并关联文化载体锚点

数据源：
    1. nanhai_poi_real.json — 高德 API 爬取（~1,353条，含评分）
    2. nanhai_culture_poi_shp.json — 2024 佛山市 POI shapefile 中筛选的
       南海区文旅相关 POI（~12,906条，无评分但覆盖面广）
    3. nanhai_poi_baidu.json — 百度 Place API 爬取（含评分和评论数）

融合策略：
    - 以 shapefile 为底座（覆盖面广）
    - 高德 API 数据补充评分字段
    - 百度 API 数据补充新增POI和评分/评论数
    - 按 POI 名称去重（同名视为同一POI，保留更完整的记录）

输出：poi_cleaned.json
"""

import os
import json
import re
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "database")


CATEGORY_MAP = {
    "自然景观": ["风景名胜", "山", "湖", "岛", "湿地", "自然", "河", "江", "瀑布", "溪", "泉",
                  "生态", "森林", "峡谷", "洞穴", "石燕岩", "白云洞", "碧玉洞"],
    "人文古迹": ["古村", "古建筑", "遗址", "故居", "祠堂", "牌坊", "古镇", "古庙", "古桥",
                  "书院", "宗祠", "家庙", "旧址", "遗迹", "文物", "古墓", "碑", "塔",
                  "炮楼", "门楼", "镬耳", "青砖"],
    "非遗体验": ["非遗", "传习所", "传承基地", "技艺", "武术馆", "武馆", "龙舟",
                  "醒狮", "龙狮", "拳术", "咏春", "洪拳", "太极", "藤编", "灰塑",
                  "剪纸", "金箔", "缫丝", "花灯"],
    "文化场馆": ["博物馆", "纪念馆", "展览馆", "文化馆", "图书馆", "美术馆",
                  "艺术馆", "科技馆", "天文馆", "规划馆", "档案馆", "画廊", "艺术中心"],
    "宗教场所": ["寺", "庙", "观", "教堂", "宗教", "庵", "道观", "佛", "天后宫",
                  "北帝", "关帝", "仙", "神"],
    "休闲娱乐": ["影视城", "度假", "乐园", "游乐", "温泉", "漂流", "农庄",
                  "庄园", "酒店", "民宿", "水上", "游艇", "高尔夫", "影城",
                  "电影", "KTV", "桌游", "密室"],
    "特色街区": ["玉器街", "商业街", "步行街", "美食街", "老街", "古街",
                  "夜市", "创意园", "产业园", "孵化器"],
    "公园绿地": ["公园", "广场", "花园", "绿道", "湿地公园", "植物园", "滨河"],
    "体育设施": ["体育", "运动", "球场", "游泳", "健身", "武术", "足球", "篮球", "羽毛球",
                  "网球", "溜冰", "攀岩"],
    "名人故居": ["故居", "纪念堂", "祖居", "旧居"],
    "教育研学": ["学校", "书院", "研学", "教育基地", "科普", "实验室"],
}

NONHERITAGE_KEYWORDS = {
    "醒狮": ["醒狮", "狮舞", "龙狮"],
    "龙舟": ["龙舟", "赛龙", "龙船"],
    "十番音乐": ["十番"],
    "咏春拳": ["咏春", "叶问"],
    "洪拳": ["洪拳"],
    "白眉拳": ["白眉"],
    "藤编": ["藤编"],
    "灰塑": ["灰塑"],
    "九江双蒸酒": ["双蒸", "九江酒"],
    "粤曲": ["粤曲", "粤剧"],
    "生菜会": ["生菜会"],
    "花灯": ["花灯", "灯会"],
    "金箔": ["金箔"],
    "龙母诞": ["龙母"],
    "鱼花": ["鱼花"],
}


def load_cultural_anchors():
    """加载文化载体锚点表"""
    anchor_path = os.path.join(OUTPUT_DIR, "cultural_anchors.json")
    if not os.path.exists(anchor_path):
        return []
    with open(anchor_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("anchors", [])


def load_poi_data():
    """加载并融合双源POI数据"""
    poi_dir = os.path.join(DATA_DIR, "poi")
    all_pois = []
    seen_names = {}

    real_path = os.path.join(poi_dir, "nanhai_poi_real.json")
    if os.path.exists(real_path):
        with open(real_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        api_pois = data.get("pois", [])
        for p in api_pois:
            name = p.get("name", "").strip()
            if name:
                seen_names[name] = p
            all_pois.append(p)
        print(f"[API数据] {len(api_pois)} 条")

    shp_path = os.path.join(poi_dir, "nanhai_culture_poi_shp.json")
    if os.path.exists(shp_path):
        with open(shp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        shp_pois = data.get("pois", [])
        added = 0
        for p in shp_pois:
            name = p.get("name", "").strip()
            if name and name not in seen_names:
                seen_names[name] = True
                all_pois.append(p)
                added += 1
        print(f"[Shapefile数据] {len(shp_pois)} 条, 新增去重后 {added} 条")

    # 3) 百度 API POI
    baidu_path = os.path.join(poi_dir, "nanhai_poi_baidu.json")
    if os.path.exists(baidu_path):
        with open(baidu_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        baidu_pois = data.get("pois", [])
        added = 0
        enriched = 0
        for p in baidu_pois:
            name = p.get("name", "").strip()
            if not name:
                continue
            if name in seen_names:
                existing = seen_names[name]
                if isinstance(existing, dict):
                    if not existing.get("rating") and p.get("overall_rating"):
                        try:
                            existing["rating"] = float(p["overall_rating"])
                            enriched += 1
                        except (ValueError, TypeError):
                            pass
            else:
                poi_entry = {
                    "name": name,
                    "address": p.get("address", ""),
                    "lng": p.get("lng"),
                    "lat": p.get("lat"),
                    "type": p.get("tag", ""),
                    "rating": p.get("overall_rating", ""),
                    "source": "baidu_api",
                }
                seen_names[name] = poi_entry
                all_pois.append(poi_entry)
                added += 1
        print(f"[百度数据] {len(baidu_pois)} 条, 新增 {added} 条, 评分补充 {enriched} 条")

    print(f"[三源融合] {len(all_pois)} 条")
    return all_pois


AMAP_TYPE_MAP = {
    "110": "自然景观",
    "1101": "自然景观",
    "1102": "人文古迹",
    "1103": "公园绿地",
    "1104": "宗教场所",
    "1105": "文化场馆",
    "1201": "休闲娱乐",
    "1202": "休闲娱乐",
    "1203": "体育设施",
    "1401": "教育研学",
    "080": "休闲娱乐",
}

def classify_poi(poi):
    """自动分类POI（优先关键词匹配，其次高德类型编码）"""
    name = poi.get("name", "")
    poi_type = poi.get("type", "")
    combined = f"{name} {poi_type}"

    for category, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in combined:
                return category

    type_code = poi.get("typecode", "")
    if type_code:
        for prefix, cat in AMAP_TYPE_MAP.items():
            if type_code.startswith(prefix):
                return cat

    return "其他"


def match_nonheritage(poi):
    """匹配关联的非遗项目"""
    name = poi.get("name", "")
    poi_type = poi.get("type", "")
    combined = f"{name} {poi_type}"

    matched = []
    for nh_name, keywords in NONHERITAGE_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                matched.append(nh_name)
                break

    return matched


def determine_town(poi):
    """根据坐标或地址判断所属镇街"""
    address = poi.get("address", "")
    name = poi.get("name", "")
    combined = f"{name} {address}"

    town_keywords = {
        "桂城街道": ["桂城", "千灯湖", "映月", "平洲", "叠滘"],
        "西樵镇": ["西樵", "黄飞鸿"],
        "九江镇": ["九江"],
        "丹灶镇": ["丹灶", "康有为", "仙岗"],
        "狮山镇": ["狮山", "官窑", "简村"],
        "大沥镇": ["大沥", "盐步", "黄岐"],
        "里水镇": ["里水", "贤鲁", "和顺", "孔村", "梦里水乡"],
    }

    for town, keywords in town_keywords.items():
        for kw in keywords:
            if kw in combined:
                return town

    try:
        lng = float(poi.get("lng", 0))
        lat = float(poi.get("lat", 0))
        if lng > 0 and lat > 0:
            if lng < 112.98 and lat < 22.96:
                return "西樵镇"
            elif lng < 113.05 and lat < 22.82:
                return "九江镇"
            elif lng < 113.05 and lat < 23.05:
                return "丹灶镇"
            elif lng > 113.12 and lat > 23.08:
                return "里水镇"
            elif lng > 113.06 and lat > 23.05:
                return "大沥镇" if lng < 113.12 else "桂城街道"
            elif lat > 23.05:
                return "狮山镇"
            else:
                return "桂城街道"
    except (ValueError, TypeError):
        pass

    return "未知"


import math as _math

def _haversine_m(lng1, lat1, lng2, lat2):
    """两坐标间的距离（米）"""
    R = 6371000
    rlat1, rlat2 = _math.radians(lat1), _math.radians(lat2)
    dlat = rlat2 - rlat1
    dlng = _math.radians(lng2 - lng1)
    a = _math.sin(dlat/2)**2 + _math.cos(rlat1)*_math.cos(rlat2)*_math.sin(dlng/2)**2
    return R * 2 * _math.atan2(_math.sqrt(a), _math.sqrt(1-a))


def match_cultural_anchors(poi, anchors, radius_m=500):
    """匹配500米范围内的文化载体锚点"""
    try:
        plng = float(poi.get("lng", 0))
        plat = float(poi.get("lat", 0))
    except (ValueError, TypeError):
        return []
    if plng < 1 or plat < 1:
        return []
    matches = []
    for a in anchors:
        alng, alat = a.get("lng", 0), a.get("lat", 0)
        if alng < 1 or alat < 1:
            continue
        dist = _haversine_m(plng, plat, alng, alat)
        if dist <= radius_m:
            matches.append({
                "anchor_name": a["name"],
                "anchor_type": a["anchor_type"],
                "distance_m": round(dist),
            })
    matches.sort(key=lambda x: x["distance_m"])
    return matches


OTHER_DISTRICT_NAMES = ["禅城", "顺德", "三水", "高明"]

def clean_and_standardize(pois, anchors=None):
    """清洗并标准化POI数据，关联文化锚点"""
    if anchors is None:
        anchors = []
    cleaned = []
    seen_names = set()
    skipped_district = 0

    for poi in pois:
        name = poi.get("name", "").strip()
        if not name or name in seen_names:
            continue

        addr = str(poi.get("address", ""))
        if any(d in addr and "南海" not in addr for d in OTHER_DISTRICT_NAMES):
            skipped_district += 1
            continue

        seen_names.add(name)

        category = classify_poi(poi)
        nh_matches = match_nonheritage(poi)
        town = determine_town(poi)

        try:
            lng = float(poi.get("lng", 0))
            lat = float(poi.get("lat", 0))
        except (ValueError, TypeError):
            lng, lat = 0, 0

        rating = poi.get("rating", "")
        try:
            rating = float(rating) if rating else 0
        except (ValueError, TypeError):
            rating = 0

        anchor_matches = match_cultural_anchors(poi, anchors) if anchors else []

        cleaned.append({
            "id": poi.get("id", ""),
            "name": name,
            "category": category,
            "original_type": poi.get("type", ""),
            "address": poi.get("address", ""),
            "town": town,
            "lng": lng,
            "lat": lat,
            "rating": rating,
            "nonheritage_match": nh_matches,
            "has_nonheritage": len(nh_matches) > 0,
            "query_type": poi.get("type_query", ""),
            "cultural_anchors": [m["anchor_name"] for m in anchor_matches],
            "has_cultural_anchor": len(anchor_matches) > 0,
            "source": poi.get("source", "api"),
        })

    return cleaned


def save_cleaned_data(cleaned_pois):
    """保存清洗后的数据"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    path = os.path.join(OUTPUT_DIR, "poi_cleaned.json")
    with open(path, "w", encoding="utf-8") as f:
        cat_stats = Counter(p["category"] for p in cleaned_pois)
        town_stats = Counter(p["town"] for p in cleaned_pois)
        nh_count = sum(1 for p in cleaned_pois if p["has_nonheritage"])
        anchor_count = sum(1 for p in cleaned_pois if p.get("has_cultural_anchor"))

        json.dump({
            "total": len(cleaned_pois),
            "category_stats": dict(cat_stats.most_common()),
            "town_stats": dict(town_stats.most_common()),
            "nonheritage_linked": nh_count,
            "cultural_anchor_linked": anchor_count,
            "pois": cleaned_pois,
        }, f, ensure_ascii=False, indent=2)

    print(f"清洗后POI: {path} ({len(cleaned_pois)} 条)")
    print(f"分类统计:")
    for cat, cnt in cat_stats.most_common():
        print(f"  {cat}: {cnt}")
    print(f"镇街分布:")
    for town, cnt in town_stats.most_common():
        print(f"  {town}: {cnt}")
    print(f"关联非遗: {nh_count} 个")
    print(f"关联文化锚点: {anchor_count} 个")


def main():
    print("=" * 60)
    print("POI数据清洗与标准化（三源融合版）")
    print("=" * 60)

    anchors = load_cultural_anchors()
    print(f"文化锚点: {len(anchors)} 条")

    pois = load_poi_data()
    print(f"加载 {len(pois)} 条原始POI")

    cleaned = clean_and_standardize(pois, anchors)
    print(f"清洗后 {len(cleaned)} 条")

    save_cleaned_data(cleaned)
    print("\n完成！")


if __name__ == "__main__":
    main()
