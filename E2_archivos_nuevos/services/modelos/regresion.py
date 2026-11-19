"""Regresion lineal por minimos cuadrados (E2, Analitica U3).

beta = (X'X)^-1 X'y  resuelta con la ecuacion normal en NumPy y comparada
contra scikit-learn. Incluye metricas (MSE, RMSE, MAE, R2) y analisis de residuos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class MinimosCuadrados:
    """Regresion lineal con intercepto, por ecuacion normal."""

    def fit(self, X, y):
        X = np.asarray(X, float)
        if X.ndim == 1:
            X = X[:, None]
        A = np.column_stack([np.ones(len(X)), X])
        # solve(A'A, A'y) = (A'A)^-1 A'y sin invertir la matriz explicitamente
        self.beta_ = np.linalg.solve(A.T @ A, A.T @ np.asarray(y, float))
        return self

    @property
    def intercepto_(self) -> float:
        return float(self.beta_[0])

    @property
    def coef_(self) -> np.ndarray:
        return self.beta_[1:]

    def predict(self, X):
        X = np.asarray(X, float)
        if X.ndim == 1:
            X = X[:, None]
        return self.beta_[0] + X @ self.beta_[1:]


def metricas(y, yhat) -> dict:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    e = y - yhat
    mse = float(np.mean(e ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {"MSE": mse, "RMSE": float(np.sqrt(mse)), "MAE": float(np.mean(np.abs(e))),
            "R2": float(1 - np.sum(e ** 2) / ss_tot)}


def durbin_watson(e) -> float:
    """~2 = sin autocorrelacion de residuos; <1.5 = positiva fuerte."""
    e = np.asarray(e, float)
    return float(np.sum(np.diff(e) ** 2) / np.sum(e ** 2))


def sesgo_curtosis(e) -> tuple[float, float]:
    e = np.asarray(e, float)
    z = (e - e.mean()) / e.std()
    return float(np.mean(z ** 3)), float(np.mean(z ** 4) - 3)


def comparar_con_sklearn(X, y) -> dict:
    """Ajusta con la implementacion propia y con scikit-learn; devuelve ambos
    juegos de coeficientes y la diferencia maxima (debe ser ~0)."""
    from sklearn.linear_model import LinearRegression

    propio = MinimosCuadrados().fit(X, y)
    sk = LinearRegression().fit(np.asarray(X, float).reshape(len(y), -1), y)
    dif = max(abs(propio.intercepto_ - sk.intercept_),
              float(np.max(np.abs(propio.coef_ - sk.coef_))))
    return {"propio": [propio.intercepto_, *propio.coef_.tolist()],
            "sklearn": [float(sk.intercept_), *sk.coef_.tolist()],
            "dif_max": float(dif)}


# ---------------------------------------------------------- caso de la papeleria
NOMBRES_X = ["t (dias)", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
             "quincena", "regreso a clases", "vacaciones dic"]


def matriz_disenio(fechas: pd.DatetimeIndex) -> pd.DataFrame:
    """Variables explicativas de las ventas diarias: tendencia, dia de la semana
    (lunes = base), quincena, regreso a clases y vacaciones de diciembre."""
    f = pd.DatetimeIndex(fechas)
    X = pd.DataFrame(index=f)
    X["t (dias)"] = (f - f[0]).days.astype(float)
    nombres = ["martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    for i, n in enumerate(nombres, start=1):
        X[n] = (f.dayofweek == i).astype(float)
    X["quincena"] = f.day.isin([15, 16, 30, 31, 1]).astype(float)
    X["regreso a clases"] = (((f.month == 8) & (f.day >= 17)) | ((f.month == 9) & (f.day <= 12))
                             | ((f.month == 1) & (f.day >= 4) & (f.day <= 25))).astype(float)
    X["vacaciones dic"] = (((f.month == 12) & (f.day >= 20)) | ((f.month == 1) & (f.day <= 3))).astype(float)
    return X


def ajustar_ventas(diarias: pd.Series, dias_prueba: int = 28) -> dict:
    """Ajusta ventas_diarias ~ variables, con corte temporal (los ultimos
    `dias_prueba` dias se reservan para evaluar; nunca se revuelve el orden)."""
    X = matriz_disenio(diarias.index)
    n_ent = len(diarias) - dias_prueba
    Xe, ye = X.iloc[:n_ent], diarias.iloc[:n_ent]
    Xp, yp = X.iloc[n_ent:], diarias.iloc[n_ent:]
    m = MinimosCuadrados().fit(Xe.values, ye.values)
    pred_ent, pred_prueba = m.predict(Xe.values), m.predict(Xp.values)
    res = ye.values - pred_ent
    simple = MinimosCuadrados().fit(Xe[["t (dias)"]].values, ye.values)  # solo tendencia
    sk = comparar_con_sklearn(Xe.values, ye.values)
    return {
        "modelo": m, "X": X, "n_entrenamiento": n_ent,
        "ajuste": pd.Series(m.predict(X.values), index=diarias.index),
        "tendencia_lineal": pd.Series(simple.predict(X[["t (dias)"]].values), index=diarias.index),
        "pendiente_diaria": float(simple.coef_[0]),
        "coeficientes": dict(zip(NOMBRES_X, m.coef_.tolist())),
        "intercepto": m.intercepto_,
        "metricas_entrenamiento": metricas(ye.values, pred_ent),
        "metricas_prueba": metricas(yp.values, pred_prueba),
        "metricas_tendencia_sola": metricas(ye.values, simple.predict(Xe[["t (dias)"]].values)),
        "residuos": pd.Series(res, index=ye.index),
        "durbin_watson": durbin_watson(res),
        "sesgo_curtosis": sesgo_curtosis(res),
        "sklearn": sk,
    }
