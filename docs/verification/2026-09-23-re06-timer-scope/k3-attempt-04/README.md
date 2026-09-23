# 第四次尝试：恢复信号后预检通过，分组首请求超时

候选`f9ce5c6b296492b423400ad66d333784a4be13bc`，base `ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb`，模型仍为mirasim-kimi/kimi-k3、xhigh。原件`~/.finance-runtime/reviews/re06-timer-scope-qc-20260923-04/`；候选只读树仍在02目录，首尾clean且SHA不变。

## 为什么有新一次

第三次实际预检失败后，不立即重试。随后只读日志观察到设备会话由`device session mint rejected (HTTP 503)`变为`device session established`，在向用户说明新状态后，另建04目录做一次有界恢复预检。`recovery-admission.json`记录依据：共享日志最后503在11593行，最后会话建立在13611行，顺序可复核；没有关联请求ID，不认定这是上次超时根因或可用性证明。网关未修改、未重启；SDK自动重试0、模型/账号替换0。

## 实测

| 阶段 | 结果 |
| --- | --- |
| 13:57真实Pi工具/流式预检 | 2请求HTTP200；1次read执行；随机测试文本正确回传；158.502秒，PASS只属于此往返 |
| 宿主离线检查 | 沙箱边界、输出限额、续读偏移、原始输出保真、C1-C10分组恰好一次，均通过；0真实模型请求 |
| 14:00 timer组explore | 首请求6366字节/2条消息，`Request timed out.`，总124.656秒；无HTTP状态、0工具、无终稿/探针 |
| 其他组与后续阶段 | e2/consent组未启动；execute/report未启动；失败explore后启动execute被门禁拒绝，未派发模型 |

本次3请求=预检2+独审1；累计10=第一次1+第二次5+第三次1+第四次3。600秒阶段总帽未触发，触发的是120秒provider请求期限；Pi exit0仍判`BLOCKED_PROVIDER_TIMEOUT`。

首个分组请求在读取任何源码之前就失败，不能只用“大段源码使上下文膨胀”解释这次观察。也不能从单次158.502秒归纳K3总体时延或吞吐。通道曾真实可用，持续审查仍未完成。

## 未得到的结论

C1-C10仍全部not_verified，Quality未评估。三个组的完整终稿、独立探针、作者测试分账、pytest `assert 1 == 2`必红对照、17业务事务+1底层包装的独立复核均未得到。装置自检不是产品测试或QC。

14:07快照load8.78/11.29/23.87、pytest0、可用39.15GiB，彼时资源门未过。之后四叶是否开跑/完成看上层README与独立acceptance收据，不改写本次模型尝试的历史快照。

## 证据

- `gateway/receipt.json`、`gateway/events.jsonl`：真实预检完整往返。
- `explore-timer/execution.json`、`model-failure.json`、`payload-shapes.jsonl`：首请求大小、超时、无终稿及固定身份。
- `stage-gate-negative-control.json`：失败explore拒绝execute的宿主阴性检查，模型请求0。
- `report.json`：宿主阻塞回执，不是审查者签字。
- `manifest.json`：42份精选材料字节哈希；脚本/.log只追加.txt，未改原字节。完整原始运行目录保留。

本次未改产品代码、生产库或8792，未push/PR/合并/部署/迁移/删除工作树或终止其他会话进程。
