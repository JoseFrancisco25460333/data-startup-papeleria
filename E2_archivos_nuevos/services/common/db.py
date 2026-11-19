"""Base de datos de consultas (PostgreSQL en AWS; SQLite para pruebas locales).

Esquema en infra/aws/schema.sql. La carga de un lote es idempotente: se borran
las filas del mismo batch_id antes de insertarlas, porque SQS entrega "al menos
una vez" y un mensaje puede procesarse dos veces.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd

COLS = ["ticket_id", "fecha", "hora", "canal", "producto", "cantidad", "precio_unitario", "total"]


class BaseSQLite:
    def __init__(self, ruta: str = ":memory:"):
        self.con = sqlite3.connect(ruta)
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS lotes (batch_id TEXT PRIMARY KEY, procesado TEXT,
                filas_entrada INTEGER, filas_salida INTEGER, correcciones INTEGER, estado TEXT);
            CREATE TABLE IF NOT EXISTS ventas (batch_id TEXT, ticket_id INTEGER, fecha TEXT, hora INTEGER,
                canal TEXT, producto TEXT, cantidad INTEGER, precio_unitario REAL, total REAL);
            CREATE INDEX IF NOT EXISTS ix_ventas_fecha ON ventas (fecha);
            CREATE INDEX IF NOT EXISTS ix_ventas_batch ON ventas (batch_id);""")

    def cargar_lote(self, batch_id: str, limpio: pd.DataFrame, rep: dict) -> None:
        f = limpio.copy()
        f["fecha"] = pd.to_datetime(f["fecha"]).dt.strftime("%Y-%m-%d")
        filas = [(batch_id, *r) for r in f[COLS].itertuples(index=False, name=None)]
        with self.con:
            self.con.execute("DELETE FROM ventas WHERE batch_id = ?", (batch_id,))
            self.con.executemany("INSERT INTO ventas VALUES (?,?,?,?,?,?,?,?,?)", filas)
            self.con.execute("INSERT OR REPLACE INTO lotes VALUES (?,?,?,?,?,?)",
                             (batch_id, datetime.now(timezone.utc).isoformat(), rep["registros_entrada"],
                              rep["registros_salida"], rep["total_corregidos"], "ok"))

    def contar(self, tabla: str = "ventas") -> int:
        return self.con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


class BasePostgres:
    """Conexion con psycopg2. Host, usuario y contrasena vienen de variables de
    entorno que en AWS inyecta Secrets Manager; nunca estan en el repositorio."""

    def __init__(self):
        import psycopg2

        self.con = psycopg2.connect(
            host=os.environ["DB_HOST"], dbname=os.getenv("DB_NAME", "papeleria"),
            user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
            sslmode=os.getenv("DB_SSLMODE", "require"))

    def cargar_lote(self, batch_id: str, limpio: pd.DataFrame, rep: dict) -> None:
        from psycopg2.extras import execute_values

        f = limpio.copy()
        f["fecha"] = pd.to_datetime(f["fecha"]).dt.date
        filas = [(batch_id, *r) for r in f[COLS].itertuples(index=False, name=None)]
        with self.con, self.con.cursor() as cur:
            cur.execute("DELETE FROM ventas WHERE batch_id = %s", (batch_id,))
            execute_values(cur, "INSERT INTO ventas (batch_id, ticket_id, fecha, hora, canal, producto, "
                                "cantidad, precio_unitario, total) VALUES %s", filas)
            cur.execute("INSERT INTO lotes (batch_id, filas_entrada, filas_salida, correcciones, estado) "
                        "VALUES (%s,%s,%s,%s,'ok') ON CONFLICT (batch_id) DO UPDATE SET "
                        "procesado = now(), filas_entrada = EXCLUDED.filas_entrada, "
                        "filas_salida = EXCLUDED.filas_salida, correcciones = EXCLUDED.correcciones, estado = 'ok'",
                        (batch_id, rep["registros_entrada"], rep["registros_salida"], rep["total_corregidos"]))


def crear_db():
    if os.getenv("BACKEND", "local") == "aws" and os.getenv("DB_HOST"):
        return BasePostgres()
    return BaseSQLite(os.getenv("SQLITE_PATH", ":memory:"))
