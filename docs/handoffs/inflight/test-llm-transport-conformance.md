# 在途交接 · test/llm-transport-conformance

- **工单**：`docs/superpowers/specs/2026-08-29-llm-transport-conformance-workorder.md`
  （backlog INDEX #12，缝普查 P1 #1——P1 三张的最后一张）。
- **分支状态**：套件建成，待验收合并。基线 main@`b90a7f6c`。
- **交付物**：`intelligence/tests/conformance_transport/`（transports/baseline +
  LT-1..LT-5 + 声明完整性 + README）。零生产代码 diff、零网络。
- **读数**：`21 passed`（2026-08-29，本分支）。baseline 为空。ruff 绿。
- **验收对照**（对照 #12 占位单）：
  - 两 transport × 全部不变量参数化 ✅；**按 transport 参数化未按厂商名** ✅
  - 返回三元组形状与错误词表 ✅（LT-1/LT-2，含「故障种类由异常类名承载」的
    生产教训契约：CLI 空响应≠非零退出）
  - 超时不越窗 ✅（LT-3；CLI 的 max(1.0,·) 地板作为已声明偏差**钉成显式契约**
    ——地板改动会先红再逼更新声明表）
  - cancelled/预算传播 ✅（LT-4 按「预算在副作用前预占」断言：超额拒发零
    传输触碰、成功恰耗一格）
  - 凭证不入 trace ✅（LT-5：reason/台账 summary/provider repr 三面）
  - 零网络 ✅：HTTP 假 urlopen（_post_chat 原码走全）；CLI 走 runner= 注入缝
    （argv/提示词/提取原码走全）。执行中实测坑：`runner=subprocess.run`
    默认参数定义时绑定，patch 模块属性无效——已写进套件 README 防重踩。
  - 既有断言不重复不删除 ✅（分工表在 README）
- **红线遵守**：pathspec 提交、未合 main、未改生产代码、零网络零 LLM。
