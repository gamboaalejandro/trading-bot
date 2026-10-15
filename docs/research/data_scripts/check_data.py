import glob, os, pandas as pd
OUT='/home/user/harness/data'
TF={'15m':900_000,'1h':3_600_000,'4h':14_400_000,'1d':86_400_000}
rows=[]
for mk in ('spot','futures'):
    for f in sorted(glob.glob(f'{OUT}/{mk}/*.csv')):
        sym,tf=os.path.basename(f)[:-4].split('_')
        d=pd.read_csv(f); ms=TF[tf]
        diff=d.timestamp.diff().dropna()
        gaps=diff[diff>ms]; missing=int(((gaps/ms)-1).sum())
        bad=int(((d.high<d[['open','close']].max(axis=1))|(d.low>d[['open','close']].min(axis=1))|(d[['open','high','low','close']]<=0).any(axis=1)).sum())
        rows.append(dict(market=mk,sym=sym,tf=tf,rows=len(d),start=pd.to_datetime(d.timestamp.iloc[0],unit='ms'),end=pd.to_datetime(d.timestamp.iloc[-1],unit='ms'),
            dups=int(d.timestamp.duplicated().sum()),gaps=len(gaps),missing_bars=missing,max_gap_h=round(gaps.max()/3.6e6,1) if len(gaps) else 0,
            bad_ohlc=bad,zero_vol=int((d.volume==0).sum()),unaligned=int((d.timestamp%ms!=0).sum())))
r=pd.DataFrame(rows); pd.set_option('display.width',250); pd.set_option('display.max_rows',300)
print(r.to_string(index=False))
r.to_csv('/tmp/claude-0/-home-user-trading-bot/b026c849-edc4-5389-885c-d44379af656a/scratchpad/coverage.csv',index=False)
# plausibilidad BTC 2021
for mk in ('spot','futures'):
    d=pd.read_csv(f'{OUT}/{mk}/BTCUSDT_1d.csv'); d['y']=pd.to_datetime(d.timestamp,unit='ms').dt.year
    print(mk,'BTC por anio min/max close:', d.groupby('y').close.agg(['min','max']).round(0).to_dict('index'))
# validacion cruzada spot (static-klines) vs spot_close del dataset de futuros, 15m
for s in ['BTCUSDT','ETHUSDT','SOLUSDT','DOGEUSDT','DOTUSDT']:
    a=pd.read_csv(f'{OUT}/spot/{s}_15m.csv')
    b=pd.read_parquet(f'{OUT}/raw/bt/Binance_Data/{s}_15m_master_2020_2026.parquet',columns=['open_time_ms','spot_close','close'])
    m=a.merge(b,left_on='timestamp',right_on='open_time_ms')
    rel=(m.close_x/m.spot_close-1).abs(); basis=(m.close_y/m.close_x-1)
    print(s,'n',len(m),'spot vs spot_close: exact%',round((rel<1e-9).mean()*100,2),'p99 relerr',f'{rel.quantile(.99):.2e}','max',f'{rel.max():.2e}',' basis fut/spot median',f'{basis.median():.2e}','p99abs',f'{basis.abs().quantile(.99):.2e}')
# funding
for f in sorted(glob.glob(f'{OUT}/funding/*.csv')):
    d=pd.read_csv(f); print('funding',os.path.basename(f)[:-4],len(d),pd.to_datetime(d.timestamp.iloc[0],unit='ms'),pd.to_datetime(d.timestamp.iloc[-1],unit='ms'),'min',d.funding_rate.min(),'max',d.funding_rate.max())
