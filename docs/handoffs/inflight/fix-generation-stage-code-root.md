# #50 日报生成双根接线

## 这个分支做什么
代码只取固定快照，数据/报告/用户态/episode 保持正确持久根；不改变 local 计划或资金口径。

## 当前状态
代码 `0f6c2810`（含前版 `2f82d4d3` 和 local-plan `4fbc8c42`）；开发树 `/Users/a77/fwp-wt-generation-stage-code-root`。未 push/合并/部署/生产补跑。验收树 `/Users/a77/fwp-wt-generation-root-validation-0f6c2810` 为干净 detached，测试后 tracked 干净。作者验收完成，独立复核/生产验收尚未做。

## 决策与被否方案
- 否了仅 PYTHONPATH/-P：它们不改相对脚本执行文件。薄启动器验证根后仍调用原 daily；子步骤本解释器+绝对代码脚本，cwd 保持数据根。
- 否了全局 cd 代码树：会把相对数据/输出带走。脚本数据根改走已有 paths，生成安全环境不扩散给 L2。
- 保留显式外置 users/episode/DB，不迁移存量；相对覆盖按数据根解释。缺代码/关键包软链逃出根/状态根指进代码树均拒绝。
- 详情 `docs/handoffs/2026-09-15-generation-stage-code-root.md`。

## 未验证 / 已知边界
- 未跑真实模型网关、矩阵业务 SQL、生产同日/跨日/L2 门与日报，不能称生产恢复。
- 新22项用临时库；SQL collector/质量结果为夹具，真实 writer/CLI/子进程执行。episode 是真实存储接口探针，不是真模型回合。
- 代码零新增只覆盖所跑夹具，不是 OS 沙箱。runtime 部署可能只复制 intelligence，必须确认 scripts/skills/market_feature_store 齐全。
- registry 三仓在场通过，但知识库/研究站是有 WIP 的现场树，不是冻结跨仓提交验收。

## 下一步
独立复核 → 用户明确授权才 push/合并 → 完整快照部署 → 分别验 import、持久化根、真实三道门 → 另行授权生成。继续不请求复盘会/不补资金兜底/不碰原数据树 WIP。

## 踩过的坑
旧 /tmp Codex 红门是 minimal 允许读取 /tmp，非网络隔离失败；/Users 已复验，旧红收据保留。曾两次并行变异污染正常测试；现变异只改临时副本。旧 local-plan /Users 验收副本疑似凭证污染，勿动；撤销/来源未确认。

## 已验证
冻结 `0f6c2810`：Ruff、shell/diff/提交钩子通过；全量9679P/77S/2x/17警告。收据 `~/.finance-runtime/test-receipts/20260914T181625Z-0f6c2810.json` 校验一致。前端lint/typecheck/build、76 tests；E2E15P；registry四条exit0，60 SKILL可解析；crosswalk exit0保留96 warning。真shell调用点独立副本改裸-m触发DATA_TREE_CODE_EXECUTED，恢复绿；提交前相关133P。日志索引见日期快照。
