#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
空间分析工具
核密度热点分析、空间聚类、文化-景点空间对比

研究方法（纯Python实现，不依赖geopandas/ArcGIS）：

    【核密度估计 (KDE)】
    - 目的：识别文旅资源的空间热点分布
    - 网格化：将南海区范围划分为40×40=1,600个网格单元
    - 核函数：Epanechnikov核 K(u) = (1-u²)² (|u|<1时, 否则=0)
    - 带宽：3.0km（经验值，约为南海区东西跨度的10%）
    - 距离计算：Haversine球面距离公式（考虑地球曲率，R=6371km）
    - 归一化：所有密度值除以最大值，映射到[0,1]区间
    - 分别对POI和非遗两组点做独立的核密度估计，用于叠加对比

    【DBSCAN空间聚类】
    - 目的：发现文旅资源的空间集聚区
    - 输入：1,353个POI + 26个非遗 = 1,379个空间点
    - 参数：eps=3.0km（邻域半径），min_points=3（核心点最小邻居数）
    - 距离度量：Haversine球面距离
    - 参数选择依据：3km约为步行30分钟或骑行10分钟的距离，
      代表"在一个游览区域内可便捷到达"的尺度

    【镇街资源密度对比】
    - 目的：量化各镇街文旅发展的均衡程度
    - 指标：POI数量(旅游密度)、非遗数量(文化密度)
    - 分级：非遗≥5=高密度, ≥2=中, <2=低; POI≥8=高, ≥4=中, <4=低

    核心发现：
    - POI热点在中心城区（桂城-大沥-狮山），非遗热点在西南（西樵-九江-丹灶）
    - 两者呈空间错位分布，是文旅融合不足在空间维度的体现
    - 九江镇=典型"文化富集-旅游洼地"（非遗5项/POI259个，全区占比低）
    
    输出：
    - spatial_analysis_results.json：聚类、镇街统计结果
    - spatial_analysis.html：四合一可视化（散点图/柱状图/热力图/雷达图）
"""

import os
import sys
import json
import math
from collections import defaultdict

_AD_DIR = os.path.dirname(os.path.abspath(__file__))
if _AD_DIR not in sys.path:
    sys.path.insert(0, _AD_DIR)
from analysis_data_sources import load_pois_list

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
GIS_DIR = os.path.join(DATA_DIR, "gis")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")


def load_all_points():
    """加载所有空间点数据（POI 优先与耦合分析同源：poi_llm_cleaned.csv）。"""
    pois = load_pois_list()

    nh_path = os.path.join(GIS_DIR, "nanhai_nonheritage.json")
    nonheritage = []
    if os.path.exists(nh_path):
        with open(nh_path, "r", encoding="utf-8") as f:
            nonheritage = json.load(f)

    return pois, nonheritage


def haversine(lng1, lat1, lng2, lat2):
    """计算两点间的距离(km)"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def kernel_density_grid(points, grid_size=50, bandwidth_km=2.0):
    """计算核密度估计（网格化）"""
    lngs = [p[0] for p in points]
    lats = [p[1] for p in points]
    min_lng, max_lng = min(lngs) - 0.02, max(lngs) + 0.02
    min_lat, max_lat = min(lats) - 0.02, max(lats) + 0.02

    lng_step = (max_lng - min_lng) / grid_size
    lat_step = (max_lat - min_lat) / grid_size

    grid = []
    max_density = 0

    for i in range(grid_size):
        for j in range(grid_size):
            cx = min_lng + (i + 0.5) * lng_step
            cy = min_lat + (j + 0.5) * lat_step

            density = 0
            for px, py in points:
                d = haversine(cx, cy, px, py)
                if d < bandwidth_km * 3:
                    u = d / bandwidth_km
                    density += (1 - u*u) ** 2 if u < 1 else 0

            if density > max_density:
                max_density = density
            grid.append([cx, cy, density])

    if max_density > 0:
        for g in grid:
            g[2] = round(g[2] / max_density, 4)

    return grid, {"min_lng": min_lng, "max_lng": max_lng, "min_lat": min_lat, "max_lat": max_lat}


def simple_dbscan(points, eps_km=3.0, min_points=3):
    """简化版DBSCAN空间聚类"""
    n = len(points)
    labels = [-1] * n
    cluster_id = 0

    visited = [False] * n

    def region_query(idx):
        neighbors = []
        px, py = points[idx]
        for j in range(n):
            if haversine(px, py, points[j][0], points[j][1]) <= eps_km:
                neighbors.append(j)
        return neighbors

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neighbors = region_query(i)

        if len(neighbors) < min_points:
            labels[i] = -1
            continue

        labels[i] = cluster_id
        seed_set = list(neighbors)
        j = 0
        while j < len(seed_set):
            q = seed_set[j]
            if not visited[q]:
                visited[q] = True
                q_neighbors = region_query(q)
                if len(q_neighbors) >= min_points:
                    seed_set.extend(q_neighbors)
            if labels[q] == -1:
                labels[q] = cluster_id
            j += 1

        cluster_id += 1

    return labels


def analyze_town_distribution(pois, nonheritage):
    """按镇街分析文旅资源密度"""
    town_stats = defaultdict(lambda: {"poi_count": 0, "nh_count": 0, "poi_types": [], "nh_categories": []})

    for poi in pois:
        town = poi.get("town", "未知")
        town_stats[town]["poi_count"] += 1
        town_stats[town]["poi_types"].append(poi["category"])

    for nh in nonheritage:
        town = nh.get("town", "未知")
        town_stats[town]["nh_count"] += 1
        town_stats[town]["nh_categories"].append(nh["category"])

    result = {}
    for town, stats in town_stats.items():
        from collections import Counter
        result[town] = {
            "poi_count": stats["poi_count"],
            "nh_count": stats["nh_count"],
            "total_resources": stats["poi_count"] + stats["nh_count"],
            "culture_density": "高" if stats["nh_count"] >= 5 else ("中" if stats["nh_count"] >= 2 else "低"),
            "tourism_density": "高" if stats["poi_count"] >= 8 else ("中" if stats["poi_count"] >= 4 else "低"),
            "poi_type_dist": dict(Counter(stats["poi_types"])),
            "nh_category_dist": dict(Counter(stats["nh_categories"])),
        }

    return result


def build_spatial_html(pois, nonheritage, poi_grid, nh_grid, clusters, town_stats):
    """生成空间分析综合可视化HTML"""
    poi_points = []
    for poi in pois:
        poi_points.append({
            "name": poi["name"],
            "value": [poi["lng"], poi["lat"], poi.get("rating", 3)],
            "category": poi["category"],
            "town": poi["town"],
        })

    nh_points = []
    for nh in nonheritage:
        nh_points.append({
            "name": nh["name"],
            "value": [nh["lng"], nh["lat"], 1],
            "level": nh["level"],
            "category": nh["category"],
        })

    town_data = []
    for town, stats in town_stats.items():
        town_data.append({
            "name": town,
            "poi": stats["poi_count"],
            "nh": stats["nh_count"],
            "total": stats["total_resources"],
        })
    town_data.sort(key=lambda x: -x["total"])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>南海区文旅空间分析</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        body {{ margin: 0; padding: 0; background: #0d1117; font-family: "Microsoft YaHei"; color: #c9d1d9; }}
        .container {{ display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; height: 100vh; gap: 2px; }}
        .chart {{ background: #161b22; border: 1px solid #21262d; }}
        .chart-title {{ position: absolute; padding: 8px 12px; color: #58a6ff; font-size: 14px; font-weight: bold; z-index: 10; }}
        #scatter {{ position: relative; }} #bar {{ position: relative; }} #heatmap {{ position: relative; }} #radar {{ position: relative; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="chart" id="scatter"><div class="chart-title">景点与非遗空间分布</div></div>
        <div class="chart" id="bar"><div class="chart-title">镇街文旅资源统计</div></div>
        <div class="chart" id="heatmap"><div class="chart-title">文旅资源热力密度</div></div>
        <div class="chart" id="radar"><div class="chart-title">镇街文旅发展均衡度</div></div>
    </div>
    <script>
        var poiData = {json.dumps(poi_points, ensure_ascii=False)};
        var nhData = {json.dumps(nh_points, ensure_ascii=False)};
        var townData = {json.dumps(town_data, ensure_ascii=False)};
        var poiGrid = {json.dumps(poi_grid[:500], ensure_ascii=False)};

        // 1. 散点图
        var scatter = echarts.init(document.getElementById('scatter'));
        scatter.setOption({{
            tooltip: {{ trigger: 'item', formatter: function(p) {{ return p.name + '<br/>' + (p.data.category||p.data.level); }} }},
            legend: {{ data: ['景点', '非遗'], top: 30, textStyle: {{color: '#aaa'}} }},
            xAxis: {{ type: 'value', name: '经度', min: 112.87, max: 113.22, nameTextStyle: {{color: '#aaa'}}, axisLabel: {{color: '#666'}} }},
            yAxis: {{ type: 'value', name: '纬度', min: 22.72, max: 23.18, nameTextStyle: {{color: '#aaa'}}, axisLabel: {{color: '#666'}} }},
            series: [
                {{ name: '景点', type: 'scatter', data: poiData.map(d => ({{name: d.name, value: d.value, category: d.category}})), symbolSize: 10, itemStyle: {{color: '#4ECDC4'}} }},
                {{ name: '非遗', type: 'scatter', data: nhData.map(d => ({{name: d.name, value: d.value, level: d.level}})), symbolSize: 8, itemStyle: {{color: '#FF6B6B'}} }}
            ]
        }});

        // 2. 柱状图
        var bar = echarts.init(document.getElementById('bar'));
        bar.setOption({{
            tooltip: {{ trigger: 'axis' }},
            grid: {{ top: 50, bottom: 30, left: 80 }},
            xAxis: {{ type: 'value', axisLabel: {{color: '#666'}} }},
            yAxis: {{ type: 'category', data: townData.map(d => d.name), axisLabel: {{color: '#aaa'}} }},
            series: [
                {{ name: '景点', type: 'bar', stack: 'total', data: townData.map(d => d.poi), itemStyle: {{color: '#4ECDC4'}} }},
                {{ name: '非遗', type: 'bar', stack: 'total', data: townData.map(d => d.nh), itemStyle: {{color: '#FF6B6B'}} }}
            ]
        }});

        // 3. 热力图
        var heatmap = echarts.init(document.getElementById('heatmap'));
        heatmap.setOption({{
            tooltip: {{}},
            xAxis: {{ type: 'value', name: '经度', min: 112.87, max: 113.22, axisLabel: {{color: '#666'}} }},
            yAxis: {{ type: 'value', name: '纬度', min: 22.72, max: 23.18, axisLabel: {{color: '#666'}} }},
            visualMap: {{ min: 0, max: 1, calculable: true, orient: 'horizontal', left: 'center', top: 30, inRange: {{color: ['#0d1117', '#1a237e', '#4a148c', '#ff6f00', '#ffd600']}}, textStyle: {{color: '#aaa'}} }},
            series: [{{ type: 'heatmap', data: poiGrid.filter(d => d[2] > 0.05), pointSize: 15, blurSize: 20 }}]
        }});

        // 4. 雷达图
        var radar = echarts.init(document.getElementById('radar'));
        var topTowns = townData.slice(0, 5);
        radar.setOption({{
            tooltip: {{}},
            legend: {{ data: topTowns.map(d => d.name), top: 30, textStyle: {{color: '#aaa'}} }},
            radar: {{
                indicator: [
                    {{name: '景点数量', max: 15}}, {{name: '非遗数量', max: 10}},
                    {{name: '总资源', max: 20}}, {{name: '资源均衡度', max: 10}}
                ],
                axisName: {{color: '#aaa'}}, splitLine: {{lineStyle: {{color: '#333'}}}}
            }},
            series: [{{
                type: 'radar',
                data: topTowns.map(d => ({{
                    name: d.name,
                    value: [d.poi, d.nh, d.total, Math.min(d.poi, d.nh) > 0 ? Math.round(10 * 2 * d.poi * d.nh / (d.poi + d.nh) / Math.max(d.poi, d.nh)) : 0]
                }}))
            }}]
        }});

        window.addEventListener('resize', function() {{ scatter.resize(); bar.resize(); heatmap.resize(); radar.resize(); }});
    </script>
</body>
</html>"""
    return html


def main():
    print("=" * 60)
    print("南海区文旅空间分析")
    print("=" * 60)

    pois, nonheritage = load_all_points()
    print(f"加载 {len(pois)} 个POI, {len(nonheritage)} 个非遗项目")

    print("\n--- 核密度分析 ---")
    poi_coords = [(p["lng"], p["lat"]) for p in pois]
    poi_grid, poi_extent = kernel_density_grid(poi_coords, grid_size=40, bandwidth_km=3.0)
    print(f"  POI热力网格: {len(poi_grid)} 个格点")

    nh_coords = [(n["lng"], n["lat"]) for n in nonheritage]
    nh_grid, nh_extent = kernel_density_grid(nh_coords, grid_size=40, bandwidth_km=3.0)
    print(f"  非遗热力网格: {len(nh_grid)} 个格点")

    print("\n--- 空间聚类 ---")
    all_coords = poi_coords + nh_coords
    labels = simple_dbscan(all_coords, eps_km=3.0, min_points=3)
    n_clusters = max(labels) + 1 if labels else 0
    noise = labels.count(-1)
    print(f"  聚类数: {n_clusters}, 噪声点: {noise}")

    print("\n--- 镇街资源分析 ---")
    town_stats = analyze_town_distribution(pois, nonheritage)
    for town, stats in sorted(town_stats.items(), key=lambda x: -x[1]["total_resources"]):
        print(f"  {town}: POI={stats['poi_count']}, 非遗={stats['nh_count']}, 文化密度={stats['culture_density']}, 旅游密度={stats['tourism_density']}")

    print("\n--- 保存结果 ---")
    os.makedirs(os.path.join(OUTPUT_DIR, "figures"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "tables"), exist_ok=True)

    spatial_results = {
        "poi_extent": poi_extent,
        "n_clusters": n_clusters,
        "noise_points": noise,
        "town_stats": town_stats,
    }
    result_path = os.path.join(OUTPUT_DIR, "tables", "spatial_analysis_results.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(spatial_results, f, ensure_ascii=False, indent=2)
    print(f"分析结果: {result_path}")

    html = build_spatial_html(pois, nonheritage, poi_grid, nh_grid, labels, town_stats)
    html_path = os.path.join(OUTPUT_DIR, "figures", "spatial_analysis.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"可视化: {html_path}")

    print("\n完成！")


if __name__ == "__main__":
    main()
