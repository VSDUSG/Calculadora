"""Configuração do Daikon.

Lê e grava o arquivo config.json na raiz do projeto. Se o arquivo não
existir, ele é criado com valores padrão na primeira execução.
"""
import json
import os
import secrets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Na nuvem, DAIKON_DADOS aponta para o disco persistente (ex.: /dados).
# Sem essa variável, tudo fica na pasta do projeto (modo rede local).
_DADOS = os.environ.get("DAIKON_DADOS", "") or BASE_DIR
CONFIG_PATH = os.path.join(_DADOS, "config.json")
STORAGE_DIR = os.path.join(_DADOS, "storage")
DICOM_DIR = os.path.join(STORAGE_DIR, "dicom")
PNG_DIR = os.path.join(STORAGE_DIR, "png")
PDF_DIR = os.path.join(STORAGE_DIR, "laudos")
DB_PATH = os.path.join(STORAGE_DIR, "daikon.db")

PADRAO = {
    "nome_clinica": "Minha Clínica",
    "subtitulo_clinica": "Ultrassonografia",
    "endereco_clinica": "",
    "telefone_clinica": "",
    "ae_title": "DAIKON",
    "porta_dicom": 11112,
    "porta_web": 8000,
    "senha": "daikon",
}


def carregar() -> dict:
    cfg = dict(PADRAO)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    mudou = False
    if "chave_sessao" not in cfg:
        cfg["chave_sessao"] = secrets.token_hex(32)
        mudou = True
    if "token_conector" not in cfg:
        # senha que o Conector da clínica usa para falar com o site
        cfg["token_conector"] = secrets.token_hex(24)
        mudou = True
    if mudou:
        salvar(cfg)
    return cfg


def salvar(cfg: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def preparar_pastas() -> None:
    for pasta in (STORAGE_DIR, DICOM_DIR, PNG_DIR, PDF_DIR):
        os.makedirs(pasta, exist_ok=True)
