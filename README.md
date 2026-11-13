# Data Startup · Papelería

Plataforma de datos para una papelería con servicio a domicilio: ingesta de ventas, limpieza, tablero y (en entregas siguientes) pronóstico de demanda, agente promotor y cotizador.

**URL pública:** _COMPLETAR cuando exista (E3)_ · **Proveedor:** AWS

## Entregas
| Entrega | Documento |
|---|---|
| E0 · Propuesta | [docs/E0-propuesta.md](docs/E0-propuesta.md) |
| E1 · Dashboard empresarial | [docs/E1-dashboard.md](docs/E1-dashboard.md) |

## Cómo levantarlo
```bash
pip install -r requirements.txt
python data/generar_ventas.py          # datos sintéticos crudos (con errores sembrados)
python services/worker/limpieza.py     # limpieza + docs/reporte_limpieza.json
streamlit run services/tablero/app.py  # tablero
pytest tests -q                        # pruebas de la limpieza
```

## Estructura
```
data/                generador y muestra anonimizada (data/sample)
docs/                E0, E1, reporte de limpieza e imágenes
services/worker/     limpieza.py (después, función serverless)
services/tablero/    app.py (Streamlit) y graficas.py
services/ingesta/    API FastAPI (E2)
services/modelos/    API /pronostico y /clasificar (E3)
tests/               pruebas
```

Los datos completos no se suben a GitHub (`.gitignore`); solo la muestra de `data/sample/`.
