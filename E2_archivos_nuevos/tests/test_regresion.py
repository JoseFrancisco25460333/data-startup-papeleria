"""Pruebas de la regresion por minimos cuadrados (services/modelos/regresion.py)."""
import numpy as np
import pandas as pd

import regresion as r


def test_recupera_coeficientes_conocidos():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(500, 3))
    y = 5 + X @ np.array([2.0, -1.0, 0.5]) + rng.normal(0, 0.01, 500)
    m = r.MinimosCuadrados().fit(X, y)
    assert abs(m.intercepto_ - 5) < 0.01
    assert np.allclose(m.coef_, [2.0, -1.0, 0.5], atol=0.01)


def test_coincide_con_sklearn():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(300, 4))
    y = X @ np.array([1.0, 2.0, 3.0, 4.0]) + rng.normal(size=300)
    assert r.comparar_con_sklearn(X, y)["dif_max"] < 1e-8


def test_metricas_a_mano():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    yhat = np.array([1.0, 2.0, 3.0, 6.0])
    m = r.metricas(y, yhat)
    assert m["MSE"] == 1.0 and m["RMSE"] == 1.0 and m["MAE"] == 0.5
    assert abs(m["R2"] - (1 - 4 / 5)) < 1e-12
    assert r.metricas(y, y)["R2"] == 1.0


def test_durbin_watson_ruido_vs_autocorrelado():
    rng = np.random.default_rng(2)
    assert abs(r.durbin_watson(rng.normal(size=5000)) - 2) < 0.1
    assert r.durbin_watson(np.cumsum(rng.normal(size=5000))) < 0.2


def test_ajustar_ventas_corte_temporal_y_calendario():
    f = pd.date_range("2025-01-01", periods=400)
    rng = np.random.default_rng(3)
    X = r.matriz_disenio(f)
    y = pd.Series(1000 + 3 * X["t (dias)"] + 800 * X["sabado"] + 500 * X["quincena"]
                  + rng.normal(0, 30, len(f)), index=f)
    o = r.ajustar_ventas(y, dias_prueba=28)
    assert o["n_entrenamiento"] == 372
    assert abs(o["coeficientes"]["sabado"] - 800) < 30
    assert abs(o["coeficientes"]["t (dias)"] - 3) < 0.2
    assert o["metricas_prueba"]["RMSE"] < 60
    assert o["sklearn"]["dif_max"] < 1e-6
