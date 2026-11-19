"""Demo sin nube: CSV -> ingesta -> raw/ -> cola -> worker -> clean/ -> base de datos.

Todo corre en un solo proceso (la cola local vive en memoria). Uso desde la raiz:
    python data/generar_lote_demo.py && python services/common/demo_local.py
"""
import os
import sys
import time

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
for sub in ["..", "../ingesta", "../worker"]:
    sys.path.insert(0, os.path.join(AQUI, sub))
import worker  # noqa: E402
from common.backends import AlmacenLocal, ColaLocal  # noqa: E402
from common.db import BaseSQLite  # noqa: E402
from core import Ingesta  # noqa: E402

almacen, cola, db = AlmacenLocal("lake_local"), ColaLocal(), BaseSQLite()
t0 = time.time()
r = Ingesta(almacen, cola).recibir_csv(open("data/lote_demo.csv", "rb").read())
print("1) ingesta respondio 202:", r)
print("2) mensajes en cola:", cola.pendientes())
worker.atender_uno(cola, almacen, db)
print("3) worker termino. clean/:", almacen.listar("clean"))
print(f"4) filas en la base de datos: {db.contar():,} (entraron {r['filas']:,}; el resto eran duplicados)")
print(f"   tiempo total: {time.time() - t0:.2f} s")
