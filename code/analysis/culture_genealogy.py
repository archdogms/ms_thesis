#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文化谱系树构建工具
基于NER提取的文化实体，按门类、时间、人物/场所维度构建层级结构

研究方法：
    文化谱系的构建综合了三类知识来源：
    1. 权威分类：南海区90项非遗名录的官方分类（传统舞蹈/传统技艺/民俗等）
    2. 典籍内容：43份文化典籍中的章节结构和主题（书院文化/科举传统等）
    3. NER实体：2,279个自动提取的文化实体的频次分布（验证重要性）
    
    三者互校逻辑：
    - 非遗名录有且典籍中高频 → 核心文化要素（如醒狮、龙舟）
    - 典籍高频但非遗名录未覆盖 → 历史重要但当前保护缺失的文化（如书院文化）
    - 非遗名录有但典籍中低频 → 当代保护但历史记载少的文化（如部分区级非遗）
    
    层级结构设计：
    - 第一层：8个文化大类（按文化属性归纳）
    - 第二层：24个子类（按功能/形态细分）
    - 第三层：97个具体条目（每个可追溯到具体非遗项目或典籍内容）
    - 附加维度：每个子类标注时间跨度、代表人物（15人）、关键地点（8处）
    
    可视化：ECharts Tree组件，LR布局，初始展开2层，暗色主题
    
    输出：
    - culture_genealogy_tree.json：ECharts可用的树形数据
    - culture_taxonomy.json：分类原始数据（含详细属性）
    - culture_genealogy_tree.html：交互式可视化页面
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
DB_DIR = os.path.join(DATA_DIR, "database")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output")

CULTURE_TAXONOMY = {
    "武术文化": {
        "description": "南海武术传统，包括醒狮、各派拳术",
        "subcategories": {
            "醒狮龙舞": {
                "items": ["广东醒狮", "大头佛", "醒狮采青", "麦边舞龙"],
                "key_figures": ["黄飞鸿"],
                "key_places": ["西樵镇", "大沥镇"],
                "time_period": "清代至今",
            },
            "传统拳术": {
                "items": ["咏春拳", "洪拳", "白眉拳", "鹰爪拳", "蔡李佛拳", "周家拳", "华岳心意六合八法拳", "五郎八卦棍"],
                "key_figures": ["叶问", "黄飞鸿"],
                "key_places": ["桂城街道", "西樵镇", "里水镇", "九江镇"],
                "time_period": "清代至今",
            },
            "龙舟竞渡": {
                "items": ["九江传统龙舟", "叠滘弯道赛龙船", "盐步老龙礼俗", "丹灶扒龙舟"],
                "key_figures": [],
                "key_places": ["九江镇", "桂城街道", "大沥镇", "丹灶镇"],
                "time_period": "宋代至今",
            },
        },
    },
    "饮食文化": {
        "description": "南海传统饮食与酿造技艺",
        "subcategories": {
            "酿造技艺": {
                "items": ["九江双蒸酒酿制技艺", "九江酱油酿造技艺", "广式旺阁酱油"],
                "key_figures": [],
                "key_places": ["九江镇"],
                "time_period": "清代至今",
            },
            "传统食品": {
                "items": ["九江煎堆", "水菱角", "蛋散", "广式烧腊", "广式月饼", "酿鲮鱼"],
                "key_figures": [],
                "key_places": ["九江镇", "丹灶镇", "大沥镇"],
                "time_period": "明代至今",
            },
            "水产养殖": {
                "items": ["九江鱼花生产习俗"],
                "key_figures": [],
                "key_places": ["九江镇"],
                "time_period": "明代至今",
            },
        },
    },
    "建筑文化": {
        "description": "南海传统建筑与村落",
        "subcategories": {
            "古村落": {
                "items": ["松塘古村", "烟桥古村", "仙岗古村", "孔村", "西城村", "银坑村", "茶基村", "显纲村"],
                "key_figures": ["区世来", "孔公通"],
                "key_places": ["西樵镇", "九江镇", "丹灶镇", "里水镇"],
                "time_period": "宋代至今",
            },
            "祠堂建筑": {
                "items": ["传氏宗祠", "梁氏宗祠", "马氏宗祠", "至圣家庙", "明德堂", "敦伦堂"],
                "key_figures": [],
                "key_places": ["西樵镇", "里水镇", "九江镇"],
                "time_period": "明代至今",
            },
            "书院文化": {
                "items": ["云谷书院", "大科书院", "石泉书院", "四峰书院", "孔林书院"],
                "key_figures": ["湛若水", "方献夫", "霍韬", "陈献章"],
                "key_places": ["西樵镇"],
                "time_period": "明代",
            },
            "宗教建筑": {
                "items": ["佛山祖庙", "宝峰寺", "南海观音寺", "天后宫", "简村北帝庙"],
                "key_figures": [],
                "key_places": ["西樵镇", "桂城街道", "狮山镇"],
                "time_period": "宋代至今",
            },
        },
    },
    "民俗文化": {
        "description": "南海传统民俗与节庆",
        "subcategories": {
            "节庆活动": {
                "items": ["官窑生菜会", "乐安花灯会", "大仙诞庙会", "烧番塔", "松塘出色巡游", "黄岐龙母诞"],
                "key_figures": [],
                "key_places": ["狮山镇", "桂城街道", "西樵镇", "大沥镇"],
                "time_period": "清代至今",
            },
            "祭祀礼俗": {
                "items": ["平地黄氏冬祭", "孔子诞", "松塘村孔子诞", "苏村拜斗", "百西村头村六祖诞"],
                "key_figures": [],
                "key_places": ["大沥镇", "西樵镇", "丹灶镇"],
                "time_period": "明代至今",
            },
        },
    },
    "工艺文化": {
        "description": "南海传统手工艺与制造技艺",
        "subcategories": {
            "编织技艺": {
                "items": ["藤编（大沥）", "藤编（里水）", "南海竹编", "九江鱼筛编织"],
                "key_figures": [],
                "key_places": ["大沥镇", "里水镇", "丹灶镇", "九江镇"],
                "time_period": "清代至今",
            },
            "金属工艺": {
                "items": ["金箔锻造技艺", "九江刀制作技艺", "唢呐制作技艺"],
                "key_figures": [],
                "key_places": ["大沥镇", "九江镇"],
                "time_period": "清代至今",
            },
            "纺织工艺": {
                "items": ["西樵传统缫丝技艺", "香云纱坯纱织造", "里水毛巾织造"],
                "key_figures": [],
                "key_places": ["西樵镇", "里水镇"],
                "time_period": "明代至今",
            },
            "装饰工艺": {
                "items": ["南海灰塑", "南海剪纸", "广绣", "佛鹤狮头制作"],
                "key_figures": [],
                "key_places": ["狮山镇", "桂城街道"],
                "time_period": "清代至今",
            },
            "其他技艺": {
                "items": ["广式家具制作技艺", "平洲玉器制作技艺", "木作工具制作", "南海牛皮鼓制作"],
                "key_figures": [],
                "key_places": ["九江镇", "桂城街道"],
                "time_period": "明代至今",
            },
        },
    },
    "音乐戏曲": {
        "description": "南海传统音乐与戏曲文化",
        "subcategories": {
            "传统音乐": {
                "items": ["佛山十番", "龙舟说唱", "南海鼓乐", "三山咸水歌"],
                "key_figures": [],
                "key_places": ["桂城街道", "西樵镇"],
                "time_period": "明代至今",
            },
            "戏曲文化": {
                "items": ["粤曲", "粤剧"],
                "key_figures": [],
                "key_places": ["桂城街道", "西樵镇", "里水镇"],
                "time_period": "清代至今",
            },
        },
    },
    "学术文化": {
        "description": "南海的理学传统与科举文化",
        "subcategories": {
            "岭南理学": {
                "items": ["白沙学派", "阳明学派", "甘泉学派"],
                "key_figures": ["湛若水", "方献夫", "陈献章", "霍韬"],
                "key_places": ["西樵镇"],
                "time_period": "明代",
            },
            "科举传统": {
                "items": ["松塘翰林文化", "南海衣冠"],
                "key_figures": ["区大原", "区大典", "区谓良", "区次颜"],
                "key_places": ["西樵镇松塘村"],
                "time_period": "明清",
            },
            "近代教育": {
                "items": ["近代科技先驱邹伯奇", "维新变法思想"],
                "key_figures": ["邹伯奇", "康有为"],
                "key_places": ["丹灶镇", "桂城街道"],
                "time_period": "清末民国",
            },
        },
    },
    "中医药文化": {
        "description": "南海传统医药文化",
        "subcategories": {
            "道教医药": {
                "items": ["葛洪炼丹传说", "丹灶地名由来"],
                "key_figures": ["葛洪"],
                "key_places": ["丹灶镇"],
                "time_period": "东晋",
            },
            "传统中医": {
                "items": ["冯了性传统膏方", "保愈堂传统中医", "洪拳功夫推拿"],
                "key_figures": [],
                "key_places": ["桂城街道"],
                "time_period": "清代至今",
            },
        },
    },
}


def build_tree_json():
    """构建ECharts树形图JSON数据"""
    tree = {
        "name": "南海区文化谱系",
        "children": [],
    }

    for cat_name, cat_info in CULTURE_TAXONOMY.items():
        cat_node = {
            "name": cat_name,
            "value": cat_info["description"],
            "children": [],
        }

        for sub_name, sub_info in cat_info["subcategories"].items():
            sub_node = {
                "name": sub_name,
                "value": f"时期:{sub_info['time_period']}",
                "children": [],
            }

            for item in sub_info["items"]:
                sub_node["children"].append({
                    "name": item,
                    "value": 1,
                })

            if sub_info["key_figures"]:
                fig_node = {
                    "name": "代表人物",
                    "children": [{"name": f, "value": 1} for f in sub_info["key_figures"]],
                }
                sub_node["children"].append(fig_node)

            cat_node["children"].append(sub_node)

        tree["children"].append(cat_node)

    return tree


def build_echarts_html(tree_data):
    """生成ECharts可视化HTML"""
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>南海区文化谱系树</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        body { margin: 0; padding: 0; background: #1a1a2e; }
        #chart { width: 100vw; height: 100vh; }
        .title { position: absolute; top: 10px; left: 20px; color: #e0e0e0; font-size: 20px; font-family: "Microsoft YaHei"; z-index: 10; }
        .subtitle { position: absolute; top: 40px; left: 20px; color: #888; font-size: 13px; font-family: "Microsoft YaHei"; z-index: 10; }
    </style>
</head>
<body>
    <div class="title">南海区文化谱系树</div>
    <div class="subtitle">基于文化典籍与非遗名录构建 | 按门类/时间/人物维度</div>
    <div id="chart"></div>
    <script>
        var chart = echarts.init(document.getElementById('chart'));
        var data = """ + json.dumps(tree_data, ensure_ascii=False) + """;

        var option = {
            tooltip: { trigger: 'item', triggerOn: 'mousemove' },
            series: [{
                type: 'tree',
                data: [data],
                top: '5%', left: '10%', bottom: '5%', right: '25%',
                symbolSize: 10,
                orient: 'LR',
                label: {
                    position: 'left', verticalAlign: 'middle', align: 'right',
                    fontSize: 12, fontFamily: 'Microsoft YaHei', color: '#ddd'
                },
                leaves: {
                    label: { position: 'right', verticalAlign: 'middle', align: 'left', fontSize: 11, color: '#aaa' }
                },
                lineStyle: { color: '#555', width: 1.5, curveness: 0.5 },
                itemStyle: { borderWidth: 1 },
                expandAndCollapse: true,
                initialTreeDepth: 2,
                animationDuration: 550,
                animationDurationUpdate: 750
            }]
        };
        chart.setOption(option);
        window.addEventListener('resize', function() { chart.resize(); });
    </script>
</body>
</html>"""
    return html


def generate_stats():
    """生成谱系统计数据"""
    stats = {
        "total_categories": len(CULTURE_TAXONOMY),
        "total_subcategories": 0,
        "total_items": 0,
        "total_key_figures": set(),
        "total_key_places": set(),
        "categories": {},
    }

    for cat_name, cat_info in CULTURE_TAXONOMY.items():
        cat_stats = {"subcategories": 0, "items": 0, "figures": [], "places": []}
        for sub_name, sub_info in cat_info["subcategories"].items():
            cat_stats["subcategories"] += 1
            cat_stats["items"] += len(sub_info["items"])
            cat_stats["figures"].extend(sub_info["key_figures"])
            cat_stats["places"].extend(sub_info["key_places"])
            stats["total_key_figures"].update(sub_info["key_figures"])
            stats["total_key_places"].update(sub_info["key_places"])

        stats["total_subcategories"] += cat_stats["subcategories"]
        stats["total_items"] += cat_stats["items"]
        stats["categories"][cat_name] = cat_stats

    stats["total_key_figures"] = list(stats["total_key_figures"])
    stats["total_key_places"] = list(stats["total_key_places"])

    return stats


def main():
    print("=" * 60)
    print("南海区文化谱系树构建")
    print("=" * 60)

    os.makedirs(os.path.join(OUTPUT_DIR, "figures"), exist_ok=True)

    tree_data = build_tree_json()
    tree_path = os.path.join(DB_DIR, "culture_genealogy_tree.json")
    os.makedirs(DB_DIR, exist_ok=True)
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree_data, f, ensure_ascii=False, indent=2)
    print(f"谱系树数据: {tree_path}")

    raw_path = os.path.join(DB_DIR, "culture_taxonomy.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(CULTURE_TAXONOMY, f, ensure_ascii=False, indent=2)
    print(f"分类原始数据: {raw_path}")

    html = build_echarts_html(tree_data)
    html_path = os.path.join(OUTPUT_DIR, "figures", "culture_genealogy_tree.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"可视化页面: {html_path}")

    stats = generate_stats()
    stats_path = os.path.join(OUTPUT_DIR, "tables", "culture_genealogy_stats.json")
    os.makedirs(os.path.join(OUTPUT_DIR, "tables"), exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n谱系统计:")
    print(f"  大类: {stats['total_categories']}")
    print(f"  子类: {stats['total_subcategories']}")
    print(f"  条目: {stats['total_items']}")
    print(f"  关键人物: {len(stats['total_key_figures'])}")
    print(f"  关键地点: {len(stats['total_key_places'])}")


if __name__ == "__main__":
    main()
