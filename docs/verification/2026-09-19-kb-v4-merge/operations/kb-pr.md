## 范围与授权
用户于2026-09-19确认“允许”两仓新增修复进入合并验收。本PR不部署、不写生产索引、不改raw原文、不解除14页历史冲突隔离。

候选 `c141a424a16faed2cc959c0839e6b0ea29ced481`；基线 `91725ea9ba0252a43665f9e3130142f946c289ae`；金融配对 `2b4948a4015e53fd1fde5bb1e50147582abde2da`。

## 改动
- Markdown水平线间的非法YAML或非mapping值保留原文；只有mapping或真正空/纯注释页头才可去除。
- 覆盖false/0/null/空列表/空字符串、CRLF及未闭合边界。
- 切块版本v4，源未变的旧切块结果仍应判stale。
- 交接保存四篇原文SHA未变、零块恢复的实际覆盖证据。

## 验收
对本PR完整SHA在新隔离树重跑KB全量（tests及skills/lib/rag/tests）与relations/sizes/quality/log/index守卫，结果完成后附评论。金融批次同时重验，旧23b/99收据不代签。
既有v4普通14434/14448、全文17974/17988入库，差额各14页冲突隔离，未解释缺口0。fresh不洗掉degraded；真实检索接线通过不等于答案质量。

## 生产不变
防写保护、post-*暂停、8792旧版都保留。长期双索引代际维护/故障恢复仍待实现，不把代码合入当作迁移上线。

证据：`docs/handoffs/2026-09-19-rag-frontmatter-v4-acceptance.md`（合前历史快照；实时合入身份以PR及新收据为准）。
