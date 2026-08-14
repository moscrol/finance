#!/usr/bin/env python3
"""验收测试：check_kb_freshness.py 修复验证

测试目标：证明修复后的脚本不会被 mtime 刷新误导成假绿。

场景：构造一个「只 touch 老文件、不加新 source_date」的场景，
     断言脚本仍然报红（断更）。

旧版缺陷：
  1. mtime 参与取 max，任何批量 frontmatter 改写或 git checkout 都会刷绿
  2. 全库取最大值，公告线活着盖住题材线断更

修复后行为：
  1. 只看 evidence_index.json 的 source_date，不读文件 mtime
  2. 按 source_quality 分线报告，监控线独立判定
"""

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

# 添加 scripts 到路径以便导入
sys.path.insert(0, str(Path(__file__).parent))

from check_kb_freshness import load_evidence_freshness


def test_mtime_does_not_affect_freshness():
    """测试 1：mtime 不影响新鲜度判定
    
    构造场景：
      - broker_research_high 最新 source_date 是 30 天前
      - 即使把 evidence_index.json 文件的 mtime 改成今天
      - 脚本仍应报告 broker_research_high 是 30 天前
    """
    print("\n=== 测试 1：mtime 不影响新鲜度判定 ===")
    
    # 构造测试数据：最新证据是 30 天前
    old_date = (date.today() - timedelta(days=30)).isoformat()
    
    test_data = {
        "items": [
            {"source_quality": "broker_research_high", "source_date": old_date, "target": "测试概念1"},
            {"source_quality": "broker_research_high", "source_date": old_date, "target": "测试概念2"},
            {"source_quality": "official_disclosure", "source_date": date.today().isoformat(), "target": "测试公司1"},
        ]
    }
    
    # 写入临时文件
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        wiki_root = tmp_path / "wiki"
        relations_dir = wiki_root / "relations"
        relations_dir.mkdir(parents=True)
        
        evidence_file = relations_dir / "evidence_index.json"
        evidence_file.write_text(json.dumps(test_data, ensure_ascii=False))
        
        # 加载新鲜度（此时 mtime 是刚才的写入时间，即"今天"）
        freshness = load_evidence_freshness(wiki_root)
        
        # 断言：broker_research_high 应该是 30 天前，不是今天
        assert "broker_research_high" in freshness, "应该有 broker_research_high 线"
        latest_date, count = freshness["broker_research_high"]
        
        assert latest_date == date.fromisoformat(old_date), \
            f"broker_research_high 最新日期应该是 {old_date}，实际是 {latest_date}"
        assert count == 2, f"broker_research_high 应该有 2 条，实际 {count}"
        
        # 计算龄期
        age = (date.today() - latest_date).days
        assert age == 30, f"龄期应该是 30 天，实际 {age} 天"
        
        print(f"✓ broker_research_high 正确识别为 {age} 天前（source_date={old_date}）")
        print("✓ 文件 mtime 是今天，但不影响判定")


def test_lane_isolation():
    """测试 2：证据线隔离
    
    构造场景：
      - official_disclosure（公告线）今天有数据
      - broker_research_high（卖方线）11 天前最后更新
      - 脚本应该分别报告两线，不是只报全局最大值
    """
    print("\n=== 测试 2：证据线隔离 ===")
    
    today_str = date.today().isoformat()
    old_date = (date.today() - timedelta(days=11)).isoformat()
    
    test_data = {
        "items": [
            {"source_quality": "official_disclosure", "source_date": today_str, "target": "公告1"},
            {"source_quality": "official_disclosure", "source_date": today_str, "target": "公告2"},
            {"source_quality": "broker_research_high", "source_date": old_date, "target": "研报1"},
            {"source_quality": "broker_research_high", "source_date": old_date, "target": "研报2"},
        ]
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        wiki_root = tmp_path / "wiki"
        relations_dir = wiki_root / "relations"
        relations_dir.mkdir(parents=True)
        
        evidence_file = relations_dir / "evidence_index.json"
        evidence_file.write_text(json.dumps(test_data, ensure_ascii=False))
        
        freshness = load_evidence_freshness(wiki_root)
        
        # 断言：两线应该分别报告
        assert "official_disclosure" in freshness
        assert "broker_research_high" in freshness
        
        official_date, official_count = freshness["official_disclosure"]
        broker_date, broker_count = freshness["broker_research_high"]
        
        assert official_date == date.today(), "公告线应该是今天"
        assert broker_date == date.fromisoformat(old_date), f"卖方线应该是 {old_date}"
        
        official_age = (date.today() - official_date).days
        broker_age = (date.today() - broker_date).days
        
        assert official_age == 0, f"公告线龄期应该是 0 天，实际 {official_age}"
        assert broker_age == 11, f"卖方线龄期应该是 11 天，实际 {broker_age}"
        
        print(f"✓ official_disclosure: {official_age} 天前（{official_count} 条）")
        print(f"✓ broker_research_high: {broker_age} 天前（{broker_count} 条）")
        print("✓ 公告线活着不会盖住卖方线断更")


def test_invalid_dates_ignored():
    """测试 3：无效日期被忽略
    
    构造场景：
      - 部分条目 source_date 为空字符串或格式错误
      - 脚本应该只统计有效日期，不崩溃
    """
    print("\n=== 测试 3：无效日期被忽略 ===")
    
    valid_date = (date.today() - timedelta(days=5)).isoformat()
    
    test_data = {
        "items": [
            {"source_quality": "broker_research_high", "source_date": valid_date, "target": "有效1"},
            {"source_quality": "broker_research_high", "source_date": "", "target": "空日期"},
            {"source_quality": "broker_research_high", "source_date": "invalid-date", "target": "格式错误"},
            {"source_quality": "broker_research_high", "target": "缺字段"},  # 没有 source_date
        ]
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        wiki_root = tmp_path / "wiki"
        relations_dir = wiki_root / "relations"
        relations_dir.mkdir(parents=True)
        
        evidence_file = relations_dir / "evidence_index.json"
        evidence_file.write_text(json.dumps(test_data, ensure_ascii=False))
        
        freshness = load_evidence_freshness(wiki_root)
        
        assert "broker_research_high" in freshness
        latest_date, count = freshness["broker_research_high"]
        
        # 应该只统计有效的那 1 条
        assert latest_date == date.fromisoformat(valid_date), "应该取到有效日期"
        assert count == 1, f"应该只统计 1 条有效日期，实际 {count}"
        
        print(f"✓ 从 4 条记录中正确提取 {count} 条有效日期")
        print(f"✓ 最新日期：{latest_date}（5 天前）")


def main():
    """运行所有测试"""
    print("检查 KB freshness 修复验收测试")
    print("=" * 60)
    
    try:
        test_mtime_does_not_affect_freshness()
        test_lane_isolation()
        test_invalid_dates_ignored()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过")
        print("\n修复验证要点：")
        print("  1. ✓ 不使用文件 mtime，只看 source_date")
        print("  2. ✓ 按 source_quality 分线报告")
        print("  3. ✓ 公告线活着不会盖住题材线断更")
        print("  4. ✓ 无效日期被正确忽略")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        return 1
    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
