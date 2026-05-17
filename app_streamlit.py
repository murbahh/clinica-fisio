"""
Clínica Fisio — versão web (celular) com Streamlit.
Execute: streamlit run app_streamlit.py
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from database import db
from database.schema import PLANOS, VALOR_SESSAO

db.init_db()

# --- Configuração da página (mobile-friendly) ---
st.set_page_config(
    page_title="Clínica Fisio",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 720px; }
    div[data-testid="stMetricValue"] { font-size: 1.4rem; }
    .stButton > button { width: 100%; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _senha_app() -> str:
    try:
        return st.secrets.get("APP_PASSWORD", "")
    except Exception:
        return os.environ.get("APP_PASSWORD", "fisio2026")


def _login():
    if st.session_state.get("logado"):
        return True

    st.title("🏥 Clínica Fisio")
    st.caption("Acesso pelo celular — versão de teste")

    senha = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar", type="primary"):
        if senha == _senha_app():
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.info(
        "Teste local: senha padrão `fisio2026` ou defina `APP_PASSWORD` / "
        "`st.secrets.APP_PASSWORD` na nuvem."
    )
    return False


def _logout_btn():
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()


def _clientes_opts():
    rows = db.listar_clientes()
    return {f"{r['id']} — {r['nome']} ({r['plano']})": r["id"] for r in rows}


def pagina_inicio():
    st.header("Resumo")
    r = db.relatorio_resultado(
        date.today().replace(day=1).isoformat(),
        date.today().isoformat(),
    )
    c1, c2 = st.columns(2)
    c1.metric("A receber (pend.)", f"R$ {r['pendente_receber']:.2f}")
    c2.metric("A pagar (pend.)", f"R$ {r['pendente_pagar']:.2f}")
    c3, c4 = st.columns(2)
    c3.metric("Receitas (mês)", f"R$ {r['receitas']:.2f}")
    c4.metric("Resultado (mês)", f"R$ {r['resultado']:.2f}")

    conn = db.get_conn()
    n_cli = conn.execute("SELECT COUNT(*) FROM clientes WHERE ativo=1").fetchone()[0]
    n_atend = conn.execute(
        "SELECT COUNT(*) FROM atendimentos WHERE data=date('now')"
    ).fetchone()[0]
    conn.close()
    st.write(f"**Clientes ativos:** {n_cli} · **Atendimentos hoje:** {n_atend}")


def pagina_clientes():
    st.header("Clientes")
    with st.form("novo_cliente", clear_on_submit=True):
        nome = st.text_input("Nome *")
        plano = st.selectbox("Plano", PLANOS)
        telefone = st.text_input("Telefone")
        if st.form_submit_button("Salvar cliente", type="primary"):
            if not nome.strip():
                st.error("Informe o nome.")
            else:
                db.salvar_cliente(nome, plano, telefone)
                st.success("Cliente salvo!")
                st.rerun()

    st.divider()
    filtro = st.selectbox("Filtrar por plano", ["todos"] + PLANOS)
    rows = db.listar_clientes(filtro)
    if not rows:
        st.info("Nenhum cliente cadastrado.")
        return
    for r in rows:
        with st.expander(f"{r['nome']} — {r['plano']}"):
            st.write(f"**ID:** {r['id']}")
            st.write(f"**Telefone:** {r['telefone'] or '—'}")


def pagina_pacotes():
    st.header("Pacotes de sessões")
    opts = _clientes_opts()
    if not opts:
        st.warning("Cadastre um cliente primeiro.")
        return

    with st.form("novo_pacote"):
        cliente_label = st.selectbox("Cliente", list(opts.keys()))
        total = st.number_input("Total de sessões", min_value=1, value=10, step=1)
        valor = st.number_input("Valor do pacote (R$)", min_value=0.0, value=1000.0, step=50.0)
        if st.form_submit_button("Criar pacote", type="primary"):
            db.criar_pacote(opts[cliente_label], int(total), float(valor))
            st.success("Pacote criado!")
            st.rerun()

    st.divider()
    conn = db.get_conn()
    rows = conn.execute(
        """SELECT p.*, c.nome FROM pacotes p
           JOIN clientes c ON c.id = p.cliente_id
           ORDER BY p.id DESC LIMIT 30"""
    ).fetchall()
    conn.close()
    for r in rows:
        rest = r["total_sessoes"] - r["sessoes_utilizadas"]
        st.write(
            f"**#{r['id']}** {r['nome']} — "
            f"{r['sessoes_utilizadas']}/{r['total_sessoes']} "
            f"(restam {rest}) — {r['status']}"
        )


def pagina_atendimentos():
    st.header("Registrar sessão")
    opts = _clientes_opts()
    if not opts:
        st.warning("Cadastre um cliente primeiro.")
        return

    cliente_label = st.selectbox("Cliente", list(opts.keys()))
    cliente_id = opts[cliente_label]

    conn = db.get_conn()
    cli = conn.execute("SELECT plano FROM clientes WHERE id=?", (cliente_id,)).fetchone()
    conn.close()
    plano = cli["plano"]
    st.info(f"Plano: **{plano}** · Valor/sessão: **R$ {VALOR_SESSAO[plano]:.2f}**")

    pacotes = db.pacotes_ativos_cliente(cliente_id)
    pacote_opts = {"Nenhum (só convênio/avulso)": None}
    for p in pacotes:
        pacote_opts[
            f"Pacote #{p['id']} ({p['sessoes_utilizadas']}/{p['total_sessoes']})"
        ] = p["id"]

    pacote_label = st.selectbox("Pacote (opcional)", list(pacote_opts.keys()))
    pacote_id = pacote_opts[pacote_label]

    if st.button("Registrar atendimento", type="primary"):
        try:
            db.registrar_atendimento(cliente_id, plano, pacote_id)
            st.success("Sessão registrada! Conta a receber gerada.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    st.divider()
    st.subheader("Últimos atendimentos")
    conn = db.get_conn()
    rows = conn.execute(
        """SELECT a.id, a.data, c.nome, a.plano
           FROM atendimentos a JOIN clientes c ON c.id = a.cliente_id
           ORDER BY a.id DESC LIMIT 15"""
    ).fetchall()
    conn.close()
    for r in rows:
        st.caption(f"#{r['id']} · {r['data']} · {r['nome']} · {r['plano']}")


def pagina_receber():
    st.header("Contas a receber")
    status = st.selectbox("Status", ["pendente", "pago", "todos"])
    rows = db.listar_contas_receber(status)
    total = sum(r["valor"] for r in rows)
    st.metric("Total listado", f"R$ {total:.2f}")

    for r in rows:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(
                f"**#{r['id']}** {r['cliente_nome']} · {r['plano']}\n\n"
                f"R$ {r['valor']:.2f} · venc. {r['data_vencimento']} · {r['status']}"
            )
        with col2:
            if r["status"] == "pendente" and st.button("Pagar", key=f"cr_{r['id']}"):
                db.baixar_conta_receber(r["id"])
                st.rerun()


def pagina_pagar():
    st.header("Contas a pagar")
    with st.form("nova_cp"):
        fornecedor = st.text_input("Fornecedor")
        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor (R$)", min_value=0.01, value=100.0, step=10.0)
        venc = st.date_input("Vencimento", value=date.today())
        if st.form_submit_button("Lançar despesa", type="primary"):
            db.salvar_conta_pagar(
                fornecedor, descricao, float(valor), venc.isoformat()
            )
            st.success("Despesa lançada!")
            st.rerun()

    st.divider()
    rows = db.listar_contas_pagar()
    for r in rows:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(
                f"**#{r['id']}** {r['fornecedor']}\n\n"
                f"{r['descricao']} · R$ {r['valor']:.2f} · {r['status']}"
            )
        with col2:
            if r["status"] == "pendente" and st.button("Pagar", key=f"cp_{r['id']}"):
                db.baixar_conta_pagar(r["id"])
                st.rerun()


def pagina_relatorio():
    st.header("Relatório")
    hoje = date.today()
    col1, col2 = st.columns(2)
    with col1:
        data_ini = st.date_input("De", value=hoje.replace(day=1))
    with col2:
        data_fim = st.date_input("Até", value=hoje)

    if st.button("Gerar relatório", type="primary"):
        r = db.relatorio_resultado(data_ini.isoformat(), data_fim.isoformat())
        st.markdown(
            f"""
            | Item | Valor |
            |------|-------|
            | Receitas recebidas | R$ {r['receitas']:.2f} |
            | Despesas pagas | R$ {r['despesas']:.2f} |
            | **Resultado** | **R$ {r['resultado']:.2f}** |
            | A receber (pendente) | R$ {r['pendente_receber']:.2f} |
            | A pagar (pendente) | R$ {r['pendente_pagar']:.2f} |
            """
        )


def main():
    if not _login():
        return

    _logout_btn()
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        ["Início", "Clientes", "Pacotes", "Sessão", "Receber", "Pagar", "Relatório"]
    )
    with tab1:
        pagina_inicio()
    with tab2:
        pagina_clientes()
    with tab3:
        pagina_pacotes()
    with tab4:
        pagina_atendimentos()
    with tab5:
        pagina_receber()
    with tab6:
        pagina_pagar()
    with tab7:
        pagina_relatorio()


if __name__ == "__main__":
    main()
