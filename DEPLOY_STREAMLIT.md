# Clínica Fisio — teste no celular pela internet (Streamlit)

## Testar no computador

```powershell
cd "D:\projeto fisiot\clinica_fisio\criar_arquivos"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-streamlit.txt
python criar_banco.py
streamlit run app_streamlit.py
```

- No PC: abra `http://localhost:8501`
- No celular (mesma Wi-Fi): `http://IP-DO-PC:8501` (ex.: `http://192.168.0.10:8501`)

**Senha padrão de teste:** `fisio2026`

---

## Publicar na internet (grátis) — Streamlit Cloud

1. Crie um repositório no **GitHub** e envie a pasta `criar_arquivos` (todos os arquivos, exceto `.venv`).
2. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login com o GitHub.
3. **New app** → escolha o repositório.
4. Configuração:
   - **Main file path:** `app_streamlit.py`
   - **App URL:** escolha um nome (ex. `clinica-fisio-teste`)
5. **Advanced settings** → **Requirements file:** `requirements-streamlit.txt`
6. **Secrets** (Settings do app → Secrets), cole:

```toml
APP_PASSWORD = "coloque_uma_senha_forte"
```

7. **Deploy** → em alguns minutos você recebe:  
   `https://clinica-fisio-teste.streamlit.app`

No celular: abra o link no Chrome → menu **Adicionar à tela inicial** (funciona como atalho de app).

---

## Alternativa: túnel no seu PC (sem GitHub)

Com o app rodando (`streamlit run app_streamlit.py`):

```powershell
pip install pyngrok
ngrok http 8501
```

Use a URL **https** que aparecer no celular. O PC precisa ficar ligado e conectado à internet.

---

## SQLite na nuvem (importante)

No **Streamlit Cloud**, o arquivo `data/clinica.db` pode ser **apagado** quando o servidor reinicia. Serve para **teste**, não para produção com muitos dados.

Para uso real com vários celulares: migre depois para **PostgreSQL** (Supabase ou Neon, plano grátis).

---

## Arquivos obrigatórios no GitHub

Envie **todos** estes arquivos na raiz do repositório:

- `app_streamlit.py`
- `clinica_data.py` ← banco de dados (obrigatório)
- `crm_pages.py` ← CRM e prontuário (obrigatório)
- `requirements-streamlit.txt`
- `.streamlit/config.toml`

Opcional: pasta `database/` (só para o app desktop).

## Estrutura usada pela web

| Arquivo | Função |
|---------|--------|
| `app_streamlit.py` | Interface no celular |
| `clinica_data.py` | SQLite e regras de negócio |
| `data/clinica.db` | Banco (criado ao abrir o app) |
| `requirements-streamlit.txt` | Dependências na nuvem |
