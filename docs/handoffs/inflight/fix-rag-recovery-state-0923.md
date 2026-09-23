# RAG 恢复与双向管道补修

## 这个分支做什么
修失败重复锁存、安全诊断、完整预热/退役边界，以及长请求与stderr互堵、写入不受超时约束。

## 当前状态
代码候选 `d29d554f176336b1ae97fb6a0a2aeb72bfcd3d49`，已整合main `2edbe4c46`。
HOLD：干净候选相关430P/1F，管道变异基线80P/3F；独审中断，无最终报告。
未推送/开PR/合main/部署；主脏树、生产数据/索引与冻结runtime未动。自有进程已结束。
详证：`docs/handoffs/2026-09-23-rag-duplex-request-deadline.md`。
8792仍3b7e473575b0；16:43 readiness单次20s超时、health200。
16:45复查503：CLI协议探测超时＋快照09-23/主库09-22；worker ready，任务0/0。
装机快照16:15、主库同步18:30，尚不能断言今日入库失败。两次告警已记。

## 决策与被否方案
- 无实例错误归启动层；实例独占完整预热故障，API不重复锁存；执行锁内拒绝退役实例。
- stdin/stdout/stderr共用非阻塞selector与同一截止时间；否掉先阻塞发送再计时。
- 半条JSON超时杀进程，不能续接下一条；完整请求后的首次热超时仍保留进程。
- 不延长超时、不放宽readiness、不退化检索；保留首次红集，不循环求绿或归咎负载。

## 下一步
先定位2s/3s子进程超时，资源允许后固定届时main组合，重跑完整管道变异及合入门禁。
独审服务恢复后取正式报告，用户确认后才合main。正式夜跑后再核数据一致性。
部署另验真实模型/会话、readiness、PID/cwd和账本；不重复旧cutover或跑rag update。

## 未验证 / 已知边界
独审两次分别容量不足/额度用尽，不代表无问题。完整Python、前端/E2E未跑。
无新候选真实BGE、自然问答或部署验收。线上CLI探测超时根因未明，不能说只剩数据问题。
管道组未执行任何变异；保留还原干净临时树，路径在results.json。旧收据不移签。

## 已验证
新增9条；改前真实管道3F，提交前迭代431P；正式d29复验430P/1F（keepalive预热2s超时）。
启动恢复14组红→绿、整套29P；管道基线80P/3F，随后同代码同超时定点3P，不翻首轮红。
Ruff、提交钩子及三仓registry四项通过。证据根：
`~/.finance-runtime/reviews/rag-recovery-state-0923/d29d554f1/`。
`related/gate-unhMl4IH/pytest.json`为正式红收据；startup/transport-mutations分账。

## 踩过的坑
run_main_gate的pytest-args按空格分词，带空格-k不能靠反斜杠包装；用精确node ID。
本轮错误调用exit4/零执行保留，不计通过。没有独审报告不能把过程日志当批准。
