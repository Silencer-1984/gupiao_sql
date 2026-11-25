# -*- coding: utf-8 -*-
"""科创50两次科技大涨的量价异常分析（纯交易数据，不含新闻）。

R1: 2025年 DeepSeek 行情（2025-01 ~ 2025-04）
R2: 2026年 4-5月行情（2026-04 ~ 2026-05）

输出：
1. 两次行情的起止、涨幅、持续时间
2. 成交量/成交额异常：放量倍数、量比、连续放量天数
3. 涨速异常：单日大涨次数、连阳、跳空
4. 波动率/恐慌度：RV20、QVIX、fear_composite 的变化
5. 均线偏离、量价背离
6. 顶部特征（事后）
"""
import sqlite3
import numpy as np
import pandas as pd

pd.set_option('display.width', 240)
pd.set_option('display.max_columns', 60)

c = sqlite3.connect('data/ashare.db')
df = pd.read_sql("""
    select p.trade_date, p.open, p.high, p.low, p.close, p.pct_chg, p.amount, p.pe_ttm,
           f.rv20, f.rv60, f.dvol20, f.dd60, f.qvix, f.fear_composite, f.fear_rv_pct, f.fear_qvix_pct
    from px_index_daily_csi p
    left join mkt_fear_daily f on p.trade_date=f.trade_date and f.index_code='000688'
    where p.index_code='000688' and p.close!=1000 order by p.trade_date
""", c)
df['trade_date'] = pd.to_datetime(df.trade_date)
df = df.reset_index(drop=True)

for w in [5, 10, 20, 60, 120]:
    df[f'ma{w}'] = df.close.rolling(w, min_periods=w).mean()
for w in [5, 10, 20]:
    df[f'ret{w}'] = df.close / df.close.shift(w) - 1
df['amt_ma20'] = df.amount.rolling(20, min_periods=20).mean()
df['amt_ma60'] = df.amount.rolling(60, min_periods=60).mean()
df['ar20'] = df.amount / df.amt_ma20          # 量比（20日）
df['ar60'] = df.amount / df.amt_ma60
df['gap'] = df.open / df.close.shift(1) - 1    # 跳空
df['amp'] = (df.high - df.low) / df.close.shift(1)  # 振幅
df['dist_ma20'] = df.close / df.ma20 - 1
df['dist_ma60'] = df.close / df.ma60 - 1


def rally_window(s, e, label):
    return df[(df.trade_date >= s) & (df.trade_date <= e)].copy(), label


def profile(w, label):
    if not len(w):
        print(f"\n[{label}] 无数据")
        return
    print(f"\n{'='*88}")
    print(f"[{label}]  {w.trade_date.iloc[0].date()} ~ {w.trade_date.iloc[-1].date()}  {len(w)}个交易日")
    print(f"{'='*88}")
    first, last = w.close.iloc[0], w.close.iloc[-1]
    imax = w.close.idxmax(); imin = w.close.idxmin()
    peak = w.close.max(); trough = w.close.min()
    print(f"区间起止: {first:.1f} → {last:.1f} ({(last/first-1)*100:+.1f}%)")
    print(f"区间最低 {trough:.1f}({w.loc[imin,'trade_date'].date()}) 最高 {peak:.1f}({w.loc[imax,'trade_date'].date()}) "
          f"峰谷幅度 {(peak/trough-1)*100:+.1f}%")
    # 量能
    print(f"\n--- 量能 ---")
    print(f"成交额均值 {w.amount.mean():.0f} 亿  区间前20日均值(基准) {df[df.trade_date<w.trade_date.iloc[0]].amount.tail(20).mean():.0f} 亿")
    print(f"量比(ar20): 均值{w.ar20.mean():.2f} 最大{w.ar20.max():.2f} "
          f"放量天数(>1.5)={int((w.ar20>1.5).sum())}  剧烈放量(>2.0)={int((w.ar20>2.0).sum())}")
    print(f"连续放量(ar20>1.3)最长 {max_run(w.ar20>1.3)} 日")
    # 涨速
    print(f"\n--- 涨速与形态 ---")
    print(f"单日涨>3%: {int((w.pct_chg>3).sum())}次  涨>5%: {int((w.pct_chg>5).sum())}次  "
          f"跌<-3%: {int((w.pct_chg<-3).sum())}次")
    print(f"跳空高开>1%: {int((w.gap>0.01).sum())}次  跳空低开<-1%: {int((w.gap<-0.01).sum())}次  "
          f"最大跳空 {w.gap.max()*100:+.2f}%")
    print(f"连阳最长 {max_run(w.close>w.close.shift(1))} 日  平均振幅 {w.amp.mean()*100:.2f}%")
    # 波动率/情绪
    print(f"\n--- 波动率与情绪 ---")
    print(f"RV20: 起{w.rv20.iloc[0]:.1f} → 高{w.rv20.max():.1f} → 末{w.rv20.iloc[-1]:.1f}")
    print(f"QVIX: 起{w.qvix.iloc[0]:.1f} → 高{w.qvix.max():.1f} → 末{w.qvix.iloc[-1]:.1f}")
    print(f"fear_composite: 起{w.fear_composite.iloc[0]:.0f} → 高{w.fear_composite.max():.0f} → 末{w.fear_composite.iloc[-1]:.0f}")
    print(f"fear_rv_pct: 起{w.fear_rv_pct.iloc[0]:.0f} → 高{w.fear_rv_pct.max():.0f} → 末{w.fear_rv_pct.iloc[-1]:.0f}")
    print(f"dd60: 最低{w.dd60.min():.1f}%  距MA20峰值 {(w.dist_ma20.max())*100:+.1f}%  "
          f"距MA60峰值 {(w.dist_ma60.max())*100:+.1f}%")
    print(f"PE_TTM: 起{w.pe_ttm.iloc[0]:.1f} → 末{w.pe_ttm.iloc[-1]:.1f}")


def max_run(mask):
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


# 先粗定位：打印2025-01~2025-05 与 2026-03~2026-06 的月度
print("=" * 88)
print("粗定位：月度收盘与成交额")
for s, e in [('2025-01-01', '2025-05-31'), ('2026-03-01', '2026-06-30')]:
    m = df[(df.trade_date >= s) & (df.trade_date <= e)].copy()
    g = m.set_index('trade_date').resample('ME').agg({'close': ['first', 'max', 'last'], 'amount': 'mean', 'ar20': 'mean'})
    g.columns = ['开', '高', '收', '日均成交', '均量比']
    g['月涨跌%'] = (g['收'] / g['开'] - 1) * 100
    print(f"\n{s} ~ {e}")
    print(g.round(2).to_string())

# 两次行情窗口（先设宽窗口，profile 后细调）
r1, _ = rally_window('2025-01-01', '2025-04-30', 'R1 2025 DeepSeek行情（宽窗口）')
r2, _ = rally_window('2026-04-01', '2026-05-31', 'R2 2026年4-5月行情（宽窗口）')
profile(r1, 'R1 2025 DeepSeek行情（宽窗口 1-4月）')
profile(r2, 'R2 2026年4-5月行情（宽窗口）')

# 逐日明细（关键段）
for s, e, label in [('2025-01-20', '2025-03-15', 'R1逐日'), ('2026-04-01', '2026-05-31', 'R2逐日')]:
    w = df[(df.trade_date >= s) & (df.trade_date <= e)].copy()
    print(f"\n{'='*88}")
    print(f"[{label}] 逐日  {s} ~ {e}")
    cols = ['trade_date', 'close', 'pct_chg', 'amount', 'ar20', 'gap', 'amp', 'rv20', 'qvix', 'fear_composite', 'fear_rv_pct', 'dist_ma20']
    out = w[cols].copy()
    out['trade_date'] = out.trade_date.dt.strftime('%m-%d')
    print(out.round(2).to_string(index=False))
