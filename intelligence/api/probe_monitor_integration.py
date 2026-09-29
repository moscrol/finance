"""
Probe Monitor Integration for Workbench API

独立探针会话，不随工作会话切换而冲突停止

集成方式：在 api/app.py 的 lifespan 里调用

    from intelligence.arena.probe_session_manager import ProbeSessionManager
    from intelligence.api.probe_monitor_integration import start_probe_monitor, stop_probe_monitor, get_probe_status

    async def lifespan(_: FastAPI):
        # ... existing startup
        probe_task = await start_probe_monitor()
        try:
            yield
        finally:
            await stop_probe_monitor(probe_task)
            ...

    @app.get("/api/arena/probe_status")
    def probe_status():
        return get_probe_status()
"""
from __future__ import annotations
import asyncio
import os
from pathlib import Path

# 全局单例
_probe_manager = None
_probe_task = None

def _should_enable():
    # 默认关闭，需环境变量开启，避免无意义消耗
    return os.environ.get("ARENA_PROBE_MONITOR_ENABLED", "").lower() in ("1","true","yes")

async def start_probe_monitor():
    global _probe_manager, _probe_task
    if not _should_enable():
        print("[probe-monitor] disabled (set ARENA_PROBE_MONITOR_ENABLED=1 to enable)")
        return None
    try:
        from intelligence.arena.probe_session_manager import ProbeSessionManager
    except ImportError as e:
        print(f"[probe-monitor] import failed: {e}")
        return None
    _probe_manager = ProbeSessionManager()
    _probe_manager.ensure_session()
    # 首次跑一轮建立基线
    try:
        await _probe_manager.run_once()
    except Exception as e:
        print(f"[probe-monitor] initial run failed: {e}")
    # 后台常驻
    interval = float(os.environ.get("ARENA_PROBE_MONITOR_INTERVAL", "300"))
    _probe_task = await _probe_manager.start_background(interval=interval)
    print(f"[probe-monitor] started independent session { _probe_manager.session_id } interval={interval}s")
    print(f"[probe-monitor] 切换工作会话不会冲突停止，因为 session_id={_probe_manager.session_id} 完全独立于 Workbench ConversationStore")
    return _probe_task

async def stop_probe_monitor(task=None):
    global _probe_manager, _probe_task
    t = task or _probe_task
    if t:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        print("[probe-monitor] stopped")
    if _probe_manager:
        _probe_manager.stop_background()
    _probe_task = None

def get_probe_status():
    if _probe_manager is None:
        try:
            from intelligence.arena.probe_session_manager import ProbeSessionManager
            mgr = ProbeSessionManager()
            return mgr.get_status()
        except Exception as e:
            return {"enabled": False, "error": str(e), "note": "独立会话未启动，设置 ARENA_PROBE_MONITOR_ENABLED=1"}
    return _probe_manager.get_status()
