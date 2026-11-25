"""科创50：0-100分仓位打分系统 + 分批进出节奏回测 + 真实日期举例。

打分维度（T日收盘可算）：
  趋势40 = 站MA20(15) + 站MA60(15) + 站MA120(10)
  动量25 = ret20>0(12) + ret60>0(13)
  量能15 = 量比>0.9(8) + 量比>1.2(7)
  情绪20 = fear<40(20) / 40-70(12) / 70-85(5) / >85(0)；RV分位>90 扣10
仓位映射：<40=0% / 40-55=25% / 55-70=50% / 70-85=75% / >=85=100%
周期上限：熊×0.5 / 动荡×0.75 / 牛×1.0
离场：跌破MA20 或 移动止损5% → 强制归零 + 冷静5日
"""
import sqlite3
import pandas as pd
import numpy as np

pd.set_option('display.width', 260)
pd.set_option('display.max_columns', 60)

c = sqlite3.connect('data/ashare.db')
df = pd.read_sql("""
    select p.trade_date,p.open,p.high,p.low,p.close,p.amount,
           f.fear_composite,f.fear_rv_pct,f.rv20
    from px_index_daily_csi p
    left join mkt_fear_daily f on p.trade_date=f.trate and f.index_code='000688'
    where p.index_code='000688' order by p.trade_date
""", c) if False else pd.read_sql("""
    select p.trade_date,p.open,p.high,p.low,p.close,p.amount,
           f.fear_composite,f.fear_rv_pct,f.rv20
    from px_index_daily_csi p
    left join mkt_fear_daily f on p.trade_date=f.trade_date and f.index_code='000688'
    where p.index_code='000688' order by p.trade_date
""", c)
df['trade_date'] = pd.to_datetime(df.trade_date)
for w in [20,60,120,200]:
    df[f'ma{w}'] = df.close.rolling(w,min_periods=w).mean()
for w in [20,60]:
    df[f'ret{w}'] = df.close/df.close.shift(w)-1
df['amt_ratio'] = df.amount/df.amount.rolling(20).mean()
df['ma200_slope'] = df.ma200-df.ma200.shift(60)
def regime(r):
    if r.close>r.ma200 and r.ma200_slope>0: return '牛'
    if r.close<r.ma200 and r.ma200_slope<0: return '熊'
    return '动荡'
df['regime']=df.apply(regime,axis=1)

# ---------- 打分 ----------
s = pd.Series(0, index=df.index)
s += np.where(df.close>df.ma20,15,0)
s += np.where(df.close>df.ma60,15,0)
s += np.where(df.close>df.ma120,10,0)
s += np.where(df.ret20>0,12,0)
s += np.where(df.ret60>0,13,0)
s += np.where(df.amt_ratio>0.9,8,0)
s += np.where(df.amt_ratio>1.2,7,0)
s += np.where(df.fear_composite<40,20,
     np.where(df.fear_composite<70,12,
     np.where(df.fear_composite<85,5,0)))
s -= np.where(df.fear_rv_pct>90,10,0)
df['score']=s.clip(0,100)

def posmap(x):
    return 0.0 if x<40 else 0.25 if x<55 else 0.50 if x<70 else 0.75 if x<85 else 1.0
df['pos_raw']=df.score.map(posmap)
cap={'熊':0.5,'动荡':0.75,'牛':1.0}
df['pos']=df.pos_raw*df.regime.map(cap)

# ---------- 回测：仓位T日算，T+1生效 ----------
START,END=pd.Timestamp('2020-11-24'),pd.Timestamp('2026-11-20')
ret=df.close.pct_change()
pos=df.pos.shift(1)  # T日信号T+1生效
mask=(df.trade_date>=START)&(df.trade_date<=END)
port=ret*pos
nav=(1+port[mask].fillna(0)).cumprod()
peak=nav.cummax(); mdd=(nav/peak-1).min()
ann=nav.iloc[-1]**(252/len(nav))-1
print(f"打分系统净值 {nav.iloc[-1]:.3f} 年化{ann*100:.2f}% 回撤{mdd*100:.2f}% 平均仓位{pos[mask].mean()*100:.1f}%")
print(f"基准买入持有 {(df.close[mask].iloc[-1]/df.close[mask].iloc[0]-1)*100:+.1f}%")

# ------ 备选仓位映射网格 ------
print("\n=== 仓位映射网格 ===")
for cuts in [ (35,50,65,80), (40,55,70,85), (45,60,75,90), (30,45,60,75) ]:
    pr=df.score.map(lambda x: 0.0 if x<cuts[0] else 0.25 if x<cuts[1] else 0.50 if x<cuts[2] else 0.75 if x<cuts[3] else 1.0)
    pp=(pr*df.regime.map(cap)).shift(1)
    nv=(1+(ret*pp)[mask].fillna(0)).cumprod()
    pk=nv.cummax()
    print(f"分档{cuts} 终值{nv.iloc[-1]:.3f} 年化{(nv.iloc[-1]**(252/len(nv))-1)*100:5.2f}% 回撤{(nv/pk-1).min()*100:6.2f}% 均仓{pp[mask].mean()*100:.0f}%")

# ---------- 真实日期举例 ----------
DATES=['2024-09-20','2024-09-27','2024-09-30','2024-10-08','2025-07-15','2025-10-09',
       '2026-01-09','2026-04-16','2026-07-01','2026-07-20','2026-09-28','2026-11-20']
print("\n========== 真实日期打分明细 ==========")
print(f"{'日期':<12}{'收盘':>8}{'趋势':>6}{'动量':>6}{'量能':>6}{'情绪':>6}{'总分':>6}{'周期':>6}{'仓位':>6}")
for d in DATES:
    r=df[df.trade_date==pd.Timestamp(d)]
    if r.empty: continue
    r=r.iloc[0]
    trend=(r.close>r.ma20)*15+(r.close>r.ma60)*15+(r.close>r.ma120)*10
    mom=(r.ret20>0)*12+(r.ret60>0)*13
    vol=(r.amt_ratio>0.9)*8+(r.amt_ratio>1.2)*7
    emo=20 if r.fear_composite<40 else 12 if r.fear_composite<70 else 5 if r.fear_composite<85 else 0
    emo-=10 if r.fear_rv_pct>90 else 0
    print(f"{d:<12}{r.close:>8.0f}{trend:>6.0f}{mom:>6.0f}{vol:>6.0f}{emo:>6.0f}{r.score:>6.0f}{r.regime:>6}{r.pos*100:>5.0f}%")

# ---------- 移动止损演示：找一段真实行情 ----------
print("\n========== 移动止损演示（2026-04-16进场那一段） ==========")
sub=df[(df.trade_date>='2026-04-16')&(df.trade_date<='2026-07-31')].copy()
ep=sub.open.iloc[0]; pk=ep
for _,r in sub.iterrows():
    pk=max(pk,r.high)
    if r.trade_date.day in [16,20,25,30] or r.close<pk*0.95:
        print(f"{r.trade_date.date()} 收{r.close:7.1f} 峰值{pk:7.1f} 峰值回撤{(r.close/pk-1)*100:6.2f}% "
              f"{'触发5%移动止损' if r.close<=pk*0.95 else ''}")
        if r.close<=pk*0.95: break
