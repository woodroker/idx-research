"""Cross-sectional next-session Top Gainer radar. Scores are ranks, not probabilities."""
from __future__ import annotations
import json, math, threading
from typing import Any
import database, store

MIN_AVG_VALUE=250_000_000
SELECTION_FRACTION=.10
# Rounded shares of historical univariate AUC lift above 0.50.
# Bid imbalance is omitted: its AUC was near random and snapshots are not queues.
FEATURE_WEIGHTS={
    "log_volume_ratio":20.7, "log_value_ratio":19.8, "ret_1d":16.5,
    "ret_5d":12.8, "ret_20d":9.3, "foreign_net_value_ratio_5d":8.7,
    "close_position":7.9,
}
_CACHE_LOCK=threading.RLock()
_CACHE_KEY=None
_CACHE_SCORES={}

def _n(row,i,default=0.0):
    try:
        x=float(row[i] or 0)
        return x if math.isfinite(x) else default
    except (IndexError,TypeError,ValueError,OverflowError):
        return default

def _logratio(x,y):
    return max(-5.0,min(5.0,math.log(x/y))) if x>0 and y>0 else 0.0

def _ranks(values):
    items=sorted(values.items(),key=lambda x:(x[1],x[0])); n=len(items); out={}; i=0
    while i<n:
        j=i+1
        while j<n and items[j][1]==items[i][1]: j+=1
        rank=50.0 if n==1 else 100.0*((i+j-1)/2)/(n-1)
        for k in range(i,j): out[items[k][0]]=rank
        i=j
    return out

def _reason(f,row,meta):
    v=row[f]
    if f=="log_volume_ratio": return "volume %.1fx rata-rata 20 sesi"%math.exp(v)
    if f=="log_value_ratio": return "nilai transaksi %.1fx rata-rata 20 sesi"%math.exp(v)
    if f=="ret_1d": return "return 1 sesi %+0.1f%%"%(100*v)
    if f=="ret_5d": return "return 5 sesi %+0.1f%%"%(100*v)
    if f=="ret_20d": return "return 20 sesi %+0.1f%%"%(100*v)
    if f=="close_position": return "close di %.0f%% rentang harian"%(100*v)
    return "arus asing net 5 sesi %+0.1f%% nilai transaksi, proxy (%s hari)"%(100*v,meta.get("foreign_flow_coverage_days",0))

def compute_scores(raw:dict[str,Any],metadata_by_code=None):
    """0-100 relative score; top decile is the watchlist candidate set."""
    px=raw.get("px") or {}; dates=sorted(px)
    if len(dates)<21: return {}
    asof=dates[-1]; latest=px[asof] or {}; metadata_by_code=metadata_by_code or {}
    feats={}; vals={}; metas={}
    for code in latest:
        series=[(d,(px.get(d) or {}).get(code)) for d in dates if (px.get(d) or {}).get(code) and _n((px.get(d) or {}).get(code),0)>0]
        if len(series)<21 or series[-1][0]!=asof: continue
        cur=series[-1][1]; c,prev,v,value=_n(cur,0),_n(cur,1),_n(cur,2),_n(cur,3)
        prior=[r for _,r in series[-21:-1]]
        pv=[_n(r,3) for r in prior if _n(r,3)>0]; vv=[_n(r,2) for r in prior if _n(r,2)>0]
        av=sum(pv)/len(pv) if pv else 0; va=sum(vv)/len(vv) if vv else 0
        if c<=0 or prev<=0 or v<=0 or value<=0 or av<MIN_AVG_VALUE: continue
        c5,c20=_n(series[-6][1],0),_n(series[-21][1],0)
        if c5<=0 or c20<=0: continue
        hi,lo=_n(cur,8,c),_n(cur,9,c)
        f={"ret_1d":c/prev-1,"ret_5d":c/c5-1,"ret_20d":c/c20-1,
           "log_value_ratio":_logratio(value,av),"log_volume_ratio":_logratio(v,va),
           "close_position":max(0,min(1,(c-lo)/(hi-lo) if hi>lo else .5))}
        meta=metadata_by_code.get(code) or {}; days=int(meta.get("foreign_flow_coverage_days") or 0)
        try: flow=float(meta["foreign_flow_ratio_5d"]) if meta.get("foreign_flow_ratio_5d") is not None else None
        except (TypeError,ValueError,OverflowError): flow=None
        if flow is not None and days>=3: f["foreign_net_value_ratio_5d"]=flow
        feats[code]=f
        vals[code]={"close":c,"rvol":v/va if va else 0,"value_ratio":value/av if av else 0,**f}
        metas[code]=meta
    if not feats: return {}
    ranks={f:_ranks({c:x[f] for c,x in feats.items() if f in x}) for f in FEATURE_WEIGHTS}
    scored=[]
    for code,row in feats.items():
        active=[f for f in FEATURE_WEIGHTS if f in row and code in ranks[f]]
        den=sum(FEATURE_WEIGHTS[f] for f in active)
        if den: scored.append((code,sum(FEATURE_WEIGHTS[f]*ranks[f][code] for f in active)/den))
    scored.sort(key=lambda x:(-x[1],x[0])); n=len(scored); top=max(1,math.ceil(n*SELECTION_FRACTION)); out={}
    for rank,(code,score) in enumerate(scored,1):
        row=vals[code]; meta=metas[code]
        topf=sorted(((FEATURE_WEIGHTS[f]*ranks[f][code],f) for f in feats[code] if code in ranks.get(f,{})),reverse=True)[:3]
        reasons=[_reason(f,row,meta) for _,f in topf]
        out[code]={"score":round(score,1),"rank":rank,"universe":n,"candidate":rank<=top,
                   "selection_pct":10,"asof":asof,"close":round(row["close"],2),
                   "rvol":round(row["rvol"],2),"value_ratio":round(row["value_ratio"],2),
                   "ret_1d_pct":round(row["ret_1d"]*100,2),
                   "close_position_pct":round(row["close_position"]*100,1),
                   "foreign_flow_ratio_5d":row.get("foreign_net_value_ratio_5d"),
                   "foreign_flow_coverage_days":int(meta.get("foreign_flow_coverage_days") or 0),
                   "foreign_flow_asof":meta.get("foreign_flow_asof"),"reasons":reasons}
    return out

def current_scores(metadata_by_code=None):
    """Read and cache current DB scores for Telegram worker use."""
    global _CACHE_KEY,_CACHE_SCORES
    conn=database.connect()
    try:
        key=(store.data_version(conn),tuple((c,m.get("foreign_flow_ratio_5d"),m.get("foreign_flow_coverage_days"),m.get("foreign_flow_asof")) for c,m in sorted((metadata_by_code or {}).items()) if m.get("foreign_flow_coverage_days")))
        with _CACHE_LOCK:
            if key!=_CACHE_KEY:
                _CACHE_SCORES=compute_scores(json.loads(store.build_data_json(conn)),metadata_by_code)
                _CACHE_KEY=key
            return dict(_CACHE_SCORES)
    finally: conn.close()
