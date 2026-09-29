**阻断：非材料协议新增了将伪造哈希从 INTEGRITY 降为 FORMAT 的路径。**

- **路径**：`/Users/a77/fwp-wt-8792-answer-closeout-0929/intelligence/services/episode_protocol.py`，`validate_episode_finish()` 的第一遍 ref 解析与第二遍 `forged_hash` 检查。
- **输入反例**：非材料合同（`grounding_scope(...) is None`），无题设计算，`evidence=()`；合同包含 `direct_answer/evidence` 与 `evidence_boundary/user_premise`：
  ```json
  {
    "status": "partial",
    "draft": "本轮未取得可核验证据。",
    "gaps": ["尚缺事实证据"],
    "bindings": [
      {
        "output_id": "direct_answer",
        "basis": "evidence",
        "evidence_hashes": ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
        "gap": ""
      },
      {
        "output_id": "evidence_boundary",
        "basis": "user_premise",
        "evidence_hashes": ["E9"],
        "gap": ""
      }
    ]
  }
  ```
- **为什么阻断**：父版处理第一条 binding 时即抛出 `forged_hash / INTEGRITY`。当前版把该检查移至第二遍，但非冻结范围的未知 ordinal 仍在第一遍立即抛出，因此第二条的 `E9` 抢先产生 `unknown_evidence_ref / FORMAT`。依据本文件的 `REJECTION_RESPONSES`，原本禁止回灌、禁止恢复的伪造来源现在允许回灌和恢复。这是本次重排新增的非材料兼容性退化，不是要求修复既有的全仓错误优先级。

**静态审查范围**：仅阅读指定五个文件并对照所附 diff；未执行测试、代码或模型调用，未检查外部依赖实现及生产。本轮来源 pass 仅覆盖已能解析、必要时已能 render 的 bindings；坏 JSON、错误 claim 结构及其他前置拒收不在其保证范围内。上述反例的 binding/claim 结构合法，不属于该边界之外的情况。
