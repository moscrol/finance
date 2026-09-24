# PR #884 门禁记录与首轮作废说明

## 不能把首轮当全绿

首轮固定 `480cad07057c243fad2e948b6c33dc160f9412b6`，从干净独立树执行；Node为26.0.0，Python3.12.13、pnpm10.12.1。Ruff、注册表5项、前端lint/typecheck/120项单测/build、E2E 34P/2S均结束且exit0，Python全量仍在运行时被宿主中止，**没有全量通过结论**。

宿主随后对沙箱做负面预检，发现通用 `allow network*` 下的local/remote过滤器组合放行了外连。第一次测试确实建立了到1.1.1.1:443的TCP连接，但未发送应用请求/凭证。不能把这个配置声称为外网隔离。保存的frontend/registry accepted=true仅是原执行器对命令和Git身份的结论，不证明安全边界；本次宿主拒收首轮作为最终门禁依据。

Python进程组4038被SIGTERM中止。控制器清理阶段又遇到PermissionError，故receipt.complete=false、accepted=false、checks为空；这不是产品测试失败数，也不能按已运行部分估算通过数。原stdout及控制器错误均保留。

## 修复及已验证部分

把入站(local)和出站(remote)规则分别挂在network-inbound/network-outbound。新增可复用预检 `scripts/review_probes/check_loopback_sandbox.py`，使用保留测试网地址192.0.2.1的IPv4 TCP探针，无应用数据：原坏策略exit1且external_denied=false；正确策略exit0，loopback_connect/external_denied/keychain_exec_denied三项严格true。

预检自身9例加原两验收器35例，共44P；目标Ruff通过。它不认证UDP、IPv6或其他原生钥匙串接口，更不是任意IO沙箱。旧28种runtime变异使用独立的全禁网策略，未受此新增本机CI规则错误影响。

## 最新提交的结论从哪里读

待审分支通过 `fc7fed47b` 对齐固定main `bbd53487f4cefdae97eae90f7322394d36e65462`，不是合回main。新增产品行为为零。

最终复验固定在写完本页后的完整提交，使用独立安装的Node22.23.2，不改变全局Node；运行根为 `~/.finance-runtime/reviews/pr884-gates-20260923-02/`。结果仅在真实执行后产生，不在此预填绿灯。

接手者读取该目录的 `verification.json` 和 #884 最新门禁评论，必须核对：revision等于PR当前head；Python完整scope通过；frontend每条命令及E2E通过；registry五项通过；初末身份干净；预检严格通过；原始日志hash匹配。目录/字段缺失、false或head不同即未完成，不得回退首轮。

最终收据保持树外，以免把含最终提交SHA的收据再提交一次、制造另一个未经验证的新tip。PR评论记录完整提交与摘要；本页只解释固定流程和保留的首红。没有合并或部署授权；历史C1-C8独审BLOCKED不变。

`MANIFEST.json`覆盖23个选定原件，逐字节复制；不是完整会话归档。最终全量JUnit等体积较大的原件留在上述运行根。
