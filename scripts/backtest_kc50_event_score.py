"""科创50 事件驱动评分体系验证。
目标：把"重大 AI/科技新闻"转成可观测的市场反应评分，验证能否抓住事件行情。
事件样本：全历史中单日涨幅>=3%且量比>=0.9 的"新闻反应型"交易日（去重20日）。
评分维度：当日反应强度 / 量能确认 / 相对大盘超额 / 前期位置 / 情绪极端度。
时序：T日收盘可观测，T+1开盘买入，统计后续收益。
"""
import sqlite3
import pandas as pd
import numpy as np

pd.set_option('display.width', 260)
pd.set_option('display.max_columns', 60)

c = sqlite3.connect('data/ashare.db')


def load(code, fear=True):
    if fear:
        q = """select p.trade_date,p.open,p.close,p.amount,p.pct_chg,p.pe_ttm,
               f.fear_composite,f.fear_rv_pct,f.dd60,f.rv20
               from px_index_daily_csi p left join mkt_fear_daily f
               on p.trade_date=f.trade_date and f.index_code='000688'
               where p.index_code=? order by p.trade_date"""
    else:
        q = "select trade_date,open,close,amount,pct_chg from px_index_daily_csi where index_code=? order by trade_date"
    d = pd.read_sql(q, c, params=(code,))
    d['trade_date'] = pd.to_datetime(d.trade_date)
    d = d[d.close != 1000].reset_index(drop=True)
    return d


kc = load('000688')
sh = load('000001', fear=False).rename(columns={'close': 'sh_close', 'pct_chg': 'sh_pct', 'amount': 'sh_amt'})
d = kc.merge(sh[['trade_date', 'sh_close', 'sh_pct']], on='trade_date', how='left')

for w in [5, 20, 60]:
    d[f'amt_ma{w}'] = d.amount.rolling(w, min_periods=w).mean()
d['ar'] = d.amount / d.amt_ma20
d['ma20'] = d.close.rolling(20).mean()
d['ma60'] = d.close.rolling(60).mean()
d['pos_ma60'] = d.close / d.ma60 - 1
d['ret20'] = d.close / d.close.shift(20) - 1
d['excess'] = d.pct_chg - d.sh_pct
d['fwd5'] = d.close.shift(-5) / d.close - 1
d['fwd10'] = d.close.shift(-10) / d.close - 1
d['fwd20'] = d.close.shift(-20) / d.close - 1
d['fwd40'] = d.close.shift(-40) / d.close - 1
d['fwd60'] = d.close.shift(-60) / d.close - 1
d['max20'] = d.close.shift(-1).rolling(20).max().shift(-19)  # 买入后20日最高收盘

NXT_OPEN = d.open.shift(-1)  # T+1开盘价
d['nxt_open'] = NXT_OPEN
CLOSE = d.close.values
OPENN = d.open.values

print("=" * 110)
print("一、2026 两次事件逐日：事件日的市场反应（可观测信号）")
print("=" * 110)
EVENTS = [
    ('2026-01-21', 'OpenClaw龙虾概念启动'),
    ('2026-02-26', '英伟达财报+OpenClaw热度'),
    ('2026-05-25', '存储涨价/三大原厂满载'),
    ('2026-06-12', 'SK海力士设备涨价+费半+7.9%'),
    ('2026-06-15', '存储主升'),
    ('2026-06-17', 'HBM/电子布五轮提价'),
    ('2026-06-22', '三大原厂Q3涨价15-30%'),
]
for dt, name in EVENTS:
    r = d[d.trade_date == dt]
    if r.empty:
        continue
    r = r.iloc[0]
    i = r.name
    b = OPENN[i + 1] if i + 1 < len(d) else np.nan
    rr = [CLOSE[i + n] / b - 1 if i + n < len(d) and np.isfinite(b) else np.nan for n in (5, 20, 40)]
    print(f"{dt} {name:<24} 涨{r.pct_chg:+5.2f}% 量比{r.ar:4.2f} 超额{r.excess:+5.2f}pp "
          f"距MA60 {r.pos_ma60*100:+5.1f}% 恐慌{r.fear_composite:4.0f} RV分位{(r.fear_rv_pct if pd.notna(r.fear_rv_pct) else float('nan')):4.0f} "
          f"→ T+1买 后续5/20/40日: {rr[0]*100:+5.1f}%/{rr[1]*100:+5.1f}%/{rr[2]*100:+5.1f}%")

print("\n" + "=" * 110)
print("二、全历史事件样本：单日涨>=3% 且 量比>=0.9（去重20日），T+1开盘买入")
print("=" * 110)
ev = d[(d.pct_chg >= 3.0) & (d.ar >= 0.9) & (d.trade_date >= '2020-01-01')].copy()
picks = []
for i in ev.index:
    if not picks or i - picks[-1] >= 20:
        picks.append(i)
ev = d.loc[picks].dropna(subset=['fwd20', 'nxt_open']).copy()
ev['buy_px'] = ev.nxt_open
# 按原始索引 i 取 T+1 之后第 N 日收盘，避免子集 shift 错位
ev['r5'] = [CLOSE[i + 5] / ev.loc[i, 'buy_px'] - 1 if i + 5 < len(d) else np.nan for i in ev.index]
ev['r20'] = [CLOSE[i + 20] / ev.loc[i, 'buy_px'] - 1 if i + 20 < len(d) else np.nan for i in ev.index]
ev['r40'] = [CLOSE[i + 40] / ev.loc[i, 'buy_px'] - 1 if i + 40 < len(d) else np.nan for i in ev.index]
print(f"事件样本 n={len(ev)}")
print(f"T+1开盘买入后: 5日均{ev.r5.mean()*100:+.2f}% (胜{(ev.r5>0).mean()*100:.0f}%) | "
      f"20日均{ev.r20.mean()*100:+.2f}% (胜{(ev.r20>0).mean()*100:.0f}%) | "
      f"40日均{ev.r40.mean()*100:+.2f}% (胜{(ev.r40>0).mean()*100:.0f}%)")
print(f"基准(全样本T+1买) 20日均 {d.dropna(subset=['fwd20']).fwd20.mean()*100:+.2f}%")

print("\n--- 逐事件明细（近3年） ---")
sub = ev[ev.trade_date >= '2023-11-01']
for _, r in sub.iterrows():
    print(f" {r.trade_date.date()} 涨{r.pct_chg:+5.2f}% 量比{r.ar:4.2f} 超额{r.excess:+5.2f}pp "
          f"距MA60{r.pos_ma60*100:+6.1f}% 恐慌{r.fear_composite:4.0f} → 20日{r.r20*100:+6.1f}% 40日{r.r40*100:+6.1f}%")

print("\n" + "=" * 110)
print("三、评分维度有效性：把事件按各维度分组，看T+1买入后20日收益")
print("=" * 110)
dims = [
    ('当日涨幅>=5%', ev.pct_chg >= 5, ev.pct_chg < 5),
    ('量比>=1.3', ev.ar >= 1.3, ev.ar < 1.3),
    ('超额>=2pp', ev.excess >= 2, ev.excess < 2),
    ('距MA60>0(趋势上)', ev.pos_ma60 > 0, ev.pos_ma60 <= 0),
    ('恐慌<50', ev.fear_composite < 50, ev.fear_composite >= 50),
    ('RV分位<80', ev.fear_rv_pct < 80, ev.fear_rv_pct >= 80),
    ('PE分位<中位', ev.pe_ttm < ev.pe_ttm.median(), ev.pe_ttm >= ev.pe_ttm.median()),
]
for name, hi, lo in dims:
    a, b = ev[hi.fillna(False)], ev[lo.fillna(False)]
    if len(a) >= 5 and len(b) >= 5:
        print(f"{name:<20} 满足n={len(a):3d} 20日均{a.r20.mean()*100:+6.2f}% 胜{(a.r20>0).mean()*100:5.1f}% | "
              f"不满足n={len(b):3d} {b.r20.mean()*100:+6.2f}% 胜{(b.r20>0).mean()*100:5.1f}% | 差{(a.r20.mean()-b.r20.mean())*100:+6.2f}pp")

print("\n" + "=" * 110)
print("四、复合评分卡：5维度各1分，检验分数与收益关系")
print("=" * 110)
ev['score'] = (
    (ev.pct_chg >= 5).astype(int) +
    (ev.ar >= 1.3).astype(int) +
    (ev.excess >= 2).astype(int) +
    (ev.pos_ma60 > 0).astype(int) +
    (ev.fear_composite < 50).astype(int)
)
for s in sorted(ev.score.unique()):
    a = ev[ev.score == s]
    print(f" 评分{s}分 n={len(a):3d}  20日均{a.r20.mean()*100:+6.2f}% 胜{(a.r20>0).mean()*100:5.1f}%  "
          f"40日均{a.r40.mean()*100:+6.2f}%")

print("\n--- 高分组(>=4分)逐事件 ---")
for _, r in ev[ev.score >= 4].iterrows():
    print(f" {r.trade_date.date()} 分{r.score} 涨{r.pct_chg:+.1f}% → 20日{r.r20*100:+.1f}%")

print("\n" + "=" * 110)
print("五、持有期与离场：事件后 SETUP（T+1买，跌破MA20/持有N日）")
print("=" * 110)
ma20_arr = d.ma20.values
close_arr = d.close.values
nxt_open_arr = d.nxt_open.values
dt_arr = d.trade_date.values


def event_trade(i, exit_rule):
    buy = nxt_open_arr[i]
    if not np.isfinite(buy):
        return np.nan
    for j in range(i + 1, min(i + 61, len(d))):
        # 收盘跌破MA20 离场（T日收盘信号，T+1开盘执行，近似用当日收盘）
        if exit_rule == 'ma20' and np.isfinite(ma20_arr[j]) and close_arr[j] < ma20_arr[j]:
            return close_arr[j] / buy - 1
        if exit_rule == 'hold20' and j == i + 20:
            return close_arr[j] / buy - 1
        if exit_rule == 'hold40' and j == i + 40:
            return close_arr[j] / buy - 1
    return close_arr[min(i + 20, len(d) - 1)] / buy - 1


for rule in ['hold20', 'hold40', 'ma20']:
    rr = np.array([event_trade(i, rule) for i in ev.index])
    rr = rr[np.isfinite(rr)]
    print(f" {rule:<8} n={len(rr):3d} 均{rr.mean()*100:+6.2f}% 中位{np.median(rr)*100:+6.2f}% 胜{(rr>0).mean()*100:5.1f}%")
