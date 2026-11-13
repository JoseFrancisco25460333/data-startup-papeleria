# E0 · Propuesta — Data Startup para papelerías

**Proyecto Integrador DATA STARTUP** · Cómputo en la Nube (IAD-2408) × Analítica de Datos (IAD-2403)
**Proveedor de nube:** AWS (Free Tier / AWS Academy) · **Repositorio:**: https://github.com/JoseFrancisco25460333/data-startup-papeleria

---

## 1. Problema y cliente

**Cliente:** una papelería de barrio con servicio de entrega a domicilio de material de papelería (cuadernos, colores, hojas, impresiones, mochilas) y, próximamente, ventas en línea.

**Qué le duele.** La papelería decide a ojo cuánto comprar y cuándo, y su demanda es muy estacional: el regreso a clases (agosto–septiembre y enero), la quincena y el fin de semana mueven las ventas de forma brusca. Si compra de menos, pierde la venta de temporada; si compra de más, se queda con inventario parado. Además, quiere hacer crecer el servicio a domicilio, pero hoy lo promociona sin saber **a quién, cuándo ni qué producto** empujar, y cotiza listas escolares a mano.

**Qué número le vamos a dar.** Cuántas unidades de cada producto va a vender las próximas 1 a 4 semanas (con intervalo de confianza) y qué productos están en riesgo de agotarse en temporada.

**Propuesta de valor.** Una plataforma en la nube que toma las ventas de la papelería, las limpia, las muestra en un tablero que el dueño entiende en 30 segundos y pronostica la demanda. Ese pronóstico alimenta dos herramientas que la papelería pidió:

- un **agente promotor de IA** que sugiere qué promocionar del servicio a domicilio y cuándo, según el pronóstico y los ciclos de venta;
- un **cotizador** de listas escolares y pedidos, con los productos y precios del catálogo.

> Alcance: lo que se evalúa en el proyecto es el *motor de datos* (ingesta, almacén, tablero, pronóstico, blindaje). El agente promotor, el cotizador y la tienda en línea son **consumidores** del servicio de modelos y se construyen después, solo si hay tiempo; no sustituyen ningún entregable.

## 2. Lean Canvas

| Bloque | Contenido |
|---|---|
| **Problema** | 1) Compra de inventario a ojo en temporadas de demanda brusca. 2) Promoción del servicio a domicilio sin datos. 3) Cotizaciones manuales y lentas. |
| **Segmento de clientes** | Papelerías independientes de barrio con 1 sucursal, que ya venden por mostrador y quieren crecer en domicilio/web. Cliente inicial: _PCO PAPELERIAS_. |
| **Propuesta de valor** | "Sabe cuánto surtir y qué promocionar, antes de la temporada." Tablero simple + pronóstico semanal + agente promotor. |
| **Solución** | Ingesta de ventas por API/CSV → data lake (raw/clean) → tablero Streamlit → API de pronóstico (ARIMA) → agente promotor y cotizador. |
| **Canales** | Visita directa a papelerías, WhatsApp, recomendación entre dueños, demo en el Demo Day. |
| **Fuentes de ingreso** | Hipótesis a validar: suscripción mensual (SaaS) por papelería, p. ej. **$499 MXN/mes**; módulo de agente promotor como complemento. |
| **Estructura de costos** | Nube (cómputo, almacenamiento, cola, base de datos), dominio, tiempo de soporte. Costo por cliente a calcular en E5 con la calculadora oficial de AWS. |
| **Métricas clave** | Papelerías activas, ahorro en merma/agotados, % de ventas por domicilio, precisión del pronóstico (RMSE/MAPE vs. modelo ingenuo). |
| **Ventaja injusta** | Modelos entrenados con la estacionalidad escolar mexicana (regreso a clases, quincena) y un agente que traduce el pronóstico en acciones concretas para el dueño. |



## 3. Inventario de datos

| Campo | Detalle |
|---|---|
| **Fuente** | Datos **sintéticos** generados con `data/generar_ventas.py` (semilla 2026), adaptados del generador del kit de arranque a una papelería. Si la papelería aliada entrega su historial, se sustituyen y se anonimizan (sin nombres, teléfonos ni direcciones). |
| **Periodo** | 1 ene 2025 – 18 oct 2026 (657 días diarios, ~21 meses) |
| **Volumen** | 67,719 registros crudos (32,397 tickets) → 67,684 tras limpieza |
| **Columnas** | `ticket_id`, `fecha`, `hora`, `canal` (mostrador / domicilio / web), `producto`, `cantidad`, `precio_unitario`, `total` |
| **Catálogo** | 14 productos (cuadernos, lápices, plumas, colores, hojas, folders, cartulina, impresiones, mochilas, calculadoras) |
| **Método de simulación** | Tendencia de crecimiento + ciclo semanal + efecto quincena + regreso a clases + vacaciones de diciembre + crecimiento de domicilio y web; con errores sembrados a propósito (duplicados, faltantes, negativos, atípicos, nombres y fechas con mal formato, totales incoherentes). |

Cumple el mínimo de 12 meses diarios y 5,000 registros.

## 4. Arranque técnico

- [ ] Cuenta de AWS creada, con usuarios individuales por integrante (sin operar con root) y MFA en la cuenta raíz
- [ ] **Alerta de presupuesto en $0** activa (AWS Budgets) — _adjuntar captura en `docs/img/budget-alert.png`_
- [ ] Repositorio de GitHub con ambos integrantes y commits de los dos
- [x] Estructura inicial del repositorio (carpetas `docs/`, `data/sample/`, `services/`, `tests/`)
- [x] Generador de datos y módulo de limpieza con pruebas

## 5. Costos preliminares y modelo de negocio

Capa gratuita de AWS durante el desarrollo ($0 MXN). El análisis de costo por cliente (1, 10 y 100 papelerías) se hará en E5 con AWS Pricing Calculator; la hipótesis de precio de $499 MXN/mes se valida con el dueño en la entrevista (pregunta 5).

## 6. Uso de IA generativa (declaración)

Se usó Claude (Anthropic) como asistente para estructurar esta propuesta, adaptar el generador sintético a una papelería, escribir el módulo de limpieza, las pruebas y el código del tablero. Los integrantes revisaron y deben poder explicar cada decisión en la defensa.
