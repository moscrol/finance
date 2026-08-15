# uq15 勘误索引（QC-1，2026-08-15）

密封 rubric 与 `uq15_rubric_hashes.json` **不得改**。判分方验封通过后，按本目录覆盖对应条款。

## 施加顺序

1. 验封：15 份 `rubric_uq15-qNN.md` 的 sha256 对照仓内哈希清单，任一不匹配则停。
2. 读本目录全部 `erratum_*.md`（先 `erratum_uq15-scoring.md`，再按题号）。
3. 题面以 `uq15_questions.jsonl` 为准；密封 rubric 里的「题面」行若与 jsonl 冲突，以 jsonl 为准。
4. 勘误与密封条款冲突时，勘误优先。

## 本批文件

| 文件 | 覆盖 |
|---|---|
| `erratum_uq15-scoring.md` | 废止「就高给分」；q15 KP3 半分解 |
| `erratum_uq15-q06.md` | KP4 不得靠复述题干拿分 |
| `erratum_uq15-q07.md` | 题干去掉假前提「持续走强」；KPs 不变 |
| `erratum_uq15-q09.md` | 整题替换为医疗服务链条（原光纤链条作废） |
| `erratum_uq15-q14.md` | 只注入 `context`，不注入 `runner_note` |
