#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用大模型对已有关系做「合规判定」：不合规则删除或由模型建议修正。
不重新跑全文抽取，只读 merged_relations.json + merged_entities.json，先按规则筛出可疑关系，
再调用 Ollama 逐批判定，输出修正后的关系文件。

用法:
  python llm_relation_compliance.py              # 默认：仅规则筛 + 大模型判定，输出 corrected
  python llm_relation_compliance.py --dry-run     # 只列出可疑关系，不调模型
  python llm_relation_compliance.py --batch 10   # 每批送 10 条给模型（默认 5）
"""

import os
import re
import json
import argparse
from datetime import datetime

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "..", "output", "llm_extraction")
ENTITY_DIR = os.path.join(OUTPUT_DIR, "entities")
MERGED_ENTITIES = os.path.join(OUTPUT_DIR, "merged_entities.json")
MERGED_RELATIONS = os.path.join(OUTPUT_DIR, "merged_relations.json")
CORRECTED_RELATIONS = os.path.join(OUTPUT_DIR, "merged_relations_corrected.json")
COMPLIANCE_LOG = os.path.join(OUTPUT_DIR, "relation_compliance_log.txt")

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:7b"

# 关系类型 → 终点允许的实体类型（与 llm_ner.py 一致）
# 同时兼容旧版类型名，便于校验历史结果文件。
RELATION_ALLOWED_TARGET_TYPES = {
    "活动于": ["地名空间", "地名", "文物建筑", "文物遗址", "建筑遗迹", "朝代年号", "历史事件"],
    "位于": ["地名空间", "地名"],
    "出生于": ["地名空间", "地名"],
    "发生于": ["地名空间", "地名", "朝代年号", "历史事件"],
    "始建于": ["朝代年号"],
    "记载于": ["典籍文献", "典籍作品"],
    "传承于": ["地名空间", "地名", "宗族姓氏", "人物"],
    "创建修建": ["文物建筑", "文物遗址", "建筑遗迹"],
    "承载文化": ["非遗项目", "非遗技艺", "民俗礼仪", "物产饮食"],
    "盛产": ["物产饮食"],
    "同族": ["人物", "宗族姓氏"],
    "关联人物": ["人物", "文物建筑", "文物遗址", "建筑遗迹", "地名空间", "地名"],
    "著有": ["典籍文献", "典籍作品"],
    "属于时期": ["朝代年号"],
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_name_to_type():
    data = load_json(MERGED_ENTITIES)
    return {e.get("name", "").strip(): e.get("type", "") for e in data.get("entities", [])}


def build_file_entities():
    """从 entities/*.json 按 source_file 汇总该文件内的实体 (name, type)，供修正时提供候选 target。"""
    file_entities = {}
    if not os.path.isdir(ENTITY_DIR):
        return file_entities
    for fn in os.listdir(ENTITY_DIR):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(ENTITY_DIR, fn)
        try:
            data = load_json(path)
        except Exception:
            continue
        chunks = data.get("chunks", {})
        seen = set()
        entities_list = []
        source_file = None
        for ch in chunks.values():
            for e in ch.get("entities", []):
                name = (e.get("name") or "").strip()
                typ = e.get("type", "")
                if not name:
                    continue
                if source_file is None:
                    source_file = e.get("source_file", "")
                if (name, typ) not in seen:
                    seen.add((name, typ))
                    entities_list.append((name, typ))
        if source_file:
            file_entities[source_file] = entities_list
    return file_entities


def find_suspicious(relations, name_to_type):
    """按规则筛出终点类型不合规的关系，返回 (index_in_relations, relation, reason)。"""
    suspicious = []
    for i, r in enumerate(relations):
        rel_type = (r.get("relation") or "").strip()
        target = (r.get("target") or "").strip()
        tgt_type = name_to_type.get(target, "")
        allowed = RELATION_ALLOWED_TARGET_TYPES.get(rel_type)
        if not allowed or not tgt_type:
            continue
        if tgt_type not in allowed:
            suspicious.append((i, r, f"{rel_type} 的 target 应为 {allowed}，当前为 {tgt_type}"))
    return suspicious


def get_candidates_for_relation(r, file_entities):
    """返回该关系所在文件中、可作为「修正后 target」的候选实体（符合该关系类型的终点类型）。"""
    rel_type = (r.get("relation") or "").strip()
    allowed = RELATION_ALLOWED_TARGET_TYPES.get(rel_type, [])
    if not allowed:
        return []
    source_file = r.get("source_file", "")
    entities = file_entities.get(source_file, [])
    return [(name, typ) for name, typ in entities if typ in allowed]


def call_ollama(system_prompt, user_prompt, temperature=0.2, timeout=120):
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": 2048},
    }
    resp = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "")


COMPLIANCE_SYSTEM = """# 角色
你是知识图谱关系合规审核专家。给定一条「不合规」的关系（例如：活动于 的 target 不能是人物），请判断应 删除 还是 修正。

# 任务
对每条关系给出唯一结论：
- **delete**：无法合理修正，应删除此条关系。
- **correct**：可修正。若从依据(evidence)或常识能推断出正确的 target（须从「候选实体」中选），则给出 new_target；否则若应改为其他关系类型则给出 new_relation；否则选 delete。

# 输出格式
严格输出 JSON 数组，每条对应输入中的一条，顺序一致。不要输出任何其他文字。
```json
[
  {"action": "delete"},
  {"action": "correct", "new_target": "西樵山"},
  {"action": "correct", "new_relation": "关联人物"}
]
```
若修正时给出 new_target，则必须来自候选实体列表中的名称。若无法修正则用 delete。"""


def batch_judge(batch_items, file_entities):
    """batch_items: [(idx, relation, reason), ...]。返回 [(idx, action, new_target?, new_relation?)], ..."""
    if not batch_items:
        return []
    lines = []
    for idx, r, reason in batch_items:
        cand = get_candidates_for_relation(r, file_entities)
        cand_str = "、".join(f"{n}（{t}）" for n, t in cand[:15]) if cand else "（无同文件内符合类型的实体）"
        lines.append(
            f"- [{idx}] {r.get('source')} --[{r.get('relation')}]--> {r.get('target')} | 原因: {reason} | 依据: {r.get('evidence', '')[:50]} | 候选target: {cand_str}"
        )
    user = "请对以下不合规关系逐条判定：删除 或 修正（若修正请从候选实体中选 new_target，或给出 new_relation）。\n\n" + "\n".join(lines)
    raw = call_ollama(COMPLIANCE_SYSTEM, user)
    out = []
    # 解析 JSON 数组
    try:
        m = re.search(r"\[[\s\S]*?\]", raw)
        if m:
            arr = json.loads(m.group())
        else:
            arr = []
        for k, (idx, r, _) in enumerate(batch_items):
            action = "delete"
            new_target = None
            new_relation = None
            if k < len(arr):
                item = arr[k] if isinstance(arr[k], dict) else {}
                action = (item.get("action") or "delete").strip().lower()
                if "correct" in action or action == "correct":
                    new_target = (item.get("new_target") or "").strip() or None
                    new_relation = (item.get("new_relation") or "").strip() or None
            out.append((idx, action, new_target, new_relation))
    except (json.JSONDecodeError, KeyError) as e:
        for idx, r, _ in batch_items:
            out.append((idx, "delete", None, None))
    return out


def main():
    parser = argparse.ArgumentParser(description="关系合规判定：规则筛 + 大模型判定/修正")
    parser.add_argument("--dry-run", action="store_true", help="只列出可疑关系，不调模型")
    parser.add_argument("--batch", type=int, default=5, help="每批送几条给模型判定，默认 5")
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 条可疑（0=全部）")
    args = parser.parse_args()

    if not os.path.exists(MERGED_RELATIONS):
        print("未找到 merged_relations.json")
        return
    if not os.path.exists(MERGED_ENTITIES):
        print("未找到 merged_entities.json")
        return

    rel_data = load_json(MERGED_RELATIONS)
    relations = list(rel_data.get("relations", []))
    name_to_type = build_name_to_type()
    file_entities = build_file_entities()

    suspicious = find_suspicious(relations, name_to_type)
    print(f"规则筛出不合规关系: {len(suspicious)} 条")

    if args.limit and args.limit > 0:
        suspicious = suspicious[: args.limit]
        print(f"限制处理前 {args.limit} 条")

    if not suspicious:
        print("无不合规关系，无需处理。")
        return

    if args.dry_run:
        for idx, r, reason in suspicious[:30]:
            print(f"  [{idx}] {r.get('source')} --[{r.get('relation')}]--> {r.get('target')} | {reason}")
        if len(suspicious) > 30:
            print(f"  ... 共 {len(suspicious)} 条")
        return

    # 构建：保留的索引集合；修正后的新关系 (idx -> new_r)
    to_remove = set()
    corrections = {}  # idx -> new_relation_dict (可能改 target 或 relation)
    batch_size = max(1, args.batch)

    for start in range(0, len(suspicious), batch_size):
        batch = suspicious[start : start + batch_size]
        results = batch_judge(batch, file_entities)
        for (idx, r, _), (_, action, new_target, new_relation) in zip(batch, results):
            if action == "delete" or (action != "correct" and not new_target and not new_relation):
                to_remove.add(idx)
                continue
            if action == "correct" or new_target or new_relation:
                new_r = dict(r)
                if new_target:
                    new_r["target"] = new_target
                if new_relation:
                    new_r["relation"] = new_relation
                corrections[idx] = new_r

    # 写出修正后的关系列表
    new_relations = []
    for i, r in enumerate(relations):
        if i in to_remove:
            continue
        if i in corrections:
            new_relations.append(corrections[i])
        else:
            new_relations.append(r)

    out = {
        "total": len(new_relations),
        "relation_stats": rel_data.get("relation_stats"),  # 可后续重算
        "relation_types": rel_data.get("relation_types", []),
        "extracted_by": rel_data.get("extracted_by", ""),
        "corrected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "compliance_note": "经规则筛 + 大模型判定：删除不合规、修正部分关系",
        "relations": new_relations,
    }
    with open(CORRECTED_RELATIONS, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 简单报告
    with open(COMPLIANCE_LOG, "w", encoding="utf-8") as f:
        f.write(f"合规判定时间: {out['corrected_at']}\n")
        f.write(f"原始关系数: {len(relations)}\n")
        f.write(f"可疑(规则): {len(suspicious)}\n")
        f.write(f"删除: {len(to_remove)}\n")
        f.write(f"修正: {len(corrections)}\n")
        f.write(f"输出关系数: {len(new_relations)}\n")

    print(f"已输出: {CORRECTED_RELATIONS}")
    print(f"删除 {len(to_remove)} 条，修正 {len(corrections)} 条，保留 {len(new_relations)} 条。")
    print(f"报告: {COMPLIANCE_LOG}")


if __name__ == "__main__":
    main()
