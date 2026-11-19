"""Logica de la ingesta, sin depender de FastAPI (asi se prueba sin levantar el servidor).

Responsabilidad de la ingesta: validar la ESTRUCTURA del lote, guardarlo tal como
llego en raw/ y avisar por la cola. La limpieza de valores (negativos, atipicos,
duplicados...) es trabajo del worker; el rechazo de registros imposibles llega en E4.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import pandas as pd

COLUMNAS = ["ticket_id", "fecha", "hora", "canal", "producto", "cantidad", "precio_unitario", "total"]
REQUERIDAS = ["ticket_id", "fecha", "hora", "canal", "producto", "precio_unitario"]
MAX_BYTES = 5 * 1024 * 1024   # un CSV de mas de 5 MB se rechaza (413)
MAX_FILAS = 50_000
PREFIJO_RAW = "raw/ventas"


class LoteInvalido(Exception):
    """El lote no cumple la estructura. `detalle` lista los problemas (maximo 10)."""

    def __init__(self, mensaje: str, detalle: list[str] | None = None, codigo: int = 422):
        super().__init__(mensaje)
        self.mensaje, self.detalle, self.codigo = mensaje, detalle or [], codigo


class ErrorDeInfraestructura(Exception):
    """Fallo al hablar con el almacen o la cola (se responde 503)."""


def validar(df: pd.DataFrame) -> None:
    """Estructura: columnas, campos obligatorios, tipos parseables. Todo o nada."""
    if df.empty:
        raise LoteInvalido("El lote no trae registros")
    if len(df) > MAX_FILAS:
        raise LoteInvalido(f"El lote tiene {len(df):,} filas; el maximo es {MAX_FILAS:,}", codigo=413)
    faltan = [c for c in REQUERIDAS if c not in df.columns]
    if faltan:
        raise LoteInvalido("Faltan columnas obligatorias", [f"columna '{c}'" for c in faltan])
    problemas: list[str] = []
    for c in REQUERIDAS:
        n = int(df[c].isna().sum())
        if n:
            problemas.append(f"'{c}' vacio en {n} fila(s)")
    for c in ["ticket_id", "hora", "precio_unitario"] + [c for c in ("cantidad", "total") if c in df]:
        malos = pd.to_numeric(df[c], errors="coerce").isna() & df[c].notna()
        if malos.any():
            problemas.append(f"'{c}' no es numerico en la fila {int(malos.idxmax()) + 2}")
    horas = pd.to_numeric(df["hora"], errors="coerce")
    if ((horas < 0) | (horas > 23)).any():
        problemas.append("'hora' fuera de 0-23")
    fechas_ok = (pd.to_datetime(df["fecha"].astype(str).str.strip(), format="%Y-%m-%d", errors="coerce").notna()
                 | pd.to_datetime(df["fecha"].astype(str).str.strip(), format="%d/%m/%Y", errors="coerce").notna())
    if (~fechas_ok).any():
        problemas.append(f"'fecha' no reconocida en la fila {int((~fechas_ok).idxmax()) + 2} (usa AAAA-MM-DD)")
    if problemas:
        raise LoteInvalido("El lote tiene errores de estructura", problemas[:10])


class Ingesta:
    def __init__(self, almacen, cola):
        self.almacen, self.cola = almacen, cola

    def _publicar(self, df: pd.DataFrame, origen: str) -> dict:
        validar(df)
        for c in COLUMNAS:               # columnas opcionales ausentes quedan vacias
            if c not in df.columns:
                df[c] = pd.NA
        ahora = datetime.now(timezone.utc)
        batch_id = f"{ahora:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
        key = f"{PREFIJO_RAW}/{ahora:%Y-%m-%d}/{batch_id}.csv"
        try:
            self.almacen.put(key, df[COLUMNAS].to_csv(index=False).encode("utf-8"))   # 1) raw tal cual
            self.cola.enviar({"batch_id": batch_id, "key": key, "filas": len(df), "origen": origen,
                              "recibido": ahora.isoformat()})                          # 2) aviso al worker
        except Exception as e:  # noqa: BLE001
            raise ErrorDeInfraestructura(str(e)) from e
        return {"batch_id": batch_id, "filas": len(df), "estado": "en cola", "raw": key}

    def recibir_registros(self, registros: list[dict]) -> dict:
        return self._publicar(pd.DataFrame(registros), "json")

    def recibir_csv(self, contenido: bytes) -> dict:
        if len(contenido) > MAX_BYTES:
            raise LoteInvalido(f"El archivo pesa mas de {MAX_BYTES // 1024 // 1024} MB", codigo=413)
        try:
            df = pd.read_csv(io.BytesIO(contenido), dtype=str, keep_default_na=True)
        except Exception as e:  # noqa: BLE001
            raise LoteInvalido("No se pudo leer el CSV", [str(e)[:200]], codigo=400) from e
        return self._publicar(df, "csv")
