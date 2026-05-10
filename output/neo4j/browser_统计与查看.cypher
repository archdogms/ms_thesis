// ═══ Neo4j Browser：统计频次 + 查看属性 ═══
// 在 Neo4j Browser 中切换到你的图数据库（如 culturegraph）后，逐条执行下面查询。
// 若节点标签是 LLMEntity 而不是 LlmEntity，把下面 LlmEntity 改成 LLMEntity 即可。

// ── 1. 关系类型频次（REL 边的 rel_type 分布）──
MATCH ()-[r:REL]->()
RETURN r.rel_type AS 关系类型, count(*) AS 数量
ORDER BY 数量 DESC;

// ── 2. 节点类型频次（按节点 type 属性）──
MATCH (n:LlmEntity)
RETURN n.type AS 实体类型, count(*) AS 数量
ORDER BY 数量 DESC;

// ── 3. 节点度分布（每个节点连了多少条边，前 20）──
MATCH (n:LlmEntity)
OPTIONAL MATCH (n)-[r:REL]-()
WITH n, count(r) AS 度
RETURN n.name AS 名称, n.type AS 类型, 度
ORDER BY 度 DESC
LIMIT 20;

// ── 4. 查看一条关系的全部属性（边上的 rel_type、confidence 等）──
MATCH (a:LlmEntity)-[r:REL]->(b:LlmEntity)
RETURN a.name AS 源, type(r) AS 关系类型, properties(r) AS 边属性, b.name AS 目标
LIMIT 5;

// ── 5. 查看一个节点的全部属性（name、type、description、confidence 等）──
// 方式 A：返回成「一个对象」，在 Browser 里可能只显示一部分
MATCH (n:LlmEntity)
RETURN properties(n) AS 节点属性
LIMIT 3;

// ── 5b. 节点属性「分列」显示（推荐：每列一个属性，看得更清楚）──
MATCH (n:LlmEntity)
RETURN n.name AS 名称, n.type AS 类型, n.description AS 描述, n.confidence AS 置信度, n.mentions AS 提及次数, n.is_anchor AS 是否锚点
LIMIT 10;

// ── 6. 图可视化（限制 300 条边，便于渲染）──
MATCH (n:LlmEntity)-[r:REL]-(m:LlmEntity)
RETURN n, r, m
LIMIT 300;

// ── 7. 按关系类型看一条示例（例如「活动于」）──
MATCH (a:LlmEntity)-[r:REL]->(b:LlmEntity)
WHERE r.rel_type = '活动于'
RETURN a.name, r.rel_type, r.confidence, b.name
LIMIT 10;

// ── 8. 关系语义异常：「活动于」的终点应是地点/朝代/建筑，不应是人 ──
// 查出「人物-活动于->人物」等不合理的三元组，便于人工审核或删除
MATCH (a:LlmEntity)-[r:REL]->(b:LlmEntity)
WHERE r.rel_type = '活动于' AND b.type = '人物'
RETURN a.name AS 起点, a.type AS 起点类型, r.rel_type AS 关系, b.name AS 终点, b.type AS 终点类型
ORDER BY a.name
LIMIT 100;
