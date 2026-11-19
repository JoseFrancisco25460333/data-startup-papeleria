"""Pruebas del API de ingesta con TestClient (requiere fastapi y httpx)."""
import io

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

cliente = TestClient(main.app)
CSV = ("ticket_id,fecha,hora,canal,producto,cantidad,precio_unitario,total\n"
       "1,2026-10-19,10,mostrador,Lapiz HB,2,6.0,12.0\n")


def test_salud_y_openapi():
    assert cliente.get("/salud").json() == {"estado": "ok"}
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert "/ventas" in rutas and "/ventas/csv" in rutas


def test_csv_valido_da_202():
    r = cliente.post("/ventas/csv", files={"archivo": ("v.csv", io.BytesIO(CSV.encode()), "text/csv")})
    assert r.status_code == 202 and r.json()["estado"] == "en cola"


def test_csv_invalido_da_422_con_detalle():
    r = cliente.post("/ventas/csv", files={"archivo": ("v.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")})
    assert r.status_code == 422 and r.json()["detalle"]


def test_json_valido_y_hora_fuera_de_rango():
    ok = {"registros": [{"ticket_id": 1, "fecha": "2026-10-19", "hora": 10, "canal": "web",
                         "producto": "Lapiz HB", "cantidad": 2, "precio_unitario": 6.0, "total": 12.0}]}
    assert cliente.post("/ventas", json=ok).status_code == 202
    ok["registros"][0]["hora"] = 30
    assert cliente.post("/ventas", json=ok).status_code == 422
