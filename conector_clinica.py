#!/usr/bin/env python3
"""Conector da Clínica — liga o seu ultrassom ao site Daikon na internet.

Roda no computador da clínica (mesma rede do aparelho de ultrassom) e:
  1. Entrega a WORKLIST ao ultrassom (busca os agendamentos no site)
  2. Recebe as IMAGENS do ultrassom e envia ao site por HTTPS
  3. Guarda as imagens numa fila se a internet cair e reenvia sozinho

Uso:  python conector_clinica.py
Na primeira execução ele pergunta o endereço do site e o token
(que aparece na tela "Ajustes" do Daikon) e grava em conector.json.

Precisa apenas de:  pip install pydicom pynetdicom requests
"""
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime

import requests
from pydicom import dcmread
from pydicom.dataset import Dataset
from pynetdicom import AE, evt, AllStoragePresentationContexts, ALL_TRANSFER_SYNTAXES
from pynetdicom.sop_class import ModalityWorklistInformationFind, Verification

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("conector")

PASTA = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(PASTA, "conector.json")
FILA = os.path.join(PASTA, "fila_envio")
CACHE_WORKLIST = os.path.join(PASTA, "worklist_cache.json")


# ------------------------------------------------------------- configuração

def carregar_config() -> dict:
    if os.path.exists(CONFIG):
        with open(CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    print()
    print("=== Primeira execução do Conector — vamos configurar ===")
    print("(esses dados aparecem na tela 'Ajustes' do site Daikon)")
    url = input("Endereço do site (ex.: https://meudaikon.onrender.com): ").strip().rstrip("/")
    token = input("Token do conector: ").strip()
    cfg = {"url_site": url, "token": token, "ae_title": "DAIKON", "porta_dicom": 11112}
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("Configuração salva em conector.json\n")
    return cfg


CFG = carregar_config()


def _cabecalhos() -> dict:
    return {"X-Daikon-Token": CFG["token"]}


# ----------------------------------------------------------------- worklist

def baixar_worklist() -> list:
    """Busca os agendamentos no site; se a internet cair, usa o último cache."""
    try:
        r = requests.get(f"{CFG['url_site']}/api/conector/worklist",
                         headers=_cabecalhos(), timeout=15)
        r.raise_for_status()
        lista = r.json()
        with open(CACHE_WORKLIST, "w", encoding="utf-8") as f:
            json.dump(lista, f)
        return lista
    except Exception as exc:
        log.warning("Site fora de alcance (%s) — usando worklist em cache", exc)
        if os.path.exists(CACHE_WORKLIST):
            with open(CACHE_WORKLIST, "r", encoding="utf-8") as f:
                return json.load(f)
        return []


def _item_worklist(ag: dict) -> Dataset:
    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 192"
    nome = (ag.get("paciente_nome") or "").strip()
    partes = nome.split()
    ds.PatientName = (f"{partes[-1]}^{' '.join(partes[:-1])}"
                      if len(partes) > 1 else nome)
    ds.PatientID = f"PAC{ag['paciente_id']:06d}"
    ds.PatientBirthDate = (ag.get("nascimento") or "").replace("-", "")
    ds.PatientSex = ag.get("sexo") or "O"
    ds.AccessionNumber = ag["accession"]
    ds.StudyInstanceUID = ag["study_uid"]
    ds.RequestedProcedureID = f"RP{ag['id']:06d}"
    ds.RequestedProcedureDescription = ag.get("procedimento_nome") or ""
    ds.ReferringPhysicianName = ag.get("medico_nome") or ""
    sps = Dataset()
    sps.Modality = "US"
    sps.ScheduledStationAETitle = CFG["ae_title"]
    sps.ScheduledProcedureStepStartDate = ag["data"].replace("-", "")
    sps.ScheduledProcedureStepStartTime = ag["hora"].replace(":", "") + "00"
    sps.ScheduledPerformingPhysicianName = ag.get("medico_nome") or ""
    sps.ScheduledProcedureStepDescription = ag.get("procedimento_nome") or ""
    sps.ScheduledProcedureStepID = f"SPS{ag['id']:06d}"
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


def handle_find(event):
    agendamentos = baixar_worklist()

    # Respeita datas exatas e intervalos DICOM (inclusive os abertos).
    try:
        sps = event.identifier.ScheduledProcedureStepSequence[0]
        bruto = str(getattr(sps, "ScheduledProcedureStepStartDate", "") or "").strip()
        partes = bruto.split("-") if bruto else []
        if len(partes) > 2 or any(p and len(p) != 8 for p in partes):
            raise ValueError(f"Data MWL inválida: {bruto!r}")

        def para_iso(data):
            return (datetime.strptime(data, "%Y%m%d").date().isoformat()
                    if data else None)

        if len(partes) == 1:
            inicio = fim = para_iso(partes[0])
        elif len(partes) == 2:
            inicio, fim = para_iso(partes[0]), para_iso(partes[1])
            if inicio and fim and inicio > fim:
                raise ValueError(f"Intervalo MWL invertido: {bruto!r}")
        else:
            inicio = fim = None
    except (AttributeError, IndexError):
        inicio = fim = None
    except ValueError as exc:
        log.warning("Consulta MWL recusada: %s", exc)
        agendamentos = []
        inicio = fim = None
    if inicio:
        agendamentos = [a for a in agendamentos if a["data"] >= inicio]
    if fim:
        agendamentos = [a for a in agendamentos if a["data"] <= fim]

    log.info("Worklist pedida pelo ultrassom: %d paciente(s)", len(agendamentos))
    for ag in agendamentos:
        if event.is_cancelled:
            yield 0xFE00, None
            return
        yield 0xFF00, _item_worklist(ag)


# ------------------------------------------------------------------ imagens

def enviar_arquivo(caminho: str) -> bool:
    try:
        with open(caminho, "rb") as f:
            r = requests.post(f"{CFG['url_site']}/api/conector/imagem",
                              headers=_cabecalhos(),
                              files={"arquivo": (os.path.basename(caminho), f,
                                                 "application/dicom")},
                              timeout=60)
        r.raise_for_status()
        return True
    except Exception as exc:
        log.warning("Falha ao enviar %s: %s", os.path.basename(caminho), exc)
        return False


def handle_store(event):
    try:
        ds = event.dataset
        ds.file_meta = event.file_meta
        os.makedirs(FILA, exist_ok=True)
        caminho = os.path.join(FILA, f"{ds.SOPInstanceUID}.dcm")
        ds.save_as(caminho, enforce_file_format=True)
        log.info("Imagem recebida do ultrassom: %s", ds.SOPInstanceUID)
        if enviar_arquivo(caminho):
            os.remove(caminho)
            log.info("Imagem enviada ao site ✔")
        else:
            log.info("Sem internet agora — imagem guardada na fila")
        return 0x0000
    except Exception:
        log.exception("Erro ao receber imagem")
        return 0xC210


def reenviar_fila():
    """A cada 30 s tenta reenviar imagens que ficaram presas sem internet."""
    while True:
        time.sleep(30)
        if not os.path.isdir(FILA):
            continue
        for nome in sorted(os.listdir(FILA)):
            caminho = os.path.join(FILA, nome)
            if nome.endswith(".dcm") and enviar_arquivo(caminho):
                os.remove(caminho)
                log.info("Imagem da fila enviada ✔ (%s)", nome)


def handle_echo(event):
    log.info("Teste de conexão (C-ECHO) do aparelho: ok")
    return 0x0000


# ----------------------------------------------------------------- programa

def main():
    try:
        r = requests.get(f"{CFG['url_site']}/api/conector/ping",
                         headers=_cabecalhos(), timeout=15)
        r.raise_for_status()
        print(f"✔ Conectado ao site: {CFG['url_site']}")
    except Exception as exc:
        print(f"⚠ Não consegui falar com o site agora ({exc}).")
        print("  O conector vai continuar tentando sozinho.")

    threading.Thread(target=reenviar_fila, daemon=True).start()

    ae = AE(ae_title=CFG["ae_title"])
    ae.add_supported_context(Verification, ALL_TRANSFER_SYNTAXES)
    ae.add_supported_context(ModalityWorklistInformationFind)
    for ctx in AllStoragePresentationContexts:
        ae.add_supported_context(ctx.abstract_syntax, ALL_TRANSFER_SYNTAXES)

    print(f"✔ Conector no ar — AE Title '{CFG['ae_title']}', porta {CFG['porta_dicom']}")
    print("  Configure o ultrassom (Storage e Worklist) com o IP deste computador.")
    print("  Deixe esta janela aberta. Para sair: Ctrl+C")
    ae.start_server(("0.0.0.0", CFG["porta_dicom"]), block=True, evt_handlers=[
        (evt.EVT_C_ECHO, handle_echo),
        (evt.EVT_C_STORE, handle_store),
        (evt.EVT_C_FIND, handle_find),
    ])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nConector encerrado.")
        sys.exit(0)
