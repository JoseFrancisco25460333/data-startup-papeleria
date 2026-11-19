"""Genera las cifras y las imagenes del analisis de E2 (serie de tiempo y regresion).

Uso (desde la raiz del repo):  python services/modelos/reporte_e2.py
Escribe docs/reporte_e2.json y docs/img/e2_*.png. Los numeros de docs/E2-cimientos.md
salen de este script.
"""
import json
import os
import sys

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "tablero"))
import graficas as g  # noqa: E402
import regresion as reg  # noqa: E402
import series as ser  # noqa: E402

df = g.preparar(pd.read_csv("data/ventas_papeleria_clean.csv"))
v = g.ventas_diarias(df)

d = ser.descomponer(v, 7)
o = reg.ajustar_ventas(v)
adf = {nombre: ser.adf(s.values) for nombre, s in [
    ("original", v), ("diferencia_1", ser.diferenciar(v)), ("diferencia_semanal_7", ser.diferenciar(v, 1, 7))]}
a, p = ser.acf(v.values, 28), ser.pacf(v.values, 28)
banda = ser.banda_confianza(len(v))
sig = lambda x: [int(k) for k in range(1, 29) if abs(x[k]) > banda]  # noqa: E731

res = {
    "dias": len(v),
    "fuerza": ser.fuerza(d),
    "estacionalidad_semanal": {g.DIAS[int(dia)]: round(float(val), 1)
                               for dia, val in zip(d.index[:7].dayofweek, d["estacionalidad"].iloc[:7])},
    "adf": adf,
    "acf_rezagos_1_7_14_21": {k: round(float(a[k]), 3) for k in (1, 7, 14, 21)},
    "pacf_rezagos_1_2_7": {k: round(float(p[k]), 3) for k in (1, 2, 7)},
    "banda_95": round(float(banda), 3),
    "rezagos_significativos_acf": sig(a),
    "rezagos_significativos_pacf": sig(p),
    "regresion": {
        "n_entrenamiento": o["n_entrenamiento"], "n_prueba": len(v) - o["n_entrenamiento"],
        "intercepto": o["intercepto"], "coeficientes": o["coeficientes"],
        "pendiente_tendencia_simple": o["pendiente_diaria"],
        "metricas_entrenamiento": o["metricas_entrenamiento"],
        "metricas_prueba": o["metricas_prueba"],
        "metricas_solo_tendencia": o["metricas_tendencia_sola"],
        "durbin_watson": o["durbin_watson"], "sesgo_curtosis": list(o["sesgo_curtosis"]),
        "comparacion_sklearn": o["sklearn"],
    },
}
os.makedirs("docs/img", exist_ok=True)
with open("docs/reporte_e2.json", "w", encoding="utf-8") as f:
    json.dump(res, f, indent=2, ensure_ascii=False)
for nombre, fn in [("e2_01_regresion", g.g_regresion), ("e2_02_descomposicion", g.g_descomposicion),
                   ("e2_03_acf_pacf", g.g_acf_pacf), ("e2_04_residuos", g.g_residuos)]:
    fig, titulo = fn(df)
    fig.tight_layout()
    fig.savefig(f"docs/img/{nombre}.png", dpi=110)
    print(nombre, "->", titulo)
print(json.dumps({k: res[k] for k in ("fuerza", "estacionalidad_semanal", "acf_rezagos_1_7_14_21",
                                       "pacf_rezagos_1_2_7", "rezagos_significativos_acf",
                                       "rezagos_significativos_pacf")}, indent=1, ensure_ascii=False))
