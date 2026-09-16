# P3f1：历史材料结构化来源绑定（作者候选，待独立 QC）

## 冻结范围

基线 `418f2bc910c673820d0accdec42b46be5aaa5528`；应用快照及 SHA-256 见
`candidate-source/`、`candidate-source-state.json`。本目录是**作者证据，不是独立 QC**。

只对当前输入被既有材料合同明确判为 `material_only` 的轮次，将真实 Message 中的
完整、completed 用户消息投影为不可变 `ConversationMaterials`。复用
`split_user_message` 的内容派生材料 ID，并保留来源 message_id；正文中的 `user:`、
`assistant:`、`## ` 不决定消息角色或边界。较早消息使用既有 summary 尾窗口预算，
不把半篇恢复为完整材料，不扩大到无限历史。只有 summary、无可信原记录时标 unavailable。

投影经默认 controller 传入 TaskFrame；显式空投影也有权威性，不再回读 prompt 文本。
旧注入 controller 不新增必需参数；运行时的 legacy frame 重建接收同一投影。
普通/full/local_only、保护块、放宽声明、未知边界和普通“继续”不启用投影。
旧直接调用未给结构化输入时保留 None/空串原语义。

**不覆盖** controller 模型历史过滤、pending-frame 提前恢复、已有注入 frame 的重验、
跨轮权限恢复、Episode 历史材料正文交付、最终答案或完整 P3/E2。来源坐标不等于
事实证据资格，也不是权限继承凭据。本片不保留材料正文；不能据材料 ID 已绑定就称交付完成。

## 发现顺序及读数（互相重叠，不相加）

P=passed，F=failed。除注明外，使用同一作者 IO 计数启动器；失败及其修正从不覆盖。

| 轮名 | 断言结果 | 禁止尝试 | pytest / shell exit | 含义 |
|---|---|---:|---|---|
| before | 4F / 4P | 0 | 1 / 1 | 原八针：助手伪装、用户正文角色/标题、summary-only 见红；截断针本轮已绿 |
| after-v1 | 10P | 0 | 0 / 0 | 八针+原两条合法材料正例 |
| focused-v2 | 33P | 0 | 0 / 0 | 来源坐标、窗口、快照、空投影、scope/签名、legacy重建控制 |
| regression-v1 | 249P | 0 | 0 / 0 | 八文件相邻回归 |
| orchestrator-v1 | 110P | **100** | 0 / **3** | **整体失败**；不能作为零禁止尝试收据 |
| withdraw-controller-v1 | 6F / 27P | 0 | 1 / 1 | 仅断开 controller→TaskFrame 投影；四条语义缺陷+两条新增消息坐标断言 |
| restored-controller-v1 | 33P | 0 | 0 / 0 | 恢复相同候选 |
| withdraw-role-v1 | 2F / 31P | 0 | 1 / 1 | 仅移除真实 user 角色检查 |
| withdraw-window-v1 | 2F / 31P | 0 | 1 / 1 | 仅撤销完整消息窗口筛选；这不是 before 截断针已红的证据 |
| restored-all-v1 | 33P | 0 | 0 / 0 | 全部六文件逐字节恢复候选 |
| regression-final-v1 | 249P | 0 | 0 / 0 | 原工作树候选最终八文件回归 |
| parent-finalized-eight-v1 | 6F / 2P | 0 | 1 / 1 | 基线应用+最终八针；新增来源坐标断言使原两条绿例见红，与 before 4F/4P 不同版本 |

`ruff-final-v1` exit0。`final-mutation-restoration.json` 确认最后基线实验后临时树再次
恢复六个候选文件。没有把变异应用到开发树。

初版八针完整文件未单独冻结，`before.log.txt` 保存四个失败的完整测试函数及 traceback；
不得把 `candidate-source/` 中最终测试冒充初版原件。早期 after/focused/regression
按当时日志保留，未声称每次都有独立源码快照；最终冻结收据由候选六文件快照约束。

### 100 次禁止尝试与无审计复跑

`orchestrator-v1-io.json` 原件完整保留：83 次 `subprocess.Popen` 来自
`runtime_provenance._git_output`；16 次 `os.scandir` 来自版本指纹遍历用户目录；
1 次 `socket.getaddrinfo(localhost,3456)`，现有14层栈不足以定位上层业务生产者。
不能笼统称为100次审查器误拒，也不能推出已成功访问生产数据。

随后曾不用审计启动器复跑八文件249P、相邻两文件110P、归档检查器15P。
`unrestricted-*-receipt.json` 留存这些 dirty 收据，**无完整 IO 计数，不用于隔离裁定**。
不再以解除审计限制追求绿灯；相邻两文件的零禁止尝试结论仍不成立。

## 复现与归档合同

- `launcher.py.txt` 是原启动器字节副本（归档 `.py.txt` 不作为应用源码 lint）。
  环境需设置 `E2_TEST_ROOT`、`E2_TEST_EVIDENCE`、唯一 `E2_TEST_NAME`，用主树
  `.venv-workbench/bin/python <launcher.py.txt> -q <tests...>`，stdout/stderr 和 shell exit
  各自保存。不得复用已存在的 NAME 覆盖历史。
- 启动器重定向 HOME/users/episodes/DB/KB、移除密钥环境、关闭插件自动加载，
  Python audit 在抛异常前计数，另拦 native `duckdb.connect`。**不是 OS 沙箱**，
  不认证其他 native 扩展所有 IO；测试为离线模型桩。
- 三组变异的精确 diff 留存。controller diff 相对基线（也含本片新增接口），
  真正撤线只有 `conversation_materials=None`；role/window diff 相对候选快照。
- `launch.json` 列出测试集合、基线与变异定义；测试快照留在 `candidate-source/`。
- 原文件逐字节复制，临时数据目录不归档。清单覆盖目录内全部文件，仅排除自身。
  提交后必须运行：

```bash
python3 scripts/check_evidence_archive.py \
  docs/verification/e2-boundary-closeout/p3f1-source-binding-20260915 \
  --revision <固定提交>
```

未推送、未合并、未部署；不运行正式 T2→T3/Knevo。冻结后作者复跑及独立 QC 的状态
见 `docs/handoffs/inflight/fix-e2-boundary-closeout.md`，不得从本目录标题推定通过。
