# 公司画像页 幻灯片格式要求

> 本文件由 `skills/公司画像页/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

### Information Density is Critical

**The #1 goal is MAXIMUM information density.** A busy executive should understand the entire company story in 30 seconds. Fill every quadrant to capacity.

**Per quadrant targets:**
- **Company Overview**: 6-8 bullets minimum (HQ, founded, employees, CEO/CFO, market cap, ticker, industry, key stat)
- **Business & Positioning**: 6-8 bullets (revenue drivers, products, market share %, competitive moat, customer count, geographic mix)
- **Key Financials**: Table with 8-10 rows OR chart + 4-5 key metrics (Revenue, EBITDA, margins, EPS, FCF, growth rates, valuation multiples)
- **Fourth quadrant**: 5-7 bullets (ownership %, recent M&A, developments, catalysts)

**Information packing techniques:**
- Combine related facts: "HQ: Austin, TX; Founded: 2003; 140K employees"
- Always include numbers: "$50B revenue" not "large revenue"
- Add context: "EBITDA margin: 25% (vs. 18% industry avg)"
- Include YoY changes: "Revenue: $125M (+28% YoY)"
- Use percentages: "Enterprise: 62% of revenue"

**If a quadrant looks sparse, add more:**
- Segment breakdowns with %
- Geographic revenue splits
- Customer concentration (top 10 = X%)
- Recent contract wins with $ values
- Guidance vs. consensus
- Insider ownership %

**Line spacing - use single textbox per section:**
```python
def add_section(slide, x, y, w, header_text, bullets, header_size=10, bullet_size=8):
    """Header + bullets in single textbox with natural spacing"""
    tb = slide.shapes.add_textbox(x, y, w, Inches(len(bullets) * 0.18 + 0.3))
    tf = tb.text_frame
    tf.word_wrap = True

    # Header paragraph
    p = tf.paragraphs[0]
    p.text = header_text
    p.font.bold = True
    p.font.size = Pt(header_size)
    p.font.color.rgb = RGBColor(0, 51, 102)
    p.space_after = Pt(6)  # Small gap after header

    # Bullet paragraphs
    for bullet in bullets:
        p = tf.add_paragraph()
        p.text = bullet
        p.font.size = Pt(bullet_size)
        p.space_after = Pt(3)
    return tb
```

**Key spacing principles:**
- Put header + bullets in SAME textbox (no separate header textbox)
- Use `space_after = Pt(6)` after header, `Pt(3)` between bullets
- Don't hardcode gaps - let paragraph spacing handle it naturally
- If content overflows, reduce font by 1pt rather than removing content

---

- **3-4 dense slides** - use quadrants, columns, tables, charts
- **Bullets for ALL body text** - NEVER paragraphs. **Use ONE textbox per section with all bullets inside** - do NOT create separate textboxes for each bullet point. Use PptxGenJS bullet formatting:
  ```javascript
  // CORRECT: Single textbox with bullet list - each array item becomes a bullet
  // Position in top-left quadrant (Company Overview) - after header with accent bar
  slide.addText(
    [
      { text: 'Headquarters: Austin, Texas; Founded 2003', options: { bullet: { indent: 10 }, breakLine: true } },
      { text: 'Employees: 140,000+ globally across 6 continents', options: { bullet: { indent: 10 }, breakLine: true } },
      { text: 'CEO: Elon Musk; CFO: Vaibhav Taneja', options: { bullet: { indent: 10 }, breakLine: true } },
      { text: 'Market Cap: $850B (#6 globally by market cap)', options: { bullet: { indent: 10 }, breakLine: true } },
      { text: 'Segments: Automotive (85%), Energy (10%), Services (5%)', options: { bullet: { indent: 10 } } }
    ],
    { x: 0.45, y: 0.95, w: 4.5, h: 2.6, fontSize: 11, fontFace: 'Arial', valign: 'top', paraSpaceAfter: 6 }
  );

  // WRONG: Multiple separate textboxes for each bullet - causes alignment issues
  // slide.addText('Headquarters: Austin', { x: 0.5, y: 1.0, bullet: true });
  ```

  **Bullet formatting tips:**
  - `bullet: { indent: 10 }` - controls bullet indentation (smaller = tighter)
  - `paraSpaceAfter: 6` - space after each paragraph in points
  - Pack multiple related facts into each bullet (e.g., "HQ: Austin; Founded: 2003")
  - Include specific numbers and percentages for information density
- **Title case** for titles (not ALL CAPS), left-aligned
- **Consistent fonts** everywhere including tables
- **Company's brand colors** - YOU MUST research actual brand colors via web search before creating slides. Do not guess or assume colors.
- **Follow brand guidelines if provided**

### Visual Reference
See `examples/Nike_Strip_Profile_Example.pptx` for layout inspiration. Adapt colors to each company's brand.
