"""Worker: consume mensajes de la cola, limpia el lote y lo guarda.

mensaje -> lee raw/ -> limpiar() -> escribe clean/ -> carga en la base de datos -> borra el mensaje

Si algo falla NO se borra el mensaje: la cola lo reentrega (reintento) y, tras
maxReceiveCount intentos, lo manda a la cola de mensajes fallidos (DLQ).
Correr:  python services/worker/worker.py     (BACKEND=local o aws)
"""
from __future__ import annotations

import io
import logging
import os
import sys

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, ".."))
from common.backends import crear_backends  # noqa: E402
from common.db import crear_db  # noqa: E402
from limpieza import limpiar  # noqa: E402

log = logging.getLogger("worker")


def clave_clean(key_raw: str) -> str:
    """raw/ventas/2026-10-19/<lote>.csv -> clean/ventas/2026-10-19/<lote>.csv"""
    if not key_raw.startswith("raw/"):
        raise ValueError(f"clave fuera de raw/: {key_raw}")
    return "clean/" + key_raw[len("raw/"):]


def procesar(cuerpo: dict, almacen, db) -> dict:
    crudo = pd.read_csv(io.BytesIO(almacen.get(cuerpo["key"])))
    limpio, rep = limpiar(crudo)
    almacen.put(clave_clean(cuerpo["key"]), limpio.to_csv(index=False).encode("utf-8"))
    db.cargar_lote(cuerpo["batch_id"], limpio, rep)
    return rep


def atender_uno(cola, almacen, db) -> bool:
    """Atiende un mensaje. Devuelve False si no habia ninguno."""
    msg = cola.recibir()
    if msg is None:
        return False
    try:
        rep = procesar(msg.cuerpo, almacen, db)
    except Exception:  # noqa: BLE001
        log.exception("lote %s fallo (intento %s); se reintentara", msg.cuerpo.get("batch_id"), msg.intentos)
        return True            # sin borrar: la cola lo reentrega o lo manda a la DLQ
    cola.borrar(msg)
    log.info("lote %s listo: %s -> %s filas, %s correcciones", msg.cuerpo["batch_id"],
             rep["registros_entrada"], rep["registros_salida"], rep["total_corregidos"])
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    almacen, cola = crear_backends()
    db = crear_db()
    log.info("worker escuchando...")
    while True:
        atender_uno(cola, almacen, db)
