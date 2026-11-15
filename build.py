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
TC = 0.001                           # costo por compra/venta
REBAL_MONTH_DAY = (11, 14)           # selección anual
FEES = {'crecimiento': 0.0075, 'dividendos': 0.0075, 'defensivo': 0.0075, 'chile': 0.0075, 'global': 0.0040, 'rentafija': 0.0030}
# Supuestos de Chile mostrados como valores por defecto (editables en la página)
CL = {'dap': 0.045, 'ipc': 0.045,
      'dap_src': 'TPM del Banco Central de Chile, 4,5% (noviembre 2026)',
      'ipc_src': 'IPC a 12 meses, INE, octubre 2026: 4,5%'}

SECT = {'Industrials': 'Industrial', 'Information Technology': 'Tecnología', 'Financials': 'Financiero', 'Health Care': 'Salud',
        'Consumer Discretionary': 'Consumo discrecional', 'Consumer Staples': 'Consumo básico', 'Utilities': 'Utilities',
        'Real Estate': 'Inmobiliario', 'Materials': 'Materiales', 'Communication Services': 'Comunicaciones', 'Energy': 'Energía'}
sp = pd.read_csv(os.path.join(ROOT, 'sp500.csv'))
sp['t'] = sp['Symbol'].str.replace('.', '-', regex=False)
sp['added'] = pd.to_datetime(sp['Date added'], errors='coerce').fillna(pd.Timestamp('1990-01-01'))
U = {r.t: SECT[r['GICS Sector']] for _, r in sp.iterrows()}          # acción -> sector
NAMES = dict(zip(sp.t, sp.Security))
ADDED = dict(zip(sp.t, sp.added))
# Acciones chilenas del IPSA (Bolsa de Santiago, sufijo .SN en Yahoo Finance)
CHILE = {
 'AGUAS-A.SN': ('Aguas Andinas', 'Utilities'), 'ANDINA-B.SN': ('Embotelladora Andina', 'Consumo básico'), 'BCI.SN': ('Banco BCI', 'Financiero'),
 'BSANTANDER.SN': ('Banco Santander Chile', 'Financiero'), 'CAP.SN': ('CAP', 'Materiales'), 'CCU.SN': ('CCU', 'Consumo básico'),
 'CENCOSUD.SN': ('Cencosud', 'Consumo básico'), 'CENCOMALLS.SN': ('Cencosud Shopping', 'Inmobiliario'), 'CHILE.SN': ('Banco de Chile', 'Financiero'),
 'CMPC.SN': ('Empresas CMPC', 'Materiales'), 'COLBUN.SN': ('Colbún', 'Utilities'), 'CONCHATORO.SN': ('Viña Concha y Toro', 'Consumo básico'),
 'COPEC.SN': ('Empresas Copec', 'Energía'), 'ECL.SN': ('Engie Energía Chile', 'Utilities'), 'ENELAM.SN': ('Enel Américas', 'Utilities'),
 'ENELCHILE.SN': ('Enel Chile', 'Utilities'), 'ENTEL.SN': ('Entel', 'Comunicaciones'), 'FALABELLA.SN': ('Falabella', 'Consumo discrecional'),
 'IAM.SN': ('Inversiones Aguas Metropolitanas', 'Utilities'), 'ILC.SN': ('Inversiones La Construcción', 'Financiero'), 'ITAUCL.SN': ('Itaú Chile', 'Financiero'),
 'LTM.SN': ('LATAM Airlines', 'Industrial'), 'MALLPLAZA.SN': ('Mallplaza', 'Inmobiliario'), 'PARAUCO.SN': ('Parque Arauco', 'Inmobiliario'),
 'QUINENCO.SN': ('Quiñenco', 'Industrial'), 'RIPLEY.SN': ('Ripley', 'Consumo discrecional'), 'SALFACORP.SN': ('SalfaCorp', 'Industrial'),
 'SMU.SN': ('SMU', 'Consumo básico'), 'SONDA.SN': ('Sonda', 'Tecnología'), 'SQM-B.SN': ('SQM', 'Materiales'), 'VAPORES.SN': ('Vapores', 'Industrial'),
 'BESALCO.SN': ('Besalco', 'Industrial'),
}
INSTR = {'VTI': 'Acciones EE.UU. (Vanguard Total Stock Market)', 'VEA': 'Acciones desarrollados sin EE.UU. (Vanguard FTSE Developed)',
         'VWO': 'Acciones emergentes (Vanguard FTSE Emerging)', 'QQQ': 'Nasdaq-100 (Invesco QQQ)', 'VTV': 'Acciones de valor EE.UU. (Vanguard Value)',
         'SHY': 'Bonos del Tesoro 1 a 3 años (iShares)', 'IEF': 'Bonos del Tesoro 7 a 10 años (iShares)', 'TLT': 'Bonos del Tesoro 20+ años (iShares)',
         'GLD': 'Oro (SPDR Gold Shares)'}
B = {
 'SPY':'S&P 500 (SPDR)','VOO':'Vanguard S&P 500','IVV':'iShares Core S&P 500','QQQ':'Nasdaq-100 (Invesco QQQ)','VTI':'Vanguard Total Stock Market',
 'SCHD':'Schwab US Dividend Equity','VIG':'Vanguard Dividend Appreciation','VDIGX':'Vanguard Dividend Growth Fund',
 'USMV':'iShares MSCI USA Min Vol','SPLV':'Invesco S&P 500 Low Volatility',
 'FCNTX':'Fidelity Contrafund','AGTHX':'American Funds Growth Fund of America',
 'VWELX':'Vanguard Wellington Fund','AOK':'iShares Core Conservative Allocation (30/70)','AOM':'iShares Core Moderate Allocation (40/60)',
 'AOR':'iShares Core Growth Allocation (60/40)','AOA':'iShares Core Aggressive Allocation (80/20)',
 'VT':'Vanguard Total World Stock','ACWI':'iShares MSCI ACWI','ECH':'iShares MSCI Chile',
 'BND':'Vanguard Total Bond Market','AGG':'iShares Core US Aggregate Bond',
 'VEA':'Vanguard FTSE Developed Markets','VWO':'Vanguard FTSE Emerging Markets','VTV':'Vanguard Value',
 'SHY':'iShares 1-3Y Treasury','IEF':'iShares 7-10Y Treasury','TLT':'iShares 20+Y Treasury','GLD':'SPDR Gold Shares',
}
EXTRA = ['^IRX', 'CLP=X', '^FVX', '^TNX', '^TYX']
FKEYS = ['shortName','trailingPE','forwardPE','returnOnEquity','profitMargins','dividendYield','beta','currentPrice']
EPISODES = [
 ('2018', 'Caída de fines de 2018', '2018-09-01', '2019-01-31'),
 ('covid', 'Pandemia, marzo 2020', '2020-02-01', '2020-04-30'),
 ('2022', 'Inflación y alza de tasas, 2022', '2021-11-01', '2022-12-31'),
 ('2025', 'Caída de abril 2025', '2025-02-01', '2025-05-31'),
]
stocks = list(U)
cl = list(CHILE)


# ------------------------------------------------------------------ datos
def load_data():
    f = lambda n: os.path.join(DATA, n)
    if OFFLINE:
        px = pd.read_csv(f('prices_adj.csv'), index_col=0, parse_dates=True)
        div = pd.read_csv(f('dividends.csv'), index_col=0, parse_dates=True)
        craw = pd.read_csv(f('close_raw.csv'), index_col=0, parse_dates=True)
    else:
        import yfinance as yf
        end = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        px = yf.download(stocks + cl + list(B) + EXTRA, start='2015-06-01', end=end, auto_adjust=True, progress=False, threads=True)['Close']
        raw = yf.download(stocks, start='2010-06-01', end=end, auto_adjust=False, progress=False, actions=True, threads=True)
        div, craw = raw['Dividends'], raw['Close']
        px.to_csv(f('prices_adj.csv')); div.to_csv(f('dividends.csv')); craw.to_csv(f('close_raw.csv'))
    px = px.sort_index()
    px = px[px[list(B)].notna().mean(axis=1) > 0.9]     # solo días con mercado en EE.UU.
    # controles: si Yahoo entregó datos incompletos, se aborta y la página queda como estaba
    assert len(px) > 2500, 'pocos días de precios'
    bad = [c for c in B if px[c].loc[START:].isna().mean() > 0.02]
    assert not bad, f'series incompletas: {bad}'
    assert px[stocks].iloc[-5:].notna().any().sum() >= 470, 'faltan acciones del S&P 500'
    assert px[cl].iloc[-5:].notna().any().sum() >= 20, 'faltan acciones chilenas'
    assert (pd.Timestamp.today() - px.index[-1]).days <= 10 or OFFLINE, 'precios desactualizados'
    return px, div.reindex(columns=stocks).fillna(0), craw.reindex(columns=stocks)


px_all, div, craw = load_data()
irx = px_all['^IRX'].ffill() / 100
_y = px_all[['^IRX', '^FVX', '^TNX', '^TYX']].ffill().iloc[-1] / 100
# rentabilidad esperada de la renta fija: tasa actual de los bonos del Tesoro, menos la comisión
EXP_RF = float(0.50 * (_y['^IRX'] + _y['^FVX']) / 2 + 0.35 * _y['^TNX'] + 0.15 * _y['^TYX'] - FEES['rentafija'])
fx = px_all['CLP=X'].ffill()
med = fx.rolling(11, center=True, min_periods=3).median()
fx = fx.where((fx / med - 1).abs() < 0.04, med).ffill().bfill()    # limpia ticks erróneos del dólar
px = px_all.drop(columns=EXTRA)
for t in cl:                                                        # acciones chilenas: limpia saltos erróneos y pasa a dólares
    s = px[t]; r = s.pct_change()
    glitch = (r.abs() > 0.35) & (r.shift(-1).abs() > 0.25) & (np.sign(r) != np.sign(r.shift(-1)))
    px[t] = s.mask(glitch).ffill(limit=10) / fx
px = px.ffill(limit=10)
cl = [t for t in cl if px[t].iloc[-5:].notna().any()]
stocks = [t for t in stocks if px[t].iloc[-5:].notna().any()]
END = px.index[-1]
ret = px.pct_change(fill_method=None)


# ------------------------------------------------------------------ reglas de los fondos
def on_or_after(d):
    i = px.index.searchsorted(d)
    return px.index[i] if i < len(px.index) else None

def sector_cap(order, cap, n, sec):
    out, cnt = [], {}
    for t in order:
        s = sec(t)
        if cnt.get(s, 0) < cap:
            out.append(t); cnt[s] = cnt.get(s, 0) + 1
        if len(out) == n:
            break
    return out

def base_feats(d, cols):
    i = px.index.get_loc(d); p = px[cols]
    mom = p.iloc[i - 21] / p.iloc[i - 252] - 1
    win = ret[cols].iloc[i - 251:i + 1]
    vol = win.std() * np.sqrt(252)
    ok = (win.notna().sum() > 230) & (win.abs() > 0).mean().gt(0.5)   # historia completa y que transe
    return pd.DataFrame({'mom': mom, 'vol': vol})[ok].dropna()

def feats(d):
    """Señales del S&P 500 calculadas solo con información disponible hasta la fecha d."""
    f = base_feats(d, stocks)
    f = f[[ADDED[t] <= d for t in f.index]]            # solo acciones que ya estaban en el índice
    yr = lambda a, b: div[f.index].loc[d - pd.Timedelta(days=365 * a):d - pd.Timedelta(days=365 * b)].sum()
    dttm, d3, d5 = yr(1, 0), yr(4, 3), yr(6, 5)
    f['dy'] = dttm / craw[f.index].loc[:d].ffill().iloc[-1]
    f['dg5'] = ((dttm / d5) ** (1 / 5) - 1).where(d5 > 0)
    f['dgrow'] = (dttm >= d3) & (d3 > 0)
    return f

us = lambda t: U[t]
def sel_growth(d):
    f = feats(d); t = sector_cap(f.sort_values('mom', ascending=False).index, 5, 25, us)
    return {x: 1 / len(t) for x in t}

def sel_div(d):
    f = feats(d)
    c = f[f.dgrow & (f.dy >= 0.015) & f.dg5.notna() & (f.vol < f.vol.quantile(0.8))]
    sc = c.dy.rank(ascending=False) + c.dg5.rank(ascending=False)
    t = sector_cap(sc.sort_values().index, 5, 25, us)
    return {x: 1 / len(t) for x in t}

def sel_def(d):
    f = feats(d); t = sector_cap(f.sort_values('vol').index, 5, 25, us)
    iv = 1 / f.loc[t, 'vol']
    return (iv / iv.sum()).to_dict()

def sel_chile(d):
    f = base_feats(d, cl)
    sc = f.mom.rank(ascending=False) + f.vol.rank()
    t = sector_cap(sc.sort_values().index, 3, 10, lambda x: CHILE[x][1])
    return {x: 1 / len(t) for x in t}

def sel_global(d):
    f = base_feats(d, ['VTI', 'VEA', 'VWO', 'QQQ', 'VTV'])
    iv = 1 / f.vol
    return (iv / iv.sum()).to_dict()

def sel_rf(d):
    return {'SHY': 0.50, 'IEF': 0.35, 'TLT': 0.15}

FUNDS = {'crecimiento': sel_growth, 'dividendos': sel_div, 'defensivo': sel_def, 'chile': sel_chile, 'global': sel_global, 'rentafija': sel_rf}

m_, d_ = REBAL_MONTH_DAY
annual = [x for x in (on_or_after(pd.Timestamp(year=y, month=m_, day=d_)) for y in range(START.year, END.year + 1)) if x is not None]
quarterly = set(annual)
for y in range(START.year, END.year + 1):
    for m in (2, 5, 8, 11):
        x = on_or_after(pd.Timestamp(year=y, month=m, day=d_))
        if x is not None and x >= START:
            quarterly.add(x)
annual_set = set(annual)


def run(selfn, fee):
    dates = px.loc[START:END].index
    nav = pd.Series(index=dates, dtype=float); nav.iloc[0] = 10000
    target, w, sels, turnover = {}, {}, {}, 0
    R = ret.fillna(0)
    for k, d in enumerate(dates):
        if k > 0:
            r = sum(w[t] * R.at[d, t] for t in w)
            nav.iloc[k] = nav.iloc[k - 1] * (1 + r) * (1 - fee / 252)
            tot = sum(w[t] * (1 + R.at[d, t]) for t in w)
            w = {t: w[t] * (1 + R.at[d, t]) / tot for t in w}
        if d in annual_set:
            target = selfn(d); sels[d] = target
        if d in quarterly or k == 0:
            to = sum(abs(target.get(t, 0) - w.get(t, 0)) for t in set(target) | set(w))
            if k > 0:
                nav.iloc[k] *= (1 - TC * to); turnover += to / 2
            w = dict(target)
    yrs = (dates[-1] - dates[0]).days / 365.25
    return nav, sels, turnover / yrs


navs, sels, turn = {}, {}, {}
for k, fn in FUNDS.items():
    navs[k], sels[k], turn[k] = run(fn, FEES[k])
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
    return dict(drop=float(run_.min()), rec_months=None if rec.empty else round((rec.index[0] - trough).days / 30.44, 1))

crisis = {'episodes': [], 'data': {}}
for key, name, a, b in EPISODES:
    e = episode(nav['SPY'], a, b)
    if e and e['drop'] < -0.10:
        crisis['episodes'].append({'key': key, 'name': name, 'a': a, 'b': b})
        for k in list(FUNDS) + ['SPY']:
            crisis['data'].setdefault(k, {})[key] = {'usd': episode(nav[k], a, b), 'clp': episode(nav_clp[k], a, b)}


# ------------------------------------------------------------------ cartera vigente y acciones
last_annual = annual[-1]
# la cartera vigente es la última selección anual; a días de la siguiente, se muestra la nueva
hold_date = END if (END - last_annual).days > 360 else last_annual
cur = {k: (FUNDS[k](END) if hold_date == END else sels[k][last_annual]) for k in FUNDS}
held = sorted({t for w in cur.values() for t in w if t in U or t in CHILE})

def load_fundamentals():
    """Fundamentales solo de las acciones en cartera. Si Yahoo falla, se conserva el dato anterior."""
    path = os.path.join(ROOT, 'fundamentals.json')
    old = json.load(open(path)) if os.path.exists(path) else {}
    if OFFLINE:
        return old
    import yfinance as yf
    out = {}
    for t in held:
        for _ in range(2):
            try:
                i = yf.Ticker(t).info
                if i.get('currentPrice'):
                    out[t] = {k: i.get(k) for k in FKEYS}; break
            except Exception:
                time.sleep(1)
        if t not in out and t in old:
            out[t] = old[t]
    json.dump(out, open(path, 'w'), indent=1)
    return out

F = load_fundamentals()
def fnum(t, k):
    v = F.get(t, {}).get(k)
    return None if v is None else float(v)

fe = feats(END); fc = base_feats(END, cl)
rows = []
def stock_row(t, name, sector, mkt, f):
    s = px[t].dropna(); s10 = s.loc[START:END]
    def cg(n):
        d0 = END - pd.DateOffset(years=n)
        if s.index[0] > d0: return None
        return float((s.iloc[-1] / s.loc[:d0].iloc[-1]) ** (1 / n) - 1)
    rr = s10.pct_change().dropna(); ex = rr - rf.reindex(rr.index).ffill()
    g = lambda c: float(f.at[t, c]) if t in f.index and c in f.columns and pd.notna(f.at[t, c]) else None
    return dict(t=t.replace('.SN', ''), name=name, sector=sector, mkt=mkt, r1=cg(1), c5=cg(5), c10=cg(10),
        vol=g('vol'), mom=g('mom'), dd=float((s10 / s10.cummax() - 1).min()) if len(s10) > 250 else None,
        sharpe=float(ex.mean() / ex.std() * np.sqrt(252)) if len(rr) > 250 else None,
        beta=fnum(t, 'beta'), fpe=fnum(t, 'forwardPE'), roe=fnum(t, 'returnOnEquity'), margin=fnum(t, 'profitMargins'),
        dy=g('dy') if mkt == 'EE.UU.' else ((fnum(t, 'dividendYield') or 0) / 100 or None), dg5=g('dg5'),
        funds=[k for k in cur if t in cur[k]])
for t in stocks:
    rows.append(stock_row(t, NAMES[t], U[t], 'EE.UU.', fe))
for t in cl:
    rows.append(stock_row(t, CHILE[t][0], CHILE[t][1], 'Chile', fc))
SR = {(x['t'] + '.SN' if x['mkt'] == 'Chile' else x['t']): x for x in rows}

def wavg(w, key):
    ws = [(SR[t][key], v) for t, v in w.items() if t in SR and SR[t][key] is not None]
    tot = sum(v for _, v in ws)
    return sum(a * v for a, v in ws) / tot if tot else None

holdings, chars = {}, {}
CLASS = {'SHY': 'Renta fija', 'IEF': 'Renta fija', 'TLT': 'Renta fija', 'GLD': 'Oro'}
for k, w in cur.items():
    h = []
    for t, v in sorted(w.items(), key=lambda x: -x[1]):
        if t in SR:
            h.append(dict(t=SR[t]['t'], w=v, name=SR[t]['name'], sector=SR[t]['sector']))
        else:
            h.append(dict(t=t, w=v, name=INSTR[t], sector=CLASS.get(t, 'ETF de acciones')))
    holdings[k] = h
    sec = {}
    for x in h:
        sec[x['sector']] = sec.get(x['sector'], 0) + x['w']
    chars[k] = dict(fpe=wavg(w, 'fpe'), roe=wavg(w, 'roe'), margin=wavg(w, 'margin'), dy=wavg(w, 'dy'),
                    beta=M[k]['beta'], n=len(h), sectors=sec, turnover=float(turn[k]))
counts = dict(sp=len(stocks), cl=len(cl))


# ------------------------------------------------------------------ salida
wk = nav.resample('W-FRI').last(); wk.iloc[-1] = nav.iloc[-1]
dd = (nav / nav.cummax() - 1).resample('W-FRI').min()
rfw = (irx.reindex(nav.index).ffill().bfill()).resample('W-FRI').last() / 52.18
fxw = fxn.resample('W-FRI').last()

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
    fx=float(fxn.iloc[-1]), cl=CL, fees=FEES, tc=TC, counts=counts, instr=INSTR, exp_rf=EXP_RF,
    rfw=[round(float(x), 6) for x in rfw], fxw=[round(float(x), 2) for x in fxw]))
json.dump(out, open(os.path.join(DATA, 'site_data.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
tpl = open(os.path.join(ROOT, 'template.html'), encoding='utf-8').read()
assert '/*__DATA__*/null' in tpl
open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(
    tpl.replace('/*__DATA__*/null', json.dumps(out, ensure_ascii=False, separators=(',', ':'))))

print('Datos al', out['asof'], '· cartera del', out['hold_date'], '· dólar', round(out['fx']))
for k in list(FUNDS) + ['SPY', 'VT', 'ECH', 'BND']:
    m = M[k]
    print(f"{k:12s} 10a {m['cagr10']:.1%}  5a {m['cagr5']:.1%}  vol {m['vol']:.1%}  dd {m['maxdd']:.1%}  final {m['final']:.0f}")
