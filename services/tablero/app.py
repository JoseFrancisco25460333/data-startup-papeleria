"""Tablero empresarial de la papeleria (E1).

Correr desde la raiz del repo:
    streamlit run services/tablero/app.py

En E1 lee el CSV limpio local (DATA_PATH). En E2 DATA_PATH apunta a la zona
clean/ del data lake en la nube y las credenciales NO van en el codigo.
"""
import json
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))
import graficas as g  # noqa: E402

DATA_PATH = os.getenv("DATA_PATH", "data/ventas_papeleria_clean.csv")
REPORTE_PATH = os.getenv("REPORTE_PATH", "docs/reporte_limpieza.json")

st.set_page_config(page_title="Papelería · Tablero", page_icon="📎", layout="wide")


@st.cache_data
def cargar(path: str) -> pd.DataFrame:
    return g.preparar(pd.read_csv(path))


df_all = cargar(DATA_PATH)

st.title("📎 Tablero de la papelería")
st.caption("Ventas, domicilio y web · datos de ejemplo (sintéticos) · "
           f"{df_all['fecha'].min():%d/%m/%Y} a {df_all['fecha'].max():%d/%m/%Y}")

# ---- filtros
with st.sidebar:
    st.header("Filtros")
    f_min, f_max = df_all["fecha"].min().date(), df_all["fecha"].max().date()
    rango = st.date_input("Periodo", (f_min, f_max), min_value=f_min, max_value=f_max)
    canales = st.multiselect("Canal", sorted(df_all["canal"].unique()),
                             default=sorted(df_all["canal"].unique()))

if isinstance(rango, tuple) and len(rango) == 2:
    ini, fin = pd.Timestamp(rango[0]), pd.Timestamp(rango[1])
else:
    ini, fin = df_all["fecha"].min(), df_all["fecha"].max()
df = df_all[(df_all["fecha"] >= ini) & (df_all["fecha"] <= fin) & (df_all["canal"].isin(canales))]

if df.empty or df["fecha"].nunique() < 28:
    st.warning("Elige un periodo de al menos 4 semanas y un canal para ver el tablero.")
    st.stop()

# ---- KPIs
k = g.kpis(df)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ventas del periodo", f"${k['ventas']:,.0f}")
c2.metric("Ticket promedio", f"${k['ticket_promedio']:,.2f}")
c3.metric("Producto estrella", k["producto_estrella"], f"${k['producto_estrella_ventas']:,.0f}",
          delta_color="off")
c4.metric("Última semana vs anterior", f"${k['semana_actual']:,.0f}", f"{k['variacion_semana']:+.1%}")

st.divider()

# ---- seis visualizaciones, cada una con su hallazgo en el titulo
for i in range(0, len(g.GRAFICAS), 2):
    cols = st.columns(2)
    for col, fn in zip(cols, g.GRAFICAS[i:i + 2]):
        fig, titulo = fn(df)
        with col:
            st.subheader(titulo)
            fig.tight_layout()
            st.pyplot(fig)

with st.expander("¿Qué significa el análisis espectral?"):
    st.write("La transformada de Fourier convierte las ventas diarias de tiempo a frecuencia. "
             "El periodo en días es 1 / frecuencia. Los picos indican cada cuántos días se repite "
             "el comportamiento de ventas.")
    st.table(pd.DataFrame(g.ciclos_dominantes(df)).rename(columns={
        "ciclo": "Ciclo", "periodo": "Periodo (días)", "potencia": "Potencia",
        "veces_sobre_ruido": "Veces sobre el ruido"}).round(1))

st.divider()
st.header("Tres recomendaciones para el dueño")
for r in g.recomendaciones(df):
    st.markdown(f"- {r}")

# ---- calidad de datos
with st.expander("Calidad de datos: qué se limpió"):
    if os.path.exists(REPORTE_PATH):
        with open(REPORTE_PATH, encoding="utf-8") as f:
            st.json(json.load(f))
    else:
        st.info("Corre `python services/worker/limpieza.py` para generar el reporte.")
