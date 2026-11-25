# -*- coding: utf-8 -*-
"""验证两次大涨中观察到的量价异常，是否具备提前预测力（全历史样本）。

候选信号：
A 放量突破日：ar20>1.4 且 pct_chg>3 且 close>MA20
B RV20短期跃升：rv20 / rv20.shift(10) > 1.30
C 量比极值日：ar20 > 2.0
D 距MA20过热：dist_ma20 > 0.15
E RV恐慌分位>90（已知负面，对照）
F 跳空高开+放量：gap>0.01 且 ar20>1.3

方法：信号去重（间隔20日），统计信号后 5/20/60 日收益均值+胜率，
并与全样本基准对比。区分"进场信号"（看未来正收益）和"离场信号"（看未来负收益）。
"""
import sqlite3
import numpy as np
import pandas as pd

pd.set_option('display.width', 220)

c = sqlite3.connect('data/ashare.db')
df = pd.read_sql("""
    select p.trade_date,p.open,p.high,p.low,p.close,p.pct_chg,p.amount,
           f.rv20,f.qvix,f.fear_composite,f.fear_rv_pct,f.dd60
    from px_index_daily_csi p left join mkt_fear_daily f
    on p.trade_date=f.trade_date and f.index_code='000688'
    where p.index_code='000688' and p.close!=1000 order by p.trade_date
""", c)
df['trade_date'] = pd.to_datetime(df.trade_date)
df = df[df.trade_date >= '2020-01-01'].reset_index(drop=True)

for w in [20, 60]:
    df[f'ma{w}'] = df.close.rolling(w, min_periods=w).mean()
df['ar20'] = df.amount / df.amount.rolling(20, min_periods=20).mean()
df['gap'] = df.open / df.close.shift(1) - 1
df['dist_ma20'] = df.close / df.ma20 - 1
df['rv_jump10'] = df.rv20 / df.rv20.shift(10)

for h in [5, 20, 60]:
    df[f'fwd{h}'] = df.close.shift(-h) / df.close - 1

base = df.dropna(subset=['fwd20', 'fwd60', 'fwd5'])
print("全样本基准:", len(base), "个交易日")
for h in [5, 20, 60]:
    print(f"  未来{h}日 均值{base[f'fwd{h}'].mean()*100:+.2f}% 胜率{(base[f'fwd{h}']>0).mean()*100:.0f}%")


def dedup(idx, gap=20):
    out = []
    for i in idx:
        if not out or i - out[-1] >= gap:
            out.append(i)
    return out


def test(name, mask, kind='entry'):
    idx = dedup(list(df[mask.fillna(False)].index))
    valid = [i for i in idx if pd.notna(df.fwd20.iloc[i]) and pd.notna(df.fwd5.iloc[i])]
    if len(valid) < 5:
        print(f"{name:<28} 样本不足({len(valid)})")
        return
    rows = []
    for h in [5, 20, 60]:
        v = df[f'fwd{h}'].iloc[valid].dropna()
        rows.append(f"{h}日{v.mean()*100:+.2f}%/(胜{(v>0).mean()*100:.0f}%)")
    print(f"{name:<28} n={len(valid):3d}  " + "  ".join(rows))


print("\n" + "=" * 100)
print("进场类信号（信号后收益应为正，才有用）")
print("=" * 100)
test("A 放量突破 ar>1.4涨>3站MA20", (df.ar20 > 1.4) & (df.pct_chg > 3) & (df.close > df.ma20))
test("A2 放量突破(+量比>1.7)", (df.ar20 > 1.7) & (df.pct_chg > 3) & (df.close > df.ma20))
test("B RV20十日跃升>30%", df.rv_jump10 > 1.30)
test("B2 RV20十日跃升>50%", df.rv_jump10 > 1.50)
test("F 跳空高开>1%+放量>1.3", (df.gap > 0.01) & (df.ar20 > 1.3))
test("F2 单日涨>5%+放量>1.3", (df.pct_chg > 5) & (df.ar20 > 1.3))

print("\n" + "=" * 100)
print("离场类信号（信号后收益应为负，才有用）")
print("=" * 100)
test("C 量比极值 ar20>2.0", df.ar20 > 2.0)
test("D 距MA20>15%", df.dist_ma20 > 0.15)
test("D2 距MA20>10%", df.dist_ma20 > 0.10)
test("E RV分位>90", df.fear_rv_pct > 90)
test("E2 fear_composite>75", df.fear_composite > 75)

print("\n" + "=" * 100)
print("组合信号：放量突破 + 不过热（过滤掉高位放量）")
print("=" * 100)
test("A+距MA20<10%+RV分位<90",
     (df.ar20 > 1.4) & (df.pct_chg > 3) & (df.close > df.ma20)
     & (df.dist_ma20 < 0.10) & (df.fear_rv_pct < 90))
test("A+距MA20<10%",
     (df.ar20 > 1.4) & (df.pct_chg > 3) & (df.close > df.ma20) & (df.dist_ma20 < 0.10))

print("\n" + "=" * 100)
print("两次行情关键日的信号状态（一次性放量日 vs 顶部日）")
print("=" * 100)
key = ['2025-02-05', '2025-02-21', '2025-02-26', '2025-02-28',
       '2026-04-08', '2026-05-06', '2026-05-25', '2026-05-29']
for ds in key:
    r = df[df.trade_date == ds]
    if not len(r):
        continue
    r = r.iloc[0]
    print(f"{ds} close={r.close:7.1f} 涨{r.pct_chg:+5.2f}% 量比{r.ar20:4.2f} "
          f"RV跃升{r.rv_jump10:4.2f} 距MA20{r.dist_ma20*100:+5.1f}% "
          f"RV分位{r.fear_rv_pct:4.0f} fear{r.fear_composite:4.0f} "
          f"→ 后20日{(r.fwd20*100 if pd.notna(r.fwd20) else float('nan')):+6.1f}%")
