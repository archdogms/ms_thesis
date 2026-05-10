"""构建文化—旅游量化指数与错位指数（4.15 意见落实）

输入：
  data/anchors/cultural_anchors.json        165 条官方物质文化载体（主桥梁）
  data/entities/entities.json               知识图谱实体（含提及频次 mentions）
  data/poi/poi_cleaned.json                 13,512 条 POI（含坐标、评分、评论）
  data/reviews/review_summary_merged.json   3,879 个景点名的评论聚合
  data/gis/nanhai_nonheritage_full90.json   91 项非遗（动态补充层）
  data/gis/scenic_a_level.json              已知 A 级景区小样本

输出：
  output/tables/indices_anchors.csv         165 条载体的 CMI / OAI / THI / MI 表
  output/tables/indices_nonheritage.csv     91 项非遗的 CMI（仅文化记忆侧）
  output/tables/indices_town_summary.csv    镇街维度汇总
  output/tables/indices_a_level.csv         A 级景区副产品样本
  output/tables/indices_overview.json       运行摘要与指数分位分布

计算口径（与论文第 5.3 节一致）：
  CMI = minmax( log(1 + mentions) )          ∈ [0, 100]
  OAI = 保护级别赋分（国家 100 / 省级 75 / 市级 50 / 区级 25 / 未评 0）
  THI = 0.4·poi_count_norm + 0.2·rating_norm + 0.4·log_review_norm
  MI  = THI − 0.5·CMI − 0.5·OAI
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)


# ----------------------------- utils --------------------------------------


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def minmax(values, lo=0.0, hi=100.0):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    vmin, vmax = np.nanmin(arr), np.nanmax(arr)
    if vmax - vmin < 1e-9:
        return np.full_like(arr, (lo + hi) / 2)
    return lo + (arr - vmin) / (vmax - vmin) * (hi - lo)


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def simplify(name: str) -> str:
    """去括号、去常见后缀，返回可匹配词。"""
    if not name:
        return ""
    s = str(name)
    for ch in "()（）[]【】 ":
        s = s.replace(ch, "")
    for suf in [
        "酿制技艺", "制作技艺", "技艺", "表演", "传承", "纪念馆", "博物馆",
        "公园", "景区", "风景名胜区", "文化广场", "广场",
    ]:
        if s.endswith(suf) and len(s) > len(suf) + 1:
            s = s[: -len(suf)]
    return s


# ----------------------------- scoring ------------------------------------


def oai_score(anchor: dict) -> float:
    """官方认证指数：按保护级别赋分。"""
    lv = (anchor.get("protection_level") or "") + "|" + (anchor.get("anchor_type") or "")
    if any(k in lv for k in ["全国重点", "国家级", "中国历史文化名镇"]):
        return 100.0
    if any(k in lv for k in ["省级文物", "省级传统", "广东省历史文化名村", "省级"]):
        return 75.0
    if "市级" in lv:
        return 50.0
    if "区级" in lv:
        return 25.0
    return 0.0


def compute_cmi_raw(anchor_name: str, entities: list[dict]) -> tuple[float, list[str]]:
    """按名称包含与实体类型约束汇总提及频次。"""
    key = simplify(anchor_name)
    if not key or len(key) < 2:
        return 0.0, []
    total = 0.0
    hit = []
    for e in entities:
        ename = e.get("name", "")
        if not ename:
            continue
        if key in ename or ename in anchor_name:
            total += float(e.get("mentions", 0) or 0)
            hit.append(ename)
            if len(hit) >= 50:
                break
    return total, hit


def compute_thi_components(anchor: dict, pois: list[dict], review_idx: dict, radius_km: float = 0.5):
    """旅游热度指数构成：缓冲内 POI 数 / 平均评分 / 评论对数总量。"""
    lat = anchor.get("lat")
    lng = anchor.get("lng")
    if not lat or not lng:
        return 0, 0.0, 0.0, []
    poi_count = 0
    rating_sum = 0.0
    rating_n = 0
    review_total = 0
    linked = []
    for p in pois:
        plat, plng = p.get("lat"), p.get("lng")
        if plat is None or plng is None:
            continue
        if haversine_km(lat, lng, plat, plng) <= radius_km:
            poi_count += 1
            r = p.get("rating")
            if r:
                try:
                    rf = float(r)
                    if rf > 0:
                        rating_sum += rf
                        rating_n += 1
                except Exception:
                    pass
            name = p.get("name", "")
            rv = review_idx.get(name)
            if rv:
                review_total += rv.get("total_count", 0) or 0
            if len(linked) < 20:
                linked.append(name)
    avg_rating = rating_sum / rating_n if rating_n else 0.0
    return poi_count, avg_rating, review_total, linked


# ----------------------------- main ---------------------------------------


def main():
    anchors_raw = load_json(DATA / "anchors" / "cultural_anchors.json")
    anchors = anchors_raw["anchors"]
    entities = load_json(DATA / "entities" / "entities.json")["entities"]
    pois_all = load_json(DATA / "poi" / "poi_cleaned.json")["pois"]
    reviews = load_json(DATA / "reviews" / "review_summary_merged.json")
    review_idx = {r.get("name"): r for r in reviews}
    nh_full = load_json(DATA / "gis" / "nanhai_nonheritage_full90.json")
    nh_items = nh_full if isinstance(nh_full, list) else nh_full.get("items", nh_full.get("nonheritage", []))
    a_level = load_json(DATA / "gis" / "scenic_a_level.json")["items"]

    # ---- 1) 165 条载体：CMI 原始值 + OAI + THI 组件 --------------------
    rows = []
    for a in anchors:
        name = a.get("name") or ""
        cmi_raw, hit_entities = compute_cmi_raw(name, entities)
        poi_count, avg_rating, review_total, linked_pois = compute_thi_components(a, pois_all, review_idx, 0.5)
        rows.append({
            "id": a.get("id"),
            "name": name,
            "anchor_type": a.get("anchor_type"),
            "sub_type": a.get("sub_type"),
            "protection_level": a.get("protection_level"),
            "town": a.get("town") or "",
            "lng": a.get("lng"),
            "lat": a.get("lat"),
            "cmi_raw_mentions": cmi_raw,
            "oai": oai_score(a),
            "poi_count_500m": poi_count,
            "avg_rating_500m": round(avg_rating, 3),
            "review_total_500m": review_total,
            "entity_hit_sample": "|".join(hit_entities[:8]),
            "poi_hit_sample": "|".join(linked_pois[:5]),
        })

    # 归一到 [0, 100]
    cmi_log = [math.log1p(r["cmi_raw_mentions"]) for r in rows]
    cmi = minmax(cmi_log)
    poi_log = [math.log1p(r["poi_count_500m"]) for r in rows]
    poi_norm = minmax(poi_log)
    rating_norm = minmax([r["avg_rating_500m"] for r in rows])
    review_log = [math.log1p(r["review_total_500m"]) for r in rows]
    review_norm = minmax(review_log)

    thi = 0.4 * poi_norm + 0.2 * rating_norm + 0.4 * review_norm
    mi = thi - 0.5 * cmi - 0.5 * np.array([r["oai"] for r in rows])

    for i, r in enumerate(rows):
        r["cmi"] = round(float(cmi[i]), 2)
        r["thi"] = round(float(thi[i]), 2)
        r["mi"] = round(float(mi[i]), 2)

    # 分层
    mi_arr = np.array([r["mi"] for r in rows])
    q1, q2, q3 = np.percentile(mi_arr, [25, 50, 75])

    def label_of(cmi_v, thi_v, mi_v):
        if abs(mi_v) <= 10 and cmi_v >= 50 and thi_v >= 50:
            return "核心耦合区"
        if abs(mi_v) <= 10:
            return "一般耦合区"
        if mi_v < -10 and cmi_v > thi_v:
            return "沉睡潜力区"
        if mi_v > 10 and thi_v > cmi_v:
            return "空心景点区"
        return "一般耦合区"

    for r in rows:
        r["mi_category"] = label_of(r["cmi"], r["thi"], r["mi"])

    # 写 indices_anchors.csv
    headers = [
        "id", "name", "anchor_type", "sub_type", "protection_level", "town",
        "lng", "lat", "cmi_raw_mentions", "cmi", "oai", "poi_count_500m",
        "avg_rating_500m", "review_total_500m", "thi", "mi", "mi_category",
        "entity_hit_sample", "poi_hit_sample",
    ]
    with (OUT / "indices_anchors.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow({h: r.get(h, "") for h in headers})

    # ---- 2) 91 项非遗的 CMI（仅文化记忆侧） ------------------------------
    nh_rows = []
    for nh in nh_items:
        nm = nh.get("name") or nh.get("项目名称") or ""
        if not nm:
            continue
        cmi_raw, hit = compute_cmi_raw(nm, entities)
        nh_rows.append({
            "name": nm,
            "level": nh.get("level") or nh.get("级别") or "",
            "town": nh.get("town") or nh.get("镇街") or "",
            "cmi_raw_mentions": cmi_raw,
            "entity_hit_sample": "|".join(hit[:8]),
        })
    if nh_rows:
        log_vals = [math.log1p(r["cmi_raw_mentions"]) for r in nh_rows]
        cmi_nh = minmax(log_vals)
        for i, r in enumerate(nh_rows):
            r["cmi"] = round(float(cmi_nh[i]), 2)
        with (OUT / "indices_nonheritage.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["name", "level", "town", "cmi_raw_mentions", "cmi", "entity_hit_sample"])
            w.writeheader()
            w.writerows(nh_rows)

    # ---- 3) 镇街维度汇总 ---------------------------------------------------
    town_agg = defaultdict(lambda: {"anchor_count": 0, "cmi_sum": 0.0, "oai_sum": 0.0, "thi_sum": 0.0, "mi_sum": 0.0})
    for r in rows:
        t = r["town"] or "未标注"
        town_agg[t]["anchor_count"] += 1
        town_agg[t]["cmi_sum"] += r["cmi"]
        town_agg[t]["oai_sum"] += r["oai"]
        town_agg[t]["thi_sum"] += r["thi"]
        town_agg[t]["mi_sum"] += r["mi"]

    # 挂接每镇街 POI 总数（从 poi_cleaned 统计）
    poi_town_count = defaultdict(int)
    for p in pois_all:
        poi_town_count[p.get("town") or "未标注"] += 1

    town_rows = []
    for t, s in town_agg.items():
        n = s["anchor_count"]
        town_rows.append({
            "town": t,
            "anchor_count": n,
            "poi_total": poi_town_count.get(t, 0),
            "cmi_mean": round(s["cmi_sum"] / n, 2) if n else 0,
            "oai_mean": round(s["oai_sum"] / n, 2) if n else 0,
            "thi_mean": round(s["thi_sum"] / n, 2) if n else 0,
            "mi_mean": round(s["mi_sum"] / n, 2) if n else 0,
        })
    town_rows.sort(key=lambda x: -x["anchor_count"])
    with (OUT / "indices_town_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["town", "anchor_count", "poi_total", "cmi_mean", "oai_mean", "thi_mean", "mi_mean"])
        w.writeheader()
        w.writerows(town_rows)

    # ---- 4) A 级景区副产品样本 --------------------------------------------
    a_rows = []
    for it in a_level:
        nm = it["name"]
        key = simplify(nm)
        match = None
        for p in pois_all:
            pn = p.get("name") or ""
            if nm in pn or pn in nm or (key and key in pn):
                match = p
                break
        review = review_idx.get(nm) or (review_idx.get(match["name"]) if match else None)
        a_rows.append({
            "name": nm,
            "level": it["level"],
            "level_score": it["score"],
            "town": it["town"],
            "poi_match": match["name"] if match else "",
            "rating": match.get("rating") if match else "",
            "review_count": review.get("total_count", 0) if review else 0,
            "positive_rate": review.get("positive_rate", 0) if review else 0,
        })
    with (OUT / "indices_a_level.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "level", "level_score", "town", "poi_match", "rating", "review_count", "positive_rate"])
        w.writeheader()
        w.writerows(a_rows)

    # ---- 5) overview --------------------------------------------------------
    def pct(arr, qs=(0, 25, 50, 75, 100)):
        return {f"p{q}": round(float(np.percentile(arr, q)), 2) for q in qs}

    cat_count = defaultdict(int)
    for r in rows:
        cat_count[r["mi_category"]] += 1

    overview = {
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_anchors": len(rows),
        "n_nonheritage": len(nh_rows),
        "n_a_level": len(a_rows),
        "weights": {"alpha": 0.5, "beta": 0.5, "thi": {"poi": 0.4, "rating": 0.2, "review": 0.4}},
        "cmi_quantiles": pct([r["cmi"] for r in rows]),
        "oai_quantiles": pct([r["oai"] for r in rows]),
        "thi_quantiles": pct([r["thi"] for r in rows]),
        "mi_quantiles": pct([r["mi"] for r in rows]),
        "mi_category_counts": dict(cat_count),
    }
    with (OUT / "indices_overview.json").open("w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)

    print("[build_indices] done")
    print("  anchors rows:", len(rows))
    print("  nonheritage rows:", len(nh_rows))
    print("  a_level rows:", len(a_rows))
    print("  mi category:", dict(cat_count))


if __name__ == "__main__":
    main()
