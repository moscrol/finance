#!/usr/bin/env python3
"""
从 model_pin_probe 的日志生成 Arena 目标模型指纹配置

用法：
  python generate_target_profile.py --log model_pin_probe/data/log.jsonl --tag my-target --out target_profiles.json --threshold 0.08

流程：
  1. 读取 log.jsonl，按 tag 过滤
  2. 按 session 分组，取每个 session 的质心
  3. 对所有质心再聚类，选最大簇作为目标模型（假设目标模型是多数）
  4. 输出 target_profiles.json，包含 centroid 和 threshold
"""
import argparse, json
from pathlib import Path
from collections import defaultdict
from statistics import mean
import math, re

def cosine_distance(a,b):
    keys=set(a)&set(b)
    if not keys: return 1.0
    dot=sum(a[k]*b[k] for k in keys)
    na=math.sqrt(sum(a[k]**2 for k in keys))
    nb=math.sqrt(sum(b[k]**2 for k in keys))
    if na==0 or nb==0: return 1.0
    return 1.0 - dot/(na*nb)

def centroid(fps):
    if not fps: return {}
    keys=set().union(*fps)
    return {k: mean(fp.get(k,0.0) for fp in fps) for k in keys}

def load_log(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]

def rounds_by_session(records, tag=None):
    grouped=defaultdict(lambda: defaultdict(list))
    for rec in records:
        if tag and rec.get('tag')!=tag: continue
        grouped[rec['session_id']][rec['round']].append(rec['fingerprint'])
    out={}
    for sid, rounds in grouped.items():
        # merge each round
        merged=[]
        for r in sorted(rounds):
            # merge_round: dict update
            m={}
            for fp in rounds[r]:
                m.update(fp)
            merged.append(m)
        out[sid]=merged
    return out

def cluster(fps, threshold=0.08):
    centers=[]; members=[]; labels=[]
    for fp in fps:
        best,best_d=-1,1e9
        for i,c in enumerate(centers):
            d=cosine_distance(fp,c)
            if d<best_d:
                best,best_d=i,d
        if best>=0 and best_d<threshold:
            labels.append(best)
            members[best].append(fp)
            centers[best]=centroid(members[best])
        else:
            labels.append(len(centers))
            centers.append(dict(fp))
            members.append([fp])
    return labels, centers

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--log', default='model_pin_probe/data/log.jsonl')
    ap.add_argument('--tag', help='只分析指定 tag')
    ap.add_argument('--out', default='target_profiles.json')
    ap.add_argument('--threshold', type=float, default=0.08)
    ap.add_argument('--name', default='target-model')
    args=ap.parse_args()

    records=load_log(args.log)
    if not records:
        print(f"日志为空: {args.log}")
        return
    sessions=rounds_by_session(records, args.tag)
    print(f"加载 {len(records)} 条, {len(sessions)} 会话, tag={args.tag}")

    # 每个会话质心
    session_centroids={}
    for sid, fps in sessions.items():
        session_centroids[sid]=centroid(fps)

    # 聚类找最大簇作为目标
    all_c=list(session_centroids.values())
    labels, centers=cluster(all_c, threshold=args.threshold)
    from collections import Counter
    cnt=Counter(labels)
    print(f"聚类阈值 {args.threshold}: {len(set(labels))} 簇, 分布 {cnt}")
    # 最大簇
    target_cluster=cnt.most_common(1)[0][0]
    target_sids=[sid for sid, lab in zip(session_centroids.keys(), labels) if lab==target_cluster]
    target_fps=[session_centroids[sid] for sid in target_sids]
    target_centroid=centroid(target_fps)

    # 计算该簇内最大距离作为建议阈值
    max_dist=max(cosine_distance(fp, target_centroid) for fp in target_fps) if target_fps else 0
    suggested_thr=max(args.threshold, max_dist*1.5)
    print(f"目标簇 {target_cluster}: {len(target_sids)} 会话, 质心, 簇内最大距离 {max_dist:.4f}, 建议阈值 {suggested_thr:.4f}")
    print(f"会话: {target_sids}")

    out={
        "targets": [
            {
                "name": args.name,
                "centroid": target_centroid,
                "threshold": suggested_thr,
                "fingerprints": target_fps,
                "source_sessions": target_sids,
                "source_tag": args.tag,
                "cluster_id": target_cluster
            }
        ],
        "meta": {
            "log": args.log,
            "tag": args.tag,
            "threshold_used": args.threshold,
            "suggested_threshold": suggested_thr,
            "total_sessions": len(sessions),
            "target_sessions": len(target_sids)
        }
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"已写入 {args.out}")

if __name__=='__main__':
    main()
