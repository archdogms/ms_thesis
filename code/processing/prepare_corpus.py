#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文本语料统一整理脚本

功能：
  1. 将分散在多个子目录中的 .txt / .md 文件统一复制到 data/corpus/
  2. 全部转为 .md 格式，加编号前缀（001_, 002_, ...）
  3. 为 .txt 文件添加 YAML frontmatter（来源、字数等元信息）
  4. 生成 corpus_index.json 统一索引
"""

import os
import json
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
TEXT_DIR = os.path.join(DATA_DIR, "典籍文本")
CORPUS_DIR = os.path.join(DATA_DIR, "corpus")


def collect_source_files():
    """收集全部文本源文件，按固定顺序"""
    sources = []

    # 1) 南海县志 OCR
    ocr_path = os.path.join(TEXT_DIR, "南海县志_OCR连续文本.txt")
    if os.path.exists(ocr_path):
        sources.append({
            "path": ocr_path,
            "origin": "南海县志OCR",
            "category": "county_chronicle",
        })

    # 2) 开题阶段典籍 (*.md)
    kaiti_dir = os.path.join(TEXT_DIR, "开题阶段典籍")
    if os.path.isdir(kaiti_dir):
        for fname in sorted(os.listdir(kaiti_dir)):
            if fname.endswith(".md"):
                sources.append({
                    "path": os.path.join(kaiti_dir, fname),
                    "origin": "开题阶段典籍",
                    "category": "classical_texts",
                })

    # 3) 南海文史资料 (*.txt)
    nanhai_dir = os.path.join(TEXT_DIR, "南海文史资料")
    if os.path.isdir(nanhai_dir):
        for fname in sorted(os.listdir(nanhai_dir)):
            if fname.endswith(".txt"):
                sources.append({
                    "path": os.path.join(nanhai_dir, fname),
                    "origin": "南海文史资料",
                    "category": "historical_materials",
                })

    return sources


def build_frontmatter(meta: dict) -> str:
    """生成 YAML frontmatter"""
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def prepare_corpus():
    os.makedirs(CORPUS_DIR, exist_ok=True)

    sources = collect_source_files()
    print(f"共发现 {len(sources)} 个文本源文件")

    index = []

    for idx, src in enumerate(sources, start=1):
        src_path = src["path"]
        src_ext = os.path.splitext(src_path)[1].lower()
        src_name = os.path.splitext(os.path.basename(src_path))[0]

        # 清理文件名中的过长后缀
        clean_name = src_name
        if len(clean_name) > 60:
            clean_name = clean_name[:60]

        corpus_name = f"{idx:03d}_{clean_name}.md"
        corpus_path = os.path.join(CORPUS_DIR, corpus_name)

        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        char_count = len(content)

        if char_count < 200:
            print(f"  跳过 (内容过少 {char_count}字): {os.path.basename(src_path)}")
            continue

        meta = {
            "title": src_name,
            "source": src["origin"],
            "category": src["category"],
            "original_format": src_ext,
            "char_count": char_count,
            "corpus_id": f"C{idx:03d}",
            "prepared_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        if src_ext == ".txt":
            output_content = build_frontmatter(meta) + content
        else:
            if content.startswith("---"):
                output_content = content
            else:
                output_content = build_frontmatter(meta) + content

        with open(corpus_path, "w", encoding="utf-8") as f:
            f.write(output_content)

        index.append({
            "corpus_id": meta["corpus_id"],
            "filename": corpus_name,
            "title": src_name,
            "source": src["origin"],
            "category": src["category"],
            "char_count": char_count,
            "original_path": os.path.relpath(src_path, DATA_DIR),
            "status": "ready",
        })

        print(f"  [{idx:03d}/{len(sources)}] {corpus_name}  ({char_count:,} 字)")

    index_path = os.path.join(CORPUS_DIR, "corpus_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(index),
            "prepared_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "files": index,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n完成！{len(index)} 个文件已整理到 {CORPUS_DIR}")
    print(f"索引文件: {index_path}")

    total_chars = sum(item["char_count"] for item in index)
    print(f"总字数: {total_chars:,}")

    return index


if __name__ == "__main__":
    prepare_corpus()
