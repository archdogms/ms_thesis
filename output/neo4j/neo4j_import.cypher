// ═══ 南海区文旅知识图谱 — Neo4j 导入脚本 ═══
// 用法: 在 Neo4j Browser 中逐段执行，或用 neo4j-admin import

// ── Step 1: 创建约束 ──
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;

// ── Step 2: 导入节点 ──
// 方式A: LOAD CSV (需把 neo4j_nodes.csv 放到 Neo4j import 目录)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_nodes.csv' AS row
CREATE (n:Entity {
  id: row.id, name: row.name, type: row.type,
  layer: row.layer, intro: row.intro, weight: toFloat(row.weight)
});

// 为每种类型添加标签
MATCH (n:Entity) WHERE n.type = "历史文化名村" SET n:历史文化名村;
MATCH (n:Entity) WHERE n.type = "镇街" SET n:镇街;
MATCH (n:Entity) WHERE n.type = "圩市街区" SET n:圩市街区;
MATCH (n:Entity) WHERE n.type = "人物" SET n:人物;
MATCH (n:Entity) WHERE n.type = "不可移动文物" SET n:不可移动文物;
MATCH (n:Entity) WHERE n.type = "文化要素" SET n:文化要素;
MATCH (n:Entity) WHERE n.type = "文化景观" SET n:文化景观;
MATCH (n:Entity) WHERE n.type = "朝代" SET n:朝代;
MATCH (n:Entity) WHERE n.type = "建筑" SET n:建筑;
MATCH (n:Entity) WHERE n.type = "景点" SET n:景点;
MATCH (n:Entity) WHERE n.type = "非遗项目" SET n:非遗项目;
MATCH (n:Entity) WHERE n.type = "地点" SET n:地点;

// ── Step 3: 导入关系 ──
// 方式A: LOAD CSV
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CALL apoc.create.relationship(a, row.relation, {weight: toFloat(row.weight)}, b) YIELD rel
RETURN count(rel);

// ── Step 3 备选 (无 APOC 插件时): 为每种关系类型单独创建 ──
// 关系类型: 位于 (159 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "位于"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`位于` {weight: toFloat(row.weight)}]->(b);

// 关系类型: 对应景点 (242 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "对应景点"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`对应景点` {weight: toFloat(row.weight)}]->(b);

// 关系类型: 共现关联 (1576 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "共现关联"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`共现关联` {weight: toFloat(row.weight)}]->(b);

// 关系类型: 典籍记载 (8 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "典籍记载"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`典籍记载` {weight: toFloat(row.weight)}]->(b);

// 关系类型: 关联人物 (4 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "关联人物"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`关联人物` {weight: toFloat(row.weight)}]->(b);

// 关系类型: 文化承载 (1 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "文化承载"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`文化承载` {weight: toFloat(row.weight)}]->(b);

// 关系类型: 传承于 (26 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "传承于"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`传承于` {weight: toFloat(row.weight)}]->(b);

// 关系类型: 文化关联 (8 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "文化关联"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`文化关联` {weight: toFloat(row.weight)}]->(b);

// 关系类型: 同时代 (83 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "同时代"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`同时代` {weight: toFloat(row.weight)}]->(b);

// 关系类型: 同门类 (11 条)
LOAD CSV WITH HEADERS FROM 'file:///neo4j_edges.csv' AS row
WITH row WHERE row.relation = "同门类"
MATCH (a:Entity {name: row.source})
MATCH (b:Entity {name: row.target})
CREATE (a)-[:`同门类` {weight: toFloat(row.weight)}]->(b);

// ── Step 4: 查询示例 ──
// 查看所有节点类型统计
MATCH (n:Entity) RETURN n.type, count(*) ORDER BY count(*) DESC;

// 查看某个锚点的所有关系
MATCH (n:Entity {name: "云泉仙馆"})-[r]-(m) RETURN n, r, m;

// 查看两个实体间的所有关系
MATCH (a:Entity {name: "九江双蒸酒酿制技艺"})-[r]-(b:Entity {name: "九江镇"}) RETURN a, r, b;

// 查找文化载体锚点的关联景点
MATCH (a:Entity {layer: 'anchor'})-[r:`对应景点`]->(p:Entity {layer: 'tourism'}) RETURN a.name, p.name LIMIT 20;