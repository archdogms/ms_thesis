# 2026-05-10 官方资源扩展成果包

本成果包落实 5.10 清单中的五项后续处理：484 处不可移动文物地址空间化与去重、历史文化资源名录的面/线/点分类处理、11 家博物馆补入展示型文化桥梁，以及“典籍—官方—旅游”诊断拆分。

## 一、输出文件

| 类型 | 文件 | 说明 |
|---|---|---|
| 表格/数据 | `official_resources_20260510.csv` | 官方资源统一空间化与去重底表 |
| 表格/数据 | `official_resources_20260510.geojson` | 官方资源 GeoJSON |
| 表格/数据 | `official_resources_summary_20260510.csv` | 官方资源类型/镇街/方法摘要 |
| 表格/数据 | `official_grid_coverage_20260510.csv` | 500 m 网格官方资源覆盖表 |
| 表格/数据 | `official_town_coverage_20260510.csv` | 镇街官方资源覆盖摘要 |
| 表格/数据 | `diagnostic_split_grid_20260510.csv` | 网格三维诊断拆分表 |
| 表格/数据 | `diagnostic_split_by_town_20260510.csv` | 镇街三维诊断拆分表 |
| 表格/数据 | `cultural_anchors_expanded_20260510.json` | 扩展文化锚点库 JSON |
| 表格/数据 | `cultural_anchors_added_20260510.csv` | 扩展文化锚点新增项 CSV |
| 图件 | `figures/official_resources_spatialization_20260510.png` | 官方资源空间化图 |
| 图件 | `figures/official_grid_coverage_20260510.png` | 500 m 网格官方资源覆盖图 |
| 图件 | `figures/diagnostic_split_by_town_20260510.png` | 典籍—官方—旅游诊断拆分图 |

## 二、空间化方法

本轮没有把近似结果写成精确测绘成果，而是为每条资源保留 `spatial_method` 与 `spatial_confidence` 字段。空间化优先级为：现有文化锚点精确命中、POI 名称命中、名称模糊命中、地址片段/村社地名质心、镇街代表点兜底。历史文化名镇使用镇街面；历史文化名村、传统村落、特色古村落使用村社中心缓冲面；历史文化街区使用街区中心缓冲面，作为后续人工数字化前的规划分析代理。

### 空间化来源统计

| 方法 | 数量 |
|---|---:|
| address_token_centroid | 138 |
| existing_anchor_name | 95 |
| town_representative_point | 148 |
| poi_name_fuzzy | 134 |
| poi_name_exact | 73 |
| existing_anchor_fuzzy | 5 |

### 去重状态

| 状态 | 数量 |
|---|---:|
| new_candidate | 424 |
| duplicate_existing_anchor | 96 |
| matched_poi_only | 73 |

### 资源类型

| 类型 | 数量 |
|---|---:|
| 不可移动文物 | 484 |
| 博物馆 | 11 |
| 灌溉遗产 | 1 |
| 历史文化名镇 | 1 |
| 历史文化名村 | 7 |
| 传统村落 | 18 |
| 历史文化街区 | 3 |
| 历史建筑名录 | 34 |
| 特色古村落 | 34 |

### 镇街分布

| 镇街 | 数量 |
|---|---:|
| 狮山镇 | 142 |
| 西樵镇 | 126 |
| 桂城街道 | 46 |
| 里水镇 | 83 |
| 丹灶镇 | 50 |
| 大沥镇 | 90 |
| 九江镇 | 56 |

## 三、图件

![官方资源空间化结果](figures/official_resources_spatialization_20260510.png)

![官方资源网格覆盖](figures/official_grid_coverage_20260510.png)

![三维诊断拆分](figures/diagnostic_split_by_town_20260510.png)

## 四、论文可用表述

5.10 扩展后，官方资源层不再只依赖 165 条已空间化载体，而是把 4.22 补充的 484 处不可移动文物、11 家博物馆和历史文化资源名录纳入统一底表。不可移动文物与博物馆按点状资源处理；历史文化名镇使用镇街面；历史文化名村、传统村落、特色古村落和历史文化街区在缺少官方村域或街区矢量边界时，采用“地名中心 + 缓冲面”的代理表达，并保留空间化方法和置信度字段。本轮另生成扩展锚点库 `cultural_anchors_expanded_20260510.json`，用于后续替换或校验 `cultural_anchors.json`。由此形成“典籍/图谱 C、官方资源 O、旅游热度 T”的三维诊断附表，可用于解释某些区域是典籍叙事不足、官方认定不足，还是旅游转化不足。

需要在论文中明确：本成果属于规划分析尺度的空间代理结果，不等同于文物测绘坐标或法定保护范围；后续若用于项目落地，应以主管部门公布坐标、保护范围和人工校核边界为准。
