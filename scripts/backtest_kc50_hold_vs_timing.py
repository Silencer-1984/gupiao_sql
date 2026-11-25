"""科创50：一次性 vs 分批建仓、长期底仓、一直不卖 vs 择时的公平对比。
Q1 分批 vs 一次性（同一进场信号，全周期/近两年/分周期年化）
Q2 长期底仓（永远不卖的一小笔钱）该何时入场
Q3 一直不卖 vs 恐慌崩盘才卖：回撤/回本时间/终值
时序：T日收盘信号，T+1开盘成交。成本按双边0.05%。
"""
import sqlite3
import pandas as pd
import numpy as np

pd.set_option('display.width', 260)
pd.set_option('display.max_columns', 60)

c = sqlite3.connect('data/ashare.db')
df = pd.read_sql("""
    select p.trade_date,p.open,p.high,p.low,p.close,p.amount,p.pe_ttm,
           f.fear_composite,f.fear_rv_pct,f.rv20,f.dd60
    from px_index_daily_csi p
    left join mkt_fear_daily f on p.trade_date=f.trade_date and f.index_code='000688'
    where p.index_code='000688' and p.close!=1000 order by p.trade_date
""", c)
df['trade_date'] = pd.to_datetime(df.trade_date)
df = df.reset_index(drop=True)
for w in [20, 60, 120, 200]:
    df[f'ma{w}'] = df.close.rolling(w, min_periods=w).mean()
for w in [20, 60]:
    df[f'ret{w}'] = df.close / df.close.shift(w) - 1
df['amt_ratio'] = df.amount / df.amount.rolling(20).mean()
df['ma200_slope'] = df.ma200 - df.ma200.shift(60)

def regime(r):
    if r.close > r.ma200 and r.ma200_slope > 0: return '牛'
    if r.close < r.ma200 and r.ma200_slope < 0: return '熊'
    return '动荡'
df['regime'] = df.apply(regime, axis=1)

def rpct(s, win=750, minp=250):
    return s.rolling(win, min_periods=minp).apply(
        lambda x: float((x[:-1] < x[-1]).mean()) if len(x) > 1 else np.nan, raw=True)
df['pe_pct3'] = rpct(df.pe_ttm)

COST = 0.0005
START, END = pd.Timestamp('2020-01-02'), df.trade_date.iloc[-1]
TWO_Y = pd.Timestamp('2024-11-22')

def stats(nav, dates, label):
    nav = pd.Series(nav, index=pd.DatetimeIndex(dates))
    if len(nav) < 20: return None
    f = nav.iloc[-1]
    days = len(nav)
    ann = f ** (252 / days) - 1
    mdd = (nav / nav.cummax() - 1).min()
    vol = nav.pct_change().std() * np.sqrt(252)
    sh = ann / vol if vol > 0 else 0
    return dict(label=label, f=f, ann=ann, mdd=mdd, sharpe=sh, days=days)

def show(rows):
    print(f"{'方案':<30}{'终值':>8}{'年化':>9}{'最大回撤':>10}{'夏普':>7}{'交易日':>7}")
    for r in rows:
        if r is None: continue
        print(f"{r['label']:<30}{r['f']:>8.3f}{r['ann']*100:>8.2f}%{r['mdd']*100:>9.2f}%{r['sharpe']:>7.2f}{r['days']:>7}")

print("\n" + "=" * 80)
print("Q1 一次性 vs 分批建仓（进场：站MA20+ret20正+量比>0.9；离场：破MA20）")
print("=" * 80)
entry = (df.close > df.ma20) & (df.ret20 > 0) & (df.amt_ratio > 0.9)
exit_ = df.close < df.ma20
ee = entry.shift(1).fillna(False).values
xx = exit_.shift(1).fillna(False).values
op, cl, dt = df.open.values, df.close.values, df.trade_date.values

def run_build(batches, s=START, e=END):
    """基于目标仓位序列累乘收益，避免现金/份额模拟的数值漂移。"""
    m = (df.trade_date >= s) & (df.trade_date <= e)
    tgt = np.zeros(len(df))
    pos, build_i, cool = False, 0, 0
    for i in range(len(df)):
        if not m.iloc[i]: continue
        if cool > 0: cool -= 1
        if pos and xx[i]:
            pos = False; cool = 5; build_i = 0
        if (not pos) and ee[i] and cool == 0:
            pos = True; build_i = 0
        if pos:
            build_i += 1
            if batches == 1: tgt[i] = 1.0
            elif build_i <= 1: tgt[i] = 1.0 / batches
            elif build_i <= int(np.ceil(batches / 2)): tgt[i] = 2.0 / batches
            else: tgt[i] = 1.0
    ts = pd.Series(tgt, index=df.index)
    ret = df.close.pct_change().fillna(0)
    dpos = ts.diff().abs().fillna(0)
    port = ts.shift(1).fillna(0) * ret - dpos * COST
    nav = (1 + port[m]).cumprod()
    return nav.values

rows = []
for n, name in [(1, '一次性满仓'), (3, '分3批建仓'), (5, '分5批建仓')]:
    rows.append(stats(run_build(n), df[(df.trade_date >= START) & (df.trade_date <= END)].trade_date, name))
bh = df[(df.trade_date >= START) & (df.trade_date <= END)].close
rows.append(stats((bh / bh.iloc[0]).values, df[(df.trade_date >= START) & (df.trade_date <= END)].trade_date, '买入持有基准'))
print("\n--- 全周期 2020-01 ~ 2026-11 ---"); show(rows)

rows2 = []
for n, name in [(1, '一次性满仓'), (3, '分3批建仓'), (5, '分5批建仓')]:
    rows2.append(stats(run_build(n, TWO_Y, END), df[(df.trade_date >= TWO_Y) & (df.trade_date <= END)].trade_date, name))
bh2 = df[(df.trade_date >= TWO_Y) & (df.trade_date <= END)].close
rows2.append(stats((bh2 / bh2.iloc[0]).values, df[(df.trade_date >= TWO_Y) & (df.trade_date <= END)].trade_date, '买入持有基准'))
print("\n--- 近两年 2024-11 ~ 2026-11 ---"); show(rows2)

periods = [
    ('长熊 21-07~22-12', '2021-07-01', '2022-12-31'),
    ('熊尾磨底 23-01~24-08', '2023-01-01', '2024-08-31'),
    ('快速发展 24-09~25-10', '2024-09-01', '2025-10-09'),
    ('动荡挤泡沫 25-10~26-11', '2025-10-10', '2026-11-20'),
]
print("\n--- 分周期：一次性S10 vs 买入持有（年化） ---")
print(f"{'周期':<26}{'一次性S10':>12}{'买入持有':>12}{'超额':>10}")
for nm, s, e in periods:
    s, e = pd.Timestamp(s), pd.Timestamp(e)
    r = stats(run_build(1, s, e), df[(df.trade_date >= s) & (df.trade_date <= e)].trade_date, '')
    sub = df[(df.trade_date >= s) & (df.trade_date <= e)].close
    bhann = (sub.iloc[-1] / sub.iloc[0]) ** (252 / len(sub)) - 1
    extra = (r['ann'] - bhann) * 100 if r else 0
    print(f"{nm:<26}{r['ann']*100:>11.1f}%{bhann*100:>11.1f}%{extra:>9.1f}pp" if r else nm)

print("\n" + "=" * 80)
print("Q2 长期底仓（买入后一直持有到今天）：不同入场规则对比")
print("=" * 80)
print("规则：满足条件的每一天都买入并持有至今，统计所有买入点的持有到期年化收益分布")

def entry_hold(mask, name, horizon_days=None):
    idx = np.where(mask.fillna(False).values)[0]
    if len(idx) == 0:
        print(f"{name:<28} 无信号"); return
    rets = []
    for i in idx:
        j = min(i + horizon_days, len(df) - 1) if horizon_days else len(df) - 1
        if j <= i: continue
        yrs = (df.trade_date.iloc[j] - df.trade_date.iloc[i]).days / 365.25
        if yrs < 0.5: continue
        base = df.open.iloc[i]
        if base > 0:
            rets.append((df.close.iloc[j] / base) ** (1 / yrs) - 1)
    if not rets:
        print(f"{name:<28} 持有期不足"); return
    a = np.array(rets)
    print(f"{name:<28} 信号{len(idx):>4}次 年化中位{np.median(a)*100:>6.1f}% "
          f"均值{a.mean()*100:>6.1f}% 正收益占比{(a>0).mean()*100:>5.1f}%")

entry_hold(pd.Series(True, index=df.index), '① 任意日买入(定投近似)')
entry_hold(df.pe_pct3 < 0.2, '② PE3年分位<20%')
entry_hold(df.pe_pct3 < 0.1, '③ PE3年分位<10%')
entry_hold(df.dd60 < -20, '④ 60日回撤<-20%')
entry_hold(df.dd60 < -30, '⑤ 60日回撤<-30%')
entry_hold(df.fear_rv_pct > 90, '⑥ RV恐慌分位>90')
entry_hold((df.close < df.ma200) & (df.ma200_slope < 0), '⑦ 熊市中买入')
entry_hold((df.close > df.ma200) & (df.ma200_slope > 0), '⑧ 牛市中买入')

print("\n" + "=" * 80)
print("Q3 一直不卖 vs 恐慌/崩盘才卖（全周期 2020-01 ~ 2026-11）")
print("=" * 80)
def run_sell_rule(sell_cond, cooldown=0, name=''):
    cash, shares, pos = 1.0, 0.0, True
    shares = cash / op[0]
    cool, eq, n_sell = 0, [], 0
    for i in range(len(df)):
        d = pd.Timestamp(dt[i])
        if d < START or d > END: continue
        if cool > 0: cool -= 1
        if pos and sell_cond[i] and cool == 0:
            cash = shares * op[i] * (1 - COST); pos = False; shares = 0.0; n_sell += 1
            cool = cooldown
        elif (not pos) and cool == 0:
            shares = cash / op[i] * (1 - COST); cash = 0.0; pos = True
        eq.append(shares * cl[i] + cash)
    sub = df[(df.trade_date >= START) & (df.trade_date <= END)]
    return stats(eq, sub.trade_date, name), n_sell

sc_none = pd.Series(False, index=df.index).values
sc_fear = (df.fear_composite > 90).shift(1).fillna(False).values
sc_dd = (df.dd60 < -30).shift(1).fillna(False).values
for sc, cd, nm in [
    (sc_none, 0, '一直不卖'),
    (sc_fear, 20, '恐慌>90卖+20日买回'),
    (sc_fear, 60, '恐慌>90卖+60日买回'),
    (sc_dd, 20, '回撤<-30%卖+20日买回'),
]:
    r, ns = run_sell_rule(sc, cd, nm)
    print(f"{nm:<26} 终值{r['f']:>7.3f} 年化{r['ann']*100:>6.2f}% 回撤{r['mdd']*100:>7.2f}% 卖出{ns:>2}次")

print("\n--- 深度回撤后的回本时间（一直不卖要熬多久） ---")
for yr in ['2020', '2021']:
    s = df[(df.trade_date >= yr + '-01-01') & (df.trade_date <= yr + '-12-31')]
    i = s.close.idxmax(); p = df.close.iloc[i]
    rec = df[df.index > i]; rec = rec[rec.close >= p]
    if len(rec):
        print(f"{yr}年高点 {df.trade_date.iloc[i].date()} {p:.0f} → 收复 {rec.trade_date.iloc[0].date()} "
              f"（{((rec.trade_date.iloc[0]-df.trade_date.iloc[i]).days/365.25):.1f}年）")
    else:
        print(f"{yr}年高点 {p:.0f} 至今未收复，已 {(df.trade_date.iloc[-1]-df.trade_date.iloc[i]).days/365.25:.1f}年")
