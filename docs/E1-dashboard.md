# E1 · Dashboard empresarial — Papelería

**Cubre:** Analítica unidad 2 (2.1 a 2.8) y Nube tema 2.4 (almacenamiento en nube)
**Datos:** sintéticos, 1 ene 2025 – 18 oct 2026 (ver E0, sección 5)


```bash
pip install -r requirements.txt
python data/generar_ventas.py              # genera data/ventas_papeleria_raw.csv
python services/worker/limpieza.py         # limpia y escribe data/ventas_papeleria_clean.csv + docs/reporte_limpieza.json
streamlit run services/tablero/app.py      # abre el tablero
```

## 1. Datos limpios

Se aplicó la limpieza de la unidad 1 con el módulo `services/worker/limpieza.py` (con pruebas en `tests/`). Resultado sobre 67,719 registros de entrada:

| Tipo de error | Registros corregidos | Cómo se corrigió |
|---|---:|---|
| Duplicados exactos | 35 | Se eliminaron |
| Tipo/formato de fecha (`DD/MM/AAAA`) | 30 | Se convirtió a fecha |
| Formato de producto (mayúsculas, espacios) | 40 | Se normalizó al catálogo de 14 productos |
| Valores faltantes (`cantidad`) | 60 | Se recuperó con `total / precio_unitario` (75 recuperados entre faltantes y atípicos); si no era posible, mediana del producto |
| Valores negativos (`cantidad`) | 25 | Valor absoluto |
| Valores atípicos (`cantidad` = 999) | 16 | Regla de Tukey por producto (Q3 + 3·IQR, mínimo 25); se recuperó igual que los faltantes |
| Errores lógicos (`total` ≠ `cantidad × precio`) | 31 | Se recalculó el total |
| **Total de correcciones** | **237** | **Salida: 67,684 registros** |

Nota: de los 16 atípicos, 15 fueron sembrados a propósito; 1 fue un valor legítimamente alto que la regla marcó (y que se recuperó con su total, sin cambiarlo).

## 2. Indicadores (KPI)

| KPI | Valor (periodo completo) |
|---|---|
| Ventas del periodo | $2,950,394 |
| Ticket promedio | $91.07 |
| Producto estrella | Cuaderno profesional ($481,612) |
| Variación última semana vs anterior | +0.2% ($35,545 vs $35,468) |

El tablero recalcula los KPI al filtrar periodo y canal.

## 3. Seis visualizaciones

Cada título responde una pregunta con un hallazgo calculado de los datos.

| # | Gráfica | Tipo | Hallazgo (título en el tablero) |
|---|---|---|---|
| 1 | `img/01_tendencia.png` | Líneas | Las ventas crecen ~16% al año y la semana más fuerte fue la del 06/09/2026 ($64,171) |
| 2 | `img/02_histograma_ticket.png` | Histograma (Sturges) | La mitad de los tickets son menores a $60, pero unos pocos grandes suben el promedio a $91 (sesgo 4.5) |
| 3 | `img/03_mapa_calor.png` | Mapa de calor día × hora | La hora pico es el sábado a las 17:00; el domingo se vende 45% de lo que se vende el sábado |
| 4 | `img/04_dispersion.png` | Dispersión | Cada producto distinto que se agrega a la compra suma ~$45 al ticket (r = 0.43): la venta cruzada sí paga |
| 5 | `img/05_espectral.png` | Análisis espectral (FFT) | Las ventas laten en ciclos semanal (7.0 días) y quincenal (15.1 días) |
| 6 | `img/06_canales.png` | Barras apiladas | Domicilio y web ya son 30% de las ventas (eran 7% hace 19 meses) |

La elección de cada gráfica responde a la pregunta: tendencia (líneas), distribución (histograma), relación entre dos variables (dispersión), composición (barras por canal) y patrón por día/hora (mapa de calor).

## 4. Análisis espectral (FFT)

Se tomó la serie de ventas diarias (657 días), se le quitó la tendencia y las temporadas largas restando una media móvil de 61 días, se aplicó una ventana de Hann y se calculó la transformada de Fourier (con relleno de ceros para ubicar mejor los picos). El **periodo en días = 1 / frecuencia**.

| Ciclo | Periodo detectado | Veces sobre el ruido | Qué significa para el negocio |
|---|---:|---:|---|
| Semanal | 7.0 días | 25× | El sábado vende ~21% más que el promedio de lunes a viernes y el domingo cae a menos de la mitad: surtir y atender según el día. |
| Quincenal | 15.1 días | 3.3× | Hay un pico de ventas alrededor del 15–16 y del 30–1: la quincena sí mueve las ventas (≈ +16%). |

Observaciones honestas:

- El pico más alto en periodos cortos (≈ 3.5 días) es el **armónico** del ciclo semanal (una semana no es una onda perfecta), no un ciclo nuevo.
- El ciclo **mensual** no aparece como pico independiente: su energía se mezcla con las temporadas largas (regreso a clases) que se filtraron al quitar la media móvil. Por eso no se reporta.
- Los datos son sintéticos y el efecto de quincena se sembró en el generador; con datos reales de la papelería hay que repetir el análisis.

## 5. Tres recomendaciones para el dueño

1. **Surtir antes de las temporadas fuertes.** En regreso a clases (17 ago–12 sep) se vende 94% más que el resto del año y en quincena 16% más. Comprar cuadernos, colores y mochilas 2–3 semanas antes para no quedarse sin ellos.
2. **Promocionar el domicilio antes del sábado**, con el aviso cerca de las 16:00–17:00, cuando llegan más pedidos a domicilio. El ticket a domicilio es casi igual al de mostrador: crecer ese canal no sacrifica el ticket.
3. **Fomentar la venta cruzada** con paquetes (cuaderno + lápiz + colores) y cotizaciones por lista escolar. El domingo vende solo 45% de lo que vende el sábado: ahí conviene una promoción propia.

## 6. Nube: almacenamiento (tema 2.4)

El E1 pide tener los datos en almacenamiento en nube. Plan para AWS S3 (pendiente de ejecutar por el equipo con su cuenta):

```text
s3://<bucket-del-equipo>/raw/ventas_papeleria_raw.csv      # tal como llegó
s3://<bucket-del-equipo>/clean/ventas_papeleria_clean.csv  # depurado
```

```bash
aws s3 cp data/ventas_papeleria_raw.csv   s3://<bucket>/raw/
aws s3 cp data/ventas_papeleria_clean.csv s3://<bucket>/clean/
```

Convención de nombres: `raw/` y `clean/` (zonas del data lake), un prefijo por zona y archivos con el nombre del dataset. Credenciales siempre en variables de entorno o perfiles de AWS CLI, **nunca en el repositorio** (`.gitignore` ya excluye `.env`, `.aws/` y `*.pem`). En E2 el tablero pasa a leer de `clean/` en la nube.

## 7. Uso de IA generativa (declaración)

Se usó Claude (Anthropic) para escribir el código del generador, la limpieza, las pruebas y el tablero, y para redactar este documento. Los resultados numéricos salen de ejecutar ese código sobre los datos. Los integrantes revisaron el código y deben poder explicar cada decisión (por ejemplo, por qué la FFT usa una media móvil de 61 días o cómo se recuperan los valores faltantes).
