# Ownership v3 独立复核尝试：BLOCKED（不是审查失败裁决）

## 当前结论

用户在说明“先独立审，再单独决定合入”后回复“执行”。本轮仅授权独立复核；没有合主干、部署、真实回填、删树或购买额度许可。

固定候选仍为 `47530e20fe5c3195e50ce429b31898d57918e413`，基准仍为 `728f327160bbd2485cb635e7ef09d040d718d7b5`。**Spec 未获得审查结果；Quality 未启动；整体独立验收 BLOCKED。** 没有新独立探针、测试读数、模型结论或 PASS。前一轮作者12068P等历史证据保持原口径，不因启动审查而升级。

## 已做与两次进程的区别

1. 读取规程和固定合同，核对候选/远端main未漂移。在两个新的独立检出准备Spec、Quality，工作根分别为 `~/fwp-wt-ownership-{spec,quality}-v3-0921`，都固定47530e20且干净。准备了共同契约、两个不同侧重的prompt以及历史回填合同摘取（逐字节git show）。没有让reviewer读生产库或共享记忆。
2. 选择已登录的Codex ChatGPT订阅。`auth-route-status.txt`只记登录方式，不含凭证；未读取或复制认证文件。强制`forced_login_method=chatgpt`，清理API key环境，忽略用户provider配置；工具沙箱只授予独立证据工作目录写权，关闭工具网络，单模型会话900秒，不切付费后备通道。
3. 首次装置启动 `spec/` 在本地配置阶段0.062秒退出1：本机Codex拒绝覆盖保留provider ID `openai`；`events.jsonl`为空，无会话启动。不是模型已审一轮，也不是代码反例。原脚本保留为`run_review.initial.py`。
4. 去掉不兼容override后，独立目录 `spec-review/` 真正启动一个会话（thread ID见events）。CLI先报缺少 `/Users/a77/.local/bin/codex-code-mode-host`，随后服务返回使用额度已耗尽，8.218秒退出1。事件只有启动和错误，没有成功模型回答或工具执行。**不能从没有usage字段推导收费为零**；能确认没有主动购额或付费API fallback。
5. 配额提示原文要求“try again at Sep 27th, 2026 1:06 AM”。这是服务提示，未标时区，未独立验证刷新时刻。已停止：不再发第二阶段Quality、不重试模型、不修全局工具安装、不切其他provider。两个审查树和冻结生产候选均未改动。

## 原件

- `spec/execution.json` / `stderr.log` / `events.jsonl`：本地配置拒绝。
- `apparatus-recovery.json`：仅装置参数修正，不是加额或模型复审。
- `spec-review/execution.json`：真实会话进程、完整启动命令、超时上限、首尾Git身份与七个生产文件哈希、日志哈希。
- `spec-review/events.jsonl`：缺执行组件、usage limit、turn.failed原件。
- `blocked-review-qc.json`：根会话离线核验，仅认定“审查未产出”，不是代替reviewer写verdict。
- `review-common.md` / `*-prompt.md` / `authorization.json`：本轮范围和边界。实际渲染后的Spec输入在 `spec-review/prompt.md`。

封存时只给 `.py`/`.log` 追加`.txt`，字节不变；manifest列全部封存源文件、大小与SHA256（不含manifest本身），数量由manifest计算。原件不覆盖。旧三轮验收归档未修改。本包是失败启动的证据，不是新验收成功收据。

## 再继续需要什么

先在不发模型请求的前提下处理执行组件/CLI兼容性；然后要么待现有订阅可用后重新确认启动，要么由用户指定其他已可用通道。任何可能产生额外费用的通道先确认时间/金额上限，不继承本轮“执行”为无限预算。新尝试用新证据目录，旧失败保留；候选变化需重新固定身份。

独立复核通过后，合主干仍须用户另行确认；生产回填与部署分别验收。本轮没有从主检出、Arena或其他活跃分支接管工作。

工具沉淀：runner只是本冻结对象的有限启动/留证脚本，已随原件保全，不安装为长期调度器；“启动成功不等于有效审查”已在既有证据卫生笔记，未再造清单或修改harness-reference。
