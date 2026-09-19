# 知识库过滤回执消费与常驻进程版本边界

## 状态与范围

2026-09-18 作者验证快照。金融分支 `fix/kb-filter-receipt`，实现提交
`698555e28784480c92be33b43f48c250ea0d0a09`，base `0a1cb8c4`。
配套知识库分支 `fix/agent-retrieval-reliability`，实现 `b62c58cb5`，本轮导航修复
`1f614b694`。两仓均只有本地提交，未推送、未合 main、未部署；生产双索引未迁移。

本轮收口的是**资料交付合同**，不是研究答案质量提升，也不自动为每个产品问句添加
等级/截至日期。生产切换、真实 BGE 模型验收、历史正文冲突修复另行办理。

## 发现顺序与决定

1. KB 已能按明确标注过滤并出回执，但金融旧消费者只收列表，兼容回退会删除不支持的
   等级条件。`telemetry.filters` 是请求值，不能据它声称条件已执行。
2. 增加 `kb_filter_receipt.parse_receipt`：核对封套状态、策略、版本/迁移状态的真实类型、
   请求与实际过滤、每条命中的元数据及内容有效性；`as_of` 判 `available_time`，不拿发布时间
   代替可得时间。合法空结果也是回执；旧元数据空结果要保留“待迁移，不代表没有事实”。
3. 已过滤的片段仍会被金融端原页重摘录、整节深读或 stale 恢复替换，新文字可能非法继承
   旧等级/日期。因此 `WikiHit.evidence_scope_bound` 阻止这些扩展；无过滤旧路径保持兼容。
4. worker 的 enrich 原先把原始单块盖回结果，丢失 KB 已裁切的邻块/预算。现在保留封套、
   证据文字、chunk IDs、原 revision，仅更新当次页新鲜度。收到新回执的结果不进结果缓存，
   保证下一问仍走实时源文件检查；模型和索引常驻缓存保留。
5. 负能力缓存最初只按脚本内容失效，但旧 worker 仍已加载旧代码。新增轻量
   `kb_code_identity.code_identity`，统一哈希 CLI、RAG 包与轻量依赖（不碰资料、索引和模型）。
   每个 worker 在自己的锁内结束旧进程再起新进程；子进程返回启动时的代码身份，调用前后
   及消费时核对，变化则丢弃响应。私有空 pycache 前缀防止同 mtime+size 命中旧字节码。
   这不是供应链认证，也不支持部署中逐文件原地写源码；正式发布仍用不可变检出与服务重启。
6. 全量测试首轮 `11474 passed / 1 failed`：展示用例因 `FINANCE_WS` 读到真实最新交易日，
   多出盘面组件。干净 base 单项同红；仅在该测试绑定临时数据根，不改生产展示规则、不删断言。
7. 浏览器首轮 `33 passed / 1 failed / 2 skipped` 是运行命令只改服务端口、漏配
   `RE06_E2E_URL`，连接了旧端口。纠正命令后通过；未借此修改产品或用例预期。

| 方案 | 评价 / 选择 |
|---|---|
| 不支持过滤就删参数重试 | 否：把约束变偏好，无资格交付 L3 证据 |
| 有 L3 字段的旧列表也算证明 | 否：不能证明邻块和上下文被同样过滤 |
| 复制 KB 的切块/标注算法到金融仓 | 否：制造两个事实源；金融仅验协议与输出一致性 |
| 过滤回执已验后继续扩读原页 | 否：扩展范围不继承原片段认证 |
| 所有旧查询一律禁用 | 否：无过滤列表仍可按原契约服务；不能声称其等级/时点已核验 |
| 仅按路径或 mtime 判断 worker 版本 | 否：路径不变、同时间/大小仍可更新；测实际加载的结果 |
| 收到新协议仍用结果缓存 | 暂否：无源文件状态绑定，可能漏隔离后续污染；牺牲结果缓存保可靠性 |
| 全局锁包重启/模型加载 | 否：只在该 worker 锁内换代，注册表锁不包慢操作 |

## 验证（绑定实现提交，不把后续文档提交冒充重测）

固定干净金融 `698555e2`：

| 检查 | 结果 |
|---|---|
| 全仓 pytest | **11481 passed / 73 skipped / 2 xfailed / 0 failed**，17 warnings，909.42s |
| 全仓 Ruff | exit 0 |
| frontend lint/typecheck/test/build | 全部 exit 0，Vitest **107 passed** |
| 浏览器 E2E | **34 passed / 2 skipped**，1.4m；两项为绑定链只在 desktop 执行的同例跨设备跳过 |
| registry parseability/check/backfill-tables/generate-views | 全部 exit 0 |
| 原 pre-commit | 密钥/体积/冲突、层级、路径、字段、数据集、工具可达性、运行目录均通过 |
| 测试收据校验 | revision/解释器/Python/依赖/干净树/未绕门/期望 revision 七项通过 |

实现提交前定向集 **181 passed**（包含三项真实跨仓测试），均进入上述全量。
代码升级两项在修前真实子进程上失败、修后通过；还测了查询中途修改代码不得交付，恢复后
实际依赖已更新。跨仓使用 KB `b62c58cb5` 的真实 CLI 与真实 worker、临时 wiki/hash 索引：
等级/硬度/来源/可得日组合、合法空结果、旧元数据迁移提示、CLI/worker 证据一致、暖进程
发现新 diff3 冲突。hash 仅为离线协议夹具，**不是生产 BGE 的质量/性能认证**。

持久原始收据：`docs/verification/2026-09-18-kb-filter-receipt/`。
其中 `pytest-receipt.json` 来自 `~/.finance-runtime/test-receipts/20260918T095109Z-698555e2.json`，
`dirty=false`，依赖指纹 `3328bed61f3e21ea`。旧失败与 worker 红测一并保留。
本轮未修 `market_stage` 的数值 RuntimeWarning、`utcnow` 弃用警告，以及 registry 的既有弃用警告。

### 复跑条件

从本分支根，`PYTHON` 指主金融树 `.venv-workbench/bin/python`，`KB_CODE` 指待验知识库树。

```bash
FINANCE_WS="$FINANCE_DATA_ROOT" KB_RECEIPT_CODE_ROOT="$KB_CODE" \
PYTHONDONTWRITEBYTECODE=1 KB_ACCESS_LOG_PATH="$TMPDIR/kb-test-access.jsonl" \
  "$PYTHON" -m pytest -q -p no:cacheprovider
"$PYTHON" -m ruff check .
cd intelligence/webapp
pnpm install --offline --frozen-lockfile
pnpm lint && pnpm typecheck && pnpm test && pnpm build
WORKBENCH_PYTHON="$PYTHON" WORKBENCH_E2E_PORT=18871 \
RE06_E2E_PORT=18874 RE06_E2E_URL=http://127.0.0.1:18874 pnpm test:e2e
```

未设置 `KB_RECEIPT_CODE_ROOT` 时三项跨仓测试明确 skip，不得说两仓协议已验。测试不能指向
生产索引重建；临时访问日志避免 fixture 遥测写到共享台账。E2E 服务使用隔离用户与现造市场库，
不是生产研究会话。最终服务已退出。

## 后续 / 不要做

- 用户确认后才能安排合并；若基线变化，整合候选须重新按本仓四叶门禁验收。
- 部署顺序：先保障 KB hook 的跨树身份与停用能力，再受控刷新双索引，保留各自
  model/include_raw/max_files；检查元数据版本、字段非空、覆盖与冲突隔离，再切消费端进程。
- 新旧兼容是有条件的：金融新端 + KB 旧端的**过滤请求会明确不可用**，不是自动成功。
  旧未标注索引即使可检索，也不自动成为 L3；不要批量猜等级/日期填满字段。
- 过滤查询目前仍沿原来的 CLI 子进程路径；本轮没有把它们迁进暖 worker，也未量真实模型
  冷启动/身份哈希开销。无过滤旧路径的本地扩读仍不具备等级/时点保证。
- KB 尚有历史正文冲突、全文 stale/缺覆盖；详见 KB
  `docs/handoffs/2026-09-18-retrieval-phase2-navigation.md`。不要删标记假装修复。
- 源码身份只覆盖声明的检索代码文件，不涵盖所有第三方包、环境变量、索引或原文身份；
  Python 依赖/数据根切换仍需正式发布和重启。回执不是恶意生产者的密码学认证。
- 第一阶段创建 KB worktree 曾被旧共享 hook 触发普通生产更新，已披露。第二阶段提交
  使用命令级安全 hooksPath，保留各仓原 pre-commit；三份已记录生产文件哈希复查不变，
  只对这三份及该时间段成立，不改写先前事故。

## 工具与知识沉淀

回执反例、真实跨仓验收、warm worker 变更/中途变更反例已进入正式测试；不留只在 `/tmp`
才能运行的长期探针。断链历史差分与正文语义恢复是一次性材料定位，不能安全做成自动选边工具。
可迁移判据回写共享 `gate-covers-only-its-return-value`；没有新增通用 harness 工具，未动共享
`harness-reference` 的他人在途改动。
