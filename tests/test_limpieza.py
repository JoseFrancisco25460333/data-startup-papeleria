"""Pruebas del modulo de limpieza. Correr: pytest tests/ -q"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "worker"))
from limpieza import limpiar  # noqa: E402


def base():
    return pd.DataFrame({
        "ticket_id": [1, 2, 3, 4, 5, 6],
        "fecha": ["2026-01-05"] * 6,
        "hora": [9, 10, 11, 12, 13, 14],
        "canal": ["mostrador"] * 6,
        "producto": ["Lapiz HB"] * 6,
        "cantidad": [2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        "precio_unitario": [6.0] * 6,
        "total": [12.0] * 6,
    })


def test_duplicados():
    df = pd.concat([base(), base().iloc[[0]]])
    limpio, rep = limpiar(df)
    assert rep["duplicados"] == 1 and len(limpio) == 6


def test_fecha_otro_formato():
    df = base()
    df.loc[0, "fecha"] = "05/01/2026"
    limpio, rep = limpiar(df)
    assert rep["tipos_fecha"] == 1
    assert (limpio["fecha"] == pd.Timestamp("2026-01-05")).all()


def test_nombre_producto():
    df = base()
    df.loc[0, "producto"] = "  lapiz hb "
    limpio, rep = limpiar(df)
    assert rep["formato_producto"] == 1 and set(limpio["producto"]) == {"Lapiz HB"}


def test_negativo_y_faltante_se_recuperan():
    df = base()
    df.loc[0, "cantidad"] = -2.0
    df.loc[1, "cantidad"] = float("nan")
    limpio, rep = limpiar(df)
    assert rep["negativos"] == 1 and rep["faltantes"] == 1
    assert (limpio["cantidad"] == 2).all() and (limpio["total"] == 12.0).all()


def test_atipico():
    df = base()
    df.loc[0, "cantidad"] = 999.0
    limpio, rep = limpiar(df)
    assert rep["atipicos"] == 1 and limpio["cantidad"].max() == 2


def test_total_incoherente():
    df = base()
    df.loc[0, "total"] = 120.0
    limpio, rep = limpiar(df)
    assert rep["logicos_total"] == 1 and (limpio["total"] == 12.0).all()


def test_columnas_faltantes():
    import pytest
    with pytest.raises(ValueError):
        limpiar(base().drop(columns=["total"]))
