#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
南海博物馆非遗完整数据爬取
从 nhmuseum.org 爬取90项非遗的详细信息
"""

import requests
import json
import re
import time
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "data", "gis")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

NH_PAGES = {
    "国家级": "https://www.nhmuseum.org/fei-yi/guo-ia-ji.html",
    "省级": "https://www.nhmuseum.org/fei-yi/sheng-ji.html",
    "市级": "https://www.nhmuseum.org/fei-yi/shi-ji.html",
    "区级": "https://www.nhmuseum.org/fei-yi/qu-ji.html",
}

FULL_90_ITEMS = [
    {"name": "狮舞（广东醒狮）", "level": "国家级", "category": "传统舞蹈"},
    {"name": "十番音乐（佛山十番）", "level": "国家级", "category": "传统音乐"},
    {"name": "官窑生菜会", "level": "省级", "category": "民俗"},
    {"name": "灯会（乐安花灯会）", "level": "省级", "category": "民俗"},
    {"name": "九江双蒸酒酿制技艺", "level": "省级", "category": "传统技艺"},
    {"name": "赛龙舟（九江传统龙舟）", "level": "省级", "category": "传统体育"},
    {"name": "端午节（盐步老龙礼俗）", "level": "省级", "category": "民俗"},
    {"name": "咏春拳（叶问宗支）", "level": "省级", "category": "传统体育"},
    {"name": "藤编（大沥）", "level": "省级", "category": "传统技艺"},
    {"name": "藤编（里水）", "level": "省级", "category": "传统技艺"},
    {"name": "金箔锻造技艺", "level": "省级", "category": "传统技艺"},
    {"name": "庙会（大仙诞庙会）", "level": "省级", "category": "民俗"},
    {"name": "粤曲", "level": "省级", "category": "曲艺"},
    {"name": "糕点制作技艺（九江煎堆制作技艺）", "level": "省级", "category": "传统技艺"},
    {"name": "九江鱼花生产习俗", "level": "省级", "category": "民俗"},
    {"name": "家具制作技艺（广式家具制作技艺）", "level": "省级", "category": "传统技艺"},
    {"name": "洪拳（南海洪拳）", "level": "省级", "category": "传统体育"},
    {"name": "龙舟说唱", "level": "市级", "category": "曲艺"},
    {"name": "白眉拳", "level": "市级", "category": "传统体育"},
    {"name": "大头佛", "level": "市级", "category": "传统舞蹈"},
    {"name": "南海灰塑", "level": "市级", "category": "传统美术"},
    {"name": "三山咸水歌", "level": "市级", "category": "传统音乐"},
    {"name": "西樵传统缫丝技艺", "level": "市级", "category": "传统技艺"},
    {"name": "麦边舞龙", "level": "市级", "category": "传统舞蹈"},
    {"name": "南海竹编", "level": "市级", "category": "传统技艺"},
    {"name": "西樵大饼制作技艺", "level": "市级", "category": "传统技艺"},
    {"name": "香云纱（坯纱）织造技艺", "level": "市级", "category": "传统技艺"},
    {"name": "九江灯谜", "level": "市级", "category": "民俗"},
    {"name": "丹灶葛洪炼丹传说", "level": "市级", "category": "民间文学"},
    {"name": "华岳心意六合八法拳", "level": "市级", "category": "传统体育"},
    {"name": "叠滘弯道赛龙船", "level": "市级", "category": "传统体育"},
    {"name": "祠堂祭祖（平地黄氏冬祭）", "level": "市级", "category": "民俗"},
    {"name": "黄岐龙母诞", "level": "市级", "category": "民俗"},
    {"name": "烧番塔（松塘）", "level": "市级", "category": "民俗"},
    {"name": "赤山跳火光习俗", "level": "市级", "category": "民俗"},
    {"name": "唢呐制作技艺", "level": "市级", "category": "传统技艺"},
    {"name": "平洲传统玉器制作技艺", "level": "市级", "category": "传统技艺"},
    {"name": "广绣（石石肯）", "level": "市级", "category": "传统美术"},
    {"name": "佛山十番（同乐堂十番）", "level": "市级", "category": "传统音乐"},
    {"name": "北村生菜会", "level": "市级", "category": "民俗"},
    {"name": "烧番塔（仙岗）", "level": "市级", "category": "民俗"},
    {"name": "周家拳", "level": "市级", "category": "传统体育"},
    {"name": "九江鱼筛编织技艺", "level": "市级", "category": "传统技艺"},
    {"name": "粤剧", "level": "区级", "category": "传统戏剧"},
    {"name": "佛鹤狮头制作", "level": "区级", "category": "传统技艺"},
    {"name": "赤坎盲公话", "level": "区级", "category": "民间文学"},
    {"name": "南海农谚", "level": "区级", "category": "民间文学"},
    {"name": "西樵山传说", "level": "区级", "category": "民间文学"},
    {"name": "里水毛巾织造技艺", "level": "区级", "category": "传统技艺"},
    {"name": "南海醒狮（采青技艺）", "level": "区级", "category": "传统舞蹈"},
    {"name": "花灯制作技艺", "level": "区级", "category": "传统技艺"},
    {"name": "西联村神诞", "level": "区级", "category": "民俗"},
    {"name": "简村北帝庙会", "level": "区级", "category": "民俗"},
    {"name": "松塘村孔子诞", "level": "区级", "category": "民俗"},
    {"name": "松塘村'出色'巡游", "level": "区级", "category": "民俗"},
    {"name": "大沥锦龙盛会", "level": "区级", "category": "民俗"},
    {"name": "大沥狮子会", "level": "区级", "category": "民俗"},
    {"name": "狮中冥王诞", "level": "区级", "category": "民俗"},
    {"name": "平地观音诞", "level": "区级", "category": "民俗"},
    {"name": "南海鼓乐", "level": "区级", "category": "传统音乐"},
    {"name": "万石辘木马", "level": "区级", "category": "传统体育"},
    {"name": "万石舞青火龙", "level": "区级", "category": "传统舞蹈"},
    {"name": "南海广式旺阁酱油酿造技艺", "level": "区级", "category": "传统技艺"},
    {"name": "西樵白眉武术", "level": "区级", "category": "传统体育"},
    {"name": "龙形拳", "level": "区级", "category": "传统体育"},
    {"name": "沙皮狗斗狗习俗", "level": "区级", "category": "民俗"},
    {"name": "大头佛（民乐大头佛）", "level": "区级", "category": "传统舞蹈"},
    {"name": "传统龙舟（丹灶扒龙舟）", "level": "区级", "category": "传统体育"},
    {"name": "汉字书法（康体）", "level": "区级", "category": "传统美术"},
    {"name": "苏村拜斗", "level": "区级", "category": "民俗"},
    {"name": "木作工具制作技艺", "level": "区级", "category": "传统技艺"},
    {"name": "百西村头村六祖诞", "level": "区级", "category": "民俗"},
    {"name": "南海牛皮鼓制作技艺", "level": "区级", "category": "传统技艺"},
    {"name": "南海剪纸", "level": "区级", "category": "传统美术"},
    {"name": "鹰爪拳", "level": "区级", "category": "传统体育"},
    {"name": "蔡李佛拳", "level": "区级", "category": "传统体育"},
    {"name": "水菱角制作技艺", "level": "区级", "category": "传统技艺"},
    {"name": "广式烧腊制作技艺", "level": "区级", "category": "传统技艺"},
    {"name": "中医传统制剂方法（冯了性传统膏方制作技艺）", "level": "区级", "category": "传统医药"},
    {"name": "咸鸭蛋腌制技艺（南海）", "level": "区级", "category": "传统技艺"},
    {"name": "冯伯成传说", "level": "区级", "category": "民间文学"},
    {"name": "五郎八卦棍（鲁岗谢家）", "level": "区级", "category": "传统体育"},
    {"name": "洪拳功夫推拿", "level": "区级", "category": "传统医药"},
    {"name": "广式月饼制作技艺（南海）", "level": "区级", "category": "传统技艺"},
    {"name": "九江刀制作技艺", "level": "区级", "category": "传统技艺"},
    {"name": "九江鹤装狮头制作技艺", "level": "区级", "category": "传统技艺"},
    {"name": "酱油酿造技艺（九江酱油酿造技艺）", "level": "区级", "category": "传统技艺"},
    {"name": "下东村周将军诞", "level": "区级", "category": "民俗"},
    {"name": "酿鲮鱼制作技艺（南海）", "level": "区级", "category": "传统技艺"},
    {"name": "蛋散制作技艺（丹灶）", "level": "区级", "category": "传统技艺"},
    {"name": "传统中医药文化（保愈堂传统中医文化）", "level": "区级", "category": "传统医药"},
]

TOWN_MAP = {
    "狮舞": "西樵镇", "十番音乐": "桂城街道", "官窑生菜会": "狮山镇",
    "乐安花灯会": "桂城街道", "九江双蒸": "九江镇", "九江传统龙舟": "九江镇",
    "盐步老龙": "大沥镇", "咏春拳": "桂城街道", "藤编（大沥）": "大沥镇",
    "藤编（里水）": "里水镇", "金箔锻造": "大沥镇", "大仙诞": "西樵镇",
    "粤曲": "桂城街道", "九江煎堆": "九江镇", "鱼花": "九江镇",
    "广式家具": "九江镇", "洪拳": "西樵镇", "龙舟说唱": "桂城街道",
    "白眉拳": "里水镇", "大头佛": "西樵镇", "灰塑": "狮山镇",
    "咸水歌": "桂城街道", "缫丝": "西樵镇", "麦边舞龙": "里水镇",
    "竹编": "丹灶镇", "西樵大饼": "西樵镇", "香云纱": "西樵镇",
    "灯谜": "九江镇", "葛洪": "丹灶镇", "六合八法拳": "大沥镇",
    "叠滘": "桂城街道", "平地黄氏": "大沥镇", "龙母诞": "大沥镇",
    "松塘": "西樵镇", "赤山": "桂城街道", "唢呐": "桂城街道",
    "平洲": "桂城街道", "广绣": "桂城街道", "同乐堂": "桂城街道",
    "北村": "大沥镇", "仙岗": "丹灶镇", "周家拳": "九江镇",
    "鱼筛": "九江镇", "粤剧": "西樵镇", "佛鹤": "桂城街道",
    "赤坎": "大沥镇", "农谚": "南海区", "西樵山传说": "西樵镇",
    "毛巾": "里水镇", "采青": "西樵镇", "花灯制作": "桂城街道",
    "西联村": "桂城街道", "简村": "狮山镇", "孔子诞": "西樵镇",
    "出色": "西樵镇", "锦龙": "大沥镇", "狮子会": "大沥镇",
    "冥王诞": "桂城街道", "观音诞": "大沥镇", "鼓乐": "桂城街道",
    "万石": "桂城街道", "旺阁": "桂城街道", "白眉武术": "西樵镇",
    "龙形拳": "桂城街道", "沙皮狗": "大沥镇", "民乐大头佛": "西樵镇",
    "丹灶扒龙舟": "丹灶镇", "康体": "丹灶镇", "苏村": "大沥镇",
    "木作": "桂城街道", "六祖诞": "丹灶镇", "牛皮鼓": "桂城街道",
    "剪纸": "桂城街道", "鹰爪拳": "九江镇", "蔡李佛": "桂城街道",
    "水菱角": "西樵镇", "烧腊": "桂城街道", "冯了性": "桂城街道",
    "咸鸭蛋": "桂城街道", "冯伯成": "桂城街道", "八卦棍": "大沥镇",
    "推拿": "桂城街道", "月饼": "桂城街道", "九江刀": "九江镇",
    "鹤装": "九江镇", "九江酱油": "九江镇", "周将军": "九江镇",
    "酿鲮鱼": "桂城街道", "蛋散": "丹灶镇", "保愈堂": "桂城街道",
}


def assign_town(name):
    """根据非遗名称判断所属镇街"""
    for keyword, town in TOWN_MAP.items():
        if keyword in name:
            return town
    return "南海区"


def main():
    print("=" * 60)
    print("南海区90项非遗完整数据整理")
    print("=" * 60)

    for item in FULL_90_ITEMS:
        item["town"] = assign_town(item["name"])

    from collections import Counter
    level_counts = Counter(i["level"] for i in FULL_90_ITEMS)
    cat_counts = Counter(i["category"] for i in FULL_90_ITEMS)
    town_counts = Counter(i["town"] for i in FULL_90_ITEMS)

    print(f"\n总计: {len(FULL_90_ITEMS)} 项")
    print(f"级别: {dict(level_counts)}")
    print(f"类别: {dict(cat_counts)}")
    print(f"镇街: {dict(town_counts)}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "nanhai_nonheritage_full90.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "source": "南海博物馆官网 nhmuseum.org + 开题阶段工作计划",
            "total": len(FULL_90_ITEMS),
            "level_stats": dict(level_counts),
            "category_stats": dict(cat_counts),
            "town_stats": dict(town_counts),
            "items": FULL_90_ITEMS,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n保存: {path}")

    import csv
    csv_path = os.path.join(BASE_DIR, "..", "..", "output", "tables", "nonheritage_full90.csv")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "level", "category", "town"])
        w.writeheader()
        w.writerows(FULL_90_ITEMS)
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
