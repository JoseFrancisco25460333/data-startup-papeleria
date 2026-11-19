"""Pruebas de la descomposicion, ACF/PACF y ADF (services/modelos/series.py)."""
import numpy as np
import pandas as pd
import pytest

import series as s


def _serie(n=364, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    y = 100 + 0.5 * t + 20 * np.sin(2 * np.pi * t / 7) + rng.normal(0, 2, n)
    return pd.Series(y, index=pd.date_range("2025-01-01", periods=n))


def test_descomposicion_suma_y_estacionalidad_centrada():
    y = _serie()
    d = s.descomponer(y, 7)
    ok = d.dropna()
    assert np.allclose(ok["tendencia"] + ok["estacionalidad"] + ok["residuo"], ok["observado"])
    assert abs(d["estacionalidad"].iloc[:7].sum()) < 1e-8
    # la tendencia recuperada crece ~0.5 por dia
    pend = np.polyfit(np.arange(len(ok)), ok["tendencia"], 1)[0]
    assert abs(pend - 0.5) < 0.02


def test_descomposicion_multiplicativa():
    y = _serie() + 200
    d = s.descomponer(y, 7, "multiplicativo").dropna()
    assert np.allclose(d["tendencia"] * d["estacionalidad"] * d["residuo"], d["observado"])
    with pytest.raises(ValueError):
        s.descomponer(y, 7, "otro")


def test_acf_ruido_blanco_y_ciclo_semanal():
    rng = np.random.default_rng(1)
    ruido = rng.normal(size=2000)
    assert abs(s.acf(ruido, 5)[1:]).max() < 0.1
    a = s.acf(_serie(700) - np.arange(700) * 0.5, 14)
    assert a[7] > 0.8 and a[7] > a[3]


def test_pacf_de_un_AR1():
    rng = np.random.default_rng(2)
    x = np.zeros(5000)
    for t in range(1, 5000):
        x[t] = 0.7 * x[t - 1] + rng.normal()
    p = s.pacf(x, 5)
    assert abs(p[1] - 0.7) < 0.05 and abs(p[2]) < 0.05 and abs(p[3]) < 0.05


def test_adf_distingue_ruido_de_caminata_aleatoria():
    rng = np.random.default_rng(3)
    ruido = rng.normal(size=600)
    caminata = np.cumsum(ruido)
    assert s.adf(ruido)["estacionaria_5%"] is True
    assert s.adf(caminata)["estacionaria_5%"] is False
    assert s.adf(np.diff(caminata))["estacionaria_5%"] is True


def test_adf_coincide_con_statsmodels():
    sm = pytest.importorskip("statsmodels.tsa.stattools")
    y = _serie(500).values
    propio = s.adf(y)
    est, _, rez, *_ = sm.adfuller(y, autolag="AIC")
    assert propio["rezagos"] == rez
    assert abs(propio["estadistico"] - est) < 1e-6
