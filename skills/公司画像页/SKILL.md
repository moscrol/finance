---
name: 公司画像页
metadata:
  pattern: generator
  also: [inversion, reviewer]
description: 投行风格公司画像页（PPT/Slide）。触发词：公司画像、画像页、strip profile、pitch book页面、公司概况幻灯片。
---
## 触发条件

用户要求为公司创建投行风格的概要画像页面、strip profile 或 pitch book 页面时触发。输出为 PPT/PDF 格式的高信息密度幻灯片。

## Workflow

### 1. Clarify Requirements
- **Ask the user**: Single-slide or multi-slide (3-4 slides)?
- **Ask the user**: Any specific focus areas or topics to emphasize?
- **Only after user confirms**, proceed to research

### 2. Research & Planning
**Data Sources:**
- **Primary**: Company filings (BamSEC, SEC EDGAR - "Item 1. Business", MD&A), investor presentations, corporate website
- **Market data**: Bloomberg, FactSet, CapIQ (price, shares, market cap, net debt, EV, ownership)
- **Estimates**: FactSet/CapIQ consensus for NTM revenue, EBITDA, EPS
- **News**: Press releases from last 90 days, M&A activity, guidance changes

**Required Metrics:**
- **Financials**: Revenue, EBITDA, margins (%), EPS, FCF for ±3 years
- **Valuation**: Market Cap, EV, EV/Revenue, EV/EBITDA, P/E multiples
- **Growth**: YoY growth rates (%)
- **Ownership**: Top 5 shareholders with % ownership
- **Segments**: Product mix and/or geographic mix (% breakdown)

**Normalization:**
- Convert all amounts to consistent currency
- Scale consistently ($mm or $bn throughout, not mixed)

**Before Building:**
- Print outline to chat with 4-5 bullet points per item (actual numbers, no placeholders)
- Print style choices: fonts, colors (hex codes), chart types for each data set
- Get user alignment: "Does this outline and visual strategy align with your vision?"

### 3. Slide-by-Slide Creation
**CRITICAL: You MUST create ONE slide at a time and get user approval before proceeding to the next slide.**

**For EACH slide:**
1. Create ONLY this one slide with PptxGenJS
2. **MANDATORY: Convert to image for review** - You MUST convert slides to images so you can visually verify them:
   ```bash
   soffice --headless --convert-to pdf presentation.pptx
   pdftoppm -jpeg -r 150 -f 1 -l 1 presentation.pdf slide
   ```
3. **MANDATORY VISUAL REVIEW**: You MUST carefully examine the rendered slide image before proceeding:
   - **Text overlap check**: Scan every text element - do any labels, bullets, or titles collide with each other?
   - **Text cutoff check**: Is any text truncated at boundaries? Are all words fully visible?
   - **Chart boundary check**: Do charts stay within their containers? Are ALL axis labels fully visible?
   - **Quadrant integrity**: Does content in one quadrant bleed into adjacent quadrants?
4. **If ANY overlap or cutoff is detected**: Fix immediately using these strategies in order:
   - **First**: Reduce font size (go down 1-2pt)
   - **Second**: Shorten text (abbreviate, remove less critical info)
   - **Third**: Adjust element positions or container sizes
   - **Re-render and verify again** - do not proceed until all text fits cleanly
5. Show slide image to user with download link
6. **STOP and wait for explicit user approval** before creating the next slide. Do NOT proceed until user confirms.

**YOU MUST CHECK FOR THESE SPECIFIC ISSUES ON EVERY PAGE:**
- Table rows colliding with text below them
- Chart x-axis labels cut off at bottom
- Long bullet points wrapping into adjacent content
- Quadrant content bleeding into adjacent quadrants
- Title text overlapping with content below
- Legend text overlapping with chart elements
- Footer/source text colliding with main content

---

## Slide Format Requirements

幻灯片格式硬要求（信息密度目标、每象限填充量、单 textbox 行距代码、bullet 格式、品牌色/字体规范、示例 PPTX 参考）见 `references/slide-format-requirements.md`。建页前加载并逐条对照。

---

## First Page Layout

首页四象限布局规范（4:3 画布坐标系、象限定位表、精确字号表、accent bar 代码、首页格式细则）见 `references/first-page-layout.md`。排第一页前按该坐标与字号落位。

---

## Subsequent Pages: Free-Form Layouts

- Two-column (40/60 or 50/50), full-slide charts, or sidebar layouts
- Each page elaborates on first page content
- Maintain consistent typography and color scheme
- Suggested flow: Products/Market → Financial Analysis → Leadership

---

## Charts (Multi-Slide Profiles)

多页画像的图表规范（数据类型→图表类型映射表 + 横向条形/饼图/折线的 PptxGenJS 代码示例）见 `references/charts.md`。

---

## Financial Data Formatting

财务数据排版规范（必须用原生 PptxGenJS 表格/图表、`addTable()` 代码示例、Bear/Base/Bull 情景表、禁用纯文本/HTML 表格）见 `references/financial-data-formatting.md`。

---

## Quality Checklist

出片前自检清单（首页项 + 全部幻灯片项：无溢出/截断、字体颜色一致、图表正确、无占位、口径一致、注明来源、IB 质量）见 `references/quality-checklist.md`，逐项过。
