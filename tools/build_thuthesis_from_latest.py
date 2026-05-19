from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_MD = ROOT / "docs" / "thesis_02" / "基于大数据的佛山市南海区旅游景区文旅融合潜力研究_md转化版.md"
TEMPLATE = ROOT / "docs" / "thuthesis-master"
BUILD_DIR = TEMPLATE / ".ms_build"
DATA_DIR = TEMPLATE / "data"
FIG_DST = TEMPLATE / "figures" / "ms_thesis"
MEDIA_DIR = SRC_MD.parent / "基于大数据的佛山市南海区旅游景区文旅融合潜力研究_md转化版_media" / "media"


def run(cmd: list[str], cwd: Path = TEMPLATE) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def strip_span(text: str) -> str:
    text = re.sub(r"<span[^>]*></span>", "", text)
    text = text.replace("<!-- -->", "")
    return text


def clean_heading(line: str) -> str:
    m = re.match(r"^(#{1,6})\s*(.+?)\s*$", line)
    if not m:
        return line
    hashes, title = m.groups()
    title = title.strip()
    if title.startswith("**") and title.endswith("**"):
        title = title[2:-2].strip()
    if len(hashes) > 1:
        title = re.sub(r"^\d+(?:\.\d+)*\s+", "", title)
    title = re.sub(r"^第\s*\d+\s*章\s*", "", title)
    return f"{hashes} {title}"


def normalize_markdown(text: str) -> str:
    text = strip_span(text)
    text = re.sub(r"```[ \t]*math\s*\n(.*?)\n```", r"$$\n\1\n$$", text, flags=re.S)
    text = text.replace("<figure>", "").replace("</figure>", "")
    text = re.sub(
        r"<figcaption><p><strong>(.*?)</strong></p></figcaption>",
        r"**\1**",
        text,
    )
    text = re.sub(r"([A-Za-z])<sub>(.*?)</sub>", r"$\1_{\2}$", text)
    text = re.sub(r"V<sub>(.*?)</sub>", r"$V_{\1}$", text)
    text = re.sub(r"R<sub>(.*?)</sub>", r"$R_{\1}$", text)
    text = re.sub(r"N<sub>(.*?)</sub>", r"$N_{\1}$", text)

    src_prefix = "基于大数据的佛山市南海区旅游景区文旅融合潜力研究_md转化版_media/media/"
    text = text.replace(src_prefix, "ms_thesis/")
    text = re.sub(r"\n(#{1,6}\s)", r"\n\n\1", text)

    lines = text.splitlines()
    out: list[str] = []
    i = 0
    image_re = re.compile(r"^!\[(.*?)\]\((.*?)\)(\{.*\})?\s*$")
    caption_re = re.compile(r"^\*\*(图\s*\d+(?:\.\d+)?[^\*]*)\*\*$|^(图\s*\d+(?:\.\d+)?\s*[^\n]*)$")
    while i < len(lines):
        line = lines[i]
        if line.startswith("### **实践意义：**"):
            out.append(line[4:])
            i += 1
            continue
        line = clean_heading(line)
        m = image_re.match(line)
        if m:
            alt, path, attrs = m.groups()
            attrs = attrs or ""
            j = i + 1
            blanks: list[str] = []
            while j < len(lines) and not lines[j].strip():
                blanks.append(lines[j])
                j += 1
            cap = caption_re.match(lines[j].strip()) if j < len(lines) else None
            if cap:
                caption = (cap.group(1) or cap.group(2)).strip()
                out.append(f"![{caption}]({path}){attrs}")
                i = j + 1
                continue
            out.append(line)
            i += 1
            continue
        out.append(line)
        i += 1

    return "\n".join(out).strip() + "\n"


def pandoc_fragment(md_text: str, out_tex: Path) -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    tmp_md = BUILD_DIR / (out_tex.stem + ".md")
    write(tmp_md, md_text)
    run(
        [
            "pandoc",
            "-f",
            "markdown+pipe_tables+fenced_code_blocks+tex_math_dollars+link_attributes+implicit_figures",
            "-t",
            "latex",
            "--top-level-division=chapter",
            "--wrap=none",
            "-o",
            str(out_tex),
            str(tmp_md),
        ]
    )
    postprocess_latex(out_tex)


def replace_table_block(text: str, title: str, replacement: str) -> str:
    pattern = (
        re.escape(title)
        + r"\n\n\{\\def\\LTcaptype\{none\} % do not increment counter\n"
        + r"\\begin\{longtable\}.*?\\end\{longtable\}\n\}\n"
    )
    new_text, count = re.subn(
        pattern,
        lambda _match: replacement.rstrip() + "\n",
        text,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"Cannot replace table block: {title}")
    return new_text


def fix_chap04_layout(text: str) -> str:
    figure_block = r"""
\begin{figure}[p]
\centering
\begin{minipage}[t]{0.48\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.24\textheight,keepaspectratio]{ms_thesis/fig_4_2a_kg_global.png}
\caption{知识图谱全局网络}
\end{minipage}\hfill
\begin{minipage}[t]{0.48\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.24\textheight,keepaspectratio]{ms_thesis/fig_4_2b_person_network.png}
\caption{人物关联总图}
\end{minipage}

\vspace{0.6em}

\centering
\includegraphics[width=\textwidth]{ms_thesis/fig_4_3b_huang_feihong.png}
\caption{黄飞鸿周边人物子图}
\end{figure}
"""
    pattern = (
        r"\\begin\{figure\}\s*\\centering\s*"
        r"\\includegraphics\[[^\]]+\]\{ms_thesis/fig_4_2a_kg_global\.png\}\s*"
        r"\\caption\{知识图谱全局网络\}\s*\\end\{figure\}\s*"
        r"\\begin\{figure\}\s*\\centering\s*"
        r"\\includegraphics\[[^\]]+\]\{ms_thesis/fig_4_2b_person_network\.png\}\s*"
        r"\\caption\{人物关联总图\}\s*\\end\{figure\}\s*"
        r"(?:"
        r"\\begin\{figure\}\s*\\centering\s*"
        r"\\includegraphics\[[^\]]+\]\{ms_thesis/fig_4_3a_kang_youwei\.png\}\s*"
        r"\\caption\{康有为周边人物子图\}\s*\\end\{figure\}\s*"
        r")?"
        r"\\begin\{figure\}\s*\\centering\s*"
        r"\\includegraphics\[[^\]]+\]\{ms_thesis/fig_4_3b_huang_feihong\.png\}\s*"
        r"\\caption\{黄飞鸿周边人物子图\}\s*\\end\{figure\}"
    )
    text, count = re.subn(pattern, lambda _match: figure_block.rstrip(), text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Cannot replace chapter 4 knowledge-graph figures")
    return text


def fix_chap05_layout(text: str) -> str:
    table_51 = r"""
\begin{table}[H]
\centering
\noindent\textbf{表 5.1　13,512 条 POI 按 11 大类的构成}\par\vspace{0.35em}
\begin{center}
{\scriptsize
\setlength{\tabcolsep}{2.5pt}
\renewcommand{\arraystretch}{1.12}
\resizebox{\textwidth}{!}{%
\begin{tabular}{@{}lrrrrrrrrrrrr@{}}
\toprule
\textbf{指标} & \textbf{公园绿地} & \textbf{自然景观} & \textbf{其他} & \textbf{宗教场所} & \textbf{人文古迹} & \textbf{文化场馆} & \textbf{休闲娱乐} & \textbf{体育设施} & \textbf{非遗体验} & \textbf{教育研学} & \textbf{特色街区} & \textbf{合计} \\
\midrule
数量 & 5,441 & 4,123 & 2,018 & 481 & 420 & 318 & 242 & 175 & 137 & 104 & 53 & 13,512 \\
占比 & 40.3\% & 30.5\% & 14.9\% & 3.6\% & 3.1\% & 2.4\% & 1.8\% & 1.3\% & 1.0\% & 0.8\% & 0.4\% & 100\% \\
\bottomrule
\end{tabular}
}
}
\end{center}
\end{table}
"""
    pattern = (
        r"\\textbf\{表 5\.1　13,512 条 POI 按 11 大类的构成\}\n\n"
        + r"\{\\def\\LTcaptype\{none\} % do not increment counter\n"
        + r"\\begin\{longtable\}.*?\\end\{longtable\}\n\}\n"
    )
    text, count = re.subn(pattern, lambda _match: table_51.rstrip() + "\n", text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Cannot replace table block: 表 5.1")
    return text


def fix_chap06_layout(text: str) -> str:
    table_68 = r"""
\noindent\textbf{表 6.8　镇街典籍---官方---旅游诊断拆分摘要}\par\vspace{0.35em}
\begin{center}
{\small
\setlength{\tabcolsep}{4pt}
\renewcommand{\arraystretch}{1.15}
\begin{tabularx}{\textwidth}{>{\raggedright\arraybackslash}p{0.14\textwidth}
>{\centering\arraybackslash}p{0.15\textwidth}
>{\centering\arraybackslash}p{0.15\textwidth}
>{\centering\arraybackslash}p{0.15\textwidth}
>{\centering\arraybackslash}p{0.16\textwidth}
>{\centering\arraybackslash}X}
\toprule
\textbf{镇街} & \textbf{\makecell{C 典籍/\\图谱均值}} & \textbf{\makecell{O 官方资源\\均值}} & \textbf{\makecell{T 旅游热度\\均值}} & \textbf{\makecell{修正错位\\均值}} & \textbf{\makecell{官方覆盖\\网格}} \\
\midrule
桂城街道 & 2.15 & 2.60 & 22.28 & 19.95 & 40 \\
大沥镇 & 1.73 & 4.01 & 17.18 & 14.54 & 67 \\
里水镇 & 0.37 & 2.09 & 7.59 & 6.53 & 54 \\
狮山镇 & 0.32 & 1.36 & 5.72 & 4.98 & 86 \\
丹灶镇 & 4.36 & 1.84 & 5.07 & 1.71 & 44 \\
西樵镇 & 11.78 & 18.29 & 6.55 & −7.83 & 715 \\
九江镇 & 6.17 & 2.46 & 5.70 & 1.01 & 35 \\
\bottomrule
\end{tabularx}
}
\end{center}
"""

    table_69 = r"""
\begin{table}[H]
\centering
\noindent\textbf{表 6.9　权重敏感性检验结果}\par\vspace{0.35em}
{\scriptsize
\setlength{\tabcolsep}{2.2pt}
\renewcommand{\arraystretch}{1.12}
\begin{tabularx}{\textwidth}{@{}>{\raggedright\arraybackslash}p{0.12\textwidth}
>{\raggedright\arraybackslash}X
>{\centering\arraybackslash}p{0.07\textwidth}
>{\centering\arraybackslash}p{0.07\textwidth}
>{\centering\arraybackslash}p{0.07\textwidth}
>{\centering\arraybackslash}p{0.07\textwidth}
>{\centering\arraybackslash}p{0.09\textwidth}@{}}
\toprule
\textbf{口径} & \textbf{权重设置} & \textbf{\makecell{核心\\耦合区}} & \textbf{\makecell{一般\\耦合区}} & \textbf{\makecell{沉睡\\潜力区}} & \textbf{\makecell{空心\\景点区}} & \textbf{\makecell{与基准\\一致比例}} \\
\midrule
基准口径 & CMI/OAI=0.5/0.5；THI=POI 0.4 + 评分 0.2 + 评论 0.4 & 5 & 57 & 54 & 49 & 100.0\% \\
文化侧加权 & CMI/OAI=0.7/0.3 & 5 & 45 & 59 & 56 & 89.7\% \\
官方侧加权 & CMI/OAI=0.3/0.7 & 5 & 70 & 49 & 41 & 90.9\% \\
POI 导向 THI & THI=POI 0.5 + 评分 0.2 + 评论 0.3 & 4 & 59 & 53 & 49 & 97.0\% \\
评论导向 THI & THI=POI 0.3 + 评分 0.2 + 评论 0.5 & 5 & 59 & 53 & 48 & 98.8\% \\
\bottomrule
\end{tabularx}
}
\end{table}
"""

    table_610 = r"""
\begin{table}[H]
\centering
\noindent\textbf{表 6.10　重点载体评论文化识别度抽样结果}\par\vspace{0.35em}
{\scriptsize
\setlength{\tabcolsep}{2.0pt}
\renewcommand{\arraystretch}{1.10}
\begin{tabularx}{\textwidth}{@{}>{\raggedright\arraybackslash}p{0.18\textwidth}
>{\centering\arraybackslash}p{0.08\textwidth}
>{\centering\arraybackslash}p{0.10\textwidth}
>{\centering\arraybackslash}p{0.055\textwidth}
>{\centering\arraybackslash}p{0.08\textwidth}
>{\centering\arraybackslash}p{0.08\textwidth}
>{\raggedright\arraybackslash}X@{}}
\toprule
\textbf{载体} & \textbf{镇街} & \textbf{分区} & \textbf{\makecell{评论\\数}} & \textbf{\makecell{文化关键词\\评论数}} & \textbf{\makecell{文化识别\\比例}} & \textbf{高频关键词} \\
\midrule
湖山胜迹门楼 & 西樵镇 & 空心景点区 & 88 & 31 & 35.2\% & 西樵山、庙、黄飞鸿、醒狮、南海、历史 \\
云泉仙馆 & 西樵镇 & 核心耦合区 & 87 & 30 & 34.5\% & 西樵山、庙、黄飞鸿、醒狮、南海、历史 \\
小云亭 & 西樵镇 & 空心景点区 & 86 & 29 & 33.7\% & 西樵山、庙、黄飞鸿、醒狮、南海、历史 \\
光分亭 & 西樵镇 & 空心景点区 & 42 & 28 & 66.7\% & 西樵山、文化、庙、道教、南海、历史 \\
象林塔 & 西樵镇 & 空心景点区 & 41 & 28 & 68.3\% & 西樵山、文化、庙、道教、南海、历史 \\
南海农谣 & 桂城街道 & 空心景点区 & 36 & 25 & 69.4\% & 博物馆、岭南、南海、文化、展览、文物 \\
平洲传统玉器制作技艺 & 桂城街道 & 核心耦合区 & 21 & 8 & 38.1\% & 文化、玉器、平洲玉器、博物馆、展览、历史 \\
九江吴家大院 & 九江镇 & 核心耦合区 & 20 & 6 & 30.0\% & 吴家大院、南海、历史、展览、博物馆、文化 \\
西樵山百步云梯 & 西樵镇 & 核心耦合区 & 12 & 5 & 41.7\% & 西樵山、历史、文化、岭南、康有为、黄飞鸿 \\
西樵山抗日阵亡将士暨死难同胞纪念碑 & 西樵镇 & 核心耦合区 & 11 & 4 & 36.4\% & 西樵山、历史、文化、岭南、康有为、黄飞鸿 \\
\bottomrule
\end{tabularx}
}
\end{table}
"""

    text = replace_table_block(text, "表 6.8　镇街典籍---官方---旅游诊断拆分摘要", table_68)
    text = replace_table_block(text, "表 6.9　权重敏感性检验结果", table_69)
    text = replace_table_block(text, "表 6.10　重点载体评论文化识别度抽样结果", table_610)
    text = re.sub(
        r"\\begin\{figure\}\s*\\centering\s*\\includegraphics\[[^\]]+\]\{ms_thesis/image19\.png\}\s*\\caption\{典籍---官方---旅游诊断拆分图\}\s*\\end\{figure\}",
        lambda _match: (
            "\\begin{figure}[H]\n"
            "\\centering\n"
            "\\includegraphics[width=\\textwidth,height=0.42\\textheight,keepaspectratio]{ms_thesis/image19.png}\n"
            "\\caption{典籍---官方---旅游诊断拆分图}\n"
            "\\end{figure}"
        ),
        text,
        count=1,
        flags=re.S,
    )
    return text


def postprocess_latex(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r",alt=\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", text)
    text = re.sub(r"\\hyperref\[_Ref\d+\]\{\{\[\}([^{}]+)\{\]\}\}", r"[\1]", text)
    text = re.sub(r"\\caption\{图\s*\d+(?:\.\d+)?[　 \t]*(.*?)\}", r"\\caption{\1}", text)
    if path.name == "ms-chap04.tex":
        text = fix_chap04_layout(text)
    if path.name == "ms-chap05.tex":
        text = fix_chap05_layout(text)
    if path.name == "ms-chap06.tex":
        text = fix_chap06_layout(text)
    path.write_text(text, encoding="utf-8", newline="\n")


def md_to_latex(md_text: str) -> str:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    tmp_md = BUILD_DIR / "inline.md"
    tmp_tex = BUILD_DIR / "inline.tex"
    write(tmp_md, md_text)
    run(
        [
            "pandoc",
            "-f",
            "markdown+pipe_tables+fenced_code_blocks+tex_math_dollars+link_attributes+implicit_figures",
            "-t",
            "latex",
            "--wrap=none",
            "-o",
            str(tmp_tex),
            str(tmp_md),
        ]
    )
    return tmp_tex.read_text(encoding="utf-8").strip()


def extract_sections(lines: list[str]) -> dict[str, int]:
    def find(pattern: str, start: int = 0) -> int:
        for idx in range(start, len(lines)):
            line = lines[idx]
            if re.search(pattern, line):
                return idx
        raise RuntimeError(f"Cannot find {pattern}")

    body = find(r"^#\s+\*\*引言\*\*|^#\s+引言")
    refs = find(r"参考文献", body)
    appendix = find(r"_Toc10557.*实体分类体系简表|实体分类体系简表", refs)
    ack = find(r"_Toc14705.*致 谢|^致 谢$", appendix)
    statement = find(r"_Toc180656789.*声 明|^声 明$", ack)
    return {
        "abstract": find(r"^摘 要\s*$"),
        "keywords": find(r"^关键词："),
        "abstract_en": find(r"^Abstract\s*$"),
        "keywords_en": find(r"^(?:\*\*)?Keywords:(?:\*\*)?"),
        "body": body,
        "refs": refs,
        "appendix": appendix,
        "ack": ack,
        "statement": statement,
    }


def split_chapters(body: str) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        if line.startswith("# ") and current:
            chunks.append("\n".join(current).strip() + "\n")
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current).strip() + "\n")
    return chunks


def latex_escape(text: str) -> str:
    text = text.replace("\\[", "[").replace("\\]", "]")
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def clean_keyword_value(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^\*+\s*", "", text)
    text = re.sub(r"\s*\*+$", "", text)
    text = text.replace("；", ",").replace(";", ",")
    return re.sub(r"\s*,\s*", ", ", text.strip())


def escape_with_urls(text: str) -> str:
    parts = re.split(r"(https?://[^\s]+)", text)
    out: list[str] = []
    for part in parts:
        if part.startswith("http://") or part.startswith("https://"):
            trailing = ""
            while part and part[-1] in ".,;":
                trailing = part[-1] + trailing
                part = part[:-1]
            out.append(r"\url{" + part + "}" + latex_escape(trailing))
        else:
            out.append(latex_escape(part))
    return "".join(out)


def build_references(refs_md: str) -> str:
    refs_md = strip_span(refs_md)
    lines = [line.strip() for line in refs_md.splitlines() if line.strip()]
    items: list[str] = []
    for line in lines:
        m = re.match(r"^\d+\.\s*(.+)$", line)
        if not m:
            continue
        item = m.group(1)
        item = item.replace("\\[", "[").replace("\\]", "]")
        item = escape_with_urls(item)
        items.append(item)
    body = "\n\n".join(f"  \\bibitem{{ref{i}}} {item}" for i, item in enumerate(items, 1))
    return (
        "% !TEX root = ../ms-thesis.tex\n\n"
        "\\begin{thebibliography}{99}\n"
        f"{body}\n"
        "\\end{thebibliography}\n"
    )


def build_appendix(app_md: str) -> str:
    app_md = strip_span(app_md)
    app_md = re.sub(r"^\s*1\.\s*实体分类体系简表\s*$", "# 实体分类体系简表", app_md, flags=re.M)
    app_md = re.sub(r"^\s*2\.\s*165 条文化载体样本分类与镇街分布统计\s*$", "# 165 条文化载体样本分类与镇街分布统计", app_md, flags=re.M)
    app_md = re.sub(r"^\s*3\.\s*载体级指数与错位分类样例\s*$", "# 载体级指数与错位分类样例", app_md, flags=re.M)
    app_md = re.sub(r"^\s*4\.\s*潜力释放条件相关矩阵\s*$", "# 潜力释放条件相关矩阵", app_md, flags=re.M)
    return normalize_markdown(app_md)


def main() -> None:
    text = SRC_MD.read_text(encoding="utf-8")
    lines = text.splitlines()
    idx = extract_sections(lines)

    cn_abs = "\n".join(lines[idx["abstract"] + 1 : idx["keywords"]]).strip()
    cn_keywords = clean_keyword_value(lines[idx["keywords"]].split("：", 1)[1])
    en_abs = "\n".join(lines[idx["abstract_en"] + 1 : idx["keywords_en"]]).strip()
    en_keywords = clean_keyword_value(lines[idx["keywords_en"]].split(":", 1)[1])

    body = "\n".join(lines[idx["body"] : idx["refs"]])
    refs = "\n".join(lines[idx["refs"] + 1 : idx["appendix"]])
    appendix = "\n".join(lines[idx["appendix"] : idx["ack"]])
    ack = "\n".join(lines[idx["ack"] + 1 : idx["statement"]]).strip()

    FIG_DST.mkdir(parents=True, exist_ok=True)
    for image in MEDIA_DIR.glob("*"):
        if image.is_file():
            shutil.copy2(image, FIG_DST / image.name)

    abstract_tex = (
        "% !TEX root = ../ms-thesis.tex\n\n"
        "\\begin{abstract}\n"
        f"{md_to_latex(cn_abs)}\n\n"
        "\\thusetup{\n"
        f"  keywords = {{{cn_keywords}}},\n"
        "}\n"
        "\\end{abstract}\n\n"
        "\\begin{abstract*}\n"
        f"{md_to_latex(en_abs)}\n\n"
        "\\thusetup{\n"
        f"  keywords* = {{{en_keywords}}},\n"
        "}\n"
        "\\end{abstract*}\n"
    )
    write(DATA_DIR / "ms-abstract.tex", abstract_tex)

    body_clean = normalize_markdown(body)
    for n, chapter in enumerate(split_chapters(body_clean), 1):
        pandoc_fragment(chapter, DATA_DIR / f"ms-chap{n:02d}.tex")

    pandoc_fragment(build_appendix(appendix), DATA_DIR / "ms-appendix.tex")
    write(DATA_DIR / "ms-references.tex", build_references(refs))

    ack_tex = (
        "% !TEX root = ../ms-thesis.tex\n\n"
        "\\begin{acknowledgements}\n"
        f"{md_to_latex(ack)}\n"
        "\\end{acknowledgements}\n"
    )
    write(DATA_DIR / "ms-acknowledgements.tex", ack_tex)

    write(
        DATA_DIR / "ms-denotation.tex",
        "% !TEX root = ../ms-thesis.tex\n\n"
        "\\begin{denotation}[4cm]\n"
        "  \\item[CMI] 文化记忆指数（Cultural Memory Index）\n"
        "  \\item[OAI] 官方认证指数（Official Accreditation Index）\n"
        "  \\item[THI] 旅游热度指数（Tourism Heat Index）\n"
        "  \\item[MI] 文化—旅游错位指数（Mismatch Index）\n"
        "  \\item[POI] 兴趣点（Point of Interest）\n"
        "  \\item[KDE] 核密度估计（Kernel Density Estimation）\n"
        "  \\item[DBSCAN] 基于密度的空间聚类算法\n"
        "  \\item[OCR] 光学字符识别（Optical Character Recognition）\n"
        "\\end{denotation}\n",
    )

    write(
        DATA_DIR / "ms-record.tex",
        "% !TEX root = ../ms-thesis.tex\n\n"
        "\\chapter*{综合论文训练记录表}\n"
        "\\addcontentsline{toc}{chapter}{综合论文训练记录表}\n"
        "\\begin{center}\n"
        "\\begin{tabular}{|p{0.14\\textwidth}|p{0.18\\textwidth}|p{0.10\\textwidth}|p{0.22\\textwidth}|p{0.10\\textwidth}|p{0.14\\textwidth}|}\n"
        "\\hline\n"
        "学生姓名 & & 学号 & & 班级 & \\\\ \\hline\n"
        "论文题目 & \\multicolumn{5}{p{0.74\\textwidth}|}{基于多源数据的佛山市南海区旅游景区文旅融合潜力研究} \\\\ \\hline\n"
        "主要内容以及进度安排 & \\multicolumn{5}{p{0.74\\textwidth}|}{\\vspace{3cm}\\raggedleft 指导教师签字：\\\\考核组组长签字：\\\\年\\quad 月\\quad 日} \\\\ \\hline\n"
        "中期考核意见 & \\multicolumn{5}{p{0.74\\textwidth}|}{\\vspace{3cm}\\raggedleft 考核组组长签字：\\\\年\\quad 月\\quad 日} \\\\ \\hline\n"
        "指导教师评语 & \\multicolumn{5}{p{0.74\\textwidth}|}{\\vspace{3cm}\\raggedleft 指导教师签字：\\\\年\\quad 月\\quad 日} \\\\ \\hline\n"
        "评阅教师评语 & \\multicolumn{5}{p{0.74\\textwidth}|}{\\vspace{3cm}\\raggedleft 评阅教师签字：\\\\年\\quad 月\\quad 日} \\\\ \\hline\n"
        "答辩小组评语 & \\multicolumn{5}{p{0.74\\textwidth}|}{\\vspace{3cm}\\raggedleft 答辩小组组长签字：\\\\年\\quad 月\\quad 日} \\\\ \\hline\n"
        "\\end{tabular}\n"
        "\\end{center}\n\n"
        "\\vspace{1em}\n"
        "\\noindent\\textbf{总成绩：}\\par\n"
        "\\vspace{2em}\n"
        "\\noindent\\textbf{教学负责人签字：}\\par\n"
        "\\vspace{2em}\n"
        "\\noindent\\textbf{年\\quad 月\\quad 日}\n",
    )
    record_path = DATA_DIR / "ms-record.tex"
    if record_path.exists():
        record_path.unlink()

    write(
        TEMPLATE / "ms-thusetup.tex",
        "% !TEX root = ./ms-thesis.tex\n\n"
        "\\thusetup{\n"
        "  output = electronic,\n"
        "  title = {基于多源数据的佛山市南海区旅游景区文旅融合潜力研究},\n"
        "  title* = {A Study on the Potential of Culture--Tourism Integration in Tourist Attractions of Nanhai District, Foshan Based on Multi-source Data},\n"
        "  department = {建筑学院景观学系},\n"
        "  discipline = {风景园林},\n"
        "  discipline* = {Landscape Architecture},\n"
        "  author = {孟帅},\n"
        "  author* = {Meng Shuai},\n"
        "  supervisor = {邬东璠, 副教授},\n"
        "  supervisor* = {Associate Professor Wu Dongfan},\n"
        "  date = {2026-06-01},\n"
        "  include-spine = false,\n"
        "}\n\n"
        "\\usepackage{amsmath}\n"
        "\\usepackage{booktabs}\n"
        "\\usepackage{longtable}\n"
        "\\usepackage{array}\n"
        "\\usepackage{calc}\n"
        "\\newcounter{none}\n"
        "\\usepackage{float}\n"
        "\\usepackage{threeparttable}\n"
        "\\usepackage{multirow}\n"
        "\\usepackage{tabularx}\n"
        "\\usepackage{makecell}\n"
        "\\usepackage{needspace}\n"
        "\\usepackage[sort]{natbib}\n"
        "\\bibliographystyle{thuthesis-bachelor}\n"
        "\\citestyle{thuthesis-bachelor}\n"
        "\\graphicspath{{figures/}{figures/ms_thesis/}}\n"
        "\\providecommand{\\tightlist}{\\setlength{\\itemsep}{0pt}\\setlength{\\parskip}{0pt}}\n"
        "\\usepackage{hyperref}\n",
    )

    chapter_inputs = "\n".join(f"\\input{{data/ms-chap{n:02d}}}" for n in range(1, len(split_chapters(body_clean)) + 1))
    write(
        TEMPLATE / "ms-thesis.tex",
        "% !TEX encoding = UTF-8\n"
        "% !TEX program = xelatex\n\n"
        "\\documentclass[degree=bachelor, fontset=windows]{thuthesis}\n\n"
        "\\input{ms-thusetup}\n\n"
        "\\begin{document}\n\n"
        "\\maketitle\n"
        "\\copyrightpage\n\n"
        "\\frontmatter\n"
        "\\input{data/ms-abstract}\n"
        "\\tableofcontents\n"
        "\\listoffigures\n"
        "\\listoftables\n"
        "\\input{data/ms-denotation}\n\n"
        "\\mainmatter\n"
        f"{chapter_inputs}\n\n"
        "\\input{data/ms-references}\n\n"
        "\\appendix\n"
        "\\input{data/ms-appendix}\n\n"
        "\\backmatter\n"
        "\\input{data/ms-acknowledgements}\n"
        "\\statement\n"
        "\\end{document}\n",
    )

    print(f"Wrote LaTeX thesis to {TEMPLATE / 'ms-thesis.tex'}")
    print(f"Copied figures to {FIG_DST}")


if __name__ == "__main__":
    main()
