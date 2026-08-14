from market_feature_store.db import connect

con = connect(read_only=True)
rows = con.execute("""
with m as (
  select trade_date, industry_1, industry_2, industry_3, sh_index_pct_chg, total_amount, advancers
  from fact_market_daily
  where trade_date between '2026-04-01' and '2026-06-05'
), dr as (
  select trade_date, sw_l1, count(*) dr_count, sum(amount) dr_amount
  from fact_sector_daily
  where pct_chg>0 and diff_ratio>10 and amount>500
  group by trade_date, sw_l1
)
select m.trade_date, m.industry_1, m.industry_2, m.industry_3,
       m.sh_index_pct_chg, m.total_amount, m.advancers,
       coalesce(d1.dr_count,0) c1, coalesce(d2.dr_count,0) c2, coalesce(d3.dr_count,0) c3,
       coalesce(d1.dr_amount,0)+coalesce(d2.dr_amount,0)+coalesce(d3.dr_amount,0) dr_amount
from m
left join dr d1 on d1.trade_date=m.trade_date and d1.sw_l1=m.industry_1
left join dr d2 on d2.trade_date=m.trade_date and d2.sw_l1=m.industry_2
left join dr d3 on d3.trade_date=m.trade_date and d3.sw_l1=m.industry_3
where coalesce(d1.dr_count,0)+coalesce(d2.dr_count,0)+coalesce(d3.dr_count,0) > 0
order by m.trade_date
""").fetchall()
con.close()
for r in rows:
    print(r)
