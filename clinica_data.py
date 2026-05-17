"""
Camada de dados SQLite — usada pelo Streamlit (arquivo único para deploy na nuvem).
O app desktop continua usando database/db.py
"""

import sqlite3
import uuid
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

CREATE TABLE IF NOT EXISTS anexos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('exame', 'laudo', 'documento', 'outro')),
    titulo TEXT,
    descricao TEXT,
    arquivo_path TEXT NOT NULL,
    nome_arquivo TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evolucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    titulo TEXT,
    texto TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    atualizado_em TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_anexos_cliente ON anexos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_evolucoes_cliente ON evolucoes(cliente_id);
"""

TIPOS_ANEXO = ["exame", "laudo", "documento", "outro"]
EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
EXT_PDF = {".pdf"}

VALOR_SESSAO = {
    "unimed": 85.0,
    "cassems": 78.0,
    "prefeitura": 70.0,
    "particular": 120.0,
}

PLANOS = list(VALOR_SESSAO.keys())

DB_PATH = Path(__file__).resolve().parent / "data" / "clinica.db"
ROOT_DIR = Path(__file__).resolve().parent
UPLOADS_ROOT = ROOT_DIR / "data" / "uploads"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()}
    if "foto_path" not in cols:
        conn.execute("ALTER TABLE clientes ADD COLUMN foto_path TEXT")
    if "observacoes" not in cols:
        conn.execute("ALTER TABLE clientes ADD COLUMN observacoes TEXT")


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    conn.close()
    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)


def _pasta_cliente(cliente_id: int) -> Path:
    pasta = UPLOADS_ROOT / str(cliente_id)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def resolver_arquivo(caminho_relativo: str | None) -> Path | None:
    if not caminho_relativo:
        return None
    p = ROOT_DIR / caminho_relativo
    return p if p.is_file() else None


def eh_imagem(nome_arquivo: str) -> bool:
    return Path(nome_arquivo).suffix.lower() in EXT_IMAGEM


def listar_clientes(plano=None, busca=None):
    conn = get_conn()
    sql = "SELECT * FROM clientes WHERE ativo=1"
    params = []
    if plano and plano != "todos":
        sql += " AND plano=?"
        params.append(plano)
    if busca and busca.strip():
        t = f"%{busca.strip()}%"
        sql += " AND (nome LIKE ? OR telefone LIKE ? OR COALESCE(cpf,'') LIKE ?)"
        params.extend([t, t, t])
    sql += " ORDER BY nome"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def obter_cliente(cliente_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM clientes WHERE id=?", (cliente_id,)).fetchone()
    conn.close()
    return row


def atualizar_observacoes_cliente(cliente_id, observacoes):
    conn = get_conn()
    conn.execute(
        "UPDATE clientes SET observacoes=? WHERE id=?",
        (observacoes.strip(), cliente_id),
    )
    conn.commit()
    conn.close()


def salvar_foto_cliente(cliente_id, bytes_arquivo, nome_original):
    ext = Path(nome_original).suffix.lower() or ".jpg"
    if ext not in EXT_IMAGEM:
        ext = ".jpg"
    destino = _pasta_cliente(cliente_id) / f"foto_perfil{ext}"
    destino.write_bytes(bytes_arquivo)
    rel = destino.relative_to(ROOT_DIR).as_posix()
    conn = get_conn()
    conn.execute("UPDATE clientes SET foto_path=? WHERE id=?", (rel, cliente_id))
    conn.commit()
    conn.close()
    return rel


def salvar_anexo(cliente_id, tipo, titulo, descricao, bytes_arquivo, nome_original):
    ext = Path(nome_original).suffix.lower() or ""
    nome_safe = f"{uuid.uuid4().hex}{ext}"
    destino = _pasta_cliente(cliente_id) / "anexos"
    destino.mkdir(exist_ok=True)
    arquivo = destino / nome_safe
    arquivo.write_bytes(bytes_arquivo)
    rel = arquivo.relative_to(ROOT_DIR).as_posix()
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO anexos
           (cliente_id, tipo, titulo, descricao, arquivo_path, nome_arquivo)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (cliente_id, tipo, titulo, descricao, rel, nome_original),
    )
    conn.commit()
    anexo_id = cur.lastrowid
    conn.close()
    return anexo_id


def listar_anexos(cliente_id, tipo=None):
    conn = get_conn()
    if tipo and tipo != "todos":
        rows = conn.execute(
            "SELECT * FROM anexos WHERE cliente_id=? AND tipo=? ORDER BY criado_em DESC",
            (cliente_id, tipo),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM anexos WHERE cliente_id=? ORDER BY criado_em DESC",
            (cliente_id,),
        ).fetchall()
    conn.close()
    return rows


def excluir_anexo(anexo_id):
    conn = get_conn()
    row = conn.execute("SELECT arquivo_path FROM anexos WHERE id=?", (anexo_id,)).fetchone()
    if row:
        p = resolver_arquivo(row["arquivo_path"])
        if p:
            p.unlink(missing_ok=True)
    conn.execute("DELETE FROM anexos WHERE id=?", (anexo_id,))
    conn.commit()
    conn.close()


def salvar_evolucao(cliente_id, titulo, texto):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO evolucoes (cliente_id, titulo, texto)
           VALUES (?, ?, ?)""",
        (cliente_id, titulo.strip() or None, texto.strip()),
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid


def listar_evolucoes(cliente_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM evolucoes WHERE cliente_id=? ORDER BY criado_em DESC",
        (cliente_id,),
    ).fetchall()
    conn.close()
    return rows


def atualizar_evolucao(evolucao_id, titulo, texto):
    conn = get_conn()
    conn.execute(
        """UPDATE evolucoes SET titulo=?, texto=?,
           atualizado_em=datetime('now', 'localtime') WHERE id=?""",
        (titulo.strip() or None, texto.strip(), evolucao_id),
    )
    conn.commit()
    conn.close()


def excluir_evolucao(evolucao_id):
    conn = get_conn()
    conn.execute("DELETE FROM evolucoes WHERE id=?", (evolucao_id,))
    conn.commit()
    conn.close()


def historico_cliente(cliente_id):
    conn = get_conn()
    atendimentos = conn.execute(
        """SELECT id, data, plano, observacoes FROM atendimentos
           WHERE cliente_id=? ORDER BY data DESC, id DESC LIMIT 50""",
        (cliente_id,),
    ).fetchall()
    pacotes = conn.execute(
        "SELECT * FROM pacotes WHERE cliente_id=? ORDER BY id DESC",
        (cliente_id,),
    ).fetchall()
    receber = conn.execute(
        """SELECT id, descricao, valor, status, data_vencimento
           FROM contas_receber WHERE cliente_id=? ORDER BY id DESC LIMIT 20""",
        (cliente_id,),
    ).fetchall()
    conn.close()
    return {
        "atendimentos": atendimentos,
        "pacotes": pacotes,
        "receber": receber,
        "anexos": listar_anexos(cliente_id),
        "evolucoes": listar_evolucoes(cliente_id),
    }


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
