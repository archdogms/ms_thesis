#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
南海文史资料PDF OCR识别
对扫描型PDF使用RapidOCR进行文字识别
"""

import os
import re
import json
import fitz  # PyMuPDF for rendering
from rapidocr_onnxruntime import RapidOCR

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
BOOKS_DIR = os.path.join(BASE_DIR, "books")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "典籍文本", "南海文史资料")
STATS_PATH = os.path.join(BASE_DIR, "data", "典籍文本", "文本统计报告.json")

EXCLUDE_VOLUMES = {"第4辑", "第7辑", "第9辑", "第32辑", "第35辑"}


def extract_volume_number(filename):
    m = re.search(r'第(\d+)辑', filename)
    return int(m.group(1)) if m else 0


def extract_short_title(filename):
    m = re.match(r'南海文史资料\s+第(\d+)辑\s*(.+?)\s*\(', filename)
    if m:
        vol = m.group(1)
        subtitle = m.group(2).strip()
        return f"第{vol}辑_{subtitle}" if subtitle else f"第{vol}辑"
    m = re.match(r'南海文史资料\s+第(\d+)辑', filename)
    return f"第{m.group(1)}辑" if m else filename[:30]


def should_exclude(filename):
    for vol in EXCLUDE_VOLUMES:
        if vol in filename:
            return True
    return False


def count_cjk(text):
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def ocr_pdf(pdf_path, ocr_engine, dpi=200):
    """将PDF每页渲染为图片后OCR识别"""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    all_text = []

    for page_num in range(total_pages):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        try:
            result, _ = ocr_engine(img_bytes)
            if result:
                page_text = "\n".join([line[1] for line in result])
                all_text.append(page_text)
        except Exception as e:
            pass

        if (page_num + 1) % 20 == 0 or page_num == total_pages - 1:
            print(f" {page_num+1}/{total_pages}", end="", flush=True)

    doc.close()
    return "\n\n".join(all_text)


def main():
    print("=" * 60)
    print("南海文史资料PDF OCR识别")
    print("=" * 60)

    ocr_engine = RapidOCR()
    print("OCR引擎: RapidOCR (ONNX Runtime)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files = sorted(
        [f for f in os.listdir(BOOKS_DIR) if f.endswith(".pdf")],
        key=extract_volume_number
    )

    to_process = [f for f in pdf_files if not should_exclude(f)]
    print(f"待处理: {len(to_process)} 本 (已排除{len(pdf_files)-len(to_process)}本)")

    results = {"success": [], "failed": []}

    for i, fname in enumerate(to_process):
        short_title = extract_short_title(fname)
        out_name = f"南海文史资料_{short_title}.txt"
        out_path = os.path.join(OUTPUT_DIR, out_name)

        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as f:
                existing_cjk = count_cjk(f.read())
            if existing_cjk > 500:
                print(f"[{i+1}/{len(to_process)}] {short_title} 已存在({existing_cjk:,}字), 跳过")
                results["success"].append({"title": short_title, "cjk_chars": existing_cjk, "status": "cached"})
                continue

        print(f"[{i+1}/{len(to_process)}] {short_title}:", end="", flush=True)
        pdf_path = os.path.join(BOOKS_DIR, fname)
        text = ocr_pdf(pdf_path, ocr_engine)
        cjk_count = count_cjk(text)

        if cjk_count > 500:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f" -> {cjk_count:,} 中文字符")
            results["success"].append({"title": short_title, "output": out_name, "cjk_chars": cjk_count})
        else:
            print(f" -> 仅{cjk_count}字符, 失败")
            results["failed"].append({"title": short_title, "cjk_chars": cjk_count})

    print(f"\n{'='*60}")
    print(f"OCR结果: 成功{len(results['success'])}本, 失败{len(results['failed'])}本")
    total_new_cjk = sum(r["cjk_chars"] for r in results["success"])
    print(f"新增中文字符: {total_new_cjk:,}")

    for r in results["success"]:
        print(f"  [OK] {r['title']}: {r['cjk_chars']:>8,} 字符")
    for r in results["failed"]:
        print(f"  [FAIL] {r['title']}: {r['cjk_chars']} 字符")

    report_path = os.path.join(OUTPUT_DIR, "OCR报告.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n--- 更新全局文本统计 ---")
    update_global_stats()


def update_global_stats():
    text_dir = os.path.dirname(OUTPUT_DIR)
    stats = []
    for root, dirs, files in os.walk(text_dir):
        for fname in files:
            if fname.endswith((".txt", ".md")) and "统计" not in fname and "报告" not in fname:
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                cjk = count_cjk(content)
                if cjk > 100:
                    stats.append({
                        "file": os.path.relpath(fpath, text_dir),
                        "chars": len(content),
                        "lines": content.count("\n") + 1,
                        "cjk_chars": cjk,
                    })
    stats.sort(key=lambda x: x["cjk_chars"], reverse=True)
    total_cjk = sum(s["cjk_chars"] for s in stats)

    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump({"total_files": len(stats), "total_cjk_chars": total_cjk, "files": stats}, f, ensure_ascii=False, indent=2)
    print(f"全局统计: {len(stats)} 个文件, {total_cjk:,} 个中文字符")


if __name__ == "__main__":
    main()
