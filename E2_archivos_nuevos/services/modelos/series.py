"""Serie de tiempo (E2, Analitica U3): descomposicion, prueba ADF, ACF y PACF.

Todo esta implementado con numpy/pandas para poder explicarlo en la defensa.
La prueba ADF se compara contra statsmodels en tests/test_series.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Valores criticos asintoticos de Dickey-Fuller (MacKinnon), regresion con constante
CRITICOS_ADF = {"1%": -3.43, "5%": -2.86, "10%": -2.57}


def descomponer(y: pd.Series, periodo: int = 7, modelo: str = "aditivo") -> pd.DataFrame:
    """Descomposicion clasica: y = tendencia + estacionalidad + residuo.

    tendencia: media movil centrada de ancho `periodo` (si es par, 2 x periodo).
    estacionalidad: promedio de (y - tendencia) por posicion dentro del ciclo,
    centrado en cero (en 1 si el modelo es multiplicativo).
    """
    if modelo not in ("aditivo", "multiplicativo"):
        raise ValueError("modelo debe ser 'aditivo' o 'multiplicativo'")
    v = y.astype(float)
    if periodo % 2:
        pesos = np.ones(periodo) / periodo
    else:
        pesos = np.r_[0.5, np.ones(periodo - 1), 0.5] / periodo
    tend = v.rolling(len(pesos), center=True).apply(lambda w: float(np.dot(w, pesos)), raw=True)
    sin_tend = v - tend if modelo == "aditivo" else v / tend
    pos = np.arange(len(v)) % periodo
    est_pos = sin_tend.groupby(pos).mean()
    est_pos = est_pos - est_pos.mean() if modelo == "aditivo" else est_pos / est_pos.mean()
    est = pd.Series(est_pos.reindex(pos).values, index=v.index)
    res = v - tend - est if modelo == "aditivo" else v / (tend * est)
    return pd.DataFrame({"observado": v, "tendencia": tend, "estacionalidad": est, "residuo": res})


def fuerza(d: pd.DataFrame) -> dict:
    """Fuerza de tendencia y estacionalidad (0 a 1), segun Hyndman."""
    r = d["residuo"].dropna()
    t = (d["tendencia"] + d["residuo"]).dropna()
    s = (d["estacionalidad"] + d["residuo"]).dropna()
    return {"tendencia": float(max(0, 1 - r.var() / t.var())),
            "estacionalidad": float(max(0, 1 - r.var() / s.var()))}


def acf(x, nlags: int = 40) -> np.ndarray:
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    x = x - x.mean()
    den = float(np.dot(x, x))
    return np.array([np.dot(x[:len(x) - k], x[k:]) / den for k in range(nlags + 1)])


def pacf(x, nlags: int = 40) -> np.ndarray:
    """PACF por recursion de Durbin-Levinson a partir de la ACF."""
    r = acf(x, nlags)
    phi = np.zeros((nlags + 1, nlags + 1))
    out = [1.0]
    for k in range(1, nlags + 1):
        if k == 1:
            phi[1, 1] = r[1]
        else:
            num = r[k] - sum(phi[k - 1, j] * r[k - j] for j in range(1, k))
            den = 1 - sum(phi[k - 1, j] * r[j] for j in range(1, k))
            phi[k, k] = num / den
            for j in range(1, k):
                phi[k, j] = phi[k - 1, j] - phi[k, k] * phi[k - 1, k - j]
        out.append(phi[k, k])
    return np.array(out)


def banda_confianza(n: int) -> float:
    """Banda de ~95% para ACF/PACF de ruido blanco: +-1.96/sqrt(n)."""
    return 1.96 / np.sqrt(n)


def _ols_adf(y: np.ndarray, p: int, inicio: int):
    dy = np.diff(y)
    t = np.arange(inicio, len(dy))
    cols = [y[t], np.ones(len(t))] + [dy[t - j] for j in range(1, p + 1)]
    X = np.column_stack(cols)
    Y = dy[t]
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    e = Y - X @ beta
    return X, Y, beta, e


def adf(x, maxlag: int | None = None) -> dict:
    """Dickey-Fuller aumentada con constante.

    dy_t = a + g*y_{t-1} + sum_j d_j*dy_{t-j} + e_t ; H0: g = 0 (raiz unitaria).
    Rezagos elegidos con AIC (maximo de Schwert). Se rechaza H0 si el
    estadistico es menor que el valor critico.
    """
    y = np.asarray(x, float)
    y = y[~np.isnan(y)]
    if maxlag is None:
        maxlag = int(np.ceil(12 * (len(y) / 100) ** 0.25))
    mejor_p, mejor_aic = 0, np.inf
    for p in range(maxlag + 1):
        X, Y, _, e = _ols_adf(y, p, maxlag)  # misma muestra para comparar AIC
        n = len(Y)
        aic = n * np.log(e @ e / n) + 2 * X.shape[1]
        if aic < mejor_aic:
            mejor_p, mejor_aic = p, aic
    X, Y, beta, e = _ols_adf(y, mejor_p, mejor_p)  # remuestrea con todas las obs
    n, k = X.shape
    s2 = e @ e / (n - k)
    se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[0, 0])
    est = float(beta[0] / se)
    return {"estadistico": est, "rezagos": int(mejor_p), "n_obs": int(n),
            "criticos": CRITICOS_ADF,
            "estacionaria_5%": bool(est < CRITICOS_ADF["5%"])}


def diferenciar(y: pd.Series, orden: int = 1, lag: int = 1) -> pd.Series:
    out = y.copy()
    for _ in range(orden):
        out = out.diff(lag)
    return out.dropna()
