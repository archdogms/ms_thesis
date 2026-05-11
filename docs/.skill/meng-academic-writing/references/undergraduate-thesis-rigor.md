# Undergraduate Thesis Rigor Guide

Use this guide when drafting or revising Meng Shuai's undergraduate graduation thesis / comprehensive paper training materials. The goal is to combine the user's natural writing style with reference-backed, data-checkable, thesis-level rigor.

## Local Source Hierarchy

When working in `C:\Users\ms\Desktop\ms_thesis`, check evidence in this order:

1. Current user request and selected text.
2. Current thesis draft: prefer `docs/thesis_01/毕业论文_正文.md`; if `docs/毕业论文_正文.md` exists, compare and use the newest/current one.
3. School and format requirements: `docs/templates/01 综合论文训练论文模板.docx` or `.pdf`; reference rules in `docs/templates/06 参考文献著录规则及注意事项.pdf`.
4. Thesis structure and tutor comments: `docs/thesis_01/毕业论文大纲.md`, `docs/thesis_01/毕业论文大纲_for_word.md`, `docs/tasks/毕业论文大纲修改建议.md`, and relevant `docs/tasks/*.md`.
5. Data and number authority: `docs/毕业论文关键文件与路径索引.md`, `docs/ms_thesis_迁移执行说明.md`, `FILES_INDEX.md`, then the actual tables in `output/tables/`.
6. Literature basis: `docs/papers/000_论文列表_文旅融合与方法参考.md` and the corresponding PDFs in `docs/papers/`.
7. Prior papers in `docs/my_previous_papers/` only for style, never for evidence in the thesis.

If sources conflict, state the conflict and prefer the most recent generated table or explicit thesis-index document. Do not silently mix old and new numbers.

## Current Thesis Frame

The current thesis is an undergraduate graduation thesis / comprehensive paper training project titled roughly `基于大数据的佛山市南海区旅游景区文旅融合潜力研究`.

Core frame:

- Research object: Foshan Nanhai District tourism attractions / cultural-tourism integration potential.
- Analytical logic: culture-tourism dual genealogy; cultural side from local texts and knowledge graph; tourism side from POI and reviews; bridge through officially recognized material cultural carriers, with intangible heritage as dynamic supplement.
- Main chapters: introduction; literature review; study area and data; knowledge graph construction; tourism product system and coupling analysis; spatial pattern and potential-release conditions; conclusions and recommendations.
- Core terms to keep consistent: `文化—旅游耦合桥梁`, `物质遗产为主、非遗为动态补充`, `文化记忆指数（CMI）`, `官方认证指数（OAI）`, `旅游热度指数（THI）`, `文化—旅游错位指数（MI）`, `沉睡潜力区`, `空心景点区`, `核心耦合区`, `一般耦合区`.

## Reference Integration Rules

- Build each literature-review paragraph around references, not around generic background.
- Use a three-step paragraph shape:
  1. `已有研究如何做`: identify object, method, and conclusion.
  2. `对本文有什么帮助`: explain which part supports the current thesis.
  3. `仍有什么不足`: connect the gap to Nanhai District, district/town scale, dual genealogy, POI, knowledge graph, mismatch index, or potential release.
- Do not cite a paper only because the topic sounds similar. Make the connection explicit: scale, method, data type, or conceptual frame.
- Use placeholders such as `[待核对页码]`, `[待补充DOI]`, or `[待确认引用格式]` when the bibliographic detail is not verified.
- Follow GB/T 7714-2015 style for final references. Keep in-text citation numbering consistent with the thesis reference list and do not invent reference numbers.

## Data and Claim Discipline

Before writing any number, verify it against the relevant table or index file. Common authoritative sources:

- Corpus size and source count: `data/corpus/corpus_index.json`, `docs/ms_thesis_迁移执行说明.md`.
- POI count and categories: `output/tables/poi_cleaned.csv`, `output/tables/poi_llm_cleaned.csv`.
- Reviews: `output/tables/review_summary_merged.csv`, `output/tables/reviews_detail.csv`, `output/tables/review_poi_matched.csv`.
- Cultural carriers and anchors: `data/anchors/cultural_anchors.json`, `output/tables/indices_anchors.csv`.
- Indices and mismatch categories: `output/tables/indices_*.csv`, `output/tables/indices_overview.json`.
- Correlation and potential analysis: `output/tables/potential_correlation_anchor.csv`, `output/tables/potential_correlation_town.csv`, `output/tables/a_level_correlation.csv`, `output/tables/potential_summary.md`.
- Grid analysis: `output/tables/grid_*.csv`, `output/tables/grid_overview*.json`, and related figures in `output/figures/grid_culture_tourism/`.

Use cautious language:

- Say `相关` rather than `影响` unless the method supports causality.
- Say `呈现出`, `可以说明`, `在本研究数据口径下` rather than absolute claims.
- Use `显著` only when a significance test or explicit significance marker is available.
- Include sample size when discussing correlations, e.g. `载体级 n = 165`, `镇街级 n = 7`, `A 级景区样本 n = 16`.
- Mention known limitations when relevant: review data does not include major dining platforms such as Dianping/Meituan; some food-led or daily-life cultural tourism may be underestimated; OCR and LLM extraction require evidence retention and manual checking.

## Undergraduate Thesis Level

Keep the ambition appropriate for an undergraduate thesis:

- Emphasize clear problem definition, reproducible data path, transparent method, and honest limitations.
- Do not overbuild high theory if the analysis does not require it. The thesis can mention policy and planning context without forcing a grand theoretical frame.
- Let method chapters explain enough for a teacher to understand and check: data source, processing steps, matching rule, index formula, and output table.
- Let result chapters answer "what was found" before "what should be done".
- Let recommendations follow directly from potential categories, spatial clusters, levels, or policy-intervenable variables.

## Chapter-Level Rigor Checks

- Abstract: four functions should appear clearly: background/problem, method/data, core results, contribution/recommendation. Numbers must match the latest source.
- Introduction: topic, object, problem, research goals, content, technical route, and chapter structure should align with the title.
- Literature review: every subsection should contain real references and end with the thesis position. Avoid empty statements like `相关研究较为丰富` unless immediately supported.
- Data chapter: describe source, collection method, cleaning, sample size, and limitation. Do not hide missing platforms or uncertain geocoding.
- Method chapter: define entity types, relation types, matching rules, formulas, weights, and evidence-retention fields.
- Results chapter: separate descriptive statistics, index results, spatial pattern, and correlation interpretation.
- Recommendations: align each proposal with evidence. For example, `沉睡潜力区` supports activation/display suggestions; `空心景点区` supports cultural narrative supplementation.
- Conclusion: no new data or references; summarize findings in the same order as research questions.

## Style With Rigor

Preserve the user's direct rhythm, but tighten thesis language:

- Prefer `本文以...为研究对象`, `本研究通过...`, `从结果来看...`, `这一结果说明...`.
- Keep `我们可以看到` sparingly in formal chapters; use `可以看到` or `本文认为` when the tone should be more thesis-like.
- Replace oral emphasis with precise qualifiers: `很大` -> `较大`, `特别明显` -> `较为明显`, `完全说明` -> `在一定程度上说明`.
- Avoid over-smooth AI prose. A slightly plain but accurate sentence is better than a polished sentence without evidence.
