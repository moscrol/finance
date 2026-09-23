# eb4 完整工程门与名称证据增补

本篇增补在[隔离验收快照](2026-09-24-eb4-independent-acceptance.md)封存之后发生的动作；前篇及原始 sealed-evidence.json 不覆盖。当前结论仍为 **数据准入未完成，不发布**。

## 完整工程门已完成

owner 的 `history-candidate/full-receipts/gate-Zgg3Ayou/pytest.json` 于 2026-09-23 19:47:25 UTC 完成：

- revision：`eb4ec08f0680f9ba8cdaf5f3e8a95be34861b12a`；原执行树干净。
- collected 15171；15084 passed、85 skipped、2 xfailed；failed/error/xpassed 均 0。
- Python 3.12.13，固定主树 `.venv-workbench/bin/python`，收据依赖指纹 `3328bed61f3e21ea`。
- 根级 gates/python/frontend 及 registry 五项 exit 均 0；前端六个 check 已逐项核对。
- 完整范围、根 target、精确 SHA、解释器、依赖、0 基座漂移校验通过，没有重复运行全仓。

随后 owner 提交了纯交接文档 `ffc67575c6608f32a8ce9fa8e517246eca41eb45`。直接从该树执行 checker 会按预期拒绝 revision 不一致；再从仍位于 eb4 的 QA 树执行同一检查通过。QA 树当时只有新增交接文档，代码范围无脏改动。两次 stdout/cwd/argv/exit 均存于 `eb4-live/engineering-completed-supplement.json`，不将 eb4 的收据移签到 ffc 或本分支后续文档提交。

工程绿并未改变隔离自然入口的 readiness 503，也不把相关模型判官提升为独立金融 QC。

## 新发现的原始时间证据

owner 在 #900/6707 指出，既有新浪名称快照不是靠文件 mtime 猜日期，而有原始 receipt：

- 抓取窗口：2026-09-22 02:12:06.752049 至 02:13:11.136272，Asia/Shanghai。
- 从已提交 input-contract 固定的 manifest SHA256 `3943ed43d2c68cbc53fb421a8694def27eabd41c871f67643544cc6431203525` 向下验证 receipt 和 70 页 raw，全部匹配。
- 原件 5564 个唯一代码，名称非空且无控制字符；均在已声明的 09-22 范围 5567 内。
- 缺 `301686.SZ`、`689009.SH`、`920229.BJ`；不扩大或缩小声明分母，不将声明范围说成官方全集。

独立解析脚本和结果：证据根下 `review_sina_name_window.py`、`sina-name-contract-adjudication.json`。该复核只读现有原件，没有新采集或写库。

## 合同裁决

已签 `2026-09-22-market-recovery-field-contracts.md` 的名称语义是 **具名时刻的供应商展示名**，不是法定名或 ST/IPO/除权官方状态。该合同没有要求每条 payload 必须有 name_effective_date，也没有要求盘后采集。

因此，这批原件可以作为覆盖 5564 只的**同日展示名证据的一部分**。这不推翻 owner 的 `can_certify_20260922_trading_session_names=false`：盘前观察并不认证全天名称或官方状态。原先对 09-21 用途的 comparison_has_target_date=false 也不修改，因为那回答的是另一个日期问题。

| 选择 | 不采用的替代 | 理由 |
| --- | --- | --- |
| 按原始窗口承认同日展示观察 | 因缺法定生效日期而全批拒绝 | 后者把已签展示名合同擅自提高成官方状态认证 |
| 保留缺三只和声明范围 5567 | 用已覆盖 5564 缩分母 | 缺证据不等于身份不存在 |
| 来源明确写 Sina，保存窗口 | 冒充合同 B 默认的东财或每行精确秒点 | 扩展输入要说清实际来源及时间精度 |
| 名称证据与行情日期分开 | 将快照内价格直接标为 09-22 bar | 观察到名称不证明同条价格属于目标交易日 |

owner 应在扩展输入合同中明示这一来源后再构造候选，不把本次证据采信当成正式 writer/换库授权。已知同日名称或状态冲突仍逐项具名核验；两只当日 IPO 需要当日具名来源，689009 已有 09-21 bar，不能仅因缺名就推成 IPO。保留原 snapshot_kind，`official_historical_universe_verified=false` 不变。

此前受托拍板已经允许声明范围恢复；本次不把取得官方全集重新加为该路径前置条件。正式恢复仍须补齐实际缺口、明确停牌分区与未知成员边界，再过 same-day/cross-day/L2/readiness 门。

## 同步与沉淀

上述工程结果、35 项变异、自然入口结果及限定名称裁决已发 #900 评论 **6712**，正文逐字回读一致。

本轮未新增生产能力，只复用既有变异/验收工具；三态消费校验已以测试和变异钉定，不只写提醒。新增知识笔记 `consumed-evidence-validation-boundary.md` 聚焦校验消费集合和写前不变量，与 owner 的 `nullable-classification-must-preserve-unknown.md` 相互补充。Vault lint 本轮为 45 errors/17 warnings，未把全库报成通过；新笔记无诊断，新增的他人笔记与其余既有错误没有代改。

所有自有 live 控制器、19051 sidecar 和 worker 已退出；此后没有新的后台验收。生产输入与 launcher 在完整旁路期间保持原身份，正式数据恢复与发布仍由 owner 继续。
