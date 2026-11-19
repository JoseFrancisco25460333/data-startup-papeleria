"""Carga de datos del tablero.

DATA_SOURCE=local (default): lee DATA_PATH, un CSV en tu computadora (solo desarrollo).
DATA_SOURCE=s3: lee TODOS los CSV de la zona clean/ del data lake (los que deja el
worker mas el historico). Las credenciales de AWS no estan en el codigo: boto3 las
toma del perfil/variables de entorno de quien corre el tablero o del rol de la maquina.
"""
from __future__ import annotations

import io
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.backends import AlmacenS3  # noqa: E402


def cargar_ventas(path_local: str = "data/ventas_papeleria_clean.csv") -> pd.DataFrame:
    if os.getenv("DATA_SOURCE", "local") == "s3":
        almacen = AlmacenS3(os.environ["BUCKET"], os.getenv("AWS_REGION"))
        claves = [k for k in almacen.listar("clean/") if k.endswith(".csv")]
        if not claves:
            raise RuntimeError("No hay archivos en clean/ del bucket")
        df = pd.concat([pd.read_csv(io.BytesIO(almacen.get(k))) for k in claves], ignore_index=True)
        return df.drop_duplicates().reset_index(drop=True)
    return pd.read_csv(os.getenv("DATA_PATH", path_local))


def origen() -> str:
    if os.getenv("DATA_SOURCE", "local") == "s3":
        return f"s3://{os.environ['BUCKET']}/clean/"
    return os.getenv("DATA_PATH", "data/ventas_papeleria_clean.csv")
