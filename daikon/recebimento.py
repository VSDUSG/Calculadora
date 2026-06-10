"""Processamento de exames DICOM recebidos.

Usado por dois caminhos:
  - servidor DICOM local (modo rede local)
  - upload HTTPS vindo do Conector da clínica (modo internet)
"""
import logging
import os

from . import config, database
from .imagens import gerar_png

log = logging.getLogger("daikon.recebimento")


def _vincular_estudo(ds) -> int:
    """Localiza/cria o estudo no banco e tenta vincular ao agendamento."""
    study_uid = str(ds.StudyInstanceUID)
    estudo = database.um("SELECT * FROM estudos WHERE study_uid = ?", (study_uid,))
    if estudo:
        return estudo["id"]

    accession = str(getattr(ds, "AccessionNumber", "") or "")
    agendamento = None
    if accession:
        agendamento = database.um(
            "SELECT * FROM agendamentos WHERE accession = ?", (accession,))
    if not agendamento:
        agendamento = database.um(
            "SELECT * FROM agendamentos WHERE study_uid = ?", (study_uid,))

    nome = str(getattr(ds, "PatientName", "") or "").replace("^", " ").strip()
    estudo_id = database.executar(
        """INSERT INTO estudos (study_uid, agendamento_id, paciente_nome,
               paciente_id_dicom, accession, descricao, data, hora)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            study_uid,
            agendamento["id"] if agendamento else None,
            nome,
            str(getattr(ds, "PatientID", "") or ""),
            accession,
            str(getattr(ds, "StudyDescription", "") or ""),
            str(getattr(ds, "StudyDate", "") or ""),
            str(getattr(ds, "StudyTime", "") or "")[:6],
        ),
    )
    if agendamento and agendamento["status"] == "agendado":
        database.executar(
            "UPDATE agendamentos SET status = 'realizado' WHERE id = ?",
            (agendamento["id"],))
        log.info("Estudo %s vinculado ao agendamento #%s", study_uid, agendamento["id"])
    return estudo_id


def registrar_dataset(ds) -> bool:
    """Grava uma imagem DICOM (pydicom Dataset com file_meta) no sistema.

    Devolve True se era uma imagem nova, False se era reenvio.
    """
    sop_uid = str(ds.SOPInstanceUID)
    study_uid = str(ds.StudyInstanceUID)

    pasta = os.path.join(config.DICOM_DIR, study_uid)
    os.makedirs(pasta, exist_ok=True)
    caminho_dcm = os.path.join(pasta, f"{sop_uid}.dcm")
    ds.save_as(caminho_dcm, enforce_file_format=True)

    estudo_id = _vincular_estudo(ds)

    if database.um("SELECT id FROM imagens WHERE sop_uid = ?", (sop_uid,)):
        return False  # reenvio da mesma imagem

    caminho_png, frames = gerar_png(caminho_dcm, sop_uid)
    numero = int(getattr(ds, "InstanceNumber", 0) or 0)
    database.executar(
        """INSERT INTO imagens (estudo_id, sop_uid, arquivo_dicom,
               arquivo_png, numero, frames)
           VALUES (?,?,?,?,?,?)""",
        (estudo_id, sop_uid, caminho_dcm, caminho_png or "", numero, frames),
    )
    log.info("Imagem registrada: estudo=%s instancia=%s", study_uid, numero)
    return True
