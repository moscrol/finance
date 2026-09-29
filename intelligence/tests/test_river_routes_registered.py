"""长河 / 连板端点必须挂在 create_app 上，且排在静态资源与 "/" 之前。

2026-09-29：app.py 被还原到 HEAD 时丢了 register_river_routes，8798 重启后
/api/river/* 全部 404，而没有任何测试报警。本测试只钉「注册了、顺序对」。
"""
from intelligence.api.app import create_app

RIVER_PATHS = {
    "/api/river/meta",
    "/api/river/entities",
    "/api/river/timeline",
    "/api/river/slice",
    "/api/river/scan",
    "/api/river/cohort",
    "/api/river/range",
    "/api/river/kline",
    "/api/limitup/calendar",
}


def test_river_routes_registered_before_static(monkeypatch, tmp_path):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_USER", "river-route-probe")
    paths = [getattr(route, "path", "") for route in create_app().routes]
    assert RIVER_PATHS <= set(paths)
    index = paths.index("/")
    assert all(paths.index(p) < index for p in RIVER_PATHS)
