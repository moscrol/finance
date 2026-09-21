# K3 审查执行器 v2：离线通过，真实审查额度阻塞

## 结论
固定候选 `fedce252330dce1065238f58e6c914417219ec53`，业务实现仍 `f73d2133968d51d3c782d3e12ee9aa4d0618ef45`。本包不含业务代码修改。

- 最终离线 29 项通过：18 项 worker 策略检查、5 项 Pi SDK 完整会话、6 项请求预算/凭证替身检查。无真实凭证读取、无真实模型请求；使用回环 HTTP 假服务，因此不是“零网络系统调用”。
- 真实 Spec 2.795 秒、Quality 2.770 秒，均凭证初始化 exit0、向 sidecar 发出 1 次请求、HTTP 429 `credit_exhausted_5h`、进程 exit71。未重试/切通道；两轴没有调用源码工具、没有终稿，仍 `BLOCKED_PROVIDER_QUOTA_NO_FINAL_REPORT`。
- 首尾候选 SHA 相同且 clean。业务测试/自然金融探针均 0；没有改生产写手、服务、配置，未合并或部署。旧 fedce 599P 不移签为本轮测试。

## 文件与证据
`executor/` 是运行代码原样副本，脚本加 `.txt` 后缀仅作证据，不注册成项目工具。`executor-inputs/` 是两轴输入，`live/` 是真实原件。`offline/` 是最终摘要；`offline-originals/` 保留失败和成功的完整离线原件，其中 SPEC/QUALITY.md 均是**假模型输出**，不是独立审查结论。

`executor/frozen-inputs.json` 的路径相对外部运行根；原始脚本对应 `executor/<name>.txt`，轴输入对应 `executor-inputs/<axis>/<name>`（策略另加 `.txt`）。`preliminary-live-input-sha256.json` 仅是较早准备记录，不用于最终身份校验。最终身份看 frozen-inputs 和 offline-acceptance。

最终执行文件的字节与冻结哈希已回读一致。manifest 覆盖本包完整文件集合；提交后还须使用 `scripts/check_evidence_archive.py` 核 Git blob，不能用磁盘校验冒充。

## 设计与边界
可信宿主持凭证并发送模型请求；Pi 仅加载明确模型与 read/search/git 三工具，不发现个人扩展、技能或记忆。模型工具使用单层 sandbox worker、清洁环境和路径白名单，不暴露任意 shell。第18次本地请求或400秒关闭探索，24次/600秒硬帽；最终输出由宿主保存，不给写盘工具。

预算闸门位于真实发送前，SDK和网关无自动 retry/fallback；sidecar内部尝试不可观测，不能将本地计数称为供应商全链硬帽。可信宿主不是OS沙箱；worker符号链接规范目标检查已实现，但没有专门的符号链接攻击测试。离线收口通过不保证真实模型收口，此轮真实路径在首个429即停。

本包保留HTTP 429错误正文，没有access/refresh token、账号库或成功模型输出。哈希只证明字节一致，不证明来源真实性。额度恢复时间仅是当时响应估计，不是当前可用性保证。

## 失败原件与纠正
首轮worker正向全部因Python路径解析失败；同原因的负向失败不能算拒绝成功。后改为先确认目标启动，再验拒绝。首轮两轴假服务共用计数，Quality首请求直接回报告，整组FAIL；后每轴独立假服务重验通过。

早期offline-acceptance曾过早写PASS（只有worker检查），在真实请求前已被29项完整验收替换；未保留其旧字节，不补造。未提交时对f605做Git包核验失败是收口顺序错误，不证明包丢失。summary的clean字段明确指封存前，封存写入后文档树当然不clean。

本执行器仍是任务级实验，不注册通用能力；后续需新授权、新目录、重验冻结输入、复采磁盘，并补凭证/取消/符号链接及sidecar内部请求边界审计。不得直接刷新旧目录或重启旧会话。
