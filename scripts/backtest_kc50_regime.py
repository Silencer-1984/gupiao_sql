"""科创50：按市场周期分regime + 止损线网格验证（修复时序：T日信号→T+1开盘成交）。

Regime（T日及之前数据，无未来函数）：
  牛/快速发展：close>MA200 且 MA200 60日斜率>0
  熊/长熊    ：close<MA200 且 MA200 60日斜率<0
  动荡/纠结  ：其余

止损：fixed_X=入场价下方X%；trail_X=峰值回撤X%；maN=跌破N日均线。
"""
import sqlite3
import pandas as pd
import numpy as np

pd.set_option('display.width', 260)
pd.set_option('display.max_columns', 60)

c = sqlite3.connect('data/ashare.db')
df = pd.read_sql("""
    select p.trade_date, p.open, p.high, p.low, p.close, p.amount, p.pe_ttm,
           f.rv20, f.fear_composite, f.fear_rv_pct, f.dd60
    from px_index_daily_csi p
    left join mkt_fear_daily f on p.trade_date=f.trade_date and f.index_code='000688'
    where p.index_code='000688' order by p.trade_date
""", c)
df['trade_date'] = pd.to_datetime(df.trade_date)
for w in [10, 20, 30, 60, 120, 200]:
    df[f'ma{w}'] = df.close.rolling(w, min_periods=w).mean()
for w in [20, 60]:
    df[f'ret{w}'] = df.close / df.close.shift(w) - 1
df['amt_ratio'] = df.amount / df.amount.rolling(20).mean()
df['ma200_slope'] = df.ma200 - df.ma200.shift(60)

def regime(r):
    if r.close > r.ma200 and r.ma200_slope > 0: return '牛/快速发展'
    if r.close < r.ma200 and r.ma200_slope < 0: return '熊/长熊'
    return '动荡/纠结'
df['regime'] = df.apply(regime, axis=1)

print("========== Regime 连续分段（>=20交易日） ==========")
blocks = df.regime.ne(df.regime.shift()).cumsum()
for (rid, blk), g in df.groupby(['regime', blocks]):
    if len(g) >= 20:
        print(f"{rid:<12} {g.trade_date.iloc[0].date()} ~ {g.trade_date.iloc[-1].date()}  {len(g):3d}日")
print("占比:", (df.regime.value_counts(normalize=True)*100).round(1).to_dict())

# ---------- 回测引擎 ----------
START, END = pd.Timestamp('2020-11-24'), pd.Timestamp('2026-11-20')

def run(entry, stop_spec, label, s=START, e=END, regime_filter=None, detail=False):
    typ, val = stop_spec
    ee = entry.shift(1).fillna(False).values
    op, hi, lo, cl, dt = (df[k].values for k in ['open','high','low','close','trade_date'])
    ma60, maN = df.ma60.values, (df[f'ma{val}'].values if typ=='ma' else None)
    cash, shares, pos = 1.0, 0.0, False
    entry_px, peak_px, ei, sell_next, reason_next = 0.0, 0.0, 0, False, None
    eq, trades, n_enter, n_stop = [], [], 0, 0
    for i in range(len(df)):
        d = pd.Timestamp(dt[i])
        if d < s or d > e: continue
        # 1) 执行昨日收盘产生的卖出信号（今日开盘成交）
        if pos and sell_next:
            xp = op[i]
            trades.append(dict(entry=str(pd.Timestamp(dt[ei]).date()), ep=entry_px,
                               exit=str(d.date()), xp=xp, pnl=xp/entry_px-1, reason=reason_next))
            cash = shares*xp; pos=False; shares=0.0
            n_stop += (reason_next=='stop')
            sell_next=False; reason_next=None
        # 2) 执行昨日进场信号（今日开盘成交）
        if (not pos) and ee[i]:
            if regime_filter is None or df.regime.iloc[i] in regime_filter:
                shares=cash/op[i]; cash=0.0; pos=True
                entry_px=op[i]; peak_px=op[i]; ei=i; n_enter+=1
        # 3) 今日收盘后计算明日卖出信号（止损判断用收盘价，峰值用最高价）
        if pos:
            peak_px=max(peak_px, hi[i])
            if   typ=='fixed' and cl[i] <= entry_px*(1-val): sell_next,reason_next=True,'stop'
            elif typ=='trail' and peak_px>entry_px and cl[i] <= peak_px*(1-val): sell_next,reason_next=True,'stop'
            elif typ=='ma' and not np.isnan(maN[i]) and cl[i] < maN[i]: sell_next,reason_next=True,'stop'
            elif cl[i] < ma60[i]: sell_next,reason_next=True,'ma60'
        else:
            sell_next=False; reason_next=None
        # 4) 权益按今日收盘
        eq.append(shares*cl[i]+cash)
    # 期末未平仓按最后收盘价
    if pos:
        xp=cl[len(df)-1]
        trades.append(dict(entry=str(pd.Timestamp(dt[ei]).date()), ep=entry_px,
                           exit=str(pd.Timestamp(dt[len(df)-1]).date()), xp=xp,
                           pnl=xp/entry_px-1, reason='open_end'))
    eq=np.array(eq)
    peak=np.maximum.accumulate(eq)
    mdd=(eq/peak-1).min()
    ann=eq[-1]**(252/len(eq))-1
    rets=pd.Series(eq).pct_change().dropna()
    sharpe=rets.mean()/rets.std()*np.sqrt(252) if rets.std()>0 else 0
    print(f"{label:<32} 终值{eq[-1]:.3f} 年化{ann*100:6.2f}% 回撤{mdd*100:6.2f}% "
          f"夏普{sharpe:5.2f} 进{n_enter:3d} 止损{n_stop:3d}")
    if detail and trades:
        t=pd.DataFrame(trades)
        print(t.assign(ep=t.ep.round(1),xp=t.xp.round(1),pnl=(t.pnl*100).round(1)).to_string(index=False))
    return eq, dict(final=eq[-1], ann=ann, mdd=mdd, sharpe=sharpe, n_enter=n_enter, n_stop=n_stop)

e5 = (df.close > df.ma120) & (df.ret20 > 0) & (df.ret60 > 0) & (df.amt_ratio > 0.9)
e10 = (df.close > df.ma20) & (df.ret20 > 0) & (df.amt_ratio > 0.9)

specs = [ (('none',None),'无止损(MA60)') ] \
      + [ (('fixed',x),f'固定止损-{x*100:.0f}%') for x in [0.03,0.05,0.08,0.10,0.12,0.15] ] \
      + [ (('trail',x),f'移动止损{x*100:.0f}%') for x in [0.04,0.05,0.06,0.08,0.10,0.12,0.15] ] \
      + [ (('ma',x),f'离场MA{x}') for x in [10,20,30] ]

print("\n========== A. S5 稳健版 止损网格（2020-11~2026-11） ==========")
for spec,lab in specs: run(e5, spec, lab)
print("\n========== B. S10 频繁版 止损网格 ==========")
for spec,lab in specs: run(e10, spec, lab)

print("\n========== C. 分周期独立回测（各段空仓起算） ==========")
periods = [
    ('长熊 2021-07~2022-12','2021-07-01','2022-12-31'),
    ('熊尾磨底 2023-01~2024-08','2023-01-01','2024-08-31'),
    ('快速发展 2024-09~2025-10','2024-09-01','2025-10-09'),
    ('动荡挤泡沫 2025-10~2026-11','2025-10-10','2026-11-20'),
]
for pname,s,e in periods:
    s,e=pd.Timestamp(s),pd.Timestamp(e)
    px0=df.loc[df.trade_date>=s,'open'].iloc[0]; px1=df.loc[df.trade_date<=e,'close'].iloc[-1]
    print(f"\n--- {pname} 基准 {(px1/px0-1)*100:+.1f}% ---")
    for sn,entry in [('S5',e5),('S10',e10)]:
        for spec,lab in [(('none',None),'无止损'),(('fixed',0.08),'固定-8%'),
                         (('trail',0.06),'移动6%'),(('trail',0.10),'移动10%')]:
            run(entry,spec,f'  {sn} {lab}',s=s,e=e)

print("\n========== D. Regime 自适应（牛/动荡用S10，熊用S5） ==========")
adapt = pd.Series(False, index=df.index)
bear = df.regime=='熊/长熊'
adapt = np.where(bear, e5, e10)
adapt = pd.Series(adapt, index=df.index)
for spec,lab in [(('none',None),'自适应无止损'),(('fixed',0.08),'自适应+固定-8%'),
                 (('trail',0.06),'自适应+移动6%'),(('trail',0.10),'自适应+移动10%')]:
    run(adapt,spec,lab)
