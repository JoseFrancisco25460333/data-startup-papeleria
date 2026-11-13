"""KPIs y graficas del tablero. Cada grafica devuelve (figura, titulo-hallazgo).

El titulo se calcula con los datos: responde una pregunta, no dice "Ventas por dia".
"""
from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
AZUL, NARANJA, VERDE, GRIS = "#2563eb", "#ea580c", "#16a34a", "#6b7280"


def _pesos(x: float) -> str:
    return f"${x:,.0f}"


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["dia_semana"] = df["fecha"].dt.dayofweek
    return df


def ventas_diarias(df: pd.DataFrame) -> pd.Series:
    s = df.groupby("fecha")["total"].sum()
    return s.reindex(pd.date_range(s.index.min(), s.index.max()), fill_value=0.0)


def tickets(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("ticket_id").agg(
        fecha=("fecha", "first"), canal=("canal", "first"),
        monto=("total", "sum"), articulos=("cantidad", "sum"), lineas=("producto", "count"))


# ------------------------------------------------------------------ KPIs
def kpis(df: pd.DataFrame) -> dict:
    t = tickets(df)
    por_prod = df.groupby("producto")["total"].sum().sort_values(ascending=False)
    diarias = ventas_diarias(df)
    ultima = diarias.index.max()
    sem_act = diarias[diarias.index > ultima - pd.Timedelta(days=7)].sum()
    sem_ant = diarias[(diarias.index > ultima - pd.Timedelta(days=14))
                      & (diarias.index <= ultima - pd.Timedelta(days=7))].sum()
    var = (sem_act / sem_ant - 1) if sem_ant else float("nan")
    return {
        "ventas": df["total"].sum(),
        "ticket_promedio": t["monto"].mean(),
        "producto_estrella": por_prod.index[0],
        "producto_estrella_ventas": por_prod.iloc[0],
        "variacion_semana": var,
        "semana_actual": sem_act,
        "semana_anterior": sem_ant,
        "fin": ultima,
    }


# ------------------------------------------------------- 1. lineas (tendencia)
def g_tendencia(df):
    d = ventas_diarias(df)
    sem = d.resample("W-SUN").sum()
    sem = sem.iloc[1:-1] if len(sem) > 3 else sem
    media7 = d.rolling(7, center=True).mean()
    x = np.arange(len(d))
    pend = np.polyfit(x, d.values, 1)[0]
    crec = pend * 365 / d.mean()
    pico = sem.idxmax()
    titulo = (f"Las ventas crecen ~{crec:.0%} al año y la semana más fuerte fue la del "
              f"{pico:%d/%m/%Y} ({_pesos(sem.max())})")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(d.index, d.values, color="#cbd5e1", lw=0.8, label="Venta diaria")
    ax.plot(media7.index, media7.values, color=AZUL, lw=2, label="Promedio móvil 7 días")
    ax.set_ylabel("Ventas (MXN)")
    ax.legend(frameon=False)
    return fig, titulo


# ------------------------------------------------------- 2. histograma (ticket)
def g_histograma(df):
    t = tickets(df)["monto"]
    bins = int(math.ceil(1 + math.log2(len(t))))  # regla de Sturges
    mediana, media = t.median(), t.mean()
    sesgo = t.skew()
    titulo = (f"La mitad de los tickets son menores a {_pesos(mediana)}, pero unos pocos grandes "
              f"suben el promedio a {_pesos(media)} (sesgo {sesgo:.1f})")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.hist(t.clip(upper=t.quantile(0.995)), bins=bins, color=AZUL, edgecolor="white")
    ax.axvline(mediana, color=NARANJA, lw=2, label=f"Mediana {_pesos(mediana)}")
    ax.axvline(media, color=VERDE, lw=2, ls="--", label=f"Promedio {_pesos(media)}")
    ax.set_xlabel(f"Monto del ticket (MXN) · {bins} bins, regla de Sturges")
    ax.set_ylabel("Tickets")
    ax.legend(frameon=False)
    return fig, titulo


# ------------------------------------------------------------ 3. mapa de calor
def g_calor(df):
    t = df.drop_duplicates("ticket_id")[["ticket_id", "dia_semana", "hora"]]
    m = pd.crosstab(t["dia_semana"], t["hora"]).reindex(range(7)).fillna(0)
    dia, hora = np.unravel_index(m.values.argmax(), m.shape)
    hora = m.columns[hora]
    por_dia = m.sum(axis=1)
    rel = por_dia.iloc[6] / por_dia.iloc[5]
    titulo = (f"La hora pico es el {DIAS[dia]} a las {hora}:00; "
              f"el domingo se vende {rel:.0%} de lo que se vende el sábado")
    fig, ax = plt.subplots(figsize=(9, 3.8))
    im = ax.imshow(m.values, aspect="auto", cmap="YlOrRd")
    ax.set_yticks(range(7), [d[:3].capitalize() for d in DIAS])
    ax.set_xticks(range(len(m.columns)), [f"{h}h" for h in m.columns])
    fig.colorbar(im, ax=ax, label="Tickets")
    return fig, titulo


# ------------------------------------------------------------ 4. dispersion
def g_dispersion(df):
    t = tickets(df)
    r = t["lineas"].corr(t["monto"])
    rng = np.random.default_rng(0)
    muestra = t.sample(min(len(t), 4000), random_state=0)
    a, b = np.polyfit(muestra["lineas"], muestra["monto"], 1)
    titulo = (f"Cada producto distinto que se agrega a la compra suma ~{_pesos(a)} al ticket "
              f"(r = {r:.2f}): la venta cruzada sí paga")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.scatter(muestra["lineas"] + rng.uniform(-0.25, 0.25, len(muestra)), muestra["monto"],
               s=6, alpha=0.3, color=AZUL)
    xs = np.linspace(muestra["lineas"].min(), muestra["lineas"].max(), 50)
    ax.plot(xs, a * xs + b, color=NARANJA, lw=2)
    ax.set_ylim(0, muestra["monto"].quantile(0.99))
    ax.set_xlabel("Productos distintos en el ticket")
    ax.set_ylabel("Monto (MXN)")
    return fig, titulo


# ------------------------------------------------------------ 5. espectral FFT
def espectro(df, nfft: int = 8192):
    """Periodograma de las ventas diarias, sin tendencia ni temporadas largas.

    Se rellena con ceros (zero-padding) hasta nfft para localizar mejor los picos.
    """
    d = ventas_diarias(df)
    lenta = d.rolling(61, center=True, min_periods=15).mean()  # tendencia + temporadas largas
    y = (d - lenta).fillna(0).values
    y = (y - y.mean()) * np.hanning(len(y))
    f = np.fft.rfftfreq(nfft, d=1.0)[1:]
    p = (np.abs(np.fft.rfft(y, n=nfft)) ** 2 / len(y))[1:]
    return 1 / f, p


BANDAS = [("semanal", 6, 8), ("quincenal", 13, 17), ("mensual", 27, 34)]


def ciclos_dominantes(df):
    """Pico mas fuerte de cada banda (semanal, quincenal, mensual) y cuanto
    supera a la potencia mediana del espectro (>3x = ciclo real, no ruido)."""
    periodo, p = espectro(df)
    base = np.median(p[(periodo >= 3) & (periodo <= 60)])
    out = []
    for nombre, lo, hi in BANDAS:
        m = (periodo >= lo) & (periodo <= hi)
        i = int(np.argmax(np.where(m, p, -1)))
        if p[i] <= p[i - 1] or p[i] <= p[i + 1] or not m[i - 1] or not m[i + 1]:
            continue  # el maximo esta en el borde de la banda: no es un pico real
        out.append({"ciclo": nombre, "periodo": float(periodo[i]), "potencia": float(p[i]),
                    "veces_sobre_ruido": float(p[i] / base)})
    return out


def g_espectral(df):
    periodo, p = espectro(df)
    cic = [c for c in ciclos_dominantes(df) if c["veces_sobre_ruido"] > 3]
    partes = ", ".join(f"{c['ciclo']} ({c['periodo']:.1f} días)" for c in cic)
    titulo = f"Las ventas laten en ciclos {partes}: hay que surtir y promocionar a ese ritmo"
    fig, ax = plt.subplots(figsize=(9, 3.6))
    m = (periodo <= 45) & (periodo >= 5)
    ax.plot(periodo[m], p[m], color=AZUL, lw=1.5)
    for c in cic:
        ax.plot([c["periodo"]], [c["potencia"]], "o", color=NARANJA)
        ax.annotate(f"{c['ciclo']}\n{c['periodo']:.1f} d", (c["periodo"], c["potencia"]),
                    textcoords="offset points", xytext=(6, 4), color=NARANJA, fontsize=9)
    ax.set_xlabel("Periodo (días) = 1 / frecuencia")
    ax.set_ylabel("Potencia")
    return fig, titulo


# ------------------------------------------------------------ 6. barras (canal)
def g_canales(df):
    m = (df.assign(mes=df["fecha"].dt.to_period("M").astype(str))
           .pivot_table(index="mes", columns="canal", values="total", aggfunc="sum").fillna(0))
    m = m.iloc[1:-1] if len(m) > 3 else m  # meses completos
    part = (m.get("domicilio", 0) + m.get("web", 0)) / m.sum(axis=1)
    titulo = (f"Domicilio y web ya son {part.iloc[-1]:.0%} de las ventas "
              f"(eran {part.iloc[0]:.0%} hace {len(m) - 1} meses)")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    base = np.zeros(len(m))
    for canal, color in [("mostrador", "#94a3b8"), ("domicilio", AZUL), ("web", NARANJA)]:
        if canal in m:
            ax.bar(m.index, m[canal].values, bottom=base, label=canal.capitalize(), color=color)
            base += m[canal].values
    ax.set_ylabel("Ventas (MXN)")
    ax.tick_params(axis="x", rotation=60)
    ax.legend(frameon=False, ncol=3)
    return fig, titulo


# ------------------------------------------------------------ hallazgos extra
def efecto_dia_semana(df):
    d = ventas_diarias(df)
    por = d.groupby(d.index.dayofweek).mean()
    return por


def efecto_quincena(df):
    d = ventas_diarias(df)
    q = d[d.index.day.isin([15, 16, 30, 31, 1])].mean()
    n = d[~d.index.day.isin([15, 16, 30, 31, 1])].mean()
    return q / n - 1


def efecto_regreso_clases(df):
    d = ventas_diarias(df)
    rc = d[((d.index.month == 8) & (d.index.day >= 17)) | ((d.index.month == 9) & (d.index.day <= 12))]
    resto = d.drop(rc.index)
    return rc.mean() / resto.mean() - 1


GRAFICAS = [g_tendencia, g_histograma, g_calor, g_dispersion, g_espectral, g_canales]


def recomendaciones(df) -> list[str]:
    """Tres recomendaciones para el dueño, calculadas con los datos filtrados."""
    quin = efecto_quincena(df)
    rc = efecto_regreso_clases(df)
    t = df.drop_duplicates("ticket_id")
    dom = t[t["canal"] == "domicilio"]
    hora_dom = int(dom["hora"].mode().iloc[0]) if len(dom) else 17
    tk = tickets(df)
    tk_canal = tk.groupby("canal")["monto"].mean()
    dif = tk_canal.get("domicilio", np.nan) / tk_canal.get("mostrador", np.nan) - 1
    dias = efecto_dia_semana(df)
    if dif > 0.03:
        txt_tk = f"El ticket a domicilio es {dif:.0%} mayor que el de mostrador: vale la pena empujarlo."
    elif dif < -0.03:
        txt_tk = f"El ticket a domicilio es {abs(dif):.0%} menor que el de mostrador: ofrece paquetes para subirlo."
    else:
        txt_tk = "El ticket a domicilio es casi igual al de mostrador: crecer ese canal no sacrifica el ticket."
    return [
        f"Surta antes de las temporadas fuertes: en regreso a clases (17 ago–12 sep) se vende "
        f"{rc:.0%} más que el resto del año y en quincena {quin:.0%} más. Compra cuadernos, colores y "
        f"mochilas 2–3 semanas antes para no quedarte sin ellos.",
        f"Lanza las promociones del servicio a domicilio antes del sábado (el día más fuerte) y manda "
        f"el aviso cerca de las {hora_dom - 1}:00–{hora_dom}:00, cuando más pedidos a domicilio llegan. "
        + txt_tk,
        f"Fomenta la venta cruzada: cada producto distinto extra sube el ticket. Ofrece paquetes "
        f"(cuaderno + lápiz + colores) y cotizaciones por lista escolar. El domingo vende solo "
        f"{dias.iloc[6] / dias.iloc[5]:.0%} de lo que vende el sábado: ahí conviene una promoción propia.",
    ]
