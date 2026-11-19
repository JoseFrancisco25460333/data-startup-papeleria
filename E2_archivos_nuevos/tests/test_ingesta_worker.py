"""Ingesta + cola + worker de punta a punta, con almacen local y cola en memoria."""
import tempfile

import pandas as pd
import pytest

import worker
from common.backends import AlmacenLocal, ColaLocal
from common.db import BaseSQLite
from core import Ingesta, LoteInvalido

FILA = {"ticket_id": 1, "fecha": "2026-10-19", "hora": 10, "canal": "mostrador",
        "producto": "Lapiz HB", "cantidad": 2, "precio_unitario": 6.0, "total": 12.0}


def montar(max_intentos=3):
    almacen, cola, db = AlmacenLocal(tempfile.mkdtemp()), ColaLocal(max_intentos), BaseSQLite()
    return Ingesta(almacen, cola), almacen, cola, db


def csv(filas):
    return pd.DataFrame(filas).to_csv(index=False).encode()


# ---------------------------------------------------------------- validacion
def test_rechaza_columnas_faltantes_y_vacio():
    ing, *_ = montar()
    with pytest.raises(LoteInvalido) as e:
        ing.recibir_csv(b"ticket_id,fecha\n1,2026-10-19\n")
    assert "Faltan columnas" in e.value.mensaje and e.value.codigo == 422
    with pytest.raises(LoteInvalido):
        ing.recibir_registros([])


def test_rechaza_tipos_y_fecha_invalidos():
    ing, *_ = montar()
    malo = dict(FILA, hora=30, fecha="ayer")
    with pytest.raises(LoteInvalido) as e:
        ing.recibir_registros([malo])
    texto = " ".join(e.value.detalle)
    assert "hora" in texto and "fecha" in texto
    with pytest.raises(LoteInvalido):
        ing.recibir_registros([dict(FILA, precio_unitario="abc")])


def test_archivo_muy_grande_da_413():
    ing, *_ = montar()
    with pytest.raises(LoteInvalido) as e:
        ing.recibir_csv(b"x" * (5 * 1024 * 1024 + 1))
    assert e.value.codigo == 413


def test_lote_invalido_no_toca_almacen_ni_cola():
    ing, almacen, cola, _ = montar()
    with pytest.raises(LoteInvalido):
        ing.recibir_registros([dict(FILA, producto=None)])
    assert almacen.listar("raw") == [] and cola.pendientes() == 0


# ------------------------------------------------------------ punta a punta
def test_flujo_completo_raw_cola_worker_clean_y_db():
    ing, almacen, cola, db = montar()
    sucio = [dict(FILA, ticket_id=i, cantidad=c) for i, c in enumerate([2, -3, None, 2], start=1)]
    sucio.append(dict(sucio[0]))                       # duplicado exacto
    r = ing.recibir_csv(csv(sucio))
    assert r["estado"] == "en cola" and cola.pendientes() == 1
    # raw guarda TAL CUAL llego (sin limpiar)
    assert len(pd.read_csv(__import__("io").BytesIO(almacen.get(r["raw"])))) == 5
    assert worker.atender_uno(cola, almacen, db) is True
    assert cola.pendientes() == 0
    clean = almacen.listar("clean")
    assert len(clean) == 1 and clean[0].startswith("clean/ventas/")
    limpio = pd.read_csv(__import__("io").BytesIO(almacen.get(clean[0])))
    assert len(limpio) == 4 and (limpio["cantidad"] > 0).all()
    assert db.contar() == 4 and db.contar("lotes") == 1


def test_worker_idempotente_si_el_mensaje_llega_dos_veces():
    ing, almacen, cola, db = montar()
    r = ing.recibir_csv(csv([FILA]))
    msg = {"batch_id": r["batch_id"], "key": r["raw"]}
    worker.procesar(msg, almacen, db)
    worker.procesar(msg, almacen, db)
    assert db.contar() == 1 and db.contar("lotes") == 1


def test_reintentos_y_cola_de_fallidos():
    ing, almacen, cola, db = montar(max_intentos=3)
    cola.enviar({"batch_id": "malo", "key": "raw/ventas/no-existe.csv"})
    for _ in range(3):
        assert worker.atender_uno(cola, almacen, db) is True   # falla y no borra
    assert cola.fallidos == []
    assert worker.atender_uno(cola, almacen, db) is False      # al 4o recibir pasa a la DLQ
    assert cola.fallidos and cola.fallidos[0]["batch_id"] == "malo"
    assert db.contar() == 0


def test_lote_pequeno_con_cantidad_irrecuperable_no_truena():
    ing, almacen, cola, db = montar()
    fila = dict(FILA, cantidad=None, total=None, producto="Cartulina")
    ing.recibir_csv(csv([fila]))
    assert worker.atender_uno(cola, almacen, db) is True
    assert cola.pendientes() == 0 and db.contar() == 0
