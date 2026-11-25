"""科创50离场→红利反向轮动策略验证（重写版，严格T+1，无未来函数）。

验证用户假设：科创策略离场后抄底红利，动荡期尤其有效。
标的：科创000688 / 中证红利000922（带日频股息率 val_index_dividend_yield）。

V1 相关性（去情绪化）
V2 科创见顶时红利股息率是否在高位（用户形容词去情绪化）
V3 双资产轮动：科创S10+MA20离场 / 科创+红利多方案，统一T+1引擎

核心引擎：T日收盘算信号，T+1开盘执行；仓位用t-1信号决定t日收益；切换扣双边0.05%。
"""
import sqlite3
import pandas as pd
import numpy as np

pd.set_option('display.width', 260)
pd.set_option('display.max_columns', 60)
c = sqlite3.connect('data/ashare.db')

def load_index(code):
    d = pd.read_sql("select trade_date,open,high,low,close from px_index_daily_csi "
                    "where index_code=? order by trade_date", c, params=(code,))
    d['trade_date'] = pd.to_datetime(d.trade_date)
    return d[d.close != 1000].reset_index(drop=True)

kc = load_index('000688').rename(columns={'close':'kc_close','open':'kc_open','trade_date':'date'})
div = load_index('000922')[['trade_date','close']].rename(columns={'trade_date':'date','close':'div_close'})
dy = pd.read_sql("select trade_date,div_yield from val_index_dividend_yield "
                 "where index_code='000922' order by trade_date", c)
dy['trade_date'] = pd.to_datetime(dy.trade_date)
dy = dy.rename(columns={'trade_date':'date','div_yield':'div_yield'})
bond = pd.read_sql("select trade_date,cn_10y from macro_bond_yield order by trade_date", c)
bond['trade_date'] = pd.to_datetime(bond.trade_date)
bond = bond.rename(columns={'trade_date':'date','cn_10y':'bond10'})
fear = pd.read_sql("select trade_date,fear_rv_pct from mkt_fear_daily "
                   "where index_code='000688' order by trade_date", c)
fear['trade_date'] = pd.to_datetime(fear.trade_date)
fear = fear.rename(columns={'trade_date':'date','fear_rv_pct':'rv_pct'})

df = (kc.merge(div, on='date', how='left').merge(dy, on='date', how='left')
        .merge(bond, on='date', how='left').merge(fear, on='date', how='left')
        .sort_values('date').reset_index(drop=True))
for w in [20, 120, 200]:
    df[f'ma{w}'] = df.kc_close.rolling(w, min_periods=w).mean()
for w in [20, 60]:
    df[f'ret{w}'] = df.kc_close / df.kc_close.shift(w) - 1
df['ma200_slope'] = df.ma200 - df.ma200.shift(60)
df['kc_ret'] = df.kc_close.pct_change()
df['div_ret'] = df.div_close.pct_change()
df['div_ma20'] = df.div_close.rolling(20).mean()
df['div_ma60'] = df.div_close.rolling(60).mean()
df['dy_pct'] = df.div_yield.rolling(750, min_periods=250).apply(
    lambda s: (s[:-1] < s[-1]).mean() if len(s) > 1 else np.nan, raw=True)
df['spread'] = df.div_yield - df.bond10

def regime(r):
    if r.kc_close > r.ma200 and r.ma200_slope > 0: return '牛'
    if r.kc_close < r.ma200 and r.ma200_slope < 0: return '熊'
    return '动荡'
df['regime'] = df.apply(regime, axis=1)

S, E = pd.Timestamp('2020-11-24'), pd.Timestamp('2026-11-20')
mask = (df.date >= S) & (df.date <= E)
w = df[mask].copy().reset_index(drop=True)
print(f"样本 {w.date.min().date()} ~ {w.date.max().date()} n={len(w)}")

# ============ V1 ============
print("\n" + "=" * 80)
print("V1 科创50 vs 中证红利 相关性（'负相关'假设去情绪化）")
print("=" * 80)
print(f"日度   r = {w.kc_ret.corr(w.div_ret):+.3f} (n={len(w)})")
tmp = w.set_index('date')[['kc_close','div_close']]
for freq, rule in [('周度','W'),('月度','ME')]:
    px = tmp.resample(rule).last()
    print(f"{freq}   r = {px.kc_close.pct_change().corr(px.div_close.pct_change()):+.3f}")
print("\n分 regime 日度相关:")
for rg in ['牛','动荡','熊']:
    sub = w[w.regime == rg]
    print(f"  {rg:<4} r = {sub.kc_ret.corr(sub.div_ret):+.3f} (n={len(sub)})")
roll = w.kc_ret.rolling(40).corr(w.div_ret)
print(f"\n40日滚动相关: 最小{roll.min():+.2f} 中位{roll.median():+.2f} 最大{roll.max():+.2f} "
      f"| r<-0.3占比{(roll<-0.3).mean()*100:.1f}% r<-0.5占比{(roll<-0.5).mean()*100:.1f}%")

# ============ V2 ============
print("\n" + "=" * 80)
print("V2 科创见顶 vs 红利股息率位置（用户形容词去情绪化）")
print("=" * 80)
w['kc_hi60'] = w.kc_close.rolling(60).max()
w['at_high'] = w.kc_close >= w.kc_hi60 * 0.98
hi = w[w.at_high & w.dy_pct.notna()]
lo = w[(~w.at_high) & w.dy_pct.notna()]
print(f"科创接近60日高点时 → 红利股息率【分位】均值 {hi.dy_pct.mean()*100:.1f}% (n={len(hi)})")
print(f"其他时点           → 红利股息率【分位】均值 {lo.dy_pct.mean()*100:.1f}% (n={len(lo)})")
print(f"科创收盘 vs 红利股息率【水平值】相关 = {w.kc_close.corr(w.div_yield):+.3f}")
print(f"科创20日收益 vs 红利股息率【分位】相关 = {w.ret20.corr(w.dy_pct):+.3f}")
print(f"\n当前(2026-11-20): 科创{w.kc_close.iloc[-1]:.0f} 红利股息率{w.div_yield.iloc[-1]:.2f}% "
      f"分位{w.dy_pct.iloc[-1]*100:.0f}% 利差{w.spread.iloc[-1]:.2f}pp")

# ============ V3 引擎 ============
print("\n" + "=" * 80)
print("V3 双资产轮动（严格T日信号→T+1执行，成本双边0.05%）")
print("=" * 80)
COST = 0.0005
n = len(df)
kc_cl, kc_op = df.kc_close.values, df.kc_open.values
dv_cl = df.div_close.values
ma20, ma120 = df.ma20.values, df.ma120.values
ret20, ret60 = df.ret20.values, df.ret60.values
rv = df.rv_pct.values
dates = df.date.values
regs = df.regime.values
dy_pct = df.dy_pct.values
sprd = df.spread.values
dv_ma20, dv_ma60 = df.div_ma20.values, df.div_ma60.values
kc_ret, dv_ret = df.kc_ret.values, df.div_ret.values

# 科创信号（T日收盘）：进场 S10 = 站MA20+ret20正+RV分位<=90；离场=破MA20
kc_entry = (kc_cl > ma20) & (ret20 > 0) & (rv <= 90) & ~np.isnan(ma20) & ~np.isnan(rv)
kc_exit = (kc_cl < ma20) & ~np.isnan(ma20)

def run(div_entry=None, div_exit=None, only_regimes=None, label='', kc_on=True):
    """div_entry/div_exit: 函数(i)->bool; 科创空仓时是否持红利。"""
    eq = []; state = 'cash'; prev_state = 'cash'; n_kc = 0; n_dv = 0; switches = 0
    div_buy_i = None
    for t in range(1, n):
        d = pd.Timestamp(dates[t])
        if d < S or d > E:
            eq.append(np.nan); continue
        s = t - 1  # 用昨日收盘信号决定今日持仓
        # 1) 科创状态更新
        if state == 'kc' and kc_exit[s]:
            state = 'cash'; switches += 1
        if state != 'kc' and kc_on and kc_entry[s] and not kc_exit[s]:
            state = 'kc'; n_kc += 1; switches += 1
        # 2) 红利：仅当科创不在手且允许时
        allow_rg = only_regimes is None or regs[s] in only_regimes
        if state == 'cash' and div_entry is not None and allow_rg:
            if div_entry(s, div_buy_i):
                state = 'div'; n_dv += 1; div_buy_i = s; switches += 1
        if state == 'div' and div_exit is not None:
            if div_exit(s, div_buy_i) or kc_entry[s]:
                state = 'cash'; div_buy_i = None; switches += 1
        # 3) 今日收益（用t日收益，仓位由t-1信号决定；切换当日按新仓计）
        r = kc_ret[t] if state == 'kc' else (dv_ret[t] if state == 'div' else 0.0)
        r = 0.0 if np.isnan(r) else r
        cost = COST if switches > 0 and (t == 1 or state != prev_state) else 0.0
        eq.append(r - cost)
        prev_state = state
    if len(eq) < n:
        eq.append(0.0)
    eq = pd.Series(eq, index=df.date)
    eq = eq[(eq.index >= S) & (eq.index <= E)]
    nav = (1 + eq.fillna(0)).cumprod()
    f = nav.iloc[-1]; ann = f ** (252 / len(nav)) - 1
    mdd = (nav / nav.cummax() - 1).min()
    rr = nav.pct_change().dropna(); sh = rr.mean() / rr.std() * np.sqrt(252) if rr.std() > 0 else 0
    return dict(f=f, ann=ann, mdd=mdd, sh=sh, nk=n_kc, nd=n_dv, sw=switches)

def show(name, r):
    print(f"{name:<34}{r['f']:>8.3f}{r['ann']*100:>8.2f}%{r['mdd']*100:>9.2f}%{r['sh']:>7.2f}"
          f"{r['nk']:>6}{r['nd']:>6}{r['sw']:>6}")

print(f"\n{'方案':<34}{'终值':>8}{'年化':>9}{'回撤':>9}{'夏普':>7}{'科创次':>6}{'红利次':>6}{'切换':>6}")
base = run()
show('① 只做科创S10+MA20(基准)', base)

# 红利规则
always_e = lambda s, bi: True
dypct_e = lambda s, bi: not np.isnan(dy_pct[s]) and dy_pct[s] > 0.7
dypct_x = lambda s, bi: not np.isnan(dy_pct[s]) and dy_pct[s] < 0.3
spread_e = lambda s, bi: not np.isnan(sprd[s]) and sprd[s] > 2.5
spread_x = lambda s, bi: not np.isnan(sprd[s]) and sprd[s] < 1.5
ma20_x = lambda s, bi: not np.isnan(dv_ma20[s]) and dv_cl[s] < dv_ma20[s]
hold_x = lambda s, bi: bi is not None and s - bi >= 20

plans = [
    ('② 科创空仓→红利(无脑长期)', always_e, None, None),
    ('③ 红利:股息分位>70%买/<30%卖', dypct_e, dypct_x, None),
    ('④ 红利:利差>2.5%买/<1.5%卖', spread_e, spread_x, None),
    ('⑤ 红利:无脑买+破MA20卖', always_e, ma20_x, None),
    ('⑥ 红利:无脑买+持有20日卖', always_e, hold_x, None),
    ('⑦ 红利:分位>70%买+破MA20卖', dypct_e, ma20_x, None),
]
for name, de, dx, rg in plans:
    show(name, run(de, dx, rg))

print("\n--- 仅在动荡期做红利（用户核心假设） ---")
for name, de, dx in [
    ('⑧ 动荡期:无脑买红利', always_e, None),
    ('⑨ 动荡期:股息分位>70%买/<30%卖', dypct_e, dypct_x),
    ('⑩ 动荡期:利差>2.5%买/<1.5%卖', spread_e, spread_x),
]:
    show(name, run(de, dx, {'动荡'}))

# 红利单独持有
sub = df[mask]
nav = sub.div_close / sub.div_close.iloc[0]
print(f"\n{'红利000922买入持有':<34}{nav.iloc[-1]:>8.3f}{(nav.iloc[-1]**(252/len(nav))-1)*100:>8.2f}%"
      f"{(nav/nav.cummax()-1).min()*100:>9.2f}%")
