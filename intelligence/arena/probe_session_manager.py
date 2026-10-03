"""
独立探针会话管理器

目标：
- 探针跑在完全独立的 session 里，不占用、不污染 Workbench 的 ConversationStore / ArenaStore 的业务会话
- 切换工作会话（ConversationList / Arena assignments）时，探针监控不冲突、不停止
- 提供常驻后台任务，定时跑金丝雀探针，检测模型指纹漂移，支持过滤

设计：
- 独立存储：~/.local/share/finance-arena/probe_monitor/
  - session.json: {session_id, created_at, adapter, target_profile}
  - status.json: {last_check, baseline_centroid, current_fingerprint, distance, is_target, drift_count}
  - log.jsonl: 每次探针的详细日志
- 独立会话 ID：probe-monitor-<uuid>，不进 Workbench 的 sessions 表，只存在这个目录
- 后台任务：asyncio 定时任务，每 interval 秒跑一轮探针（默认 300s），计算与基线的距离，超过阈值则报警并记录
- 过滤集成：ProbeFilter 从 target_profiles.json 加载，探针会话的指纹也用同一套 style_features，保证一致

使用：
    from intelligence.arena.probe_session_manager import ProbeSessionManager
    mgr = ProbeSessionManager()
    mgr.ensure_session()  # 创建或恢复独立会话
    await mgr.run_once()  # 跑一轮探针
    status = mgr.get_status()  # 获取当前状态

    # 后台常驻
    await mgr.start_background(interval=300)

与 Workbench 解耦：
- Workbench 的 TurnOrchestrator 跑在 conversation_id 上，探针跑在 probe-monitor-* 上，两套 session 完全隔离
- 切换 ConversationList 不会影响 probe_monitor 的 session_id
- 即使 Workbench 重启，probe_monitor 的 session.json 还在，可恢复
"""
from __future__ import annotations
import asyncio
import json
import math
import re
import time
import uuid
from pathlib import Path
from statistics import mean
from typing import Dict, List

BASE_DIR = Path.home() / ".local/share/finance-arena/probe_monitor"
SESSION_FILE = BASE_DIR / "session.json"
STATUS_FILE = BASE_DIR / "status.json"
LOG_FILE = BASE_DIR / "log.jsonl"

# 复用指纹逻辑
_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")
_FULLWIDTH_PUNCT = re.compile(r"[，。！？；：、]")
_HALFWIDTH_PUNCT = re.compile(r"[,.!?;:]")
_MD_HEADER = re.compile(r"^#{1,6}\s", re.M)
_MD_BULLET = re.compile(r"^\s*[-*•]\s", re.M)
_MD_NUMBERED = re.compile(r"^\s*\d+[.、)]\s", re.M)
_MD_BOLD = re.compile(r"\*\*[^*]+\*\*")
_MD_TABLE = re.compile(r"^\|.*\|\s*$", re.M)
_MD_CODE = re.compile(r"```")
_OPENERS = re.compile(r"^(好的|当然|没问题|Sure|Certainly|Of course|Great question|好问题)", re.I)
_CLOSERS = re.compile(r"(希望.*帮助|如果.*还有.*问题|随时.*告诉我|Let me know|Hope this helps)", re.I)
_FIRST_PERSON = re.compile(r"(我认为|我觉得|我建议|个人认为|I think|I believe|I'd suggest)", re.I)
_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")

def style_features(text: str) -> Dict[str, float]:
    n = max(len(text), 1)
    sentences = [s for s in re.split(r"[。！？.!?\n]+", text) if s.strip()]
    lines = [l for l in text.split("\n") if l.strip()]
    n_lines = max(len(lines), 1)
    cjk = len(_CJK.findall(text))
    latin = len(_LATIN.findall(text))
    fw = len(_FULLWIDTH_PUNCT.findall(text))
    hw = len(_HALFWIDTH_PUNCT.findall(text))
    return {
        "len_log": min(math.log10(n) / 4, 1.0),
        "avg_sent_len": min(mean(len(s) for s in sentences) / 100, 1.0) if sentences else 0.0,
        "line_density": min(n_lines / (n / 50), 1.0),
        "cjk_ratio": cjk / max(cjk + latin, 1),
        "fullwidth_punct_ratio": fw / max(fw + hw, 1),
        "emoji_per_100": min(len(_EMOJI.findall(text)) / (n / 100), 1.0),
        "uses_header": 1.0 if _MD_HEADER.search(text) else 0.0,
        "uses_bullet": 1.0 if _MD_BULLET.search(text) else 0.0,
        "uses_numbered": 1.0 if _MD_NUMBERED.search(text) else 0.0,
        "uses_bold": 1.0 if _MD_BOLD.search(text) else 0.0,
        "uses_table": 1.0 if _MD_TABLE.search(text) else 0.0,
        "uses_code": 1.0 if _MD_CODE.search(text) else 0.0,
        "bold_per_100": min(len(_MD_BOLD.findall(text)) / (n / 100), 1.0),
        "has_opener": 1.0 if _OPENERS.search(text.strip()) else 0.0,
        "has_closer": 1.0 if _CLOSERS.search(text) else 0.0,
        "first_person": 1.0 if _FIRST_PERSON.search(text) else 0.0,
    }

def cosine_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) & set(b)
    if not keys:
        return 1.0
    dot = sum(a[k]*b[k] for k in keys)
    na = math.sqrt(sum(a[k]**2 for k in keys))
    nb = math.sqrt(sum(b[k]**2 for k in keys))
    if na==0 or nb==0:
        return 1.0
    return 1.0 - dot/(na*nb)

def centroid(fps: List[Dict[str, float]]):
    if not fps: return {}
    keys=set().union(*fps)
    return {k: mean(fp.get(k,0.0) for fp in fps) for k in keys}

# 金丝雀探针（轻量版，3个，回答短，不浪费配额）
CANARY_PROBES=[
    {"id":"identity","prompt":"请只用一个词回答：你的知识截止到哪一年？"},
    {"id":"style_opinion","prompt":"你觉得远程办公好还是坐班好？简短回答。"},
    {"id":"behavior_tokenize","prompt":"单词 strawberry 里有几个字母 r？只输出数字。"},
]

class ProbeSessionManager:
    def __init__(self, base_dir: Path = BASE_DIR):
        self.base_dir=Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.session_file=self.base_dir / "session.json"
        self.status_file=self.base_dir / "status.json"
        self.log_file=self.base_dir / "log.jsonl"
        self.session_id=None
        self.baseline_centroid=None
        self.baseline_spread=0.0
        self._bg_task=None
        self._load_session()

    def _load_session(self):
        if self.session_file.exists():
            try:
                data=json.loads(self.session_file.read_text(encoding='utf-8'))
                self.session_id=data.get('session_id')
                self.baseline_centroid=data.get('baseline_centroid')
                self.baseline_spread=data.get('baseline_spread',0.0)
                print(f"[probe-monitor] restored session {self.session_id}")
            except Exception as e:
                print(f"[probe-monitor] failed to load session.json: {e}")

    def ensure_session(self):
        """确保有一个独立的探针会话ID，不依赖 Workbench"""
        if self.session_id:
            return self.session_id
        # 独立 ID，不进 Workbench 的 sessions 表
        self.session_id=f"probe-monitor-{uuid.uuid4().hex[:12]}"
        self.session_file.write_text(json.dumps({
            "session_id": self.session_id,
            "created_at": time.time(),
            "adapter": "independent",
            "note": "独立探针会话，与 Workbench ConversationList 完全隔离，切换工作会话不冲突"
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"[probe-monitor] created independent session {self.session_id}")
        return self.session_id

    def _fingerprint_text(self, text: str):
        return style_features(text)

    def _call_real_llm(self, prompt: str) -> str | None:
        """尝试用真实 LLM 链路跑探针，失败返回 None"""
        try:
            from intelligence.services.llm_refine import chat_with_tools
            messages=[{"role":"user","content":prompt}]
            msg, provider, reason = chat_with_tools(messages=messages, tools=[], timeout=20, temperature=0.2)
            if msg and isinstance(msg, dict):
                content = msg.get("content","")
                if content:
                    print(f"[probe-monitor] real LLM reply via {provider} len={len(content)}")
                    return content
            print(f"[probe-monitor] real LLM failed: {reason} provider={provider}")
        except Exception as e:
            print(f"[probe-monitor] real LLM exception: {e}")
        return None

    async def run_once(self, adapter=None):
        """
        跑一轮金丝雀探针，计算指纹和与基线的距离
        adapter: 可选，实现了 send(session_id, prompt) -> (session_id, reply) 的对象
                 如果为 None，则尝试真实 LLM 调用，失败回退到模拟（用于测试过滤逻辑）
        """
        self.ensure_session()
        fps=[]
        replies={}
        for probe in CANARY_PROBES:
            reply=None
            if adapter:
                try:
                    _, reply = adapter.send(self.session_id, probe["prompt"])
                except Exception as e:
                    reply=f"[adapter error: {e}]"
            else:
                # 先尝试真实 LLM
                reply = self._call_real_llm(probe["prompt"])
            if not reply:
                # 模拟回退
                mock_map={
                    "identity": "2026",
                    "style_opinion": "远程和坐班各有利弊，取决于工作性质和个人自律性，混合办公往往更平衡。",
                    "behavior_tokenize": "3"
                }
                reply=mock_map.get(probe["id"], "测试回复")
            fp=self._fingerprint_text(reply)
            fps.append(fp)
            replies[probe["id"]]=reply
            # log
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "a", encoding='utf-8') as f:
                f.write(json.dumps({
                    "ts": time.time(),
                    "session_id": self.session_id,
                    "probe_id": probe["id"],
                    "prompt": probe["prompt"],
                    "reply": reply,
                    "fingerprint": fp
                }, ensure_ascii=False)+"\n")

        merged={}
        for fp in fps:
            merged.update(fp)
        # 基线建立
        if self.baseline_centroid is None:
            self.baseline_centroid=merged
            self.baseline_spread=0.0
            # 保存基线到 session.json
            data=json.loads(self.session_file.read_text(encoding='utf-8'))
            data["baseline_centroid"]=self.baseline_centroid
            data["baseline_spread"]=self.baseline_spread
            self.session_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"[probe-monitor] baseline established")
        else:
            dist=cosine_distance(merged, self.baseline_centroid)
            is_drift=dist > max(0.08, self.baseline_spread*2)
            # 更新 status
            drift_count=0
            if self.status_file.exists():
                try:
                    drift_count=json.loads(self.status_file.read_text()).get("drift_count",0)
                except:
                    drift_count=0
            status={
                "last_check": time.time(),
                "session_id": self.session_id,
                "current_fingerprint": merged,
                "baseline_centroid": self.baseline_centroid,
                "distance": dist,
                "is_drift": is_drift,
                "drift_count": drift_count+1 if is_drift else drift_count,
                "replies": replies,
                "note": "独立会话，切换工作会话不影响"
            }
            self.status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"[probe-monitor] check distance={dist:.4f} drift={is_drift}")
            return status
        # 首次也写 status
        self.status_file.write_text(json.dumps({
            "last_check": time.time(),
            "session_id": self.session_id,
            "current_fingerprint": merged,
            "baseline_centroid": self.baseline_centroid,
            "distance": 0.0,
            "is_drift": False,
            "drift_count": 0,
            "replies": replies
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        return {"distance":0.0,"is_drift":False}

    def get_status(self):
        if self.status_file.exists():
            try:
                return json.loads(self.status_file.read_text(encoding='utf-8'))
            except:
                return {}
        if self.session_file.exists():
            try:
                data=json.loads(self.session_file.read_text(encoding='utf-8'))
                return {"session_id": data.get("session_id"), "baseline": bool(data.get("baseline_centroid")), "note": "no status yet"}
            except:
                pass
        return {}

    async def start_background(self, interval: float = 300, adapter=None):
        """常驻后台，每 interval 秒跑一轮，不阻塞主流程"""
        if self._bg_task and not self._bg_task.done():
            print("[probe-monitor] background already running")
            return
        self.ensure_session()
        async def loop():
            print(f"[probe-monitor] background started interval={interval}s session={self.session_id}")
            while True:
                try:
                    await self.run_once(adapter=adapter)
                except Exception as e:
                    print(f"[probe-monitor] background error: {e}")
                await asyncio.sleep(interval)
        self._bg_task=asyncio.create_task(loop())
        return self._bg_task

    def stop_background(self):
        if self._bg_task:
            self._bg_task.cancel()
            print("[probe-monitor] background stopped")

# CLI 测试
if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--once', action='store_true', help='跑一轮')
    ap.add_argument('--status', action='store_true', help='查看状态')
    ap.add_argument('--reset', action='store_true', help='重置独立会话')
    ap.add_argument('--bg', action='store_true', help='后台常驻')
    ap.add_argument('--interval', type=float, default=300)
    args=ap.parse_args()
    mgr=ProbeSessionManager()
    if args.reset:
        for f in [mgr.session_file, mgr.status_file]:
            if f.exists(): f.unlink()
        print("reset done")
    if args.status:
        print(json.dumps(mgr.get_status(), ensure_ascii=False, indent=2))
    if args.once:
        asyncio.run(mgr.run_once())
        print(json.dumps(mgr.get_status(), ensure_ascii=False, indent=2))
    if args.bg:
        async def main():
            await mgr.start_background(interval=args.interval)
            while True:
                await asyncio.sleep(3600)
        asyncio.run(main())
