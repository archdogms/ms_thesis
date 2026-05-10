#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
双谱系耦合分析工具
系统对比文化谱系与景点谱系，识别文旅融合的四种状态

研究方法：
    核心逻辑：文化资源="供给侧"（典籍记载的文化遗产），景点="需求侧"（游客可体验的旅游产品），
    两者的匹配程度决定文旅融合水平。
    
    实体对齐方法（四种匹配类型）：
    1. 实体对应：非遗项目名 ↔ 传承基地/博物馆名
       如 "九江双蒸酒酿制技艺" ↔ "九江双蒸博物馆"（最强匹配）
    2. 文化承载：文化人物/概念 ↔ 纪念场所
       如 "黄飞鸿武术文化" ↔ "黄飞鸿纪念馆"
    3. 空间共存：文化遗存 ↔ 所在景区
       如 "岭南理学/书院文化" ↔ "西樵山书院遗址"（有载体但体验化不足）
    4. 主题关联：文化主题 ↔ 主题景点
       如 "宗教信仰文化" ↔ "南海观音寺"
    
    耦合状态判定规则：
    - 强耦合 = 实体对应 或 文化承载 → 融合成功（文化有明确旅游载体）
    - 错位   = 空间共存 或 主题关联 → 挖掘不足（有关联但深度不够）
    - 缺失A  = 遍历非遗名录中无任何对应旅游产品的项目 → 文化未转化
    - 缺失B  = 遍历景点中无文化内涵支撑的现代设施 → 有形无魂
    
    耦合协调度模型（连续值0-1）：
    基于文化资源密度(C)和旅游发展度(T)两个系统的协调关系：
    - 耦合度 C_coupling = sqrt(C×T) / ((C+T)/2)
    - 综合发展指数 T_index = α×C + β×T  (α=β=0.5)
    - 耦合协调度 D = sqrt(C_coupling × T_index)
    分级: D≥0.8极高, D≥0.6高, D≥0.4中, D≥0.2低, D<0.2极低
    
    输出：
    - coupling_results.json：四种状态的详细列表+镇街耦合协调度
    - coupling_summary.json：统计摘要+核心发现+优化建议
    - coupling_analysis.html：关系图+统计面板的交互式可视化
"""

import os
import sys
import json
import math
from collections import defaultdict, Counter

_AD_DIR = os.path.dirname(os.path.abspath(__file__))
if _AD_DIR not in sys.path:
    sys.path.insert(0, _AD_DIR)
from analysis_data_sources import (
    culture_mentions_by_town,
    load_pois_list,
    review_total_by_town,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
DB_DIR = os.path.join(DATA_DIR, "database")
GIS_DIR = os.path.join(DATA_DIR, "gis")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")

CULTURE_TO_SCENIC_MAP = [
    {"culture": "广东醒狮", "scenic": "南海醒狮传承基地", "match_type": "实体对应", "notes": "国家级非遗有传承基地"},
    {"culture": "广东醒狮", "scenic": "黄飞鸿中联电缆武术龙狮协会", "match_type": "实体对应", "notes": "省级传承基地"},
    {"culture": "咏春拳", "scenic": "咏春拳叶问宗支传承基地", "match_type": "实体对应", "notes": "省级非遗有传承基地"},
    {"culture": "九江双蒸酒酿制技艺", "scenic": "九江双蒸博物馆", "match_type": "实体对应", "notes": "省级非遗有博物馆载体"},
    {"culture": "佛山十番", "scenic": "佛山十番传承基地", "match_type": "实体对应", "notes": "国家级非遗有传承基地"},
    {"culture": "盐步老龙礼俗", "scenic": "盐步老龙礼俗传承基地", "match_type": "实体对应", "notes": "省级非遗有传承基地"},
    {"culture": "官窑生菜会", "scenic": "官窑生菜会传承基地", "match_type": "实体对应", "notes": "省级非遗有传承基地"},
    {"culture": "黄飞鸿武术文化", "scenic": "黄飞鸿纪念馆", "match_type": "文化承载", "notes": "武术文化核心人物有纪念馆"},
    {"culture": "康有为维新思想", "scenic": "康有为故居", "match_type": "文化承载", "notes": "近代思想文化有故居载体"},
    {"culture": "松塘翰林文化", "scenic": "松塘古村", "match_type": "空间共存", "notes": "科举文化保存在古村落中"},
    {"culture": "岭南理学/书院文化", "scenic": "西樵山书院遗址", "match_type": "空间共存", "notes": "四大书院遗址在西樵山"},
    {"culture": "岭南理学/书院文化", "scenic": "西樵山风景名胜区", "match_type": "空间共存", "notes": "理学名山同为景区"},
    {"culture": "古村落建筑文化", "scenic": "烟桥古村", "match_type": "空间共存", "notes": "古村落同时是旅游景点"},
    {"culture": "古村落建筑文化", "scenic": "仙岗古村", "match_type": "空间共存", "notes": "古村落同时是旅游景点"},
    {"culture": "孔子后裔文化", "scenic": "孔村至圣家庙", "match_type": "文化承载", "notes": "孔子后裔聚居有祠堂"},
    {"culture": "宗教信仰文化", "scenic": "南海观音寺", "match_type": "主题关联", "notes": "佛教文化有实体寺庙"},
    {"culture": "宗教信仰文化", "scenic": "宝峰寺", "match_type": "主题关联", "notes": "西樵山古刹"},
    {"culture": "葛洪炼丹传说", "scenic": "丹灶葛洪炼丹传说纪念地", "match_type": "文化承载", "notes": "道教医药文化有纪念地"},
    {"culture": "龙舟竞渡", "scenic": "叠滘弯道赛龙船", "match_type": "实体对应", "notes": "市级非遗活态传承"},
    {"culture": "平洲玉器文化", "scenic": "平洲玉器街", "match_type": "主题关联", "notes": "传统技艺有商业街区"},
    {"culture": "水乡文化", "scenic": "里水梦里水乡", "match_type": "主题关联", "notes": "岭南水乡风情旅游"},
    {"culture": "乐安花灯会", "scenic": "乐安花灯会传承基地", "match_type": "实体对应", "notes": "省级非遗有传承基地"},
    {"culture": "大沥锦龙盛会", "scenic": "大沥镇锦龙盛会传承基地", "match_type": "实体对应", "notes": "市级非遗有传承基地"},
    {"culture": "藤编技艺", "scenic": "藤编里水传承基地", "match_type": "实体对应", "notes": "省级非遗有传承基地"},
    {"culture": "金箔锻造技艺", "scenic": "金箔锻造技艺传习所", "match_type": "实体对应", "notes": "省级非遗有传习所"},
]

UNMATCHED_CULTURE = [
    {"name": "洪拳（南海洪拳）", "level": "省级", "category": "武术文化", "reason": "无专门的展示场馆或体验景点"},
    {"name": "白眉拳", "level": "市级", "category": "武术文化", "reason": "仅有学校传承基地，缺少面向游客的体验点"},
    {"name": "九江煎堆制作技艺", "level": "省级", "category": "饮食文化", "reason": "无专门的展示或体验场所"},
    {"name": "九江鱼花生产习俗", "level": "省级", "category": "饮食文化", "reason": "养殖基地未开发为旅游点"},
    {"name": "广式家具制作技艺", "level": "省级", "category": "工艺文化", "reason": "无面向公众的展示馆"},
    {"name": "西樵传统缫丝技艺", "level": "市级", "category": "工艺文化", "reason": "丝厂传承但未开放旅游"},
    {"name": "香云纱坯纱织造技艺", "level": "市级", "category": "工艺文化", "reason": "企业传承，未开放参观"},
    {"name": "龙舟说唱", "level": "市级", "category": "音乐戏曲", "reason": "无固定演出场所"},
    {"name": "三山咸水歌", "level": "市级", "category": "音乐戏曲", "reason": "濒危状态，缺少活态展示"},
    {"name": "南海灰塑", "level": "市级", "category": "工艺文化", "reason": "技艺散落于古建筑中，缺少专题展馆"},
    {"name": "南海竹编", "level": "市级", "category": "工艺文化", "reason": "传承基地在文化站，未开放旅游"},
    {"name": "赤坎盲公话", "level": "区级", "category": "民间文学", "reason": "方言类非遗，缺少体验载体"},
    {"name": "南海农谚", "level": "区级", "category": "民间文学", "reason": "口头文学，缺少实体展示"},
    {"name": "西樵山传说", "level": "区级", "category": "民间文学", "reason": "与景区融合度低"},
]

UNMATCHED_SCENIC = [
    {"name": "千灯湖公园", "category": "公园绿地", "reason": "现代城市公园，缺少文化内涵植入"},
    {"name": "映月湖公园", "category": "公园绿地", "reason": "休闲空间，文化底蕴薄弱"},
    {"name": "南海湿地公园", "category": "公园绿地", "reason": "生态景观，与南海文化关联弱"},
    {"name": "南海影视城", "category": "休闲娱乐", "reason": "影视拍摄基地，非南海本土文化表达"},
    {"name": "南海体育中心", "category": "体育设施", "reason": "现代设施，与传统体育文化关联弱"},
    {"name": "贤鲁岛", "category": "自然景观", "reason": "生态旅游为主，文化挖掘不足"},
]


def analyze_coupling():
    """执行耦合分析"""
    results = {
        "strong_coupling": [],
        "misalignment": [],
        "missing_A": [],
        "missing_B": [],
    }

    for mapping in CULTURE_TO_SCENIC_MAP:
        entry = {
            "culture_element": mapping["culture"],
            "scenic_spot": mapping["scenic"],
            "match_type": mapping["match_type"],
            "notes": mapping["notes"],
        }

        if mapping["match_type"] in ("实体对应", "文化承载"):
            results["strong_coupling"].append(entry)
        elif mapping["match_type"] in ("空间共存", "主题关联"):
            entry["status"] = "空间或主题层面有联系，但深度融合不足"
            results["misalignment"].append(entry)

    for item in UNMATCHED_CULTURE:
        results["missing_A"].append({
            "culture_element": item["name"],
            "level": item["level"],
            "category": item["category"],
            "reason": item["reason"],
            "suggestion": f"建议开发{item['name']}相关的体验景点或展示空间",
        })

    for item in UNMATCHED_SCENIC:
        results["missing_B"].append({
            "scenic_spot": item["name"],
            "category": item["category"],
            "reason": item["reason"],
            "suggestion": f"建议为{item['name']}注入南海本土文化内容",
        })

    return results


def generate_coupling_summary(results):
    """生成耦合分析摘要"""
    summary = {
        "strong_coupling_count": len(results["strong_coupling"]),
        "misalignment_count": len(results["misalignment"]),
        "missing_A_count": len(results["missing_A"]),
        "missing_B_count": len(results["missing_B"]),
        "key_findings": [
            f"共识别 {len(results['strong_coupling'])} 对强耦合文旅要素，主要集中在非遗传承基地与对应文化项目",
            f"发现 {len(results['misalignment'])} 对错位关系，文化与景点仅在空间或主题层面有关联，深度融合不足",
            f"识别 {len(results['missing_A'])} 项文化资源未转化为旅游产品，包括多项省级和市级非遗",
            f"发现 {len(results['missing_B'])} 个景点缺少文化内涵支撑，多为现代公园和休闲设施",
        ],
        "recommendations": [
            "优先开发省级非遗中尚未旅游化的项目（如洪拳、煎堆技艺、鱼花习俗等）",
            "为千灯湖等现代公园注入南海非遗元素（如十番音乐演出、醒狮表演等）",
            "加强书院文化与西樵山景区的深度融合（如复原书院场景、开发理学体验课程）",
            "推动九江片区的美食非遗集群化展示（双蒸酒+煎堆+鱼花+酱油）",
            "开发古村落连线旅游路线（松塘-烟桥-仙岗-孔村），提升文旅体验丰富度",
        ],
    }
    return summary


def build_coupling_html(results, summary):
    """生成耦合分析可视化HTML"""
    strong = results["strong_coupling"]
    misalign = results["misalignment"]
    missing_a = results["missing_A"]
    missing_b = results["missing_B"]

    links_data = []
    categories = set()
    for item in strong:
        links_data.append({"source": item["culture_element"], "target": item["scenic_spot"], "lineStyle": {"color": "#4CAF50", "width": 2}})
        categories.add(item["culture_element"])
        categories.add(item["scenic_spot"])
    for item in misalign:
        links_data.append({"source": item["culture_element"], "target": item["scenic_spot"], "lineStyle": {"color": "#FF9800", "width": 1.5, "type": "dashed"}})
        categories.add(item["culture_element"])
        categories.add(item["scenic_spot"])

    nodes_data = []
    for name in categories:
        is_culture = any(name == s["culture_element"] for s in strong + misalign)
        is_scenic = any(name == s["scenic_spot"] for s in strong + misalign)
        if is_culture and not is_scenic:
            nodes_data.append({"name": name, "category": 0, "symbolSize": 25})
        elif is_scenic and not is_culture:
            nodes_data.append({"name": name, "category": 1, "symbolSize": 20})
        else:
            nodes_data.append({"name": name, "category": 2, "symbolSize": 22})

    for item in missing_a[:8]:
        nodes_data.append({"name": item["culture_element"], "category": 2, "symbolSize": 15})
    for item in missing_b[:5]:
        nodes_data.append({"name": item["scenic_spot"], "category": 3, "symbolSize": 15})

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>双谱系耦合分析</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        body {{ margin: 0; padding: 0; background: #0f0f23; font-family: "Microsoft YaHei"; }}
        #chart {{ width: 70vw; height: 100vh; float: left; }}
        #panel {{ width: 28vw; height: 100vh; float: right; overflow-y: auto; padding: 20px; box-sizing: border-box; color: #ddd; }}
        h2 {{ color: #4ECDC4; border-bottom: 1px solid #333; padding-bottom: 8px; }}
        h3 {{ color: #FF6B6B; margin-top: 16px; }}
        .stat {{ display: inline-block; background: #1a1a3e; padding: 8px 16px; margin: 4px; border-radius: 6px; }}
        .stat .num {{ font-size: 24px; font-weight: bold; }}
        .green {{ color: #4CAF50; }} .orange {{ color: #FF9800; }} .red {{ color: #f44336; }} .blue {{ color: #2196F3; }}
        ul {{ padding-left: 16px; }} li {{ margin: 4px 0; font-size: 13px; color: #aaa; }}
        .finding {{ background: #1a1a3e; padding: 10px; margin: 6px 0; border-radius: 4px; border-left: 3px solid #4ECDC4; font-size: 13px; }}
    </style>
</head>
<body>
    <div id="chart"></div>
    <div id="panel">
        <h2>双谱系耦合分析</h2>
        <div>
            <div class="stat"><div class="num green">{summary['strong_coupling_count']}</div>强耦合</div>
            <div class="stat"><div class="num orange">{summary['misalignment_count']}</div>错位</div>
            <div class="stat"><div class="num red">{summary['missing_A_count']}</div>缺失A(未转化)</div>
            <div class="stat"><div class="num blue">{summary['missing_B_count']}</div>缺失B(有形无魂)</div>
        </div>
        <h3>核心发现</h3>
        {"".join(f'<div class="finding">{f}</div>' for f in summary["key_findings"])}
        <h3>优化建议</h3>
        <ul>{"".join(f'<li>{r}</li>' for r in summary["recommendations"])}</ul>
        <h3>缺失A: 文化未转化</h3>
        <ul>{"".join(f'<li><b>{a["culture_element"]}</b>({a["level"]}) - {a["reason"]}</li>' for a in missing_a[:8])}</ul>
        <h3>缺失B: 有形无魂</h3>
        <ul>{"".join(f'<li><b>{b["scenic_spot"]}</b> - {b["reason"]}</li>' for b in missing_b)}</ul>
    </div>
    <script>
        var chart = echarts.init(document.getElementById('chart'));
        var option = {{
            legend: {{ data: ['文化要素', '景点', '未转化文化', '缺魂景点'], top: 10, textStyle: {{color: '#aaa'}} }},
            series: [{{
                type: 'graph', layout: 'force', roam: true, draggable: true,
                categories: [
                    {{name: '文化要素', itemStyle: {{color: '#FF6B6B'}}}},
                    {{name: '景点', itemStyle: {{color: '#4ECDC4'}}}},
                    {{name: '未转化文化', itemStyle: {{color: '#f44336'}}}},
                    {{name: '缺魂景点', itemStyle: {{color: '#2196F3'}}}}
                ],
                data: {json.dumps(nodes_data, ensure_ascii=False)},
                links: {json.dumps(links_data, ensure_ascii=False)},
                label: {{ show: true, fontSize: 11, color: '#ddd', fontFamily: 'Microsoft YaHei' }},
                force: {{ repulsion: 300, edgeLength: [80, 200], gravity: 0.1 }},
                lineStyle: {{ curveness: 0.2 }}
            }}]
        }};
        chart.setOption(option);
    </script>
</body>
</html>"""
    return html


def calculate_coupling_coordination():
    """按镇街计算耦合协调度（连续值模型）"""
    towns = ["桂城街道", "西樵镇", "九江镇", "丹灶镇", "狮山镇", "大沥镇", "里水镇"]

    nh_path = os.path.join(GIS_DIR, "nanhai_nonheritage.json")

    pois = load_pois_list()
    nonheritage = []
    if os.path.exists(nh_path):
        with open(nh_path, "r", encoding="utf-8") as f:
            nonheritage = json.load(f)

    poi_by_town = Counter(p.get("town", "未知") for p in pois)
    nh_by_town = Counter(nh.get("town", "未知") for nh in nonheritage)

    culture_town_map = culture_mentions_by_town(towns)
    review_by_town = review_total_by_town(pois)

    max_poi = max(poi_by_town.values()) if poi_by_town else 1
    max_nh = max(nh_by_town.values()) if nh_by_town else 1
    max_culture = max(max(culture_town_map.values()) if culture_town_map else 0, 1)
    max_rev = max(review_by_town.values()) if review_by_town else 0
    use_rev = max_rev > 0

    results = []
    for town in towns:
        poi_count = poi_by_town.get(town, 0)
        nh_count = nh_by_town.get(town, 0)
        culture_mentions = culture_town_map.get(town, 0)
        rev = review_by_town.get(town, 0)

        T = poi_count / max_poi if max_poi > 0 else 0
        if use_rev:
            C = (
                nh_count / max_nh * 0.35
                + culture_mentions / max_culture * 0.25
                + rev / max_rev * 0.4
            )
        else:
            C = (
                nh_count / max_nh * 0.6 + culture_mentions / max_culture * 0.4
            ) if max_nh > 0 else 0

        if C > 0 and T > 0:
            coupling = math.sqrt(C * T) / ((C + T) / 2)
        else:
            coupling = 0

        t_index = 0.5 * C + 0.5 * T
        D = math.sqrt(abs(coupling * t_index))

        if D >= 0.8:
            level = "极高协调"
        elif D >= 0.6:
            level = "高度协调"
        elif D >= 0.4:
            level = "中度协调"
        elif D >= 0.2:
            level = "低度协调"
        else:
            level = "极低协调"

        results.append({
            "town": town,
            "poi_count": poi_count,
            "nonheritage_count": nh_count,
            "culture_mentions": culture_mentions,
            "review_total_merged": rev,
            "C_weights_note": "0.35nh+0.25culture+0.4review" if use_rev else "0.6nh+0.4culture",
            "T_tourism": round(T, 4),
            "C_culture": round(C, 4),
            "coupling_degree": round(coupling, 4),
            "development_index": round(t_index, 4),
            "coordination_degree": round(D, 4),
            "level": level,
        })

    results.sort(key=lambda x: x["coordination_degree"], reverse=True)
    return results


def main():
    print("=" * 60)
    print("双谱系耦合分析")
    print("=" * 60)

    results = analyze_coupling()
    summary = generate_coupling_summary(results)

    coordination = calculate_coupling_coordination()
    results["coordination"] = coordination

    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "figures"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "tables"), exist_ok=True)

    result_path = os.path.join(DB_DIR, "coupling_results.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"耦合分析结果: {result_path}")

    summary["coordination_by_town"] = coordination
    summary_path = os.path.join(OUTPUT_DIR, "tables", "coupling_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"分析摘要: {summary_path}")

    print(f"\n镇街耦合协调度:")
    for c in coordination:
        print(f"  {c['town']}: D={c['coordination_degree']:.3f} ({c['level']})")

    html = build_coupling_html(results, summary)
    html_path = os.path.join(OUTPUT_DIR, "figures", "coupling_analysis.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"可视化: {html_path}")

    print(f"\n耦合状态统计:")
    print(f"  强耦合: {summary['strong_coupling_count']}")
    print(f"  错位: {summary['misalignment_count']}")
    print(f"  缺失A(文化未转化): {summary['missing_A_count']}")
    print(f"  缺失B(有形无魂): {summary['missing_B_count']}")


if __name__ == "__main__":
    main()
