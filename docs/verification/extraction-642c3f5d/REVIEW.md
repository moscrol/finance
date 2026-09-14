# 工单 #53 第三轮复审：642c3f5d

结论：仍需返修。规范轴 2 项 P2，需求轴 3 项 P2；没有发现收据造假或把失败读数冒充全绿。四项行为缺口已各自形成可执行红测，第五项为复跑与交接指针过期。

## 固定范围与证据

- 候选：`642c3f5d5a66ffa1a6b90a1b8c177a65ff3c79e6`；最后产品代码：`b916091e1f43838b12d63c3c55f192634385f908`。两者之间只有文档变化。
- 固定基线：`1fef3d276d0e251158803fc09d5a81e60d79241b`。完整差异 `git diff 1fef3d27...642c3f5d`，重点复审 `git diff caba87c7..642c3f5d`。
- 需求合同：`docs/superpowers/specs/2026-09-14-extraction-first-p0-workorder.md`，规范：`AGENTS.md`、台账导出合同与最终交接要求。
- 审查树：`/private/tmp/extraction-qc-642c3f5d`，分支 `codex/review-extraction-642c3f5d`。隔离于有大量其他改动的主工作区。所有行为探针只用临时 users 与固定切片。
- 本轮独立定向：8 模块 **263P / exit 0**；改动 Python 文件 ruff 与 diff-check 通过。未重新跑仓级全量。
- 独立核验既有收据：`b916091e / dirty=false / 9671P / 0F / exit 0`，`--expect-revision` 校验通过。新增测试 AST 对账 **77+39+1=117**。
- 独立旧代码回放：`caba87c7` 产品文件 + 原13条R回归，**11F / 2P / exit 1**。
- 独立变异：**19/19 RED→GREEN**，还原 **116P / exit 0**；原始115P发生在后来那条诊断用例加入之前。变异只在另一临时树运行，已恢复干净。
- 八叶原始输出均存在且读数匹配；首跑1红及随后9670P、9671P两次全绿的输出均留存。本轮 `merge-tree` 对固定基线 exit 0，无冲突；此事实不替代未来合并时的最新主线门禁。
- 代码地图正门返回结构层 `refused_empty`；没有把空图当架构结论，调用链判断来自精确源码及真实CLI探针。

## 规范轴

### N1 · P2 · 残片隔离恢复后，个人导出仍整份失败

位置：`intelligence/services/observation_script.py:815–819`、`intelligence/services/personal_export.py:82`。

R1使观察台账逐行解码并保留半汉字残片。实测正常行 → `e7 ae` 残片 → 再提交正常草稿，观察读取成功、前后两版都在；真实 `personal-export --user u1 --json` 却在整文件UTF-8解码时抛 `UnicodeDecodeError`，无导出结果。

工单 §2.3、§2.4 要求原始个人导出保留全部记录；`_append_line` 也明确把残片保留为证据。导出解码器本身是既存代码，本项定位为**本轮残片恢复方案漏验的出口**，不是声称新引入了那个解码器。修复需让正常记录可导出、坏行以可逆表示保留，不能用静默丢弃坏行来通过。

红测：`test_recovered_utf8_fragment_does_not_block_personal_export`。

### N2 · P2 · 最终复跑与在途交接仍指旧版本

位置：`docs/verification/2026-09-14-extraction-first-p0.md:304`，`docs/handoffs/inflight/feat-extraction-first-p0.md:8、29`。

收据自称最终产品版本为 `b916091e`，复跑命令却 checkout `7a86ce4e`，会漏掉全部二轮返修；交接当前顶端/下一步又指 `8410e9d3`，遗漏后续诊断修复。违反 AGENTS 的实际状态回写与工单 §5.6–7、A15 的最终交付可复核要求。保留另一agent的历史独立结论合理，但应分开标明历史被测提交、当前产品提交和文档顶端，复跑命令必须落到最终被测代码。

没有报告判断性代码气味；规范轴最高 P2。

## 需求轴

### S1 · P2 · R3找到复用草稿后，仍把确认挂回旧尝试

位置：`intelligence/cli.py:3616–3618`。

复现：A提交草稿并读取关闭 → B复用该草稿读取完成 → `confirm --from-draft <实体> --attempt-id B`。命令 exit 0、草稿版本正确，但 `extraction_attempt_id` 与确认事件的 `attempt_id` 都变成 A，按B查询没有确认事件。原因是正确选出 `mine` 后，又无条件用草稿提交时的尝试覆盖用户给的B。

违反 §2.1「确认保留关联的 source_draft_id/attempt_id」与 §2.4.1。显式选择的确认尝试B应保留，原稿出处由 `source_draft_id` 表达，二者是独立坐标。现有R3回归仅断言成功与版本，没有断言最终确认归属。

红测：`test_confirmation_keeps_requested_reuse_attempt`。

### S2 · P2 · R2仅修显式ID，自动续接仍重复生成正文

位置：`intelligence/cli.py:3408–3416、3438–3444`。

复现：有草稿，read完成收据已落盘但close抛错，尝试仍pending；原样重跑read，不补 `--attempt-id`。`open_attempt` 自动复用相同ID，却绕过只在显式ID分支内的收据查询，`build` 再执行一次并回显完整骨架；台账仍只有原来那张完成收据。

违反 §2.4.1「未传则复用同键未结束尝试」及 §2.4.4「同ID查询/重试返回原成功收据……不重新生成」。应先确定实际尝试，再统一执行完成收据判定与终态补齐；不能只靠用户照着错误提示补一个参数。数据在两次调用间变化时，新正文也会继续对应旧收据，因此断言必须覆盖实际输出和构建次数。

红测：`test_implicit_retry_replays_receipt_without_building`。

### S3 · P2 · 同尝试A→B→A，最后的A被当旧请求吞掉

位置：`intelligence/services/observation_script.py:1400–1410`。

实测同一尝试依次提交A、B、A：前三次均exit 0，但返回版本为1、2、1，第三次 `created=false`；最终有效草稿与read收据仍指版本2的B。去重遍历全历史，只按尝试+内容哈希，无法区分“重试刚才那次A”和“经过B之后重新选择A”。

违反 §2.1「同一关联键下最后一次成功提交」与 §2.4.5「草稿新版本是新动作」。需要给提交发生次序/请求身份留位置，同时保留连续A→A的重试幂等；不能把每次调用时间塞回稳定键。

红测：`test_draft_a_b_a_makes_final_a_current`。需求轴最高 P2。

## 原六项的复核边界

R1原观察台账读取反例已绿，但导出接缝尚有N1；R2显式ID重试已绿，自动续接尚有S2；R3原先“找不到复用草稿”的错误已消失，最终关联尚有S1。R4错误归属拒绝、R5落盘时复验、R6改due产生新动作的原回归与变异均通过。本轮没有把全部原修复笼统判无效，也没有把原测试变绿等同于合同全部闭合。

同秒仅改降级条件会撞script_id的现象经检查基线即已存在，未列为本轮新增缺陷。首跑抖动的处置证据可见，本轮不把“全文无关键词”单独当成无调用路径交集的证明；随后完整绿收据本身有效。

## 复跑与返修交接

四条断言在本目录 `test_review_contracts.py`，候选上实测 **4F / exit 1**。从目标工作树运行：

```bash
PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -p no:randomly /private/tmp/extraction-qc-642c3f5d/docs/verification/extraction-642c3f5d/test_review_contracts.py
```

固定切片与身份夹具来自现有 `test_observation_extraction_first.Base`。四条探针不自动纳入常规测试目录；执行方可迁入正式回归，保留断言再修实现。N2通过逐条核对最终提交与复跑命令验收。

耐久原始证据目录：`/Users/a77/.finance-runtime/reviews/extraction-642c3f5d-20260914/`，含新四红输出、三条流程JSON、残片导出探针、定向263P输出、19变异输出、旧版本11F/2P输出与最终收据校验输出。

审查未改候选产品实现、未推送、未合main、未部署或启动真人实验。下一步为执行方修复N1/N2/S1/S2/S3，再在干净最终提交上取得相应门禁。
