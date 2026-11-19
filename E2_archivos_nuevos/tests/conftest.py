"""Rutas para que las pruebas importen los modulos de services/."""
import os
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
for sub in ["services", "services/ingesta", "services/worker", "services/modelos", "services/tablero"]:
    sys.path.insert(0, os.path.join(RAIZ, sub))
