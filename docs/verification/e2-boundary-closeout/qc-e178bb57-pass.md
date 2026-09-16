P3a 局部复审通过：本轮范围内未发现 verified finding。结论仅覆盖明确 `material_only` 的 Episode 装配与合同约束，不构成产品安全放行。

审查版本固定为 `e178bb57c751e97f9f1c231ce253221d0b892b58`，处于 detached HEAD；开始、结束均 clean，暂存区和工作区 diff 均为空。审查了 `8d1b3573..HEAD` 三个应用文件的全部变更、新增 `test_e2_material_freeze.py`，并对照设计 D3/D4/D5、门页及 P2 独立通过记录。未修改应用、原题或 46 针，未调用其他 agent、金融 API，未操作生产用户态，未合并、推送或部署；报告由宿主 `-o` 保存。

实际测试使用指定解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，设置 `FWP_TEST_RECEIPT=0`，关闭 pytest 缓存和 Python 字节码写入：

- 指定六文件：**180 passed，2.62 秒**。
- 相邻 `test_episode_protocol.py`：**42 passed，0.18 秒**。
- 合计 **222 passed**。未将作者自测记录计入本轮结果，也未声称运行全仓测试或正式多轮验收。

独立反例核验结果如下：

1. **冻结三元组一致。** 显式传入 `web_search/market_data`，最终授权、证据计划 requirements 和所有输出槽 evidence_types 均为空。限制在 mandatory 能力回补之后施加，后续 prior/prime 槽不能把读取要求带回来。见 [episode_factory.py:657](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/episode_factory.py:657)。

2. **复制与恢复不能重新加读权限。** 分别重加 `memory_lookup`、非 mandatory 的 optional requirement、输出槽工具证据，经过 `replace`、`from_dict` 和兼容构造三条路径，共九种组合均被 `ResearchContractError` 拒绝；正常序列化往返保持相等。不是只检查 mandatory 而漏掉 optional。见 [research_contract.py:909](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/research_contract.py:909)。

3. **范围声明未冒充事实证据。** 独立使用连续原题号 17/18，得到对应 `answer_q17/answer_q18`；原 T2 八题也逐一保留题文、无合成 memo 槽。题目槽 grounding 为 `evidence`，仅 `evidence_boundary` 为 `user_premise`。这证明装配投影正确，不代表最终材料锚点校验已经完成。见 [episode_factory.py:758](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/episode_factory.py:758)。

4. **短路和旁路授权有效。** 给 `_roots`、直接预取入口的收集函数设置一调用就失败的替身，均未触发；注册表工具、预取与计算 loader 为空。另行构造注册表强塞三种能力，故意标成 `local/stable`，全部在 runner 前拒绝，记录 `authorize`、capability 和 tool_call_id，调用集合保持为空。见 [episode_tools.py:978](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/episode_tools.py:978)、[research_tool_registry.py:1118](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/research_tool_registry.py:1118)。

工厂的静态 KB 调用替身未触发，未分型 conversation、perspective、stance、retrieval 背景均被清除；指定测试中的 full 与普通问题兼容检查通过。

独立探针出现过两处预期不成立，已核明而未掩盖：不连续题号 17/29 在上游解析时只留下 q29，该解析文件本轮未变，不列作新增 P3a 回归；原 T3 单独解析为 `state_unavailable`，不能直接期待八个 material-only 输出槽。后者属于明示延后的可信续轮恢复。修正探针适用前提后，相关局部检查通过。

`local_only` 实际 IO、全入口注入及确定性旁路、可信恢复与歧义澄清、最终材料锚点和逐题交付仍未验收；本次通过不覆盖这些能力。