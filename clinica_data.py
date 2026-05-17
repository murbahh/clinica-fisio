"""
Camada de dados SQLite — usada pelo Streamlit (arquivo único para deploy na nuvem).
O app desktop continua usando database/db.py
"""

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cpf TEXT,
    telefone TEXT,
    email TEXT,
    plano TEXT NOT NULL CHECK (plano IN ('unimed','cassems','prefeitura','particular')),
    numero_carteirinha TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS valores_plano (
    plano TEXT PRIMARY KEY CHECK (plano IN ('unimed','cassems','prefeitura','particular')),
    valor_sessao REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS pacotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    total_sessoes INTEGER NOT NULL CHECK (total_sessoes > 0),
    sessoes_utilizadas INTEGER NOT NULL DEFAULT 0,
    valor_total REAL,
    data_compra TEXT NOT NULL DEFAULT (date('now')),
    data_validade TEXT,
    status TEXT NOT NULL DEFAULT 'ativo',
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS atendimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    pacote_id INTEGER,
    data TEXT NOT NULL DEFAULT (date('now')),
    hora TEXT,
    plano TEXT NOT NULL,
    observacoes TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (pacote_id) REFERENCES pacotes(id)
);

CREATE TABLE IF NOT EXISTS contas_receber (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    atendimento_id INTEGER,
    descricao TEXT,
    valor REAL NOT NULL,
    data_vencimento TEXT,
    data_pagamento TEXT,
    status TEXT NOT NULL DEFAULT 'pendente',
    plano TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (atendimento_id) REFERENCES atendimentos(id)
);

CREATE TABLE IF NOT EXISTS contas_pagar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fornecedor TEXT,
    descricao TEXT,
    categoria TEXT,
    valor REAL NOT NULL,
    data_vencimento TEXT,
    data_pagamento TEXT,
    status TEXT NOT NULL DEFAULT 'pendente'
);

CREATE INDEX IF NOT EXISTS idx_clientes_plano ON clientes(plano);
CREATE INDEX IF NOT EXISTS idx_atendimentos_cliente ON atendimentos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_receber_status ON contas_receber(status);
CREATE INDEX IF NOT EXISTS idx_pagar_status ON contas_pagar(status);

INSERT OR IGNORE INTO valores_plano (plano, valor_sessao) VALUES
    ('unimed', 85.0),
    ('cassems', 78.0),
    ('prefeitura', 70.0),
    ('particular', 120.0);
"""

VALOR_SESSAO = {
    "unimed": 85.0,
    "cassems": 78.0,
    "prefeitura": 70.0,
    "particular": 120.0,
}

PLANOS = list(VALOR_SESSAO.keys())

DB_PATH = Path(__file__).resolve().parent / "data" / "clinica.db"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def listar_clientes(plano=None):
    conn = get_conn()
    if plano and plano != "todos":
        rows = conn.execute(
            "SELECT * FROM clientes WHERE ativo=1 AND plano=? ORDER BY nome",
            (plano,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM clientes WHERE ativo=1 ORDER BY nome"
        ).fetchall()
    conn.close()
    return rows


def salvar_cliente(nome, plano, telefone):
    conn = get_conn()
    conn.execute(
        "INSERT INTO clientes (nome, plano, telefone) VALUES (?, ?, ?)",
        (nome.strip(), plano, telefone.strip()),
    )
    conn.commit()
    conn.close()


def criar_pacote(cliente_id, total_sessoes, valor_total):
    conn = get_conn()
    conn.execute(
        """INSERT INTO pacotes (cliente_id, total_sessoes, valor_total)
           VALUES (?, ?, ?)""",
        (cliente_id, total_sessoes, valor_total),
    )
    conn.commit()
    conn.close()


def pacotes_ativos_cliente(cliente_id):
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM pacotes
           WHERE cliente_id=? AND status='ativo'
             AND sessoes_utilizadas < total_sessoes""",
        (cliente_id,),
    ).fetchall()
    conn.close()
    return rows


def registrar_atendimento(cliente_id, plano, pacote_id=None, gerar_receber=True):
    conn = get_conn()
    cur = conn.cursor()

    if pacote_id:
        pacote = cur.execute(
            "SELECT * FROM pacotes WHERE id=? AND cliente_id=?",
            (pacote_id, cliente_id),
        ).fetchone()
        if not pacote or pacote["sessoes_utilizadas"] >= pacote["total_sessoes"]:
            conn.close()
            raise ValueError("Pacote inválido ou esgotado.")

    cur.execute(
        """INSERT INTO atendimentos (cliente_id, pacote_id, plano)
           VALUES (?, ?, ?)""",
        (cliente_id, pacote_id, plano),
    )
    atendimento_id = cur.lastrowid

    if pacote_id:
        cur.execute(
            """UPDATE pacotes SET sessoes_utilizadas = sessoes_utilizadas + 1
               WHERE id=?""",
            (pacote_id,),
        )
        cur.execute(
            """UPDATE pacotes SET status='esgotado'
               WHERE id=? AND sessoes_utilizadas >= total_sessoes""",
            (pacote_id,),
        )

    if gerar_receber:
        valor = VALOR_SESSAO[plano]
        cur.execute(
            """INSERT INTO contas_receber
               (cliente_id, atendimento_id, descricao, valor, data_vencimento, plano)
               VALUES (?, ?, ?, ?, date('now', '+30 days'), ?)""",
            (
                cliente_id,
                atendimento_id,
                f"Sessão fisioterapia ({plano})",
                valor,
                plano,
            ),
        )

    conn.commit()
    conn.close()
    return atendimento_id


def listar_contas_receber(status=None):
    conn = get_conn()
    sql = """
        SELECT cr.*, c.nome AS cliente_nome
        FROM contas_receber cr
        JOIN clientes c ON c.id = cr.cliente_id
    """
    if status and status != "todos":
        rows = conn.execute(
            sql + " WHERE cr.status=? ORDER BY cr.data_vencimento",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(sql + " ORDER BY cr.data_vencimento").fetchall()
    conn.close()
    return rows


def baixar_conta_receber(conta_id):
    conn = get_conn()
    conn.execute(
        """UPDATE contas_receber
           SET status='pago', data_pagamento=date('now')
           WHERE id=?""",
        (conta_id,),
    )
    conn.commit()
    conn.close()


def salvar_conta_pagar(fornecedor, descricao, valor, vencimento):
    conn = get_conn()
    conn.execute(
        """INSERT INTO contas_pagar (fornecedor, descricao, valor, data_vencimento)
           VALUES (?, ?, ?, ?)""",
        (fornecedor, descricao, valor, vencimento),
    )
    conn.commit()
    conn.close()


def listar_contas_pagar(status=None):
    conn = get_conn()
    if status and status != "todos":
        rows = conn.execute(
            "SELECT * FROM contas_pagar WHERE status=? ORDER BY data_vencimento",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM contas_pagar ORDER BY data_vencimento"
        ).fetchall()
    conn.close()
    return rows


def baixar_conta_pagar(conta_id):
    conn = get_conn()
    conn.execute(
        """UPDATE contas_pagar
           SET status='pago', data_pagamento=date('now')
           WHERE id=?""",
        (conta_id,),
    )
    conn.commit()
    conn.close()


def relatorio_resultado(data_ini, data_fim):
    conn = get_conn()
    receitas = conn.execute(
        """SELECT COALESCE(SUM(valor), 0) FROM contas_receber
           WHERE status='pago' AND data_pagamento BETWEEN ? AND ?""",
        (data_ini, data_fim),
    ).fetchone()[0]
    despesas = conn.execute(
        """SELECT COALESCE(SUM(valor), 0) FROM contas_pagar
           WHERE status='pago' AND data_pagamento BETWEEN ? AND ?""",
        (data_ini, data_fim),
    ).fetchone()[0]
    pendente_receber = conn.execute(
        "SELECT COALESCE(SUM(valor), 0) FROM contas_receber WHERE status='pendente'"
    ).fetchone()[0]
    pendente_pagar = conn.execute(
        "SELECT COALESCE(SUM(valor), 0) FROM contas_pagar WHERE status='pendente'"
    ).fetchone()[0]
    conn.close()
    return {
        "receitas": receitas,
        "despesas": despesas,
        "resultado": receitas - despesas,
        "pendente_receber": pendente_receber,
        "pendente_pagar": pendente_pagar,
    }
