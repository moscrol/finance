# 8792 回答能力收尾：选定原件包

结论只看[正式报告](../2026-09-28-answer-capability-evaluation.md)。`manifest.json` 索引66件选定原件：**45件逐字节副本入库，21件原始日志仅留树外**，全部记录来源路径、字节数与SHA-256。`storage=external_only` 的 `path` 只是逻辑标签，文件应按 `source` 读取；其他条目按本包相对路径读取。遵守仓库不提交日志的规则，不改后缀绕过；不把旧答卷/旧门禁移签给新代码。

## 从哪里开始

| 要核什么 | 文件 |
| --- | --- |
| 最终工程代码 | `python-7c16a38ec.json`、`main-gate-7c16a38ec.exit`；门禁与receipt-check日志由manifest索引树外原件 |
| 前端/注册表 | `frontend-7c16a38ec/frontend.json`、`registry-7c16a38ec/registry.json`；其相对日志名按manifest解析到树外原件 |
| 原题/规则/19份公开答卷 | `answers/packet.json`，逐份 `answers/review-01.json`…`review-19.json` |
| 版本与实验臂 | `answers/origin-key.json`、`answers/arm-key.json`、`answers/controls-summary.json` |
| 最终作者裁决 | `answers/author-adjudication.json`；非盲审，不冒充独立结论；`author-identity-check.json` 为19/19机械核对 |
| 新五题独审原件 | `answers/independent-five-{packet,raw}.json`、`independent-request.md`、`independent-identity-check.json` |
| 旧独审错配 | `answers/old-independent-invalid.md`：review-16未答却判可用，review-18题型/引用错配；原件保留但撤销验收效力 |
| 代码复审先阻断后修复 | `source-review-v1.md`、`source-review-v2.md`，后者只做有限静态检查 |
| 行为反例红绿 | manifest的`regressions/`逻辑条目；`nonfrozen-precedence-red.log`为夹具缺gap导致的无效红测，真正行为反例是`red-v2` |
| 生产时点变化 | `production-health-{earlier,closeout}.json`、`observables-closeout.json`；只读快照，不是本候选部署验收 |
| 工具反证 | `tools/mutations.json`及manifest的`tools/`日志索引：harness-reference `e136472` 的28项合成测试，撤掉两个哈希检查各被测试抓红 |

## 读数边界

- `7c16a38ec` Python完整18,595P/74S/2X、0F/E，收集18,671；同SHA前端与注册表通过。`11f7ce233`/`3892eb8b4`只表示各自工程历史。
- 最新自然五题绑定 `220693df3`，收尾新增自然请求0。作者最终为比较可用，历史/消息不可用，两财务部分可用。
- 新独审review-19的答案哈希少一位，整包机械准入exit1，该行不作有效独立证据。其余4条身份合格不等于语义正确；review-18独审usable而作者partial，分歧原样保存。
- 多个“本次运行未交付公开答卷。”具有同一文本哈希，**不能只按哈希join**，须同时核id/case。没有交付的内部草稿不替代公开答案。
- manifest用于核验所列副本/树外原件身份，不证明所有原始运行都已入Git或裁决必然正确。JSONL会话全轨迹、完整pytest原始日志、约489MB失败现场归档和200,919项manifest仍在树外；离开这台机器只带Git克隆，无法重读树外日志。

树外根：`~/.finance-runtime/reviews/8792-answer-capability-20260928/`，第二轮原始运行在 `authoring-v2/`、`quote-repair/`；收尾在 `closeout-0929/`。失败包为 `closeout-0929/failed-basetemp-220693df3.tar.gz` 与同名 `-manifest.json`，旧脚本 `archive_failed_temp.py` 是已执行的历史动作，**不要重跑其删除流程**。

## 离线复核入口

通用量具候选已推 `harness-reference` 分支 `docs/answer-review-audit-0929`（代码 `e136472`），[WIP PR #18](http://127.0.0.1:3300/a77/harness-reference/pulls/18)，未合main。使用其 `scripts/check_answer_review.py`：

```bash
python scripts/check_answer_review.py <本包>/answers/packet.json <本包>/answers/author-adjudication.json
# 预期exit 0：只核身份/覆盖/连续原句，不给语义背书
python scripts/check_answer_review.py <本包>/answers/independent-five-packet.json <本包>/answers/independent-five-raw.json
# 预期exit 1：review-19 answer_hash_mismatch；不得静默补哈希
```

通用 `verified_tree_archive.py` 不删源；它没有运行于本历史归档，不能将合成测试追认成旧包的新工具验收。清理必须另核所有权/授权/源未变，禁止拿旧成功收据当删除许可。
