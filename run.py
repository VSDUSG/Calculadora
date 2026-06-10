#!/usr/bin/env python3
"""Inicia o Daikon: servidor web + servidor DICOM, tudo junto.

Uso:  python3 run.py
Depois abra http://localhost:8000 (ou o IP do computador) no navegador.
"""
import logging

import uvicorn

from daikon import config, database, dicom_server
from daikon.web import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    cfg = config.carregar()
    config.preparar_pastas()
    database.iniciar()
    dicom_server.iniciar_em_thread()

    print()
    print("=" * 56)
    print("  Daikon iniciado!")
    print(f"  Site/aplicativo : http://localhost:{cfg['porta_web']}")
    print(f"  Servidor DICOM  : AE Title '{cfg['ae_title']}'  porta {cfg['porta_dicom']}")
    print(f"  Senha inicial   : {cfg['senha']}")
    print("=" * 56)
    print()

    uvicorn.run(app, host="0.0.0.0", port=cfg["porta_web"], log_level="warning")
