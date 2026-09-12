# method-closed-loop · 3393915e 质检

## 这个分支做什么
固定3393915e审1e5ad6f6/310e9f4e/3393915e，只写独立报告，不改实现/装机/生产。

## 决策与被否方案
- 认可核心修复，保留权限/归属/迁移文档问题；不因新反例否认原修复，也不因全量绿忽略反例。
- AST同函数出现性作补充，不冒充所有写入前必经闸；不要求做复杂通用控制流分析。
- 详情`docs/handoffs/2026-09-12-method-closed-loop-3393915e-review.md`。

## 当前状态
作者树开审已是2f5c7a03且干净，receipts修复已由对方提交。本轮不审该笔；3393915e仅改迁移文档，确未裹入receipts.py。用户消息中的“仍未提交/全量未跑”已过期。本枝仅审查文档，不推不合。

## 已验证
冻结代码定向86P/10.52s；Ruff、zsh语法通过。收据`~/.finance-runtime/test-receipts/20260912T103505Z-3393915e.json`。
真临时旁路库：history封存前rc0，封存后rc2且已有history/standing逐文件哈希不变；capture报封存。
真实夜跑函数+daily/notify spy：坏JSON结构/目录/悬空链/坏协议/已封存/help失败均不调用daily且告警；unset/有效/真旧CLI正常分流。
后续2f5c7a03整树收据`20260912T103007Z-2f5c7a03.json`=9447P/0F/77skip、dirty=false、exit0，已核实但非本轮执行，不认证其receipts代码质量。

## 未验证 / 已知边界
- P2：store.py:269 lexists仍把权限错误当不存在。有效指针的协议根去掉遍历权限，active两模式都rc4/无告警；本轮没证明可进一步写错观察。
- P2：supersede --user u1 --study-dir other协议仍rc0、封存other；root仅回读active，文档却称它限定协议写入根。需明确合同或补写前归属检查。
- P2：迁移MV/MB标量组合命令在zsh rc127；register后status缺standing，不能验卡片；history后普通status无版本字段；report应--record而非--study-dir；枚举行仍伪命令；文档help失败仍误称无能力。
- AST改进项：闸移到return后，结构谓词仍绿，内存变异能写history。现有history行为测试可抓住，不是当前代码修复失效。
- 未跑真实夜跑、迁移/共享库重建、封存后存量recheck结算、断电/并发封存模型；未复验后续receipts。

## 下一步
用户确认唯一收口人后修权限/归属合同与文档，改active help旧码，压inflight（仍5145字节）；对新头复验，再决定门禁。推荐method/夜跑作者收口，对方交付receipts SHA后停同树写，但本会话未代用户调度。

## 踩过的坑
参数合法≠完成验收；lexists≠只对ENOENT返回假；--user存在≠限制写入对象；结构有调用≠调用会执行。证据`/tmp/method-qc-3393915e-evidence/`；临时权限finally恢复，变异只在内存，未落实现回归门。
