#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
POI 数据清洗流水线 — 基于 Ollama 本地大模型（多线程并发版）

功能：
  1. 纠正 POI 分类（category）
  2. 打上「文旅相关」标签（is_cultural_tourism）
  3. 断点续跑：每批次处理后实时存盘，中断后恢复自动跳过已完成批次
  4. 多线程并发调用 Ollama，最大化 CPU/GPU 利用率

用法：
  python llm_poi_clean.py                          # 断点续跑（默认 qwen3:8b、每批3条、4线程）
  python llm_poi_clean.py --threads 8            # 8 线程并发（需 Ollama OLLAMA_NUM_PARALLEL 匹配）
  python llm_poi_clean.py --reset                  # 清空旧进度，从头开始（改 batch/model 时务必加）
  python llm_poi_clean.py --merge-only             # 仅合并已有结果，输出最终 CSV
"""

import os
import sys
import re
import json
import time
import argparse
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tqdm import tqdm
except ImportError:
    print("请安装 tqdm: pip install tqdm")
    sys.exit(1)

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ════════════════════ 路径配置 ════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(BASE_DIR, "..", "..")
INPUT_CSV = os.path.join(PROJECT_DIR, "output", "tables", "poi_cleaned.csv")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output", "poi_llm_clean")
PROGRESS_PATH = os.path.join(OUTPUT_DIR, "progress.json")
LOG_PATH = os.path.join(OUTPUT_DIR, "clean_log.log")
OUTPUT_CSV = os.path.join(PROJECT_DIR, "output", "tables", "poi_llm_cleaned.csv")

# ════════════════════ 可变配置（通过命令行参数修改） ════════════════════

CFG = {
    "ollama_url": "http://localhost:11434/api/chat",
    "model": "qwen3:8b",
    "batch_size": 3,
    "num_threads": 4,
}

_progress_lock = threading.Lock()
_log_lock = threading.Lock()

# ════════════════════ 分类体系 ════════════════════

VALID_CATEGORIES = [
    "人文古迹", "宗教场所", "自然景观", "公园绿地",
    "文化场馆", "非遗体验", "教育研学", "休闲娱乐",
    "体育运动", "特色街区", "红色文化", "餐饮住宿",
    "商业服务", "其他",
]
CATEGORY_SET = set(VALID_CATEGORIES)

# ════════════════════ Prompt 模板 ════════════════════

SYSTEM_PROMPT = """\
# 角色
你是佛山市南海区「文旅 POI 数据清洗」首席标注员。数据来自高德等地图 API，存在大量**原始分类（category）错误**；你必须以**名称 name** 与 **original_type（分号分隔的地图类型链）** 为主、地址与镇街为辅，独立判断，**不要盲从原始 category**。

# 任务（每条 POI 必须完成）
1. **corrected_category**：从下方 14 类中**唯一**选一类（字符串必须与列表完全一致，勿自造类别）。
2. **is_cultural_tourism**：是否与南海区**文化旅游场景**相关（bool）。

# 14 类定义（只能从中选，一字不差）

- **人文古迹**：宗族祠堂、宗祠、公祠、大宗祠、家祠、乡约祠；名人故居、纪念馆；古村/历史街区中的文化遗存；牌坊、古塔、古桥、书院、碑刻、考古/历史遗址（非自然地貌）。
- **宗教场所**：佛教/道教寺观、观音寺、教堂、清真寺等**宗教活动**场所。注意：**祠堂≠寺庙**，宗族祭祀建筑归「人文古迹」。
- **自然景观**：山体、湖泊河流、湿地、林地、风景名胜中的**自然地貌/水体**（非人造小公园）。单纯「牌坊」若依附道路且无自然景区语境，优先「人文古迹」而非自然景观。
- **公园绿地**：各类公园、社区公园、湿地公园（城市公园属性）、广场、绿道、城市广场。
- **文化场馆**：博物馆、图书馆、美术馆、文化馆、展览馆、科技馆、档案馆、文化宫等**公共文化设施**。
- **非遗体验**：非遗展示/传习、醒狮武术与非遗主题场馆、传统工艺体验馆（名称或类型明确非遗）。
- **教育研学**：中小学、大学、职业学校、幼儿园、培训机构、科教场所（**普通培训机构**通常 is_cultural_tourism=false）。
- **休闲娱乐**：影院、KTV、酒吧、游乐园、主题乐园、农庄度假区、影剧院、游戏游艺（非体育竞技主场地）。
- **体育运动**：体育馆、体育场、健身中心、拳馆/武术训练（**商业健身房**）、球场、体育中心。
- **特色街区**：文创园、创意产业园、步行街、特色小镇、玉器街等**街区/园区**尺度。
- **红色文化**：革命旧址、红色景区、烈士纪念设施、党史教育基地。
- **餐饮住宿**：酒店、宾馆、民宿、餐厅、酒楼、小吃店等（**连锁快餐/无名小餐馆**一般 is_cultural_tourism=false，除非明显地方文化主题）。
- **商业服务**：充电宝、停车场、写字楼、公司、银行、美容美发、服装零售、门牌号、路口、公交站、共享设备、购物店等**无游览价值的设施**。
- **其他**：村委会、会堂、居民楼、纯地名、无法归入以上任一类。

# 高德 original_type 关键词速查（辅助，仍以名称为准）
- 含「寺庙道观」「教堂」「清真寺」→ 多属 **宗教场所**（但若名称是宗祠/公祠 → **人文古迹**）。
- 含「公园广场」「公园」「城市广场」→ 多属 **公园绿地**。
- 含「博物馆」「图书馆」「美术馆」「科教文化场所」且名称匹配 → **文化场馆**。
- 含「红色景区」→ **红色文化**。
- 含「体育休闲服务」「运动场馆」→ **体育运动**。
- 含「风景名胜」但名称是祠堂/宗祠 → **人文古迹**（常见错误：被标成风景名胜或自然景观）。
- 含「餐饮服务」「购物服务」「生活服务」「交通设施服务」「商务住宅」且名称无文化景点特征 → **商业服务** 或 **餐饮住宿**（看名称是否饭店酒店）。

# 易错纠正（必须遵守）
- 「XX宗祠 / XX公祠 / 陈氏大宗祠」→ **人文古迹**，禁止因 original_type 含寺庙道观就判宗教场所。
- 「XX公园 / XX广场」→ **公园绿地**，禁止判自然景观（除非明确为山/湖景区名如西樵山）。
- 「XX纪念馆 / XX故居」→ **人文古迹**（名人）或 **红色文化**（革命人物/事件）。
- 健身房、搏击俱乐部、服装店、充电宝、停车场 → **商业服务** 或 **体育运动**（拳馆类），**is_cultural_tourism=false**。

# 文旅相关 is_cultural_tourism
- **true**：游客或文化研究者可能专程前往——古迹、宗教景点、博物馆、公园景区、非遗场馆、红色景点、文化街区、有故事的地标建筑等。
- **false**：纯通勤/生活消费、培训、写字楼、停车充电、普通零售餐饮、门牌与无名设施。

# 输出（硬性要求）
- 只输出 **一个 JSON 数组**，不要 Markdown、不要解释、不要代码块围栏。
- 数组长度必须等于本批 POI 条数；**每条对应一个对象**，**idx 从 0 起连续递增**。
- 字段仅三个：`idx`（int）、`corrected_category`（string，14 类之一）、`is_cultural_tourism`（boolean）。

示例（格式示意）：
[{"idx":0,"corrected_category":"人文古迹","is_cultural_tourism":true},{"idx":1,"corrected_category":"商业服务","is_cultural_tourism":false}]
"""


def build_user_prompt(batch_items):
    n = len(batch_items)
    lines = [
        f"本批共 {n} 条 POI，请输出恰好 {n} 个 JSON 对象，idx 必须为 0..{n-1}，与下列顺序一一对应：\n",
    ]
    for i, item in enumerate(batch_items):
        lines.append(
            f"[{i}] 名称: {item['name']} | "
            f"原始分类: {item['category']} | "
            f"原始类型: {item['original_type']} | "
            f"地址: {item.get('address', '')} | "
            f"镇街: {item['town']}"
        )
    return "\n".join(lines)


# ════════════════════ Ollama 调用 ════════════════════

def call_ollama(system_prompt, user_prompt, temperature=0.1, max_retries=3):
    payload = {
        "model": CFG["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.85,
            "repeat_penalty": 1.05,
            "num_predict": 4096,
        },
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(CFG["ollama_url"], json=payload, timeout=300)
            if resp.status_code == 200:
                msg = resp.json().get("message", {})
                return msg.get("content", "")
            else:
                print(f"  [T{threading.current_thread().name}] Ollama HTTP {resp.status_code}, 重试 {attempt+1}/{max_retries}")
                time.sleep(3)
        except requests.exceptions.ConnectionError:
            print(f"  [T{threading.current_thread().name}] Ollama 连接失败, 重试 {attempt+1}/{max_retries}")
            time.sleep(5)
        except requests.exceptions.Timeout:
            print(f"  [T{threading.current_thread().name}] Ollama 超时, 重试 {attempt+1}/{max_retries}")
            time.sleep(5)
    return None


def parse_json_response(text):
    if not text:
        return []
    text = text.strip()

    think_end = text.rfind("</think>")
    if think_end != -1:
        text = text[think_end + len("</think>"):].strip()

    if text.startswith("["):
        try:
            end = text.rfind("]") + 1
            return json.loads(text[:end])
        except json.JSONDecodeError:
            pass

    m = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return []


# ════════════════════ 进度管理（线程安全） ════════════════════

def load_progress():
    if os.path.exists(PROGRESS_PATH):
        try:
            with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "results" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            print("  警告: progress.json 损坏，已重置")
    return {
        "model": CFG["model"],
        "batch_size": CFG["batch_size"],
        "total_rows": 0,
        "completed_batches": [],
        "results": {},
        "stats": {"processed": 0, "cultural_tourism": 0, "category_changes": 0},
        "last_update": "",
        "status": "idle",
    }


def save_progress(progress):
    with _progress_lock:
        progress["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tmp = PROGRESS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        os.replace(tmp, PROGRESS_PATH)


def append_log(batch_id, count, ct_count, cat_changes, elapsed):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tid = threading.current_thread().name
    line = (
        f"{ts} | {tid} | batch={batch_id} | processed={count} | "
        f"cultural_tourism={ct_count} | cat_changes={cat_changes} | "
        f"elapsed={elapsed:.1f}s"
    )
    with _log_lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ════════════════════ 批次处理 ════════════════════

def process_batch(batch_items, batch_id, progress):
    user_prompt = build_user_prompt(batch_items)
    response = call_ollama(SYSTEM_PROMPT, user_prompt)
    parsed = parse_json_response(response)

    batch_results = {}
    ct_count = 0
    cat_changes = 0

    result_map = {}
    for item in parsed:
        if isinstance(item, dict) and "idx" in item:
            result_map[item["idx"]] = item

    for i, poi in enumerate(batch_items):
        row_idx = str(poi["_row_idx"])
        if i in result_map:
            r = result_map[i]
            cat = r.get("corrected_category", poi["category"])
            if cat not in CATEGORY_SET:
                cat = poi["category"]
            is_ct = bool(r.get("is_cultural_tourism", False))
        else:
            cat = poi["category"]
            is_ct = False

        if cat != poi["category"]:
            cat_changes += 1
        if is_ct:
            ct_count += 1

        batch_results[row_idx] = {
            "corrected_category": cat,
            "is_cultural_tourism": is_ct,
        }

    with _progress_lock:
        progress["results"].update(batch_results)
        progress["completed_batches"].append(batch_id)
        progress["stats"]["processed"] += len(batch_items)
        progress["stats"]["cultural_tourism"] += ct_count
        progress["stats"]["category_changes"] += cat_changes

    save_progress(progress)
    return len(batch_items), ct_count, cat_changes


# ════════════════════ 主流程（多线程） ════════════════════

def run_cleaning():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    batch_size = CFG["batch_size"]
    num_threads = CFG["num_threads"]

    print(f"读取数据: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)
    total = len(df)
    print(f"总计 {total} 条 POI\n")

    progress = load_progress()
    progress["total_rows"] = total
    progress["batch_size"] = batch_size
    completed_batches = set(progress.get("completed_batches", []))

    batches = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_id = f"batch_{start:06d}"
        batch_items = []
        for idx in range(start, end):
            row = df.iloc[idx]
            batch_items.append({
                "_row_idx": idx,
                "name": str(row["name"]),
                "category": str(row["category"]),
                "original_type": str(row.get("original_type", "")),
                "address": str(row.get("address", "")),
                "town": str(row.get("town", "")),
            })
        batches.append((batch_id, batch_items))

    pending = [(bid, items) for bid, items in batches if bid not in completed_batches]
    done_count = len(batches) - len(pending)

    print(f"{'='*60}")
    print(f"POI 数据清洗 — LLM 分类纠正 + 文旅打标（多线程）")
    print(f"模型: {CFG['model']} | 批次大小: {batch_size} | 并发线程: {num_threads}")
    print(f"总批次: {len(batches)} | 已完成: {done_count} | 待处理: {len(pending)}")
    print(f"已处理 POI: {progress['stats']['processed']}")
    print(f"{'='*60}\n")

    if not pending:
        print("所有批次已完成，无需继续处理。")
        return

    progress["status"] = "running"
    save_progress(progress)

    bar = tqdm(total=len(pending), desc="清洗进度", ncols=110)

    def _worker(batch_id, batch_items):
        t0 = time.time()
        count, ct_count, cat_changes = process_batch(batch_items, batch_id, progress)
        elapsed = time.time() - t0
        append_log(batch_id, count, ct_count, cat_changes, elapsed)
        return count, ct_count, cat_changes, elapsed

    with ThreadPoolExecutor(max_workers=num_threads, thread_name_prefix="W") as pool:
        futures = {
            pool.submit(_worker, bid, items): bid
            for bid, items in pending
        }
        for fut in as_completed(futures):
            bid = futures[fut]
            try:
                count, ct_count, cat_changes, elapsed = fut.result()
                bar.update(1)
                bar.set_postfix(
                    已处理=progress["stats"]["processed"],
                    文旅=progress["stats"]["cultural_tourism"],
                    改分类=progress["stats"]["category_changes"],
                    耗时=f"{elapsed:.1f}s",
                )
            except Exception as e:
                print(f"\n  批次 {bid} 异常: {e}")
                bar.update(1)

    bar.close()

    progress["status"] = "completed"
    save_progress(progress)

    print(f"\n{'='*60}")
    print(f"清洗完成！")
    print(f"  处理: {progress['stats']['processed']} 条")
    print(f"  文旅相关: {progress['stats']['cultural_tourism']} 条")
    print(f"  分类纠正: {progress['stats']['category_changes']} 条")
    print(f"{'='*60}")


def merge_results():
    print(f"\n合并结果到 {OUTPUT_CSV} ...")

    progress = load_progress()
    results = progress.get("results", {})

    if not results:
        print("错误: 没有找到清洗结果，请先运行清洗。")
        return

    df = pd.read_csv(INPUT_CSV)
    print(f"原始数据: {len(df)} 条")
    print(f"清洗结果: {len(results)} 条")

    corrected_cats = []
    is_ct_flags = []
    original_cats = []

    for idx in range(len(df)):
        key = str(idx)
        if key in results:
            r = results[key]
            corrected_cats.append(r["corrected_category"])
            is_ct_flags.append(r["is_cultural_tourism"])
        else:
            corrected_cats.append(df.iloc[idx]["category"])
            is_ct_flags.append(False)
        original_cats.append(df.iloc[idx]["category"])

    df["original_category"] = original_cats
    df["category"] = corrected_cats
    df["is_cultural_tourism"] = is_ct_flags

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n输出文件: {OUTPUT_CSV}")

    print(f"\n=== 纠正后分类分布 ===")
    print(df["category"].value_counts().to_string())

    changed = sum(1 for a, b in zip(original_cats, corrected_cats) if a != b)
    ct_total = sum(is_ct_flags)
    print(f"\n分类变更: {changed} 条 ({changed/len(df)*100:.1f}%)")
    print(f"文旅相关: {ct_total} 条 ({ct_total/len(df)*100:.1f}%)")

    cat_migration = {}
    for orig, new in zip(original_cats, corrected_cats):
        if orig != new:
            key = f"{orig} → {new}"
            cat_migration[key] = cat_migration.get(key, 0) + 1
    if cat_migration:
        print(f"\n=== 分类迁移 TOP 20 ===")
        for k, v in sorted(cat_migration.items(), key=lambda x: -x[1])[:20]:
            print(f"  {k}: {v} 条")

    return df


def reset_progress():
    if os.path.exists(PROGRESS_PATH):
        os.remove(PROGRESS_PATH)
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
    print("已清空清洗进度。")


# ════════════════════ 入口 ════════════════════

def main():
    parser = argparse.ArgumentParser(description="POI 数据清洗 — LLM 分类纠正 + 文旅打标")
    parser.add_argument("--reset", action="store_true", help="清空进度，从头开始")
    parser.add_argument("--merge-only", action="store_true", help="仅合并已有结果输出CSV")
    parser.add_argument("--batch-size", type=int, default=3, help="每批 POI 数量 (默认: 3)")
    parser.add_argument("--model", default="qwen3:8b", help="Ollama 模型 (默认: qwen3:8b)")
    parser.add_argument("--threads", type=int, default=4, help="并发线程数 (默认: 4)")
    args = parser.parse_args()

    CFG["model"] = args.model
    CFG["batch_size"] = args.batch_size
    CFG["num_threads"] = args.threads

    if args.reset:
        reset_progress()

    if args.merge_only:
        merge_results()
        return

    run_cleaning()
    merge_results()


if __name__ == "__main__":
    main()
