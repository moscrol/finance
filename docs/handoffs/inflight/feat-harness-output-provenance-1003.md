## 这个分支做什么
P1b第一片：输出来源贯通装配/履约；不是完整题意修订。承接P1a，总方向仍acc743c84。

## 当前状态
自有树`~/fwp-wt-harness-output-provenance-1003`。基线0ac1ec6e1，实现0f1853774，最终代码/测试pin **c18d6f0fe**。本地提交，未push/合并/部署，新真实模型0。
Memory候选c33b37dc在`~/agent-memory-wt-harness-output-provenance-1003`，为避自动推送未写共享主目录；共享主线仍待授权整合。lint无新增但存量46错/31警告，详见日期快照。

## 决策与被否方案
- 来源随对象/否槽名名单：同名建议不能降用户要求；别名取必需性OR并保来源并集。
- legacy保原义/否默认全降可选：缺根请求锚点时会空答假完成；也不伪装user_request。
- 旧payload/hash不动/否重签快照：新来源变更必须通过当前授权精确核验。
- 同步迁移ID与元数据/否放松校验：全仓暴露历史续问漏迁移，保用户义务后修复。
展开：[日期快照](../2026-10-03-harness-output-provenance.md)。

## 未验证 / 已知边界
前端/浏览器E2E、独审、GitHub CI未跑；来源运行测试用脚本模型，既有HTTP回归不是新PLAN全链自然交付验收。金融质量未证，地图empty不证覆盖。
SDK只验初始来源与缺项准入，尚无PLAN接纳。题型/主体/时间窗在线修订、根请求/解释revision、合同/恢复版本分离、旧词面门退出仍待。

## 下一步
先定“根请求与解释版本”小片边界：复用PLAN、stale先拒再派工具、保权限/根预算/旧证据原件，补连续/SDK真实接纳点及HTTP专项。别搬并行补丁栈。
R17/R19封存不重跑；R18已被R19承接非漏实验；旧身份候选632P/1F仍阻塞自身。正式四格先于240，本片不放行；后续模型/发布须授权。

## 踩过的坑
锁解释器`/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python`，Keychain=0；不改共享依赖。首全量0f185为18819P/8F；基线历史170P证7项是本片回归，材料1项是拒绝提前。原失败保留。
证据根`~/.finance-runtime/reviews/harness-output-provenance-20261003/`；最终收尾看closeout.json。

## 已验证
c18干净全仓18832P/76S/2X、Ruff及full-scope精确收据通过；13新变异+9旧P1a变异同版捕获/还原SHA通过，前后54P/295P；注册表五项过。不是前端/质量通过。详见[验证报告](../../verification/2026-10-03-harness-output-provenance.md)。
