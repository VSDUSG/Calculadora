"""Servidor DICOM do Daikon (roda em segundo plano junto com o site).

Serviços oferecidos ao aparelho de ultrassom:
  - C-ECHO  (Verification)        : teste de conexão ("ping DICOM")
  - C-STORE (Storage SCP)         : recebe as imagens do exame em tempo real
  - C-FIND  (Modality Worklist)   : envia a lista de pacientes agendados
"""
import logging
import threading

from pydicom.dataset import Dataset
from pydicom.uid import generate_uid
from pynetdicom import AE, evt, AllStoragePresentationContexts, ALL_TRANSFER_SYNTAXES
from pynetdicom.sop_class import ModalityWorklistInformationFind, Verification

from . import config, database
from .recebimento import registrar_dataset

log = logging.getLogger("daikon.dicom")

# Raiz de UID do projeto (prefixo público do pydicom) para gerar StudyInstanceUID
UID_RAIZ = "1.2.826.0.1.3680043.8.498."


def novo_study_uid() -> str:
    return generate_uid(prefix=UID_RAIZ)


# ---------------------------------------------------------------- Worklist

def _agendamento_para_dataset(ag: dict, cfg: dict) -> Dataset:
    """Converte um agendamento do banco em um item de resposta da Worklist."""
    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 192"  # UTF-8

    nome = (ag.get("paciente_nome") or "").strip()
    # DICOM usa '^' entre sobrenome e nome: "SILVA^JOAO"
    partes = nome.split()
    if len(partes) > 1:
        ds.PatientName = f"{partes[-1]}^{' '.join(partes[:-1])}"
    else:
        ds.PatientName = nome
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
    sps.ScheduledStationAETitle = cfg["ae_title"]
    sps.ScheduledProcedureStepStartDate = ag["data"].replace("-", "")
    sps.ScheduledProcedureStepStartTime = ag["hora"].replace(":", "") + "00"
    sps.ScheduledPerformingPhysicianName = ag.get("medico_nome") or ""
    sps.ScheduledProcedureStepDescription = ag.get("procedimento_nome") or ""
    sps.ScheduledProcedureStepID = f"SPS{ag['id']:06d}"
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


def _consultar_worklist(identifier) -> list:
    """Busca agendamentos que casam com a consulta do aparelho."""
    data_filtro = None
    try:
        sps_query = identifier.ScheduledProcedureStepSequence[0]
        bruto = getattr(sps_query, "ScheduledProcedureStepStartDate", "") or ""
        bruto = str(bruto).strip()
        if bruto and "-" not in bruto and len(bruto) == 8:
            data_filtro = f"{bruto[0:4]}-{bruto[4:6]}-{bruto[6:8]}"
        elif "-" in bruto:  # intervalo "YYYYMMDD-YYYYMMDD": deixamos passar tudo
            data_filtro = None
    except (AttributeError, IndexError):
        pass

    sql = """
        SELECT a.*, p.nome AS paciente_nome, p.nascimento, p.sexo,
               pr.nome AS procedimento_nome, m.nome AS medico_nome
        FROM agendamentos a
        JOIN pacientes p ON p.id = a.paciente_id
        LEFT JOIN procedimentos pr ON pr.id = a.procedimento_id
        LEFT JOIN medicos m ON m.id = a.medico_id
        WHERE a.status = 'agendado'
    """
    params = []
    if data_filtro:
        sql += " AND a.data = ?"
        params.append(data_filtro)
    sql += " ORDER BY a.data, a.hora"
    return database.query(sql, params)


def handle_find(event):
    cfg = config.carregar()
    try:
        agendamentos = _consultar_worklist(event.identifier)
    except Exception:
        log.exception("Erro consultando a worklist")
        yield 0xC001, None
        return
    log.info("Worklist solicitada: %d agendamento(s) enviados", len(agendamentos))
    for ag in agendamentos:
        if event.is_cancelled:
            yield 0xFE00, None
            return
        yield 0xFF00, _agendamento_para_dataset(ag, cfg)


# ---------------------------------------------------------------- C-STORE

def handle_store(event):
    try:
        ds = event.dataset
        ds.file_meta = event.file_meta
        registrar_dataset(ds)
        return 0x0000
    except Exception:
        log.exception("Erro ao receber imagem DICOM")
        return 0xC210


def handle_echo(event):
    log.info("C-ECHO recebido de %s", event.assoc.requestor.ae_title)
    return 0x0000


# ---------------------------------------------------------------- Servidor

def iniciar_em_thread() -> AE:
    """Sobe o servidor DICOM numa thread em segundo plano."""
    cfg = config.carregar()
    ae = AE(ae_title=cfg["ae_title"])
    ae.add_supported_context(Verification, ALL_TRANSFER_SYNTAXES)
    ae.add_supported_context(ModalityWorklistInformationFind)
    for contexto in AllStoragePresentationContexts:
        ae.add_supported_context(contexto.abstract_syntax, ALL_TRANSFER_SYNTAXES)

    handlers = [
        (evt.EVT_C_ECHO, handle_echo),
        (evt.EVT_C_STORE, handle_store),
        (evt.EVT_C_FIND, handle_find),
    ]

    def _rodar():
        log.info("Servidor DICOM '%s' escutando na porta %s",
                 cfg["ae_title"], cfg["porta_dicom"])
        ae.start_server(("0.0.0.0", cfg["porta_dicom"]),
                        evt_handlers=handlers, block=True)

    threading.Thread(target=_rodar, daemon=True, name="dicom-server").start()
    return ae
