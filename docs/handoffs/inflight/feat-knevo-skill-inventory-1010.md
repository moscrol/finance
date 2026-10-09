## 这个分支做什么

在 Pi 线 `fix/knevo-pi-runtime-1010`（HEAD `708411e7d`）之上，只做不与 Pi 线相撞的 knevo 炼化：按 44 轮原文的 `load_skill` 真实返回补齐其余专项，落机制来源清单，并用六道真题验证。不碰 `finance-market-review` / `finance-mode`、`integrations/pi/`、产品代码、出口门、`agent-product-door.md`。
前身 `feat/knevo-skill-layer-1009` 已被 Pi 线超集接手并删除。决策与踩坑展开见 `docs/handoffs/2026-10-10-knevo-skill-inventory.md`。

## 当前状态

- 专项：新建 `finance-review-check` / `finance-associate` / `finance-kol-analyze`；重写 `finance-analyze-stock` / `finance-industry-track` / `finance-forecast-event`。六个都按 knevo 八章通式。
- 清单：`docs/superpowers/specs/2026-10-10-knevo-mechanism-inventory.md`。
- **六题真实首发已跑**（`a6cf2e289`，证据根 `~/.finance-runtime/knevo-skill-inventory-1010/`）：读数与裁决见 `docs/verification/2026-10-10-knevo-skill-inventory-live-results.md`。路由 6/6 读对专项、工具错误 0、截止日泄漏 0；「预览当全集」在 9/30 同题消失；剩两族表达错句（量价写成资金、阈值无来源），review-check 对它们查出 0/3。
- 据此给 review-check 的 D 维补了「逐句核一票否决清单」（六题之后写入，未经真实验证）。
- 未推送、未合并、未部署。

## 已验证 / 未验证

已验证：两份 knevo 契约测试 + 注册表绑定 + 可解析性；ruff；注册表四项 `--check`；Pi 线 HEAD 全量 21344P；六题各一次真实首发（人工核读，非盲评）。
未验证：review-check D 维修正的真实效果；派单、二看、跨轮记忆；独立盲评；与 Pi 线合并（预计只 `skills.registry.json` / `AGENTS.md` 需重生成）。

## 下一步

1. 用 r4 原答案再跑一次 review-check（同题、新 revision），看 D 维三处能否抓到。
2. Pi 线放手 finance-mode 后，并入清单 §1 标「待并入」的 OS 项；资金化措辞与阈值无来源两族归表达阶段，与 Pi 线同向，不在本分支重复做。
3. 清单 §4 的运行时项按单变量、先红后绿、先 Pi 臂后 8792 推进。
