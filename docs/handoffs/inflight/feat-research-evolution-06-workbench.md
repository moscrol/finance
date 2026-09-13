# feat/research-evolution-06-workbench · 2026-09-13 · 研究进化 06：Workbench 集成与验收

## 一句话

01–05 五个模块已经接进**既有 Workbench 会话**：一个 GET 投影 + 三个 POST + 前端「维护」页，
判定全部回调各轨真函数，06 只做取数、授权与单 writer 落盘。工程链路已验；
**真实前向样本与真人试点一个都没有**，不得据此说方法有效或有商业验证。

## 这棵树是什么

- 工作树 `/Users/a77/fwp-wt-research-evolution-06`，分支 `feat/research-evolution-06-workbench`。
- 它是**组合分支**：`gitea/main@631786ab` + 规格分支 + 01–05 五个实现分支（六次 `--no-ff`，零冲突）
  + 06 自己的四个提交。别在别处重新合一遍——直接用这棵树。
- 进度与逐条验收对照 `docs/superpowers/plans/2026-09-13-research-evolution/06/PROGRESS.md`；
  跨轨缺口与未做项 `.../06/BLOCKED.md`。两份都是真值表，接手可直接按步执行。

## 接手要知道的五件事

1. **`?user=` 不是认证。** 未配认证层时只认服务配置用户与 `RESEARCH_EVOLUTION_ALLOWED_USERS`
   白名单，其余一律 `owner_forbidden`；他人对象与不存在对象返回同一个 `not_found`。
2. **新台账已在 `docs/learning/ledger-map.md` 登记**（6 条），落 `user_space(user).root/research_evolution/`，
   单 writer 是 `EvolutionStore`。前向实验那条的唯一写入者仍是 03 的 `Repository`，06 只注入根。
3. **原判断台账一个字节没动。** 管理动作只改维护项状态；要关闭一条维护项，
   必须指到原写入者（`judgments.record_judgment`）写下的新判断行。
4. **市场取数与时钟是注入的资源**（`create_app(research_evolution_evidence=..., research_evolution_clock=...)`）。
   注入的是资源不是判定——01/02/04/05 的函数一行没换。生产走 `RiverEvidenceSource`，
   库路径在 `app.py` 显式解析（river 的缺省是 cwd 相对路径，在 uvicorn 工作目录下会指错树）。
5. **8792 是部署家，不是这棵树**（cwd `~/.finance-runtime/finance-workspace-2ee664fae9c4`）。
   本轨没碰它。线上状态只认 `/api/health` 的 revision。

## 过程中修掉的四个真 bug（都在 PROGRESS 有测试对应）

1. `int(expected_revision or -1)` 把合法的修订号 **0** 当假值 → 每条维护项的第一个动作都判版本冲突，
   而错误信息里前后两个数一模一样，读起来像并发。
2. 证据目录按 ref 去重时取插入顺序最后一条 → 绑定基线随取数顺序漂到一个**晚于绑定时刻**的版本，
   于是「先跟踪、后被改」这条线永远不成立。改成取「截止前记录时刻最晚」的那一版。
3. `view_digest` 覆盖了 `evaluation_at` 及其派生 id → 同样内容每秒一个新摘要。
4. `publish_immutable` 往内容寻址件正文里 setdefault `owner_user_id` → 打坏冻结协议自己的哈希，
   05 当场报「冻结后被改过？」。归属改回靠路径隔离。

## 跑起来

```bash
cd /Users/a77/fwp-wt-research-evolution-06
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY -m pytest -q intelligence/tests/test_research_evolution_*.py     # 63 passed
$PY -m ruff check intelligence/                                      # clean
cd intelligence/webapp && export PATH=/Users/a77/finance-workspace-private/.venv-workbench/bin:$PATH
pnpm install && pnpm lint && pnpm typecheck && pnpm test && pnpm build
pnpm exec playwright install chromium                                # 本树此前没装
WORKBENCH_E2E_PORT=8797 pnpm test:e2e --project=desktop               # 8 passed
```

## 没做的（不假装做了）

I13 完整配对试点（缺真人）、I14 后台暂停与端到端耗时（缺浏览器可见性事件上报）、
I15 走完一轮真实前向（缺已授权结果源）、`evidence-catalog` 的 UI 选择器。逐条原因与下一步在 BLOCKED §3。

## 下一步

1. 先把纯文档分支 `docs/river-next-specs` 合进 main，再并本组合分支。**等用户确认**，不强推。
2. 合并前在最终组合 revision 上重跑全量等价 CI + registry + e2e（本文收据绑的是 `e0dec906`）。
3. BLOCKED §2 的五条跨轨缺口交对应 owner；其中第 1 条（04 的结果身份 vs 03 的曝光身份）
   会影响练习揭示路径，现在是 fail closed。
