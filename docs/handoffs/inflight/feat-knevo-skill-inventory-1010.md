## 这个分支做什么

基于A线（原基座708411e7d，本轮已合流82f20863e及main 8b01812bd），只做专项knevo炼化：按 44 轮原文的 `load_skill` 真实返回补齐其余专项，落机制来源清单，并用六道真题验证。不碰 `finance-market-review` / `finance-mode`、`integrations/pi/`、产品代码、出口门、`agent-product-door.md`。
前身 `feat/knevo-skill-layer-1009` 已被 Pi 线超集接手并删除。决策与踩坑展开见 `docs/handoffs/2026-10-10-knevo-skill-inventory.md`。

## 当前状态

- 专项：新建 `finance-review-check` / `finance-associate` / `finance-kol-analyze`；重写 `finance-analyze-stock` / `finance-industry-track` / `finance-forecast-event`。六个都按 knevo 八章通式。
- 清单：`docs/superpowers/specs/2026-10-10-knevo-mechanism-inventory.md`。
- **六题真实首发已跑**（`a6cf2e289`，证据根 `~/.finance-runtime/knevo-skill-inventory-1010/`）：读数与裁决见 `docs/verification/2026-10-10-knevo-skill-inventory-live-results.md`。路由6/6、工具错误0、截止日泄漏0；全量计数被消费，但q0集中带动归因仍在，q4反向量价推资金，q1两项自算同比错（应约-14.5%/-15.3%），不是只剩两族错句。review-check对三处D维问题查出0/3，详情已勘误。
- 据此给 review-check 的 D 维补了「逐句核一票否决清单」，**同题复跑 q5b（`4f147e50a`）一处都没抓到且自报「核过」**：禁止句进正文换来的是自报通过。又改为 D 维必须逐句列出原文与判定（未验证）。表达层的修法是 lint 标注回灌而非拒收，归 Pi 线表达阶段，本分支不做。
- 已推GitHub Draft #87，base为A线#86；未合main、未部署。本轮组合4933412a5，registry由技能源重建且check/table校验过；后续文档tip另计。完整工程状态看`~/.finance-runtime/pi-crossline-closeout-20261011/`同SHA收据和#87回贴。

## 已验证 / 未验证

已验证：旧专项契约/注册表定向检查与六题首发（人工核读，非盲评）。更正：21344P属于Pi旧基座708411e7d，不是本清点分支或后续Pi头的全量。新提交门禁按精确SHA收据/PR另计。
未验证：industry-track从未被六题选中；review-check D维逐句列原文后的真实效果；派单、二看、跨轮记忆、独立盲评。与A合流时registry生成物须重建，不手解JSON。

## 下一步

1. 用户已定A为成文层唯一owner：qualifications核逐句命题、词面补充、一次标注修订不拒收。本线只交反例和专项方法，B实验不扩写，不另跑同题求绿。
2. 本轮按授权推GitHub Draft，先A后本线；最终候选的全量/前端门禁独立留证，合main仍待用户。
3. finance-mode九段待并入项与清单§4运行时项另切片，先Pi验证再谈8792。
