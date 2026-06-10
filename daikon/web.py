"""Aplicação web do Daikon (FastAPI): API + interface web/celular (PWA)."""
import hashlib
import hmac
import logging
import os
import secrets
import time
import uuid

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, database, pdf_laudo
from .dicom_server import novo_study_uid

log = logging.getLogger("daikon.web")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="Daikon", docs_url=None, redoc_url=None)


# ------------------------------------------------------------------ Sessão

def _assinar(valor: str) -> str:
    chave = config.carregar()["chave_sessao"].encode()
    return hmac.new(chave, valor.encode(), hashlib.sha256).hexdigest()


def _token_novo() -> str:
    valor = f"{secrets.token_hex(16)}.{int(time.time())}"
    return f"{valor}.{_assinar(valor)}"


def _token_valido(token: str) -> bool:
    if not token or token.count(".") != 2:
        return False
    aleatorio, emitido, assinatura = token.rsplit(".", 2)
    valor = f"{aleatorio}.{emitido}"
    if not hmac.compare_digest(_assinar(valor), assinatura):
        return False
    try:
        return time.time() - int(emitido) < 60 * 60 * 24 * 30  # 30 dias
    except ValueError:
        return False


LIVRES = {"/api/login", "/manifest.json", "/sw.js", "/icon.svg", "/style.css",
          "/app.js", "/", "/index.html"}


@app.middleware("http")
async def exigir_login(request: Request, chamar):
    caminho = request.url.path
    if caminho not in LIVRES and not _token_valido(
            request.cookies.get("daikon_sessao", "")):
        if caminho.startswith("/api/") or caminho.startswith("/arquivos/"):
            return JSONResponse({"erro": "login_necessario"}, status_code=401)
    return await chamar(request)


@app.post("/api/login")
def login(dados: dict = Body(...)):
    cfg = config.carregar()
    if not hmac.compare_digest(str(dados.get("senha", "")), str(cfg["senha"])):
        raise HTTPException(401, "Senha incorreta")
    resposta = JSONResponse({"ok": True})
    resposta.set_cookie("daikon_sessao", _token_novo(), max_age=60 * 60 * 24 * 30,
                        httponly=True, samesite="lax")
    return resposta


@app.post("/api/logout")
def logout():
    resposta = JSONResponse({"ok": True})
    resposta.delete_cookie("daikon_sessao")
    return resposta


# ------------------------------------------------------------------ Médicos

@app.get("/api/medicos")
def listar_medicos():
    return database.query("SELECT * FROM medicos WHERE ativo = 1 ORDER BY nome")


@app.post("/api/medicos")
def criar_medico(d: dict = Body(...)):
    novo = database.executar(
        "INSERT INTO medicos (nome, crm, especialidade) VALUES (?,?,?)",
        (d.get("nome", "").strip(), d.get("crm", ""), d.get("especialidade", "")))
    return {"id": novo}


@app.put("/api/medicos/{mid}")
def editar_medico(mid: int, d: dict = Body(...)):
    database.executar(
        "UPDATE medicos SET nome=?, crm=?, especialidade=? WHERE id=?",
        (d.get("nome", ""), d.get("crm", ""), d.get("especialidade", ""), mid))
    return {"ok": True}


@app.delete("/api/medicos/{mid}")
def remover_medico(mid: int):
    database.executar("UPDATE medicos SET ativo=0 WHERE id=?", (mid,))
    return {"ok": True}


# ------------------------------------------------------------- Procedimentos

@app.get("/api/procedimentos")
def listar_procedimentos():
    return database.query(
        "SELECT * FROM procedimentos WHERE ativo = 1 ORDER BY nome")


@app.post("/api/procedimentos")
def criar_procedimento(d: dict = Body(...)):
    novo = database.executar(
        """INSERT INTO procedimentos (nome, preco, duracao_min, modelo_laudo)
           VALUES (?,?,?,?)""",
        (d.get("nome", "").strip(), float(d.get("preco") or 0),
         int(d.get("duracao_min") or 20), d.get("modelo_laudo", "")))
    return {"id": novo}


@app.put("/api/procedimentos/{pid}")
def editar_procedimento(pid: int, d: dict = Body(...)):
    database.executar(
        """UPDATE procedimentos SET nome=?, preco=?, duracao_min=?, modelo_laudo=?
           WHERE id=?""",
        (d.get("nome", ""), float(d.get("preco") or 0),
         int(d.get("duracao_min") or 20), d.get("modelo_laudo", ""), pid))
    return {"ok": True}


@app.delete("/api/procedimentos/{pid}")
def remover_procedimento(pid: int):
    database.executar("UPDATE procedimentos SET ativo=0 WHERE id=?", (pid,))
    return {"ok": True}


# ----------------------------------------------------------------- Pacientes

@app.get("/api/pacientes")
def listar_pacientes(busca: str = ""):
    if busca:
        return database.query(
            "SELECT * FROM pacientes WHERE nome LIKE ? ORDER BY nome LIMIT 30",
            (f"%{busca}%",))
    return database.query("SELECT * FROM pacientes ORDER BY nome LIMIT 200")


@app.post("/api/pacientes")
def criar_paciente(d: dict = Body(...)):
    nome = d.get("nome", "").strip()
    if not nome:
        raise HTTPException(400, "Nome é obrigatório")
    novo = database.executar(
        """INSERT INTO pacientes (nome, nascimento, sexo, telefone, documento)
           VALUES (?,?,?,?,?)""",
        (nome, d.get("nascimento", ""), d.get("sexo", "O"),
         d.get("telefone", ""), d.get("documento", "")))
    return {"id": novo}


@app.put("/api/pacientes/{pid}")
def editar_paciente(pid: int, d: dict = Body(...)):
    database.executar(
        """UPDATE pacientes SET nome=?, nascimento=?, sexo=?, telefone=?,
               documento=? WHERE id=?""",
        (d.get("nome", ""), d.get("nascimento", ""), d.get("sexo", "O"),
         d.get("telefone", ""), d.get("documento", ""), pid))
    return {"ok": True}


# -------------------------------------------------------------- Agendamentos

@app.get("/api/agendamentos")
def listar_agendamentos(data: str = "", inicio: str = "", fim: str = ""):
    sql = """
        SELECT a.*, p.nome AS paciente_nome, p.telefone,
               pr.nome AS procedimento_nome, m.nome AS medico_nome,
               (SELECT e.id FROM estudos e WHERE e.agendamento_id = a.id LIMIT 1)
                   AS estudo_id
        FROM agendamentos a
        JOIN pacientes p ON p.id = a.paciente_id
        LEFT JOIN procedimentos pr ON pr.id = a.procedimento_id
        LEFT JOIN medicos m ON m.id = a.medico_id
    """
    params, filtros = [], []
    if data:
        filtros.append("a.data = ?")
        params.append(data)
    if inicio:
        filtros.append("a.data >= ?")
        params.append(inicio)
    if fim:
        filtros.append("a.data <= ?")
        params.append(fim)
    if filtros:
        sql += " WHERE " + " AND ".join(filtros)
    sql += " ORDER BY a.data, a.hora"
    return database.query(sql, params)


@app.post("/api/agendamentos")
def criar_agendamento(d: dict = Body(...)):
    if not d.get("paciente_id") or not d.get("data") or not d.get("hora"):
        raise HTTPException(400, "Paciente, data e hora são obrigatórios")
    preco = d.get("preco")
    if preco in (None, "") and d.get("procedimento_id"):
        proc = database.um("SELECT preco FROM procedimentos WHERE id=?",
                           (d["procedimento_id"],))
        preco = proc["preco"] if proc else 0
    accession = f"DK{uuid.uuid4().hex[:10].upper()}"
    novo = database.executar(
        """INSERT INTO agendamentos (paciente_id, procedimento_id, medico_id,
               data, hora, preco, observacoes, accession, study_uid)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (d["paciente_id"], d.get("procedimento_id"), d.get("medico_id"),
         d["data"], d["hora"], float(preco or 0), d.get("observacoes", ""),
         accession, novo_study_uid()))
    return {"id": novo, "accession": accession}


@app.put("/api/agendamentos/{aid}")
def editar_agendamento(aid: int, d: dict = Body(...)):
    database.executar(
        """UPDATE agendamentos SET procedimento_id=?, medico_id=?, data=?,
               hora=?, preco=?, pago=?, status=?, observacoes=? WHERE id=?""",
        (d.get("procedimento_id"), d.get("medico_id"), d.get("data"),
         d.get("hora"), float(d.get("preco") or 0), int(d.get("pago") or 0),
         d.get("status", "agendado"), d.get("observacoes", ""), aid))
    return {"ok": True}


@app.delete("/api/agendamentos/{aid}")
def cancelar_agendamento(aid: int):
    database.executar(
        "UPDATE agendamentos SET status='cancelado' WHERE id=?", (aid,))
    return {"ok": True}


# ------------------------------------------------------------------- Estudos

@app.get("/api/estudos")
def listar_estudos(limite: int = 50):
    return database.query("""
        SELECT e.*,
               (SELECT COUNT(*) FROM imagens i WHERE i.estudo_id = e.id)
                   AS total_imagens,
               (SELECT i.id FROM imagens i WHERE i.estudo_id = e.id
                    AND i.arquivo_png != '' ORDER BY i.numero LIMIT 1) AS capa_id,
               a.preco, a.pago, p.nome AS paciente_cadastro,
               pr.nome AS procedimento_nome,
               COALESCE(l.finalizado, -1) AS laudo_status
        FROM estudos e
        LEFT JOIN agendamentos a ON a.id = e.agendamento_id
        LEFT JOIN pacientes p ON p.id = a.paciente_id
        LEFT JOIN procedimentos pr ON pr.id = a.procedimento_id
        LEFT JOIN laudos l ON l.estudo_id = e.id
        ORDER BY e.recebido_em DESC LIMIT ?""", (min(limite, 500),))


@app.get("/api/estudos/{eid}")
def detalhar_estudo(eid: int):
    estudo = database.um("""
        SELECT e.*, a.paciente_id, a.medico_id AS agendamento_medico_id,
               pr.nome AS procedimento_nome, pr.modelo_laudo
        FROM estudos e
        LEFT JOIN agendamentos a ON a.id = e.agendamento_id
        LEFT JOIN procedimentos pr ON pr.id = a.procedimento_id
        WHERE e.id = ?""", (eid,))
    if not estudo:
        raise HTTPException(404, "Estudo não encontrado")
    estudo["imagens"] = database.query(
        """SELECT id, numero, frames, arquivo_png != '' AS tem_png
           FROM imagens WHERE estudo_id = ? ORDER BY numero, id""", (eid,))
    estudo["laudo"] = database.um(
        "SELECT * FROM laudos WHERE estudo_id = ?", (eid,))
    if estudo["paciente_id"]:
        estudo["paciente"] = database.um(
            "SELECT * FROM pacientes WHERE id = ?", (estudo["paciente_id"],))
    return estudo


@app.get("/arquivos/imagem/{iid}")
def baixar_imagem(iid: int):
    img = database.um("SELECT arquivo_png FROM imagens WHERE id = ?", (iid,))
    if not img or not img["arquivo_png"] or not os.path.exists(img["arquivo_png"]):
        raise HTTPException(404, "Imagem não disponível")
    return FileResponse(img["arquivo_png"], media_type="image/png")


# -------------------------------------------------------------------- Laudos

@app.post("/api/estudos/{eid}/laudo")
def salvar_laudo(eid: int, d: dict = Body(...)):
    if not database.um("SELECT id FROM estudos WHERE id = ?", (eid,)):
        raise HTTPException(404, "Estudo não encontrado")
    existente = database.um("SELECT id FROM laudos WHERE estudo_id = ?", (eid,))
    valores = (d.get("titulo", ""), d.get("texto", ""), d.get("medico_id"),
               ",".join(str(i) for i in d.get("imagens_ids", [])),
               int(d.get("finalizado") or 0))
    if existente:
        database.executar(
            """UPDATE laudos SET titulo=?, texto=?, medico_id=?, imagens_ids=?,
                   finalizado=?, atualizado_em=datetime('now','localtime')
               WHERE estudo_id=?""", valores + (eid,))
    else:
        database.executar(
            """INSERT INTO laudos (titulo, texto, medico_id, imagens_ids,
                   finalizado, estudo_id) VALUES (?,?,?,?,?,?)""",
            valores + (eid,))
    return {"ok": True}


@app.get("/api/estudos/{eid}/laudo.pdf")
def baixar_pdf(eid: int):
    estudo = database.um("SELECT * FROM estudos WHERE id = ?", (eid,))
    laudo = database.um("SELECT * FROM laudos WHERE estudo_id = ?", (eid,))
    if not estudo or not laudo:
        raise HTTPException(404, "Salve o laudo antes de gerar o PDF")

    paciente = None
    if estudo["agendamento_id"]:
        ag = database.um("SELECT * FROM agendamentos WHERE id = ?",
                         (estudo["agendamento_id"],))
        if ag:
            paciente = database.um("SELECT * FROM pacientes WHERE id = ?",
                                   (ag["paciente_id"],))
    if not paciente:
        paciente = {"nome": estudo["paciente_nome"], "nascimento": "", "sexo": ""}

    medico = None
    if laudo["medico_id"]:
        medico = database.um("SELECT * FROM medicos WHERE id = ?",
                             (laudo["medico_id"],))

    pngs = []
    ids = [i for i in (laudo["imagens_ids"] or "").split(",") if i.strip()]
    for iid in ids:
        img = database.um("SELECT arquivo_png FROM imagens WHERE id = ?", (iid,))
        if img and img["arquivo_png"]:
            pngs.append(img["arquivo_png"])

    data_exame = ""
    if estudo["data"] and len(estudo["data"]) == 8:
        d8 = estudo["data"]
        data_exame = f"{d8[0:4]}-{d8[4:6]}-{d8[6:8]}"
    estudo = dict(estudo)
    estudo["data_exame"] = data_exame

    caminho = pdf_laudo.gerar_pdf(estudo, dict(laudo), dict(paciente),
                                  dict(medico) if medico else None,
                                  pngs, config.carregar())
    nome_arquivo = f"laudo_{(paciente['nome'] or 'paciente').replace(' ', '_')}.pdf"
    return FileResponse(caminho, media_type="application/pdf",
                        filename=nome_arquivo)


# ------------------------------------------------------------- Configuração

CHAVES_PUBLICAS = ("nome_clinica", "subtitulo_clinica", "endereco_clinica",
                   "telefone_clinica", "ae_title", "porta_dicom", "porta_web")


@app.get("/api/config")
def ler_config():
    cfg = config.carregar()
    return {k: cfg[k] for k in CHAVES_PUBLICAS}


@app.put("/api/config")
def gravar_config(d: dict = Body(...)):
    cfg = config.carregar()
    for chave in CHAVES_PUBLICAS:
        if chave in d:
            cfg[chave] = d[chave]
    if d.get("nova_senha"):
        cfg["senha"] = str(d["nova_senha"])
    config.salvar(cfg)
    return {"ok": True,
            "aviso": "Portas e AE Title só mudam após reiniciar o Daikon."}


@app.get("/api/resumo")
def resumo(data: str = ""):
    """Painel: números do dia para a tela inicial."""
    from datetime import date
    data = data or date.today().isoformat()
    ags = database.query(
        "SELECT status, preco, pago FROM agendamentos WHERE data = ?", (data,))
    estudos_hoje = database.um(
        "SELECT COUNT(*) AS n FROM estudos WHERE date(recebido_em) = ?", (data,))
    pendentes = database.um("""
        SELECT COUNT(*) AS n FROM estudos e
        LEFT JOIN laudos l ON l.estudo_id = e.id
        WHERE COALESCE(l.finalizado, 0) = 0""")
    return {
        "data": data,
        "agendados": sum(1 for a in ags if a["status"] == "agendado"),
        "realizados": sum(1 for a in ags if a["status"] == "realizado"),
        "faturamento": sum(a["preco"] or 0 for a in ags
                           if a["status"] != "cancelado"),
        "recebido": sum(a["preco"] or 0 for a in ags
                        if a["pago"] and a["status"] != "cancelado"),
        "exames_recebidos": estudos_hoje["n"] if estudos_hoje else 0,
        "laudos_pendentes": pendentes["n"] if pendentes else 0,
    }


# ------------------------------------------------------------------ Estático

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
