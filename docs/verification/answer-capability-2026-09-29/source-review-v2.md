未发现本次差异的阻断问题。

静态复核范围：仅阅读指定五个文件及所附 diff；未运行测试、代码或模型调用。因此不能代签全量工程、生产链路或实际金融答案质量。

核验结论：

- **上一轮非冻结反例已修复**  
  路径：`intelligence/services/episode_protocol.py` → `validate_episode_finish()`。  
  非 `material_only/local_only` 时，每条 binding 在同一轮解析完成后立即调用 `_validate_binding_target_and_hashes()`。因此：
  - 第一条 binding 为伪造哈希时，立即抛出 `forged_hash / INTEGRITY`；
  - 第一条为 `basis_mismatch` 或 `unknown_output` 时，也立即抛出对应错误；
  - 后续 binding 的 `E9` 或坏 claim 不再抢先降级。  
  这与新增的 `test_nonfrozen_binding_checks_keep_per_binding_rejection_order()` 一致，旧复审反例不会再降为 `unknown_evidence_ref / FORMAT`。

- **冻结范围仍先完成全量来源扫描**  
  `material_only/local_only` 下，循环阶段继续收集所有 binding 的材料锚点、历史坐标及证据范围问题；可恢复的 basis/ref 检查延后到全部来源扫描之后。  
  已有 `test_whole_finish_source_integrity_precedes_recoverable_binding_errors()`、`test_quote_error_cannot_mask_source_integrity_violation()` 覆盖该优先级。

- **未知 ordinal 没有静默删除成功路径**  
  冻结范围遇到 `E9` 时，代码虽不把它加入 `resolved_refs`，但会将原异常加入 `deferred_ref_errors`。后续：
  - 若同时有来源完整性问题，抛出 `material_source_violation`；
  - 若没有来源完整性问题，最终抛出保存的 `unknown_evidence_ref`。  
  因此不会因未知 ordinal 被临时移除而成功放行。坏 JSON、非字符串 hash、错误 claim 结构仍按前置拒收处理，符合本次范围。

- **合法 quote-only 保持**  
  没有工具证据哈希但有合法材料 claim/quote 的 binding，在冻结来源检查和抽出的目标/hash校验中仍可通过；quote 错误仍走 `material_quote_mismatch` 的可恢复路径，非法材料坐标或超范围来源仍先归为 `material_source_violation`。

- **#819 旧证据保持**  
  `frozen_prior_hashes` 仍由已验证的 `prior_evidence` 注入；旧 hash 在证据池中且属于允许的恢复来源时不会被 P6 冻结范围拒收。`test_actual_loop_sees_remapped_originals_without_tools_or_inherited_coverage()` 与 `test_frozen_scope_exempts_only_restored_prior_atoms()` 对此已有覆盖。
