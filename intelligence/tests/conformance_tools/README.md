# 工具注册表缝契约符合性套件

缝：`research_tool_registry._DEFAULT_TOOL_METADATA` 的 N 个工具 × 统一
`ToolSpec` / `ToolObservation` 契约。工具个数用解析器数（`tools.TOOL_NAMES`
直接枚举唯一事实源），不写死。

来源工单：`docs/superpowers/specs/2026-08-29-conformance-seam-census-workorder.md`
任务 B；机制复用运行时后端套件三件结构
（`intelligence/tests/conformance/`，分支 `test/runtime-conformance-suite`）。

```bash
.venv-workbench/bin/python -m pytest intelligence/tests/conformance_tools/ -q
```

首轮读数（2026-08-29）：`83 passed`，baseline 为空。

## 三件

| 文件 | 是什么 |
|---|---|
| `tools.py` | 参数表（逐工具）+ 能力声明表 + 探针 runner / registry / context 工厂 |
| `baseline.py` | 棘轮 baseline（首轮为空；规则同运行时套件：红入账带原因、绿逼清账、只缩不涨） |
| `test_t1..t7_*.py` | 每个不变量一个文件，`parametrize(TOOL_NAMES)` 逐工具跑 |

## 不变量 → 断言落点

| # | 不变量 | 断言落点 |
|---|---|---|
| T-1 | 返回形状守 `ToolObservation` 契约 | 逐工具 `registry.execute` + `ToolRunnerAdapter` 四种归一化形状 |
| T-2 | 只读保证 | 棘轮式源码扫描：`intelligence/services/` 每处 `duckdb.connect(` 必须显式 `read_only=True`；注册表公开面无写动词 |
| T-3 | 参数校验 fail-closed | 逐工具坏参数矩阵（query 类 / snapshot 类按 `spec.parse_arguments` 运行时分派，不写死名单）+ 跨工具 prepared 串号拒绝 |
| T-4 | 拒绝 detail 非空可操作 | 逐工具 `str(exc)` 非空、≠分类码、指得出参数（2026-08-12 事故：detail 恒空致 14 次同形状盲目重试） |
| T-5 | 证据发射契约 | 逐工具：带 hash 证据进 `evidence_hashes` 且与交付证据对齐、来源非空 |
| T-6 | 尊重 deadline / 取消 | 逐工具：episode 的 deadline 与取消谓词**同一份**传进 `AgentToolContext`；取消后不交付（单点形状，取代表工具） |
| T-7 | capability 与元数据一致、不可见即不可调 | 逐工具：capability==声明；specs/definitions/prompt 三个可见性出口同步裁剪；execute 未授权抛显式错误且 runner 零触碰 |

## 与运行时后端缝的关键差别（判据）

运行时缝的 4+1 个后端是**各自为政的实现**（同一不变量在各后端有独立代码
路径），所以声明表需要 REDUCED / UNSUPPORTED 档。工具缝的契约由
`ResearchToolRegistry` **单点强制**，N 个工具在注册表层是同一实现的 N 份
配置——默认注册面全 SUPPORTED、baseline 为空是如实读数，不是套件没牙
（T-7 的 prompt_block 断言与 T-6 的取消断言首轮就抓过两处口径问题）。

这个缝真正的漂移入口在**装配面**：`build_episode_registry` 会给个别工具
换 schema / parse_arguments（`finance_query` 的语义查询 schema 即现例）、
按 capability 条件装配（`memory_lookup` 需 memory_user）。装配面与声明的
一致性由 pre-commit 门禁 `tool-reachability`（声明 12 = 无条件装配 11 +
条件 1）看守，生产 schema 的校验行为由各工具自己的单测管；本套件不重复。

## 怎么加新工具

往 `_DEFAULT_TOOL_METADATA` 加条目后，本套件自动把它纳入参数表（解析器
数）。新工具必须全绿；若它的参数形状既不是 query 也不是 snapshot，先在
`default_registry` 里给它挂 parse_arguments，再在 `tools.valid_arguments`
补对应的合法参数形状。
