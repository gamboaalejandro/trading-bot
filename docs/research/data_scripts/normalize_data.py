"""Normaliza datos crudos (clonados de GitHub) a /home/user/harness/data/{spot,futures,funding}.
Fuentes:
  futuros: github.com/kbsingh1399/Backtesting_Data  (Binance_Data/*_15m_master_2020_2026.parquet)
  spot:    github.com/finom/static-klines           (.klines-cache/{SYM}/{tf}/*.json, formato kline REST Binance)
No genera datos: solo re-muestrea (agrega) velas reales de 15m a 1h/4h/1d para futuros.
"""
import glob, json, os, sys
import pandas as pd

RAW = '/home/user/harness/data/raw'
OUT = '/home/user/harness/data'
COLS = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
TF_MS = {'15m': 900_000, '1h': 3_600_000, '4h': 14_400_000, '1d': 86_400_000}
CUTOFF_MS = int(sys.argv[1]) if len(sys.argv) > 1 else None  # descarta velas no cerradas

def resample(df, tf):
    ms = TF_MS[tf]
    g = df.groupby(df.timestamp // ms * ms)
    r = pd.DataFrame({'open': g.open.first(), 'high': g.high.max(), 'low': g.low.min(),
                      'close': g.close.last(), 'volume': g.volume.sum(), 'n': g.size()})
    r.index.name = 'timestamp'
    r = r.reset_index()
    full = ms // 900_000
    return r[r.n == full].drop(columns='n')   # solo velas completas (todas las sub-velas 15m presentes)

def futures():
    os.makedirs(f'{OUT}/futures', exist_ok=True); os.makedirs(f'{OUT}/funding', exist_ok=True)
    for f in sorted(glob.glob(f'{RAW}/bt/Binance_Data/*_15m_master_2020_2026.parquet')):
        sym = os.path.basename(f).split('_')[0]
        d = pd.read_parquet(f, columns=['open_time_ms', 'open', 'high', 'low', 'close', 'volume_base', 'funding_rate_pct'])
        d = d.rename(columns={'open_time_ms': 'timestamp', 'volume_base': 'volume'}).sort_values('timestamp')
        d = d.drop_duplicates('timestamp')
        d[COLS].to_csv(f'{OUT}/futures/{sym}_15m.csv', index=False)
        for tf in ('1h', '4h', '1d'):
            resample(d, tf)[COLS].to_csv(f'{OUT}/futures/{sym}_{tf}.csv', index=False)
        # funding: la columna es el ultimo funding (en %) propagado a cada vela 15m.
        # Se toma en cada frontera 00/08/16 UTC y en cualquier otra vela donde el valor cambie.
        ts = pd.to_datetime(d.timestamp, unit='ms')
        mask = ((ts.dt.hour % 8 == 0) & (ts.dt.minute == 0)) | (d.funding_rate_pct.diff().fillna(0) != 0)
        fu = pd.DataFrame({'timestamp': d.timestamp[mask], 'funding_rate': d.funding_rate_pct[mask] / 100.0})
        fu.to_csv(f'{OUT}/funding/{sym}.csv', index=False)
        print('futures', sym, len(d))

def spot():
    os.makedirs(f'{OUT}/spot', exist_ok=True)
    for sd in sorted(glob.glob(f'{RAW}/sk/.klines-cache/*')):
        sym = os.path.basename(sd)
        for tf in ('15m', '1h', '4h', '1d'):
            rows = []
            for jf in sorted(glob.glob(f'{sd}/{tf}/*.json')):
                with open(jf) as fh:
                    rows.extend(json.load(fh))
            if not rows:
                continue
            d = pd.DataFrame([r[:7] for r in rows], columns=COLS + ['close_time'])
            d[COLS[1:]] = d[COLS[1:]].astype(float)
            d['timestamp'] = d.timestamp.astype('int64')
            if CUTOFF_MS:
                d = d[d.close_time.astype('int64') < CUTOFF_MS]
            d = d.sort_values('timestamp').drop_duplicates('timestamp')
            d[COLS].to_csv(f'{OUT}/spot/{sym}_{tf}.csv', index=False)
            print('spot', sym, tf, len(d))

if __name__ == '__main__':
    futures(); spot()
