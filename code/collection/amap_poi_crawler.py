#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
高德地图POI数据采集工具
采集佛山市南海区文旅相关兴趣点数据

使用前请在 config 中填入你的高德 Web API Key
申请地址: https://console.amap.com/dev/key/app
"""

import requests
import json
import time
import os
import csv
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "data", "poi")

CONFIG = {
    "amap_key": "YOUR_AMAP_KEY_HERE",
    "city": "佛山",
    "district": "南海区",
    "search_types": {
        "旅游景点": "110000",
        "风景名胜": "110100",
        "公园广场": "110101",
        "博物馆": "140100",
        "展览馆": "140200",
        "图书馆": "140300",
        "科技馆": "140400",
        "文化宫": "140500",
        "影剧院": "140600",
        "体育场馆": "140700",
        "宗教场所": "160000",
        "历史建筑": "110206",
        "纪念馆": "110205",
        "美术馆": "140201",
    },
    "keyword_searches": [
        "非遗", "传习所", "古村", "古镇", "祠堂", "庙宇",
        "博物馆", "纪念馆", "文化馆", "历史建筑", "遗址",
        "醒狮", "龙舟", "武术", "咏春", "书院",
    ],
    "request_interval": 0.3,
    "page_size": 25,
}


def search_poi_by_type(amap_key, type_code, type_name, city="佛山", district="南海区"):
    """按POI类型编码检索"""
    all_pois = []
    page = 1

    while True:
        params = {
            "key": amap_key,
            "types": type_code,
            "city": city,
            "citylimit": "true",
            "offset": CONFIG["page_size"],
            "page": page,
            "extensions": "all",
            "output": "json",
        }

        try:
            resp = requests.get("https://restapi.amap.com/v3/place/text", params=params, timeout=10)
            data = resp.json()

            if data.get("status") != "1":
                print(f"  API错误: {data.get('info', 'unknown')}")
                break

            pois = data.get("pois", [])
            if not pois:
                break

            for poi in pois:
                ad = poi.get("ad_info", {})
                if district and district not in poi.get("adname", ""):
                    continue

                location = poi.get("location", "")
                lng, lat = ("", "")
                if location and "," in location:
                    lng, lat = location.split(",")

                all_pois.append({
                    "name": poi.get("name", ""),
                    "type_query": type_name,
                    "type": poi.get("type", ""),
                    "typecode": poi.get("typecode", ""),
                    "address": poi.get("address", ""),
                    "pname": poi.get("pname", ""),
                    "cityname": poi.get("cityname", ""),
                    "adname": poi.get("adname", ""),
                    "lng": lng,
                    "lat": lat,
                    "tel": poi.get("tel", ""),
                    "rating": poi.get("biz_ext", {}).get("rating", ""),
                    "cost": poi.get("biz_ext", {}).get("cost", ""),
                    "photos": len(poi.get("photos", [])),
                    "id": poi.get("id", ""),
                })

            total = int(data.get("count", 0))
            if page * CONFIG["page_size"] >= total:
                break
            page += 1
            time.sleep(CONFIG["request_interval"])

        except Exception as e:
            print(f"  请求异常: {e}")
            break

    return all_pois


def search_poi_by_keyword(amap_key, keyword, city="佛山", district="南海区"):
    """按关键词检索"""
    all_pois = []
    page = 1

    while True:
        params = {
            "key": amap_key,
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "offset": CONFIG["page_size"],
            "page": page,
            "extensions": "all",
            "output": "json",
        }

        try:
            resp = requests.get("https://restapi.amap.com/v3/place/text", params=params, timeout=10)
            data = resp.json()

            if data.get("status") != "1":
                break

            pois = data.get("pois", [])
            if not pois:
                break

            for poi in pois:
                if district and district not in poi.get("adname", ""):
                    continue

                location = poi.get("location", "")
                lng, lat = ("", "")
                if location and "," in location:
                    lng, lat = location.split(",")

                all_pois.append({
                    "name": poi.get("name", ""),
                    "type_query": f"关键词:{keyword}",
                    "type": poi.get("type", ""),
                    "typecode": poi.get("typecode", ""),
                    "address": poi.get("address", ""),
                    "pname": poi.get("pname", ""),
                    "cityname": poi.get("cityname", ""),
                    "adname": poi.get("adname", ""),
                    "lng": lng,
                    "lat": lat,
                    "tel": poi.get("tel", ""),
                    "rating": poi.get("biz_ext", {}).get("rating", ""),
                    "cost": poi.get("biz_ext", {}).get("cost", ""),
                    "photos": len(poi.get("photos", [])),
                    "id": poi.get("id", ""),
                })

            total = int(data.get("count", 0))
            if page * CONFIG["page_size"] >= total:
                break
            page += 1
            time.sleep(CONFIG["request_interval"])

        except Exception as e:
            print(f"  请求异常: {e}")
            break

    return all_pois


def deduplicate_pois(pois):
    """根据高德POI ID去重"""
    seen = {}
    for poi in pois:
        pid = poi["id"]
        if pid and pid not in seen:
            seen[pid] = poi
        elif not pid:
            key = f"{poi['name']}_{poi['lng']}_{poi['lat']}"
            if key not in seen:
                seen[key] = poi
    return list(seen.values())


def save_results(pois, output_dir):
    """保存采集结果"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = os.path.join(output_dir, f"nanhai_poi_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "crawl_time": timestamp,
            "total_count": len(pois),
            "pois": pois,
        }, f, ensure_ascii=False, indent=2)
    print(f"JSON已保存: {json_path}")

    csv_path = os.path.join(output_dir, f"nanhai_poi_{timestamp}.csv")
    if pois:
        fields = list(pois[0].keys())
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(pois)
        print(f"CSV已保存: {csv_path}")

    return json_path, csv_path


def run_full_crawl():
    """执行完整采集流程"""
    print("=" * 60)
    print("南海区文旅POI数据采集")
    print("=" * 60)

    key = CONFIG["amap_key"]
    if key == "YOUR_AMAP_KEY_HERE":
        print("\n[警告] 未配置高德API Key，将生成示例数据")
        print("请前往 https://console.amap.com/dev/key/app 申请Key")
        print("然后修改本文件中 CONFIG['amap_key'] 的值\n")
        generate_sample_data()
        return

    all_pois = []

    print("\n--- 按类型检索 ---")
    for type_name, type_code in CONFIG["search_types"].items():
        print(f"检索: {type_name} ({type_code})")
        pois = search_poi_by_type(key, type_code, type_name)
        print(f"  找到 {len(pois)} 条")
        all_pois.extend(pois)
        time.sleep(CONFIG["request_interval"])

    print("\n--- 按关键词检索 ---")
    for keyword in CONFIG["keyword_searches"]:
        print(f"检索: {keyword}")
        pois = search_poi_by_keyword(key, keyword)
        print(f"  找到 {len(pois)} 条")
        all_pois.extend(pois)
        time.sleep(CONFIG["request_interval"])

    print(f"\n原始数据: {len(all_pois)} 条")
    all_pois = deduplicate_pois(all_pois)
    print(f"去重后: {len(all_pois)} 条")

    save_results(all_pois, OUTPUT_DIR)
    print("\n采集完成！")


def generate_sample_data():
    """
    生成南海区文旅POI示例数据
    数据基于公开信息整理，坐标为近似值，用于开发和分析流程验证
    """
    sample_pois = [
        {"name": "西樵山风景名胜区", "type_query": "旅游景点", "type": "风景名胜;风景名胜;国家级景点", "typecode": "110100", "address": "西樵镇环山大道山南路", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.968", "lat": "22.932", "tel": "0757-86880980", "rating": "4.5", "cost": "70", "photos": 15, "id": "B02F3080HH"},
        {"name": "南海博物馆", "type_query": "博物馆", "type": "科教文化服务;博物馆;博物馆", "typecode": "140100", "address": "桂城街道灯湖西路28号", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.143", "lat": "23.027", "tel": "0757-86289610", "rating": "4.3", "cost": "", "photos": 8, "id": "B02F308001"},
        {"name": "南海影视城", "type_query": "旅游景点", "type": "风景名胜;风景名胜;影视城", "typecode": "110100", "address": "西樵镇西岸村", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.943", "lat": "22.942", "tel": "0757-86893228", "rating": "4.1", "cost": "80", "photos": 12, "id": "B02F308002"},
        {"name": "黄飞鸿纪念馆", "type_query": "纪念馆", "type": "科教文化服务;展览馆;纪念馆", "typecode": "110205", "address": "西樵镇黄飞鸿大道", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.961", "lat": "22.937", "tel": "", "rating": "4.2", "cost": "", "photos": 6, "id": "B02F308003"},
        {"name": "康有为故居", "type_query": "历史建筑", "type": "风景名胜;风景名胜;名人故居", "typecode": "110206", "address": "丹灶镇银河苏村", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.009", "lat": "23.005", "tel": "", "rating": "4.0", "cost": "", "photos": 5, "id": "B02F308004"},
        {"name": "南海观音寺", "type_query": "宗教场所", "type": "风景名胜;风景名胜;寺庙", "typecode": "160000", "address": "西樵镇西樵山", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.970", "lat": "22.928", "tel": "", "rating": "4.4", "cost": "20", "photos": 10, "id": "B02F308005"},
        {"name": "松塘古村", "type_query": "关键词:古村", "type": "风景名胜;风景名胜;古村落", "typecode": "110100", "address": "西樵镇上金瓯村委会松塘村", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.942", "lat": "22.920", "tel": "", "rating": "4.3", "cost": "", "photos": 8, "id": "B02F308006"},
        {"name": "烟桥古村", "type_query": "关键词:古村", "type": "风景名胜;风景名胜;古村落", "typecode": "110100", "address": "九江镇烟南村", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.013", "lat": "22.780", "tel": "", "rating": "4.0", "cost": "", "photos": 4, "id": "B02F308007"},
        {"name": "简村北帝庙", "type_query": "宗教场所", "type": "风景名胜;风景名胜;庙宇", "typecode": "160000", "address": "狮山镇简村", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.115", "lat": "23.072", "tel": "", "rating": "3.8", "cost": "", "photos": 2, "id": "B02F308008"},
        {"name": "千灯湖公园", "type_query": "公园广场", "type": "风景名胜;公园;城市公园", "typecode": "110101", "address": "桂城街道灯湖西路", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.141", "lat": "23.032", "tel": "", "rating": "4.6", "cost": "", "photos": 20, "id": "B02F308009"},
        {"name": "南海龙舟广场", "type_query": "关键词:龙舟", "type": "体育休闲服务;运动场馆;综合体育场馆", "typecode": "140700", "address": "桂城街道", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.153", "lat": "23.029", "tel": "", "rating": "4.0", "cost": "", "photos": 3, "id": "B02F308010"},
        {"name": "叠滘弯道赛龙船", "type_query": "关键词:龙舟", "type": "风景名胜;风景名胜;民俗活动", "typecode": "110100", "address": "桂城街道叠滘村", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.124", "lat": "23.043", "tel": "", "rating": "4.5", "cost": "", "photos": 5, "id": "B02F308011"},
        {"name": "盐步老龙礼俗传承基地", "type_query": "关键词:非遗", "type": "科教文化服务;文化宫;文化活动中心", "typecode": "140500", "address": "大沥镇盐步", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.142", "lat": "23.069", "tel": "", "rating": "", "cost": "", "photos": 1, "id": "B02F308012"},
        {"name": "南海醒狮传承基地", "type_query": "关键词:醒狮", "type": "科教文化服务;文化宫;文化活动中心", "typecode": "140500", "address": "西樵镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.955", "lat": "22.936", "tel": "", "rating": "", "cost": "", "photos": 2, "id": "B02F308013"},
        {"name": "黄飞鸿中联电缆武术龙狮协会", "type_query": "关键词:醒狮", "type": "体育休闲服务;运动场馆;武术馆", "typecode": "140700", "address": "西樵镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.958", "lat": "22.938", "tel": "", "rating": "4.1", "cost": "", "photos": 3, "id": "B02F308014"},
        {"name": "佛山十番传承基地", "type_query": "关键词:非遗", "type": "科教文化服务;文化宫;文化活动中心", "typecode": "140500", "address": "桂城街道", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.160", "lat": "23.020", "tel": "", "rating": "", "cost": "", "photos": 1, "id": "B02F308015"},
        {"name": "咏春拳叶问宗支传承基地", "type_query": "关键词:咏春", "type": "体育休闲服务;运动场馆;武术馆", "typecode": "140700", "address": "桂城街道", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.150", "lat": "23.025", "tel": "", "rating": "4.2", "cost": "", "photos": 2, "id": "B02F308016"},
        {"name": "九江双蒸博物馆", "type_query": "博物馆", "type": "科教文化服务;博物馆;博物馆", "typecode": "140100", "address": "九江镇沙口工业区", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.028", "lat": "22.793", "tel": "0757-86508800", "rating": "4.3", "cost": "", "photos": 7, "id": "B02F308017"},
        {"name": "南海区文化馆", "type_query": "文化宫", "type": "科教文化服务;文化宫;文化馆", "typecode": "140500", "address": "桂城街道南海大道北64号", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.148", "lat": "23.038", "tel": "0757-86393891", "rating": "4.0", "cost": "", "photos": 3, "id": "B02F308018"},
        {"name": "西樵山书院遗址", "type_query": "关键词:书院", "type": "风景名胜;风景名胜;遗址", "typecode": "110100", "address": "西樵镇西樵山", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.967", "lat": "22.935", "tel": "", "rating": "3.5", "cost": "", "photos": 2, "id": "B02F308019"},
        {"name": "宝峰寺", "type_query": "宗教场所", "type": "风景名胜;风景名胜;寺庙", "typecode": "160000", "address": "西樵镇西樵山", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.972", "lat": "22.930", "tel": "", "rating": "4.1", "cost": "", "photos": 4, "id": "B02F308020"},
        {"name": "南海湿地公园", "type_query": "公园广场", "type": "风景名胜;公园;城市公园", "typecode": "110101", "address": "桂城街道", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.159", "lat": "23.015", "tel": "", "rating": "4.2", "cost": "", "photos": 6, "id": "B02F308021"},
        {"name": "大沥镇锦龙盛会传承基地", "type_query": "关键词:非遗", "type": "科教文化服务;文化宫;文化活动中心", "typecode": "140500", "address": "大沥镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.089", "lat": "23.068", "tel": "", "rating": "", "cost": "", "photos": 1, "id": "B02F308022"},
        {"name": "里水梦里水乡", "type_query": "旅游景点", "type": "风景名胜;风景名胜;水乡", "typecode": "110100", "address": "里水镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.135", "lat": "23.118", "tel": "", "rating": "4.4", "cost": "60", "photos": 12, "id": "B02F308023"},
        {"name": "贤鲁岛", "type_query": "旅游景点", "type": "风景名胜;风景名胜;岛屿", "typecode": "110100", "address": "里水镇贤鲁岛", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.153", "lat": "23.142", "tel": "", "rating": "4.2", "cost": "", "photos": 8, "id": "B02F308024"},
        {"name": "官窑生菜会传承基地", "type_query": "关键词:非遗", "type": "科教文化服务;文化宫;文化活动中心", "typecode": "140500", "address": "狮山镇官窑", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.038", "lat": "23.102", "tel": "", "rating": "", "cost": "", "photos": 1, "id": "B02F308025"},
        {"name": "藤编里水传承基地", "type_query": "关键词:非遗", "type": "科教文化服务;文化宫;文化活动中心", "typecode": "140500", "address": "里水镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.130", "lat": "23.115", "tel": "", "rating": "", "cost": "", "photos": 1, "id": "B02F308026"},
        {"name": "金箔锻造技艺传习所", "type_query": "关键词:非遗", "type": "科教文化服务;文化宫;文化活动中心", "typecode": "140500", "address": "大沥镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.085", "lat": "23.065", "tel": "", "rating": "", "cost": "", "photos": 0, "id": "B02F308027"},
        {"name": "平洲玉器街", "type_query": "旅游景点", "type": "风景名胜;风景名胜;特色街区", "typecode": "110100", "address": "桂城街道平洲", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.190", "lat": "23.005", "tel": "", "rating": "4.0", "cost": "", "photos": 5, "id": "B02F308028"},
        {"name": "南海体育中心", "type_query": "体育场馆", "type": "体育休闲服务;运动场馆;综合体育场馆", "typecode": "140700", "address": "桂城街道南海大道北", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.152", "lat": "23.035", "tel": "", "rating": "4.0", "cost": "", "photos": 3, "id": "B02F308029"},
        {"name": "乐安花灯会传承基地", "type_query": "关键词:非遗", "type": "科教文化服务;文化宫;文化活动中心", "typecode": "140500", "address": "桂城街道", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.145", "lat": "23.040", "tel": "", "rating": "", "cost": "", "photos": 0, "id": "B02F308030"},
        {"name": "孔村至圣家庙", "type_query": "关键词:祠堂", "type": "风景名胜;风景名胜;祠堂", "typecode": "110100", "address": "里水镇和顺孔村", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.145", "lat": "23.105", "tel": "", "rating": "3.9", "cost": "", "photos": 2, "id": "B02F308031"},
        {"name": "仙岗古村", "type_query": "关键词:古村", "type": "风景名胜;风景名胜;古村落", "typecode": "110100", "address": "丹灶镇仙岗村", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.005", "lat": "23.010", "tel": "", "rating": "3.8", "cost": "", "photos": 3, "id": "B02F308032"},
        {"name": "显纲村革命旧址", "type_query": "关键词:遗址", "type": "风景名胜;风景名胜;革命遗址", "typecode": "110206", "address": "九江镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.020", "lat": "22.790", "tel": "", "rating": "", "cost": "", "photos": 1, "id": "B02F308033"},
        {"name": "丹灶葛洪炼丹传说纪念地", "type_query": "关键词:非遗", "type": "风景名胜;风景名胜;纪念地", "typecode": "110205", "address": "丹灶镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.015", "lat": "23.018", "tel": "", "rating": "3.5", "cost": "", "photos": 2, "id": "B02F308034"},
        {"name": "南海图书馆", "type_query": "图书馆", "type": "科教文化服务;图书馆;图书馆", "typecode": "140300", "address": "桂城街道南海大道北", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.146", "lat": "23.036", "tel": "0757-86230391", "rating": "4.3", "cost": "", "photos": 4, "id": "B02F308035"},
        {"name": "西城村古建筑群", "type_query": "关键词:历史建筑", "type": "风景名胜;风景名胜;古建筑", "typecode": "110206", "address": "西樵镇西城村", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "112.950", "lat": "22.925", "tel": "", "rating": "3.7", "cost": "", "photos": 2, "id": "B02F308036"},
        {"name": "南海九江吴家大院", "type_query": "关键词:历史建筑", "type": "风景名胜;风景名胜;古建筑", "typecode": "110206", "address": "九江镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.032", "lat": "22.788", "tel": "", "rating": "4.0", "cost": "", "photos": 3, "id": "B02F308037"},
        {"name": "九江鱼花养殖基地", "type_query": "关键词:非遗", "type": "风景名胜;风景名胜;特色基地", "typecode": "110100", "address": "九江镇", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.025", "lat": "22.785", "tel": "", "rating": "", "cost": "", "photos": 1, "id": "B02F308038"},
        {"name": "南海区非遗展示馆", "type_query": "关键词:非遗", "type": "科教文化服务;展览馆;展览馆", "typecode": "140200", "address": "桂城街道", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.150", "lat": "23.030", "tel": "", "rating": "4.1", "cost": "", "photos": 3, "id": "B02F308039"},
        {"name": "映月湖公园", "type_query": "公园广场", "type": "风景名胜;公园;城市公园", "typecode": "110101", "address": "桂城街道", "pname": "广东省", "cityname": "佛山市", "adname": "南海区", "lng": "113.155", "lat": "23.023", "tel": "", "rating": "4.3", "cost": "", "photos": 7, "id": "B02F308040"},
    ]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    json_path = os.path.join(OUTPUT_DIR, "nanhai_poi_sample.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "crawl_time": "sample_data",
            "note": "示例数据，基于公开信息整理。获取真实数据请配置高德API Key后重新运行。",
            "total_count": len(sample_pois),
            "pois": sample_pois,
        }, f, ensure_ascii=False, indent=2)

    csv_path = os.path.join(OUTPUT_DIR, "nanhai_poi_sample.csv")
    fields = list(sample_pois[0].keys())
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sample_pois)

    print(f"示例数据已生成: {len(sample_pois)} 条POI")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")


if __name__ == "__main__":
    run_full_crawl()
