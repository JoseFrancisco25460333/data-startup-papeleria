"""Generador de ventas sinteticas para una papeleria con servicio a domicilio.

Uso (desde la raiz del repo):  python data/generar_ventas.py
Salida: data/ventas_papeleria_raw.csv y data/sample/ventas_muestra.csv

Cada fila es una linea de ticket (un producto dentro de una venta).
Simula 21 meses: tendencia de crecimiento, ciclo semanal, efecto quincena,
regreso a clases (agosto-septiembre y enero), vacaciones de diciembre y
crecimiento de los canales domicilio y web. Siembra errores a proposito
(faltantes, negativos, atipicos, nombres mal escritos, fechas en otro formato,
duplicados y totales inconsistentes) para practicar el preprocesamiento.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(2026)

INICIO, FIN = "2025-01-01", "2026-10-18"
dias = pd.date_range(INICIO, FIN, freq="D")

# producto: (precio MXN, peso de popularidad, es_escolar, cantidad tipica)
PRODUCTOS = {
    "Cuaderno profesional": (38, 10, True, 1.6),
    "Cuaderno italiano": (30, 6, True, 1.4),
    "Lapiz HB": (6, 14, True, 3.0),
    "Pluma azul": (8, 16, False, 2.5),
    "Colores caja 12": (55, 4, True, 1.1),
    "Marcatextos": (14, 6, False, 1.8),
    "Hojas blancas paq 500": (110, 3, False, 1.2),
    "Folder manila": (4, 14, False, 6.0),
    "Pegamento en barra": (18, 6, True, 1.3),
    "Tijeras escolares": (28, 2, True, 1.0),
    "Cartulina": (9, 9, True, 3.0),
    "Impresion B/N hoja": (2, 12, False, 14.0),
    "Mochila escolar": (320, 1.0, True, 1.0),
    "Calculadora cientifica": (220, 0.8, True, 1.0),
}
nombres = list(PRODUCTOS)
precios = np.array([PRODUCTOS[p][0] for p in nombres], dtype=float)
pesos = np.array([PRODUCTOS[p][1] for p in nombres], dtype=float)
escolar = np.array([PRODUCTOS[p][2] for p in nombres])
qtip = np.array([PRODUCTOS[p][3] for p in nombres])

SEMANA = [1.00, 1.00, 1.00, 1.05, 1.10, 1.25, 0.55]  # lun..dom
HORAS = np.arange(8, 21)  # 8:00 a 20:59
H_MOSTRADOR = np.array([5, 6, 4, 4, 7, 8, 5, 4, 5, 7, 5, 3, 1], float)
H_DOMICILIO = np.array([0.5, 1, 1, 2, 3, 3, 3, 4, 6, 8, 8, 6, 3], float)
H_WEB = np.array([1, 1, 1, 2, 2, 2, 3, 3, 4, 6, 8, 9, 6], float)

filas = []
ticket_id = 0
for dia in dias:
    t = (dia - dias[0]).days
    f = 1 + 0.0003 * t
    f *= SEMANA[dia.weekday()]
    if dia.day in (15, 16, 30, 31, 1):
        f *= 1.25  # quincena
    reg_clases = (dia.month == 8 and dia.day >= 17) or (dia.month == 9 and dia.day <= 12)
    enero_escolar = dia.month == 1 and 4 <= dia.day <= 25
    if reg_clases:
        f *= 1.7
    elif enero_escolar:
        f *= 1.35
    if (dia.month == 12 and dia.day >= 20) or (dia.month == 1 and dia.day <= 3):
        f *= 0.5
    if dia.month == 7:
        f *= 0.8
    n_tickets = rng.poisson(42 * f)

    p_dom = 0.05 + 0.17 * t / len(dias)
    web_inicio = pd.Timestamp("2026-03-01")
    p_web = 0.0 if dia < web_inicio else min(0.03 + 0.07 * (dia - web_inicio).days / 230, 0.10)
    w = pesos * np.where(escolar, 2.2 if (reg_clases or enero_escolar) else 1.0, 1.0)
    w = w / w.sum()

    for _ in range(n_tickets):
        ticket_id += 1
        u = rng.random()
        canal = "web" if u < p_web else ("domicilio" if u < p_web + p_dom else "mostrador")
        hp = {"mostrador": H_MOSTRADOR, "domicilio": H_DOMICILIO, "web": H_WEB}[canal]
        hora = int(rng.choice(HORAS, p=hp / hp.sum()))
        k = int(min(1 + rng.poisson(1.1), 6))
        items = rng.choice(len(nombres), size=k, replace=False, p=w)
        for i in items:
            cant = max(1, int(rng.poisson(qtip[i])))
            filas.append([ticket_id, dia.strftime("%Y-%m-%d"), hora, canal,
                          nombres[i], cant, precios[i], cant * precios[i]])

df = pd.DataFrame(filas, columns=["ticket_id", "fecha", "hora", "canal", "producto",
                                  "cantidad", "precio_unitario", "total"])

# ---- errores sembrados (el total NO se recalcula: hay inconsistencias logicas)
n = len(df)
df["cantidad"] = df["cantidad"].astype(float)
df.loc[rng.choice(n, 60, replace=False), "cantidad"] = np.nan          # faltantes
df.loc[rng.choice(n, 25, replace=False), "cantidad"] *= -1             # negativos
df.loc[rng.choice(n, 15, replace=False), "cantidad"] = 999             # atipicos
df.loc[rng.choice(n, 30, replace=False), "total"] *= rng.choice([0.5, 2, 10], 30)  # total incoherente
idx = rng.choice(n, 40, replace=False)
df.loc[idx, "producto"] = [(" " + s.lower() + " ") if j % 2 else s.upper()
                           for j, s in enumerate(df.loc[idx, "producto"])]  # formato
idx = rng.choice(n, 30, replace=False)
df.loc[idx, "fecha"] = pd.to_datetime(df.loc[idx, "fecha"]).dt.strftime("%d/%m/%Y")  # tipo
df = pd.concat([df, df.sample(35, random_state=1)])                    # duplicados
df = df.sample(frac=1, random_state=2).reset_index(drop=True)

df.to_csv("data/ventas_papeleria_raw.csv", index=False)
df.head(300).to_csv("data/sample/ventas_muestra.csv", index=False)
print(f"{len(df):,} registros, {df.ticket_id.nunique():,} tickets, {INICIO} a {FIN}")
