# 工单53第四轮复审：f43b89c6

结论：仍需返修。规范轴2项P2，需求轴2项P2。T3属于原审查要求，应保留修复方向；当前版本只补齐草稿层，下游事件与确认来源仍不一致。

## 固定范围与证据

- 候选 `f43b89c6cbb091544c1af93ea2f4164bd1813b74`；返修差异 `git diff 642c3f5d...f43b89c6`，5笔提交，8文件。最后产品代码为 `901c7a87`，之后只有文档。
- 审查树 `/private/tmp/extraction-qc-f43b89c6`，取固定候选后才建立本审查文档分支 `codex/review-extraction-f43b89c6`。主树与作者树未改。
- 合同：`docs/superpowers/specs/2026-09-14-extraction-first-p0-workorder.md`；规范：AGENTS、台账原始导出约定、前轮审查报告。
- 独立定向8模块247P；改动Python的Ruff与diff-check通过；固定 `1fef3d27` 的merge-tree exit0，树对象 `c6c470204c18f3eb7efd8399fab03f31a20f067a`。
- 全量收据 `20260914T032322Z-c9ebab07.json` 在另一干净树 `c9ebab07` 用指定解释器和 `--expect-revision c9ebab07` 独立校验exit0：9682P/0F/干净树。原始输出也匹配。`60fdc37c..c9ebab07` 仅交接md、`c9ebab07..f43b89c6` 仅收据md；代码及测试未变，认可该历史读数的代码适用性，但结束时收据本身不能追溯证明跑测全程无人改树。
- AST逐名对账77+50+1=128，无删除测试。前端四叶、E2E15P和registry原始日志存在且匹配。本轮未重跑全量及前端，不把历史收据写成本轮新读数。
- 新增M20–M25独立六条全部RED→GREEN，还原127P。未重跑M1–M19；那19条的独立核验属于上轮。
- 原两套探针合计13P/1F：642c报告原四条3P/1F，Q1–Q3报告十条10P。原T3仍红；新增事件/确认来源5测4F/1P，4红是两问题各两个观察面，不重复计数。导出字节碰撞另1F。

## 规范轴

### N1 · P2 · 坏行导出仍丢失原始字节

位置：`intelligence/services/personal_export.py:89–92`。

前轮642c报告N1明确要求“正常记录可导出、坏行以可逆表示保留”。当前 `decode(errors="replace")` 把不同坏字节都换成替换字符。真实 `export_ledger` 探针把 `7b226e6f7465223a22e7ae` 与 `7b226e6f7465223a22e7af` 分别夹在正常前后行之间，两次导出完全相同：`{"_unparsed_line":"{\"note\":\"�"}`。正常行保住了，原始坏字节却无法恢复或区分。

T4回归只断言正常行和占位键存在，未验可逆性。可读预览之外应保留可逆字节编码，并以解码后原字节完全相同验收。本项是原返修合同未闭合，不是临时增加备份需求。

探针：本目录 `test_export_bytes.py`，1F。

### N2 · P2 · 当前交接仍注入过期的门禁状态与范围说明

位置：`docs/handoffs/inflight/feat-extraction-first-p0.md:18–22`；另见第10行。

交接仍写全量9671，且称“仓级全量、前端、e2e未在901c7a87+上重跑”；最终收据与实际日志已是c9ebab07的9682及更新后的前端结果。第10行又称T2/T3/T4是自找缺口、第三轮只有Q1–Q3，遗漏了另一份642c报告。

违反AGENTS完成后回写真实状态和工单A15可复核要求。下一会话会误判缺门禁，甚至撤回范围内修复。历史独立复核可保留，但当前状态需指向最新收据，并同时列出两份报告。收据里保留旧阶段的数字不构成问题；这里的问题是交接用现在时陈述已经失效的事实。

规范轴2项，最高P2；未报告判断性代码气味。

## 需求轴

### S1 · P2 · 第三版草稿仍没有独立的成功提交事件

位置：`intelligence/services/observation_script.py:1400–1415、1441–1442`；下游 `projected_events:1006–1008`。

同一尝试A→B→A→A，返回版本1/2/3/3，created依次true/true/true/false，版本层已正确。但v1与v3仍使用相同的attempt+content哈希动作键及event_id；事件投影按该键全历史去重，`observation list --events` 只有v1/v2两条提交，read收据却已指v3。

违反工单§2.4.5“同动作重试去重，草稿新版本是新动作”，及成功新版本应产生draft_submitted的事件表。

**原第三轮测试第71行本来就断言3条提交事件。** 正式迁入的T3三测（`test_extraction_first_review_fixes.py:712–738`）遗漏该断言，当前原题仍红。M22只证明草稿层的测试能捕获回退，不能证明完整T3已关闭。

应分别定义连续重试判据与新版本动作身份，保留A→A幂等，同时让新版本对应新的成功事件；不能直接删除投影去重，因为它还保护repoint的重复确认。

探针：`test_original_four_contracts.py::ReviewContracts::test_draft_a_b_a_makes_final_a_current`；`test_version_contracts.py`中的事件两测是补充观察面。

### S2 · P2 · 第三版A确认后仍返回第一版A的来源

位置：T3新增版本处 `observation_script.py:1410–1421`；确认身份 `_confirm_action_key:446–479` 与旧收据短路 `register:703–709`。

同尝试依次A(v1)提交并确认、B(v2)提交并确认、A(v3)提交并确认。第三次草稿保存成功，CLI选择当前v3并向writer传入source_draft_id；确认键却没有包含该来源，writer匹配全历史第一版A后直接返回旧记录。命令exit0，确认source_draft_id为v1，用户刚确认的v3没有被保留。

违反§2.1“确认保留关联的source_draft_id/attempt_id，不覆盖原稿”。这是新版本启用后暴露的相邻回归：“确认来源等于本次实际选中草稿”的同一探针，旧642c通过、当前失败。旧版latest停B是另一已知缺陷，不能据此退回旧版；对照仅证明下游恒等关系被新版本打破。

修复确认身份对所选source_draft_id的表达；若选择复用既有checkpoint，也不能静默返回错误来源。回归同时覆盖立即重复同版确认与不同版本同内容确认。

探针：`test_version_contracts.py::DraftReversionContracts::test_confirmation_matches_actually_selected_latest_version_regression`。另有完整三次提交确认探针。两条下游恒等探针合计旧2P→新2F；不是新增四项问题。

需求轴2项，最高P2；范围外0。

## T3范围裁决

保留T3，不能退回全历史草稿去重。

第三轮实际上有两份独立报告：`codex/review-extraction-642c3f5d` 的 `docs/verification/extraction-642c3f5d/REVIEW.md` 明列S3“A→B→A最后A被吞掉”，并附含事件断言的原题；`docs/qc-extraction-b916091e` 的报告列Q1–Q3。后来的交接只引用了后者，因此把前者要求误记为范围外。工单§2.1最后成功提交、§2.4.5新版新动作也直接支持T3。

认领误带提交与披露共享树取数问题是必要说明，但不能替代行为验收。本轮不据此否掉有效9682收据，也不再重复计同一流程错误；需要返修的是上述可复现残留与交接不一致。

## 复跑与交付边界

反例保存在本目录，故意放在常规测试目录之外。只写临时users，身份与切片用现有Base夹具，无模型/网络、无真实台账写入。下面先进入待审代码树，再从审查树读取探针；固定rootdir/confcutdir/import-mode，避免pytest导入旧审查树的conftest后误测旧代码。

```bash
cd <待审代码树>
PYTHONPATH="$PWD" FWP_TEST_RECEIPT=0 \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  -q -p no:randomly --rootdir="$PWD" --confcutdir="$PWD" --import-mode=importlib \
  /private/tmp/extraction-qc-f43b89c6/docs/verification/extraction-f43b89c6/
```

在固定候选上归档全套10例为4P/6F，其中6红对应3个行为问题的重复观察面；文档N2另查。要求保留原断言全部转绿。

耐久原始证据：`/Users/a77/.finance-runtime/reviews/extraction-f43b89c6-20260914/`，含收据校验、247P、原四题结果、旧新恒等对照、字节碰撞与mutation目录。根审查一次直接跨树跑旧探针被旧conftest改变导入路径，`root-original-and-new-probes.txt`测到了旧代码，已作废；复制探针并固定导入方式后的`root-original-four-final.txt`等才用于结论。

候选实现未改，未推、未合main、未部署或启动真人实验。本审查分支仅归档报告、反例和交接；不是修复分支。下一步执行者修N1/N2/S1/S2，保留T3方向与原断言，再取固定新提交的门禁。
