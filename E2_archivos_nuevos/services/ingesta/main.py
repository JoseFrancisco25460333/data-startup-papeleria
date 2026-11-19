"""API de ingesta (FastAPI). Correr:  uvicorn main:app --host 0.0.0.0 --port 8000
Documentacion OpenAPI automatica en /docs (Swagger) y /openapi.json.

BACKEND=local  -> carpeta lake_local/ + cola en memoria (desarrollo)
BACKEND=aws    -> S3 (BUCKET) + SQS (QUEUE_URL); credenciales por el rol de la instancia
"""
from __future__ import annotations

import os
import sys

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.backends import crear_backends  # noqa: E402
from core import ErrorDeInfraestructura, Ingesta, LoteInvalido  # noqa: E402

app = FastAPI(
    title="Ingesta · Data Startup Papelería",
    version="0.2.0",
    description="Recibe ventas por JSON o CSV, las guarda tal como llegan en `raw/` y las "
                "manda a una cola para que el worker las limpie. Responde 202 de inmediato.",
)
_almacen, _cola = crear_backends()
servicio = Ingesta(_almacen, _cola)


class Registro(BaseModel):
    ticket_id: int
    fecha: str = Field(examples=["2026-10-19"], description="AAAA-MM-DD")
    hora: int = Field(ge=0, le=23)
    canal: str = Field(examples=["mostrador"], description="mostrador, domicilio o web")
    producto: str = Field(min_length=1)
    cantidad: float | None = None
    precio_unitario: float
    total: float | None = None


class Lote(BaseModel):
    registros: list[Registro] = Field(min_length=1, max_length=50_000)


class Aceptado(BaseModel):
    batch_id: str
    filas: int
    estado: str
    raw: str


def _responder(fn, *args):
    try:
        return fn(*args)
    except LoteInvalido as e:
        return JSONResponse(status_code=e.codigo, content={"error": e.mensaje, "detalle": e.detalle})
    except ErrorDeInfraestructura:
        raise HTTPException(status_code=503, detail="Servicio temporalmente no disponible; reintenta") from None


@app.get("/salud", tags=["operacion"])
def salud():
    """Para el balanceador o el monitoreo."""
    return {"estado": "ok"}


@app.post("/ventas", status_code=202, response_model=Aceptado, tags=["ingesta"],
          responses={422: {"description": "Estructura invalida"}, 503: {"description": "Cola o almacen caidos"}})
def ingestar_json(lote: Lote):
    """Registra un lote de ventas en JSON."""
    return _responder(servicio.recibir_registros, [r.model_dump() for r in lote.registros])


@app.post("/ventas/csv", status_code=202, response_model=Aceptado, tags=["ingesta"],
          responses={400: {"description": "CSV ilegible"}, 413: {"description": "Archivo demasiado grande"},
                     422: {"description": "Estructura invalida"}, 503: {"description": "Cola o almacen caidos"}})
async def ingestar_csv(archivo: UploadFile = File(..., description="CSV con las columnas de ventas")):
    """Sube un CSV de ventas (maximo 5 MB)."""
    contenido = await archivo.read(5 * 1024 * 1024 + 1)
    return _responder(servicio.recibir_csv, contenido)
