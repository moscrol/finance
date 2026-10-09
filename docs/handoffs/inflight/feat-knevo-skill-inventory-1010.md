## 这个分支做什么

在 Pi 线 `fix/knevo-pi-runtime-1010`（HEAD `708411e7d`）之上，只做不与 Pi 线相撞的 knevo 炼化：按 44 轮原文的 `load_skill` 真实返回补齐其余专项，并把机制来源清单落成仓内台账。不碰 `finance-market-review` / `finance-mode`、`integrations/pi/`、产品代码、出口门、`agent-product-door.md`。
前身 `feat/knevo-skill-layer-1009` 已被 Pi 线超集接手并删除。决策、被否方案与踩坑展开见 `docs/handoffs/2026-10-10-knevo-skill-inventory.md`。

## 当前状态

- 新专项：`finance-review-check`、`finance-associate`、`finance-kol-analyze`。
- 重写（Pi 线未动过的三个）：`finance-analyze-stock`（含业绩点评骨架）、`finance-industry-track`（report / track 双骨架）、`finance-forecast-event`（决策者模拟不可省）。六个专项按 knevo 八章通式。
- 清单：`docs/superpowers/specs/2026-10-10-knevo-mechanism-inventory.md`（证据等级 × 落点 × 状态、四个防反向归因前提、材料矛盾、故意不抄、待做）。
- 测试：`intelligence/tests/test_knevo_skill_inventory.py`；注册表与 AGENTS.md 行已更新。未推送、未合并、未部署。

## 已验证 / 未验证

已验证：两份 knevo 契约测试 + 注册表绑定 + 可解析性 60P；ruff；注册表四项 `--check`。Pi 线 HEAD 全量 21344P（`/tmp/knevo-pi-fullgate.log`）。
未验证：新专项与重写专项的真实首发；与 Pi 线合并（预计只 `skills.registry.json` / `AGENTS.md` 需重生成）。

## 下一步

1. 真实首发：q0 同题 9/30 复盘（与 Pi 线、裸 Pi 并排）+ q1–q5 各专项一道题，证据根 `~/.finance-runtime/knevo-skill-inventory-1010/`。
2. Pi 线放手 finance-mode 后，并入清单 §1 标「待并入」的 OS 项。
3. 清单 §4 的运行时项按单变量、先红后绿、先 Pi 臂后 8792 推进。
