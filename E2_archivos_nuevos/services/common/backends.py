"""Almacenamiento de objetos y cola de mensajes, con dos implementaciones:

- Local (carpeta + cola en memoria): para desarrollar y probar sin cuenta de nube.
- AWS (S3 + SQS): el mismo codigo de la ingesta y del worker corre en la nube.

Las credenciales de AWS NUNCA van en el codigo: boto3 las toma del rol de la
instancia (EC2) o del perfil/variables de entorno de quien desarrolla.
"""
from __future__ import annotations

import json
import os
import uuid
from collections import deque
from pathlib import Path


# ------------------------------------------------------------------ almacenamiento
class AlmacenLocal:
    def __init__(self, raiz: str = "lake_local"):
        self.raiz = Path(raiz)

    def put(self, key: str, data: bytes) -> None:
        ruta = self.raiz / key
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(data)

    def get(self, key: str) -> bytes:
        return (self.raiz / key).read_bytes()

    def listar(self, prefijo: str) -> list[str]:
        base = self.raiz / prefijo
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.raiz)).replace(os.sep, "/")
                      for p in base.rglob("*") if p.is_file())


class AlmacenS3:
    def __init__(self, bucket: str, region: str | None = None):
        import boto3

        self.bucket = bucket
        self.s3 = boto3.client("s3", region_name=region)

    def put(self, key: str, data: bytes) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get(self, key: str) -> bytes:
        return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def listar(self, prefijo: str) -> list[str]:
        claves, token = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefijo}
            if token:
                kw["ContinuationToken"] = token
            r = self.s3.list_objects_v2(**kw)
            claves += [o["Key"] for o in r.get("Contents", []) if not o["Key"].endswith("/")]
            token = r.get("NextContinuationToken")
            if not token:
                return claves


# ------------------------------------------------------------------------- cola
class Mensaje:
    def __init__(self, cuerpo: dict, recibo: str, intentos: int = 1):
        self.cuerpo, self.recibo, self.intentos = cuerpo, recibo, intentos


class ColaLocal:
    """Cola en memoria con la misma semantica que SQS: un mensaje que no se borra
    reaparece (reintento) y tras `max_intentos` pasa a la cola de mensajes fallidos."""

    def __init__(self, max_intentos: int = 3):
        self.max_intentos = max_intentos
        self._cola: deque = deque()
        self._en_vuelo: dict[str, tuple[dict, int]] = {}
        self.fallidos: list[dict] = []  # DLQ

    def enviar(self, cuerpo: dict) -> str:
        id_ = uuid.uuid4().hex
        self._cola.append((id_, cuerpo, 0))
        return id_

    def recibir(self) -> Mensaje | None:
        # los mensajes en vuelo que no se borraron vuelven a la cola (visibility timeout vencido)
        for recibo, (cuerpo, n) in list(self._en_vuelo.items()):
            del self._en_vuelo[recibo]
            if n >= self.max_intentos:
                self.fallidos.append(cuerpo)
            else:
                self._cola.append((recibo, cuerpo, n))
        if not self._cola:
            return None
        id_, cuerpo, n = self._cola.popleft()
        self._en_vuelo[id_] = (cuerpo, n + 1)
        return Mensaje(cuerpo, id_, n + 1)

    def borrar(self, msg: Mensaje) -> None:
        self._en_vuelo.pop(msg.recibo, None)

    def pendientes(self) -> int:
        return len(self._cola) + len(self._en_vuelo)


class ColaSQS:
    """SQS real. Reintentos y cola de fallidos los define la propia cola
    (visibility timeout + redrive policy con maxReceiveCount), no el codigo."""

    def __init__(self, url: str, region: str | None = None, espera: int = 20):
        import boto3

        self.url, self.espera = url, espera
        self.sqs = boto3.client("sqs", region_name=region)

    def enviar(self, cuerpo: dict) -> str:
        return self.sqs.send_message(QueueUrl=self.url, MessageBody=json.dumps(cuerpo))["MessageId"]

    def recibir(self) -> Mensaje | None:
        r = self.sqs.receive_message(QueueUrl=self.url, MaxNumberOfMessages=1,
                                     WaitTimeSeconds=self.espera,
                                     AttributeNames=["ApproximateReceiveCount"])
        for m in r.get("Messages", []):
            return Mensaje(json.loads(m["Body"]), m["ReceiptHandle"],
                           int(m["Attributes"]["ApproximateReceiveCount"]))
        return None

    def borrar(self, msg: Mensaje) -> None:
        self.sqs.delete_message(QueueUrl=self.url, ReceiptHandle=msg.recibo)


def crear_backends():
    """Lee la configuracion del entorno. BACKEND=local (default) o aws."""
    if os.getenv("BACKEND", "local") == "aws":
        region = os.getenv("AWS_REGION")
        return (AlmacenS3(os.environ["BUCKET"], region),
                ColaSQS(os.environ["QUEUE_URL"], region))
    return AlmacenLocal(os.getenv("LAKE_DIR", "lake_local")), ColaLocal()
