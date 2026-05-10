// 在 Neo4j 里给节点按 type 设置 color 属性（不依赖 Neo4j Browser，用 Cypher 执行即可）
// 执行方式：用 Neo4j Desktop 的「Open with」选 Cypher Shell，或任意能执行 Cypher 的客户端，逐条或整段执行。
// 若节点标签是 LLMEntity，把下面 LlmEntity 改成 LLMEntity。

MATCH (n:LlmEntity) WHERE n.type = "人物" SET n.color = "#4A90D9";
MATCH (n:LlmEntity) WHERE n.type = "地名" SET n.color = "#7ED787";
MATCH (n:LlmEntity) WHERE n.type = "建筑遗迹" SET n.color = "#F5A623";
MATCH (n:LlmEntity) WHERE n.type = "典籍作品" SET n.color = "#BD10E0";
MATCH (n:LlmEntity) WHERE n.type = "非遗技艺" SET n.color = "#D0021B";
MATCH (n:LlmEntity) WHERE n.type = "朝代年号" SET n.color = "#50E3C2";
MATCH (n:LlmEntity) WHERE n.type = "历史事件" SET n.color = "#B8E986";
MATCH (n:LlmEntity) WHERE n.type = "物产饮食" SET n.color = "#F8E71C";
MATCH (n:LlmEntity) WHERE n.type = "宗族姓氏" SET n.color = "#9013FE";
