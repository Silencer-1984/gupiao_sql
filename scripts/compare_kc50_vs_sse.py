"""科创50 vs 上证指数：验证"大盘涨→科创涨更多"传导假设，最近三年。
纯本地数据。信号只用历史，未来收益仅用于统计检验（非交易）。
"""
import sqlite3
import numpy as np
import pandas as pd

pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 60)

c = sqlite3.connect('data/ashare.db')
CODES = {'000001': '上证', '000300': '沪深300', '000985': '中证全指', '000688': '科创50'}
cols = {}
for code, name in CODES.items():
    d = pd.read_sql("select trade_date,close from px_index_daily_csi where index_code=? order by trade_date",
                    c, params=(code,))
    d['trade_date'] = pd.to_datetime(d.trade_date)
    if code == '000688':
        d = d[d.trade_date >= '2020-01-01']   # 2019-12-31 前为基期占位 1000
    cols[name] = d.set_index('trade_date')['close']
    print(f"{name:<8} {d.trade_date.min().date()} ~ {d.trade_date.max().date()}  n={len(d)}")

px = pd.DataFrame(cols).dropna()
START = pd.Timestamp('2023-11-20')
p3 = px[px.index >= START].copy()
print(f"\n共同区间 {p3.index.min().date()} ~ {p3.index.max().date()}  交易日 {len(p3)}")


def stat(s):
    r = s.pct_change().dropna()
    cum = s.iloc[-1] / s.iloc[0] - 1
    ann = (1 + cum) ** (252 / len(r)) - 1
    vol = r.std() * np.sqrt(252)
    mdd = (s / s.cummax() - 1).min()
    return (f"累计{cum*100:7.1f}%  年化{ann*100:7.2f}%  波动{vol*100:6.1f}%  "
            f"回撤{mdd*100:7.1f}%  夏普{ann/vol:5.2f}")


print("\n" + "=" * 100)
print("一、三年总览 2023-11 ~ 2026-11")
print("=" * 100)
for name in CODES.values():
    print(f"{name:<8} 起{p3[name].iloc[0]:8.1f} 终{p3[name].iloc[-1]:8.1f}  {stat(p3[name])}")

print("\n--- 分年度收益 ---")
yr = p3.resample('YE').last()
yr_ret = yr.pct_change()
yr_ret.iloc[0] = yr.iloc[0] / p3.iloc[0] - 1
print((yr_ret * 100).round(1).to_string())

r = p3.pct_change().dropna()
x = r['上证'].values
y = r['科创50'].values

print("\n" + "=" * 100)
print("二、弹性 beta：科创50 对 上证")
print("=" * 100)
b_all = np.polyfit(x, y, 1)[0]
b_up = np.polyfit(x[x > 0], y[x > 0], 1)[0]
b_dn = np.polyfit(x[x < 0], y[x < 0], 1)[0]
corr = np.corrcoef(x, y)[0, 1]
print(f"全样本beta={b_all:.2f}  上行beta={b_up:.2f}  下行beta={b_dn:.2f}  "
      f"日相关={corr:.3f}  R2={corr**2:.3f}")
print(f"上证涨日 n={(x>0).sum():4d} 科创均{y[x>0].mean()*100:+.2f}% | "
      f"上证跌日 n={(x<0).sum():4d} 科创均{y[x<0].mean()*100:+.2f}%")

print("\n--- 按上证当日涨跌分组，科创50 同期表现 ---")
for lo, hi, label in [(-np.inf, -0.02, '上证<-2%'), (-0.02, 0, '上证-2%~0'),
                      (0, 0.01, '上证0~1%'), (0.01, np.inf, '上证>1%')]:
    m = (x > lo) & (x <= hi)
    if m.sum() > 5:
        ratio = y[m].mean() / x[m].mean() if abs(x[m].mean()) > 1e-9 else np.nan
        print(f"{label:<14} n={m.sum():4d}  上证均{x[m].mean()*100:+6.2f}%  "
              f"科创均{y[m].mean()*100:+6.2f}%  倍数{ratio:5.2f}  科创胜率{(y[m]>0).mean()*100:5.1f}%")

print("\n--- 领先滞后：corr(上证[t-k], 科创[t])，k>0 表示上证领先 ---")
for k in [0, 1, 2, 3, 5, 10]:
    a = r['上证'].shift(k)
    b = r['科创50']
    m = a.notna() & b.notna()
    print(f"  k={k:2d}  corr={np.corrcoef(a[m], b[m])[0, 1]:.3f}")

print("\n" + "=" * 100)
print("三、核心：知道大盘在涨后买谁，未来 20 日各指数收益")
print("=" * 100)
fwd = pd.DataFrame({name: p3[name].shift(-20) / p3[name] - 1 for name in CODES.values()})

# 信号A：上证过去20日涨幅
sig = p3['上证'] / p3['上证'].shift(20) - 1
tmp = pd.DataFrame({'sig': sig}).join(fwd).dropna()
tmp['grp'] = pd.qcut(tmp['sig'], 5, labels=False)
print("\n[信号A] 上证过去20日涨幅 五档 → 未来20日收益")
print(f"{'档位':<14}{'上证过去20日':>13}" + "".join(f"{n:>12}" for n in CODES.values()))
for g in range(5):
    sub = tmp[tmp.grp == g]
    print(f"G{g} {'低→高':<10}{sub.sig.mean()*100:>12.1f}%" + "".join(f"{sub[n].mean()*100:>11.1f}%" for n in CODES.values()))
print(f"{'无条件基准':<14}{'':>13}" + "".join(f"{tmp[n].mean()*100:>11.1f}%" for n in CODES.values()))
for cond, label in [(tmp.sig > 0, '上证过去20日>0'), (tmp.sig <= 0, '上证过去20日<=0')]:
    sub = tmp[cond]
    print(f"{label:<20} n={len(sub):4d}  科创未来20日{sub['科创50'].mean()*100:+6.2f}%  "
          f"胜率{(sub['科创50']>0).mean()*100:5.1f}%  "
          f"超额(vs上证){(sub['科创50']-sub['上证']).mean()*100:+6.2f}pp")

# 信号B：上证站上MA60
ma60 = p3['上证'].rolling(60, min_periods=60).mean()
sig2 = (p3['上证'] > ma60)
tmp2 = pd.DataFrame({'sig2': sig2}).join(fwd).dropna()
print("\n[信号B] 上证站上MA60 → 未来20日收益")
print(f"{'状态':<14}{'n':>6}" + "".join(f"{n:>12}" for n in CODES.values()))
for v, label in [(True, '站上MA60'), (False, '跌破MA60')]:
    sub = tmp2[tmp2.sig2 == v]
    print(f"{label:<14}{len(sub):>6}" + "".join(f"{sub[n].mean()*100:>11.1f}%" for n in CODES.values()))

print("\n" + "=" * 100)
print("四、风险对比")
print("=" * 100)
try:
    mo = p3.resample('ME').last().pct_change().dropna()
except Exception:
    mo = p3.resample('M').last().pct_change().dropna()
for name in CODES.values():
    dnvol = r.loc[r[name] < 0, name].std() * np.sqrt(252)
    print(f"{name:<8} 最差月{mo[name].min()*100:6.1f}%  最好月{mo[name].max()*100:6.1f}%  "
          f"月胜率{(mo[name]>0).mean()*100:5.1f}%  下行波动{dnvol*100:5.1f}%")
print(f"\n上证单日<-2% ({(x<-0.02).sum()}天): 科创均{y[x<-0.02].mean()*100:+.2f}% "
      f"最差{y[x<-0.02].min()*100:+.2f}%")
print(f"上证单日>2% ({(x>0.02).sum()}天): 科创均{y[x>0.02].mean()*100:+.2f}% "
      f"最好{y[x>0.02].max()*100:+.2f}%")
