"""Limpieza de ventas de la papeleria (modulo reutilizable).

En E1 se corre a mano sobre el CSV; en E2 este mismo modulo corre dentro del
worker que consume la cola, y en E3 dentro de una funcion serverless.

limpiar(df) -> (df_limpio, reporte) donde reporte indica cuantos registros se
corrigieron de cada tipo: duplicados, tipos, formato, faltantes, negativos,
atipicos y errores logicos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CATALOGO = [
    "Cuaderno profesional", "Cuaderno italiano", "Lapiz HB", "Pluma azul",
    "Colores caja 12", "Marcatextos", "Hojas blancas paq 500", "Folder manila",
    "Pegamento en barra", "Tijeras escolares", "Cartulina", "Impresion B/N hoja",
    "Mochila escolar", "Calculadora cientifica",
]
_CANON = {p.lower(): p for p in CATALOGO}
COLUMNAS = ["ticket_id", "fecha", "hora", "canal", "producto",
            "cantidad", "precio_unitario", "total"]


def _parse_fecha(serie: pd.Series) -> pd.Series:
    """ISO (AAAA-MM-DD) primero; lo que no cuadre se intenta como DD/MM/AAAA."""
    s = serie.astype(str).str.strip()
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    otro = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    return iso.fillna(otro)


def limpiar(df: pd.DataFrame, k_iqr: float = 3.0) -> tuple[pd.DataFrame, dict]:
    faltan = set(COLUMNAS) - set(df.columns)
    if faltan:
        raise ValueError(f"Faltan columnas: {sorted(faltan)}")
    df = df[COLUMNAS].copy()
    rep: dict[str, int] = {"registros_entrada": len(df)}

    # 1) duplicados exactos
    rep["duplicados"] = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)

    # 2) tipos: fecha en otro formato -> datetime; numericos como numero
    fecha_iso = pd.to_datetime(df["fecha"].astype(str).str.strip(), format="%Y-%m-%d", errors="coerce")
    rep["tipos_fecha"] = int(fecha_iso.isna().sum())
    df["fecha"] = _parse_fecha(df["fecha"])
    sin_fecha = int(df["fecha"].isna().sum())
    for c in ["hora", "cantidad", "precio_unitario", "total"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["fecha", "precio_unitario"]).reset_index(drop=True)
    rep["descartados_sin_fecha_o_precio"] = sin_fecha

    # 3) formato: nombres de producto (espacios, mayusculas) al catalogo
    limpio = df["producto"].astype(str).str.strip()
    canon = limpio.str.lower().map(_CANON)
    rep["formato_producto"] = int((canon.notna() & (canon != df["producto"])).sum())
    df["producto"] = canon.fillna(limpio)
    rep["producto_fuera_de_catalogo"] = int((~df["producto"].isin(CATALOGO)).sum())
    df["canal"] = df["canal"].astype(str).str.strip().str.lower()

    # 4) negativos (error logico: no hay ventas de cantidad negativa) -> valor absoluto
    neg = df["cantidad"] < 0
    rep["negativos"] = int(neg.sum())
    df.loc[neg, "cantidad"] = df.loc[neg, "cantidad"].abs()

    # 5) atipicos: regla de Tukey por producto (Q3 + k*IQR) -> mediana del producto
    pos = df[df["cantidad"] > 0]
    q1 = pos.groupby("producto")["cantidad"].quantile(0.25)
    q3 = pos.groupby("producto")["cantidad"].quantile(0.75)
    mediana = pos.groupby("producto")["cantidad"].median()
    umbral = (q3 + k_iqr * (q3 - q1)).clip(lower=25)
    um = df["producto"].map(umbral)
    atip = df["cantidad"] > um
    rep["atipicos"] = int(atip.sum())
    rep["faltantes"] = int(df["cantidad"].isna().sum())  # se cuentan antes de marcar atipicos
    df.loc[atip, "cantidad"] = np.nan  # se recuperan junto con los faltantes

    # 6) faltantes: cantidad vacia. Si total y precio son validos, la cantidad se
    #    recupera como total / precio (si da un entero razonable); si no, mediana.
    falt = df["cantidad"].isna()
    recup = (df["total"] / df["precio_unitario"]).round()
    ok = falt & recup.between(1, um) & ((df["total"] / df["precio_unitario"] - recup).abs() < 1e-6)
    df.loc[ok, "cantidad"] = recup[ok]
    resto = df["cantidad"].isna()
    df.loc[resto, "cantidad"] = df.loc[resto, "producto"].map(mediana)
    rep["recuperados_desde_total"] = int(ok.sum())
    # lotes pequenos: si un producto no tiene mediana (todas sus cantidades faltan), no hay
    # forma honesta de estimar la cantidad -> se descarta y se reporta
    sin_cant = df["cantidad"].isna()
    rep["descartados_sin_cantidad"] = int(sin_cant.sum())
    df = df[~sin_cant].reset_index(drop=True)
    df["cantidad"] = df["cantidad"].round().astype(int)

    # 7) logicos: total debe ser cantidad * precio_unitario
    total_ok = (df["cantidad"] * df["precio_unitario"]).round(2)
    incons = (df["total"].round(2) != total_ok)
    rep["logicos_total"] = int(incons.sum())
    df["total"] = total_ok

    df["hora"] = df["hora"].fillna(df["hora"].median()).astype(int)
    df["ticket_id"] = df["ticket_id"].astype(int)
    df = df.sort_values(["fecha", "ticket_id"]).reset_index(drop=True)
    rep["registros_salida"] = len(df)
    rep["total_corregidos"] = int(sum(rep[k] for k in (
        "duplicados", "tipos_fecha", "formato_producto", "negativos",
        "atipicos", "faltantes", "logicos_total")))
    return df, rep


if __name__ == "__main__":
    import json
    import sys

    entrada = sys.argv[1] if len(sys.argv) > 1 else "data/ventas_papeleria_raw.csv"
    salida = sys.argv[2] if len(sys.argv) > 2 else "data/ventas_papeleria_clean.csv"
    limpio, reporte = limpiar(pd.read_csv(entrada))
    limpio.to_csv(salida, index=False)
    with open("docs/reporte_limpieza.json", "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    print(json.dumps(reporte, indent=2, ensure_ascii=False))
