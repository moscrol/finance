# fix/e2-boundary-closeout

## 这个分支做什么
按v10分片收口E2材料边界；只动fwp-wt-e2-boundary-closeout，主树不动。

## 当前状态
应用a819ecde、作者复验归档0b18f185未变。独立QC两次均被服务阻塞：首次并发限制（3次工具读取）；用户授权第二次有界新上下文报overloaded（0工具、无测试/报告、IO未测）。两次exit0均不算通过，原件分别保留；第二次关闭自动重试，未再启动/换模型。
新原件与产品门已提交af50a26c：`docs/verification/e2-boundary-closeout/p3f1-a819ecde-independent-qc2-blocked/`。未推送/合并/部署，不跑正式T2→T3/Knevo。

## 决策与被否方案
- 真实completed用户Message、内容材料ID及message_id绑定；否决正文角色/标题猜来源。
- 共用既有窗口，只取完整消息；summary-only不可恢复，已知空投影不回读prompt。否决无限历史/片段冒充原件。
- 只对当前明确material_only接默认controller及legacy frame重建；旧注入签名兼容，不扩普通/full/local_only。
- 坐标≠事实证据≠权限；不保存正文、不改controller历史提示词。理由见`docs/handoffs/2026-09-15-e2-p3f1-source-binding.md`。
- P3f清空历史已反证撤回，不恢复；第二次服务失败后停止，不拿作者读数代签。

## 已验证
a819ecde作者干净树八文件249P/禁止尝试0，检查器15P、Ruff通过；三处撤线6F/27P、2F/31P、2F/31P，恢复33P，均0禁止。初版4F/4P与最终八针基线6F/2P不混读。
本轮协调者重验6f7eef14旧归档：首次中断9/9、作者复验16/16完整；新增归档af50a26c固定提交13/13完整。第二次审查树HEAD固定a819ecde、干净；应用/脚本/测试相对a819ecde无改动，没有新增应用测试读数。

## 未验证 / 已知边界
仍无P3f1独立裁定。相邻两文件110P但100次禁止尝试、shell exit3（83版本子进程/16用户目录扫描/1localhost:3456解析），无审计110P不能洗掉失败。
未盖controller模型历史、pending恢复/已有注入frame重验、D7权限继承、Episode历史正文交付及最终答案；余P3静态路由/日历/未知基底/旁路、local_only更多runner与原题号槽、P4–P7及全仓/前端/E2E合入门禁未完。

## 下一步
1. 服务恢复且新一次授权后，用新目录/NAME有界独立复核a819ecde；必须实际测试、计数、出报告。
2. 通过后再冻结历史提示词及正文送达小片，不能称来源全链安全。
3. harness-reference KIT检查器索引仍待安全专树补登，不动他人BUILD脏改。

## 踩过的坑
shell显式cd；pytest/ruff用主树venv。重叠集合不相加；异常前计数，Python audit非OS沙箱。原件逐字节归档、提交后验Git完整性。CLI exit0与无工具都不能推导测试通过/0禁止尝试。
