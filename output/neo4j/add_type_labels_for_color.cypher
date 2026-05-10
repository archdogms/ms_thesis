// ═══ 为节点按 type 属性添加类型标签，便于在 Neo4j Browser 中按颜色区分 ═══
// 在 Neo4j Browser 中执行下面语句（若节点标签是 LLMEntity 请把 LlmEntity 改成 LLMEntity）。

MATCH (n:LlmEntity) WHERE n.type = "人物" SET n:`人物`;
MATCH (n:LlmEntity) WHERE n.type = "地名" SET n:`地名`;
MATCH (n:LlmEntity) WHERE n.type = "建筑遗迹" SET n:`建筑遗迹`;
MATCH (n:LlmEntity) WHERE n.type = "典籍作品" SET n:`典籍作品`;
MATCH (n:LlmEntity) WHERE n.type = "非遗技艺" SET n:`非遗技艺`;
MATCH (n:LlmEntity) WHERE n.type = "朝代年号" SET n:`朝代年号`;
MATCH (n:LlmEntity) WHERE n.type = "历史事件" SET n:`历史事件`;
MATCH (n:LlmEntity) WHERE n.type = "物产饮食" SET n:`物产饮食`;
MATCH (n:LlmEntity) WHERE n.type = "宗族姓氏" SET n:`宗族姓氏`;

// 执行完后，在 Neo4j Browser 的「样式」里应用 neo4j_browser_style_by_type.txt 中的样式即可按类型显示不同颜色。
