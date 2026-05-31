"""将1月板块数据写入飞书 Bitable + 电子表格。"""
import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime

# Add shared path
sys.path.insert(0, str(__import__('pathlib').Path.home() / '.claude/shared'))
from feishu_utils import load_config, get_token, api, fetch_all_records, batch_update

CFG = load_config()
TOKEN = get_token(CFG)
APP_TOKEN = CFG["app_token"]
BITABLE_TABLE = "tblXqyf9Av1rGg0n"
SPREADSHEET_TOKEN = "AHqIwJyMKiglO2kokwYcHRjJnWd"
SHEET_ID = "e8a204"

# Load data
with open('/tmp/sector_jan_all.json') as f:
    DATA = json.load(f)

# Name mapping from fupanhui
NAME_MAP = {
    "885537.TI":"3D打印","886037.TI":"6G","886071.TI":"AI PC","886019.TI":"AIGC",
    "886108.TI":"AI应用","886070.TI":"AI手机","886099.TI":"AI智能体","886085.TI":"AI眼镜",
    "886074.TI":"AI语料","886053.TI":"BC电池","885927.TI":"CRO","886031.TI":"ChatGPT",
    "885947.TI":"DRG/DIP","886100.TI":"DeepSeek","886039.TI":"ERP","885878.TI":"HJT电池",
    "886095.TI":"IP经济(谷子经济)","881271.TI":"IT服务","885925.TI":"MCU芯片","886040.TI":"MLOps",
    "886046.TI":"MR(混合现实)","885959.TI":"PCB","886063.TI":"PEEK材料","886020.TI":"PET铜箔",
    "886026.TI":"POE胶膜","886068.TI":"Sora概念(文生视频)","886007.TI":"TOPCON电池",
    "886017.TI":"Web3.0","886000.TI":"一体化压铸","885540.TI":"三胎","881118.TI":"专用设备",
    "881141.TI":"中药","885362.TI":"云计算","881177.TI":"互联网电商","885728.TI":"人工智能",
    "886069.TI":"人形机器人","885946.TI":"传感器","886067.TI":"低空经济","886016.TI":"供销社",
    "881156.TI":"保险","886013.TI":"信创","885921.TI":"储能","881270.TI":"元件",
    "886009.TI":"先进封装","885531.TI":"光伏","881279.TI":"光伏设备","886054.TI":"光刻机",
    "885864.TI":"光刻胶","881122.TI":"光学光电子","886011.TI":"光热发电","886084.TI":"光纤",
    "881149.TI":"公路铁路运输","886033.TI":"共封装光学(CPO)","881123.TI":"其他电子",
    "881282.TI":"其他电源设备","881179.TI":"其他社会服务","881102.TI":"养殖业","885700.TI":"军工",
    "886076.TI":"军工信息化","881276.TI":"军工电子","881166.TI":"军工装备","881103.TI":"农产品加工",
    "881263.TI":"农化制品","885825.TI":"冰雪产业","886051.TI":"减肥药","886008.TI":"减速器",
    "886015.TI":"创新药","881138.TI":"包装印刷","881109.TI":"化学制品","881140.TI":"化学制药",
    "881108.TI":"化学原料","881264.TI":"化学纤维","881144.TI":"医疗器械","881175.TI":"医疗服务",
    "881143.TI":"医药商业","881121.TI":"半导体","884229.TI":"半导体设备","886091.TI":"华为手机",
    "886093.TI":"华为数字能源","886058.TI":"华为昇腾","886094.TI":"华为盘古","881174.TI":"厨卫电器",
    "886065.TI":"可控核聚变","886077.TI":"合成生物","886078.TI":"商业航天","886032.TI":"固态电池",
    "881265.TI":"塑料制品","881283.TI":"多元金融","886062.TI":"多模态AI","885566.TI":"大飞机",
    "886043.TI":"太赫兹","886042.TI":"存储芯片","886012.TI":"宠物经济","881139.TI":"家居用品",
    "881173.TI":"小家电","886064.TI":"小米汽车","886098.TI":"小红书","881170.TI":"小金属",
    "885552.TI":"小金属","885930.TI":"工业母机","881168.TI":"工业金属","881268.TI":"工程机械",
    "881115.TI":"建筑材料","881116.TI":"建筑装饰","881274.TI":"影视院线","886030.TI":"成飞",
    "881153.TI":"房地产","886087.TI":"房屋检测","881178.TI":"教育","886034.TI":"数字水印",
    "885866.TI":"数字货币","885887.TI":"数据中心","886023.TI":"数据确权","886041.TI":"数据要素",
    "881164.TI":"文化传媒","886057.TI":"新型工业化","881160.TI":"旅游及酒店","885736.TI":"无人驾驶",
    "886036.TI":"时空大数据","886055.TI":"星闪","886059.TI":"智能座舱","886090.TI":"智谱AI",
    "885912.TI":"有机硅","881136.TI":"服装家纺","885517.TI":"机器人","886002.TI":"机器视觉",
    "881151.TI":"机场航运","885633.TI":"染料","886052.TI":"核污染防治","881266.TI":"橡胶制品",
    "886035.TI":"毫米波雷达","885960.TI":"民爆","885551.TI":"氟化工","885823.TI":"氢能源",
    "881125.TI":"汽车整车","881128.TI":"汽车服务及其他","881126.TI":"汽车零部件",
    "881107.TI":"油气开采及服务","885939.TI":"海峡两岸","881124.TI":"消费电子","886044.TI":"液冷服务器",
    "881148.TI":"港口航运","881275.TI":"游戏","881105.TI":"煤炭开采加工","885775.TI":"燃料电池",
    "881146.TI":"燃气","881152.TI":"物流","885425.TI":"特高压","881284.TI":"环保设备",
    "881181.TI":"环境治理","884059.TI":"玻璃玻纤","881142.TI":"生物制品","886005.TI":"生物质能发电",
    "881145.TI":"电力","881172.TI":"电子化学品","881277.TI":"电机","881281.TI":"电池",
    "881278.TI":"电网设备","881131.TI":"白色家电","881273.TI":"白酒","885922.TI":"盐湖提锂",
    "886060.TI":"短剧游戏","885781.TI":"石墨电极","881180.TI":"石油加工贸易","885650.TI":"碳纤维",
    "885863.TI":"磷化工","881101.TI":"种植业与林业","885343.TI":"稀土永磁","886010.TI":"空气能热泵",
    "886049.TI":"空间计算","886050.TI":"算力租赁","881135.TI":"纺织制造","885988.TI":"统一大市场",
    "886081.TI":"维生素","881165.TI":"综合","881182.TI":"美容护理","881267.TI":"能源金属",
    "886047.TI":"脑机接口","881171.TI":"自动化设备","885884.TI":"航空发动机","885756.TI":"芯片",
    "886048.TI":"英伟达","886004.TI":"虚拟电厂","886028.TI":"血氧仪","881130.TI":"计算机设备",
    "881157.TI":"证券","886080.TI":"财税数字化","881169.TI":"贵金属","881159.TI":"贸易",
    "886038.TI":"超导","885886.TI":"超级电容","881269.TI":"轨交设备","881272.TI":"软件开发",
    "885909.TI":"辅助生殖","881162.TI":"通信服务","881129.TI":"通信设备","881117.TI":"通用设备",
    "881137.TI":"造纸","885730.TI":"量子科技","881114.TI":"金属新材料","885865.TI":"金属钴",
    "885971.TI":"金属铅","885973.TI":"金属铜","885970.TI":"金属锌","885969.TI":"金属镍",
    "886003.TI":"钒电池","886006.TI":"钙钛矿电池","885928.TI":"钠离子电池","881112.TI":"钢铁",
    "886073.TI":"铜缆高速连接","881155.TI":"银行","884286.TI":"锂","884309.TI":"锂电池",
    "886061.TI":"长安汽车","886056.TI":"阿尔茨海默","886105.TI":"雅下水电","881158.TI":"零售",
    "881167.TI":"非金属材料","885641.TI":"风电","881280.TI":"风电设备","886066.TI":"飞行汽车(eVTOL)",
    "881134.TI":"食品加工制造","881133.TI":"饮料制造","886001.TI":"高压快充","886018.TI":"高压氧舱",
    "885530.TI":"黄金","881132.TI":"黑色家电",
}

def code_to_name(code):
    """将 TI code 转中文名，处理小金属重复。"""
    return NAME_MAP.get(code, code)

def date_to_label(date_str):
    """2026-01-05 -> 26-01-05"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.year % 100:02d}-{d.month:02d}-{d.day:02d}"


def write_bitable():
    """写入 Bitable sector_daily：创建字段 + 批量更新。"""
    print("=== Bitable sector_daily ===")

    # Get existing records: sector name -> record_id
    records = fetch_all_records(TOKEN, BITABLE_TABLE, APP_TOKEN)
    name_to_id = {}
    for r in records:
        name = r["fields"].get("板块", "")
        name_to_id[name] = r["record_id"]
    print(f"现有记录: {len(name_to_id)}")

    # Get existing fields
    fields_result = api("GET", "/fields", TOKEN, table_id=BITABLE_TABLE, app_token=APP_TOKEN)
    existing_fields = {f["field_name"]: f["field_id"] for f in fields_result.get("data", {}).get("items", [])}

    dates = sorted(DATA.keys())
    for date_str in dates:
        label = date_to_label(date_str)
        field_pct = f"{label}涨幅"
        field_amt = f"{label}成交额"

        # Create fields if needed
        for fname in [field_pct, field_amt]:
            if fname not in existing_fields:
                r = api("POST", "/fields", TOKEN,
                       {"field_name": fname, "type": 1},
                       table_id=BITABLE_TABLE, app_token=APP_TOKEN)
                if r.get("code") == 0:
                    fid = r.get("data", {}).get("field", {}).get("field_id", "")
                    existing_fields[fname] = fid
                    print(f"  创建字段: {fname}")
                else:
                    print(f"  创建字段失败 {fname}: {r.get('msg')}", file=sys.stderr)

        # Build update records
        sectors = DATA[date_str]
        updates = []
        for code, vals in sectors.items():
            name = code_to_name(code)
            rid = name_to_id.get(name)
            if not rid:
                # Try with TS code suffix for duplicates
                rid = name_to_id.get(f"{name}({code})")
            if rid:
                fields = {}
                pct = vals.get("pct_chg")
                amt = vals.get("amount")
                if pct is not None:
                    fields[field_pct] = f"{pct:.2f}%"
                if amt is not None:
                    fields[field_amt] = f"{amt:.1f}"
                if fields:
                    updates.append({"record_id": rid, "fields": fields})

        if updates:
            n = batch_update(TOKEN, BITABLE_TABLE, updates, APP_TOKEN)
            print(f"  {date_str}: 更新 {n} 条记录")
        else:
            print(f"  {date_str}: 无数据可写")

def write_spreadsheet():
    """写入电子表格 sector_marginal_sheet：每日期一列 diff_ratio。"""
    print("\n=== 电子表格 sector_marginal_sheet ===")

    base_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_TOKEN}"

    # Read A column to get sector order
    url = f"{base_url}/values/{SHEET_ID}!A1:A230"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        a_col = json.loads(resp.read())

    rows = a_col.get("data", {}).get("valueRange", {}).get("values", [])
    print(f"A列行数: {len(rows)}")

    # Build index: sector name -> row number (1-indexed)
    # rows[0] = A1, rows[1] = A2, etc.
    sector_row = {}
    for i, row in enumerate(rows):
        if row and row[0]:
            name = str(row[0]).strip()
            if name != "板块":
                sector_row[name] = i + 1  # rows[0] = A1 = row 1

    # Read header row to find next empty column
    url = f"{base_url}/values/{SHEET_ID}!1:1"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        header_data = json.loads(resp.read())
    header_vals = header_data.get("data", {}).get("valueRange", {}).get("values", [[]])
    header_row = header_vals[0] if header_vals else []
    next_col_idx = len(header_row) + 1  # 1-indexed
    if next_col_idx <= 1:
        next_col_idx = 2  # A列是板块名，数据从B列开始
    print(f"当前 {len(header_row)} 列有表头，下一列: B -> col {next_col_idx}")

    # Write columns in date order
    dates = sorted(DATA.keys())
    col = next_col_idx
    for date_str in dates:
        label = date_to_label(date_str)
        sectors = DATA[date_str]

        # Build values array: header + data rows aligned to A column
        values = [[label]]
        for row_num in range(2, 229):  # rows 2-228 (max 227 sectors)
            # Find which sector name is at this row
            name_at_row = None
            for n, r in sector_row.items():
                if r == row_num:
                    name_at_row = n
                    break

            if name_at_row:
                # Find matching TI code for this sector name
                val = ""
                for code, v in sectors.items():
                    n = code_to_name(code)
                    if n == name_at_row or f"{n}({code})" == name_at_row:
                        dr = v.get("diff_ratio")
                        if dr is not None:
                            val = f"{dr:.2f}"
                        break
                values.append([val])
            else:
                values.append([""])

        # Write column
        col_letter = chr(64 + col) if col <= 26 else chr(64 + (col-1)//26) + chr(64 + (col-1)%26 + 1)
        rng = f"{SHEET_ID}!{col_letter}1:{col_letter}{len(values)}"
        body = {"valueRange": {"range": rng, "values": values}}
        put_url = f"{base_url}/values"
        data = json.dumps(body).encode()
        req = urllib.request.Request(put_url, data=data,
                                     headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                                     method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            if result.get("code") == 0:
                print(f"  {date_str}: 写入 {col_letter} 列 ({len(values)-1} 行)")
            else:
                print(f"  {date_str}: 写入失败 {result.get('code')}: {result.get('msg')}", file=sys.stderr)
        except urllib.error.HTTPError as e:
            print(f"  {date_str}: HTTP {e.code}: {e.reason}", file=sys.stderr)

        col += 1


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--spreadsheet-only":
        write_spreadsheet()
    else:
        write_bitable()
        write_spreadsheet()
    print("\nDone.")
