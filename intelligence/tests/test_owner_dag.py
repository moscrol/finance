

def test_stage_exception_records_message_and_location() -> None:
    """阶段异常必须留下消息与代码位置。

    回归：owner_dag 只记 type(exc).__name__。真实 run 里出现过两次
    "company_mapping 执行失败（TypeError）"，消息和位置全丢，事后无法诊断。
    """
    from intelligence.workbench_skills import owner_dag

    try:
        list(None)  # type: ignore[call-overload]
    except TypeError as exc:
        detail = owner_dag._failure_detail(exc)

    assert detail.startswith("TypeError: ")
    assert "iterable" in detail
    assert "@test_owner_dag.py:" in detail


def test_failure_detail_is_bounded() -> None:
    from intelligence.workbench_skills import owner_dag

    detail = owner_dag._failure_detail(ValueError("x" * 5000))

    assert len(detail) <= owner_dag._FAILURE_DETAIL_MAX_CHARS
