#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
南海文史资料PDF 多线程并行OCR（带进度条）
使用 ThreadPoolExecutor + tqdm，每本PDF独立显示进度
ONNX Runtime 会释放GIL，所以线程池可有效并行
支持断点续跑（已完成的自动跳过）
"""

import os
import re
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import fitz
from rapidocr_onnxruntime import RapidOCR

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
BOOKS_DIR = os.path.join(BASE_DIR, "books")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "典籍文本", "南海文史资料")
STATS_PATH = os.path.join(BASE_DIR, "data", "典籍文本", "文本统计报告.json")

EXCLUDE_VOLUMES = {"第4辑", "第7辑", "第9辑", "第32辑", "第35辑"}
WORKERS = 12

print_lock = Lock()


def extract_volume_number(filename):
    m = re.search(r'第(\d+)辑', filename)
    return int(m.group(1)) if m else 0


def extract_short_title(filename):
    m = re.match(r'南海文史资料\s+第(\d+)辑\s*(.+?)\s*\(', filename)
    if m:
        vol, sub = m.group(1), m.group(2).strip()
        return f"第{vol}辑_{sub}" if sub else f"第{vol}辑"
    m = re.match(r'南海文史资料\s+第(\d+)辑', filename)
    return f"第{m.group(1)}辑" if m else filename[:30]


def should_exclude(filename):
    return any(vol in filename for vol in EXCLUDE_VOLUMES)


def count_cjk(text):
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def ocr_one_book(task):
    """OCR处理单本PDF（在线程中运行）"""
    idx, total, fname, short_title, pdf_path, out_path = task

    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            cjk = count_cjk(f.read())
        if cjk > 500:
            with print_lock:
                print(f"  [{idx}/{total}] {short_title}: 已有缓存 ({cjk:,}字), 跳过")
            return {"title": short_title, "cjk_chars": cjk, "status": "cached", "pages": 0}

    engine = RapidOCR()
    doc = fitz.open(pdf_path)
    n_pages = len(doc)
    all_text = []

    with print_lock:
        print(f"  [{idx}/{total}] {short_title} ({n_pages}页) 开始...")

    for page_num in range(n_pages):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(200/72, 200/72))
        img_bytes = pix.tobytes("png")
        try:
            result, _ = engine(img_bytes)
            if result:
                all_text.append("\n".join([line[1] for line in result]))
        except Exception:
            pass

        done = page_num + 1
        if done % 10 == 0 or done == n_pages:
            pct = done * 100 // n_pages
            filled = pct // 5
            bar = "#" * filled + "-" * (20 - filled)
            with print_lock:
                print(f"  [{idx}/{total}] {short_title}: [{bar}] {pct:3d}% ({done}/{n_pages})")

    doc.close()
    text = "\n\n".join(all_text)
    cjk = count_cjk(text)

    if cjk > 500:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        with print_lock:
            print(f"  [{idx}/{total}] {short_title}: 完成! {cjk:,} 中文字符")
        return {"title": short_title, "cjk_chars": cjk, "status": "ok", "pages": n_pages}
    else:
        with print_lock:
            print(f"  [{idx}/{total}] {short_title}: 失败 (仅{cjk}字符)")
        return {"title": short_title, "cjk_chars": cjk, "status": "fail", "pages": n_pages}


def main():
    print("=" * 60)
    print(f"南海文史资料PDF 多线程并行OCR")
    print(f"线程数: {WORKERS} | 断点续跑: 已完成自动跳过")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files = sorted(
        [f for f in os.listdir(BOOKS_DIR) if f.endswith(".pdf")],
        key=extract_volume_number
    )
    to_process = [f for f in pdf_files if not should_exclude(f)]
    print(f"\n待处理: {len(to_process)} 本 (排除{len(pdf_files)-len(to_process)}本涉政/已有)\n")

    tasks = []
    for i, fname in enumerate(to_process, 1):
        short_title = extract_short_title(fname)
        out_name = f"南海文史资料_{short_title}.txt"
        out_path = os.path.join(OUTPUT_DIR, out_name)
        pdf_path = os.path.join(BOOKS_DIR, fname)
        tasks.append((i, len(to_process), fname, short_title, pdf_path, out_path))

    start = time.time()

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(ocr_one_book, t): t for t in tasks}
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                task = futures[future]
                print(f"  [ERROR] {task[3]}: {e}")
                results.append({"title": task[3], "cjk_chars": 0, "status": "error", "pages": 0})

    elapsed = time.time() - start

    ok = [r for r in results if r["status"] == "ok"]
    cached = [r for r in results if r["status"] == "cached"]
    fail = [r for r in results if r["status"] in ("fail", "error")]

    print(f"\n{'='*60}")
    print(f"全部完成! 耗时 {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")
    print(f"  新OCR: {len(ok)} 本")
    print(f"  缓存跳过: {len(cached)} 本")
    print(f"  失败: {len(fail)} 本")

    total_cjk = sum(r["cjk_chars"] for r in results if r["status"] in ("ok", "cached"))
    print(f"  总中文字符: {total_cjk:,}\n")

    results.sort(key=lambda x: -x["cjk_chars"])
    for r in results:
        tag = {"ok": " OK ", "cached": "CACHE", "fail": "FAIL", "error": "ERROR"}.get(r["status"], "???")
        print(f"  [{tag}] {r['title']}: {r['cjk_chars']:>8,} 字符")

    report = os.path.join(OUTPUT_DIR, "OCR报告.json")
    with open(report, "w", encoding="utf-8") as f:
        json.dump({"elapsed_seconds": round(elapsed), "workers": WORKERS, "results": results}, f, ensure_ascii=False, indent=2)

    print(f"\n--- 更新全局文本统计 ---")
    update_stats()


def update_stats():
    text_dir = os.path.dirname(OUTPUT_DIR)
    stats = []
    for root, _, files in os.walk(text_dir):
        for fname in files:
            if fname.endswith((".txt", ".md")) and "统计" not in fname and "报告" not in fname:
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                cjk = count_cjk(content)
                if cjk > 100:
                    stats.append({
                        "file": os.path.relpath(fpath, text_dir),
                        "chars": len(content), "lines": content.count("\n") + 1, "cjk_chars": cjk,
                    })
    stats.sort(key=lambda x: x["cjk_chars"], reverse=True)
    total = sum(s["cjk_chars"] for s in stats)
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump({"total_files": len(stats), "total_cjk_chars": total, "files": stats}, f, ensure_ascii=False, indent=2)
    print(f"全局统计: {len(stats)} 个文件, {total:,} 个中文字符")


if __name__ == "__main__":
    main()
