"""
运行中模型漂移检测集成

在 GLMModelClient.complete 和 OpenAI Agents SDK 返回后，自动指纹检测

用法：在 api/app.py lifespan 里
    from intelligence.services.model_drift_integration import install_drift_detection
    install_drift_detection()

之后每个 run 的 LLM 回复都会被记录到 run_dir/model_drift.jsonl
并可通过 /api/arena/probe_status 或 /api/runs/{run_id}/drift 获取
"""
from __future__ import annotations
import os
import glob
from pathlib import Path
from typing import Dict

_detectors: Dict[str, object] = {}
_enabled = False

def _should_enable():
    return os.environ.get("ARENA_MODEL_DRIFT_DETECTION", "").lower() in ("1","true","yes") or os.environ.get("ARENA_PROBE_MONITOR_ENABLED", "").lower() in ("1","true","yes")

def _find_run_dir(run_id: str) -> Path | None:
    if not run_id or run_id=="unknown":
        return None
    # 1. try default user
    try:
        from intelligence.services.run_store import RunStore
        for uid in [None, "default", os.environ.get("WORKBENCH_USER_ID")]:
            try:
                store = RunStore(user_id=uid)
                rd = store.run_dir(run_id)
                if rd.exists():
                    return rd
            except Exception:
                continue
    except Exception:
        pass
    # 2. scan filesystem ~/.local/share/finance-arena/users/*/runs/<run_id>
    candidates = glob.glob(str(Path.home()/".local/share/finance-arena/users/*/runs"/run_id))
    if candidates:
        return Path(candidates[0])
    # 3. scan /Users/a77/.local/share...
    # 4. fallback to /tmp? just return None
    return None

def get_detector(run_id: str, run_dir: Path | None = None):
    from .model_drift_detector import ModelDriftDetector
    if run_id not in _detectors:
        if run_dir is None:
            run_dir = _find_run_dir(run_id)
        _detectors[run_id] = ModelDriftDetector(run_dir=run_dir, run_id=run_id)
    else:
        if run_dir and getattr(_detectors[run_id], 'run_dir', None) is None:
            _detectors[run_id].run_dir = Path(run_dir)
        # 如果 run_dir 后来找到了，补上
        if getattr(_detectors[run_id], 'run_dir', None) is None:
            found = _find_run_dir(run_id)
            if found:
                _detectors[run_id].run_dir = found
    return _detectors[run_id]

def install_drift_detection():
    global _enabled
    if _enabled:
        return
    if not _should_enable():
        print("[drift-detection] disabled (set ARENA_MODEL_DRIFT_DETECTION=1 or ARENA_PROBE_MONITOR_ENABLED=1)")
        return
    _enabled=True
    print("[drift-detection] installing hooks for GLM and OpenAI runtimes")

    # Patch GLMModelClient.complete
    try:
        from intelligence.runtime import glm_agent_runtime
        orig_complete = glm_agent_runtime.GLMModelClient.complete

        def patched_complete(self, *, messages, tools, timeout):
            result = orig_complete(self, messages=messages, tools=tools, timeout=timeout)
            try:
                run_id = getattr(self, '_current_run_id', None) or os.environ.get("CURRENT_RUN_ID", "unknown")
                run_dir = _find_run_dir(run_id)
                detector = get_detector(run_id, run_dir)
                text = ""
                if hasattr(result, 'content'):
                    text = result.content or ""
                elif isinstance(result, dict):
                    text = result.get('content','')
                else:
                    text = str(result)[:2000]
                if text:
                    model_hint = getattr(self, '_model', None) or getattr(result, 'model', None) or "glm"
                    detector.observe(text, step=f"glm_complete_{len(detector.fingerprints)}", model_hint=str(model_hint))
            except Exception as e:
                print(f"[drift-detection] patch error: {e}")
            return result

        glm_agent_runtime.GLMModelClient.complete = patched_complete
        print("[drift-detection] patched GLMModelClient.complete")
    except Exception as e:
        print(f"[drift-detection] failed to patch GLM: {e}")

    # Patch OpenAI Agents SDK runner
    try:
        from intelligence.runtime import openai_agents_runtime
        orig_run = openai_agents_runtime._run_openai_agents_sdk

        def patched_run(request):
            result = orig_run(request)
            try:
                run_id = getattr(request, 'run_id', None) or os.environ.get("CURRENT_RUN_ID", "unknown")
                run_dir = _find_run_dir(run_id)
                detector = get_detector(run_id, run_dir)
                text = ""
                if hasattr(result, 'content'):
                    text = result.content or ""
                elif hasattr(result, 'answer'):
                    text = getattr(result.answer, 'content', '') if hasattr(result.answer,'content') else str(result.answer)
                else:
                    text = str(result)[:2000]
                if text:
                    detector.observe(text, step=f"openai_{len(detector.fingerprints)}", model_hint="openai")
            except Exception as e:
                print(f"[drift-detection] openai patch error: {e}")
            return result

        openai_agents_runtime._run_openai_agents_sdk = patched_run
        print("[drift-detection] patched openai_agents_runtime._run_openai_agents_sdk")
    except Exception as e:
        print(f"[drift-detection] failed to patch OpenAI: {e}")

    # Also patch TurnOrchestrator to set current run_id
    try:
        from intelligence.runtime import conversation_orchestrator
        orig_run_turn = conversation_orchestrator.TurnOrchestrator.run_turn

        async def patched_run_turn(self, *args, **kwargs):
            run_id = kwargs.get('run_id') or (args[0] if args else "unknown")
            if hasattr(run_id, 'run_id'):
                run_id = run_id.run_id
            run_id_str = str(run_id)
            prev = os.environ.get("CURRENT_RUN_ID")
            os.environ["CURRENT_RUN_ID"]=run_id_str
            # 同时给 GLM client 打上 _current_run_id 便于追踪
            try:
                return await orig_run_turn(self, *args, **kwargs)
            finally:
                if prev is None:
                    os.environ.pop("CURRENT_RUN_ID", None)
                else:
                    os.environ["CURRENT_RUN_ID"]=prev

        conversation_orchestrator.TurnOrchestrator.run_turn = patched_run_turn
        print("[drift-detection] patched TurnOrchestrator.run_turn")
    except Exception as e:
        print(f"[drift-detection] failed to patch TurnOrchestrator: {e}")

def get_all_detectors_report():
    return {rid: det.get_report() for rid, det in _detectors.items()}

def get_detector_report(run_id: str):
    det = _detectors.get(run_id)
    if det:
        return det.get_report()
    # Try load from disk
    try:
        run_dir = _find_run_dir(run_id)
        if run_dir:
            drift_file = Path(run_dir)/"model_drift.jsonl"
            if drift_file.exists():
                lines=drift_file.read_text(encoding='utf-8').splitlines()
                history=[__import__('json').loads(l) for l in lines if l.strip()]
                return {"run_id": run_id, "from_disk": True, "run_dir": str(run_dir), "history": history[-10:], "total_steps": len(history), "has_drifted": any(h.get('is_drift') for h in history)}
        # fallback scan all
        import glob
        for p in glob.glob(str(Path.home()/".local/share/finance-arena/users/*/runs/*/model_drift.jsonl")):
            if run_id in p:
                lines=Path(p).read_text(encoding='utf-8').splitlines()
                history=[__import__('json').loads(l) for l in lines if l.strip()]
                return {"run_id": run_id, "from_disk": True, "run_dir": str(Path(p).parent), "history": history[-10:], "total_steps": len(history), "has_drifted": any(h.get('is_drift') for h in history)}
    except Exception as e:
        return {"run_id": run_id, "error": str(e)}
    return {"run_id": run_id, "status": "no-data"}
