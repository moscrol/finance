# 在途交接 · docs/harness-learning-seams

更新:2026-08-22 · 执行队列四项已全部合入 main,spec 随本分支落库。树 `/Users/a77/fwp-wt-harness-learn-spec` ← `gitea/main@dd6ca952`。

## 这个分支做什么

学习合同:`docs/superpowers/specs/2026-08-22-harness-seams-to-learn-design.md`。从现有 Continuous Episode 反推还开着的缝,不是从 CC 倒推缺口。不是 08-15 吸收稿的续章。

## 当前状态

- spec §8 队列四项全部执行并合入(合并序 #318→#319→#320→#321):
  - §4.2 追问 legacy 门 → PR #318:`generate_followups` 默认 `use_llm=False`,Workbench 恒不润色,删「模板即降级」误标
  - L2 静/动态分界 → PR #319:题型规则/任务哈希/工具表移出 system 进 user JSON,`SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 标边界,指纹基线换新(措辞未动,只搬位置)
  - L3 删噪声层 → PR #320:`tool_observation_noise.prune_tool_observation`,4 可删键 / 20 必须留键,先 prune 再 budget,只作用模型副本
  - L4 dsh 收据 → PR #321:`docs/verification/2026-08-22-dsh-static-shape-audit.md`,47f9438→99f6f02 新增包 0、无须焊入,08-17 收据盖 superseded
- 合并前集成门(四分支 + #317 合成态):ruff 全绿;全量 pytest 5996 passed / 13 skipped / 0 failed;webapp lint / typecheck / 65 test / build 全绿。
- 同日初稿作废条款仍有效:禁止按初稿 L1b 加「缺 as_of 拒执行」(spec §6 / §11.3)。

## 剩余(均已在 spec / 各 PR 记档,不在本窗)

- L2 后续:`cache_control` 接线(合同两步走的第二步);openai repair 轮仍在 system 后追加后缀(既有行为,不在 L2 范围)
- §4.2:产品级「打开润色」开关未开,要开另立单
- 第 5 层 LLM compact:先有连续失败熔断器再谈
- 下次 dsh pin 变更 → 按吸收稿 §9.5 新开收据

## 不要做

不要按初稿 L1b 加「缺 as_of 拒执行」。不要把状态写回 spec §8。不要往 08-15 吸收稿叠活队列。不要覆写 `2026-08-17-dsh-static-shape-audit.md` 正文(已由 #321 盖 superseded)。
