# feat/adaptive-research-loop 在途

## 这个分支做什么
#72 / PR #868，以及#75独审、#76 L6。WIP，不合入、不部署。

## 决策与被否方案
- K3/GLM均可选，身份、独立证据与有限预算不变。本轮只修工装，不启动真实审查。
- 真实CLI菜单检查+跨响应状态机；否了只改prompt或顺序执行，同轮参数早于读取结果生成。
- 从封存输入校验哈希后迁移到新根，不改旧批次。决策见 `../2026-09-23-pi-review-protocol-repair.md`。

## 当前状态
工装修复已提交 `324a76f9a`：三阶段CLI开放deliver_stage；准入read结果成功后才开放write，再验落盘和final；检查先于请求记账。收据见 `docs/verification/2026-09-23-pi-review-protocol-repair/`。本轮本地提交，未推送。
私有根 `~/.finance-runtime/reviews/pr868-pi-protocol-repair-20260923-1900/`；inputs仅PREPARED_NOT_AUTHORIZED，离线测试夹具不可作真实准入。
1830批仍BLOCKED_GATEWAY_TOOL_ROUNDTRIP、4次请求；旧GLM73次超时和两旧K3原件不改。#75无独立终稿；L6仍NOT_PASSED，实际1/1/0。

## 已验证
324a76f9a干净树定向55P/0F/0E/0S，收据校验通过；新工装25项，pi0.85.1真实CLI，假HTTP27次、真实模型0次，含零请求菜单与拒绝反例。Ruff/Node/提交钩子绿，两轴沙箱绿。
旧1830批167份归档/私有原件hash无差异，新42份输入无差异；候选树干净，19899无监听。

## 未验证 / 已知边界
真实GLM对新菜单/协议的遵从性未验；合成STAGE_COMPLETE不是独审。作者测试/产品审查探针/自然题本轮均0。
候选仍31f1b40dd、base9a0227986；全量仅属7ad61a0d3，45P仅属2f4b5f089/2c61ff825。C2/C3/C5/C6覆盖、当前完整门禁和最新main联合树待验。

## 下一步
1. 新授权后用prepare_pi_review_repair.py另建输入根；重冻身份、重做沙箱和网关准入，不复用测试收据。
2. 补作者测试、行为覆盖及独立Spec/Quality终稿。真实阶段失败即停，不自动重试或扩预算。
3. 不补Q3、不重发旧自然题；合前仍需完整门禁、联合树、自然验收及用户确认。

## 踩过的坑
工具注册不等于CLI开放；同轮工具参数无结果依赖；被拒绝的后续请求不可先记成外发。测试目录中的PASS只是夹具。harness-reference/BUILD.md有他人改动，KIT索引同步留待该仓处理。
