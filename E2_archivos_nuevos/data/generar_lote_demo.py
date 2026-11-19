"""Genera un CSV de "ventas nuevas" para la demo en vivo del flujo de E2.

Toma la ultima semana del CSV limpio, la mueve 7 dias adelante, renumera los
tickets a partir del ultimo y siembra unos errores (para que el worker tenga
algo que limpiar). Uso:  python data/generar_lote_demo.py  -> data/lote_demo.csv
Despues:  curl -F "archivo=@data/lote_demo.csv" http://<IP>:8000/ventas/csv
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
d = pd.read_csv("data/ventas_papeleria_clean.csv", parse_dates=["fecha"])
ult = d[d["fecha"] > d["fecha"].max() - pd.Timedelta(days=7)].copy()
ult["fecha"] = ult["fecha"] + pd.Timedelta(days=7)
ult["ticket_id"] = ult["ticket_id"] + (d["ticket_id"].max() - ult["ticket_id"].min() + 1)
ult["fecha"] = ult["fecha"].dt.strftime("%Y-%m-%d")
ult = ult.reset_index(drop=True)
n = len(ult)
ult["cantidad"] = ult["cantidad"].astype(float)
ult.loc[rng.choice(n, 3, replace=False), "cantidad"] = np.nan          # faltantes
ult.loc[rng.choice(n, 2, replace=False), "cantidad"] *= -1             # negativos
idx = rng.choice(n, 4, replace=False)
ult.loc[idx, "producto"] = ult.loc[idx, "producto"].str.lower()        # formato
ult.loc[rng.choice(n, 2, replace=False), "total"] += 5                 # total incoherente
ult = pd.concat([ult, ult.sample(3, random_state=1)])                  # duplicados
ult.to_csv("data/lote_demo.csv", index=False)
print(f"{len(ult)} registros del {ult['fecha'].min()} al {ult['fecha'].max()} -> data/lote_demo.csv")
