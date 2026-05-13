# `ms_thesis` 论文定稿资料迁移 — 完整执行说明

本文档供你在 **`knowledge_graph` 仓库根目录** 执行：将论文正文、模板、插图、`output/tables` 全量、**`data/corpus` 典籍（原样复制：当前为 `corpus_index.json` + 53 篇 `*.md`）**、**阶段性任务与答辩材料（`docs/tasks` 不含 html、`docs/ppt`、`docs/papers`）**，以及**正文与附录核对所需的核心数据**复制到 **`ms_thesis/`**，便于后续新建独立 Git 仓库归档或提交。

**执行前请阅读全文**；含密钥的文件默认**不复制**。

---

## 1. 约定

| 项 | 说明 |
|----|------|
| **源根目录** | 本仓库根目录，下文记为 `$RepoRoot`（例如 `C:\Users\ms\Desktop\mid\knowledge_graph`）。 |
| **目标根目录** | `$RepoRoot\ms_thesis`（与先前方案中的 `@ms_thesis` 对应）。 |
| **路径风格** | 文档内以 Windows 反斜杠书写；PowerShell 中可用 `Join-Path` 避免手写错误。 |
| **正文中的插图引用** | `docs/毕业论文_正文.md` 以 `../output/figures/` 为根；其中 **图 4.1、4.2、6.1** 使用子路径 **`../output/figures/knowledge_graph/`**；其余多为根下 `thesis_*.png` 与 `fig*.png`。复制到 `ms_thesis` 时保持 **`ms_thesis\docs\`** 与 **`ms_thesis\output\figures\`**（含 `maps/`、`grid_culture_tourism/`、`knowledge_graph/` 子目录）的相对关系与主仓一致即可。 |
| **禁止复制** | `config.json`（含 API 密钥）、`~$*.docx` 锁文件、`.vscode`、`.git`（新仓自行 `git init`）。 |

---

## 2. 数据通扫与版本对照（2026-05-10）

本节基于对仓库内**相关 JSON/CSV 的实际读取**与**文件体积、修改时间**核对，用于定稿前判断「以谁为准」及迁移包是否缺件。**未打开**每个数十 MB 文件的逐行全文（无必要）；对关键小文件已读字段，对大体量文件已读结构头与统计脚本结果。

### 2.1 语料规模（典籍）— **`data/corpus` 原样复制**

| 文件 / 目录 | 版本信息（文件内字段） | 结论 |
|-------------|------------------------|------|
| `data/corpus/`（整目录） | 当前为 **`corpus_index.json`** + **53** 篇 **`*.md`**，无其它后缀 | **不做筛选**：`Copy-Item` 将目录下现有文件**原样**复制到 `ms_thesis\data\corpus\`（与主仓一致）。 |
| `data/corpus/corpus_index.json` | `prepared_at`: **2026-03-15 16:51**；`total`: **53**；各篇 `char_count` 之和 = **8,991,098** | 与正文「约 899 万字」一致；**定稿数字以此索引为准**。 |
| `data/corpus/*.md` | 与索引一一对应 | 即论文所用标准化典籍正文；篇数与索引 `total` 对齐即可。 |

### 2.2 抽取进度与合并图谱（实体 / 关系）

| 文件 | 版本信息（文件内字段） | 结论 |
|------|------------------------|------|
| `data/entities_relations/progress.json` | `task`: `qwen_extraction`；`model`: **qwen3.5-plus**；`total_files`/`completed` 列表：**53** 篇；`stats.entities`: **61,218**，`stats.relations`: **42,024**；`last_update`: **2026-03-28 20:41:02**；`status`: **completed** | **唯一权威进度文件**（仓库内已无 `output/qwen_extraction/progress.json`）。对应正文「原始抽取」规模；**与合并后 8,048 / 19,382 口径不同**，勿混用。正文第 4 章引用路径即此。 |
| `data/entities_relations/merged_entities.json` | 根对象 `total` 等统计；实体列表长度（脚本解析）= **8,048** | 与正文「合并图谱 8,048 实体」一致。 |
| `data/entities_relations/merged_relations.json` | 关系列表长度（脚本解析）= **19,382** | 与正文「19,382 关系」一致。 |
| `data/entities_relations/neo4j_frequency_rank_palette.json` | 与合并库同批更新（磁盘时间 **2026-04-21**） | 与正文「六档配色」叙述配套，建议与 `merged_*.json` 同包迁移。 |

**体积提示**：`merged_entities.json` ≈ **3.6 MB**，`merged_relations.json` ≈ **6.3 MB**（合计约 **10 MB**），并非「数百 MB」；若仍嫌大可只带 `progress.json` + 表。磁盘时间均为 **2026-04-21**，与 `progress.json` 内 `last_update` 不同属正常（后续可能做过合并/导出触达时间戳）。

### 2.3 POI 全链路文件分层（务必区分用途）

下列路径均以仓库根为起点；**条数 13,512** 为正文口径时，以 `poi_cleaned` 主库（JSON/CSV）为准。

#### A. 原始 / 中间输入（`data/poi/`，本仓现存）

| 文件 | 内容概要 | 与正文关系 |
|------|----------|------------|
| `data/poi/poi_amap.json` | 高德侧拉取的 POI 原始或中间结果 | **原始供给**之一；正文「三源」中的高德源；非最终条数口径。 |
| `data/poi/poi_shapefile.json` | 公开 Shapefile 整合的南海 POI 底座 | **原始供给**之一；正文「Shapefile」源；非最终条数口径。 |
| `data/poi/poi_cleaned.json` | 三源融合、去重、镇街与类目、文化锚点挂接等之后的 **`pois` 列表** | **主库**；列表长度 **13,512**；`build_indices` 等分析脚本直接读取；磁盘时间 **2026-03-24**。 |

> 说明：索引文档中曾出现 `nanhai_poi_real.json` 等文件名，**当前仓库 `data/poi` 下未检出**；若你本地另有百度等原始 JSON，请自行加入 `$RepoRoot\data\poi\` 后再执行迁移脚本，或在外部资料包中一并归档。

#### B. 清洗结果导出表（`output/tables/`，随「全表」复制）

| 文件 | 内容概要 | 与正文关系 |
|------|----------|------------|
| `poi_cleaned.csv` | `poi_cleaned.json` 的 **扁平导出** | **附录 / Excel 核对主用**；数据行 **13,512**；时间 **2026-03-30**。 |
| `poi_llm_cleaned.csv` | 在清洗结果上经 **本地 LLM（qwen3.5:9b）** 纠类 / 文旅相关性后的版本 | 与 `poi_cleaned` **同行数**；正文若写「大模型参与 POI 类目」则引用此表；时间 **2026-03-30**。 |
| `poi_entity_linkage.csv` | POI 与图谱实体匹配明细 | 网格「文化侧」与图谱链路的输入之一；**2026-04-21**。 |
| `poi_entity_linkage_overview.json` | 上表及网格链路的 **汇总钉书钉**（如 `poi_in_bbox`、`anchor_matched_to_entity`） | 与 §2.9 叙述一致。 |
| `poi_with_reviews.json` | POI 与评论侧挂接的中间 JSON | 评论热度进入 THI 等时的中间产物。 |
| `nh_poi_match.csv` | 非遗 ↔ POI 匹配 | 耦合桥梁分析。 |
| `review_poi_matched.csv`、`review_poi_link.csv` | 评论景点名 ↔ POI **五段式匹配**结果 | 评论 **16,391** 条叙事与 POI 关联证据。 |
| `spatial_town_stats.csv`、`spatial_analysis_results.json` 等 | 空间分析用表中含 **镇街 POI 计数** 等 | 与 KDE / 镇街对比图配套。 |

#### C. LLM 清洗运行记录（`output/poi_llm_clean/`）

| 文件 | 内容概要 | 是否必拷 |
|------|----------|----------|
| `progress.json` | `model`: **qwen3.5:9b**；`total_rows`: **13,512**；含已完成 `batch_*` 列表 | **建议拷**：证明 LLM 批处理全覆盖；体积约 **0.9 MB**。 |
| `clean_log.log` | 清洗过程日志 | **可选**：排错用。 |

### 2.4 非遗名录 + **`docs/tasks/4.22` 桥梁口径**

#### 2.4.1 表文件：`nonheritage.csv` vs `nonheritage_full90.csv`

| 文件 | 观测 | 结论 |
|------|------|------|
| `output/tables/nonheritage.csv` | 约 **26** 行数据 + 表头；列含经纬度、`geocode_*`；时间 **2026-03-18** | **早期精简 / 子集**，与「90 项」全量口径不一致。 |
| `output/tables/nonheritage_full90.csv` | **90** 行数据 + 表头；列主要为 name/level/category/town；时间 **2026-05-13** | **论文耦合、指数、GIS 全量非遗均以 90 项为准**；与 `data/gis/nanhai_nonheritage_full90.json` 顶层 `total`: **90** 一致。省级项目“藤编”按项目去重为 1 项，但镇街归属同时记录大沥镇和里水镇。 |

#### 2.4.2 与 `docs/tasks/4.22` 阶段成果对齐（**迁移时整夹复制**，见第 4 节）

`docs/tasks/4.22/` 当前含：`4.22.md`（讨论纪要）、`20260421.md` / `20260421.pdf`（**2026-04-21** 桥梁与网格口径说明）、`不可移动文物Excel.xls`、`附件：历史文化资源名录.xls`、`南海区11家博物馆基本信息2025.6.xlsx` 等。其中 **`20260421.md` 已写明的桥梁与网格数字**与论文叙述应对齐：

- **主桥梁（物质性文化载体）**：不可移动文物 **80**、文化景观 **19**、历史文化名村与传统村落 **12**、圩市街区 **18**；空间上集中于西樵、九江、丹灶；并说明桂城、大沥、里水、狮山在**原始数据源中无对应物质载体录入**（非处理遗漏）。
- **补充桥梁**：区级以上非遗 **90 项全量**（与 `nonheritage_full90` / `indices_overview` 的 `n_nonheritage` 一致）。
- **软连接**：无稳定空间载体的非遗与典籍知识 → 文本与关系图层，**不参与**空间匹配。
- **网格错位表（500 m）**：0 跳 vs 1 跳五类格数（如沉睡潜力 **99 → 170**、核心耦合 **6 → 8** 等）见该文档 §「图 1」表格；与 `output/tables/grid_overview_kg.json` 中 `category_counts_0hop` / `1hop` **一致**。

定稿迁移时：**除表与 JSON 外，务必将 `docs/tasks/4.22` 整目录**（及 `docs/tasks/5.10` 等同类阶段稿，若存在）**一并复制**，避免纸质附件与仓库脱节。

#### 2.4.3 相关「参考文献」PDF 与答辩材料

正文参考文献所涉 PDF 位于 `docs/papers/`；开题 / 中期 **pptx + pdf** 等位于 `docs/ppt/`。第 4 节脚本 **递归复制 `docs/papers`、`docs/ppt` 与 `docs/tasks`**（阶段性 md / pdf / xlsx / 附图等）；**`docs/tasks` 下所有 `*.html` 不复制**（临时导出，见第 4 节 `robocopy /XF`）。

### 2.5 GIS：点位 JSON 与 GeoJSON

| 文件 | 版本信息 | 结论 |
|------|----------|------|
| `data/gis/nanhai_nonheritage.json` | 数组项为带经纬度、geocode 的非遗点 | 与短表 `nonheritage.csv` 同型，偏「可上图」点集。 |
| `data/gis/nanhai_nonheritage_full90.json` | 顶层 `total`: **91**；`source` 说明南海博物馆官网等 | **全量非遗空间与统计口径**；与 `nonheritage_full90.csv` 配套。 |
| `data/gis/scenic_a_level.json` | `_version`: **2026-04-19**；`items` 长度 **16**（与 A 级样本分析一致） | 与 `indices_a_level.csv`、`a_level_correlation.csv`（同日 **2026-04-19**）为同一轮分析。 |
| `data/gis/*.geojson`（如 `nanhai_towns_real.geojson`、`nanhai_towns_voronoi_approx.geojson`、`nanhai_boundary.geojson`） | 镇街/边界几何；**2026-04-21** 等晚于部分旧 shp | 若附录或复现制图需要，建议在脚本中**可选复制**（默认脚本已补充，见第 4 节）。 |

### 2.6 文化锚点：`cultural_anchors.json` vs `cultural_anchors.bak.json`

| 文件 | 观测 | 结论 |
|------|------|------|
| `data/anchors/cultural_anchors.json` | 顶层 `total`: **220**；`type_stats` 分项与正文「桥梁构成」叙述一致；时间 **2026-04-21** | **唯一主表**；迁移必拷。 |
| `data/anchors/cultural_anchors.bak.json` | 时间 **2026-03-24**，体积较小 | **备份**；默认**不拷**以免双份歧义。 |

### 2.7 耦合结果：`data/database` vs `output/analysis`

| 文件 | 观测 | 结论 |
|------|------|------|
| `data/database/coupling_results.json` | 时间 **2026-03-30**，体积略大 | 与 `output/analysis/coupling_results.json`（**2026-03-24**）**前几项 `strong_coupling` 结构一致**；以 **较新日期** 作备份主份更稳妥。 |
| `output/analysis/coupling_results.json` | 略旧 | 与上为**同类叙事数据**；若只收一份，**优先 `data/database`**；当前脚本**两处皆拷**，体积均小（约 **13 KB**），并存无害。 |
| `output/tables/coupling_summary.json` | **2026-03-30** | 镇街协调度等**文字化汇总**，与答辩 PPT 口径相关；保留。 |

### 2.8 网格与知识图谱网格：`grid_*` vs `grid_*_kg`

| 文件 | 版本信息（文件内） | 结论 |
|------|----------------------|------|
| `output/tables/grid_overview.json` | `generated_at`: **2026-04-21 22:31:45**；文化侧权重含 **OAI**；`n_cells_total`: **4662**；错位分层规则见 `thresholds` | **基础口径**（锚点层文化 vs 旅游）。 |
| `output/tables/grid_overview_kg.json` | `generated_at`: **2026-04-21 22:31:46**；文化侧含 **official / mentions**；`category_counts_0hop` / `1hop` | **知识图谱 0-hop / 1-hop** 错位计数；与正文图 6.1 双口径叙述对应。**两文件需同时保留**，不可只拷其一。 |
| `grid_indices.csv` / `grid_indices_kg.csv` 等同批 | 磁盘日期 **2026-04-21** | 与上配套。 |

### 2.9 指数与相关分析（CMI / OAI / THI / MI）

| 文件 | 版本信息（文件内） | 结论 |
|------|----------------------|------|
| `output/tables/indices_overview.json` | `generated_at`: **2026-04-19 16:19:24**；`n_anchors`: **165**，`n_nonheritage`: **91**，`n_a_level`: **16**；`mi_category_counts` 四类格子数与正文一致 | **全文指数叙事的主摘要**；定稿必对。 |
| `output/tables/indices_anchors.csv` 等 | 同日 **2026-04-19** | 与 `indices_overview` 同轮。 |
| `output/tables/poi_entity_linkage_overview.json` | 无 `generated_at`；`entities_total`: **8048**，`relations_total`: **19382**，与合并库一致 | 与网格/图谱链路的**总览钉书钉**；建议保留。 |

### 2.10 体验分：`experience_scores.csv` 与 `experience_scores.json`

| 文件 | 观测 | 结论 |
|------|------|------|
| `experience_scores.csv` | 约 **1.2 MB**，**2026-03-18** | 表格式，便于 Excel。 |
| `experience_scores.json` | 约 **4.8 MB**，**2026-03-15** | 同源另一类序列化，**信息冗余**；定稿若只备一份，**保留 CSV 即可**；当前「全量 `tables`」复制会两份皆在，可接受。 |

### 2.11 评论侧

| 文件 | 观测 | 结论 |
|------|------|------|
| `data/reviews/review_summary_merged.json` | 约 **1.0 MB**，**2026-03-24** | 与 `output/tables/review_summary_merged.csv` 同源不同形；**建议仍拷 JSON** 供脚本复用。 |
| `data/reviews/merged_reviews_supp.json` | 约 **9.0 MB** | **补充评论聚合**；非每章必需；**默认不拷**，需要时单独 `Copy-Item`（见第 4 节可选块）。 |

### 2.12 其他大体量表（通扫摘要）

| 文件 | 大小（约） | 说明 |
|------|------------|------|
| `output/tables/review_poi_matched.csv` | **6.0 MB** | 评论—POI 匹配明细。 |
| `output/tables/reviews_detail.csv` | **6.5 MB** | 评论明细。 |
| `output/tables/triple_map_data.json` | **7.0 MB** | 三联映射中间结果；与 `triple_map_feasibility.md` 同批 **2026-04-14**。 |
| `output/tables/place_entity_index.json` | **0.96 MB** | 地名—实体索引。 |
| `output/analysis/scenic_genealogy_tree.json` | **~1.8 MB** | 景点谱系树可视化数据。 |
| `output/analysis/scenic_town_tree.json` | **~1.5 MB** | 镇街—景点树。 |
| `data/poi/poi_cleaned.json` | **~7.1 MB** | POI 主 JSON。 |
| `output/neo4j/neo4j_llm_edges.csv` | **~0.36 MB** | LLM 边表；节点表约 **0.58 MB**。 |

### 2.13 `output/tables` 全文件清单（名称 · 字节 · 修改日期）

下列 **44** 个文件为当前仓库 `output/tables` 目录通扫结果（**整目录应迁入 `ms_thesis`**）：

| 文件名 | 大小（字节） | 修改日期 |
|--------|----------------|----------|
| `a_level_correlation.csv` | 188 | 2026-04-19 |
| `coupling_analysis.csv` | 4170 | 2026-03-18 |
| `coupling_summary.json` | 4046 | 2026-03-30 |
| `culture_entities.csv` | 132501 | 2026-03-18 |
| `culture_genealogy_stats.json` | 3326 | 2026-03-15 |
| `experience_scores.csv` | 1200306 | 2026-03-18 |
| `experience_scores.json` | 4994431 | 2026-03-15 |
| `grid_entity_linkage.csv` | 125315 | 2026-04-21 |
| `grid_indices.csv` | 385578 | 2026-04-21 |
| `grid_indices_kg.csv` | 507715 | 2026-04-21 |
| `grid_overview.json` | 6351 | 2026-04-21 |
| `grid_overview_kg.json` | 1409 | 2026-04-21 |
| `grid_town_summary.csv` | 511 | 2026-04-21 |
| `grid_town_summary_kg.csv` | 702 | 2026-04-21 |
| `indices_a_level.csv` | 1150 | 2026-04-19 |
| `indices_anchors.csv` | 41289 | 2026-04-19 |
| `indices_nonheritage.csv` | 6282 | 2026-04-19 |
| `indices_overview.json` | 873 | 2026-04-19 |
| `indices_town_summary.csv` | 704 | 2026-04-19 |
| `located_entities.csv` | 53227 | 2026-04-14 |
| `nh_coupling_detail.json` | 29792 | 2026-03-31 |
| `nh_coupling_summary.csv` | 187 | 2026-03-31 |
| `nh_entity_match.csv` | 10014 | 2026-03-31 |
| `nh_poi_match.csv` | 10187 | 2026-03-31 |
| `nonheritage.csv` | 3698 | 2026-03-18 |
| `nonheritage_full90.csv` | 4935 | 2026-03-01 |
| `place_entity_index.json` | 984398 | 2026-04-14 |
| `poi_cleaned.csv` | 2748239 | 2026-03-30 |
| `poi_entity_linkage.csv` | 1239001 | 2026-04-21 |
| `poi_entity_linkage_overview.json` | 465 | 2026-04-21 |
| `poi_llm_cleaned.csv` | 2996575 | 2026-03-30 |
| `poi_with_reviews.json` | 103275 | 2026-04-14 |
| `potential_correlation_anchor.csv` | 792 | 2026-04-19 |
| `potential_correlation_town.csv` | 900 | 2026-04-19 |
| `potential_summary.md` | 1951 | 2026-04-19 |
| `review_poi_link.csv` | 211053 | 2026-03-25 |
| `review_poi_matched.csv` | 6298826 | 2026-03-30 |
| `review_summary_merged.csv` | 176426 | 2026-03-18 |
| `reviews_detail.csv` | 6798767 | 2026-03-18 |
| `spatial_analysis_results.json` | 5274 | 2026-03-30 |
| `spatial_town_stats.csv` | 294 | 2026-03-18 |
| `town_analysis_input.csv` | 428 | 2026-04-19 |
| `town_entity_linkage.csv` | 1824 | 2026-04-21 |
| `triple_map_data.json` | 7368088 | 2026-04-14 |
| `triple_map_feasibility.md` | 1779 | 2026-04-14 |

### 2.14 Git 上「两条路径」的正文文件

若 `git status` 同时出现 `docs/毕业论文_正文.md` 与 `docs\毕业论文_正文.md`，在 Windows 上多为**同一物理文件**的显示差异；以 **`git hash-object` 或 IDE 最近保存** 确认无分裂副本即可，迁移时只拷一次 `docs\毕业论文_正文.md`（脚本已写）。

---

## 3. 目标目录结构（推荐）

执行完成后应接近以下布局（**保持正文与 `../output/figures` 的相对路径有效**）：

```text
ms_thesis/
  README.md                          # 可选：本包用途说明
  pictures/                          # 与主仓根目录 pictures/ 一致：Neo4j 子图等 PNG（与 knowledge_graph 内为同批复制）
  docs/
    templates/                       # 学校模板（整目录复制）
    毕业论文_正文.md
    毕业论文关键文件与路径索引.md
    ms_thesis_迁移执行说明.md
    毕业论文大纲.md                  # 若你以 for_word 为准可改复制列表
    毕业论文大纲_for_word.md
    tasks/                           # 阶段性成果：md / pdf / xlsx / 子目录 4.22、5.10 等（递归；不含 html）
    papers/                          # 参考文献 PDF 等（递归）
    ppt/                             # 开题 / 中期：pptx、pdf、样式等（递归）
  output/
    figures/                         # 正文引用插图
    tables/                          # 全量导出表（与主仓 output/tables 一致）
    analysis/                        # 耦合与谱系树 JSON
    neo4j/                           # 可选：节点边 CSV + cypher
    poi_llm_clean/                   # 可选：progress.json
  data/
    anchors/                         # 文化锚点、谱系辅助
    corpus/
      corpus_index.json              # 篇目与字数索引
      *.md                           # 53 篇标准化典籍全文（必拷）
    gis/                             # 非遗与 A 级景区 JSON + 镇街/边界 GeoJSON（见第 4 节脚本）
    poi/
      poi_amap.json                  # 高德原始/中间
      poi_shapefile.json             # Shapefile 整合中间
      poi_cleaned.json               # 三源融合主库（体积大，见第 7 节）
    reviews/
      review_summary_merged.json
    entities_relations/              # 图谱进度、合并总库、配色（体积大，见第 7 节）
    database/
      coupling_results.json
  tools/
    export_thesis_docx.py
    prepare_thesis_assets.py
  code/                              # 论文相关代码节选（与主仓 code/ 子目录一致，见 code/README.md）
    processing/                      # API/本地 LLM 抽取、语料、POI、export_csv
    analysis/                        # 指数、相关、空间、网格、耦合、三联映射等
    data_processing/                 # 评论—POI 匹配
    collection/                      # OCR、POI/评论/非遗采集
```

若你希望 **`ms_thesis` 根目录即新仓库根**，上述结构可直接 `cd ms_thesis && git init`。

---

## 4. 一键复制脚本（PowerShell）

在 **PowerShell** 中执行；将第一行 `$RepoRoot` 改成你的本机路径（或已在该仓库根目录时改用 `Get-Location`）。

```powershell
# ========= 可改：仓库根 =========
$RepoRoot = "C:\Users\ms\Desktop\mid\knowledge_graph"
Set-Location $RepoRoot

$Dest = Join-Path $RepoRoot "ms_thesis"
$ErrorActionPreference = "Stop"

function Ensure-Dir($p) { New-Item -ItemType Directory -Force -Path $p | Out-Null }

# ---------- 目录 ----------
Ensure-Dir (Join-Path $Dest "docs\templates")
Ensure-Dir (Join-Path $Dest "docs\ppt")
Ensure-Dir (Join-Path $Dest "docs\papers")
Ensure-Dir (Join-Path $Dest "docs\tasks")
Ensure-Dir (Join-Path $Dest "output\figures")
Ensure-Dir (Join-Path $Dest "output\tables")
Ensure-Dir (Join-Path $Dest "output\analysis")
Ensure-Dir (Join-Path $Dest "output\neo4j")
Ensure-Dir (Join-Path $Dest "output\poi_llm_clean")
Ensure-Dir (Join-Path $Dest "data\anchors")
Ensure-Dir (Join-Path $Dest "data\corpus")
Ensure-Dir (Join-Path $Dest "data\gis")
Ensure-Dir (Join-Path $Dest "data\poi")
Ensure-Dir (Join-Path $Dest "data\reviews")
Ensure-Dir (Join-Path $Dest "data\entities_relations")
Ensure-Dir (Join-Path $Dest "data\database")
Ensure-Dir (Join-Path $Dest "tools")

# ---------- 文档与模板 ----------
Copy-Item -Force "docs\毕业论文_正文.md" (Join-Path $Dest "docs\")
Copy-Item -Force "docs\毕业论文关键文件与路径索引.md" (Join-Path $Dest "docs\")
if (Test-Path "docs\毕业论文大纲.md") { Copy-Item -Force "docs\毕业论文大纲.md" (Join-Path $Dest "docs\") }
if (Test-Path "docs\毕业论文大纲_for_word.md") { Copy-Item -Force "docs\毕业论文大纲_for_word.md" (Join-Path $Dest "docs\") }
if (Test-Path "docs\毕业论文_正文_定稿.docx") { Copy-Item -Force "docs\毕业论文_正文_定稿.docx" (Join-Path $Dest "docs\") }
Copy-Item -Recurse -Force "docs\templates\*" (Join-Path $Dest "docs\templates\")
if (Test-Path "docs\ms_thesis_迁移执行说明.md") {
  Copy-Item -Force "docs\ms_thesis_迁移执行说明.md" (Join-Path $Dest "docs\")
}
# 阶段性成果：docs/tasks（递归，排除 *.html）
$TasksSrc = Join-Path $RepoRoot "docs\tasks"
$TasksDst = Join-Path $Dest "docs\tasks"
if (Test-Path $TasksSrc) {
  cmd /c "robocopy `"$TasksSrc`" `"$TasksDst`" /E /XF *.html /NFL /NDL /NJH /NJS /nc /ns /np"
}
if (Test-Path "docs\papers") {
  Copy-Item -Recurse -Force "docs\papers" (Join-Path $Dest "docs\")
}
if (Test-Path "docs\ppt") {
  Copy-Item -Recurse -Force "docs\ppt" (Join-Path $Dest "docs\")
}

# ---------- 插图（与正文 grep 一致；KG 类见 knowledge_graph 子目录）----------
$figs = @(
  "thesis_data_pipeline.png",
  "thesis_poi_structure.png","fig2_category_scatter.png","thesis_a_level_correlation.png",
  "fig4_density_overlay.png","fig3_town_bar.png",
  "thesis_anchor_correlation_heatmap.png","fig5_jiujiang_zoom.png"
)
foreach ($n in $figs) {
  $src = Join-Path "output\figures" $n
  if (Test-Path $src) { Copy-Item -Force $src (Join-Path $Dest "output\figures\") }
}
foreach ($sub in @("maps","grid_culture_tourism","knowledge_graph")) {
  $sd = Join-Path "output\figures" $sub
  if (Test-Path $sd) {
    $dd = Join-Path $Dest "output\figures\$sub"
    New-Item -ItemType Directory -Force -Path $dd | Out-Null
    Copy-Item -Force (Join-Path $sd "*.png") $dd -ErrorAction SilentlyContinue
  }
}
$kgFlat = @("thesis_llm_extraction_pipeline.png","thesis_kg_examples.png","thesis_mismatch_maps.png")
$kgDest = Join-Path $Dest "output\figures\knowledge_graph"
New-Item -ItemType Directory -Force -Path $kgDest | Out-Null
foreach ($n in $kgFlat) {
  $src = Join-Path "output\figures" $n
  if ((Test-Path $src) -and -not (Test-Path (Join-Path $kgDest $n))) { Copy-Item -Force $src $kgDest }
}
if (Test-Path "pictures") {
  $pDest = Join-Path $Dest "pictures"
  New-Item -ItemType Directory -Force -Path $pDest | Out-Null
  cmd /c "robocopy `"$(Resolve-Path pictures)`" `"$pDest`" *.png /E /NFL /NDL /NJH /NJS /nc /ns /np"
  cmd /c "robocopy `"$(Resolve-Path pictures)`" `"$kgDest`" *.png /E /NFL /NDL /NJH /NJS /nc /ns /np"
}

# ---------- 论文用表：output/tables 全量 ----------
Copy-Item -Force "output\tables\*" (Join-Path $Dest "output\tables\")

# ---------- output/analysis ----------
if (Test-Path "output\analysis") {
  Copy-Item -Force "output\analysis\*.json" (Join-Path $Dest "output\analysis\")
}

# ---------- Neo4j 导出（可选大体量，见第 7 节）----------
if (Test-Path "output\neo4j") {
  Copy-Item -Force "output\neo4j\*.csv" (Join-Path $Dest "output\neo4j\") -ErrorAction SilentlyContinue
  Copy-Item -Force "output\neo4j\*.cypher" (Join-Path $Dest "output\neo4j\") -ErrorAction SilentlyContinue
}

# ---------- POI LLM 清洗记录 ----------
if (Test-Path "output\poi_llm_clean\progress.json") {
  Copy-Item -Force "output\poi_llm_clean\progress.json" (Join-Path $Dest "output\poi_llm_clean\")
}
if (Test-Path "output\poi_llm_clean\clean_log.log") {
  Copy-Item -Force "output\poi_llm_clean\clean_log.log" (Join-Path $Dest "output\poi_llm_clean\")
}

# ---------- 典籍：data/corpus 原样复制（当前为 corpus_index.json + *.md）----------
if (Test-Path "data\corpus") {
  Copy-Item -Recurse -Force "data\corpus\*" (Join-Path $Dest "data\corpus\")
}

# ---------- data：锚点、GIS、评论、耦合备份 ----------
$anchorFiles = @(
  "cultural_anchors.json","culture_taxonomy.json","culture_genealogy_tree.json"
)
foreach ($n in $anchorFiles) {
  $p = Join-Path "data\anchors" $n
  if (Test-Path $p) { Copy-Item -Force $p (Join-Path $Dest "data\anchors\") }
}
$gis = @("nanhai_nonheritage.json","nanhai_nonheritage_full90.json","scenic_a_level.json")
foreach ($n in $gis) {
  $p = Join-Path "data\gis" $n
  if (Test-Path $p) { Copy-Item -Force $p (Join-Path $Dest "data\gis\") }
}
# GIS GeoJSON（镇街/边界/非遗几何，附录或复现制图用）
$geo = @(
  "nanhai_towns_real.geojson","nanhai_towns_voronoi_approx.geojson","nanhai_boundary.geojson",
  "nanhai_nonheritage.geojson","nanhai_towns.geojson"
)
foreach ($n in $geo) {
  $p = Join-Path "data\gis" $n
  if (Test-Path $p) { Copy-Item -Force $p (Join-Path $Dest "data\gis\") }
}
if (Test-Path "data\reviews\review_summary_merged.json") {
  Copy-Item -Force "data\reviews\review_summary_merged.json" (Join-Path $Dest "data\reviews\")
}
if (Test-Path "data\database\coupling_results.json") {
  Copy-Item -Force "data\database\coupling_results.json" (Join-Path $Dest "data\database\")
}

# ---------- POI：data/poi 下全部 JSON（amap / shapefile / cleaned）----------
Get-ChildItem "data\poi\*.json" -ErrorAction SilentlyContinue | ForEach-Object {
  Copy-Item -Force $_.FullName (Join-Path $Dest "data\poi\")
}

# ---------- 实体关系：进度、合并总库、配色（大文件）----------
$er = @(
  "progress.json",
  "merged_entities.json",
  "merged_relations.json",
  "neo4j_frequency_rank_palette.json"
)
foreach ($n in $er) {
  $p = Join-Path "data\entities_relations" $n
  if (Test-Path $p) { Copy-Item -Force $p (Join-Path $Dest "data\entities_relations\") }
}

# ---------- 可选：评论补充聚合（约 9 MB，默认注释）----------
# if (Test-Path "data\reviews\merged_reviews_supp.json") {
#   Copy-Item -Force "data\reviews\merged_reviews_supp.json" (Join-Path $Dest "data\reviews\")
# }

# ---------- 论文导出脚本 ----------
Copy-Item -Force "tools\export_thesis_docx.py" (Join-Path $Dest "tools\")
Copy-Item -Force "tools\prepare_thesis_assets.py" (Join-Path $Dest "tools\")

# ---------- 论文相关代码节选 → code/（与 tools/run_ms_thesis_migration.py 中列表保持一致）----------
# 推荐：python tools\run_ms_thesis_migration.py（已含 code 复制与 code/README.md）
# 若坚持纯 PowerShell，可按该 Python 文件中的 code_relpaths 逐条 Copy-Item 到 (Join-Path $Dest "code\...")

# ---------- 根 README（可选）----------
@"
# ms_thesis 论文资料包

从 knowledge_graph 按 docs/ms_thesis_迁移执行说明.md 生成。
正文路径：docs/毕业论文_正文.md；插图：output/figures/（含 knowledge_graph 等子目录）；Neo4j 原图：pictures/；数据表：output/tables/；典籍：data/corpus/（原样）；阶段文档：docs/tasks（无 html）、docs/papers、docs/ppt；口径见本说明第 2 节。
请勿将含密钥的 config.json 提交到公开仓库。
"@ | Set-Content -Encoding utf8 (Join-Path $Dest "README.md")

Write-Host "Done. Output:" $Dest
```

**说明**：

- **`output\tables\*` 全量复制**：与「重要数据全部纳入」一致，含 `grid_*`、`triple_map_*`、`poi_entity_linkage*` 等当前目录下 **44** 个文件（清单见第 2.13 节）。
- **`merged_*.json`**：实测合计约 **10 MB** 量级（非数百 MB）；若仍不想带进新仓可注释 `$er` 中对应两行，仅用 `progress.json` + `output/tables` 核对正文数字。
- **`output\neo4j\*.csv`**：当前仓库内 LLM 节点/边表约 **1 MB** 内；不需要重导 Neo4j 时可整段注释「Neo4j 导出」块。
- **`docs\tasks`**：用 **`robocopy /XF *.html`** 递归复制，**排除一切 html**；`exit` 码 **0–7** 均视为成功。`tasks/figures` 下 png 仍保留，与 `output/figures` 正文图可能重复，以 `output/figures` 为定稿引用。
- **`data\corpus`**：普通 `Copy-Item`，与主仓目录内容**原样一致**（不单独处理 txt）。
- **`pictures\`**：Python 脚本在 Windows 上对 **`ms_thesis\pictures\`** 与 **`output\figures\knowledge_graph\`** 各执行一次 **robocopy**，避免中文文件名在 `shutil.copy2` 下偶发失败。

---

## 5. 文件清单速查（与脚本对应）

### 5.1 文档、答辩与阶段成果

| 源路径 | 目标 |
|--------|------|
| `docs/毕业论文_正文.md` | `ms_thesis/docs/` |
| `docs/毕业论文关键文件与路径索引.md` | `ms_thesis/docs/` |
| `docs/ms_thesis_迁移执行说明.md` | `ms_thesis/docs/` |
| `docs/毕业论文大纲.md`、`docs/毕业论文大纲_for_word.md` | `ms_thesis/docs/`（存在则复制） |
| `docs/毕业论文_正文_定稿.docx` | `ms_thesis/docs/`（存在则复制） |
| `docs/templates/*` | `ms_thesis/docs/templates/` |
| `docs/tasks/`（**递归**；脚本排除 `*.html`，含 `4.22`、`5.10`、`figures`、各期 md/pdf/xls/xlsx 等） | `ms_thesis/docs/tasks/` |
| `docs/papers/`（**递归**，参考文献 PDF 等） | `ms_thesis/docs/papers/` |
| `docs/ppt/`（**递归**，pptx / pdf / grass 等） | `ms_thesis/docs/ppt/` |
| **`pictures/*.png`**（仓库根目录，Neo4j 导出等） | **`ms_thesis/pictures/`**（整目录镜像）**与** **`ms_thesis/output/figures/knowledge_graph/`**（与正文 `../output/figures/knowledge_graph/` 对齐；Windows 下由脚本 **robocopy** 复制，减少中文路径失败） |

### 5.2 插图（`output/figures`）

与正文引用一致：多数 `thesis_*.png` 与 `fig2`–`fig5` 等仍在 `output/figures/` **根目录**；**图 4.1、4.2、6.1** 在 **`output/figures/knowledge_graph/`**。主仓 **`pictures/`** 中的 Neo4j 子图原图会**迁移进 `ms_thesis` 两处**：**`ms_thesis/pictures/`**（与主仓布局一致）与 **`ms_thesis/output/figures/knowledge_graph/`**（便于与正文相对路径同包核对）。任务文档另用：`output/figures/maps/`、`output/figures/grid_culture_tourism/`。子目录由脚本从 `output/figures/...` 复制；`pictures` 由 **robocopy（Windows）** 或递归复制（其他系统）写入上述两目标。

### 5.3 表格（`output/tables`）

**整目录复制**（当前仓库内包括但不限于）：  
`poi_cleaned.csv`、`poi_llm_cleaned.csv`、`review_summary_merged.csv`、`reviews_detail.csv`、`review_poi_matched.csv`、`review_poi_link.csv`、`nonheritage_full90.csv`、`nonheritage.csv`、`coupling_analysis.csv`、`coupling_summary.json`、`nh_coupling_summary.csv`、`nh_coupling_detail.json`、`nh_entity_match.csv`、`nh_poi_match.csv`、`culture_entities.csv`、`culture_genealogy_stats.json`、`experience_scores.csv`、`spatial_analysis_results.json`、`spatial_town_stats.csv`、`indices_anchors.csv`、`indices_nonheritage.csv`、`indices_town_summary.csv`、`indices_a_level.csv`、`indices_overview.json`、`potential_correlation_anchor.csv`、`potential_correlation_town.csv`、`a_level_correlation.csv`、`potential_summary.md`、`grid_indices.csv`、`grid_indices_kg.csv`、`grid_town_summary.csv`、`grid_town_summary_kg.csv`、`grid_entity_linkage.csv`、`grid_overview.json`、`grid_overview_kg.json`、`town_entity_linkage.csv`、`town_analysis_input.csv`、`triple_map_data.json`、`place_entity_index.json`、`located_entities.csv`、`poi_entity_linkage.csv`、`poi_entity_linkage_overview.json`、`poi_with_reviews.json` 等。

### 5.4 分析产出 JSON

| 源路径 |
|--------|
| `output/analysis/coupling_results.json` |
| `output/analysis/scenic_genealogy_tree.json` |
| `output/analysis/scenic_town_tree.json` |

### 5.5 核心数据（`data/`）

| 源路径 | 用途 |
|--------|------|
| `data/anchors/cultural_anchors.json` | 载体锚点主表 |
| `data/anchors/culture_taxonomy.json`、`culture_genealogy_tree.json` | 谱系辅助 |
| `data/corpus/` | **`corpus_index.json` + 53 篇 `*.md` 原样复制**（与主仓 `data/corpus` 一致） |
| `data/gis/nanhai_nonheritage.json`、`nanhai_nonheritage_full90.json`、`scenic_a_level.json` | 非遗与 A 级景区样本 |
| `data/gis/*.geojson`（脚本已拷：`nanhai_towns_real`、`nanhai_towns_voronoi_approx`、`nanhai_boundary`、`nanhai_nonheritage`、`nanhai_towns`） | 镇街面、边界与非遗几何；与 **2026-04-21** 网格分析同批空间底座 |
| `data/poi/poi_amap.json`、`poi_shapefile.json` | 高德 / Shapefile 侧原始或中间 POI |
| `data/poi/poi_cleaned.json` | 三源融合主库，与 `poi_cleaned.csv` 同源 |
| `data/reviews/review_summary_merged.json` | 评论汇总 JSON |
| `data/database/coupling_results.json` | 耦合备份 |
| `data/entities_relations/progress.json` | **唯一**抽取进度与原始规模（**非** `output/qwen_extraction/progress.json`） |
| `data/entities_relations/merged_entities.json`、`merged_relations.json` | 合并后图谱总库（**大**） |
| `data/entities_relations/neo4j_frequency_rank_palette.json` | 节点分档配色 |

### 5.6 Neo4j 导出（可选）

| 源路径 |
|--------|
| `output/neo4j/neo4j_nodes.csv`、`neo4j_edges.csv` |
| `output/neo4j/neo4j_llm_nodes.csv`、`neo4j_llm_edges.csv` |
| `output/neo4j/*.cypher`（若存在） |

### 5.7 工具脚本

| 源路径 |
|--------|
| `tools/export_thesis_docx.py` |
| `tools/prepare_thesis_assets.py` |

复制后若在新目录单独跑脚本，需把两脚本内的 **`ROOT = Path(__file__).resolve().parents[1]`** 改为仍指向包根（通常仍为「脚本的上两级」时，应改为 `parents[1]` 若脚本在 `ms_thesis/tools` 则 `parents[1]` 已是 `ms_thesis` — 与现逻辑一致，**一般不必改**）。

### 5.8 论文相关代码节选（`code/`）

由 **`tools/run_ms_thesis_migration.py`** 从主仓 `code/` 复制，子路径与主仓一致，便于 `build_indices.py`、`grid_indices_kg.py` 等通过 **`parents[2]`** 将项目根解析为 **`ms_thesis/`** 根目录（与 `data/`、`output/` 并列）。**清单以 Python 脚本内 `code_relpaths` 为准**（含：`processing/qwen_ner_multithread.py`、`llm_ner.py`、`llm_relation_compliance.py`、`prepare_corpus.py`、`poi_cleaner.py`、`llm_poi_clean.py`、`export_csv.py`；`analysis/` 下 `build_indices`、`potential_correlation`、`spatial_analysis`、`grid_indices`、`grid_indices_kg`、`poi_entity_linkage`、`culture_genealogy`、`coupling_analysis`、`nonheritage_coupling_match`、`build_triple_map`、`analysis_data_sources`；`data_processing/match_review_to_poi.py`；`collection/` 下 OCR 与 POI/评论/非遗采集脚本）。目标路径：`ms_thesis/code/...`。说明全文见复制后的 **`ms_thesis/code/README.md`**。

---

## 6. 明确不复制项

| 路径 | 原因 |
|------|------|
| `config.json` | 含密钥，公开仓勿提交 |
| `data/anchors/cultural_anchors.bak.json` | 旧备份；以 `cultural_anchors.json` 为准，避免双份 |
| `~$*.docx` | Word 临时文件 |
| `.vscode/`、`.cursor/`、`.qoder/` | 编辑器与工具缓存 |
| `output/qwen_extraction/`（若日后重新生成）按篇 `entities/*.json`、`relations/*.json` | 体量极大；总览以 **`data/entities_relations/progress.json`** + `merged_*.json` 或 `output/tables` 为准；默认不拷 |
| `docs/tasks/**/*.html` | 临时页面 / 导出预览；**默认不拷**（脚本已 `/XF *.html`） |

若你**必须**在新仓保留可复现的按篇抽取结果，可另开附录用 `robocopy` 同步 `output\qwen_extraction`（**当前仓库可无此目录**；不在默认脚本内）。

---

## 7. 大体量文件与磁盘说明

复制前可在仓库根执行：

```powershell
Get-Item "data\poi\poi_cleaned.json","data\entities_relations\merged_entities.json","data\entities_relations\merged_relations.json","output\neo4j\*.csv" -ErrorAction SilentlyContinue | Select-Object FullName, @{n="MB";e={[math]::Round($_.Length/1MB,2)}}
```

若合计超过你可接受的上传体积，可按下序删减：**`neo4j/*.csv`** → **`merged_*.json`** → **`docs/tasks/figures` 重复图**（勿删 `output/figures` 正文图）。尽量保留：**`data/corpus` 原样** + **`output/tables/*`** + **`data/entities_relations/progress.json`** + **`cultural_anchors.json`**。

---

## 8. 复制后校验清单

- [ ] `ms_thesis\docs\毕业论文_正文.md` 存在，且其中 `](../output/figures/` 相对路径在磁盘上能解析到 `ms_thesis\output\figures\` 对应文件。
- [ ] 第 4 节脚本所列 **11 张图** 均在 `ms_thesis\output\figures\`（根或 `maps/`、`grid_culture_tourism/`、`knowledge_graph/` 子目录，与正文路径一致）。
- [ ] **`ms_thesis\pictures\`** 与 **`ms_thesis\output\figures\knowledge_graph\`** 均含主仓 **`pictures\*.png`**（Neo4j 子图等；若仅一处有文件，检查迁移日志是否出现 `robocopy` / `OSError` 告警）。
- [ ] `ms_thesis\output\tables` 内文件数量与源目录一致（当前主仓为 **44** 个文件，见第 2.13 节；若删减请记录）。
- [ ] `ms_thesis\docs\ms_thesis_迁移执行说明.md` 已随包复制（便于新仓查阅口径）。
- [ ] `ms_thesis\data\corpus\` 与主仓 **`data\corpus` 原样一致**（**53** 个 `*.md` + `corpus_index.json`）。
- [ ] `ms_thesis\docs\tasks\` 下**无** `*.html`；`4.22`、`papers`、`ppt` 等含预期文件。
- [ ] `data\entities_relations\progress.json` 存在；若需要附录级实体列表再确认 `merged_*.json`。
- [ ] 未误拷 `config.json`、`~$*.docx`。
- [ ] 在新目录执行（可选）`python tools\prepare_thesis_assets.py` 前，确认已安装 `pillow`、`matplotlib`、`pandas` 等依赖。
- [ ] `ms_thesis\code\README.md` 存在，且 `code\processing`、`code\analysis` 等节选脚本齐全（见第 5.8 节）。

---

## 9. 新建 Git 仓库建议命令

```powershell
Set-Location (Join-Path $RepoRoot "ms_thesis")
git init
"# ms_thesis`nconfig.json`n*.tmp`n~$*" | Out-File -Encoding utf8 .gitignore
git add .
git status
git commit -m "Initial import: thesis draft, figures, tables, and core data"
```

`.gitignore` 中请确保忽略任何未来误放的密钥文件。

---

## 10. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-10 | 首版：含全量 `output/tables`、核心 `data`、合并图谱与 Neo4j 可选复制、PowerShell 一键脚本。 |
| 2026-05-10 | 二版：通扫 `output/tables`（44 文件）及核心 JSON/CSV；写入易混淆数据版本对照（第 2 节）；修正 `merged_*.json` 体积描述；脚本增加本说明自拷、GIS GeoJSON、`merged_reviews_supp` 可选块；章节顺延为 1–10。 |
| 2026-05-10 | 三版：`data/corpus` **整包**迁入；`progress` **仅以** `data/entities_relations` 为准；§2.3 POI 分层；§2.4 对齐 `docs/tasks/4.22`；脚本复制 `docs/tasks`、`docs/papers`、`docs/ppt`；`data/poi` 全 JSON；可选 `clean_log`。 |
| 2026-05-10 | 四版：**不复制** `docs/tasks` 下 `*.html`；**去掉**典籍外挂 txt 与 `corpus_txt_original`；**`data/corpus` 仅原样复制**（md + 索引）。 |
| 2026-05-10 | 五版：迁移脚本增加 **`ms_thesis/code/`** 节选（API/本地抽取、指数、网格、POI、评论匹配、采集与 OCR）；附 **`code/README.md`**；执行说明 §3 / §5.8 同步。 |

---

执行或删减脚本某几段前，建议你本地 **先 `git status` 确认 `毕业论文_正文.md` 为待提交的最新稿**，再运行 **第 4 节** 脚本。若你希望把 **`ms_thesis` 放在仓库外路径**，只需将脚本中 `$Dest` 改为目标绝对路径，并自行调整 README 中的说明即可。定稿前请对照 **第 2 节** 核对易混淆数据口径。
