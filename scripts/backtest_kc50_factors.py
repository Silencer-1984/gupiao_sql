"""科创50择时因子与策略回测 — 纯本地数据，结果打印到 stdout。

因子范围：核心10个（趋势/动量/估值/情绪/量能），卖出统一用跌破MA60。
信号 T 日收盘生成，T+1 开盘成交，避免未来函数。
"""
import sqlite3
import numpy as np
import pandas as pd

pd.set_option('display.width', 240)
pd.set_option('display.max_columns', 60)

START, END = '2020-11-24', '2026-11-20'   # 最近 6 年
c = sqlite3.connect('data/ashare.db')
df = pd.read_sql("""
    select p.trade_date, p.open, p.high, p.low, p.close, p.pct_chg, p.amount, p.pe_ttm,
           f.rv20, f.rv60, f.dd60, f.qvix, f.fear_rv_pct, f.fear_qvix_pct, f.fear_composite
    from px_index_daily_csi p
    left join mkt_fear_daily f on p.trade_date=f.trade_date and f.index_code='000688'
    where p.index_code='000688'
    order by p.trade_date
""", c)
df['trade_date'] = pd.to_datetime(df.trade_date)
df = df.dropna(subset=['close']).reset_index(drop=True)
print("数据区间:", df.trade_date.min().date(), "~", df.trade_date.max().date(), "行数", len(df))
print("PE_TTM 摘要:\n", df.pe_ttm.describe(percentiles=[.01,.1,.5,.9,.99]).round(2).to_string())

# ---------- 因子构造（全样本预计算，回测区间截断） ----------
for w in [20, 60, 120, 250]:
    df[f'ma{w}'] = df.close.rolling(w, min_periods=w).mean()
for w in [5, 20, 60, 120]:
    df[f'ret{w}'] = df.close / df.close.shift(w) - 1

def rpct(s, win, minp=120):
    """滚动历史分位：当前值在过去 win 根里的百分位（0~1），不含自身比较偏差"""
    return s.rolling(win, min_periods=minp).apply(
        lambda x: float((x[:-1] < x[-1]).mean()) if len(x) > 1 else np.nan, raw=True)

df['pe_pct3'] = rpct(df.pe_ttm, 750)          # PE 3 年分位
df['fear_pct3'] = rpct(df.fear_composite, 750)
df['rv_pct3'] = rpct(df.rv20, 750)
df['amt_ma20'] = df.amount.rolling(20).mean()
df['amt_ratio'] = df.amount / df.amt_ma20
df['qvix_chg5'] = df.qvix / df.qvix.shift(5) - 1

df['fwd20'] = df.close.shift(-20) / df.close - 1
df['fwd60'] = df.close.shift(-60) / df.close - 1

w = df[(df.trade_date >= START) & (df.trade_date <= '2026-09-15')].copy()  # 留 fwd60 窗口
print("检验区间:", w.trade_date.min().date(), "~", w.trade_date.max().date(), "交易日", len(w))

# ---------- 1. 单因子分组检验（未来 60 日收益） ----------
print("\n========== 单因子检验：条件成立 vs 不成立 的未来60日收益 ==========")
print(f"{'因子':<24}{'不满足':>11}{'满足':>11}{'差值':>11}{'满足样本':>10}")

def test_binary(name, mask):
    v = w.loc[mask, 'fwd60'].dropna()
    iv = w.loc[~mask, 'fwd60'].dropna()
    if len(v) < 30 or len(iv) < 30:
        print(f"{name:<24}{'样本不足':>11}")
        return
    print(f"{name:<24}{iv.mean()*100:>10.2f}%{v.mean()*100:>10.2f}%"
          f"{(v.mean()-iv.mean())*100:>10.2f}pp{len(v):>10}")

test_binary('1 close>MA120', w.close > w.ma120)
test_binary('2 close>MA60', w.close > w.ma60)
test_binary('3 MA20>MA60', w.ma20 > w.ma60)
test_binary('4 ret20>0', w.ret20 > 0)
test_binary('5 ret60>0', w.ret60 > 0)
test_binary('6 pe_pct3<0.3', w.pe_pct3 < 0.3)
test_binary('7 fear<40', w.fear_composite < 40)
test_binary('8 fear>80', w.fear_composite > 80)
test_binary('9 fear_rv_pct>90', w.fear_rv_pct > 90)
test_binary('10 amt_ratio>1.3', w.amt_ratio > 1.3)
test_binary('rv_pct3>0.9', w.rv_pct3 > 0.9)
test_binary('dd60<-20', w.dd60 < -20)

print("\n--- 五分位分组：因子值由低到高的 fwd60 均值 ---")
for col in ['pe_pct3', 'fear_composite', 'ret20', 'amt_ratio']:
    tmp = w[[col, 'fwd60']].dropna().copy()
    try:
        tmp['grp'] = pd.qcut(tmp[col], 5, labels=False, duplicates='drop')
        g = tmp.groupby('grp').fwd60.agg(['mean', 'count'])
        print(f"{col:<18}" + '  '.join(
            f"G{i}:{r['mean']*100:+.1f}%(n{int(r['count'])})" for i, r in g.iterrows()))
    except Exception as e:
        print(col, 'err', e)

# ---------- 2. 策略回测 ----------
def backtest(entry, exit_, label):
    e = entry.shift(1).fillna(False).values       # T 日信号 -> T+1 开盘成交
    x = exit_.shift(1).fillna(False).values
    op, cl, dates = df.open.values, df.close.values, df.trade_date.values
    cash, shares, pos = 1.0, 0.0, False
    eq, dates_bt, ntrade = [], [], 0
    for i in range(len(df)):
        d = pd.Timestamp(dates[i])
        if d < pd.Timestamp(START) or d > pd.Timestamp(END):
            continue
        if pos and x[i]:
            cash = shares * op[i]; pos = False; shares = 0.0; ntrade += 1
        if (not pos) and e[i]:
            shares = cash / op[i]; cash = 0.0; pos = True; ntrade += 1
        eq.append(shares * cl[i] + cash)
        dates_bt.append(d)
    eq = np.array(eq)
    peak = np.maximum.accumulate(eq)
    mdd = (eq / peak - 1).min()
    ann = eq[-1] ** (252 / len(eq)) - 1
    rets = pd.Series(eq).pct_change().dropna()
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0
    ser = pd.Series(eq, index=pd.DatetimeIndex(dates_bt))
    yr_last = ser.resample('YE').last()
    yr = yr_last.pct_change()
    yr.iloc[0] = yr_last.iloc[0] - 1
    yr_txt = ' '.join(f"{t.year}:{v*100:+.0f}%" for t, v in yr.items())
    print(f"{label:<28} 终值{eq[-1]:.3f} 年化{ann*100:6.2f}% 回撤{mdd*100:6.2f}% "
          f"夏普{sharpe:5.2f} 交易{ntrade:3d}次 | {yr_txt}")
    return eq, pos

print("\n========== 策略回测（T+1开盘成交；卖出统一=跌破MA60） ==========")
backtest(pd.Series(True, index=df.index), pd.Series(False, index=df.index), 'S0 买入持有')

s1e = (df.close > df.ma120)
s1x = (df.close < df.ma60)
backtest(s1e, s1x, 'S1 趋势MA120')

s2e = (df.close > df.ma120) & (df.ret20 > 0) & (df.ret60 > 0)
backtest(s2e, s1x, 'S2 +20/60双动量')

backtest(s2e & (df.pe_pct3 < 0.85), s1x, 'S3 +PE分位<85%')
backtest(s2e & (df.fear_composite < 85), s1x, 'S4 +恐慌度<85')
backtest(s2e & (df.amt_ratio > 0.9), s1x, 'S5 +量比>0.9')
backtest(s2e & (df.pe_pct3 < 0.85) & (df.fear_composite < 85)
         & (df.amt_ratio > 0.9), s1x, 'S6 核心综合')

# 右侧确认类：等重新站上均线再进，不猜底
cross60_up = (df.close > df.ma60) & (df.close.shift(1) <= df.ma60.shift(1))
cross20_up = (df.close > df.ma20) & (df.close.shift(1) <= df.ma20.shift(1))
backtest(cross60_up & (df.amt_ratio > 0.9), s1x, 'S7 上穿MA60+量比')
backtest(cross60_up, s1x, 'S8 上穿MA60')
backtest(cross20_up & (df.amt_ratio > 1.0), s1x, 'S9 上穿MA20+量比')
backtest((df.close > df.ma20) & (df.ret20 > 0) & (df.amt_ratio > 0.9), s1x, 'S10 站MA20+动量+量')

# ---------- 3. 当前状态 ----------
print("\n========== 最新交易日信号状态 ==========")
last = df.iloc[-1]
items = [
    ('收盘价', f"{last.close:.2f}"),
    ('MA60', f"{last.ma60:.2f}"),
    ('MA120', f"{last.ma120:.2f}"),
    ('20日动量', f"{last.ret20*100:+.2f}%"),
    ('60日动量', f"{last.ret60*100:+.2f}%"),
    ('PE_TTM', f"{last.pe_ttm:.2f}"),
    ('PE 3年分位', f"{last.pe_pct3*100:.1f}%"),
    ('恐慌度', f"{last.fear_composite:.1f}"),
    ('RV恐慌分位', f"{last.fear_rv_pct:.1f}"),
    ('量比', f"{last.amt_ratio:.2f}"),
    ('60日回撤', f"{last.dd60:.1f}%"),
]
print(' | '.join(f"{k}={v}" for k, v in items))
print("进场条件:", "满足" if (last.close > last.ma120 and last.ret20 > 0 and last.ret60 > 0
      and last.pe_pct3 < 0.85 and last.fear_composite < 85 and last.amt_ratio > 0.9) else "不满足")
print("出场条件(破MA60):", "触发" if last.close < last.ma60 else "未触发")
print("距MA60:", f"{(last.close/last.ma60-1)*100:+.2f}%",
      " 距MA120:", f"{(last.close/last.ma120-1)*100:+.2f}%")