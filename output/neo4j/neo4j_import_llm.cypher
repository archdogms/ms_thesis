// ═══ LLM 抽取知识图谱 — Neo4j 导入脚本 ═══
//
// 【重要】file:/// 只能读「当前连接数据库」的 import 目录，不能读项目路径！
//
// 做法一（推荐）：用 Python 直接导入，不依赖 import 目录
//   pip install neo4j
//   cd 中期阶段/code/visualization
//   python llm_kg_neo4j_direct.py
//   按提示输入 Neo4j 密码即可。
//
// 做法二：用 CSV 时，必须先把文件放进「该数据库的」import 目录：
//   1. 在 Neo4j Desktop 里先点 Connect 连上要用的库（如 culturegraph）
//   2. 点左上角三条线菜单 → Open Folder → Import，会打开一个文件夹
//   3. 把 neo4j_llm_nodes.csv、neo4j_llm_edges.csv 复制到该文件夹（不要放子目录）
//   4. 在 Query 里逐段执行下面语句

// ── Step 1: 约束 ──
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:LLMEntity) REQUIRE n.id IS UNIQUE;

// ── Step 2: 导入节点 ──
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_nodes.csv' AS row
CREATE (n:LLMEntity {
  id: toInteger(row.id),
  name: row.name,
  type: row.type,
  description: row.description,
  confidence: toFloat(row.confidence),
  mentions: toInteger(row.mentions),
  is_anchor: toInteger(row.is_anchor) = 1
});

// 为每种实体类型添加标签（便于按类型查询）
MATCH (n:LLMEntity) WHERE n.type = "人物" SET n:`人物`;
MATCH (n:LLMEntity) WHERE n.type = "典籍作品" SET n:`典籍作品`;
MATCH (n:LLMEntity) WHERE n.type = "历史事件" SET n:`历史事件`;
MATCH (n:LLMEntity) WHERE n.type = "地名" SET n:`地名`;
MATCH (n:LLMEntity) WHERE n.type = "宗族姓氏" SET n:`宗族姓氏`;
MATCH (n:LLMEntity) WHERE n.type = "建筑遗迹" SET n:`建筑遗迹`;
MATCH (n:LLMEntity) WHERE n.type = "朝代年号" SET n:`朝代年号`;
MATCH (n:LLMEntity) WHERE n.type = "物产饮食" SET n:`物产饮食`;
MATCH (n:LLMEntity) WHERE n.type = "非遗技艺" SET n:`非遗技艺`;

// ── Step 3: 导入关系（无 APOC 时按类型分批）──
// 关系: 属于时期 (820 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "属于时期"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`属于时期` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 记载于 (472 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "记载于"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`记载于` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 出生于 (180 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "出生于"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`出生于` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 活动于 (2098 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "活动于"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`活动于` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 位于 (950 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "位于"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`位于` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 著有 (607 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "著有"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`著有` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 关联人物 (1231 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "关联人物"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`关联人物` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 发生于 (185 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "发生于"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`发生于` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 同类 (371 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "同类"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`同类` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 创建修建 (385 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "创建修建"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`创建修建` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 同族 (616 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "同族"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`同族` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 承载文化 (1427 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "承载文化"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`承载文化` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 始建于 (95 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "始建于"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`始建于` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 盛产 (274 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "盛产"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`盛产` {confidence: toFloat(row.confidence)}]->(b);

// 关系: 传承于 (174 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_llm_edges.csv' AS row
WITH row WHERE row.relation = "传承于"
MATCH (a:LLMEntity {name: row.source})
MATCH (b:LLMEntity {name: row.target})
CREATE (a)-[:`传承于` {confidence: toFloat(row.confidence)}]->(b);

// ── 查询示例 ──
// 按类型统计节点
MATCH (n:LLMEntity) RETURN n.type AS type, count(*) AS cnt ORDER BY cnt DESC;

// 查看「康有为」相关关系
MATCH (n:LLMEntity {name: "康有为"})-[r]-(m) RETURN n, r, m LIMIT 50;

// 查看「西樵山」一度邻居
MATCH (n:LLMEntity {name: "西樵山"})-[r]-(m) RETURN n, r, m;