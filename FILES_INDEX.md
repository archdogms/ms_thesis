# ms_thesis 资料包文件索引

供大模型与人工撰写时**快速定位**；下列统计为生成该文件时的快照。完整口径、可删减项与校验清单见 **`docs/ms_thesis_迁移执行说明.md`**。

**生成时间**：`2026-05-10T19:42:09`（本机本地时间）

## 1. 论文撰写优先路径

| 用途 | 路径（相对 `ms_thesis/` 根） |
|------|------------------------------|
| 毕业论文正文 | `docs/毕业论文_正文.md` |
| 关键数据源与命令索引 | `docs/毕业论文关键文件与路径索引.md` |
| 迁移与体积说明 | `docs/ms_thesis_迁移执行说明.md` |
| 包总览 | `README.md` |
| **本索引** | `FILES_INDEX.md` |
| 插图根目录 | `output/figures/` |
| 地图预览 | `output/figures/maps/` |
| 500 m 网格错位系列 | `output/figures/grid_culture_tourism/` |
| 知识图谱正文图与子图 | `output/figures/knowledge_graph/` |
| Neo4j 导出原图（与上互为副本） | `pictures/` |
| 论文用表 | `output/tables/` |
| 分析 JSON | `output/analysis/` |
| Neo4j 表（可选） | `output/neo4j/` |
| 典籍全文 | `data/corpus/*.md` + `corpus_index.json` |
| 合并实体/关系（大文件） | `data/entities_relations/merged_entities.json`、`merged_relations.json` |
| 图谱进度与配色 | `data/entities_relations/progress.json`、`neo4j_frequency_rank_palette.json` |
| POI / 评论 / 锚点 | `data/poi/`、`data/reviews/`、`data/anchors/` |
| 节选代码 | `code/`（说明见 `code/README.md`） |
| 导出脚本 | `tools/export_thesis_docx.py`、`tools/prepare_thesis_assets.py` |
| 阶段任务与附件 | `docs/tasks/`（无 html）、`docs/papers/`、`docs/ppt/` |

## 2. 根目录一览

- **`code`** — 目录
- **`data`** — 目录
- **`docs`** — 目录
- **`output`** — 目录
- **`pictures`** — 目录
- **`tools`** — 目录
- **`README.md`** — 文件

## 3. 数量快照

- `data/corpus/`：`**53**` 个 `.md` 典籍文件（另含 `corpus_index.json` 等）
- `output/tables/`：`**48**` 个文件
- `output/figures/` 根下 PNG：**`8`**；`maps/`：**`4`**；`grid_culture_tourism/`：**`6`**；`knowledge_graph/`：**`10`**
- `pictures/`：`**7`** 个 PNG
- `code/`：`**25`** 个 `.py`（节选）

## 4. `output/tables` 文件名摘录（前 24 个，按名字排序）

需要具体指标或表名时，优先在此目录 `grep` / 打开对应 CSV；大 JSON 用脚本或 IDE 分页读。

- `a_level_correlation.csv`
- `coupling_analysis.csv`
- `coupling_summary.json`
- `culture_entities.csv`
- `culture_genealogy_stats.json`
- `experience_scores.csv`
- `experience_scores.json`
- `grid_entity_linkage.csv`
- `grid_indices.csv`
- `grid_indices_kg.csv`
- `grid_overview.json`
- `grid_overview_kg.json`
- `grid_town_summary.csv`
- `grid_town_summary_kg.csv`
- `indices_a_level.csv`
- `indices_anchors.csv`
- `indices_nonheritage.csv`
- `indices_overview.json`
- `indices_town_summary.csv`
- `located_entities.csv`
- `nh_coupling_detail.json`
- `nh_coupling_summary.csv`
- `nh_entity_match.csv`
- `nh_poi_match.csv`
- … 共 **48** 个文件，此处仅列前 **24** 个。

## 5. 大模型阅读建议（撰写向）

1. **先读** `docs/毕业论文_正文.md` 与 `docs/毕业论文关键文件与路径索引.md`，建立章节与数据对应关系。
2. **核对数字**：以 `output/tables/` 中 `indices_*`、`grid_*`、`potential_*` 等与正文图表标题对齐；勿凭记忆改表内统计值。
3. **知识图谱体量**：`merged_entities.json` / `merged_relations.json` 极大，仅必要时按 `progress.json` 或正文口径抽样打开。
4. **插图路径**：正文引用 `../output/figures/…`；图 4.1、4.2、6.1 在 `knowledge_graph/` 子目录。
5. **复算与复现**：以 `code/README.md` 所列脚本为准，在 **`ms_thesis` 根目录** 下解释运行（脚本内 `parents[2]` 指向包根）。
