

def test_stage_artifact_round_trips_failure_detail() -> None:
    """failure_detail 必须能存活序列化往返，否则诊断信息在落盘时丢失。"""
    from intelligence.services.research_contract import StageArtifact

    artifact = StageArtifact(
        stage="company_mapping",
        status="failed",
        elapsed_ms=12,
        degrade_reason="company_mapping 执行失败（TypeError）",
        failure_detail="TypeError: 'NoneType' object is not iterable @research_owner.py:1538",
    )

    restored = StageArtifact.from_dict(artifact.to_dict())

    assert restored is not None
    assert restored.failure_detail == artifact.failure_detail
    assert restored.degrade_reason == artifact.degrade_reason


def test_stage_artifact_from_dict_tolerates_absent_failure_detail() -> None:
    """旧 artifact 没有该字段，反序列化不得报错。"""
    from intelligence.services.research_contract import StageArtifact

    restored = StageArtifact.from_dict(
        {"stage": "s", "status": "failed", "elapsed_ms": 1}
    )

    assert restored is not None
    assert restored.failure_detail is None
