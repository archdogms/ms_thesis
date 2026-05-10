#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
真实景点评论爬取工具
从携程、马蜂窝等平台爬取南海区主要景点的真实用户评论
合规原则：低频请求、仅用于学术研究、不进行商业用途
"""

import requests
import json
import time
import os
import re
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "data", "reviews")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

SCENIC_SPOTS_CTRIP = [
    {"name": "西樵山风景名胜区", "ctrip_id": "77597", "mfw_id": "6620441"},
    {"name": "南海影视城", "ctrip_id": "77610", "mfw_id": "6620509"},
    {"name": "千灯湖公园", "ctrip_id": "4432862", "mfw_id": "30671847"},
    {"name": "南海观音寺", "ctrip_id": "4432747", "mfw_id": ""},
    {"name": "康有为故居", "ctrip_id": "77611", "mfw_id": "6620487"},
    {"name": "松塘古村", "ctrip_id": "", "mfw_id": "24898044"},
    {"name": "南海博物馆", "ctrip_id": "", "mfw_id": ""},
    {"name": "黄飞鸿纪念馆", "ctrip_id": "", "mfw_id": "6620479"},
    {"name": "九江双蒸博物馆", "ctrip_id": "4432814", "mfw_id": ""},
    {"name": "里水梦里水乡", "ctrip_id": "", "mfw_id": ""},
    {"name": "宝峰寺", "ctrip_id": "", "mfw_id": ""},
    {"name": "烟桥古村", "ctrip_id": "", "mfw_id": ""},
    {"name": "平洲玉器街", "ctrip_id": "", "mfw_id": ""},
    {"name": "贤鲁岛", "ctrip_id": "", "mfw_id": ""},
    {"name": "仙岗古村", "ctrip_id": "", "mfw_id": ""},
]


def crawl_ctrip_comments(spot_name, ctrip_id, max_pages=3):
    """从携程抓取评论"""
    if not ctrip_id:
        return []

    reviews = []
    for page in range(1, max_pages + 1):
        url = f"https://m.ctrip.com/restapi/soa2/13444/json/getCommentCollapseList"
        payload = {
            "arg": {
                "channelType": 2,
                "collapseType": 0,
                "commentTagId": 0,
                "pageIndex": page,
                "pageSize": 10,
                "poiId": int(ctrip_id),
                "sourceType": 1,
                "sortType": 3,
                "starType": 0,
            }
        }
        try:
            resp = requests.post(url, json=payload, headers={
                **HEADERS,
                "Content-Type": "application/json",
            }, timeout=15)
            data = resp.json()

            items = data.get("result", {}).get("items", [])
            if not items:
                break

            for item in items:
                content = item.get("content", "")
                score = item.get("score", 0)
                publish_time = item.get("publishTime", "")

                if content and len(content) > 5:
                    reviews.append({
                        "spot_name": spot_name,
                        "rating": score / 10.0 if score > 5 else score,
                        "review_text": content[:500],
                        "review_date": publish_time[:10] if publish_time else "",
                        "source": "携程",
                    })
        except Exception as e:
            print(f"      携程请求异常: {e}")
            break

        time.sleep(random.uniform(2, 4))

    return reviews


def crawl_mfw_comments(spot_name, mfw_id, max_pages=2):
    """从马蜂窝抓取评论"""
    if not mfw_id:
        return []

    reviews = []
    for page in range(1, max_pages + 1):
        url = f"https://www.mafengwo.cn/poi/{mfw_id}.html"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            text = resp.text

            comment_blocks = re.findall(
                r'<div class="rev-txt">\s*"?(.*?)"?\s*</div>',
                text, re.DOTALL
            )

            if not comment_blocks:
                comment_blocks = re.findall(
                    r'"comment":"(.*?)"',
                    text
                )

            for block in comment_blocks:
                clean = re.sub(r'<[^>]+>', '', block).strip()
                clean = clean.replace('\\n', ' ').replace('\n', ' ').strip()
                if clean and len(clean) > 5:
                    reviews.append({
                        "spot_name": spot_name,
                        "rating": 0,
                        "review_text": clean[:500],
                        "review_date": "",
                        "source": "马蜂窝",
                    })

            star_matches = re.findall(r'"star":(\d)', text)
            for i, star in enumerate(star_matches):
                if i < len(reviews):
                    reviews[i]["rating"] = int(star)

        except Exception as e:
            print(f"      马蜂窝请求异常: {e}")
            break

        time.sleep(random.uniform(2, 5))
        break

    return reviews


def crawl_amap_comments_from_poi(poi_data_path):
    """从已采集的高德POI数据中提取评分信息（高德不提供评论文本但有评分）"""
    reviews = []
    if not os.path.exists(poi_data_path):
        return reviews

    with open(poi_data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    spot_names = {s["name"] for s in SCENIC_SPOTS_CTRIP}

    for poi in data.get("pois", []):
        name = poi.get("name", "")
        rating = poi.get("rating", "")
        if rating and name:
            try:
                rating_float = float(rating)
                if rating_float > 0:
                    reviews.append({
                        "spot_name": name,
                        "rating": rating_float,
                        "review_text": f"高德评分: {rating_float}",
                        "review_date": "",
                        "source": "高德",
                        "is_rating_only": True,
                    })
            except (ValueError, TypeError):
                pass

    return reviews


def analyze_sentiment(text):
    """简单情感分析"""
    positive_words = [
        "好", "美", "棒", "赞", "漂亮", "推荐", "值得", "喜欢", "不错",
        "优美", "壮观", "精美", "舒适", "便利", "丰富", "有趣", "震撼",
        "历史", "文化", "传统", "特色", "适合", "愉快", "满意",
    ]
    negative_words = [
        "差", "烂", "坑", "失望", "无聊", "脏", "贵", "挤", "累",
        "不好", "不行", "一般", "还行", "太", "没有", "缺少",
    ]

    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)

    if pos_count > neg_count + 1:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    else:
        return "neutral"


def main():
    print("=" * 60)
    print("真实景点评论爬取")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_reviews = []

    print("\n--- 高德POI评分提取 ---")
    poi_path = os.path.join(BASE_DIR, "..", "..", "data", "poi", "nanhai_poi_real.json")
    amap_reviews = crawl_amap_comments_from_poi(poi_path)
    print(f"  提取 {len(amap_reviews)} 条高德评分")
    all_reviews.extend(amap_reviews)

    print("\n--- 携程评论爬取 ---")
    for spot in SCENIC_SPOTS_CTRIP:
        if spot["ctrip_id"]:
            print(f"  {spot['name']} (ctrip_id={spot['ctrip_id']})...")
            reviews = crawl_ctrip_comments(spot["name"], spot["ctrip_id"])
            print(f"    获取 {len(reviews)} 条")
            all_reviews.extend(reviews)
            time.sleep(random.uniform(1, 3))

    print("\n--- 马蜂窝评论爬取 ---")
    for spot in SCENIC_SPOTS_CTRIP:
        if spot["mfw_id"]:
            print(f"  {spot['name']} (mfw_id={spot['mfw_id']})...")
            reviews = crawl_mfw_comments(spot["name"], spot["mfw_id"])
            print(f"    获取 {len(reviews)} 条")
            all_reviews.extend(reviews)
            time.sleep(random.uniform(1, 3))

    print(f"\n--- 情感分析 ---")
    for r in all_reviews:
        if not r.get("is_rating_only"):
            r["sentiment"] = analyze_sentiment(r["review_text"])
        else:
            if r["rating"] >= 4:
                r["sentiment"] = "positive"
            elif r["rating"] >= 3:
                r["sentiment"] = "neutral"
            else:
                r["sentiment"] = "negative"

    print(f"总计 {len(all_reviews)} 条评论/评分数据")

    json_path = os.path.join(OUTPUT_DIR, "nanhai_reviews_real.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "note": "真实数据：高德评分 + 携程/马蜂窝评论爬取",
            "total_count": len(all_reviews),
            "reviews": all_reviews,
        }, f, ensure_ascii=False, indent=2)
    print(f"JSON: {json_path}")

    from collections import Counter, defaultdict
    spot_map = defaultdict(list)
    for r in all_reviews:
        spot_map[r["spot_name"]].append(r)

    summary = []
    for name, revs in spot_map.items():
        rated = [r for r in revs if r["rating"] and r["rating"] > 0]
        avg_rating = sum(r["rating"] for r in rated) / len(rated) if rated else 0
        sentiments = Counter(r.get("sentiment", "neutral") for r in revs)
        text_reviews = [r for r in revs if not r.get("is_rating_only")]

        summary.append({
            "name": name,
            "total_count": len(revs),
            "text_review_count": len(text_reviews),
            "avg_rating": round(avg_rating, 2),
            "positive_count": sentiments.get("positive", 0),
            "neutral_count": sentiments.get("neutral", 0),
            "negative_count": sentiments.get("negative", 0),
            "positive_rate": round(sentiments.get("positive", 0) / max(len(revs), 1) * 100, 1),
            "sources": list(set(r["source"] for r in revs)),
        })

    summary.sort(key=lambda x: -x["total_count"])

    summary_path = os.path.join(OUTPUT_DIR, "review_summary_real.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n--- 评论汇总 ---")
    for s in summary[:20]:
        print(f"  {s['name']}: {s['total_count']}条, 评分{s['avg_rating']}, 好评率{s['positive_rate']}% ({','.join(s['sources'])})")

    print(f"\n汇总: {summary_path}")
    print("完成！")


if __name__ == "__main__":
    main()
