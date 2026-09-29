"""
Probe-based model filter for FinArena

用途：利用 model_pin_probe 的指纹机制，过滤掉非目标模型的回答。

原理：
- 先用已知目标模型的若干轮探针回复，生成目标质心 fingerprint
- 每次 Arena 调用 agent 得到 Answer 后，额外跑一轮轻量探针（或直接对 Answer 本身提取风格指纹），计算与目标质心的余弦距离
- 距离 > threshold 则判定为非目标模型，过滤掉，不进入发布流程

集成点：
- runner.py 的 run_pair 在得到 results 后，调用 filter
- 或在 store.add_match 前调用

使用示例：
    from intelligence.arena.probe_filter import ProbeFilter
    pf = ProbeFilter.from_target_file('target_profiles.json')
    if not pf.is_target(answer.content):
        # 过滤
        ...

target_profiles.json 格式：
{
  "targets": [
    {
      "name": "target-model-v1",
      "fingerprints": [ {...}, {...} ],
      "centroid": {...},
      "threshold": 0.08
    }
  ]
}
"""
from __future__ import annotations
import json
import math
import re
from pathlib import Path
from statistics import mean
from typing import Dict, List

_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
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
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(a[k] ** 2 for k in keys))
    nb = math.sqrt(sum(b[k] ** 2 for k in keys))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)

def centroid(fps: List[Dict[str, float]]) -> Dict[str, float]:
    if not fps:
        return {}
    keys = set().union(*fps)
    return {k: mean(fp.get(k, 0.0) for fp in fps) for k in keys}

class ProbeFilter:
    def __init__(self, targets: List[Dict], default_threshold: float = 0.08):
        self.targets = targets
        self.default_threshold = default_threshold

    @classmethod
    def from_target_file(cls, path: str | Path, default_threshold: float = 0.08):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"target profile not found: {path}")
        data = json.loads(p.read_text(encoding='utf-8'))
        targets = data.get('targets', [])
        if not targets and 'fingerprints' in data:
            fps = data['fingerprints']
            targets = [{'name': data.get('name','target'), 'centroid': centroid(fps), 'threshold': data.get('threshold', default_threshold), 'fingerprints': fps}]
        return cls(targets, default_threshold)

    @classmethod
    def from_fingerprints(cls, fingerprints: List[Dict[str, float]], name: str = 'target', threshold: float = 0.08):
        c = centroid(fingerprints)
        return cls([{'name': name, 'centroid': c, 'threshold': threshold, 'fingerprints': fingerprints}], threshold)

    def fingerprint_text(self, text: str) -> Dict[str, float]:
        return style_features(text)

    def distance_to_target(self, text: str, target_name: str | None = None):
        fp = self.fingerprint_text(text)
        best_name, best_dist = None, 1e9
        for t in self.targets:
            if target_name and t['name'] != target_name:
                continue
            d = cosine_distance(fp, t['centroid'])
            if d < best_dist:
                best_dist = d
                best_name = t['name']
        return best_name, best_dist

    def is_target(self, text: str, target_name: str | None = None):
        name, dist = self.distance_to_target(text, target_name)
        if name is None:
            return False, 'no-target', 1.0
        thr = next((t.get('threshold', self.default_threshold) for t in self.targets if t['name']==name), self.default_threshold)
        return dist <= thr, name, dist

    def filter_answers(self, answers: List[Dict], target_name: str | None = None):
        kept, filtered = [], []
        for ans in answers:
            content = ans.get('content','') if isinstance(ans, dict) else getattr(ans,'content','')
            ok, tname, dist = self.is_target(content, target_name)
            record = {**ans, '_probe': {'target': tname, 'distance': dist, 'is_target': ok}}
            if ok:
                kept.append(record)
            else:
                filtered.append(record)
        return {'kept': kept, 'filtered': filtered, 'all_target': len(filtered)==0}

if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--target', required=True, help='target_profiles.json')
    ap.add_argument('--text', help='直接测试一段文本')
    ap.add_argument('--file', help='测试文件，每行一段文本')
    args=ap.parse_args()
    pf=ProbeFilter.from_target_file(args.target)
    if args.text:
        ok,name,dist=pf.is_target(args.text)
        print(f"is_target={ok} target={name} distance={dist:.4f}")
    if args.file:
        for line in Path(args.file).read_text().splitlines():
            if not line.strip(): continue
            ok,name,dist=pf.is_target(line)
            print(f"{dist:.4f} {ok} {name} :: {line[:60]}")
