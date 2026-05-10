# ms_thesis

**本科综合论文训练 / 毕业设计资料与复算代码的独立归档仓库**  
论文题目：**基于大数据的佛山市南海区旅游景区文旅融合潜力研究**

远程仓库：<https://github.com/Archdogms/ms_thesis>

---

## 本仓库是干什么的

本仓库**不是**一个从零开始的「空项目骨架」，而是从原 **`knowledge_graph`** 研究仓库中，按 `docs/ms_thesis_迁移执行说明.md` 的约定**迁移、裁剪并固定下来**的一套**论文定稿包**。用途包括：

1. **撰写与排版**：正文以 Markdown 维护（`docs/毕业论文_正文.md`），可用脚本导出 Word；插图、表格路径与正文引用一致，便于终稿核对。  
2. **数据与口径留档**：典籍语料、POI 主库、知识图谱合并结果、GIS、评论匹配表、各类指数与网格统计等，与正文中的数字、图表、附录一一对应，避免「论文写了、数据找不到」。  
3. **方法与结果可复查**：`code/` 中保留与论文相关的采集、清洗、抽取、分析脚本节选；在仓库根目录运行 Python，可按相同路径复算 `output/tables/` 与部分图表（依赖环境见 `code/README.md`）。  
4. **答辩与过程材料**：阶段任务记录（`docs/tasks/`）、参考文献目录（`docs/papers/`）、答辩用 PPT（`docs/ppt/`）、学校模板（`docs/templates/`）与迁移说明一并收录，方便整包备份或交给导师审阅。

若你更熟悉「主研究仓库」：`ms_thesis` 相当于把**写论文、交材料、对数字**所必需的那一部分从 `knowledge_graph` 抽出来，单独 `git` 管理；**不含**日常实验用的全部历史分支与密钥配置。

---

## 研究在做什么（与仓库内容的对应关系）

论文以**「文化—旅游」双谱系对照**为框架，在**佛山市南海区**尺度上识别文旅错位、评估融合潜力，并讨论可干预的规划条件。

| 侧面 | 数据与实现要点 | 在本仓库中的主要落点 |
|------|----------------|----------------------|
| **文化侧** | 53 份地方典籍（约 899 万字，以 `data/corpus/corpus_index.json` 为准）；OCR 与校对后，用大模型抽取实体与关系，合并为约 **8,048** 实体、**19,382** 条关系的图谱 | `data/corpus/`、`data/entities_relations/`、`output/neo4j/`、`output/figures/knowledge_graph/` |
| **旅游侧** | 高德、百度、公开 Shapefile **三源融合**后的 **13,512** 条 POI；携程、高德、去哪儿、马蜂窝等合计 **16,391** 条平台评论及与 POI 的匹配 | `data/poi/`、`data/reviews/`、`output/tables/poi_*.csv`、`review_poi_*.csv` 等 |
| **空间衔接** | 「耦合桥梁」：以官方认定的物质文化载体等为主桥梁（正文口径 **165** 条载体层分析），91 项非遗等为补充层；镇街与 **500 m 网格**（约 4,662 格）下沉分析 | `data/anchors/`、`data/gis/`、`output/tables/grid_*.csv`、`grid_overview*.json`、`output/figures/grid_culture_tourism/`、`maps/` |
| **指数与统计** | 文化记忆指数（CMI）、官方认证指数（OAI）、旅游热度指数（THI）、错位指数（MI）及载体四象限分类；镇街相关矩阵、A 级景区子样本等 | `output/tables/indices_*.csv`、`potential_*.csv`、`a_level_correlation.csv` 等 |

更细的**文件级口径、版本对照、哪些表以谁为准**，必须以 **`docs/ms_thesis_迁移执行说明.md`** 为准（尤其是 POI 条数、非遗 91 项全量、网格 0 跳/1 跳知识图谱口径等）。

---

## 仓库里有什么（路径速查）

| 用途 | 路径 |
|------|------|
| 毕业论文正文（Markdown） | `docs/毕业论文_正文.md` |
| 关键数据源与命令索引 | `docs/毕业论文关键文件与路径索引.md` |
| 迁移说明、体积、版本与校验口径 | `docs/ms_thesis_迁移执行说明.md` |
| 全文文件索引（撰写/检索用） | `FILES_INDEX.md` |
| 论文插图 | `output/figures/`（含 `maps/`、`grid_culture_tourism/`、`knowledge_graph/`） |
| Neo4j 子图等原图（与部分 `output/figures` 互为副本） | `pictures/` |
| 论文用表、分析 JSON | `output/tables/`、`output/analysis/` |
| Neo4j 导出 Cypher/CSV（可选） | `output/neo4j/` |
| 典籍语料 | `data/corpus/*.md`、`data/corpus/corpus_index.json` |
| 实体关系合并结果（体积相对大） | `data/entities_relations/` |
| POI、评论、锚点、GIS | `data/poi/`、`data/reviews/`、`data/anchors/`、`data/gis/` |
| 分析脚本节选 | `code/`（模块说明见 [`code/README.md`](code/README.md)） |
| Word 导出、插图素材脚本 | `tools/` |
| 阶段任务、论文模板、参考文献 | `docs/tasks/`、`docs/templates/`、`docs/papers/`、`docs/ppt/` |

---

## 目录结构（简）

```
ms_thesis/
├── code/           # 采集、OCR、清洗、LLM 抽取、指数与网格分析等（节选）
├── data/           # 语料、POI、GIS、实体关系、评论等
├── docs/           # 正文、大纲、迁移说明、任务记录、模板、答辩材料索引
├── output/         # 图表、表格、Neo4j 导出、部分运行记录
├── pictures/       # 论文用图（部分与 output/figures 对应）
├── tools/          # Markdown → Word、插图预处理等
├── FILES_INDEX.md
└── README.md
```

---

## 工具脚本

在仓库**根目录**下执行（脚本内 `ROOT` 指向 `ms_thesis` 根）：

- **`tools/export_thesis_docx.py`**：将 `docs/毕业论文_正文.md` 等导出为 Word（依赖 `python-docx`）。  
- **`tools/prepare_thesis_assets.py`**：论文插图与表格相关素材处理（依赖 `PIL`、`matplotlib`、`pandas` 等）。

具体用法见各脚本文件内注释或 argparse（若有）。

---

## 复算分析代码

`code/` 下脚本约定以 **`ms_thesis` 根目录** 为项目根（与 `data/`、`output/` 并列）。在根目录执行：

```powershell
cd "c:\Users\ms\Desktop\ms_thesis"   # 按你的实际路径修改
python code/analysis/build_indices.py   # 示例：按 code/README 选择脚本
```

各子目录职责、脚本列表、API 与本地模型依赖见 **[`code/README.md`](code/README.md)**。

---

## 安全与隐私

**请勿将含有 API 密钥、账号密码的 `config.json` 或其他密钥文件提交到公开仓库。**  
采集与抽取类脚本建议使用环境变量（例如 `DASHSCOPE_API_KEY`）替代硬编码密钥。迁移说明中已明确默认**不复制**主仓的 `config.json`。

---

## 建议阅读顺序

1. 本 **`README.md`**（了解仓库定位与目录）。  
2. **`docs/ms_thesis_迁移执行说明.md`**（定稿数字、表文件权威版本、缺件排查）。  
3. **`FILES_INDEX.md`**（按文件名快速定位）。  
4. 撰写正文时打开 **`docs/毕业论文_正文.md`**，需要核对数据命令时查 **`docs/毕业论文关键文件与路径索引.md`**。

---

## 作者与许可说明

正文与数据为学位论文研究工作的一部分；公开仓库内请勿上传未脱敏的密钥与个人隐私信息。若导师或学校对公开范围有要求，请自行调整 `.gitignore` 或仓库可见性。
