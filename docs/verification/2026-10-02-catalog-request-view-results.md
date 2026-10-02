# 工具目录请求视图：工程结果

R-20261002-13，base75af45fc0，独立feat/catalog-request-view-1002。
启动预测另存plan文档，不向其追加结果。本批工程帽0，真实模型0，旧累计96不变。

## 实际接线

`intelligence/eval/catalog_request_view.py` 是评测专用 `AgentModelClient.complete` 包装器，
默认关闭，不接入生产factory，不增加新的工具或权限，不按题型/模型名称选工具。
从按context约束的真实registry提取metadata；同次请求的工具集合、完整说明/契约、
类型敏感的参数schema及目录原文都相符才去重。短目录仍保留名称、能力、成本和新鲜度。
不相符、菜单关闭或无字节收益时保留原文；不改变API工具列表，也不改持久化历史。

启用必须有同步存证sink。先记录原始/实际messages、tools、timeout及hash，失败不发模型请求。
存证接收深拷贝，不能反向改请求。每次从原始消息生成视图；收尾无工具时完整目录仍在。
旧loop的原历史INV-R1不能单独证明实际发包；评测另存投影收据并核对HTTP内容，不冒称透明生产接线。

## 已实跑

- 在仓内的新空实现上23 failed / 15 passed；这是新增功能的身份适配器RED，不是旧产品漏洞。
- 实现后38P；再补原生GLM HTTP序列化截获、授权/读取范围和GLMAgentRuntime消费者。
- 最终新增41项通过；连同AgentEpisode、参考循环、GLMRuntime与协议共6文件：
  **271 passed / 0 failed，4.19秒**。收据20261002T055321Z-75af45fc-339aaa2ce1cd.json。
- 六项变异6/6捕获：删说明核对、弱化schema标量比较、忽略关闭、篡改输入payload、跳过存证、篡改消息历史。
  恢复原字节后重跑271项通过。全仓Ruff通过。
- `ContinuousAgentEpisode`、`HarnessReferenceLoop`、`GLMAgentRuntime` 三个实际消费者均通过脚本模型测试；
  GLM原生HTTP序列化由拦截器取出发包体与收据逐字段核对，未外呼。
- 初次相关测试命令误用了不存在的test_research_tool_registry.py，exit4、零收集，保留related.log；
  更正路径后才有上述6文件读数。测试fixture导入触发F811，改为显式fixture工厂，不压掉警告。

## 不成立的结论

- 不是真实模型效果；未独立盲评，未测收益、恢复率、token或时延。
- HarnessReferenceLoop不是正式四格中的薄ReAct；核心GLMAgentRuntime不是完整8792对话入口。
- 本地原型两个合成工具目录524→180 UTF-8字节不能外推生产token或质量收益。
- 共享httpx0.25.2≠lock0.28.1仍在；code-map为空。不能宣称干净环境全量验收。
- PR16上Python/frontend已成功但E2E仍红，不因本候选通过局部检查而豁免。

下一阶段需另登记模型请求帽、固定版本/数据/题目/预算与顺序，保留未调试及信息足够控制。
不合并、不部署、不改共享venv、不覆盖主树/Codex/PR14/15，不以布尔分数宣布通用收益。
私有证据：`~/.finance-runtime/catalog-request-view-20261002/`。
