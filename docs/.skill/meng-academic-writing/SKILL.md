---
name: meng-academic-writing
description: Chinese academic writing and revision in Meng Shuai's prior-paper style, with special support for source-grounded undergraduate thesis and graduation-design writing. Use when Codex is asked to draft, rewrite, polish, expand, summarize, outline, or continue Chinese thesis/paper sections in the user's established style, especially architecture, landscape, cultural-tourism, rural studies, history, design evaluation, literature review, problem analysis, case analysis, abstract, conclusion, and undergraduate graduation thesis writing. Also use when the user asks to reduce machine-like phrasing, make prose sound closer to their own previous papers, combine reference literature or project evidence, or keep rigorous academic expression without over-polishing.
---

# Meng Academic Writing

## Core Rule

Write in a style that is close to the user's previous Chinese coursework papers: direct, explanatory, problem-oriented, and moderately formal. Preserve academic rigor, source discipline, and logical clarity. Do not promise to bypass AI detection; treat requests about "AI rate" as requests to reduce templated, generic, machine-like wording and strengthen the user's own writing texture.

Read `references/style-profile.md` when doing substantial drafting, rewriting a full section, or making a style-sensitive revision.

For undergraduate thesis or graduation-design tasks, also read `references/undergraduate-thesis-rigor.md`. Treat the user's current thesis draft, school template, literature list, and data tables as higher-priority evidence than the prior-paper style profile.

## Workflow

1. Identify the writing task: abstract, introduction/problem statement, literature review, case analysis, mechanism analysis, conclusion, or revision/polishing.
2. Gather task-local evidence before drafting:
   - Read the current thesis section or outline if a file/path is available.
   - Read relevant reference literature summaries, PDFs, data tables, or requirement files before making factual claims.
   - If writing inside `C:\Users\ms\Desktop\ms_thesis`, follow the local source hierarchy in `references/undergraduate-thesis-rigor.md`.
3. Build a simple argument path before drafting: background -> problem -> reason/mechanism -> evidence/case -> judgment -> conclusion.
4. Draft with the user's preferred structure:
   - Use numbered headings such as `一．摘要`, `二．问题提出`, `三．文献综述`, `四．实例分析`, `五．结论` when the task is a paper or coursework essay.
   - For the current undergraduate thesis, prefer the school thesis chapter structure: `第 1 章 引言`, `第 2 章 文献综述与相关研究述评`, `第 3 章 研究区域与数据基础`, `第 4 章 ...`, through conclusion, references, appendices, and acknowledgements.
   - Use `摘要` and `关键词` for formal paper-like outputs when appropriate.
   - Let each section begin from a broad background or concrete phenomenon, then narrow into the specific research question.
5. Apply the style pass:
   - Prefer plain explanatory phrasing over highly polished, slogan-like prose.
   - Use the user's common connectors naturally: `对于`, `通过`, `可以`, `我们可以看到/发现`, `并且`, `但是`, `这一`, `这种`, `相关`, `问题`, `机制`.
   - Use medium-long sentences with clear causal or progressive relations; intersperse occasional shorter judgment sentences.
   - Keep a measured first-person plural voice when suitable: `我们可以看到`, `我们需要`, `我们已经明白`.
6. Apply the rigor pass:
   - Do not fabricate citations, data, quotations, authors, years, or policy details.
   - If evidence is needed but not provided, mark it as `[待补充文献/数据]` or ask for sources.
   - Tighten claims with scope markers such as `在一定程度上`, `从目前材料来看`, `可以认为`, `并不意味着`.
   - Distinguish source-backed facts, analysis based on computed results, and planning recommendations.
   - Remove obvious typos, duplicated words, and overly casual expressions while keeping the user's direct rhythm.

## Section Patterns

### Abstract

Use a compact chain: field/background -> existing problem -> object/method -> main finding -> significance. The abstract may be one dense paragraph. Avoid overly decorative openings.

### Problem Statement

Start from a larger historical, social, disciplinary, or technical background. Then state the contradiction or inadequacy in the current situation. End by explaining why the topic is worth discussing.

### Literature Review

Summarize prior work plainly: who studied what, what contribution it made, and what gap remains. Do not turn the review into a list of empty praise. If references are missing, use placeholders rather than inventing them.

For undergraduate thesis work, every literature-review subsection should end with a short "研究述评" movement: summarize what the references have already solved, identify what remains insufficient for the user's object/scale/method, then state how this thesis responds.

### Analysis

Use a cause-and-effect sequence. The user's papers often explain why a problem appears, what mechanism sustains it, and how a solution may form a positive or negative feedback loop. Make this chain explicit.

### Case Discussion

Introduce the case with basic context, then explain its process, spatial/social mechanism, or design logic. Tie the case back to the central problem instead of leaving it as narrative description.

### Conclusion

Restate what has been clarified through the analysis, then give a modest judgment or implication. It is acceptable to end with a slightly stronger rhetorical sentence, but keep it academically restrained for thesis writing.

For thesis conclusions, pair each finding with its evidence basis: data table, figure, chapter analysis, or cited literature. Avoid adding new arguments in the conclusion.

## Revision Priorities

When polishing existing text, preserve the user's original order and intention unless the logic is unclear. Improve in this order:

1. Fix factual uncertainty and missing evidence markers.
2. Repair sentence logic and transitions.
3. Make wording closer to the user's direct academic voice.
4. Smooth grammar and punctuation.
5. Avoid excessive refinement that makes the prose sound generic or detached from the user's style.

## Avoid

- Do not imitate accidental mistakes from old papers.
- Do not overuse ornate four-character phrases, marketing-style claims, or formulaic AI transitions.
- Do not make every paragraph end with a grand conclusion.
- Do not replace all direct expressions with abstract nouns.
- Do not hide uncertainty. Use careful qualification when evidence is incomplete.
- Do not use old papers as factual evidence for the current thesis; use them only as style evidence.
