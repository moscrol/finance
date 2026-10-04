# 具体纠偏交付修复实施计划

**Goal:** FINANCEWORKS-8：召回命中后，模型仍能读到用户具体纠正的内容，而非只看到抽象原则。

**Architecture:** 在 `user_memory` 提供统一的纠偏展示函数，CLI记忆块与Episode调用同一函数。正文先于补充原则；日期、归属、撤销、只读身份和现有预算继续由原模块负责。

**Tech Stack:** Python 3.12，现有纠偏JSONL、FastAPI TestClient与provider输入捕获，无新运行依赖。按用户“逐步推进”的授权在本会话执行。

## 证据与选择

固定基线 `56d0131b31ec6669e0b5c7672449f7ebd6af5b1f`。真实冻结记录已通过实际registry复现：`principle or correction` 抹掉见顶具体指标和看板具体矩阵名。证据为同日memory-recall-v2验证报告及私有delivery-v2.json。问题位于命中后的展示，与召回算法是否semantic无关。

| 方案 | 取舍 |
|---|---|
| 只交付correction | 能保具体内容，但无须丢弃有用补充原则 |
| correction在前、不同的principle附后 | 采用；单条预算优先给具体纠偏，两出口一致 |
| 重新总结或加语义分类器 | 不采用；额外模型/规则会引入新错误，也不是本缺口所需 |

保持原有仅含principle的兼容返回。仅做去除首尾空白后的完全相同文本去重；不按关键词判断哪条过时，不修改台账或选择次序。对内容超预算保留现有截断提示，不声称无限完整；不携带original字段（那是被纠正的说法）。

## 步骤

- [x] 先改 `test_user_memory.py` 原展示断言并加重复原则回归；在 `test_workbench_correction_http.py` 用合成纠偏包含具体条件与抽象原则，真实HTTP进入新的会话，捕获首个provider请求，断言两段同时送达、先具体后原则、不送original、不泄漏目录、台账不变。先确认旧代码红。
- [x] 在 `intelligence/services/user_memory.py` 新增 `correction_memory_text(record)`：

  ```python
  correction = str(record.get("correction") or "").strip()
  principle = str(record.get("principle") or "").strip()
  if correction and principle and principle != correction:
      return f"{correction}\n补充原则：{principle}"
  return correction or principle
  ```

  `_correction_lines` 使用该函数；`episode_tools.memory_lookup_runner` 用同函数取body。CLI空correction行原先跳过的规则保留，不扩大可读记录集。
- [x] 运行既有user_memory、memory_opening_prefetch、episode_tools、workbench_correction_http与personal_memory_recall_http测试。具体命令：`.venv-workbench/bin/python -m pytest -q intelligence/tests/test_user_memory.py intelligence/tests/test_episode_tools.py intelligence/tests/test_memory_opening_prefetch.py intelligence/tests/test_workbench_correction_http.py intelligence/tests/test_personal_memory_recall_http.py`。须绿，原隔离/撤销/预算合同不得退化。
- [x] 用冻结真实记录通过实际registry及CLI再次核对具体指标/矩阵名已交付，记录哈希，不改题集或默认。此探针仅证明传递；HTTP脚本模型不代签真实模型回答质量。
- [ ] 更新产品入口文档与本分支交接，独立Spec/Standards；固定SHA完整本机/前端/E2E/GitHub全部绿后合入，PR32先合。部署与真实答案验收继续按总规格执行。

## 不在本补丁中代签

产品/开发记忆分流、旧授权适用范围、同题矛盾解决、语义冷启动、真实模型答案收益均另验。不把本修复描述为记忆质量整体验收完成。
