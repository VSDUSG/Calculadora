"""Banco de dados SQLite do Daikon.

Tabelas:
  medicos        - médicos solicitantes/executantes
  procedimentos  - tipos de exame com preço
  pacientes      - cadastro de pacientes
  agendamentos   - agenda de exames (alimenta a Worklist DICOM)
  estudos        - estudos DICOM recebidos do ultrassom
  imagens        - imagens de cada estudo
  laudos         - texto do laudo de cada estudo
"""
import os
import sqlite3
import threading
from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS medicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    crm TEXT DEFAULT '',
    especialidade TEXT DEFAULT '',
    ativo INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS procedimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    preco REAL DEFAULT 0,
    duracao_min INTEGER DEFAULT 20,
    modelo_laudo TEXT DEFAULT '',
    ativo INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pacientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    nascimento TEXT DEFAULT '',
    sexo TEXT DEFAULT 'O',
    telefone TEXT DEFAULT '',
    documento TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS agendamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id),
    procedimento_id INTEGER REFERENCES procedimentos(id),
    medico_id INTEGER REFERENCES medicos(id),
    data TEXT NOT NULL,             -- YYYY-MM-DD
    hora TEXT NOT NULL,             -- HH:MM
    preco REAL DEFAULT 0,
    pago INTEGER DEFAULT 0,
    status TEXT DEFAULT 'agendado', -- agendado | realizado | cancelado
    accession TEXT UNIQUE,          -- Accession Number enviado na Worklist
    study_uid TEXT,                 -- Study Instance UID gerado para a Worklist
    observacoes TEXT DEFAULT '',
    criado_em TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS estudos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_uid TEXT UNIQUE NOT NULL,
    agendamento_id INTEGER REFERENCES agendamentos(id),
    paciente_nome TEXT DEFAULT '',
    paciente_id_dicom TEXT DEFAULT '',
    accession TEXT DEFAULT '',
    descricao TEXT DEFAULT '',
    data TEXT DEFAULT '',
    hora TEXT DEFAULT '',
    recebido_em TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS imagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudo_id INTEGER NOT NULL REFERENCES estudos(id),
    sop_uid TEXT UNIQUE NOT NULL,
    arquivo_dicom TEXT NOT NULL,
    arquivo_png TEXT DEFAULT '',
    numero INTEGER DEFAULT 0,
    frames INTEGER DEFAULT 1,
    recebido_em TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS laudos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudo_id INTEGER UNIQUE NOT NULL REFERENCES estudos(id),
    titulo TEXT DEFAULT '',
    texto TEXT DEFAULT '',
    medico_id INTEGER REFERENCES medicos(id),
    imagens_ids TEXT DEFAULT '',    -- ids de imagens incluídas no PDF, separados por vírgula
    finalizado INTEGER DEFAULT 0,
    atualizado_em TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


def conexao() -> sqlite3.Connection:
    """Uma conexão por thread (o servidor DICOM roda em threads próprias)."""
    con = getattr(_local, "con", None)
    if con is None:
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        con = sqlite3.connect(config.DB_PATH)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        _local.con = con
    return con


def iniciar() -> None:
    con = conexao()
    con.executescript(SCHEMA)
    con.commit()


def query(sql: str, params=()) -> list:
    cur = conexao().execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def um(sql: str, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def executar(sql: str, params=()) -> int:
    con = conexao()
    cur = con.execute(sql, params)
    con.commit()
    return cur.lastrowid
