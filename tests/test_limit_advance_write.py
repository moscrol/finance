from __future__ import annotations

import importlib.util
import io
import json
import sys
import types
from pathlib import Path
from unittest import mock

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/limit-advance/scripts/write.py"
PAYLOAD = {
    "date": "08-01",
    "trading_days": ["08-01"],
    "stocks": [{"name": "测试股", "first_date": "08-01"}],
}


def _load_module(monkeypatch):
    fake = types.ModuleType("feishu_utils")
    fake.load_config = lambda: {"app_token": "test-app"}
    fake.get_token = lambda _cfg: "test-token"
    for name in (
        "api",
        "fetch_all_records",
        "list_fields",
        "create_field",
        "delete_field",
        "get_table_id",
        "batch_update",
        "batch_delete",
    ):
        setattr(fake, name, mock.Mock())
    monkeypatch.setitem(sys.modules, "feishu_utils", fake)
    spec = importlib.util.spec_from_file_location("limit_advance_write_tested", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_partial_existing_record_update_exits_before_reporting_success(
    monkeypatch, capsys
) -> None:
    module = _load_module(monkeypatch)
    monkeypatch.setattr(module.sys, "stdin", io.StringIO(json.dumps(PAYLOAD)))
    monkeypatch.setattr(module, "get_token", lambda: "token")
    monkeypatch.setattr(module, "get_table_id", lambda *args, **kwargs: "table")
    monkeypatch.setattr(
        module,
        "list_fields",
        lambda *args, **kwargs: [
            {"field_name": "序号", "field_id": "seq"},
            {"field_name": "08-01", "field_id": "date"},
        ],
    )
    monkeypatch.setattr(
        module,
        "fetch_all_records",
        lambda *args, **kwargs: [
            {"record_id": "rec-1", "fields": {"股票简称": "测试股"}}
        ],
    )
    monkeypatch.setattr(module, "batch_delete", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "batch_update", lambda *args, **kwargs: 0)
    create_api = mock.Mock(return_value={"code": 0, "data": {"records": []}})
    monkeypatch.setattr(module, "api", create_api)

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 1
    assert "请求 1 条，实际成功 0 条" in capsys.readouterr().err
    create_api.assert_not_called()


def test_partial_create_exits_before_reindex(monkeypatch, capsys) -> None:
    module = _load_module(monkeypatch)
    monkeypatch.setattr(module.sys, "stdin", io.StringIO(json.dumps(PAYLOAD)))
    monkeypatch.setattr(module, "get_token", lambda: "token")
    monkeypatch.setattr(module, "get_table_id", lambda *args, **kwargs: "table")
    monkeypatch.setattr(
        module,
        "list_fields",
        lambda *args, **kwargs: [
            {"field_name": "序号", "field_id": "seq"},
            {"field_name": "08-01", "field_id": "date"},
        ],
    )
    monkeypatch.setattr(module, "fetch_all_records", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "batch_delete", lambda *args, **kwargs: None)
    update = mock.Mock(return_value=0)
    monkeypatch.setattr(module, "batch_update", update)
    monkeypatch.setattr(
        module,
        "api",
        mock.Mock(return_value={"code": 1, "data": {"records": []}}),
    )

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 1
    assert "新增部分失败：请求 1 条，实际成功 0 条" in capsys.readouterr().err
    update.assert_called_once()


def test_partial_reindex_exits_without_verification_success(monkeypatch, capsys) -> None:
    module = _load_module(monkeypatch)
    monkeypatch.setattr(module.sys, "stdin", io.StringIO(json.dumps(PAYLOAD)))
    monkeypatch.setattr(module, "get_token", lambda: "token")
    monkeypatch.setattr(module, "get_table_id", lambda *args, **kwargs: "table")
    monkeypatch.setattr(
        module,
        "list_fields",
        lambda *args, **kwargs: [
            {"field_name": "序号", "field_id": "seq"},
            {"field_name": "08-01", "field_id": "date"},
        ],
    )
    records = [
        {
            "record_id": "rec-1",
            "fields": {"股票简称": "测试股", "08-01": "测试股"},
        }
    ]
    monkeypatch.setattr(
        module, "fetch_all_records", lambda *args, **kwargs: records
    )
    monkeypatch.setattr(module, "batch_delete", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "batch_update", mock.Mock(side_effect=[1, 0]))

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "更新 1 条，新增 0 条" in captured.out
    assert "序号重排部分失败：请求 1 条，实际成功 0 条" in captured.err
    assert "写入验证通过" not in captured.out


def test_complete_update_and_reindex_report_actual_counts(monkeypatch, capsys) -> None:
    module = _load_module(monkeypatch)
    monkeypatch.setattr(module.sys, "stdin", io.StringIO(json.dumps(PAYLOAD)))
    monkeypatch.setattr(module, "get_token", lambda: "token")
    monkeypatch.setattr(module, "get_table_id", lambda *args, **kwargs: "table")
    monkeypatch.setattr(
        module,
        "list_fields",
        lambda *args, **kwargs: [
            {"field_name": "序号", "field_id": "seq"},
            {"field_name": "08-01", "field_id": "date"},
        ],
    )
    records = [
        {
            "record_id": "rec-1",
            "fields": {"股票简称": "测试股", "08-01": "测试股"},
        }
    ]
    monkeypatch.setattr(
        module, "fetch_all_records", lambda *args, **kwargs: records
    )
    monkeypatch.setattr(module, "batch_delete", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "batch_update", mock.Mock(side_effect=[1, 1]))

    module.main()

    captured = capsys.readouterr()
    assert "更新 1 条，新增 0 条" in captured.out
    assert "序号已按首板日期重排（1 条）" in captured.out
    assert "写入验证通过 (1 条) ✓" in captured.out
    assert captured.err == ""
