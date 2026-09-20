# 研究求证意识候选

## 这个分支做什么
培养机制求证、竞争解释与反证；当前收口旧证据恢复、日期误删保护和真实入口边界。

## 决策与被否方案
- 选 `prior_evidence` 封装 old/new E 号映射，否 runtime 直接投影：职责和回归都保留。
- 选“句首短日期 + 绑定 source_date 月日”局部遮罩，否扩大正则/全局放行：数量门仍 fail-closed，judge 仍裁决。
- 保留旧 V4 on2 原件，否用新运行覆盖：分开程序误删、模型语义和版本证据。
- 不搬 E2 WIP、不改全局 `user_premise`：材料资格与推断是两层合同；P5 在候选待 P7，P6 外置。

## 当前状态
分支 `feat/research-reasoning-awareness`；代码 `2cfa9d0d7`；本轮仅文档/收据，off，未 push/PR/合 main/部署。8798 停，8792 PID `32544` 未动。

## 已验证
- 全仓 pytest `12049P/87S/2X/0F`、Ruff 绿；全仓收据 `~/.finance-runtime/test-receipts/20260920T195644Z-2cfa9d0d.json`。
- 日期隔离 `338P`；撤保护 `5F/8F`；相关回归 `477P`；K3 Spec/Quality PASS，但共享 refs/agent-memory 漂移。
- 旧 on2 只读重放：目标句到达 stub judge，仅 observation-only。
- V5：前两次澄清；最小题面有“9-18 逆势放量上涨”方向错误；句首 run `060912_869656` 第一字符为 `9`，目标 `9-11` 绑定 E6(`2026-09-11`)，9-14 绑定 E5，目标首句到达真实 judge 后 `demoted_to_issue`。
- manifest：`/Users/a77/.finance-runtime/reasoning-boundaries-20260921/v5-short-date/MANIFEST.json`，SHA256 `8142bec5b5213693bc2c97d3354345fb7ae488877621d2443b9fa63d02b8a387`。

## 未验证 / 已知边界
最新 run `completed/repaired` 不等于语义通过；数字句仍被门删。总量证据不支持“出逃/兑现”；独立盲审 `passed=false`，拒绝 `[1,2,3,5]`。V4 `n=2` 且 flag 未知；P5 在候选待 P7，P6 binding 未入；供需题、前端/E2E/registry、跨仓漂移未验。当前候选与 P6 在 `episode_semantic_verifier.py` 冲突，收据外置（`p6-integration-preflight.json`，SHA256 `9f312839…a6d581`）。跨会话、多层、混合联网、任意日期窗口、checkpoint 未证明。

## 下一步
1. 提交本轮三份文档，核对只包含 pathspec 指定文件。
2. P6 owner 先解 `episode_semantic_verifier.py` 冲突，合并树重跑四叶/独立语义验收；P5 owner 补 P7；继续补未见题和 fixture 反例，不把路径证据写成 PASS。
3. 处理前端/E2E/registry 与 `kb/rag-query` 漂移；暂停合 main、部署、重启 8792、付费外审、删生产原件。

## 踩过的坑
probe 显示路径可能不是隔离 users 真路径；旧 E 号不能跨轮引用；`9-11` 必须绑定日期后局部放行；`completed`、同源 judge、结构 gate 和答案保留不能替代独立语义验收；共享 refs/记忆漂移必须入收据。

## 工具沉淀盘点
复用既有 probe、收据和校验命令；没有新增生产执行器或跨项目工具。
