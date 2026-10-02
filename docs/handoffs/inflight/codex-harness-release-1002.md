## 这个分支做什么

合成可审查的 harness 发布候选，保留模型决定任务和工具的空间；不把工程测试冒充模型净收益。

## 决策与被否方案

- 保留 PR8、PR10、PR11–14、PR15；排除 #20 档位硬政策、11/16/17/19 硬语义路由、A7、数字字段候选和工具差分分支。
- 身份、权限、预算、证据版本及错误反馈不降级；evidence_read 仍默认关闭且须显式授权，不改固定流水线。
- 范围以 `docs/handoffs/2026-10-02-harness-release-scope.md` 为准；10/1 派生快照修复不是代码部署。

## 当前状态

- 接手树 `/tmp/harness-opt/tmp/arena-harness-release-1002`，分支 `fix/harness-release-1002-takeover`，起点 `e25381b24`；最新源码提交 `1f8a8efb3`。
- `beff372c6`：只在子研究收件箱成功认领并追加消息后记展示覆盖；嵌套正文按实际可见字符计，不奖励重读，不跨 Episode 泄漏。
- `1f8a8efb3`：两条快照入口复用交易日三态，历史/未来/休市/未知请求不取现货；保留有真实日期的历史 DuckDB，未知候选 fail closed。
- 原发布树 `codex/harness-release-1002@e25381b24` 与三份未跟踪文档均未改；没有 push、合入 main、部署或业务库改写。

## 已验证

- 干净源码 `1f8a8efb3`：锁版本本树 Python，focused **292 passed**；补 conformance 时钟后迭代 **320 passed**，全仓 Ruff/hooks 通过。
- 本树新建独立 Python 环境，doctor 含 frontend=ready、无依赖漂移；隔离 Node 22.23.3 / pnpm 10.12.1，不升级共享环境。
- 有效 RED：证据 3 failed/1 passed；快照 15 failed/1 passed。修复后的完整/部分投递、未投递、拒收/丢弃、隔离及日期边界已回归。
- 完整证据、收据与命令见 `docs/verification/2026-10-02-harness-takeover.md`。

## 门禁与未覆盖

- 最终候选门禁的动态结果以 `/tmp/arena-harness-validation-1002/final-candidate-v2/` 专用产物及其 revision/clean/scope 为准；本文不声明全量绿。旧 f4 full=19727 passed/4 failed/99 skipped/2 xfailed；不放行。
- 尚无真实模型六条、多轮净收益、2×2/留出题和独立 reviewer 证据；不能据工程绿启用实验能力。GitHub checks 尚未执行，生产健康未重新验收。

## 下一步与坑

- 用最终 SHA 完成整仓 Python、前端/E2E、registry，再补独立复核及有界真实多轮验收；所有证据齐后再请求用户确认 PR/main/生产切换。
- full 收据须验 `--require-full-scope --expect-revision`，不读共享 latest 冒认本轮；专用树验证期间不得移动 HEAD。
- 历史交付须保留 served/source 日期并标 historical；latest/meta 不倒退，不能从缺行猜休市。
- 不提交凭据、用户原始数据、运行产物或虚拟环境；不删枝、吊销 token、写预测台账。`deploy_workbench_runtime.sh` 不是 detached 部署器。
