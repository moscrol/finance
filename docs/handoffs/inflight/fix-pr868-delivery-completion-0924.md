# fix/pr868-delivery-completion-0924

## 这个分支做什么
修 #868 审查控制器的交付协议：结构化 result，完成标志由控制器绑定。基于 ce2a2713121a，原 #868 作者树、1405 封存批均未改。

## 决策与被否方案
- 选控制器填写 complete；否了再给模型一次修复回合，因该字段是提交状态，不是模型判决，无须新增请求。
- reviewer 的 stage/axis/revision/baseline/complete 全部拒收；证据和 verdict 原样保留。complete=true 不表示 PASS。
- 将结构化对象修复写入现有 prepare_pi_review_repair.py，不继续从 docs 下原型拷可执行代码。历史原件保持不变。

## 当前状态
本枝离线修补已落地，针对性测试通过。它不是新独审批次，也未改变 #868 的候选、批准额度或验收状态。请求仍累计166/209，完整新78次批需上限至少244。

## 未验证 / 已知边界
- 未跑付费模型、独审、L6或全仓四叶；不等于 #868 可合入或部署。
- prepare 默认保留旧档案的候选配置与作者输入，是迁移工具，不是当前候选准入。新批必须由原执行者另建根、固定候选/基座、重生成输入/收据和授权，不能直接执行旧 run_stage.py。
- 新协议禁止审查者填写 complete（连 true 也拒收）；prepare已同步三阶段提示词。不得拿旧提示词配新协议。

## 下一步
原 #868 执行者审阅并采用本枝相对 ce2 的补丁；新批从当前 scripts 生成，不从 sealed docs 原型覆盖。获得新增额度、完成工程与身份准入后再开新双轴，1405继续BLOCKED_NO_RETRY。

## 踩过的坑
Pi工具 schema 先于工具执行校验，给 execute 内补字段救不了工具外的必填拒收。已有测试此前只覆盖字符串接口，未覆盖1405结构化对象的 complete 必填。

## 已验证
- 43P：真Pi CLI + localhost脚本化响应，不读Keychain、不访问付费模型。覆盖双轴三阶段、最后一次保留请求、字段注入、缺证拒收、工具菜单、串并行与预算保护。
- 在临时输入中恢复1405的 complete 必填 schema，同一交付被拒；修补输入单请求交付，BLOCKED_INCOMPLETE_EVIDENCE仍保留。
- Ruff / node --check / git diff --check；原封存输入字节不变由测试核验。
