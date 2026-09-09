# baseline/capability-benchmark-00

## 这个分支做什么
能力升级任务包 00 号单「用真实工作衡量能力增长」：30 道真实研究工作题（10 类 × 2 公开 + 1 密封）、评分规则、走 Workbench 真实对话门的 runner、匿名配对评审包与汇总（含反向验证）。合同在 `codex/docs-capability-upgrade-plan@b80decbd` 的 `docs/superpowers/plans/2026-09-09-capability-upgrade/00-*.md`；进度 `progress/00.md`，阻塞 `blocked/00.md`（同目录，本分支）。

## 决策与被否方案
- 选：新建题集只补「真实工作题」（财务计算 / 材料理解 / 跨公司 / 跨日续研 / 方法验证…），零重叠钉单测。否：复用冻结 30 题——它与 28 题重叠 19 道，是方差回归集不是泛化集。
- 选：题面公开、判分要点密封（sha256 入仓、本体在 `~/capability-benchmark-00-sealed-20260909/`）。否：全公开——B6 判据已被「照答案调」过一次。
- 选：入口只认 `POST /api/conversations/{id}/messages`，无 `continuous-episode.json` 记 engine_missing。否：CLI ask / live_probe ask——不经过判官。
- 选：多轮题前序 user 轮真实投放，assistant 参考稿只给评审。否：注入冻结 assistant 稿——API 不支持且不是真实体验。
- 选：评测用户 `cb00-baseline` 台账从真实用户快照种子重置（同数据）。否：空用户——记忆题会失真。
- 选：费用只记 token。否：折算金额——仓内无 cost 埋点，网关按配额计费。

## 当前状态
`193c848e`（2 提交，基线 `gitea/main@5eb24515`），树干净。**基线全跑阻塞在模型网关 cockpit-cliproxy（127.0.0.1:57244）无进程**（15:15 起，生产 8792 同受影响）。后台编排脚本 `~/.finance-runtime/capability-benchmark-00/run-baseline-when-gateway-up.sh` 每分钟探网关，最多等 6 h，恢复后自动跑 30 题，产物落 `intelligence/eval/runs/<ts>-cb00-baseline-<rev>.json`，日志 `…/logs/baseline-orchestrator.log`。sidecar 8813 从本树起（`start-sidecar.sh`），health 三读 = 本树 / 干净 / 指纹一致。

## 已验证
- `validate` / `overlap`（零重叠 6 套题集）/ `seal-verify` 全 rc=0；`test_capability_benchmark.py` 10 passed；ruff 0；pre-commit 11 道过。
- 探针题 `cb00-calc-01` 真实走门：engine=A、episode 落盘、preflight 通过；失败原因是网关 URLError，非 runner 问题。
- 生产运行态取证（进程 cwd 0060da5c、模型 gpt-5.6-sol/zhipu、tier max、工具 all、数据截止 09-07）写在 progress/00.md。

## 未验证 / 已知边界
- 30 题基线读数：**未产生**。artifact 出来后要做：`review-pack --decoy …` → 人工评审 → `aggregate`（decoy 胜则非零退出）→ 写 `docs/verification/2026-09-09-capability-benchmark-00-baseline.md`。
- readiness `market_data_consistency=false`（快照 09-08 领先库 09-07），生产同态；只记录不处理。
- 无同题 Knevo 样本，不报告竞品胜负；竞品答案按 bench6 v2 协议粘贴到 `docs/learning/knevo-distill/cb00/`。
- 单跑不做显著性宣称（30×15 才分辨 5pp）。
