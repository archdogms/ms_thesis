#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将 reviews_detail.csv 中的评论（spot_name）匹配到 poi_llm_cleaned.csv 中的 POI。
原表不动，结果输出到新表。

匹配策略（五段式，命中即停）：
  1. 精确匹配：标准化后名称完全一致
  2. 核心名精确匹配：进一步剥离常见后缀后匹配
  3. 别名 / 括号内容精确匹配
  4. 包含匹配（双向，需排除泛化词）
  5. 模糊匹配（high >= 80，low >= 65 需人工复核）

输出：
  output/tables/review_poi_matched.csv   — 评论表 + 匹配的 POI 信息
  output/tables/review_poi_link.csv      — 纯映射表（去重的 spot_name → poi）
"""

import os
import re
import pandas as pd
from rapidfuzz import fuzz, process

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TABLE_DIR = os.path.join(BASE_DIR, "..", "..", "output", "tables")

REVIEWS_PATH = os.path.join(TABLE_DIR, "reviews_detail.csv")
POI_PATH = os.path.join(TABLE_DIR, "poi_llm_cleaned.csv")
OUT_MATCHED = os.path.join(TABLE_DIR, "review_poi_matched.csv")
OUT_LINK = os.path.join(TABLE_DIR, "review_poi_link.csv")

NANHAI_TOWNS = ["桂城", "西樵", "九江", "狮山", "里水", "丹灶", "大沥"]

# 仅剥离带行政后缀的前缀，避免误删"南海""顺德"等地名组成部分
ADMIN_PREFIXES = [
    "佛山市南海区", "佛山市顺德区", "佛山市禅城区", "佛山市三水区", "佛山市高明区",
    "广东省佛山市", "广东省广州市", "广东省",
    "佛山市", "广州市", "中山市", "东莞市", "深圳市", "珠海市",
    "南海区", "顺德区", "禅城区", "三水区", "高明区",
    "中央电视台",
]

# 泛化通用名，不能单独作为包含匹配的依据
GENERIC_NAMES = {
    "广场", "公园", "博物馆", "图书馆", "体育馆", "体育中心", "文化馆",
    "文化街", "文化公园", "文化广场", "湿地公园", "森林公园",
    "游乐园", "乐园", "生态园", "摩天轮", "书院", "体育场",
    "展览馆", "纪念馆", "艺术馆", "科学馆", "美术馆",
    "中学", "小学", "幼儿园", "大学",
    "会展中心", "国际会议中心", "高尔夫球会", "创意产业园",
    "教堂", "寺庙", "祠堂",
    "过桥米线", "大雄宝殿",
    "空间", "钟楼", "花塔", "龙津", "清泉", "考拉", "珠江",
    "南园", "玉岩", "红树林", "老爷车", "小火车", "古村落",
    "东门广场", "山顶广场", "体育公园", "金融博物馆",
    "创客公园", "生态湿地", "文化中心", "儿童乐园",
}


def normalize_name(raw):
    """标准化名称：去括号内容、去行政前缀、去符号空白"""
    if not isinstance(raw, str):
        return ""
    s = raw.strip()
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    for prefix in ADMIN_PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = re.sub(r"[-—·•\s　]", "", s)
    return s.strip()


def extract_core_name(norm):
    """进一步提取核心名称：去除常见后缀修饰"""
    if not norm:
        return norm
    s = norm
    for pat in [r"风景名胜区$", r"风景区$", r"景区$", r"旅游区$",
                r"度假区$", r"度假村$", r"生态园$"]:
        s = re.sub(pat, "", s)
    return s if s else norm


def extract_bracket_alias(raw):
    """从括号中提取别名"""
    if not isinstance(raw, str):
        return []
    aliases = re.findall(r"[（(]([^）)]+)[）)]", raw)
    return [normalize_name(a) for a in aliases if len(a) >= 2]


def extract_town_hint(text, spot_name=""):
    """从评论文本和景点名中提取镇街线索"""
    combined = (spot_name or "") + " " + (text or "")
    for t in NANHAI_TOWNS:
        if t in combined:
            return t
    return ""


def build_poi_lookup(poi_df):
    """构建 POI 查找结构"""
    records = []
    for _, row in poi_df.iterrows():
        name = row["name"] if isinstance(row["name"], str) else ""
        norm = normalize_name(name)
        core = extract_core_name(norm)
        if not norm:
            continue
        records.append({
            "poi_id": row["id"],
            "poi_name": name,
            "poi_name_norm": norm,
            "poi_name_core": core,
            "poi_category": str(row.get("category", "")),
            "poi_town": str(row.get("town", "")),
            "poi_lng": str(row.get("lng", "")),
            "poi_lat": str(row.get("lat", "")),
            "poi_is_cultural_tourism": str(row.get("is_cultural_tourism", "")),
        })
    return pd.DataFrame(records)


def _result(row, score, method):
    return {
        "poi_id": row["poi_id"],
        "poi_name": row["poi_name"],
        "poi_town": row["poi_town"],
        "poi_category": row["poi_category"],
        "poi_lng": row["poi_lng"],
        "poi_lat": row["poi_lat"],
        "poi_is_cultural_tourism": row["poi_is_cultural_tourism"],
        "match_score": round(score, 1),
        "match_method": method,
    }


def _is_generic(name):
    """判断名称是否为泛化通用词"""
    return name in GENERIC_NAMES


def _contain_match(spot_norm, spot_core, norm2rows, min_ratio=0.40):
    """双向包含匹配，排除泛化通用词"""
    best = None
    best_score = 0

    search_names = {spot_norm}
    if spot_core and spot_core != spot_norm and len(spot_core) >= 3:
        search_names.add(spot_core)

    for norm_key, rows in norm2rows.items():
        if not norm_key or len(norm_key) < 3:
            continue

        for s_name in search_names:
            if len(s_name) < 3:
                continue

            shorter_len = min(len(s_name), len(norm_key))
            longer_len = max(len(s_name), len(norm_key))

            if shorter_len / longer_len < min_ratio:
                continue

            is_contained = False
            shorter_str = ""

            if s_name in norm_key:
                is_contained = True
                shorter_str = s_name
            elif norm_key in s_name:
                is_contained = True
                shorter_str = norm_key

            if not is_contained:
                continue

            if _is_generic(shorter_str):
                continue

            score = (shorter_len / longer_len) * 95
            if score > best_score:
                best_score = score
                row = rows.iloc[0]
                best = _result(row, best_score, "contain")

    return best


def _fuzzy_match(spot_norm, poi_names_list, poi_lookup_df, town_hint,
                 high_threshold=80, low_threshold=72):
    """模糊匹配"""
    if len(spot_norm) < 2:
        return None

    results = process.extract(
        spot_norm,
        poi_names_list,
        scorer=fuzz.token_sort_ratio,
        limit=5,
    )

    best = None
    best_final = 0

    for matched_norm, score, idx in results:
        if score < low_threshold:
            continue

        matched_rows = poi_lookup_df[poi_lookup_df["poi_name_norm"] == matched_norm]
        if matched_rows.empty:
            continue
        row = matched_rows.iloc[0]

        bonus = 0
        if town_hint and isinstance(row["poi_town"], str) and town_hint in row["poi_town"]:
            bonus = 5

        final_score = min(score + bonus, 100.0)
        if final_score > best_final:
            best_final = final_score
            method = "fuzzy_high" if final_score >= high_threshold else "fuzzy_low"
            best = _result(row, final_score, method)

    if best and best["match_score"] >= low_threshold:
        return best
    return None


def do_match(spot_name, spot_norm, spot_core, spot_aliases,
             poi_lookup, norm2rows, core2rows, poi_names_list, town_hint):
    """五段式匹配"""

    # 1. 精确匹配
    if spot_norm in norm2rows:
        row = norm2rows[spot_norm].iloc[0]
        return _result(row, 100.0, "exact")

    # 2. 核心名精确匹配
    if spot_core and spot_core != spot_norm and len(spot_core) >= 3 and spot_core in core2rows:
        row = core2rows[spot_core].iloc[0]
        return _result(row, 97.0, "core_exact")

    # 3. 别名精确匹配
    for alias in spot_aliases:
        if len(alias) < 2:
            continue
        if alias in norm2rows:
            row = norm2rows[alias].iloc[0]
            return _result(row, 95.0, "alias_exact")
        if alias in core2rows:
            row = core2rows[alias].iloc[0]
            return _result(row, 93.0, "alias_core")

    # 4. 包含匹配
    contain_result = _contain_match(spot_norm, spot_core, norm2rows)
    if contain_result:
        return contain_result

    # 5. 模糊匹配
    fuzzy_result = _fuzzy_match(spot_norm, poi_names_list, poi_lookup, town_hint)
    if fuzzy_result:
        return fuzzy_result

    return None


def main():
    print("=" * 60)
    print("评论-POI 匹配工具 v3")
    print("=" * 60)

    print("\n加载数据...")
    reviews = pd.read_csv(REVIEWS_PATH, dtype=str).fillna("")
    poi = pd.read_csv(POI_PATH, dtype=str).fillna("")
    print(f"  评论: {len(reviews)} 行, {reviews['spot_name'].nunique()} 个唯一景点名")
    print(f"  POI:  {len(poi)} 行")

    print("\n构建索引...")
    poi_lookup = build_poi_lookup(poi)
    norm2rows = {k: v for k, v in poi_lookup.groupby("poi_name_norm")}
    core2rows = {k: v for k, v in poi_lookup.groupby("poi_name_core")}
    poi_names_list = poi_lookup["poi_name_norm"].unique().tolist()

    unique_spots = reviews["spot_name"].unique()
    print(f"\n开始匹配 {len(unique_spots)} 个唯一景点名...\n")

    link_records = []

    for i, spot in enumerate(unique_spots):
        if i % 500 == 0 and i > 0:
            print(f"  进度: {i}/{len(unique_spots)}")

        spot_norm = normalize_name(spot)
        spot_core = extract_core_name(spot_norm)
        spot_aliases = extract_bracket_alias(spot)

        sample_rows = reviews[reviews["spot_name"] == spot].head(3)
        combined_text = " ".join(sample_rows["text"].tolist())
        town_hint = extract_town_hint(combined_text, spot)

        result = do_match(
            spot, spot_norm, spot_core, spot_aliases,
            poi_lookup, norm2rows, core2rows, poi_names_list, town_hint,
        )

        if result:
            auto = result["match_score"] >= 85
            need_review = result["match_score"] < 85
            link_records.append({
                "spot_name": spot,
                "poi_id": result["poi_id"],
                "poi_name": result["poi_name"],
                "poi_category": result["poi_category"],
                "poi_town": result["poi_town"],
                "poi_lng": result["poi_lng"],
                "poi_lat": result["poi_lat"],
                "is_cultural_tourism": result["poi_is_cultural_tourism"],
                "match_score": result["match_score"],
                "match_method": result["match_method"],
                "is_auto_matched": auto,
                "need_manual_review": need_review,
            })
        else:
            link_records.append({
                "spot_name": spot,
                "poi_id": "",
                "poi_name": "",
                "poi_category": "",
                "poi_town": "",
                "poi_lng": "",
                "poi_lat": "",
                "is_cultural_tourism": "",
                "match_score": 0,
                "match_method": "unmatched",
                "is_auto_matched": False,
                "need_manual_review": True,
            })

    link_df = pd.DataFrame(link_records)

    # ---- 统计 ----
    total = len(unique_spots)
    method_counts = link_df["match_method"].value_counts()
    matched_count = total - method_counts.get("unmatched", 0)
    auto_count = int(link_df["is_auto_matched"].sum())
    review_need = int(link_df["need_manual_review"].sum())

    print("\n" + "=" * 60)
    print("匹配结果统计")
    print("=" * 60)
    for method, cnt in method_counts.items():
        print(f"  {method:>12}: {cnt}")
    print(f"\n  总匹配率:     {matched_count}/{total} = {matched_count/total*100:.1f}%")
    print(f"  自动确认:     {auto_count}")
    print(f"  需人工复核:   {review_need}")

    spot_counts = reviews.groupby("spot_name").size().reset_index(name="review_count")
    link_with_cnt = link_df.merge(spot_counts, on="spot_name", how="left")
    matched_reviews = link_with_cnt[link_with_cnt["match_method"] != "unmatched"]["review_count"].sum()
    print(f"  评论级覆盖:   {matched_reviews}/{len(reviews)} = {matched_reviews/len(reviews)*100:.1f}%")

    # ---- 保存映射表 ----
    link_df = link_df.sort_values(["match_method", "match_score"],
                                   ascending=[True, False])
    link_df.to_csv(OUT_LINK, index=False, encoding="utf-8-sig")
    print(f"\n映射表已保存: {os.path.abspath(OUT_LINK)}")

    # ---- 生成评论匹配结果表（精简列） ----
    print("生成评论匹配结果表...")
    join_cols = ["poi_id", "poi_name", "poi_category", "poi_town",
                 "poi_lng", "poi_lat", "is_cultural_tourism",
                 "match_score", "match_method"]
    match_map = link_df.set_index("spot_name")[join_cols].to_dict("index")

    extra_cols = {col: [] for col in join_cols}
    for _, row in reviews.iterrows():
        info = match_map.get(row["spot_name"], {})
        for col in join_cols:
            extra_cols[col].append(info.get(col, ""))

    out_df = pd.DataFrame({
        "platform": reviews["platform"],
        "spot_name": reviews["spot_name"],
        "text": reviews["text"],
        "time": reviews["time"],
        "poi_id": extra_cols["poi_id"],
        "poi_name": extra_cols["poi_name"],
        "poi_category": extra_cols["poi_category"],
        "poi_town": extra_cols["poi_town"],
        "poi_lng": extra_cols["poi_lng"],
        "poi_lat": extra_cols["poi_lat"],
        "is_cultural_tourism": extra_cols["is_cultural_tourism"],
        "match_score": extra_cols["match_score"],
        "match_method": extra_cols["match_method"],
    })

    out_df.to_csv(OUT_MATCHED, index=False, encoding="utf-8-sig")
    print(f"评论匹配结果表已保存: {os.path.abspath(OUT_MATCHED)}")

    # ---- 未匹配 TOP 列表 ----
    unmatched_df = link_with_cnt[link_with_cnt["match_method"] == "unmatched"]
    unmatched_df = unmatched_df.sort_values("review_count", ascending=False)
    print("\n" + "=" * 60)
    print("未匹配 TOP 20（供参考）:")
    print("=" * 60)
    for _, r in unmatched_df.head(20).iterrows():
        cnt = r["review_count"]
        print(f"  [{cnt:>3}条评论] {r['spot_name']}")

    # ---- 低分匹配 TOP 列表 ----
    low_score = link_with_cnt[
        (link_with_cnt["need_manual_review"] == True) &
        (link_with_cnt["match_method"] != "unmatched")
    ].sort_values("review_count", ascending=False)
    print("\n" + "=" * 60)
    print("需人工复核 TOP 20:")
    print("=" * 60)
    for _, r in low_score.head(20).iterrows():
        cnt = r["review_count"]
        print(f"  [{cnt:>3}条] {r['spot_name']} -> {r['poi_name']} "
              f"({r['match_method']}, {r['match_score']})")

    print("\n完成！")


if __name__ == "__main__":
    main()
