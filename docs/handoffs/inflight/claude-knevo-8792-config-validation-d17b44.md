# 8792 撤 Grok 判官（已切生产）+ T2 路由修复（本分支已提交，待部署）

## 这个分支做什么
清单第 4 项：撤 Grok 独立判官改 K3 自审（已切生产、小样验收）。其间复验 T2 材料题被生产路由缺陷挡住（已修复未部署）。

## 决策与被否方案
| 选了 | 否了 | 理由 |
|---|---|---|
| 四个 LLM_JUDGE_* 一起注掉 | 只注 BACKEND | 只注 BACKEND 会走 `if model:` 向网关要 grok → fail-closed 全站降级（同 09-09 形状） |
| 长度闸盖六条细粒度路由（家族入口）+ query_understanding 同闸 | 只修 disclosure_scan、只闸 turn_controller | 六条同一无锚点弱点；匹配器有两个调用点，只闸一处端到端仍误判 |
| 阈值 160（去空白） | 三词相邻 | 真实短问句最长 ~69 字，材料题数百至上千字，无重叠区；相邻要求治标不治本 |

## 当前状态
- 判官切换：生产已生效，回滚锚 `~/.local/bin/start-finance-workbench.bak-20260912-pre-nogrok`；小样验收见 `1b9944dd` 交接。
- 路由修复已提交：`d0d59220`、`7ea9d958`。**生产快照仍 2efdff46，缺陷在生产还在。**
- 探针重写为 ID 配对：`c964df2e` + QC P2 修补 `fd40b55b`（传输异常全走 exit 2 无 traceback；回归 12 例含 ID 位置锁）。退出码合同见 docstring；旧「数基线」废弃。
- 事故与修复全记录（含第二调用点追记）：`docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/README.md`。

## 已验证
- 端到端：`decide_turn(T2)` → comparison/research（安全失败方向）；160/161 边界两入口一致；13/14 examples 归位（kol_review 存量 miss 生产同现，strict xfail 记着）。
- 全量 intelligence/tests：7002 passed / 2 xfailed，收据 `~/.finance-runtime/test-receipts/20260912T162655Z-1b9944dd.json`。

## 未验证 / 已知边界
- **生产没部署修复，T2/T3 复验不具备条件。** 等用户拍板：只部署这条修复（最小面），或与清单第 3 项「对齐 80 提交」合并。
- K3 自审仅一发检索题小样；材料/方法论/弃权题与长期质量（系统性偏差类）未测。
- 运行时落后 gitea/main 80 提交，那六张 PR 未部署。

## 下一步
1. 用户拍板后部署修复 → `scripts/workbench_probe.py --question-file t2-question.txt`（探针用户 `recheck-t23-0912`）复验 T2→T3，按退出码判读（非零即败）。
2. 清单第 2 项补 09-11 数据；第 3 项对齐 80 提交（做前留本次收据作锚点）。

## 踩过的坑
- 静默成功形态：`status=validated` 与 `diagnostic.state=not_requested` 同真——只看 status 的仪表永远绿。
- 改完词面匹配器先 grep 全部调用点、验证钉 `decide_turn` 端到端；第一版只钉被改那层，漏了 `query_understanding`。
- 探针续问只认 POST 发回的 run_id/message_id 对：旧轮答案、非空失败存根都能骗过「数基线/看非空」；claim run 终态先于 revise 消息，completed 而消息暂空要继续短轮询。
