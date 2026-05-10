"""潜力释放条件的相关性分析（4.15 意见落实）

输入：
  output/tables/indices_anchors.csv    165 条载体指数表
  output/tables/indices_town_summary.csv
  output/tables/indices_a_level.csv
  data/poi/poi_cleaned.json            POI（统计镇街特征）
  data/anchors/cultural_anchors.json   锚点（统计分级与类型密度）
  data/gis/nanhai_nonheritage_full90.json  非遗数量

输出：
  output/tables/potential_correlation_anchor.csv   载体级皮尔森 + 斯皮尔曼相关矩阵
  output/tables/potential_correlation_town.csv     镇街级相关矩阵
  output/tables/a_level_correlation.csv            A 级景区副产品相关分析
  output/tables/potential_summary.md               可读性报告
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)


def read_csv_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_float(x, default=0.0):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def pearson(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3 or np.std(x) < 1e-9 or np.std(y) < 1e-9:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def rankdata(arr):
    arr = np.asarray(arr, dtype=float)
    order = arr.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(arr) + 1)
    # tie-aware: average ranks of equal values
    i = 0
    while i < len(arr):
        j = i
        while j + 1 < len(arr) and arr[order[j + 1]] == arr[order[i]]:
            j += 1
        if j > i:
            avg = (ranks[order[i]] + ranks[order[j]]) / 2
            for k in range(i, j + 1):
                ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x, y):
    if len(x) < 3:
        return float("nan")
    return pearson(rankdata(x), rankdata(y))


def corr_matrix(data: dict[str, list[float]], method="pearson"):
    names = list(data.keys())
    n = len(names)
    mat = [[0.0] * n for _ in range(n)]
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if i == j:
                mat[i][j] = 1.0
            else:
                f = pearson if method == "pearson" else spearman
                mat[i][j] = f(data[a], data[b])
    return names, mat


def write_matrix(path: Path, names, mat, title: str):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([title] + names)
        for i, nm in enumerate(names):
            w.writerow([nm] + [("" if (isinstance(v, float) and math.isnan(v)) else round(v, 3)) for v in mat[i]])


# ----------------------------- main ---------------------------------------


def main():
    anchors = read_csv_rows(OUT / "indices_anchors.csv")
    towns = read_csv_rows(OUT / "indices_town_summary.csv")
    a_level = read_csv_rows(OUT / "indices_a_level.csv")

    # ---- 1) 载体级相关矩阵 --------------------------------------------------
    variables = {
        "CMI": [to_float(r["cmi"]) for r in anchors],
        "OAI": [to_float(r["oai"]) for r in anchors],
        "THI": [to_float(r["thi"]) for r in anchors],
        "MI":  [to_float(r["mi"])  for r in anchors],
        "POI_500m": [to_float(r["poi_count_500m"]) for r in anchors],
        "Rating_500m": [to_float(r["avg_rating_500m"]) for r in anchors],
        "Review_500m": [to_float(r["review_total_500m"]) for r in anchors],
    }
    names, mat_p = corr_matrix(variables, "pearson")
    _, mat_s = corr_matrix(variables, "spearman")
    write_matrix(OUT / "potential_correlation_anchor.csv", names, mat_p, "Pearson")
    # 在同一文件追加斯皮尔曼
    with (OUT / "potential_correlation_anchor.csv").open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([])
        w.writerow(["Spearman"] + names)
        for i, nm in enumerate(names):
            w.writerow([nm] + [("" if (isinstance(v, float) and math.isnan(v)) else round(v, 3)) for v in mat_s[i]])

    # ---- 2) 镇街级相关矩阵（带物质 vs 非遗对比） -----------------------------
    # 镇街原始样本太少（7 个），这里加上锚点类型密度作为变量
    anchors_raw = json.load((DATA / "anchors" / "cultural_anchors.json").open(encoding="utf-8"))["anchors"]
    nh_raw = json.load((DATA / "gis" / "nanhai_nonheritage_full90.json").open(encoding="utf-8"))
    nh_items = nh_raw if isinstance(nh_raw, list) else nh_raw.get("items", nh_raw.get("nonheritage", []))

    material_by_town = defaultdict(int)  # 不可移动文物 + 名村 + 文化景观 + 圩市街区
    nh_anchor_by_town = defaultdict(int)  # 非遗空间锚点
    for a in anchors_raw:
        t = a.get("town") or ""
        if not t:
            continue
        if a.get("anchor_type") in ["不可移动文物", "历史文化名村", "文化景观", "圩市街区"]:
            material_by_town[t] += 1
        elif a.get("anchor_type") == "非遗项目":
            nh_anchor_by_town[t] += 1

    nh_count_by_town = defaultdict(int)
    for nh in nh_items:
        tt = nh.get("town") or nh.get("镇街") or ""
        if tt:
            nh_count_by_town[tt] += 1

    # 仅保留 7 个主要镇街进入相关分析（过滤 nan / 未标注 / 村社）
    main_towns = ["桂城街道", "里水镇", "狮山镇", "大沥镇", "丹灶镇", "西樵镇", "九江镇"]
    town_map = {r["town"]: r for r in towns}
    rows_t = []
    for t in main_towns:
        base = town_map.get(t, {})
        rows_t.append({
            "town": t,
            "poi_total": to_float(base.get("poi_total")),
            "cmi_mean": to_float(base.get("cmi_mean")),
            "oai_mean": to_float(base.get("oai_mean")),
            "thi_mean": to_float(base.get("thi_mean")),
            "mi_mean": to_float(base.get("mi_mean")),
            "material_count": material_by_town.get(t, 0),
            "nh_anchor_count": nh_anchor_by_town.get(t, 0),
            "nh_total_count": nh_count_by_town.get(t, 0),
        })
    # 写到 csv 以便查看
    with (OUT / "town_analysis_input.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_t[0].keys()))
        w.writeheader()
        w.writerows(rows_t)

    tvars = {
        "POI_Total": [r["poi_total"] for r in rows_t],
        "Material_Count": [r["material_count"] for r in rows_t],
        "NH_Total": [r["nh_total_count"] for r in rows_t],
        "CMI_mean": [r["cmi_mean"] for r in rows_t],
        "OAI_mean": [r["oai_mean"] for r in rows_t],
        "THI_mean": [r["thi_mean"] for r in rows_t],
        "MI_mean": [r["mi_mean"] for r in rows_t],
    }
    names_t, mat_tp = corr_matrix(tvars, "pearson")
    _, mat_ts = corr_matrix(tvars, "spearman")
    with (OUT / "potential_correlation_town.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Pearson (n=%d)" % len(rows_t)] + names_t)
        for i, nm in enumerate(names_t):
            w.writerow([nm] + [("" if (isinstance(v, float) and math.isnan(v)) else round(v, 3)) for v in mat_tp[i]])
        w.writerow([])
        w.writerow(["Spearman (n=%d)" % len(rows_t)] + names_t)
        for i, nm in enumerate(names_t):
            w.writerow([nm] + [("" if (isinstance(v, float) and math.isnan(v)) else round(v, 3)) for v in mat_ts[i]])

    # ---- 3) A 级景区副产品分析 ----------------------------------------------
    xs_lv = [to_float(r["level_score"]) for r in a_level]
    xs_rate = [to_float(r["rating"]) for r in a_level]
    xs_rev = [to_float(r["review_count"]) for r in a_level]
    xs_pos = [to_float(r["positive_rate"]) for r in a_level]

    pairs = [
        ("level_score ~ rating",        xs_lv,  xs_rate),
        ("level_score ~ review_count",  xs_lv,  xs_rev),
        ("level_score ~ positive_rate", xs_lv,  xs_pos),
        ("rating ~ review_count",       xs_rate, xs_rev),
    ]
    with (OUT / "a_level_correlation.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pair", "pearson", "spearman", "n"])
        for name, x, y in pairs:
            w.writerow([name, round(pearson(x, y), 3), round(spearman(x, y), 3), len(x)])

    # ---- 4) 可读报告 ---------------------------------------------------------
    lines = []
    lines.append("# 潜力释放条件相关性分析（自动生成）\n")
    lines.append(f"生成时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("## 一、载体级指标（n = %d）相关系数（皮尔森）\n" % len(anchors))
    lines.append("```")
    lines.append("\t" + "\t".join(names))
    for i, nm in enumerate(names):
        row = [("%6.3f" % v) if not (isinstance(v, float) and math.isnan(v)) else "   -  " for v in mat_p[i]]
        lines.append(nm + "\t" + "\t".join(row))
    lines.append("```\n")

    lines.append("## 二、镇街级指标（n = %d）相关系数（皮尔森）\n" % len(rows_t))
    lines.append("```")
    lines.append("\t" + "\t".join(names_t))
    for i, nm in enumerate(names_t):
        row = [("%6.3f" % v) if not (isinstance(v, float) and math.isnan(v)) else "   -  " for v in mat_tp[i]]
        lines.append(nm + "\t" + "\t".join(row))
    lines.append("```\n")

    lines.append("## 三、物质遗产 vs 非遗 与 POI 的相关性对比\n")
    r_mat_poi = pearson(tvars["Material_Count"], tvars["POI_Total"])
    r_nh_poi = pearson(tvars["NH_Total"], tvars["POI_Total"])
    lines.append(f"- Material_Count ~ POI_Total (镇街): **r = {r_mat_poi:.3f}**")
    lines.append(f"- NH_Total ~ POI_Total (镇街)       : **r = {r_nh_poi:.3f}**")
    if r_mat_poi > r_nh_poi:
        lines.append("- 结论：物质遗产密度与 POI 总量的相关性**高于**非遗数量与 POI 总量，支持以物质遗产为主桥梁的方法选择。\n")
    else:
        lines.append("- 结论：当前数据下非遗数量与 POI 总量的相关性不低于物质遗产，需结合具体片区讨论（详见正文 5.2 节）。\n")

    lines.append("## 四、A 级景区副产品（n = %d）\n" % len(a_level))
    lines.append("| 指标对 | Pearson | Spearman |")
    lines.append("|--------|--------:|---------:|")
    for name, x, y in pairs:
        lines.append(f"| {name} | {pearson(x, y):.3f} | {spearman(x, y):.3f} |")
    lines.append("")
    lines.append("注：A 级评定样本量较小（n = %d），以上系数仅作为副产品参考。正文以 POI 评分与评论热度作为代理变量。" % len(a_level))

    with (OUT / "potential_summary.md").open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("[potential_correlation] done")
    print("  anchor corr n=%d" % len(anchors))
    print("  town corr n=%d" % len(rows_t))
    print("  a-level pairs: %d" % len(pairs))
    print("  material~poi r=%.3f,  nh_total~poi r=%.3f" % (r_mat_poi, r_nh_poi))


if __name__ == "__main__":
    main()
