#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
阿里千问智能实体/关系抽取流水线 v3

使用阿里千问 API (DashScope) + OpenAI 兼容接口，从典籍文本中抽取文化实体和语义关系。
支持 AI 分级标签和官方分类标签双重标注体系。

特性：
  - 支持阿里千问 API (qwen-max, qwen-plus, qwen-turbo 等)
  - 双重标签体系：AI 分级标签 + 官方分类标签
  - 多线程并发；每线程独立片段进度条，描述中显示线程与书名
  - 智能重试：限流指数退避、其它错误可重试
  - 断点续跑：按 chunk 落盘，重启跳过已完成
  - 配置：环境变量 DASHSCOPE_API_KEY 优先，其次项目根目录 config.json

用法：
  python code\processing\qwen_ner_multithread.py --threads 8                          # 全量抽取
  python code\processing\qwen_ner_multithread.py --demo --threads 2                   # demo 模式（取前3篇各2000字）
  python code\processing\qwen_ner_multithread.py --demo --config path/to/config.json  # demo + 自定义配置
  python code\processing\qwen_ner_multithread.py --merge-only                         # 仅合并已有结果
  python code\processing\qwen_ner_multithread.py --reset                              # 清空输出重跑
  python code\processing\qwen_ner_multithread.py --model qwen-3.5-plus --chunk-size 1200   # 覆盖模型和chunk


全量跑 53 篇文件，两步指令：

第1步：清空旧输出 + 全量抽取

python code\processing\qwen_ner_multithread.py --config config.json --threads 20
第2步（抽取完成后）：合并结果

python code\processing\qwen_ner_multithread.py --merge-only --config config.json
"""

import os
import re
import json
import time
import shutil
import argparse
import hashlib
import threading
from datetime import datetime
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

try:
    from tqdm import tqdm
except ImportError:
    print("请安装 tqdm: pip install tqdm")
    raise SystemExit(1)

from openai import OpenAI, APIError, RateLimitError

try:
    from opencc import OpenCC
    _t2s_converter = OpenCC("t2s")
    def to_simplified(text: str) -> str:
        """繁体→简体转换"""
        return _t2s_converter.convert(text) if text else text
except ImportError:
    print("提示: 未安装 opencc-python-reimplemented，繁简转换不可用 (pip install opencc-python-reimplemented)")
    def to_simplified(text: str) -> str:
        return text

# ════════════════════ 路径（与 llm_ner.py 一致：processing -> code -> 项目根）════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", ".."))
DATA_DIR = os.path.join(ROOT_DIR, "data")
CORPUS_DIR = os.path.join(DATA_DIR, "corpus")
DB_DIR = os.path.join(DATA_DIR, "database")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output", "qwen_extraction")
ENTITY_DIR = os.path.join(OUTPUT_DIR, "entities")
RELATION_DIR = os.path.join(OUTPUT_DIR, "relations")
PROGRESS_PATH = os.path.join(OUTPUT_DIR, "progress.json")
LOG_PATH = os.path.join(OUTPUT_DIR, "extraction_log.log")
DEFAULT_CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

DEFAULT_MODEL = "qwen-3.5-plus"
DEFAULT_CHUNK_SIZE = 800
CHUNK_OVERLAP = 50
DEFAULT_THREADS = 4
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_DELAY = 2.0

_progress_lock = threading.Lock()
_log_lock = threading.Lock()
_wid_lock = threading.Lock()
_worker_seq = [0]

client: Optional[OpenAI] = None
RUNTIME_MODEL = DEFAULT_MODEL


def _pool_init_worker():
    with _wid_lock:
        i = _worker_seq[0]
        _worker_seq[0] += 1
    threading.current_thread()._qwen_wid = i


def _worker_slot() -> int:
    return int(getattr(threading.current_thread(), "_qwen_wid", 0))


def load_config_file(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_api_key(cfg: Dict[str, Any]) -> str:
    k = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if k:
        return k
    k = (cfg.get("api_key") or cfg.get("dashscope_api_key") or "").strip()
    return k


def build_runtime_settings(
    cfg: Dict[str, Any],
    args: Optional[argparse.Namespace] = None,
) -> Dict[str, Any]:
    out = {
        "api_key": resolve_api_key(cfg),
        "base_url": (cfg.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1").strip(),
        "model": (cfg.get("model") or cfg.get("qwen_model") or DEFAULT_MODEL).strip(),
        "chunk_size": int(cfg.get("chunk_size", DEFAULT_CHUNK_SIZE)),
        "threads": int(cfg.get("max_threads", DEFAULT_THREADS)),
        "max_retries": int(cfg.get("max_retries", DEFAULT_MAX_RETRIES)),
        "retry_delay": float(cfg.get("retry_delay", DEFAULT_RETRY_DELAY)),
    }
    if args:
        if getattr(args, "model", None):
            out["model"] = args.model.strip()
        if getattr(args, "chunk_size", None):
            out["chunk_size"] = int(args.chunk_size)
        if getattr(args, "threads", None) is not None:
            out["threads"] = int(args.threads)
        if getattr(args, "max_retries", None):
            out["max_retries"] = int(args.max_retries)
    return out


def init_openai_client(api_key: str, base_url: str) -> OpenAI:
    global client
    client = OpenAI(api_key=api_key, base_url=base_url)
    return client


# ════════════════════ 文化锚点 ════════════════════

ANCHOR_NAMES = set()


def load_anchors():
    global ANCHOR_NAMES
    anchor_path = os.path.join(DB_DIR, "cultural_anchors.json")
    if os.path.exists(anchor_path):
        with open(anchor_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ANCHOR_NAMES = {a["name"] for a in data.get("anchors", [])}
    print(f"文化锚点: {len(ANCHOR_NAMES)} 条")


# ════════════════════ AI 分类体系（docs/分类体系.md "AI分类总表"）════════════════════

AI_CLASSIFICATION_HIERARCHY = {
    "A 非遗文化体系": [
        "A1 表演艺术类非遗", "A2 传统技艺类非遗", "A3 民俗节庆类非遗",
        "A4 信俗礼仪类非遗", "A5 传统体育游艺类非遗", "A6 饮食酿造类非遗及文化物产",
    ],
    "B 物质文化遗产体系": [
        "B1 古建筑类", "B2 宗教建筑类", "B3 纪念性建筑与名人故居类",
        "B4 古遗址与生产遗存类", "B5 石刻碑记类", "B6 古村落与聚落遗产类",
    ],
    "C 传承主体体系": [
        "C1 历史文化人物", "C2 非遗传承人及技艺人物",
        "C3 文物营建与守护人物", "C4 宗族姓氏与地方社群",
    ],
    "D 文化空间体系": [
        "D1 山川水系空间", "D2 镇街圩市空间",
        "D3 历史街区与传统片区", "D4 传承场所与活动场地",
    ],
    "E 文献记忆体系": [
        "E1 地方志类", "E2 族谱家乘类", "E3 碑记题咏类",
        "E4 文集著述类", "E5 口述史与地方记忆材料",
    ],
    "F 历史时序体系": ["F1 朝代年号类", "F2 历史事件类", "F3 发展阶段类"],
}

AI_ENTITY_TYPES: List[str] = []
AI_LABEL_BY_TYPE: Dict[str, str] = {}
for _main, _subs in AI_CLASSIFICATION_HIERARCHY.items():
    for _t in _subs:
        AI_ENTITY_TYPES.append(_t)
        AI_LABEL_BY_TYPE[_t] = _main

AI_LAYER_BY_LABEL = {
    "A 非遗文化体系": "文化本体层",
    "B 物质文化遗产体系": "文化本体层",
    "C 传承主体体系": "传承承载层",
    "D 文化空间体系": "传承承载层",
    "E 文献记忆体系": "认知支撑层",
    "F 历史时序体系": "认知支撑层",
}

# ════════════════════ 官方分类体系（docs/官方分类表.csv，基于国家标准）════════════════════

OFFICIAL_CLASSIFICATION_HIERARCHY = {
    "非物质文化遗产": [
        "民间文学", "传统音乐", "传统舞蹈", "传统戏剧", "曲艺",
        "传统体育、游艺与杂技", "传统美术", "传统技艺", "传统医药", "民俗",
    ],
    "非遗传承主体": ["传承人", "传承群体"],
    "不可移动文物": [
        "古文化遗址", "古墓葬", "古建筑", "石窟寺及石刻",
        "近现代重要史迹及代表性建筑", "其他不可移动文物",
    ],
    "可移动文物": ["珍贵文物", "一般文物", "古代文物", "近代现代文物"],
    "历史文化名城名镇名村": [
        "历史文化名城", "历史文化名镇", "历史文化名村",
        "历史文化街区", "历史建筑",
    ],
    "自然保护地": ["国家公园", "自然保护区", "自然公园"],
    "公共文化资源": [
        "公共文化设施", "公共文化产品", "公共文化活动",
        "公共文化服务", "公共文化主体",
    ],
    "旅游资源": ["旅游景区", "旅游度假区", "旅游休闲街区", "夜间文化和旅游消费集聚区"],
}

OFFICIAL_ENTITY_TYPES: List[str] = []
OFFICIAL_LABEL_BY_TYPE: Dict[str, str] = {}
for _main, _subs in OFFICIAL_CLASSIFICATION_HIERARCHY.items():
    for _t in _subs:
        OFFICIAL_ENTITY_TYPES.append(_t)
        OFFICIAL_LABEL_BY_TYPE[_t] = _main

# ════════════════════ AI↔官方 交叉映射（空列表=该AI类型无对应官方分类）════════════════════

AI_TO_OFFICIAL_MAPPING: Dict[str, List[str]] = {
    "A1 表演艺术类非遗": ["非物质文化遗产"],
    "A2 传统技艺类非遗": ["非物质文化遗产"],
    "A3 民俗节庆类非遗": ["非物质文化遗产"],
    "A4 信俗礼仪类非遗": ["非物质文化遗产"],
    "A5 传统体育游艺类非遗": ["非物质文化遗产"],
    "A6 饮食酿造类非遗及文化物产": ["非物质文化遗产"],
    "B1 古建筑类": ["不可移动文物"],
    "B2 宗教建筑类": ["不可移动文物"],
    "B3 纪念性建筑与名人故居类": ["不可移动文物"],
    "B4 古遗址与生产遗存类": ["不可移动文物"],
    "B5 石刻碑记类": ["不可移动文物"],
    "B6 古村落与聚落遗产类": ["历史文化名城名镇名村"],
    "C1 历史文化人物": [],
    "C2 非遗传承人及技艺人物": ["非遗传承主体"],
    "C3 文物营建与守护人物": [],
    "C4 宗族姓氏与地方社群": ["非遗传承主体"],
    "D1 山川水系空间": ["自然保护地"],
    "D2 镇街圩市空间": ["历史文化名城名镇名村"],
    "D3 历史街区与传统片区": ["历史文化名城名镇名村"],
    "D4 传承场所与活动场地": ["公共文化资源"],
    "E1 地方志类": ["可移动文物"],
    "E2 族谱家乘类": ["可移动文物"],
    "E3 碑记题咏类": ["不可移动文物", "可移动文物"],
    "E4 文集著述类": ["可移动文物"],
    "E5 口述史与地方记忆材料": ["非物质文化遗产"],
    "F1 朝代年号类": [],
    "F2 历史事件类": [],
    "F3 发展阶段类": [],
}

VALID_RELATION_GROUPS = frozenset({
    "空间关联", "传承延续", "营建创造", "文献记载",
    "时序归属", "从属分类", "文化表征", "社群组织", "人物关联",
})

VAGUE_RELATION_TERMS = frozenset({
    "相关", "有关", "联系", "涉及", "关联", "关于",
    "渊源深厚", "谱写新篇章", "密不可分", "息息相关",
    "一脉相承", "源远流长", "博大精深", "根深蒂固",
    "交相辉映", "水乳交融", "薪火相传",
})

ENTITY_SYSTEM_PROMPT = """\
你是南海区文化遗产专家。从文本中提取文化实体，标注AI分类和官方分类两套标签。所有输出必须简体中文（繁体转简体）。

# AI分类体系（ai_grade_label + ai_grade_type 必须严格匹配）

## A 非遗文化体系
- A1 表演艺术类非遗：醒狮、粤剧、龙舟说唱、十番音乐
- A2 传统技艺类非遗：灰塑、藤编、木雕、砖雕、陶塑
- A3 民俗节庆类非遗：生菜会、龙舟竞渡、庙会、花灯会
- A4 信俗礼仪类非遗：民间信仰、龙母诞、地方礼俗
- A5 传统体育游艺类非遗：洪拳、咏春、龙舟竞技、狮艺
- A6 饮食酿造类非遗及文化物产：九江双蒸酒、西樵大饼

## B 物质文化遗产体系
- B1 古建筑类：书院、祠堂、庙宇、楼阁、塔桥
- B2 宗教建筑类：宝峰寺、南海观音寺、云泉仙馆
- B3 纪念性建筑与名人故居类：康有为故居、黄飞鸿纪念馆
- B4 古遗址与生产遗存类：古窑址、聚落遗存
- B5 石刻碑记类：碑刻、摩崖石刻、匾额题记
- B6 古村落与聚落遗产类：松塘村、烟桥村、仙岗村

## C 传承主体体系
- C1 历史文化人物：康有为、湛若水、黄飞鸿
- C2 非遗传承人及技艺人物：工匠、艺师
- C3 文物营建与守护人物：创建者、修建者
- C4 宗族姓氏与地方社群：九江关氏、松塘区氏

## D 文化空间体系
- D1 山川水系空间：西樵山、西江、北江
- D2 镇街圩市空间：九江镇、丹灶镇、西樵镇
- D3 历史街区与传统片区
- D4 传承场所与活动场地：传习所、武馆

## E 文献记忆体系
- E1 地方志类：南海县志、大德南海志
- E2 族谱家乘类：族谱、家乘
- E3 碑记题咏类：碑记、诗文题刻
- E4 文集著述类：文集、学术著作
- E5 口述史与地方记忆材料

## F 历史时序体系
- F1 朝代年号类：明代、清代、民国、光绪二十四年
- F2 历史事件类：公车上书、戊戌变法
- F3 发展阶段类

# 官方分类体系（official_label + official_type 严格匹配，无对应则填""）

- 非物质文化遗产: 民间文学、传统音乐、传统舞蹈、传统戏剧、曲艺、传统体育、游艺与杂技、传统美术、传统技艺、传统医药、民俗
- 非遗传承主体: 传承人、传承群体
- 不可移动文物: 古文化遗址、古墓葬、古建筑、石窟寺及石刻、近现代重要史迹及代表性建筑
- 可移动文物: 古代文物、近代现代文物
- 历史文化名城名镇名村: 历史文化名城、历史文化名镇、历史文化名村、历史文化街区、历史建筑
- 自然保护地: 国家公园、自然保护区、自然公园
- 公共文化资源: 公共文化设施、公共文化产品、公共文化活动
- 旅游资源: 旅游景区、旅游度假区、旅游休闲街区

# AI→官方映射

| AI类型 | 官方label | 官方type示例 |
|---|---|---|
| A1-A5 | 非物质文化遗产 | 传统舞蹈/传统技艺/民俗/传统体育、游艺与杂技 等 |
| A6 | 非物质文化遗产 | 传统技艺 |
| B1-B2 | 不可移动文物 | 古建筑 |
| B3 | 不可移动文物 | 近现代重要史迹及代表性建筑 |
| B4 | 不可移动文物 | 古文化遗址 |
| B5 | 不可移动文物 | 石窟寺及石刻 |
| B6 | 历史文化名城名镇名村 | 历史文化名村 |
| C1、C3、F1-F3 | （留空""） | （留空""） |
| C2 | 非遗传承主体 | 传承人 |
| C4 | 非遗传承主体 | 传承群体 |
| D1 | 自然保护地 | 自然公园 |
| D2 | 历史文化名城名镇名村 | 历史文化名镇 |
| D3 | 历史文化名城名镇名村 | 历史文化街区 |
| D4 | 公共文化资源 | 公共文化设施 |
| E1-E4 | 可移动文物 | 古代文物 |
| E5 | 非物质文化遗产 | 民间文学 |

# 规则

1. 实体须原文中实际出现的具体名词，2~15字
2. 笼统集合词（"南海名人""南海风俗"）不提取，应提取具体的人名或具体风俗
3. 同一实体多种称谓只取最常见的一个
4. description须含原文具体信息
5. 古村落→B6；祠堂书院→B1；宗教建筑→B2
6. confidence有区分度，不要全给同一个分数

# 输出格式

仅输出JSON数组，字段如下例：
[{"name":"醒狮","ai_grade_label":"A 非遗文化体系","ai_grade_type":"A1 表演艺术类非遗","official_label":"非物质文化遗产","official_type":"传统舞蹈","description":"岭南传统表演艺术，又称南狮，南海地区代表性非遗项目","confidence":0.96}]

无实体则输出[]。不要输出任何解释文字，仅输出JSON。
"""

RELATION_SYSTEM_PROMPT = """\
你是南海区文旅知识图谱专家。根据实体列表和原文，提取实体间关系。所有输出必须简体中文。

# 方向规则（最重要）

"source + relation_text + target" 必须读成通顺的主谓宾句子。
✅ 康有为→出生于→丹灶镇  ✅ 南海县志→记载→西樵山  ✅ 松塘村→位于→西樵镇
❌ 西樵山→位于→云路村（反了）  ❌ 丹灶镇→出生于→康有为（反了）
输出前默读每条，不通顺则调换方向。

# relation_group（9类）

空间关联: 位于/坐落于/发源于（事物→地理空间）
传承延续: 师承/传承/合并为/演变为（人物→人物；村落→村落）
营建创造: 创建/修建/重修/捐建（人物→建筑文物）
文献记载: 记载/收录/载有（文献→被记内容；source须为文献类实体）
时序归属: 始建于/形成于/兴盛于/刊于（实体→时间）
从属分类: 属于/下辖/又名/即（子→父/别名）
文化表征: 象征/承载（具体→抽象）
社群组织: 祭祀/主持/举办（社群→文化对象）
人物关联: 出生于/创立/著述/主修（source须为人物C1/C2/C3）

# 规则

1. source/target须与实体列表名称完全一致
2. relation_text用具体动词短语(2~6字)，基于原文语义提炼，禁用修饰性描写("渊源深厚""谱写新篇章"不可)
3. evidence须为原文真实片段(≤50字)，繁转简但保持原文措辞，禁止"文中提及"等元描述
4. 找不到原文依据的关系不输出
5. 同一对实体只保留一个方向（A→B"包含"和B→A"收录于"是同一条，只留一个）
6. 朝代仅作时间背景时不构成"记载于"关系；并列步骤不等于"属于"
7. 合并/演变→传承延续（非时序归属）；又名/即→从属分类
8. 禁止空泛词："相关""有关""联系""涉及"

# 输出格式

仅JSON数组，示例：
[{"source":"康有为","target":"丹灶镇","relation_text":"出生于","relation_group":"人物关联","evidence":"康有为，南海丹灶苏村人","confidence":0.96}]

无关系输出[]。
"""


def call_qwen_api(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_retries: Optional[int] = None,
    retry_delay: Optional[float] = None,
) -> Optional[str]:
    assert client is not None
    m = model or RUNTIME_MODEL
    retries = max_retries if max_retries is not None else DEFAULT_MAX_RETRIES
    delay = retry_delay if retry_delay is not None else DEFAULT_RETRY_DELAY

    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=m,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                top_p=0.8,
                max_tokens=4096,
                stream=False,
                timeout=120,
                extra_body={"enable_thinking": False},
            )
            if resp.choices:
                return resp.choices[0].message.content or ""
            print(f"  API 空 choices，重试 {attempt + 1}/{retries}")
        except RateLimitError as e:
            wait = delay * (2 ** attempt)
            print(f"  限流 {e}，{wait:.1f}s 后重试 {attempt + 1}/{retries}")
            time.sleep(wait)
        except APIError as e:
            print(f"  APIError {e}，重试 {attempt + 1}/{retries}")
            time.sleep(delay)
        except Exception as e:
            err = str(e).lower()
            if "timeout" in err or "timed out" in err:
                print(f"  请求超时，重试 {attempt + 1}/{retries}")
            else:
                print(f"  错误 {type(e).__name__}: {e}，重试 {attempt + 1}/{retries}")
            time.sleep(delay)
    return None


def parse_json_response(text: Optional[str]) -> List[Dict[str, Any]]:
    if not text:
        return []
    text = text.strip()
    te = text.rfind("</think>")
    if te != -1:
        text = text[te + len("</think>") :].strip()
    if text.startswith("["):
        try:
            end = text.rfind("]") + 1
            return json.loads(text[:end])
        except json.JSONDecodeError:
            pass
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e > s:
        try:
            return json.loads(text[s : e + 1])
        except json.JSONDecodeError:
            pass
    return []


def split_text_to_chunks(text: str, chunk_size: int, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if text.startswith("---"):
        end_fm = text.find("---", 3)
        if end_fm != -1:
            text = text[end_fm + 3 :].strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^一-龥a-zA-Z0-9，。、；：\"'（）《》—…·！？\s]", "", text)
    chunks = []
    pos = 0
    while pos < len(text):
        end = min(pos + chunk_size, len(text))
        chunk = text[pos:end]
        if len(chunk.strip()) > 50:
            chunks.append(chunk.strip())
        pos += chunk_size - overlap
    return chunks


NON_CULTURAL_ENTITIES = frozenset({
    "英吉利", "法兰西", "法蘭西", "日本", "美国", "西班牙", "秘鲁",
    "中国", "中华民族", "中华人民共和国",
})


def validate_entity(e: Any) -> bool:
    if not isinstance(e, dict):
        return False
    name = to_simplified((e.get("name") or "").strip())
    agl = (e.get("ai_grade_label") or "").strip()
    agt = (e.get("ai_grade_type") or "").strip()
    ol = (e.get("official_label") or "").strip()
    ot = (e.get("official_type") or "").strip()
    conf = e.get("confidence", 0)
    if not name or len(name) < 2 or len(name) > 15:
        return False
    if name in NON_CULTURAL_ENTITIES:
        return False
    if agt not in AI_ENTITY_TYPES:
        return False
    if AI_LABEL_BY_TYPE.get(agt) != agl:
        return False
    valid_official_labels = AI_TO_OFFICIAL_MAPPING.get(agt, [])
    if ol or ot:
        if ol not in valid_official_labels:
            return False
        if ot and ot not in OFFICIAL_ENTITY_TYPES:
            return False
        if ot and OFFICIAL_LABEL_BY_TYPE.get(ot) != ol:
            return False
    elif valid_official_labels:
        pass
    if not isinstance(conf, (int, float)) or conf < 0.5:
        return False
    if name in ANCHOR_NAMES:
        return conf >= 0.5
    if conf < 0.70:
        return False
    return True


RELATION_GROUP_HINTS: Dict[str, str] = {
    "合并为": "传承延续", "合并自": "传承延续", "演变为": "传承延续",
    "改名为": "传承延续", "师承": "传承延续", "传承自": "传承延续",
    "又名": "从属分类", "即": "从属分类", "亦称": "从属分类",
    "属于": "从属分类", "下辖": "从属分类", "包含": "从属分类",
    "位于": "空间关联", "坐落于": "空间关联", "发源于": "空间关联",
    "分布于": "空间关联",
    "始建于": "时序归属", "形成于": "时序归属", "兴盛于": "时序归属",
    "刊于": "时序归属", "修于": "时序归属", "毁于": "时序归属",
    "重建于": "时序归属",
    "记载": "文献记载", "收录": "文献记载", "载有": "文献记载",
    "记载于": "文献记载",
    "创建": "营建创造", "修建": "营建创造", "重修": "营建创造",
    "捐建": "营建创造", "营建": "营建创造",
    "出生于": "人物关联", "创立": "人物关联", "著述": "人物关联",
    "主修": "人物关联", "主纂": "人物关联",
    "祭祀": "社群组织", "主持": "社群组织", "举办": "社群组织",
    "供奉": "社群组织",
    "象征": "文化表征", "承载": "文化表征",
}


def validate_relation(r: Any, known_entities: set) -> bool:
    if not isinstance(r, dict):
        return False
    src = (r.get("source") or "").strip()
    tgt = (r.get("target") or "").strip()
    rel = (r.get("relation_text") or r.get("relation") or "").strip()
    rg = (r.get("relation_group") or "").strip()
    evidence = (r.get("evidence") or "").strip()
    conf = r.get("confidence", 0)
    if not src or not tgt or not rel or src == tgt:
        return False
    if rel in VAGUE_RELATION_TERMS:
        return False
    if not evidence:
        return False
    if not isinstance(conf, (int, float)) or conf < 0.65:
        return False
    if src not in known_entities or tgt not in known_entities:
        return False
    hint = RELATION_GROUP_HINTS.get(rel)
    if hint:
        r["relation_group"] = hint
    if rg and rg not in VALID_RELATION_GROUPS:
        r["relation_group"] = ""
    return True


def _simplify_entity(e: Dict[str, Any]) -> Dict[str, Any]:
    """繁→简 + 字段规整"""
    e["name"] = to_simplified(e["name"].strip())
    e["ai_grade_label"] = (e.get("ai_grade_label") or "").strip()
    e["ai_grade_type"] = (e.get("ai_grade_type") or "").strip()
    e["ai_layer"] = AI_LAYER_BY_LABEL.get(e["ai_grade_label"], "")
    e["official_label"] = (e.get("official_label") or "").strip()
    e["official_type"] = (e.get("official_type") or "").strip()
    e["description"] = to_simplified((e.get("description") or "").strip())
    return e


def extract_entities_from_chunk(chunk_text: str, file_title: str = "") -> tuple:
    user_prompt = (
        f"以下是佛山市南海区文史资料《{file_title}》的一段文本。"
        f"请按规则提取文化相关实体（含 AI分类 与 官方分类 两套标签）。\n\n【文本】\n{chunk_text}"
    )
    response = call_qwen_api(ENTITY_SYSTEM_PROMPT, user_prompt)
    raw = parse_json_response(response)
    valid = []
    seen_names = set()
    for e in raw:
        if not validate_entity(e):
            continue
        e = _simplify_entity(e)
        if e["name"] in seen_names:
            continue
        seen_names.add(e["name"])
        e["is_anchor"] = e["name"] in ANCHOR_NAMES
        e["source_file"] = file_title
        valid.append(e)
    return valid, response


def extract_relations_from_chunk(
    chunk_text: str, entities_in_chunk: List[Dict[str, Any]], file_title: str = ""
) -> tuple:
    if len(entities_in_chunk) < 2:
        return [], ""
    lines = []
    for e in entities_in_chunk[:30]:
        off_tag = e.get("official_type", "")
        off_str = f"；官方:{e.get('official_label', '')}/{off_tag}" if off_tag else ""
        lines.append(
            f"  - {e['name']}（AI:{e.get('ai_grade_type', '')}{off_str}）"
            f"：{e.get('description', '')}"
        )
    entity_list_str = "\n".join(lines)
    user_prompt = (
        f"以下是《{file_title}》的一段文本及已提取实体。\n"
        f"请判断实体间关系（可多对多关系）。\n\n【实体列表】\n{entity_list_str}\n\n【原文】\n{chunk_text}"
    )
    response = call_qwen_api(RELATION_SYSTEM_PROMPT, user_prompt)
    raw = parse_json_response(response)
    known = {e["name"] for e in entities_in_chunk}
    valid = []
    for r in raw:
        r["source"] = to_simplified((r.get("source") or "").strip())
        r["target"] = to_simplified((r.get("target") or "").strip())
        rt = to_simplified((r.get("relation_text") or r.get("relation") or "").strip())
        r["relation_text"] = rt
        r["evidence"] = to_simplified((r.get("evidence") or "").strip())
        r.pop("relation", None)
        if not validate_relation(r, known):
            continue
        rg = (r.get("relation_group") or "").strip()
        r["relation_group"] = rg if rg in VALID_RELATION_GROUPS else ""
        r["source_file"] = file_title
        valid.append(r)
    return valid, response


def load_progress() -> Dict[str, Any]:
    if os.path.exists(PROGRESS_PATH):
        try:
            with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            print("  警告: progress.json 损坏，已重置")
    return {
        "task": "qwen_extraction",
        "model": RUNTIME_MODEL,
        "total_files": 0,
        "completed_files": [],
        "file_chunk_progress": {},
        "stats": {"entities": 0, "relations": 0},
        "last_update": "",
        "status": "idle",
    }


def _safe_json_write(target_path: str, data: Any):
    """原子写入JSON，用唯一临时文件名 + 重试，避免 Windows 文件锁冲突"""
    tmp = target_path + f".{os.getpid()}_{threading.get_ident()}.tmp"
    for attempt in range(5):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, target_path)
            return
        except OSError:
            time.sleep(0.1 * (attempt + 1))
    try:
        os.remove(tmp)
    except OSError:
        pass


def save_progress(progress: Dict[str, Any]):
    with _progress_lock:
        progress["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        progress["model"] = RUNTIME_MODEL
        _safe_json_write(PROGRESS_PATH, progress)


def append_log(filename: str, chunk: str, ent_count: int, rel_count: int, elapsed: float):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tid = threading.current_thread().name
    wid = _worker_slot()
    line = (
        f"{ts} | W{wid} {tid} | model={RUNTIME_MODEL} | file={filename} | {chunk} | "
        f"E={ent_count} R={rel_count} | {elapsed}s\n"
    )
    with _log_lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)


def load_file_entities(filename: str) -> Dict[str, Any]:
    path = os.path.join(ENTITY_DIR, filename.replace(".md", ".json"))
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"chunks": {}}


def save_file_entities(filename: str, data: Dict[str, Any]):
    path = os.path.join(ENTITY_DIR, filename.replace(".md", ".json"))
    _safe_json_write(path, data)


def load_file_relations(filename: str) -> Dict[str, Any]:
    path = os.path.join(RELATION_DIR, filename.replace(".md", ".json"))
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"chunks": {}}


def save_file_relations(filename: str, data: Dict[str, Any]):
    path = os.path.join(RELATION_DIR, filename.replace(".md", ".json"))
    _safe_json_write(path, data)


def reset_all():
    for d in (ENTITY_DIR, RELATION_DIR):
        if os.path.isdir(d):
            shutil.rmtree(d)
    for f in (
        PROGRESS_PATH,
        LOG_PATH,
        os.path.join(OUTPUT_DIR, "merged_entities.json"),
        os.path.join(OUTPUT_DIR, "merged_relations.json"),
        os.path.join(OUTPUT_DIR, "demo_report.md"),
    ):
        if os.path.exists(f):
            os.remove(f)
    print("已清空 qwen_extraction 输出。")


def get_corpus_files(demo: bool = False) -> List[Dict[str, Any]]:
    index_path = os.path.join(CORPUS_DIR, "corpus_index.json")
    if not os.path.exists(index_path):
        print("错误: corpus_index.json 不存在，请先运行 prepare_corpus.py")
        return []
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    files = index["files"]
    if demo:
        demo_targets = ["南海县志_OCR连续文本", "南海龙狮", "西樵山专辑"]
        demo_files = []
        for f_info in files:
            for target in demo_targets:
                if target in f_info["title"]:
                    demo_files.append(f_info)
                    break
            if len(demo_files) >= 3:
                break
        return demo_files or files[:3]
    return files


def process_file(
    file_info: Dict[str, Any],
    progress: Dict[str, Any],
    chunk_size: int,
    demo: bool = False,
    max_workers: int = 1,
) -> tuple:
    filename = file_info["filename"]
    title = file_info["title"]
    filepath = os.path.join(CORPUS_DIR, filename)
    if not os.path.exists(filepath):
        print(f"  文件不存在: {filepath}")
        return 0, 0
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    if demo:
        text = text[:12000]
    chunks = split_text_to_chunks(text, chunk_size)
    if not chunks:
        return 0, 0

    ent_data = load_file_entities(filename)
    rel_data = load_file_relations(filename)
    completed = set(ent_data.get("chunks", {}).keys())
    file_ent = file_rel = 0
    wid = _worker_slot()
    pos = wid + 1 if max_workers > 1 else None
    desc = f"W{wid}|{title[:18]}"
    chunk_bar = tqdm(
        enumerate(chunks),
        total=len(chunks),
        desc=desc,
        leave=False,
        ncols=110,
        position=pos,
        dynamic_ncols=False,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
    )
    for chunk_idx, chunk_text in chunk_bar:
        chunk_key = f"chunk_{chunk_idx:04d}"
        if chunk_key in completed:
            file_ent += len(ent_data["chunks"][chunk_key].get("entities", []))
            file_rel += len(rel_data.get("chunks", {}).get(chunk_key, {}).get("relations", []))
            continue
        t0 = time.time()
        entities, _ = extract_entities_from_chunk(chunk_text, title)
        file_ent += len(entities)
        ent_data.setdefault("chunks", {})[chunk_key] = {
            "entities": entities,
            "chunk_text_hash": hashlib.md5(chunk_text.encode()).hexdigest()[:8],
        }
        save_file_entities(filename, ent_data)
        relations, _ = extract_relations_from_chunk(chunk_text, entities, title)
        file_rel += len(relations)
        rel_data.setdefault("chunks", {})[chunk_key] = {"relations": relations}
        save_file_relations(filename, rel_data)
        elapsed = time.time() - t0
        append_log(filename, chunk_key, len(entities), len(relations), round(elapsed, 1))
        with _progress_lock:
            progress["file_chunk_progress"][filename] = chunk_idx + 1
            progress["stats"]["entities"] += len(entities)
            progress["stats"]["relations"] += len(relations)
        save_progress(progress)
        chunk_bar.set_postfix_str(f"E={file_ent} R={file_rel}")
    chunk_bar.close()
    return file_ent, file_rel


def run_extraction(
    demo: bool,
    chunk_size: int,
    num_threads: int,
    max_retries: int,
    retry_delay: float,
):
    global RUNTIME_MODEL, DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY
    DEFAULT_MAX_RETRIES = max_retries
    DEFAULT_RETRY_DELAY = retry_delay

    for d in (OUTPUT_DIR, ENTITY_DIR, RELATION_DIR):
        os.makedirs(d, exist_ok=True)
    load_anchors()
    files = get_corpus_files(demo=demo)
    if not files:
        return 0, 0

    progress = load_progress()
    completed = set(progress.get("completed_files", []))
    pending = [f for f in files if f["filename"] not in completed] if not demo else files
    done_count = len(files) - len(pending)

    mode_str = "DEMO" if demo else f"全量 {len(files)} 篇 / 待处理 {len(pending)}"
    print(f"\n{'='*60}\n千问抽取 — {mode_str}\n模型: {RUNTIME_MODEL} | 线程: {num_threads} | chunk={chunk_size}\n{'='*60}\n")

    progress["total_files"] = len(files)
    progress["status"] = "running"
    save_progress(progress)

    total_ent = total_rel = 0
    counter_lock = threading.Lock()
    global _worker_seq
    _worker_seq[0] = 0

    file_bar = tqdm(
        total=len(pending),
        desc="文件总进度",
        position=0,
        ncols=110,
        leave=True,
        dynamic_ncols=False,
    )

    def worker(fi: Dict[str, Any]):
        nonlocal total_ent, total_rel
        fn = fi["filename"]
        ttl = fi["title"]
        slot = _worker_slot()
        tqdm.write(f"[W{slot}] 开始: {ttl} ({fn})")
        try:
            ec, rc = process_file(fi, progress, chunk_size, demo=demo, max_workers=num_threads)
        except Exception as e:
            tqdm.write(f"[W{slot}] 失败 {fn}: {e}")
            raise
        with counter_lock:
            total_ent += ec
            total_rel += rc
        if not demo:
            with _progress_lock:
                if fn not in progress.get("completed_files", []):
                    progress.setdefault("completed_files", []).append(fn)
            save_progress(progress)
        with counter_lock:
            file_bar.set_postfix_str(f"E={total_ent} R={total_rel}")
        file_bar.update(1)
        tqdm.write(f"[W{slot}] 完成: {ttl} E={ec} R={rc}")

    if num_threads <= 1:
        for fi in pending:
            worker(fi)
    else:
        with ThreadPoolExecutor(
            max_workers=num_threads,
            thread_name_prefix="Qwen",
            initializer=_pool_init_worker,
        ) as ex:
            futs = [ex.submit(worker, fi) for fi in pending]
            for fut in as_completed(futs):
                err = fut.exception()
                if err:
                    tqdm.write(f"任务异常: {err}")

    file_bar.close()
    progress["status"] = "completed"
    save_progress(progress)
    print(f"\n完成。实体累计片段条数(未去重): {total_ent}，关系: {total_rel}\n输出: {OUTPUT_DIR}\n")
    return total_ent, total_rel


def merge_results():
    print("\n合并实体…")
    entity_counter: Counter = Counter()
    entity_info: Dict[str, Dict[str, Any]] = {}
    entity_sources: Dict[str, set] = defaultdict(set)
    for fname in sorted(os.listdir(ENTITY_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(ENTITY_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)
        for chunk_data in data.get("chunks", {}).values():
            for e in chunk_data.get("entities", []):
                name = to_simplified((e.get("name") or "").strip())
                if not name:
                    continue
                entity_counter[name] += 1
                entity_sources[name].add(e.get("source_file", fname))
                prev = entity_info.get(name, {})
                if not prev or e.get("confidence", 0) > prev.get("confidence", 0):
                    e_copy = dict(e)
                    e_copy["name"] = name
                    e_copy["description"] = to_simplified((e.get("description") or "").strip())
                    entity_info[name] = e_copy
    merged = []
    for name, cnt in entity_counter.most_common():
        info = entity_info[name]
        if cnt >= 2 or name in ANCHOR_NAMES:
            agl = info.get("ai_grade_label", "")
            merged.append(
                {
                    "name": name,
                    "ai_grade_label": agl,
                    "ai_grade_type": info.get("ai_grade_type", ""),
                    "ai_layer": AI_LAYER_BY_LABEL.get(agl, ""),
                    "official_label": info.get("official_label", ""),
                    "official_type": info.get("official_type", ""),
                    "description": info.get("description", ""),
                    "confidence": round(float(info.get("confidence", 0.8)), 2),
                    "mentions": cnt,
                    "source_count": len(entity_sources[name]),
                    "is_anchor": name in ANCHOR_NAMES,
                }
            )
    ai_type_stats = dict(Counter(e["ai_grade_type"] for e in merged))
    ai_label_stats = dict(Counter(e["ai_grade_label"] for e in merged))
    ai_layer_stats = dict(Counter(e["ai_layer"] for e in merged if e["ai_layer"]))
    official_label_stats = dict(Counter(e["official_label"] for e in merged if e["official_label"]))
    official_type_stats = dict(Counter(e["official_type"] for e in merged if e["official_type"]))
    out = {
        "total": len(merged),
        "ai_type_stats": ai_type_stats,
        "ai_label_stats": ai_label_stats,
        "ai_layer_stats": ai_layer_stats,
        "official_label_stats": official_label_stats,
        "official_type_stats": official_type_stats,
        "ai_classification_hierarchy": AI_CLASSIFICATION_HIERARCHY,
        "official_classification_hierarchy": OFFICIAL_CLASSIFICATION_HIERARCHY,
        "ai_to_official_mapping": AI_TO_OFFICIAL_MAPPING,
        "ai_layer_by_label": AI_LAYER_BY_LABEL,
        "extracted_by": f"Qwen API ({RUNTIME_MODEL})",
        "merged_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "entities": merged,
    }
    path = os.path.join(OUTPUT_DIR, "merged_entities.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"合并实体: {len(merged)} → {path}")
    print(f"AI层级分布: {ai_layer_stats}")
    print(f"AI一级类分布: {ai_label_stats}")
    print(f"官方大类分布: {official_label_stats}")

    print("\n合并关系…")
    merged_rels = []
    seen = set()
    for fname in sorted(os.listdir(RELATION_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(RELATION_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)
        for chunk_data in data.get("chunks", {}).values():
            for r in chunk_data.get("relations", []):
                src = to_simplified((r.get("source") or "").strip())
                tgt = to_simplified((r.get("target") or "").strip())
                rt = to_simplified((r.get("relation_text") or "").strip())
                r["source"] = src
                r["target"] = tgt
                r["relation_text"] = rt
                r["evidence"] = to_simplified((r.get("evidence") or "").strip())
                if rt in VAGUE_RELATION_TERMS:
                    continue
                key = (src, tgt, rt)
                if key not in seen:
                    seen.add(key)
                    merged_rels.append(r)
    merged_names = {e["name"] for e in merged}
    final_rels = [r for r in merged_rels if r["source"] in merged_names and r["target"] in merged_names]
    pair_rels: Dict[tuple, List[str]] = defaultdict(list)
    for r in final_rels:
        pair = tuple(sorted([r["source"], r["target"]]))
        pair_rels[pair].append(r.get("relation_text", ""))
    multi = sum(1 for v in pair_rels.values() if len(set(v)) > 1)
    rel_stats = dict(Counter(r.get("relation_text", "") for r in final_rels))
    group_stats = dict(Counter(r.get("relation_group", "") for r in final_rels if r.get("relation_group")))
    rel_out = {
        "total": len(final_rels),
        "multi_relation_pairs": multi,
        "relation_stats": rel_stats,
        "relation_group_stats": group_stats,
        "valid_relation_groups": sorted(VALID_RELATION_GROUPS),
        "extracted_by": f"Qwen API ({RUNTIME_MODEL})",
        "merged_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "relations": final_rels,
    }
    rpath = os.path.join(OUTPUT_DIR, "merged_relations.json")
    with open(rpath, "w", encoding="utf-8") as f:
        json.dump(rel_out, f, ensure_ascii=False, indent=2)
    print(f"合并关系: {len(final_rels)} → {rpath}")
    return merged, final_rels


def generate_demo_report():
    lines = [
        "# Qwen 抽取 DEMO\n",
        f"时间: {datetime.now():%Y-%m-%d %H:%M}\n",
        f"模型: {RUNTIME_MODEL}\n",
        "---\n",
    ]
    for fname in sorted(os.listdir(ENTITY_DIR)):
        if not fname.endswith(".json"):
            continue
        title = fname.replace(".json", "")
        ep = os.path.join(ENTITY_DIR, fname)
        rp = os.path.join(RELATION_DIR, fname)
        with open(ep, "r", encoding="utf-8") as f:
            ed = json.load(f)
        rd = {}
        if os.path.exists(rp):
            with open(rp, "r", encoding="utf-8") as f:
                rd = json.load(f)
        lines.append(f"\n## {title}\n")
        all_e = []
        for cv in ed.get("chunks", {}).values():
            all_e.extend(cv.get("entities", []))
        seen_ent = {}
        for e in all_e:
            nm = to_simplified((e.get("name") or "").strip())
            if nm and nm not in seen_ent:
                seen_ent[nm] = e
        unique_e = list(seen_ent.values())
        lines.append(f"实体 {len(unique_e)}\n")
        for e in unique_e:
            nm = to_simplified(e["name"])
            off = e.get("official_type", "")
            off_str = f" | 官方:{e.get('official_label', '')}/{off}" if off else " | 官方:无"
            lines.append(
                f"- {nm} | AI:{e.get('ai_grade_type', '')}{off_str} | {e.get('confidence')}\n"
            )
        all_r = []
        for cv in rd.get("chunks", {}).values():
            all_r.extend(cv.get("relations", []))
        filtered_r = [r for r in all_r
                       if to_simplified(r.get("relation_text", "")) not in VAGUE_RELATION_TERMS]
        lines.append(f"\n关系 {len(filtered_r)}\n")
        for r in filtered_r:
            rg = r.get("relation_group", "")
            rg_tag = f"[{rg}] " if rg else ""
            src = to_simplified(r.get("source", ""))
            tgt = to_simplified(r.get("target", ""))
            rt = to_simplified(r.get("relation_text", ""))
            ev = to_simplified(r.get("evidence", ""))[:30]
            lines.append(f"- {rg_tag}{src} —{rt}→ {tgt} | {ev}\n")
    report_path = os.path.join(OUTPUT_DIR, "demo_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))
    print(f"DEMO 报告: {report_path}")


def main():
    global RUNTIME_MODEL
    parser = argparse.ArgumentParser(description="千问 API 实体/关系抽取（双标签）")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--merge-only", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="配置文件路径")
    parser.add_argument("--model", default=None, help="覆盖 config 中的模型名")
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--threads", type=int, default=None, help="并发线程数（每线程处理不同书籍）")
    parser.add_argument("--max-retries", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config_file(args.config)
    if args.config != DEFAULT_CONFIG_PATH and not cfg:
        print(f"未找到配置文件: {args.config}")
        raise SystemExit(1)

    rt = build_runtime_settings(cfg, args)
    key = rt["api_key"]
    if not key:
        print(
            "未配置 API Key：请在环境变量 DASHSCOPE_API_KEY 或 config.json 的 "
            "api_key / dashscope_api_key 中设置。"
        )
        raise SystemExit(1)

    init_openai_client(key, rt["base_url"])
    RUNTIME_MODEL = rt["model"]
    threads = max(1, int(rt["threads"]))
    chunk_sz = int(rt["chunk_size"])
    max_retries = int(rt["max_retries"])
    retry_delay = float(rt["retry_delay"])

    if args.reset:
        reset_all()

    if args.merge_only:
        load_anchors()
        merge_results()
        return

    run_extraction(
        demo=args.demo,
        chunk_size=chunk_sz,
        num_threads=threads,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )
    if args.demo:
        generate_demo_report()
    else:
        merge_results()


if __name__ == "__main__":
    main()
