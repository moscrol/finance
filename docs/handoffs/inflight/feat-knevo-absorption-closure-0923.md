# Knevo 材料吸收续修

## 这个分支做什么
PR #877 WIP：沿原题/八问/原审稿闸修交付，不合main、不部署8792、不回补、不写生产画像。

## 决策与被否方案
- 响应体沿原绝对时限shutdown连接，拒收晚稿；不加预算/重试、不遗留后台HTTP。
- 判官首层失败也留阶段耗时；私有原返回不进公开稿/修复提示，不自动改报告或跨ID补引用。
- 工程、completed、内部passed、作者接纳分账；不改冻结题/原件凑绿。
- 展开：`docs/handoffs/2026-09-23-knevo-response-window.md`；旧协议快照保留。

## 当前状态
代码7cfc51d524681e2b9a8740e6b16e064a32006ed1已提交：工具聊天流式/非流式响应读取窗口、首层审稿记录、inspect阶段耗时。
新隔离包1/包3均failed，写手首发约75秒、终局补写约40秒后失败，未到材料判官，无有效八问稿。sidecar已停，8817无监听；两题不是新盲测分母，driver仍not_evaluated。
证据：`~/.finance-runtime/knevo-absorption-20260923/response-window-7cfc51d52/current.json`。
旧58f28c三包审稿预算耗尽/unsupported+[1]非法/超时仍保留。G1b旧答认领、包3 A/B改判不自洽未修。

## 已验证
7cfc干净定向1768P/2S/1X/0F，Ruff/收据验签通过；两个撤保护各2F，恢复正向72P。真实本地慢流证明旧idle timeout会越窗，新guard拒收并退出线程；已吐正文不重播。
两题原题保真/material_only/0 Episode工具请求，不等于全IO零。冻结原件未改。

## 未验证 / 已知边界
guard在urlopen返回后安装，不覆盖DNS/建连/响应头主动中断；本地TLS/其它HTTP实现未验。阶段elapsed含已有重试，不是单次HTTP耗时。
新live两题都未到判官，错误扁平为流式失败，缺底层异常类，不能凭时长确认watchdog触发或签判官线上预算。
无本版本全仓/前端/组合main门禁；旧8aadc收据不移签。旧f1fd 0/12、Q14语义漏判与真实Q18前置未补验。

## 下一步
1. 完整八问在原写手窗口内成稿，同时逐句绑全输入；不靠加预算/少答/恢复无限读取过关。
2. 再验材料首层与非事实复核；分清阶段总耗时、单次调用、无预算和超时。
3. 处理锚点互斥/历史认领/A-B/Q14；删句后重验八问。旧包1 c40的90>100也是内容错，不是补引用能修。

## 踩过的坑
用主树.venv-workbench/bin/python，run_main_gate从目标树cwd跑。重放带material_outputs，否则误诊report_keys。缺诊断是unknown。独立根非OS沙箱；共享harness-reference脏且旧，未接管。
