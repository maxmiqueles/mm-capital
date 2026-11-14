#!/usr/bin/env python3
"""MM Capital · reconstruye index.html con datos al día.

Uso:
    python build.py            descarga datos de Yahoo Finance y genera index.html
    python build.py --offline  usa los CSV guardados en data/ (para pruebas)

Pasos: 1) descarga precios y dividendos  2) arma los 4 fondos con reglas
point-in-time y corre el backtest  3) calcula métricas, crisis y cartera vigente
4) inserta los datos en template.html y escribe index.html
"""
import json, os, sys, time
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
os.makedirs(DATA, exist_ok=True)
OFFLINE = '--offline' in sys.argv

START = pd.Timestamp('2016-11-14')   # inicio del backtest
FEE = 0.0075                         # comisión anual de los fondos MM
TC = 0.001                           # costo por compra/venta
REBAL_MONTH_DAY = (11, 14)           # selección anual
# Supuestos de Chile mostrados como valores por defecto (editables en la página)
CL = {'dap': 0.045, 'ipc': 0.045,
      'dap_src': 'TPM del Banco Central de Chile, 4,5% (noviembre 2026)',
      'ipc_src': 'IPC a 12 meses, INE, octubre 2026: 4,5%'}

U = {
 'AAPL':'Tecnología','MSFT':'Tecnología','NVDA':'Tecnología','AVGO':'Tecnología','ORCL':'Tecnología','ADBE':'Tecnología','CRM':'Tecnología','CSCO':'Tecnología','TXN':'Tecnología','QCOM':'Tecnología','IBM':'Tecnología','INTU':'Tecnología',
 'GOOGL':'Comunicaciones','META':'Comunicaciones','NFLX':'Comunicaciones','VZ':'Comunicaciones','T':'Comunicaciones',
 'AMZN':'Consumo discrecional','HD':'Consumo discrecional','MCD':'Consumo discrecional','NKE':'Consumo discrecional','LOW':'Consumo discrecional','TJX':'Consumo discrecional','SBUX':'Consumo discrecional',
 'PG':'Consumo básico','KO':'Consumo básico','PEP':'Consumo básico','WMT':'Consumo básico','COST':'Consumo básico','CL':'Consumo básico','MO':'Consumo básico','PM':'Consumo básico',
 'JNJ':'Salud','UNH':'Salud','LLY':'Salud','ABBV':'Salud','MRK':'Salud','PFE':'Salud','ABT':'Salud','TMO':'Salud','AMGN':'Salud',
 'JPM':'Financiero','BAC':'Financiero','V':'Financiero','MA':'Financiero','GS':'Financiero','BLK':'Financiero','BRK-B':'Financiero','SPGI':'Financiero',
 'CAT':'Industrial','HON':'Industrial','UNP':'Industrial','LMT':'Industrial','UPS':'Industrial','DE':'Industrial','ADP':'Industrial',
 'XOM':'Energía','CVX':'Energía',
 'NEE':'Utilities','DUK':'Utilities','SO':'Utilities',
 'O':'Inmobiliario','PLD':'Inmobiliario',
 'LIN':'Materiales',
}
B = {
 'SPY':'S&P 500 (SPDR)','QQQ':'Nasdaq-100 (Invesco QQQ)','VTI':'Vanguard Total Stock Market',
 'SCHD':'Schwab US Dividend Equity','VIG':'Vanguard Dividend Appreciation','VDIGX':'Vanguard Dividend Growth Fund',
 'USMV':'iShares MSCI USA Min Vol','SPLV':'Invesco S&P 500 Low Volatility',
 'FCNTX':'Fidelity Contrafund','AGTHX':'American Funds Growth Fund of America',
 'VWELX':'Vanguard Wellington Fund','AOR':'iShares Core Growth Allocation (60/40)',
 'IEF':'iShares 7-10Y Treasury','GLD':'SPDR Gold Shares',
}
EXTRA = ['^IRX', 'CLP=X']
FKEYS = ['shortName','marketCap','trailingPE','forwardPE','priceToBook','returnOnEquity','profitMargins','revenueGrowth','earningsGrowth','dividendYield','payoutRatio','debtToEquity','beta','targetMeanPrice','currentPrice']
EPISODES = [
 ('2018', 'Caída de fines de 2018', '2018-09-01', '2019-01-31'),
 ('covid', 'Pandemia, marzo 2020', '2020-02-01', '2020-04-30'),
 ('2022', 'Inflación y alza de tasas, 2022', '2021-11-01', '2022-12-31'),
 ('2025', 'Caída de abril 2025', '2025-02-01', '2025-05-31'),
]
stocks = list(U)


# ------------------------------------------------------------------ datos
def load_data():
    f = lambda n: os.path.join(DATA, n)
    if OFFLINE:
        px = pd.read_csv(f('prices_adj.csv'), index_col=0, parse_dates=True)
        div = pd.read_csv(f('dividends.csv'), index_col=0, parse_dates=True)
        craw = pd.read_csv(f('close_raw.csv'), index_col=0, parse_dates=True)
        if 'CLP=X' not in px:
            px['CLP=X'] = pd.read_csv(f('usdclp.csv'), index_col=0, parse_dates=True).iloc[:, 0]
    else:
        import yfinance as yf
        end = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        px = yf.download(stocks + list(B) + EXTRA, start='2015-06-01', end=end, auto_adjust=True, progress=False, threads=True)['Close']
        raw = yf.download(stocks, start='2010-06-01', end=end, auto_adjust=False, progress=False, actions=True, threads=True)
        div, craw = raw['Dividends'], raw['Close']
        px.to_csv(f('prices_adj.csv')); div.to_csv(f('dividends.csv')); craw.to_csv(f('close_raw.csv'))
    px = px.sort_index()
    core = px[stocks + list(B)]
    px = px[core.notna().mean(axis=1) > 0.9]          # descarta días sin mercado en EE.UU.
    # controles: si Yahoo entregó datos incompletos, se aborta y la página queda como estaba
    assert len(px) > 2500, 'pocos días de precios'
    bad = [c for c in stocks + list(B) if px[c].loc[START:].isna().mean() > 0.02]
    assert not bad, f'series incompletas: {bad}'
    assert (pd.Timestamp.today() - px.index[-1]).days <= 10 or OFFLINE, 'precios desactualizados'
    return px, div.fillna(0), craw


def load_fundamentals():
    path = os.path.join(ROOT, 'fundamentals.json')
    old = json.load(open(path)) if os.path.exists(path) else {}
    if OFFLINE:
        return old
    import yfinance as yf
    out = {}
    for t in stocks:
        for _ in range(3):
            try:
                i = yf.Ticker(t).info
                if i.get('currentPrice'):
                    out[t] = {k: i.get(k) for k in FKEYS}
                    break
            except Exception:
                time.sleep(2)
    for t in stocks:                                    # si falla alguno, se conserva el dato anterior
        if t not in out and t in old:
            out[t] = old[t]
    assert len(out) == len(stocks), 'faltan fundamentales'
    json.dump(out, open(path, 'w'), indent=1)
    return out


px_all, div, craw = load_data()
F = load_fundamentals()
irx = px_all['^IRX'].ffill() / 100
fx = px_all['CLP=X'].ffill()
med = fx.rolling(11, center=True, min_periods=3).median()
fx = fx.where((fx / med - 1).abs() < 0.04, med).ffill().bfill()    # limpia ticks erróneos del dólar
px = px_all.drop(columns=EXTRA).ffill()
END = px.index[-1]
ret = px.pct_change()


# ------------------------------------------------------------------ reglas de los fondos
def on_or_after(d):
    i = px.index.searchsorted(d)
    return px.index[i] if i < len(px.index) else None

def sector_cap(order, cap, n):
    out, cnt = [], {}
    for t in order:
        s = U[t]
        if cnt.get(s, 0) < cap:
            out.append(t); cnt[s] = cnt.get(s, 0) + 1
        if len(out) == n:
            break
    return out

def feats(d):
    """Señales calculadas solo con información disponible hasta la fecha d."""
    i = px.index.get_loc(d); p = px[stocks]
    mom = p.iloc[i - 21] / p.iloc[i - 252] - 1
    vol = ret[stocks].iloc[i - 251:i + 1].std() * np.sqrt(252)
    yr = lambda a, b: div[stocks].loc[d - pd.Timedelta(days=365 * a):d - pd.Timedelta(days=365 * b)].sum()
    dttm, d3, d5 = yr(1, 0), yr(4, 3), yr(6, 5)
    dy = dttm / craw[stocks].loc[:d].iloc[-1]
    dg5 = ((dttm / d5) ** (1 / 5) - 1).where(d5 > 0)
    return pd.DataFrame({'mom': mom, 'vol': vol, 'dy': dy, 'dgrow': (dttm >= d3) & (d3 > 0), 'dg5': dg5})

def sel_growth(f):
    t = sector_cap(f.sort_values('mom', ascending=False).index, 4, 12)
    return {x: 1 / 12 for x in t}

def sel_div(f):
    c = f[f.dgrow & (f.dy >= 0.015) & f.dg5.notna() & (f.vol < f.vol.quantile(0.8))]
    sc = c.dy.rank(ascending=False) + c.dg5.rank(ascending=False)
    t = sector_cap(sc.sort_values().index, 3, 12)
    return {x: 1 / len(t) for x in t}

def sel_def(f):
    t = sector_cap(f.sort_values('vol').index, 3, 12)
    iv = 1 / f.loc[t, 'vol']
    return (iv / iv.sum()).to_dict()

def sel_bal(f):
    sc = f.mom.rank(ascending=False) + f.vol.rank()
    t = sector_cap(sc.sort_values().index, 3, 15)
    w = {x: 0.60 / 15 for x in t}; w['IEF'] = 0.25; w['GLD'] = 0.15
    return w

FUNDS = {'crecimiento': sel_growth, 'dividendos': sel_div, 'defensivo': sel_def, 'balanceado': sel_bal}

m_, d_ = REBAL_MONTH_DAY
annual = [x for x in (on_or_after(pd.Timestamp(year=y, month=m_, day=d_)) for y in range(START.year, END.year + 1)) if x is not None]
quarterly = set(annual)
for y in range(START.year, END.year + 1):
    for m in (2, 5, 8, 11):
        x = on_or_after(pd.Timestamp(year=y, month=m, day=d_))
        if x is not None and x >= START:
            quarterly.add(x)
annual_set = set(annual)


def run(selfn):
    dates = px.loc[START:END].index
    nav = pd.Series(index=dates, dtype=float); nav.iloc[0] = 10000
    target, w, sels, turnover = {}, {}, {}, 0
    for k, d in enumerate(dates):
        if k > 0:
            r = sum(w[t] * ret.at[d, t] for t in w)
            nav.iloc[k] = nav.iloc[k - 1] * (1 + r) * (1 - FEE / 252)
            tot = sum(w[t] * (1 + ret.at[d, t]) for t in w)
            w = {t: w[t] * (1 + ret.at[d, t]) / tot for t in w}
        if d in annual_set:
            target = selfn(feats(d)); sels[d] = target
        if d in quarterly or k == 0:
            to = sum(abs(target.get(t, 0) - w.get(t, 0)) for t in set(target) | set(w))
            if k > 0:
                nav.iloc[k] *= (1 - TC * to); turnover += to / 2
            w = dict(target)
    yrs = (dates[-1] - dates[0]).days / 365.25
    return nav, sels, turnover / yrs


navs, sels, turn = {}, {}, {}
for k, fn in FUNDS.items():
    navs[k], sels[k], turn[k] = run(fn)
for t in B:
    s = px[t].loc[START:END]; navs[t] = s / s.iloc[0] * 10000
nav = pd.DataFrame(navs)
rf = irx.reindex(nav.index).ffill().bfill() / 252
fxn = fx.reindex(nav.index).ffill().bfill()
nav_clp = nav.mul(fxn / fxn.iloc[0], axis=0)


# ------------------------------------------------------------------ métricas
def metrics(s):
    r = s.pct_change().dropna(); ex = r - rf.loc[r.index]
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    def cagr(n):
        d0 = s.index[-1] - pd.DateOffset(years=n)
        if d0 < s.index[0] - pd.Timedelta(days=5):
            return None
        s0 = s.loc[:d0].iloc[-1] if d0 >= s.index[0] else s.iloc[0]
        return (s.iloc[-1] / s0) ** (1 / n) - 1
    spy = nav['SPY'].pct_change().dropna()
    beta = np.cov(r, spy)[0, 1] / spy.var()
    alpha = ((r.mean() - rf.mean()) - beta * (spy.mean() - rf.mean())) * 252
    dd = s / s.cummax() - 1
    cal = {}
    for y in range(START.year + 1, END.year + 1):
        a = s.loc[:f'{y - 1}-12-31'].iloc[-1]; b = s.loc[:f'{y}-12-31'].iloc[-1]
        cal[str(y) if y < END.year else f'{y} YTD'] = b / a - 1
    return dict(cagr10=cagr(10) or (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1, cagr5=cagr(5), cagr3=cagr(3), r1=cagr(1),
                ytd=list(cal.values())[-1], vol=r.std() * np.sqrt(252), sharpe=ex.mean() / ex.std() * np.sqrt(252),
                sortino=(ex.mean() * 252) / (r[r < 0].std() * np.sqrt(252)), maxdd=dd.min(), beta=beta, alpha=alpha,
                upcap=r[spy > 0].mean() / spy[spy > 0].mean(), dncap=r[spy < 0].mean() / spy[spy < 0].mean(),
                final=s.iloc[-1], calendar=cal)

M = {k: metrics(nav[k]) for k in nav.columns}


def episode(s, a, b):
    """Caída de máximo a mínimo dentro de la ventana y meses hasta recuperar el máximo."""
    w = s.loc[a:b]
    if len(w) < 20:
        return None
    run_ = w / w.cummax() - 1
    trough = run_.idxmin(); peak = w.loc[:trough].idxmax()
    after = s.loc[trough:]; rec = after[after >= w[peak]]
    return dict(drop=float(run_.min()), peak=str(peak.date()), trough=str(trough.date()),
                rec_months=None if rec.empty else round((rec.index[0] - trough).days / 30.44, 1))

crisis = {'episodes': [], 'data': {}}
for key, name, a, b in EPISODES:
    e = episode(nav['SPY'], a, b)
    if e and e['drop'] < -0.10:
        crisis['episodes'].append({'key': key, 'name': name})
        for k in list(FUNDS) + ['SPY']:
            crisis['data'].setdefault(k, {})[key] = {'usd': episode(nav[k], a, b), 'clp': episode(nav_clp[k], a, b)}


# ------------------------------------------------------------------ cartera vigente y acciones
def fnum(t, k):
    v = F.get(t, {}).get(k)
    return None if v is None else float(v)

last_annual = annual[-1]
# la cartera vigente es la última selección anual; a días de la siguiente, se muestra la nueva
hold_date = END if (END - last_annual).days > 360 else last_annual
fe = feats(END)
cur = {k: (FUNDS[k](feats(hold_date)) if hold_date == END else sels[k][last_annual]) for k in FUNDS}

p = px[stocks]
rows = []
for t in stocks:
    s = p[t]; s10 = s.loc[START:END]
    cg = lambda n: (s.iloc[-1] / s.loc[:END - pd.DateOffset(years=n)].iloc[-1]) ** (1 / n) - 1
    rr = ret[t].loc[START:END].dropna(); ex = rr - rf.reindex(rr.index).ffill()
    tgt, cp = fnum(t, 'targetMeanPrice'), fnum(t, 'currentPrice')
    rows.append(dict(t=t, name=F[t]['shortName'], sector=U[t], price=cp, r1=cg(1), c5=cg(5), c10=cg(10),
        vol=float(fe.at[t, 'vol']), mom=float(fe.at[t, 'mom']), dd=float((s10 / s10.cummax() - 1).min()),
        sharpe=float(ex.mean() / ex.std() * np.sqrt(252)), beta=fnum(t, 'beta'), pe=fnum(t, 'trailingPE'),
        fpe=fnum(t, 'forwardPE'), roe=fnum(t, 'returnOnEquity'), margin=fnum(t, 'profitMargins'),
        growth=fnum(t, 'revenueGrowth'), dy=(fnum(t, 'dividendYield') or 0) / 100,
        upside=(tgt / cp - 1) if tgt and cp else None,
        dg5=None if pd.isna(fe.at[t, 'dg5']) else float(fe.at[t, 'dg5']), funds=[k for k in cur if t in cur[k]]))
SR = {x['t']: x for x in rows}

def wavg(w, key):
    ws = [(SR[t][key], v) for t, v in w.items() if t in SR and SR[t][key] is not None]
    tot = sum(v for _, v in ws)
    return sum(a * v for a, v in ws) / tot if tot else None

holdings, chars = {}, {}
for k, w in cur.items():
    h = []
    for t, v in sorted(w.items(), key=lambda x: -x[1]):
        if t in SR:
            h.append(dict(t=t, w=v, name=SR[t]['name'], sector=SR[t]['sector']))
        else:
            h.append(dict(t=t, w=v, name=B[t], sector='Renta fija' if t == 'IEF' else 'Oro'))
    holdings[k] = h
    sec = {}
    for x in h:
        sec[x['sector']] = sec.get(x['sector'], 0) + x['w']
    chars[k] = dict(fpe=wavg(w, 'fpe'), roe=wavg(w, 'roe'), margin=wavg(w, 'margin'),
                    dy=sum(SR[t]['dy'] * v for t, v in w.items() if t in SR) + 0.04 * w.get('IEF', 0),
                    beta=wavg(w, 'beta'), n=len(h), sectors=sec, turnover=float(turn[k]))


# ------------------------------------------------------------------ salida
wk = nav.resample('W-FRI').last(); wk.iloc[-1] = nav.iloc[-1]
dd = (nav / nav.cummax() - 1).resample('W-FRI').min()

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)): return None if np.isnan(o) else round(float(o), 6)
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.bool_): return bool(o)
    return o

out = clean(dict(asof=str(END.date()), start=str(nav.index[0].date()), hold_date=str(hold_date.date()),
    dates=[str(d.date()) for d in wk.index],
    nav={k: [round(x, 1) for x in wk[k]] for k in wk.columns},
    dd={k: [round(x, 4) for x in dd[k]] for k in dd.columns},
    metrics=M, bench=B, stocks=rows, holdings=holdings, chars=chars, crisis=crisis,
    fx=float(fxn.iloc[-1]), cl=CL, fee=FEE, tc=TC))
json.dump(out, open(os.path.join(DATA, 'site_data.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
tpl = open(os.path.join(ROOT, 'template.html'), encoding='utf-8').read()
assert '/*__DATA__*/null' in tpl
open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(
    tpl.replace('/*__DATA__*/null', json.dumps(out, ensure_ascii=False, separators=(',', ':'))))

print('Datos al', out['asof'], '· cartera del', out['hold_date'], '· dólar', round(out['fx']))
for k in list(FUNDS) + ['SPY']:
    m = M[k]
    print(f"{k:12s} 10a {m['cagr10']:.1%}  5a {m['cagr5']:.1%}  vol {m['vol']:.1%}  dd {m['maxdd']:.1%}  final {m['final']:.0f}")
