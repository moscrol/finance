# 779b6ee2 独立复审：代码边界通过，迁移手册仍需小修

## 对象与裁决

审查 `feat/method-closed-loop@779b6ee236842d602a1effd4164fbf3f6a5c01b1`，重点为
`2f5c7a03..779b6ee2` 的四文件增量及其消费边界。独立树：
`/private/tmp/method-review-779b6ee2-pi`；本文与交接在独立文档分支
`docs/review-method-779b6ee2`，没有修改被审分支。

- 接受 779b6ee2 的整树绿单；共享 latest 被另一树覆盖不使历史收据失效。
- 接受本次两处运行代码修复及 AST 检查的收窄表述；本轮未发现这两处的新阻断。
- 迁移方案仍有两个已复现的验收缺口，执行迁移前必修。不能宣称「迁移手册全部收口」。
- 不是合并、部署、迁移授权。建议先做小型文档/帮助文案收尾，再冻结候选、补齐门禁。

## 已修项：独立复验

### 1. 指针权限失败

真实 register + activate 临时协议，root chmod 0600（保留读写、取消遍历）后调用真实 CLI：

| 场景 | rc | 结果 |
|---|---:|---|
| 正常 active | 0 | state=ok |
| 取消 root 遍历权限，普通 active | 3 | state=unreadable，stderr 有 PermissionError |
| 同条件 --print-dir | 3 | stdout strip 后空；stderr 有 PermissionError |

结束后恢复临时目录权限。`os.lstat` 保留错误分类、`stat.S_ISREG` 拒绝非普通文件的修法成立。
这比返回布尔值的 `lexists` 合适，因为业务需要区分「不存在」与「查不出」。

### 2. supersede --user 是操作范围

临时用户 alice/bob 各有协议，真实 CLI 使用显式 `--user`（非仅重跑新增的 --root 用例）：

- `--user alice --study-dir <bob>`：rc=2，说明「不属于该 root」，没有封存标记。
- `--user bob --study-dir <bob>`：rc=0，有封存标记。

范围校验位于 supersede 副作用之前，与 set_active 同用归一化后的父目录比较。接受收紧方案；
这是本机工具的操作范围约束，不宣称它是操作系统权限或服务端鉴权边界。

### 3. AST 只作漏调用/先后报警

把 cmd_history 的封存闸移到 return 后，源码仅复制到临时目录，不改被审文件。
调用原仓测试函数，结构测试报 `cmd_history` 的闸晚于写入，行为测试报「已封存协议仍接受 history」。
两条同时变红。接受当前说明：不是控制流证明；永不执行分支仍不在静态检查保证内。

## 尚存发现

### P2 / 迁移前必改：§4.1 的重复能力探针仍混淆「查不出」与「没有」

位置：`docs/superpowers/specs/2026-09-12-label-version-migration-plan.md:199-202`。

§4.3 已正确分三路，但 §4.1 仍有：

```bash
$PY "$CODE_ROOT/scripts/method_validation.py" --help | grep -qE '[{,]active[,}]' \
  && echo "链切已完成" || echo "链切未做：夜跑会用内置默认协议"
```

从文档提取原命令，在 `zsh -f` 下用临时假 CLI 注入 help exit 70：

- §4.1：打印「链切未做：夜跑会用内置默认协议」，最终 rc=0。
- §4.3：打印「查不出能力（--help rc=70）：help-boom」。

前者会误导操作人排错，与夜跑「停掉方法日步并告警」相反。建议删除 §4.1 的重复实现，
直接引用 §4.3，避免再次只修一份。§4.3 是人工诊断片段，末尾 echo 返回 0 不应当作机器放行码。

### P2 / 迁移前必改：history 核对只查目录，不验收据

位置：同文档 `:182`。

`ls "$NEW/history"` 加 `prot_ "$NEW" label_version` 证明的是目录名与协议声明，
不是 history 真正跑完。临时创建一份 v5 协议及空 `history/2026-09-12/`，没有写任何记录：

- 表中命令 rc=0，打印日期目录及 v5；
- `list_records(study, "history") == []`。

这并非只能靠手工造出：store.write_record 先创建日期目录，随后才发布记录，中途失败可能留空目录。

建议验④时保存真实 `history` 命令的退出码及输出里的 `record` 路径；然后
`mv_ report --record "$RECORD"` 校验原件，并核对它是新协议的 history、其实际
features/outcomes metadata 对应 v5、窗口与覆盖读数符合预期。加入「空目录或坏收据不通过」的
验收反例。不要靠 ls、文件名或协议自身版本替代运行证据。

## 同笔顺手清理的陈旧文字（不重新扩大功能范围）

- 迁移方案 `:69` 的 supersede 示例缺 --user/--root、`:103-104` 及 `:69` 未带解释器；
  `:210` 的回退示例也没显式用户。统一用 §4.1 的函数及操作范围，不保留第二套口令。
- 同文档 `:113` 仍称「active 非零 → 回退默认」，应写失效绑定停并告警。
- 同文档 `:143`「所有命令都带 --user/--root」与紧随其后的命令分类矛盾，改为仅适用根目录操作。
- `scripts/method_validation.py:650` 顶层帮助仍说「无绑定返回 1」，应对齐 0/4/3。
- `skills/daily-full-review/scripts/nightly_full_review.sh:52-53` 注释仍称封存指针回退默认，
  源码实际已正确拒绝。
- 被审分支 inflight 仍停在「第六轮待复验 / 再跑整树」，应由收口人按新事实覆写并压到 ≤3K。

## 收据与本轮检查

指定原始收据：`~/.finance-runtime/test-receipts/20260912T105415Z-779b6ee2.json`。
使用工作台解释器执行 `check_test_receipt.py <file> --require-target . --expect-revision 779b6ee2`，
返回 0：revision/解释器/Python/依赖指纹一致，dirty=false，target="."，
9449 passed / 0 failed / 0 error / 77 skipped，exit_status=0，依赖门未绕过。

另读原件确认：

- `20260912T103007Z-2f5c7a03.json`：9447/0/0，77 skipped，整树绝对路径目标，干净，exit 0。
- `20260912T105433Z-4427b481.json`：18 秒后的另一树运行，不能归给 779b6ee2。

独立执行：

- 全仓 Ruff exit 0；nightly `zsh -n` exit 0。
- 六文件 pytest **218 passed**：test_method_validation / test_method_validation_cli /
  test_method_flywheel / test_methodology_backtest / test_methodology_lifecycle / test_label_binding_parity。
  包含真正执行夜跑绑定段的 help 失败、旧 CLI、异常码、有效绑定回归。
- 上述额外权限、显式 --user、文档、移闸变异探针均已运行。
- 只做 merge-tree 预演：远程 main=6382c13b 是 779b6ee2 的祖先；预演 exit 0，生成 tree
  `bba8764efc6a8921a7bd74d1cc242d6fdeb3a257` 与 779b6ee2 的 tree 完全一致。
- 远程分支仍为 2f5c7a03（git ls-remote 实测），不能拿新尖给旧 PR #738 放行。

完整本轮日志在 `/private/tmp/method-review-779b6ee2-evidence/`：
`probe.py`、`probe.log`、`targeted.log`、`ruff.log`、`receipt-check.log`。
定向测试使用 `FWP_TEST_RECEIPT=0`，不争抢共享 latest；以完整日志为凭。
最初一次测试命令误用了两个不存在的文件名，收集 exit 4、没有执行测试；已纠正并完整重跑，
不算产品失败，也不计入 218。

## 推进顺序与停止条件

1. 用户确认单一收口人；其他 agent 只交付证据，不再同树写入。本人没有替用户指定。
2. 收口人修上述迁移文本与帮助文案，更新 inflight，冻结最终 SHA，更新远程 #738。
3. 在最终待合候选上补齐 Python / frontend / e2e / registry-check 等价门禁。
   779b6ee2 已有的整树绿单继续有效，但不冒充改后 SHA 的收据；不要仅因 latest 覆盖重跑。
   任一叶子红或没有结论都不合。用户点头后才合并；本轮没有执行合并。
4. 合入与运行恢复分开：先核对实际夜跑 CODE_ROOT、用户根、METHOD_STUDY_DIR 是否覆盖指针，
   再按迁移方案 §4 的①→⑦逐步授权执行，运行快照切换仍需单独确认。
   执行前重新清点待回检，不能沿用 09-12 的「0」；若非 0，暂停旧协议直接封存方案。
5. 新协议 history 要有可验证原件；首次真实夜跑要有成功 capture/skip 原因与实际选中协议，
   不能只看 active 读回或日志里的「开始 study=…」就宣布闭环恢复。

本轮未独立重跑整树全量；未运行 frontend/e2e/registry-check；未连接生产库/模型，
未查当前待回检，未改配置、迁移、推送或合并。唯一用户态写入是按项目规定经 CLI 记录收据归属纠偏，
没有触碰 method_validation 的生产协议、指针、观察或结算。

工具盘点：一次性反例脚本只为本轮审查；新发现由拥有分支接成行为回归，不另建通用工具。
「目录存在≠产物有效 / 可变索引≠原始证据」属已有证据卫生原则，本轮不另立知识清单。
