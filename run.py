#!/usr/bin/env python3
"""Inicia o Daikon: servidor web + servidor DICOM, tudo junto.

Uso:  python3 run.py
Depois abra http://localhost:8000 (ou o IP do computador) no navegador.

Na nuvem (Render, Railway etc.) a plataforma define a variável PORT e
o DICOM local fica desligado com DAIKON_NUVEM=1 — quem fala com o
ultrassom lá na clínica é o conector_clinica.py.
"""
import logging
import os

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

    nuvem = os.environ.get("DAIKON_NUVEM", "") == "1"
    if not nuvem:
        dicom_server.iniciar_em_thread()

    porta_web = int(os.environ.get("PORT", cfg["porta_web"]))

    print()
    print("=" * 56)
    print("  Daikon iniciado!")
    print(f"  Site/aplicativo : http://localhost:{porta_web}")
    if nuvem:
        print("  Modo nuvem      : DICOM desligado aqui (use o Conector)")
    else:
        print(f"  Servidor DICOM  : AE Title '{cfg['ae_title']}'  porta {cfg['porta_dicom']}")
    print(f"  Senha inicial   : {cfg['senha']}")
    print("=" * 56)
    print()

    uvicorn.run(app, host="0.0.0.0", port=porta_web, log_level="warning")
