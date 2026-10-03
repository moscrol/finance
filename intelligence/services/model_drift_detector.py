"""
运行中模型漂移检测

目标：跑的时候也能和探针一样检测模型，知道正在跑的模型是哪个型号，怕跑着跑着路由了

实现：
- 每轮 LLM 回复后，提取风格指纹（复用 probe_filter 的 style_features）
- 与本 run 的基线质心比较，距离 > threshold 则判定漂移
- 记录到 run_dir 下的 model_drift.jsonl，便于事后审计
- 提供当前模型推断：根据指纹与 target_profiles.json 的距离，猜最接近的目标模型

集成点：
- intelligence/runtime/glm_agent_runtime.py 的 GLMModelClient.chat() 返回后
- intelligence/runtime/openai_agents_runtime.py 的 _run_openai_agents_sdk 返回后
- intelligence/runtime/agent_episode.py 的每轮结束

使用：
    from intelligence.services.model_drift_detector import ModelDriftDetector
    detector = ModelDriftDetector(run_dir=Path(...), run_id=run_id)
    detector.observe(text, step="llm_call_1", model_hint="glm-4.5")
    if detector.has_drifted():
        # 报警或中断
"""
from __future__ import annotations
import json
import math
import re
import time
from pathlib import Path
from statistics import mean
from typing import Dict, List

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

class ModelDriftDetector:
    def __init__(self, run_dir: Path | None = None, run_id: str = "unknown", threshold: float = 0.08, target_profiles_path: Path | None = None):
        self.run_dir=Path(run_dir) if run_dir else None
        self.run_id=run_id
        self.threshold=threshold
        self.fingerprints: List[Dict[str,float]] = []
        self.history: List[Dict] = []
        self.baseline_centroid=None
        self.baseline_spread=0.0
        self.targets=None
        # 加载目标配置用于推断型号
        if target_profiles_path is None:
            target_profiles_path=Path.home()/".local/share/finance-arena/target_profiles.json"
        if Path(target_profiles_path).exists():
            try:
                data=json.loads(Path(target_profiles_path).read_text(encoding='utf-8'))
                self.targets=data.get('targets',[])
            except Exception as e:
                print(f"[drift-detector] failed to load targets {target_profiles_path}: {e}")

    def _log(self, record: Dict):
        if self.run_dir:
            try:
                self.run_dir.mkdir(parents=True, exist_ok=True)
                with open(self.run_dir/"model_drift.jsonl","a",encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False)+"\n")
            except Exception:
                pass

    def observe(self, text: str, step: str = "unknown", model_hint: str | None = None):
        """观察一次 LLM 回复"""
        fp=style_features(text)
        self.fingerprints.append(fp)
        now=time.time()

        # 推断最接近的目标型号
        best_target, best_dist = None, 1e9
        if self.targets:
            for t in self.targets:
                d=cosine_distance(fp, t.get('centroid',{}))
                if d<best_dist:
                    best_dist=d
                    best_target=t.get('name')

        if self.baseline_centroid is None:
            self.baseline_centroid=fp
            self.baseline_spread=0.0
            record={
                "ts": now,
                "run_id": self.run_id,
                "step": step,
                "model_hint": model_hint,
                "distance": 0.0,
                "is_drift": False,
                "best_target": best_target,
                "best_distance": best_dist,
                "fingerprint": fp,
                "text_preview": text[:200]
            }
            self.history.append(record)
            self._log(record)
            print(f"[drift-detector][{self.run_id}] baseline established step={step} target={best_target} dist={best_dist:.4f}")
            return record

        dist=cosine_distance(fp, self.baseline_centroid)
        is_drift=dist > max(self.threshold, self.baseline_spread*1.5) if len(self.fingerprints)>2 else False
        # 更新 spread（判定之后）
        self.baseline_spread=max(self.baseline_spread, dist)

        record={
            "ts": now,
            "run_id": self.run_id,
            "step": step,
            "model_hint": model_hint,
            "distance": dist,
            "is_drift": is_drift,
            "baseline_spread": self.baseline_spread,
            "best_target": best_target,
            "best_distance": best_dist,
            "fingerprint": fp,
            "text_preview": text[:200]
        }
        self.history.append(record)
        self._log(record)

        if is_drift:
            print(f"[drift-detector][{self.run_id}] 🚨 DRIFT step={step} distance={dist:.4f} thr={self.threshold} target={best_target} dist_to_target={best_dist:.4f} model_hint={model_hint}")
            print(f"  建议：停止关键任务，检查当前模型型号，必要时重抽会话")
        else:
            print(f"[drift-detector][{self.run_id}] ok step={step} distance={dist:.4f} target={best_target} dist_to_target={best_dist:.4f}")

        # 动态更新基线质心（滑动窗口，避免基线过旧）
        if not is_drift and len(self.fingerprints)<=10:
            self.baseline_centroid=centroid(self.fingerprints)

        return record

    def has_drifted(self):
        return any(h.get('is_drift') for h in self.history)

    def current_model(self):
        """返回当前最可能的模型型号"""
        if not self.history:
            return None
        last=self.history[-1]
        return {"target": last.get('best_target'), "distance": last.get('best_distance'), "drift": last.get('is_drift'), "model_hint": last.get('model_hint')}

    def get_report(self):
        if not self.history:
            return {"run_id": self.run_id, "status": "no-data"}
        last=self.history[-1]
        return {
            "run_id": self.run_id,
            "total_steps": len(self.history),
            "drift_count": sum(1 for h in self.history if h.get('is_drift')),
            "has_drifted": self.has_drifted(),
            "current": last,
            "baseline_spread": self.baseline_spread,
            "threshold": self.threshold
        }
