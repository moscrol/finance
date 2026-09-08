# 在途交接 · test/datablock-conformance

- **工单**：`docs/superpowers/specs/2026-08-29-datablock-conformance-workorder.md`
  （backlog INDEX #14，缝普查 P1 #3——普查点名杠杆最高的未覆盖缝）。
- **分支状态**：套件建成，待验收合并。基线 main@`505189e5`。
- **交付物**：`intelligence/tests/conformance_datablocks/`（blocks/baseline +
  DB-1..DB-6 + 声明完整性 + README）。零生产代码 diff；套件运行时零 import
  `ask.py`（该模块导入重，装配对账走 AST 只读源码）。
- **读数**：`193 passed, 1 xfailed`（`.venv-workbench/bin/python -m pytest
  intelligence/tests/conformance_datablocks/ -q`，2026-08-29，本分支干净树）。
  ruff 对套件目录全过。
- **验收对照**（对照 #14 占位单）：
  - 逐块参数化（`BLOCK_NAMES` 解析器数，实测 20）✅
  - 能力声明表逐块带出处（notes 承载 D3/MAINLINE_KB 旁路、D5 汇总特例）✅
  - 棘轮 baseline 规则同参照套件 ✅——且**首轮即有阳性对照**：装配对账抓到
    `MARKET_DAILY` 绕开 enabled_providers 门控（既不经构造面、全仓无
    `provider_enabled` 调用，注册表裁剪承诺落空），strict xfail 入
    `DB-6:MARKET_DAILY`，修复占位单 `2026-08-29-market-daily-gating-workorder.md`
    已立（真缺陷，非套件误报；与「授予的额度必须真的传到最下游执行者」同族）。
  - 工单不变量草案 → 落点：applies 门控（DB-3）、collect 形状与引用带回
    （DB-3）、裁剪零执行（DB-3/运行器层；装配面逐块痕迹缺口登记
    `ASSEMBLY_FINDINGS` 不入 baseline）、不静默造文本（DB-4/DB-5 的失败与
    超窗出口）、块间无隐式顺序依赖（DB-4 反序完成压测 + 串并行等价）。
  - 零 IO ✅（探针 provider；AST 只读源码）。
- **执行中的定性判断**（供验收对照）：
  1. 门控与运行器契约由 `evidence_registry`/`ask_planner` 单点强制（同工具
     缝判据），全 SUPPORTED + baseline 单条是如实读数。
  2. 装配面此前没有任何对账门（工具缝有 pre-commit `tool-reachability`），
     DB-6 补上；首跑即咬到 MARKET_DAILY——「注册了 ⇔ 够得着」在这条缝上
     此前不成立。
  3. D3/MAINLINE_KB 是「留有门控的显式旁路」（豁免构造面、单验门控在位）；
     MARKET_DAILY 两者皆无，故为缺陷而非第三个旁路。
- **红线遵守**：pathspec 提交、未合 main、未改生产代码（MARKET_DAILY 缺陷
  登记 finding+baseline+占位单，未顺手修）、零网络零 LLM。
