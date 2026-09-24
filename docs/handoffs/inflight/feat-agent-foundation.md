# feat/agent-foundation

## 这个分支做什么

把现有环境合同、锁、门禁接成可重复的 Agent 开发基线，并修六图确定性错误。工作树 `~/fwp-wt-agent-foundation`。

## 决策与被否方案

沿用 pip/pnpm 锁 + 薄 CLI，否全量容器化/共享 venv 升级：控制本片范围与副作用。
地图登记来源和触发器，不复制能力清单、不拿路径存在性代替语义或生产验证。
背景与取舍见 `docs/handoffs/2026-09-24-agent-foundation.md`。

## 当前状态

代码主体 `29e42db81`，基线 `gitea/main@a54fed0d0`；未合入、未部署。收尾另补 Git 源摘要字节保真（入口24项通过），随本交接提交；旧收据不覆盖后补丁。
共享文档候选：memory `docs/agent-foundation@6eb6efc1`（`~/memory-wt-agent-foundation`）；harness `docs/agent-foundation@54bef89`（`~/harness-wt-agent-foundation`）。原树的他人改动未动。

## 已验证

新树 venv 从开发锁安装，pip check / doctor 通过；两项离线研究 smoke 通过。
干净代码提交相关回归 174P/1S；收据 `~/.finance-runtime/test-receipts/20260924T124733Z-29e42db8-4aa1c9b3f188.json` 已校验。仅对该提交成立，不是全量读数。
全仓 Ruff、提交静态门禁、runtime catalog --check 通过。
代码图在代码提交上重建成功；memory 图谱审计无 STALE，在途/未验证项仍留。

## 未验证 / 已知边界

全量 Python / 前端 / E2E / registry 合入组合未执行。doctor --frontend 因 Node 26.0.0（合同22）阻塞，未改全局工具链。
未验新机器整栈、真实模型、生产数据或部署；产品门页历史瘦身与全图语义审计未做。

## 下一步

先读 `docs/workflows/agent-foundation.md`，跑 doctor；共享图用 FWP_AGENT_MEMORY 显式绑定候选 vault。
若准备合入：fetch 后核对新主干，用 Node22 跑完整门禁，用户确认后分仓合入；不可拿上述定向读数当四叶签字。

## 踩过的坑

能力图失效测试在历史 `27034ce44` 确实存在，移动分支引用才是错误，已钉提交。
本地 venv 不完整/坏软链不得静默回退共享 venv。dirty 代码图不再 ready。
通用零件已归 KIT/BUILD，无一次性 /tmp 工具遗留；doctor 的源摘要不是图谱已验鲜声明。
