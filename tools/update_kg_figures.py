from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PICTURES = ROOT / "pictures"
THESIS_DIR = ROOT / "docs" / "thesis_02"
LATEX_FIG_DIR = ROOT / "docs" / "thuthesis-master" / "figures" / "ms_thesis"
BUILD_DIR = ROOT / "docs" / "thesis_02" / "_kg_figure_build"

LATEST_MD_NAME = "基于大数据的佛山市南海区旅游景区文旅融合潜力研究_md转化版.md"
LATEST_MEDIA_DIR_NAME = "基于大数据的佛山市南海区旅游景区文旅融合潜力研究_md转化版_media"
INITIAL_MD_NAME = "基于大数据的佛山市南海区旅游景区文旅融合潜力研究_初稿.md"
INITIAL_MEDIA_DIR_NAME = "基于大数据的佛山市南海区旅游景区文旅融合潜力研究_初稿_media"

DOCX_NAMES = [
    "md转化版.docx",
    "基于多源数据的佛山市南海区旅游景区文旅融合潜力研究_md转化版.docx",
    "基于多源数据的佛山市南海区旅游景区文旅融合潜力研究_完整版.docx",
    "基于大数据的佛山市南海区旅游景区文旅融合潜力研究_初稿.docx",
]

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W_NS, "a": A_NS, "r": R_NS, "rel": REL_NS}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in [
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def fit_image(img: Image.Image, box: tuple[int, int]) -> Image.Image:
    img = img.convert("RGB")
    img.thumbnail(box, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", box, "white")
    x = (box[0] - img.width) // 2
    y = (box[1] - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def panel(draw: ImageDraw.ImageDraw, xy: tuple[int, int], size: tuple[int, int], label: str) -> None:
    x, y = xy
    w, h = size
    draw.rounded_rectangle((x, y, x + w, y + h), radius=14, outline=(220, 220, 220), width=2)
    draw.text((x + 18, y + h - 44), label, fill=(20, 20, 20), font=font(28))


def make_pair(out_path: Path, left_name: str, right_name: str, left_label: str, right_label: str) -> None:
    left = Image.open(PICTURES / left_name)
    right = Image.open(PICTURES / right_name)

    panel_w, panel_h = 1440, 1220
    label_h = 58
    gap = 56
    margin = 48
    canvas_w = panel_w * 2 + gap + margin * 2
    canvas_h = panel_h + label_h + margin * 2
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(canvas)

    left_box = fit_image(left, (panel_w - 36, panel_h - 24))
    right_box = fit_image(right, (panel_w - 36, panel_h - 24))
    lx, y = margin, margin
    rx = margin + panel_w + gap

    canvas.paste(left_box, (lx + 18, y + 12))
    canvas.paste(right_box, (rx + 18, y + 12))
    panel(draw, (lx, y), (panel_w, panel_h), left_label)
    panel(draw, (rx, y), (panel_w, panel_h), right_label)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, optimize=True)


def replace_text(path: Path, replacements: dict[str, str]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in replacements.items():
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8", newline="\n")
        return True
    return False


def rels_map(docx_dir: Path) -> dict[str, str]:
    rels_path = docx_dir / "word" / "_rels" / "document.xml.rels"
    tree = ET.parse(rels_path)
    out: dict[str, str] = {}
    for rel in tree.getroot():
        rid = rel.attrib.get(f"{{{REL_NS}}}Id") or rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rid and target:
            out[rid] = target
    return out


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(t.text or "" for t in paragraph.findall(".//w:t", NS))


def paragraph_embeds(paragraph: ET.Element) -> list[str]:
    return [e.attrib[f"{{{R_NS}}}embed"] for e in paragraph.findall(".//a:blip", NS) if f"{{{R_NS}}}embed" in e.attrib]


def replace_docx_text(docx_dir: Path) -> bool:
    replacements = {
        "图 4.2 汇总展示了知识图谱全局网络与人物关联总图。": "图 4.2 汇总展示了更新后的知识图谱全局网络与人物关联总图。",
        "图 4.2 汇总展示了知识图谱全局网络与人物关联子图。": "图 4.2 汇总展示了更新后的知识图谱全局网络与人物关联总图。",
        "人物子图则用于说明典籍记忆如何通过人物、地点、技艺与事件向外扩展。": "人物关联总图则用于说明典籍记忆如何通过人物、地点、技艺与事件向外扩展。",
        "图 4.2　知识图谱全局网络与典型人物子图": "图 4.2　知识图谱全局网络与人物关联总图",
    }
    doc_path = docx_dir / "word" / "document.xml"
    tree = ET.parse(doc_path)
    changed = False
    for paragraph in tree.findall(".//w:p", NS):
        text_nodes = paragraph.findall(".//w:t", NS)
        if not text_nodes:
            continue
        text = "".join(node.text or "" for node in text_nodes)
        new_text = text
        for old, new in replacements.items():
            new_text = new_text.replace(old, new)
        if new_text != text:
            text_nodes[0].text = new_text
            for node in text_nodes[1:]:
                node.text = ""
            changed = True
    if changed:
        tree.write(doc_path, encoding="utf-8", xml_declaration=True)
    return changed


def find_docx_targets(docx_dir: Path) -> dict[str, list[str]]:
    doc = ET.parse(docx_dir / "word" / "document.xml")
    paragraphs = doc.findall(".//w:body/w:p", NS)
    targets = {"4.2": [], "4.3": []}
    for idx, para in enumerate(paragraphs):
        text = paragraph_text(para)
        fig = "4.2" if "图 4.2" in text or "图4.2" in text else "4.3" if "图 4.3" in text or "图4.3" in text else None
        if not fig:
            continue
        for prior in range(idx - 1, max(-1, idx - 8), -1):
            embeds = paragraph_embeds(paragraphs[prior])
            if embeds:
                targets[fig].extend(embeds)
                break
    return targets


def rewrite_docx_images(source_path: Path, output_path: Path, fig42: Path, fig43: Path) -> dict[str, list[str]]:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        with zipfile.ZipFile(source_path) as zf:
            zf.extractall(tmp)

        rels = rels_map(tmp)
        targets_by_fig = find_docx_targets(tmp)
        replaced: dict[str, list[str]] = {}
        for fig, source in [("4.2", fig42), ("4.3", fig43)]:
            replaced[fig] = []
            for rid in targets_by_fig.get(fig, []):
                target = rels.get(rid)
                if not target or not target.startswith("media/"):
                    continue
                dest = tmp / "word" / target
                shutil.copy2(source, dest)
                replaced[fig].append(target)
        text_changed = replace_docx_text(tmp)

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file in tmp.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(tmp).as_posix())

    replaced["text"] = ["updated"] if text_changed else []
    return replaced


def replace_docx_images(docx_path: Path, fig42: Path, fig43: Path) -> dict[str, object]:
    if not docx_path.exists():
        return {"status": "missing"}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = docx_path.with_suffix(f".kgfig_backup_{stamp}.docx")
    updated_copy = docx_path.with_name(f"{docx_path.stem}_知识图谱新版.docx")

    try:
        with open(docx_path, "r+b") as f:
            f.read(0)
    except PermissionError:
        replaced = rewrite_docx_images(docx_path, updated_copy, fig42, fig43)
        return {"status": "locked", "updated_copy": str(updated_copy), "replaced": replaced}

    shutil.copy2(docx_path, backup)
    with TemporaryDirectory() as td:
        temp_output = Path(td) / docx_path.name
        replaced = rewrite_docx_images(docx_path, temp_output, fig42, fig43)
        shutil.copy2(temp_output, docx_path)
    return {"status": "updated", "backup": str(backup), "replaced": replaced}


def main() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    fig42 = BUILD_DIR / "fig_4_2_kg_overview_final.png"
    fig43 = BUILD_DIR / "fig_4_3_kg_person_detail_final.png"

    make_pair(fig42, "知识图谱总图.png", "人物关联总图.png", "（a）知识图谱总图", "（b）人物关联总图")
    make_pair(fig43, "康有为周边人物.png", "黄飞鸿周边人物.png", "（a）康有为周边人物", "（b）黄飞鸿周边人物")

    copied: list[str] = []
    latest_media = THESIS_DIR / LATEST_MEDIA_DIR_NAME / "media"
    for target_dir in [latest_media, LATEX_FIG_DIR]:
        target_dir.mkdir(parents=True, exist_ok=True)
        for src, name in [(fig42, "fig_4_2_kg_overview_final.png"), (fig43, "fig_4_3_kg_person_detail_final.png")]:
            dest = target_dir / name
            shutil.copy2(src, dest)
            copied.append(str(dest))

    initial_media = THESIS_DIR / INITIAL_MEDIA_DIR_NAME / "media"
    if initial_media.exists():
        shutil.copy2(fig42, initial_media / "image4.png")
        copied.append(str(initial_media / "image4.png"))

    md_changes = {}
    md_changes[str(THESIS_DIR / LATEST_MD_NAME)] = replace_text(
        THESIS_DIR / LATEST_MD_NAME,
        {
            "图 4.2 汇总展示了知识图谱全局网络与人物关联总图。": "图 4.2 汇总展示了更新后的知识图谱全局网络与人物关联总图。",
            "图 4.3），用于说明典籍记忆如何通过人物、地点、技艺与事件向外扩展。": "图 4.3），用于说明典籍记忆如何通过人物、地点、技艺与事件向外扩展。",
        },
    )
    md_changes[str(THESIS_DIR / INITIAL_MD_NAME)] = replace_text(
        THESIS_DIR / INITIAL_MD_NAME,
        {
            "图 4.2 汇总展示了知识图谱全局网络与人物关联子图。": "图 4.2 汇总展示了更新后的知识图谱全局网络与人物关联总图。",
            "**图 4.2　知识图谱全局网络与典型人物子图**": "**图 4.2　知识图谱全局网络与人物关联总图**",
        },
    )

    docx_changes = {}
    for name in DOCX_NAMES:
        path = THESIS_DIR / name
        if path.exists():
            docx_changes[str(path)] = replace_docx_images(path, fig42, fig43)

    report = {
        "fig42": str(fig42),
        "fig43": str(fig43),
        "copied": copied,
        "md_changes": md_changes,
        "docx_changes": docx_changes,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
