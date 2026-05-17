"""Telas CRM / prontuário do paciente (Streamlit)."""

from datetime import date

import streamlit as st

import clinica_data as db
from clinica_data import PLANOS, TIPOS_ANEXO, VALOR_SESSAO


def _mostrar_foto(caminho_relativo, largura=120):
    path = db.resolver_arquivo(caminho_relativo)
    if path:
        st.image(str(path), width=largura)
    else:
        st.markdown("👤")


def pagina_crm_dashboard():
    if st.session_state.get("crm_cliente_id"):
        pagina_prontuario(st.session_state.crm_cliente_id)
        return

    st.header("CRM — Pacientes")
    st.caption("Toque em **Abrir prontuário** para ver histórico, fotos, exames e evolução.")

    c1, c2 = st.columns(2)
    with c1:
        busca = st.text_input("Buscar", placeholder="Nome ou telefone...")
    with c2:
        filtro = st.selectbox("Plano", ["todos"] + PLANOS)

    rows = db.listar_clientes(plano=filtro, busca=busca)
    if not rows:
        st.info("Nenhum paciente encontrado.")
        return

    st.metric("Pacientes", len(rows))

    for r in rows:
        with st.container(border=True):
            col_foto, col_info, col_btn = st.columns([1, 2, 1])
            with col_foto:
                foto = r["foto_path"] if "foto_path" in r.keys() else None
                _mostrar_foto(foto, 90)
            with col_info:
                st.markdown(f"### {r['nome']}")
                st.caption(f"Plano: **{r['plano']}** · Tel: {r['telefone'] or '—'}")
                cpf = r["cpf"] if "cpf" in r.keys() else None
                if cpf:
                    st.caption(f"CPF: {cpf}")
            with col_btn:
                if st.button(
                    "Abrir prontuário",
                    key=f"crm_open_{r['id']}",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state.crm_cliente_id = r["id"]
                    st.rerun()


def pagina_prontuario(cliente_id: int):
    cli = db.obter_cliente(cliente_id)
    if not cli:
        st.error("Paciente não encontrado.")
        if st.button("Voltar"):
            st.session_state.pop("crm_cliente_id", None)
            st.rerun()
        return

    if st.button("← Voltar ao CRM", use_container_width=True):
        st.session_state.pop("crm_cliente_id", None)
        st.rerun()

    foto_path = cli["foto_path"] if "foto_path" in cli.keys() else None
    c1, c2 = st.columns([1, 2])
    with c1:
        _mostrar_foto(foto_path, 140)
        up_foto = st.file_uploader(
            "Foto do paciente",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"up_foto_{cliente_id}",
        )
        if up_foto and st.button("Salvar foto", key=f"save_foto_{cliente_id}"):
            db.salvar_foto_cliente(cliente_id, up_foto.getvalue(), up_foto.name)
            st.success("Foto atualizada!")
            st.rerun()
    with c2:
        st.markdown(f"## {cli['nome']}")
        st.write(f"**Plano:** {cli['plano']} · **Tel:** {cli['telefone'] or '—'}")
        if cli["email"] if "email" in cli.keys() else None:
            st.write(f"**E-mail:** {cli['email']}")
        obs = cli["observacoes"] if "observacoes" in cli.keys() else ""
        nova_obs = st.text_area("Observações gerais", value=obs or "", height=80)
        if st.button("Salvar observações", key=f"obs_{cliente_id}"):
            db.atualizar_observacoes_cliente(cliente_id, nova_obs)
            st.success("Salvo!")

    secao = st.selectbox(
        "Seção do prontuário",
        [
            "📋 Resumo",
            "📝 Evolução",
            "🩻 Exames e laudos",
            "📅 Atendimentos",
            "💰 Financeiro",
        ],
        key=f"secao_pront_{cliente_id}",
    )

    if secao.startswith("📋"):
        _secao_resumo(cliente_id)
    elif secao.startswith("📝"):
        _secao_evolucao(cliente_id)
    elif secao.startswith("🩻"):
        _secao_anexos(cliente_id)
    elif secao.startswith("📅"):
        _secao_atendimentos(cliente_id)
    else:
        _secao_financeiro(cliente_id)


def _secao_resumo(cliente_id):
    h = db.historico_cliente(cliente_id)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Atendimentos", len(h["atendimentos"]))
    c2.metric("Anexos", len(h["anexos"]))
    c3.metric("Evoluções", len(h["evolucoes"]))
    c4.metric("Pacotes", len(h["pacotes"]))

    st.subheader("Última evolução")
    if h["evolucoes"]:
        ev = h["evolucoes"][0]
        titulo = ev["titulo"] or "Sem título"
        st.markdown(f"**{titulo}** — {ev['criado_em']}")
        st.write(ev["texto"][:500] + ("..." if len(ev["texto"]) > 500 else ""))
    else:
        st.caption("Nenhuma evolução registrada.")

    st.subheader("Últimos anexos")
    for a in h["anexos"][:3]:
        st.caption(f"{a['tipo'].upper()}: {a['titulo'] or a['nome_arquivo']} — {a['criado_em']}")


def _secao_evolucao(cliente_id):
    st.subheader("Nova evolução")
    with st.form(f"form_evol_{cliente_id}"):
        titulo = st.text_input("Título (opcional)", placeholder="Ex.: Sessão 5 - joelho")
        texto = st.text_area(
            "Evolução clínica",
            height=220,
            placeholder="Queixa, conduta, exercícios, resposta ao tratamento...",
        )
        if st.form_submit_button("Salvar evolução", type="primary"):
            if not texto.strip():
                st.error("Escreva a evolução.")
            else:
                db.salvar_evolucao(cliente_id, titulo, texto)
                st.success("Evolução salva!")
                st.rerun()

    st.divider()
    st.subheader("Histórico de evoluções")
    evolucoes = db.listar_evolucoes(cliente_id)
    if not evolucoes:
        st.info("Nenhuma evolução ainda.")
        return

    for ev in evolucoes:
        with st.expander(f"{ev['titulo'] or 'Evolução'} — {ev['criado_em']}"):
            st.markdown(ev["texto"])
            if st.button("Excluir", key=f"del_ev_{ev['id']}"):
                db.excluir_evolucao(ev["id"])
                st.rerun()


def _secao_anexos(cliente_id):
    st.subheader("Anexar exame / laudo / imagem")
    with st.form(f"form_anexo_{cliente_id}"):
        tipo = st.selectbox("Tipo", TIPOS_ANEXO)
        titulo = st.text_input("Título", placeholder="Ex.: Ressonância joelho")
        descricao = st.text_area("Descrição (opcional)", height=60)
        arquivo = st.file_uploader(
            "Arquivo (imagem ou PDF)",
            type=["jpg", "jpeg", "png", "webp", "pdf"],
        )
        if st.form_submit_button("Anexar", type="primary"):
            if not arquivo:
                st.error("Selecione um arquivo.")
            else:
                db.salvar_anexo(
                    cliente_id,
                    tipo,
                    titulo,
                    descricao,
                    arquivo.getvalue(),
                    arquivo.name,
                )
                st.success("Anexo salvo!")
                st.rerun()

    st.divider()
    filtro = st.selectbox("Filtrar", ["todos"] + TIPOS_ANEXO, key=f"f_anexo_{cliente_id}")
    anexos = db.listar_anexos(cliente_id, filtro)

    if not anexos:
        st.info("Nenhum anexo.")
        return

    for a in anexos:
        with st.container(border=True):
            st.markdown(f"**{a['tipo'].upper()}** — {a['titulo'] or a['nome_arquivo']}")
            st.caption(f"{a['criado_em']} · {a['descricao'] or ''}")
            path = db.resolver_arquivo(a["arquivo_path"])
            if path and db.eh_imagem(a["nome_arquivo"] or ""):
                st.image(str(path), use_container_width=True)
            elif path:
                with open(path, "rb") as f:
                    st.download_button(
                        "Baixar arquivo",
                        f.read(),
                        file_name=a["nome_arquivo"] or "anexo",
                        key=f"dl_{a['id']}",
                    )
            if st.button("Excluir anexo", key=f"del_anexo_{a['id']}"):
                db.excluir_anexo(a["id"])
                st.rerun()


def _secao_atendimentos(cliente_id):
    cli = db.obter_cliente(cliente_id)
    plano = cli["plano"]
    st.info(f"Valor/sessão ({plano}): R$ {VALOR_SESSAO[plano]:.2f}")

    pacotes = db.pacotes_ativos_cliente(cliente_id)
    pacote_opts = {"Nenhum": None}
    for p in pacotes:
        pacote_opts[f"Pacote #{p['id']} ({p['sessoes_utilizadas']}/{p['total_sessoes']})"] = p[
            "id"
        ]
    pacote_label = st.selectbox("Pacote", list(pacote_opts.keys()), key=f"pac_{cliente_id}")
    if st.button("Registrar sessão aqui", type="primary", key=f"at_{cliente_id}"):
        try:
            db.registrar_atendimento(cliente_id, plano, pacote_opts[pacote_label])
            st.success("Sessão registrada!")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    st.divider()
    h = db.historico_cliente(cliente_id)
    for a in h["atendimentos"]:
        st.caption(f"#{a['id']} · {a['data']} · {a['plano']}")


def _secao_financeiro(cliente_id):
    h = db.historico_cliente(cliente_id)
    for p in h["pacotes"]:
        rest = p["total_sessoes"] - p["sessoes_utilizadas"]
        st.write(
            f"Pacote #{p['id']}: {p['sessoes_utilizadas']}/{p['total_sessoes']} "
            f"(restam {rest}) — {p['status']}"
        )
    st.divider()
    for cr in h["receber"]:
        st.caption(
            f"#{cr['id']} R$ {cr['valor']:.2f} — {cr['status']} — venc. {cr['data_vencimento']}"
        )
