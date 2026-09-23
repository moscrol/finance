# 第三次尝试：分组准备完成，实际预检失败

2026-09-23用户再次要求继续推进。候选仍固定`f9ce5c6b296492b423400ad66d333784a4be13bc`，基线`ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb`。沿用已锁定的独占detached源码树，首尾clean；运行目录改为`~/.finance-runtime/reviews/re06-timer-scope-qc-20260923-03/`，新Pi会话不继承旧结论。

## 实测与分账

- 13:44真实Pi预检：固定mirasim-kimi/kimi-k3、xhigh、流式+read/bash/write工具声明；第1请求`Request timed out.`，总122.945秒，无HTTP状态、无工具执行、无终稿。单请求期限120秒，270秒总帽未触发，Pi exit0仍判阻塞。
- 本次模型请求1，全部为预检；累计7=第一次1+第二次5+本次1。SDK自动重试0、模型替换0、网关变更/重启0。
- 分组explore未启动，execute/report亦未启动；没有审查者探针和pytest必红对照，Spec/Quality仍无独立结论。
- 13:54资源快照load16.78/29.40/44.42、pytest4、可用40.42GiB，资源门未过，没有新增全量测试。

## 已准备但未实审

`group-plan.json`与三份`prompt-explore-*.md`：timer=C7-C10、e2=C1-C3、consent=C4-C6及事务同族；C1-C10恰好覆盖一次。每组保持explore/execute/report分段，新目录、新会话，不因分组减主张覆盖。

读取限额：read正文最多120行/6000字节，按实际已返回行计算next offset；过长单行显式拒绝。bash回传正文最多6000字符，完整原始输出保留。`caps-preflight-02/receipt.json`验证限额、无跳行续读、原始输出保真与分组覆盖；第一次cap自检的99字节测试行被误当100字节，修正测试夹具后通过，原始失败命令仍在运行目录。

`sandbox-preflight/receipt.json`验证只读候选、凭据/作者报告/网络屏蔽、仅work可写。`stage-gate-negative-control.json`验证失败预检在凭据访问/模型派发前阻断分组启动，模型请求0。以上是宿主装置自检，不是独立QC或产品测试。

## 网关线索与边界

18788仍由bun进程95055监听。13:47读取共享stderr时见连续`device session mint rejected (HTTP 503)`；随后尾部出现`device session established`。13:54归档的最后200行中503计数为0，不能继续描述为“当前持续503”。日志无本次请求关联ID，服务侧503不是该模型请求收到的HTTP状态，更不能据此认定超时根因。

后续若以设备会话恢复信号准入新的预检，必须另记新尝试，不能覆盖本次失败或转移第二次成功收据。

## 证据入口

`gateway/receipt.json`与`events.jsonl`是原始请求结果；`gateway-diagnostic.json`是脱敏服务线索；`report.json`为宿主阻塞回执。`manifest.json`列32份精选材料的字节哈希，脚本和.log以.txt后缀存证，未改内容；全量原始材料保留在运行目录。固定候选、作者树均未改，未推送/PR/合并/部署/生产写入或删除worktree。
