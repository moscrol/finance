#!/usr/bin/env python3
"""
连板日历 Dashboard 后端 - 重做版

功能：
1. 从 DuckDB market_feature_store.duckdb 读取 fact_limit_advance_daily 等表
2. 生成最近 60 天的日历 JSON
3. 提供简单的 HTTP API 供前端调用
4. 也可直接生成静态 data.json

用法：
  python3 backend.py --generate  # 生成 data.json
  python3 backend.py --serve --port 8000  # 启动 API 服务
"""

import argparse
import json
import pathlib
from datetime import datetime

DB_PATHS = [
    "/Users/a77/finance-workspace-private/db/market_feature_store.duckdb",
    "./db/market_feature_store.duckdb",
    "../db/market_feature_store.duckdb",
    "/home/user/market_feature_store.duckdb",
]

def find_db():
    for p in DB_PATHS:
        if pathlib.Path(p).exists():
            return p
    return None

def generate_calendar(days=60):
    try:
        import duckdb
    except ImportError:
        print("duckdb 未安装，pip install duckdb")
        return []

    db_path = find_db()
    if not db_path:
        print(f"未找到 DuckDB，尝试路径: {DB_PATHS}")
        return []

    con = duckdb.connect(db_path, read_only=True)
    trading_days = con.execute(f'''
    SELECT trade_date FROM fact_market_daily ORDER BY trade_date DESC LIMIT {days}
    ''').fetchall()
    trading_days = [d[0].isoformat() if hasattr(d[0],'isoformat') else str(d[0]) for d in trading_days]
    trading_days = sorted(trading_days)

    calendar_data = []
    for td in trading_days:
        ladder = con.execute(f'''
        SELECT boards, COUNT(*) as cnt
        FROM fact_limit_advance_daily
        WHERE trade_date = '{td}'
        GROUP BY boards ORDER BY boards
        ''').fetchall()
        ladder_dict = {int(b): int(c) for b,c in ladder}

        details = con.execute(f'''
        SELECT stock_name, stock_ts_code, boards, theme, pct_chg
        FROM fact_limit_advance_daily
        WHERE trade_date = '{td}'
        ORDER BY boards DESC, stock_name
        ''').fetchall()
        details_list = [
            {'name': r[0], 'ts_code': r[1], 'boards': int(r[2]), 'theme': r[3], 'pct': float(r[4]) if r[4] is not None else None}
            for r in details
        ]

        market = con.execute(f'''
        SELECT limit_up, limit_down, advancers, total_amount, market_stage
        FROM fact_market_daily WHERE trade_date = '{td}'
        ''').fetchone()

        leader = con.execute(f'''
        SELECT height, leader_name FROM fact_leader_height_daily WHERE trade_date = '{td}'
        ''').fetchone()

        calendar_data.append({
            'trade_date': td,
            'ladder': ladder_dict,
            'details': details_list,
            'total_lianban': len(details_list),
            'max_boards': max(ladder_dict.keys()) if ladder_dict else 0,
            'market': {
                'limit_up': market[0] if market else None,
                'limit_down': market[1] if market else None,
                'advancers': market[2] if market else None,
                'amount': float(market[3]) if market and market[3] else None,
                'stage': market[4] if market else None
            },
            'leader': {
                'height': int(leader[0]) if leader else 0,
                'name': leader[1] if leader else None
            }
        })

    con.close()
    return calendar_data

def serve(port=8000):
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import urllib.parse

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/api/calendar':
                days = int(urllib.parse.parse_qs(parsed.query).get('days',['60'])[0])
                data = generate_calendar(days=days)
                self.send_response(200)
                self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin','*')
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
            elif parsed.path == '/api/stats':
                data = generate_calendar(days=90)
                if not data:
                    self.send_error(404)
                    return
                stats = {
                    'total_days': len(data),
                    'avg_max_boards': sum(d['max_boards'] for d in data)/len(data),
                    'max_boards_overall': max(d['max_boards'] for d in data),
                    'max_boards_date': max(data, key=lambda x: x['max_boards'])['trade_date'],
                    'total_lianban': sum(d['total_lianban'] for d in data),
                }
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Access-Control-Allow-Origin','*')
                self.end_headers()
                self.wfile.write(json.dumps(stats, ensure_ascii=False).encode())
            else:
                return super().do_GET()

        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin','*')
            super().end_headers()

    print(f"Serving at http://0.0.0.0:{port}  (API: /api/calendar?days=60)")
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--generate', action='store_true', help='生成 data.json')
    ap.add_argument('--serve', action='store_true', help='启动 HTTP 服务')
    ap.add_argument('--port', type=int, default=8000)
    ap.add_argument('--days', type=int, default=60)
    args = ap.parse_args()

    if args.generate:
        data = generate_calendar(days=args.days)
        out = pathlib.Path(__file__).parent / 'data.json'
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"已生成 {out} ({len(data)} 天)")
        # 同时拷一份到 finance-workspace-private
        remote = pathlib.Path('/Users/a77/finance-workspace-private/market_snapshot/limitup_calendar.json')
        if remote.parent.exists():
            remote.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"已同步到 {remote}")

    if args.serve:
        serve(port=args.port)

    if not args.generate and not args.serve:
        # 默认生成
        data = generate_calendar(days=args.days)
        print(json.dumps(data[-2:], ensure_ascii=False, indent=2))
