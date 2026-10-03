# 评测批时间预算：R-20261002-15工程结果

base为最新origin/main@3a2718c6c7db，独立fix/eval-batch-deadline-1002，不依赖PR16/17。
**仅工程confirmed；新增真实模型0，累计100不变。** 默认生产路径无变化，R14仍封存、无补跑。

## 实现

- `intelligence/eval/batch_deadline.py`：BatchDeadline组合墙钟与单调时钟，墙钟前跳收紧单调绝对截止；随后回拨不能再放宽。导出/导入绝对spec给同机子进程，不续一个新窗口。
- 等待每次只睡到剩余预算/检查间隔；到期不进入下一格。
- 非流式HTTP把timeout和原生deadline.expires_at都夹紧；收到晚回包时先交原始字节给存证sink，再拒绝返回。存证本身跨截止也不交付。sink的真实持久化仍由调用方负责。
- `run_supervised`把整批可信命令放到新POSIX进程组，监督预算；到期直接停止该组、回收直接子进程，正常退出也清理同组残留后代。不能只靠worker自己检查。
- `scripts/run_eval_bounded.py`独占run目录，启动/终态收据fsync并读回，拒绝同目录重用；成功0、worker失败1、截止/未启动124、launcher/storage错误2。命令/环境不进入JSON收据；stdout.log是私有子进程输出，调用方不能往里打印凭据。

## 验证过程与保留失败

1. Bridge登记写入502后只读确认未执行；断连期先冻Arena本地计划，再做原型26F19P→45P、扩展47P。当地没有Ruff，保留未运行事实；不是仓内读数。
2. 恢复后补仓内启动登记，明确已有本地原型；不冒称盲预测。仓内新接口空实现 **28F19P**，不是旧生产漏洞证明；实现后47P。
3. 加原生HTTP工作进程/本地模拟服务器，首次 **49P1F**：killpg出现PermissionError；失败保留于green-native.log。
   没有吞掉权限错误。仅在直接子进程已结束、系统PID/组/状态表确认无活成员时，允许退出竞争边界；有活成员、子进程仍跑、空/坏进程表、查询失败均失败。
   这处理的是已观察错误边界，不把「Mac僵尸组竞争」说成已独立证明的唯一根因。
4. 新增上述权限/空表检查后57P；进一步让空表fail-closed时，首相关回归 **137P1F**，因旧测试样例仍期待空表成功。修正该样例并保留独立空表拒绝测试；原失败related.log保留。
5. 最终新增 **58项**，六文件相关回归 **138 passed / 0 failed / 20.23s**。
   收据 `20261002T065114Z-3a2718c6-4433d7019f06.json`。全仓Ruff通过；未称全仓pytest/CI通过。
6. **8/8变异捕获**：忽略墙钟、HTTP不夹紧、晚回包直接返回、只杀父不杀组、接受迟到exit0、覆盖收据、丢掉迟到证据、把权限错误下活组当已清理。
   恢复源码后再回归，source SHA与变异清单完全相同。修正的是测试样例，不移签变异到另一源码。
7. 首次提交被unread-fields门禁拦下：三个耗时字段通过asdict动态序列化，静态门禁未识别其读取。改为真实显式to_dict收据序列化，不加白名单、不跳门禁；最终源码另重跑变异与回归。
8. 独立CLI烟测：按时命令exit0；卡住的批exit124，无late success输出；启动/终态收据实际存在。只运行有限本地进程。

原生HTTP测试使用127.0.0.1模拟端点并启用loopback_only、NO_PROXY；真实网络栈有本机通信，**外部/供应商请求0、真实模型0**。
已核对native HTTP工作子进程与所监督worker在同一组；到期不继续运行（OS可能短暂保留待回收的僵尸孙进程，不冒称已由我们reap）。

## 如何给未来新批接线

```bash
python scripts/run_eval_bounded.py --seconds 600 \
  --receipt-dir "$PRIVATE_ROOT/new-frozen-run" -- python path/to/new_worker.py
```

worker从`BatchDeadline.from_environment()`取同一绝对截止；用wait_until安排间隔，
用read_http包装原生非流式传输，并保留原driver的发包前物理预留、原始请求、实际body/receipt对账和响应model准入。
须用新批、新输入冻结、独占目录；**示例不是授权重跑R14，也不替代模型次数帽/身份/质量评分**。
未来真实评测driver接入与整批对账尚未验证，此处只交付可复用工具和原生传输离线接线。

## 不能外推的边界

- 非实时OS有轮询/调度与清理尾时；清理耗时独立返回，不承诺精准0延迟终止。监督者必须运行：实际主机暂停、监督者异常死亡/被外部结束后的清理没有验证。
- 禁止worker/后代daemonize、setsid或改变身份逃出监督组；不是对不可信代码的安全沙箱。
- 不能撤销供应商已接受的请求、推理或费用。监督终止可能留下已有预留但无完整响应的尝试，必须标记未完成；不能靠native provider_attempts填成实际HTTP。
- 只支持非流式完整body接线；部分读取超时没有完整body，不能伪造一份。关闭前未落盘的数据不保证恢复。
- 不改生产原生monotonic「睡眠暂停」语义；本评测层另加墙钟约束。只模拟时钟/恢复，未实际让宿主睡眠，也未杀任何生产进程。
- 共享httpx漂移仍blocked，code-map结构层empty。新CI未签全绿；PR8/16/17及正式四格/生产门不豁免。

证据：`~/.finance-runtime/eval-batch-deadline-20261002/`，含plan/registration-note、RED及全部失败、mutations、source-manifest、CLI smoke、相关测试日志。
不改旧R14 frozen文件，下一真实模型批必须另登记，不追其来源坏句堆专用规则。
