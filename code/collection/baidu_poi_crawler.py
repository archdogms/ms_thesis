#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
百度地图 Place API v2.0 POI 爬虫

以南海区7个镇街中心点为圆心，半径5km，搜索文旅相关关键词。
支持断点续跑、进度条、去重。
"""

import os
import json
import time
import math
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
POI_DIR = os.path.join(DATA_DIR, "poi")
OUTPUT_PATH = os.path.join(POI_DIR, "nanhai_poi_baidu.json")
PROGRESS_PATH = os.path.join(POI_DIR, "baidu_crawl_progress.json")

BAIDU_AK = "NuA8hFYgnt9n0aj1FfCeLP1gDr7RsQKp"
SEARCH_URL = "https://api.map.baidu.com/place/v2/search"

TOWN_CENTERS = {
    "桂城街道": (113.1427, 23.0268),
    "西樵镇":   (112.9690, 22.9750),
    "九江镇":   (112.9820, 22.8470),
    "丹灶镇":   (112.9900, 23.0580),
    "狮山镇":   (113.1400, 23.0880),
    "大沥镇":   (113.0700, 23.0600),
    "里水镇":   (113.1200, 23.1400),
}

SEARCH_KEYWORDS = [
    "景点", "博物馆", "祠堂", "古迹", "公园",
    "寺庙", "非遗", "文化", "纪念馆", "故居",
    "古村", "古建筑", "遗址", "塔", "庙",
    "书院", "艺术馆", "展览馆", "旅游",
]

SEARCH_RADIUS = 5000  # 5km


def load_progress():
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed_tasks": [], "pois": {}}


def save_progress(progress):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def search_pois(keyword, lat, lng, page_num=0):
    """调用百度Place API v2.0搜索POI"""
    params = {
        "query": keyword,
        "location": f"{lat},{lng}",
        "radius": SEARCH_RADIUS,
        "output": "json",
        "ak": BAIDU_AK,
        "scope": 2,
        "page_size": 20,
        "page_num": page_num,
        "coord_type": 1,  # GPS坐标 → 百度坐标在服务端自动转换
    }

    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=10)
        data = resp.json()

        if data.get("status") != 0:
            msg = data.get("message", "unknown")
            if "AK" in msg or "quota" in msg.lower():
                print(f"  ⚠ API错误: {msg}")
                return None, False
            return [], True

        results = data.get("results", [])
        has_more = len(results) == 20
        return results, has_more

    except Exception as e:
        print(f"  请求异常: {e}")
        return None, False


def parse_poi(raw):
    """解析百度API返回的单个POI"""
    loc = raw.get("location", {})
    detail = raw.get("detail_info", {})

    return {
        "name": raw.get("name", ""),
        "address": raw.get("address", ""),
        "province": raw.get("province", ""),
        "city": raw.get("city", ""),
        "area": raw.get("area", ""),
        "lng": loc.get("lng"),
        "lat": loc.get("lat"),
        "uid": raw.get("uid", ""),
        "tag": detail.get("tag", ""),
        "type": detail.get("type", ""),
        "overall_rating": detail.get("overall_rating", ""),
        "comment_num": detail.get("comment_num", ""),
        "source": "baidu_api",
    }


def is_nanhai(poi):
    """过滤：只保留南海区的POI"""
    area = poi.get("area", "")
    address = poi.get("address", "")
    if "南海" in area:
        return True
    if "南海" in address:
        return True
    return False


def crawl():
    os.makedirs(POI_DIR, exist_ok=True)
    progress = load_progress()
    completed = set(progress["completed_tasks"])
    all_pois = progress.get("pois", {})

    tasks = []
    for town, (lng, lat) in TOWN_CENTERS.items():
        for kw in SEARCH_KEYWORDS:
            task_id = f"{town}_{kw}"
            tasks.append((task_id, town, kw, lat, lng))

    remaining = [t for t in tasks if t[0] not in completed]
    total = len(tasks)
    done = total - len(remaining)

    print(f"百度POI爬取: 共{total}个搜索任务, 已完成{done}, 剩余{len(remaining)}")
    print(f"已累计POI: {len(all_pois)} 条\n")

    for i, (task_id, town, kw, lat, lng) in enumerate(remaining):
        print(f"[{done + i + 1}/{total}] {town} - {kw}", end="", flush=True)

        page = 0
        task_count = 0
        while True:
            results, has_more = search_pois(kw, lat, lng, page_num=page)

            if results is None:
                print(" API限制，等待3秒...")
                time.sleep(3)
                results, has_more = search_pois(kw, lat, lng, page_num=page)
                if results is None:
                    print(" 跳过")
                    break

            for raw in results:
                poi = parse_poi(raw)
                uid = poi["uid"]
                if uid and uid not in all_pois and is_nanhai(poi):
                    poi["search_town"] = town
                    poi["search_keyword"] = kw
                    all_pois[uid] = poi
                    task_count += 1

            if not has_more or page >= 9:
                break
            page += 1
            time.sleep(0.4)

        completed.add(task_id)
        progress["completed_tasks"] = list(completed)
        progress["pois"] = all_pois
        save_progress(progress)

        print(f"  +{task_count} (总计: {len(all_pois)})")
        time.sleep(0.35)

    poi_list = list(all_pois.values())

    output = {
        "total": len(poi_list),
        "source": "baidu_place_api_v2",
        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "search_config": {
            "radius_m": SEARCH_RADIUS,
            "keywords": SEARCH_KEYWORDS,
            "towns": list(TOWN_CENTERS.keys()),
        },
        "pois": poi_list,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n完成！共 {len(poi_list)} 条南海区POI")
    print(f"保存至: {OUTPUT_PATH}")

    return poi_list


if __name__ == "__main__":
    crawl()
