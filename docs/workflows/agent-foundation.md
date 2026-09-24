# Agent 开发基线

用于新工作树、换机器或搭建 Agent；不是生产安装器，也不替代合入验收。
环境要求唯一源 `test-environment.json`，版本锁 `requirements-dev.lock` 引用现有消费侧锁。
六图的来源、维护触发器与人工边界登记在 `docs/agent-maps.json`，不另建能力清单。

## 开工

1. `git fetch gitea`，从 `gitea/main` 开独立工作树，保留用户原树的未提交改动。
2. 在目标树运行 `python3 scripts/workspace.py doctor`。它只读，不 fetch、不调模型、不读生产数据正文。
   输出包含树、分支、提交、dirty、解释器、锁版本差异，以及六图来源的摘要与版本。
   `ready` 仅表示离线开发依赖符合合同；地图验证、前端、生产状态分开报告。
3. 需要新环境时，运行 `python3 scripts/workspace.py bootstrap --python <匹配合同的基础解释器>` 查看计划，
   确认后追加 `--install`。只创建当前树的 `.venv-workbench`，拒绝改动已存在的目录或软链，
   不升级主树共享环境；安装失败时保留现场，先诊断，再由维护者处理该新环境。
4. 再跑 `doctor` 和 `python3 scripts/workspace.py smoke`。后者使用临时 home/数据根和合成回答，
   禁止 Python 网络连接，检查真实 `TurnOrchestrator` 的结果持久化及三轮会话继承。
   不调用真实模型，不复制生产 DuckDB，不留下个人台账。这是测试防误用护栏，不是恶意代码沙箱。
5. 前端工作另跑 `doctor --frontend` 核版本，再到 `intelligence/webapp` 执行
   `pnpm install --frozen-lockfile` 和原有 lint/typecheck/test/build。仅运行 doctor 不安装前端依赖。

解释器解析由 `scripts/workspace_env.py` 统一负责：`FWP_WORKBENCH_PYTHON` 显式覆盖 > 本树 venv >
Git 公共检出树的 venv。合同始终读取当前树，不能借主树的旧合同来证明新树可用。
覆盖值属于本机环境，不写进 Git；脚本不会加载 `.env` 或打印凭证。
安装后以 `doctor` 核对全部锁定版本，不以“import 成功”冒充版本一致。
采集侧可选库不在这个最小开发锁中，全仓测试与数据采集须按对应合同补齐。

## 地图保鲜

- 代码地图：提交代码后运行 `python3 scripts/code_map.py build --postprocess none`，再查 `status --json`。
  仅使用本地结构索引，不请求叙事生成；索引只对当前检出生效，dirty 覆盖未验证时返回 stale。
- 外部记忆库：本树 `.agent-memory`，或显式 `FWP_AGENT_MEMORY=<vault>`；Harness 规范库可用
  `FWP_HARNESS_REFERENCE=<repo>` 绑定。缺少外部库显示 unavailable，不阻塞离线样例，不冒充已校验。
- Harness 规范读取 `gitea/main:DESIGN-stack.md`，不读取他人的脏工作树。
- `doctor` 只登记来源，不自动执行需要人工判断的更新。按 manifest 的 triggers 找受影响地图，
  符号存在由原校验器验证；合入、部署、真实效果四种状态分别提供依据。
- 能力审计 `graph_audit.py` 的默认 finance 路径是主检出树。审候选时用显式 `--repos-root`，
  在临时父目录中将 `finance-workspace-private` 绑定到目标树；保留输出中的 revision，缺仓/分支仍算未验证。

## 收尾

改实现时同步对应地图及最小回归；纠正原则时归并正文，历史证据留日期快照。
通用零件以“失败形状 + 实现位置 + 验证边界”回写 Harness 工具包。
在干净候选上按 `acceptance-workflow.md` 跑合入门禁，沿用 `run_main_gate.sh` 与测试收据；
本入口的 smoke 不产生全量绿或生产验收结论。动作完成后写本分支 inflight，用户确认前不合并或部署。
