# 公司画像页 首页布局规范

> 本文件由 `skills/公司画像页/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

Must pass "30-second comprehension test" for a busy executive.

### Slide Setup (CRITICAL)
**Use 4:3 aspect ratio** (standard IB pitch book format):
```javascript
const pptx = new pptxgen();
pptx.layout = 'LAYOUT_4x3';  // 10" wide × 7.5" tall - MUST USE THIS
```

### Slide Coordinate System
PptxGenJS uses inches. 4:3 slide = **10" wide × 7.5" tall**.
- **x**: horizontal position from left edge (0 = left, 10 = right)
- **y**: vertical position from top edge (0 = top, 7.5 = bottom)
- **Content must stay within bounds** - leave 0.3" margin on all sides

### First Page Positioning (in inches)
```
┌─────────────────────────────────────────────────────────────────┐
│ y=0.2  Title: Company Name (Ticker)                             │
├────────────────────────────┬────────────────────────────────────┤
│ y=0.6  Company Overview    │ y=0.6  Business & Positioning      │
│ x=0.3, w=4.7               │ x=5.0, w=4.7                       │
│ h=3.0                      │ h=3.0                              │
├────────────────────────────┼────────────────────────────────────┤
│ y=3.7  Key Financials      │ y=3.7  Stock/Recent Developments   │
│ x=0.3, w=4.7               │ x=5.0, w=4.7                       │
│ h=3.5                      │ h=3.5                              │
└────────────────────────────┴────────────────────────────────────┘
                                                            y=7.5
```

### Title Section (y=0.2)
**Company Name (Ticker)** - Example: `Tesla, Inc. (TSLA)`
```javascript
slide.addText('Tesla, Inc. (TSLA)', { x: 0.3, y: 0.2, w: 9.4, h: 0.35, fontSize: 18, bold: true });
```

### 4-Quadrant Layout (y=0.6 to y=7.2)

| Quadrant | Position | Content |
|----------|----------|---------|
| **1** | x=0.3, y=0.6, w=4.7, h=3.0 | **Company Overview**: HQ, founded, key stats, business summary (4-5 bullets) |
| **2** | x=5.0, y=0.6, w=4.7, h=3.0 | **Business & Positioning**: revenue drivers, products/services, competitive position, growth drivers (4-5 bullets) |
| **3** | x=0.3, y=3.7, w=4.7, h=3.5 | **Key Financials**: Revenue, EBITDA, margins, EPS, FCF + Valuation (Mkt Cap, EV, multiples) — **table OR chart, not both** |
| **4** | x=5.0, y=3.7, w=4.7, h=3.5 | **For public companies**: 1Y stock price chart + top shareholders. **For private**: Recent developments or Ownership/M&A history |

### Font Sizes - USE THESE EXACT VALUES
| Element | Size | Notes |
|---------|------|-------|
| Slide title | 24pt | Bold, company brand color |
| Quadrant headers | 14pt | Bold, with accent bar |
| Body/bullet text | 11pt | Regular weight |
| Table text | 10pt | Use 9pt for dense tables |
| Chart labels | 9pt | Keep labels short |
| Source/footer | 8pt | Bottom of slide |

**CRITICAL: If text overflows, REDUCE font size by 1pt and re-render.**

### Visual Accents (REQUIRED)
Each quadrant header MUST have a colored accent bar to the left:
```javascript
// Add accent bar for quadrant header
slide.addShape(pptx.shapes.RECTANGLE, {
  x: 0.3, y: 0.6, w: 0.08, h: 0.25,
  fill: { color: 'E31937' }  // Use company brand color
});
slide.addText('Company Overview', {
  x: 0.45, y: 0.6, w: 4.5, h: 0.3, fontSize: 14, bold: true, fontFace: 'Arial'
});
```

**Visual elements to include:**
- Accent bars next to all section headers (brand color)
- Thin horizontal divider line between top and bottom quadrants
- Company logo in top-right corner if available
- Subtle gridlines in tables (light gray #CCCCCC)

### First Page Formatting
- **Font: Arial** (or as specified by user/brand guidelines)
- **Quadrant titles**: Title Case (not ALL CAPS), e.g., "Company Overview" not "COMPANY OVERVIEW"
- **Bullets**: Bold key terms at start, e.g., "**Market Position:** Leading global manufacturer..."
- White background only — no boxes, fills, or shading
- Section headers: bold text, follow brand guidelines for styling
- All quadrants equally sized and aligned
