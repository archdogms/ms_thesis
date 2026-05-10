#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt


ROOT = Path(__file__).resolve().parents[1]


def strip_inline(text: str) -> str:
    text = re.sub(r"<sup>\[?([0-9,\-]+)\]?</sup>", r"[\1]", text)
    text = re.sub(r"</?[^>]+>", "", text)
    text = text.replace("**", "").replace("__", "")
    text = text.replace("*", "")
    text = text.replace("`", "")
    return text.strip()


def set_run_font(run, size: float | None = None, bold: bool | None = None) -> None:
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def set_paragraph_format(paragraph, first_indent: bool = False) -> None:
    fmt = paragraph.paragraph_format
    fmt.line_spacing = Pt(20)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    if first_indent:
        fmt.first_line_indent = Pt(24)


def add_text_paragraph(doc: Document, text: str, *, style: str | None = None, bold: bool = False, center: bool = False) -> None:
    paragraph = doc.add_paragraph(style=style)
    set_paragraph_format(paragraph, first_indent=(style is None and not center))
    if center:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(strip_inline(text))
    set_run_font(run, 12, bold)


def add_heading(doc: Document, level: int, text: str) -> None:
    paragraph = doc.add_paragraph(style=f"Heading {min(level, 4)}")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
    fmt = paragraph.paragraph_format
    fmt.line_spacing = Pt(20)
    fmt.space_before = Pt(18 if level == 1 else 12)
    fmt.space_after = Pt(8 if level == 1 else 4)
    run = paragraph.add_run(strip_inline(text))
    set_run_font(run, {1: 16, 2: 14, 3: 13}.get(level, 12), True)


def add_markdown_table(doc: Document, lines: list[str]) -> None:
    rows = []
    for i, line in enumerate(lines):
        cells = [strip_inline(cell) for cell in line.strip().strip("|").split("|")]
        if i == 1 and all(re.fullmatch(r":?-+:?", c.strip()) for c in cells):
            continue
        rows.append(cells)
    if not rows:
        return

    max_cols = max(len(row) for row in rows)
    table = doc.add_table(rows=len(rows), cols=max_cols)
    table.style = "Table Grid"
    table.autofit = True
    for r, row in enumerate(rows):
        for c in range(max_cols):
            cell_text = row[c] if c < len(row) else ""
            cell = table.cell(r, c)
            cell.text = ""
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run(cell_text)
            set_run_font(run, 10.5, bold=(r == 0))
    doc.add_paragraph()


def resolve_image(md_path: Path, image_ref: str) -> Path:
    ref = image_ref.strip()
    if ref.startswith("<") and ref.endswith(">"):
        ref = ref[1:-1]
    path = Path(ref)
    if path.is_absolute():
        return path
    return (md_path.parent / path).resolve()


def add_image(doc: Document, md_path: Path, image_ref: str) -> None:
    image_path = resolve_image(md_path, image_ref)
    if not image_path.exists():
        add_text_paragraph(doc, f"【图片缺失：{image_ref}】", bold=True, center=True)
        return
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    run.add_picture(str(image_path), width=Inches(6.2))


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.6)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(12)

    for level, size in [(1, 16), (2, 14), (3, 13), (4, 12)]:
        style = styles[f"Heading {level}"]
        style.font.name = "Times New Roman"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        style.font.size = Pt(size)
        style.font.bold = True


def export(md_path: Path, output_path: Path) -> None:
    doc = Document()
    configure_document(doc)

    lines = md_path.read_text(encoding="utf-8").splitlines()
    in_comment = False
    in_code = False
    in_equation = False
    table_buf: list[str] = []

    def flush_table() -> None:
        nonlocal table_buf
        if table_buf:
            add_markdown_table(doc, table_buf)
            table_buf = []

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("<!--"):
            in_comment = True
        if in_comment:
            if stripped.endswith("-->"):
                in_comment = False
            continue

        if stripped.startswith("```"):
            flush_table()
            in_code = not in_code
            continue
        if in_code:
            add_text_paragraph(doc, stripped)
            continue

        if stripped == "$$":
            flush_table()
            in_equation = not in_equation
            continue
        if in_equation:
            add_text_paragraph(doc, stripped, center=True)
            continue

        if stripped.startswith("|"):
            table_buf.append(stripped)
            continue
        flush_table()

        if not stripped:
            doc.add_paragraph()
            continue
        if stripped == "---":
            doc.add_page_break()
            continue

        image = re.match(r"!\[[^\]]*\]\((.*?)\)", stripped)
        if image:
            add_image(doc, md_path, image.group(1))
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            add_heading(doc, len(heading.group(1)), heading.group(2))
            continue

        if stripped.startswith("- "):
            paragraph = doc.add_paragraph(style="List Bullet")
            set_paragraph_format(paragraph)
            run = paragraph.add_run(strip_inline(stripped[2:]))
            set_run_font(run, 12)
            continue

        if re.match(r"^\d+\.\s+", stripped):
            paragraph = doc.add_paragraph(style="List Number")
            set_paragraph_format(paragraph)
            run = paragraph.add_run(strip_inline(re.sub(r"^\d+\.\s+", "", stripped)))
            set_run_font(run, 12)
            continue

        only_bold = re.fullmatch(r"\*\*(.*?)\*\*", stripped)
        if only_bold:
            add_text_paragraph(doc, only_bold.group(1), bold=True, center=True)
            continue

        add_text_paragraph(doc, stripped)

    flush_table()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the thesis Markdown draft to a Word document.")
    parser.add_argument("--input", required=True, help="Input Markdown path")
    parser.add_argument("--output", required=True, help="Output docx path")
    args = parser.parse_args()

    md_path = (ROOT / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)
    output_path = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    export(md_path, output_path)
    print(output_path)


if __name__ == "__main__":
    main()
