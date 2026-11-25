"""科创50两策略 2024-09 以来实盘复盘：进场次数/日期/收益明细。"""
import sqlite3
import pandas as pd
import numpy as np

pd.set_option('display.width', 240)
pd.set_option('display.max_columns', 60)

c = sqlite3.connect('data/ashare.db')
df = pd.read_sql("""
    select p.trade_date, p.open, p.high, p.low, p.close, p.amount,
           f.fear_composite, f.fear_rv_pct, f.rv20
    from px_index_daily_csi p
    left join mkt_fear_daily f on p.trade_date=f.trade_date and f.index_code='000688'
    where p.index_code='000688' order by p.trade_date
""", c)
df['trade_date'] = pd.to_datetime(df.trade_date)
for w in [20, 60, 120]:
    df[f'ma{w}'] = df.close.rolling(w).mean()
for w in [20, 60]:
    df[f'ret{w}'] = df.close / df.close.shift(w) - 1
df['amt_ratio'] = df.amount / df.amount.rolling(20).mean()

START, END = pd.Timestamp('2024-09-01'), pd.Timestamp('2026-11-20')
BULL_END = pd.Timestamp('2025-02-28')     # 用户口径：半年长牛；市场实际顶部 2025-10

# S5 原版（回测年化8.71%的口径）与报告版（+恐慌/VV风控）
e5 = (df.close > df.ma120) & (df.ret20 > 0) & (df.ret60 > 0) & (df.amt_ratio > 0.9)
e5r = e5 & (df.fear_composite < 85) & (df.fear_rv_pct <= 90)
e10 = (df.close > df.ma20) & (df.ret20 > 0) & (df.amt_ratio > 0.9)
x_exit = df.close < df.ma60

def trade_log(entry, exit_, label):
    ee, xx = entry.shift(1).fillna(False).values, exit_.shift(1).fillna(False).values
    op, hi, lo, cl, dt = (df[k].values for k in ['open', 'high', 'low', 'close', 'trade_date'])
    pos, ei, ep, rows = False, None, None, []
    for i in range(len(df)):
        d = pd.Timestamp(dt[i])
        if d < START:
            continue
        if d > END:
            break
        if pos and xx[i]:
            rows.append(dict(entry=pd.Timestamp(dt[ei]).date(), ep=ep,
                             exit=pd.Timestamp(dt[i]).date(), xp=op[i],
                             days=i - ei, pnl=op[i]/ep - 1,
                             mfe=hi[ei:i+1].max()/ep - 1,
                             mae=lo[ei:i+1].min()/ep - 1, open_end=False))
            pos = False
        if (not pos) and ee[i]:
            pos, ei, ep = True, i, op[i]
    if pos:
        rows.append(dict(entry=pd.Timestamp(dt[ei]).date(), ep=ep,
                         exit=pd.Timestamp(dt[len(df)-1]).date(), xp=cl[-1],
                         days=len(df)-1-ei, pnl=cl[-1]/ep - 1,
                         mfe=hi[ei:].max()/ep - 1, mae=lo[ei:].min()/ep - 1,
                         open_end=True))
    t = pd.DataFrame(rows)
    print(f"\n========== {label}：区间内进场 {len(t)} 次 ==========")
    if len(t) == 0:
        return t
    t['阶段'] = np.where(t.entry <= BULL_END.date(), '半年长牛', '一年半动荡')
    disp = t.copy()
    for col in ['ep','xp']:
        disp[col] = disp[col].map(lambda v: f"{v:.1f}")
    for col in ['pnl','mfe','mae']:
        disp[col] = disp[col].map(lambda v: f"{v*100:+.1f}%")
    print(disp[['entry','ep','exit','xp','days','pnl','mfe','mae','阶段','open_end']]
          .to_string(index=False, header=['进场日','进场价','出场日','出场价','持有日','收益','最大浮盈','最大浮亏','阶段','未平仓']))
    wins = (t.pnl > 0).sum()
    print(f"汇总: 胜率 {wins}/{len(t)} ({wins/len(t)*100:.0f}%)  "
          f"单笔均值 {t.pnl.mean()*100:+.2f}%  中位 {t.pnl.median()*100:+.2f}%  "
          f"最好 {t.pnl.max()*100:+.1f}%  最差 {t.pnl.min()*100:+.1f}%  "
          f"复利累计 {(1+t.pnl).prod()*100-100:+.1f}%")
    print("分阶段:", ' | '.join(
        f"{g}: {len(sub)}次, 胜{(sub.pnl>0).sum()}, 均值{sub.pnl.mean()*100:+.1f}%, 累计{(1+sub.pnl).prod()*100-100:+.1f}%"
        for g, sub in t.groupby('阶段', sort=False)))
    return t

t5 = trade_log(e5, x_exit, 'S5 稳健版（原版：MA120+双动量+量比>0.9）')
t5r = trade_log(e5r, x_exit, 'S5 报告版（+恐慌<85 & RV分位<=90）')
t10 = trade_log(e10, x_exit, 'S10 频繁版（站MA20+ret20正+量比>0.9）')

# 基准对比
px0 = df.loc[df.trade_date >= START, 'open'].iloc[0]
px1 = df.loc[df.trade_date <= END, 'close'].iloc[-1]
print(f"\n基准: 2024-09-02 开盘 {px0:.1f} → 2026-11-20 收盘 {px1:.1f} = {(px1/px0-1)*100:+.1f}%")
