# 引擎 B 数据块缝契约符合性套件

缝：`ask_planner.DataBlockProvider`（name/label/applies/collect）×
`evidence_registry.REGISTRY` 的 N 个命名块 × `run_providers` 运行器。
块个数用解析器数（`blocks.BLOCK_NAMES` 直接枚举唯一事实源），不写死。

来源工单：`docs/superpowers/specs/2026-08-29-datablock-conformance-workorder.md`
（缝普查 P1 #3）；机制复用工具缝套件三件结构（`intelligence/tests/conformance_tools/`）。

```bash
.venv-workbench/bin/python -m pytest intelligence/tests/conformance_datablocks/ -q
```

首轮读数（2026-08-29）：`193 passed, 1 xfailed`。xfail 即阳性对照：装配对账
首跑抓到 **MARKET_DAILY 绕开 enabled_providers 门控**（既不经构造面、全仓无
`provider_enabled` 调用，注册表的裁剪承诺对它落空），以 strict xfail 入
baseline（`DB-6:MARKET_DAILY`）。同日 `R-20260829-02` 修复（owner 侧预取接
门控）后 strict xfail 转 XPASS 逼清账——棘轮闭环首次真实运转，该块转为
声明旁路，baseline 回空，套件 `194 passed`。

## 三件

| 文件 | 是什么 |
|---|---|
| `blocks.py` | 参数表（逐块）+ 能力声明表 + 探针 provider 工厂 + 装配面 AST 扫描 |
| `baseline.py` | 棘轮 baseline（首轮为空；红入账带原因、绿逼清账、只缩不涨） |
| `test_db1..db6_*.py` | 每个不变量一个文件，`parametrize(BLOCK_NAMES)` 逐块跑 |

## 不变量 → 断言落点

| # | 不变量 | 断言落点 |
|---|---|---|
| DB-1 | 注册表形状（三字段齐全、名/label 唯一、顺序单源） | 逐块 spec + `PROVIDER_NAMES == REGISTRY` 顺序 |
| DB-2 | 门控语义（None=全允许、名单=白名单、未知名 fail closed、M/V 记忆门） | 逐块 `provider_enabled` / `without_providers` / `providers_allowing_memory` |
| DB-3 | applies 为假 ⇒ collect 零调用；为真 ⇒ 恰一次且 (块文本, 引用) 原样带回 | 逐块探针 provider × `run_providers` |
| DB-4 | 汇总顺序=注册顺序（与完成顺序无关）、单块失败只降级、串并行等价 | 反序完成压测 + 逐块注错 + 双模式对比 |
| DB-5 | 窗烧穿零取数、超窗显式留痕、不造文本 | 逐块 × 串/并两模式 × 过期 deadline |
| DB-6 | 装配对账：注册 ⇔ 装配、label 一致、构造顺序=注册顺序、D3 串行门控在位 | AST 只读 `ask.py` 源码（不执行，见下） |

## 与工具缝的关键差别（判据）

门控与运行器契约由 `evidence_registry` / `ask_planner` **单点强制**，N 个块
在这两层是同一实现的 N 份配置——默认声明全 SUPPORTED、baseline 为空是如实
读数。漂移入口在**装配面**（`ask.py` 内联闭包，各块 applies/collect 独立
演化）：工具缝的装配一致性有 pre-commit `tool-reachability` 门禁看守，数据
块缝此前**没有任何对账面**——DB-6 就是它的对账门（AST 扫描 name/label 字
面量，认不出的构造形状 fail closed）。

装配面两个特例（声明 notes 承载）：D3 不经构造面、串行收尾但同受门控
（DB-6 单验其门控调用在位）；D5 构造并行取数但汇总排 D3 后（消费侧特殊
排序，运行器契约不受影响）。

已登记 finding（不改生产代码）：被 `enabled_providers` 裁剪与意图门控未命
中在装配面同样无逐块痕迹（仅 stage 计数），事后无法区分「被裁剪」与「词面
未命中」——见 `blocks.ASSEMBLY_FINDINGS`。

各块 collect 闭包的**取数正确性**（空结果口径、数据边界声明等）由各块下游
模块自己的单测管（`test_market_timeseries` / `test_market_midterm` 等），
本套件不重复。

## 怎么加新块

往 `evidence_registry.REGISTRY` 加条目后，本套件自动把它纳入参数表。新块
必须全绿；若它像 D3 一样不经 `DataBlockProvider` 构造面，先在 DB-6 的豁免
集与 `BLOCK_NOTES` 写清理由。
