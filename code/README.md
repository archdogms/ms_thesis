# 论文相关代码（节选）

目录结构与主仓库 `knowledge_graph/code/` **一致**：`processing/`、`analysis/`、`data_processing/`、`collection/`。
多数分析脚本使用 `Path(__file__).resolve().parents[2]` 或等价 `.. / ..` 将 **项目根** 定为 **`ms_thesis` 根目录**（与 `data/`、`output/` 并列），在 `ms_thesis` 根下运行 Python 命令即可复算表。

## processing
- **qwen_ner_multithread.py** — 通义千问 **DashScope API** 实体/关系抽取（OpenAI 兼容接口）。
- **llm_ner.py** — 本地 **Ollama** 抽取流水线。
- **llm_relation_compliance.py** — 关系合规、筛选与合并相关逻辑。
- **prepare_corpus.py** — 典籍标准化与篇目索引。
- **poi_cleaner.py** / **llm_poi_clean.py** — 三源 POI 融合与 LLM 类目清洗。
- **export_csv.py** — 将 JSON 等导出为 `output/tables/`。

## analysis
- **build_indices.py** — CMI / OAI / THI / MI 与 `indices_*.csv`。
- **potential_correlation.py** — 载体级、镇街级相关矩阵与 `potential_*.csv`。
- **spatial_analysis.py** — 空间分析（KDE、镇街统计等）。
- **grid_indices.py** / **grid_indices_kg.py** — 500 m 网格基础口径与知识图谱 0/1 跳口径。
- **poi_entity_linkage.py** — POI—实体链路与网格输入。
- **culture_genealogy.py** — 文化谱系统计。
- **coupling_analysis.py** / **nonheritage_coupling_match.py** — 文旅耦合与非遗匹配。
- **build_triple_map.py** — 典籍—官方—旅游三联映射（若仍保留对应表）。
- **analysis_data_sources.py** — 分析侧数据源汇总。

## data_processing
- **match_review_to_poi.py** — 评论景点名与 POI 五段式匹配。

## collection
- **ocr_books_pdf.py** / **ocr_books_parallel.py** — 典籍 OCR。
- **amap_poi_crawler.py** / **baidu_poi_crawler.py** — POI 采集。
- **review_crawler_real.py** — 多平台评论采集。
- **crawl_nonheritage_full.py** — 非遗名录扩展采集。

## 依赖与密钥
各脚本依赖见文件头与 import；常见包：`numpy`、`pandas`、`requests`、`openai`、`tqdm` 等。
**勿将 `config.json` 含 API Key 的版本提交公开仓库**；可用环境变量 `DASHSCOPE_API_KEY` 等替代。
