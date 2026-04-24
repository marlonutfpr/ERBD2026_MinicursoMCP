import sys
import os
import streamlit as st
import asyncio
import json
import pandas as pd
import re
from datetime import date, timedelta
from dotenv import load_dotenv

# Adiciona mcp/ ao path para importar mcp_core
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp'))
from mcp_core import mcp_call_tool_async, mcp_multi_call_async, agente_llm_loop

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Configuração inicial da página Streamlit
st.set_page_config(
    page_title="Minicurso MCP: Agente de Dados",
    page_icon="🤖",
    layout="wide"
)

# -----------------------------------------------------------------------------
# MOTOR DE COMUNICAÇÃO MCP (CLIENT)
# Funções async em mcp_core.py — aqui só os wrappers síncronos com UI.
# -----------------------------------------------------------------------------

def executar_ferramenta(tool_name: str, arguments: dict):
    """Sincroniza a chamada assíncrona para o Streamlit (que é síncrono)."""
    with st.spinner(f"Agente a invocar a ferramenta '{tool_name}'..."):
        return asyncio.run(mcp_call_tool_async(tool_name, arguments))

def executar_multiplas_ferramentas(chamadas: list) -> list:
    """Executa em série uma lista de (tool_name, arguments) numa única sessão MCP."""
    return asyncio.run(mcp_multi_call_async(chamadas))

# Mapa de nomes em linguagem natural → sigla de moeda
_MAPA_MOEDAS = {
    "dólar americano": "USD", "dolar americano": "USD",
    "dólar": "USD",  "dolar": "USD",  "usd": "USD",
    "euro": "EUR",   "eur": "EUR",
    "libra esterlina": "GBP", "libra": "GBP", "pound": "GBP", "gbp": "GBP",
    "iene": "JPY",   "yen": "JPY",   "jpy": "JPY",
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH",
    "dólar canadense": "CAD", "dolar canadense": "CAD", "cad": "CAD",
    "peso argentino": "ARS", "peso": "ARS", "ars": "ARS",
    "franco suíço": "CHF", "franco suico": "CHF", "chf": "CHF",
    "dólar australiano": "AUD", "dolar australiano": "AUD", "aud": "AUD",
}

def _detectar_moeda_e_data(t: str):
    """Extrai moeda(s) e data (se houver) de um texto em linguagem natural."""
    moedas = []
    # Percorre do nome mais longo para o mais curto para evitar matches parciais
    for nome, sigla in sorted(_MAPA_MOEDAS.items(), key=lambda x: -len(x[0])):
        if nome in t and sigla not in moedas:
            moedas.append(sigla)
    if not moedas:
        moedas = ["USD", "EUR"]  # padrão

    # Detecta data
    data = ""
    if "hoje" in t:
        data = date.today().strftime("%Y-%m-%d")
    elif "ontem" in t:
        data = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        m = re.search(r'\b(\d{2})[/-](\d{2})[/-](\d{4})\b', t)
        if m:
            data = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        else:
            m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', t)
            if m:
                data = m.group(0)

    return ",".join(moedas), data


def interpretar_linguagem_natural(texto: str):
    """
    Mapeia uma pergunta em linguagem natural para a ferramenta MCP correta.
    Retorna (tool_name, arguments, descricao) ou (None, None, None) se não reconhecido.
    """
    t = texto.lower().strip()

    # Intenção: cotação de moedas
    palavras_cambio = ["câmbio", "cambio", "cotação", "cotacao", "conversão", "conversao",
                       "moeda", "brl"] + list(_MAPA_MOEDAS.keys())
    if any(p in t for p in palavras_cambio):
        moeda, data = _detectar_moeda_e_data(t)
        args = {"moeda": moeda}
        if data:
            args["data"] = data
        desc = f"🌐 Consultando cotação de **{moeda}** em relação ao BRL"
        if data:
            desc += f" em **{data}**"
        return "consultar_cotacao_moedas", args, desc

    # Intenção: total gasto por cliente (precisa de ID no formato Cnnnn)
    match_id = re.search(r'\b(c\d{4})\b', t)
    if match_id and any(p in t for p in ["gasto", "gastou", "compra", "comprou",
                                          "total", "ltv", "valor", "gast"]):
        id_cliente = match_id.group(1).upper()
        return "calcular_total_gasto_cliente", {"id_cliente": id_cliente}, \
               f"📈 Calculando total gasto pelo cliente {id_cliente} no Big Data (CSV)"

    # Intenção: listar clientes por tag
    for tag in ["vip", "novo", "b2b", "inadimplente", "fraude"]:
        if tag in t:
            return "listar_clientes_por_tag", {"tag_procurada": tag}, \
                   f"🗂️ Buscando clientes com a tag '{tag}' na base NoSQL"

    # Intenção: métricas/preço de produtos (incluindo dimensões bloqueadas para demonstração)
    for dim in ["margem", "lucro", "fornecedor", "custo"]:
        if dim in t:
            return "obter_metricas_produtos", {"dimensao": dim}, \
                   f"📊 Tentando consultar dimensão restrita '{dim}' — bloqueio esperado"

    if any(p in t for p in ["produto", "preço", "preco", "média", "media",
                             "categoria", "métrica", "metrica", "relacional"]):
        return "obter_metricas_produtos", {"dimensao": "categoria"}, \
               "📊 Consultando preço médio de produtos por categoria (SQLite)"

    return None, None, None


# -----------------------------------------------------------------------------
# CONSULTAS COMPOSTAS — encadeamento de múltiplas ferramentas MCP
# Cada função abre UMA sessão e faz N chamadas sequenciais, simulando o
# raciocínio multi-passo de um LLM que "pensa em voz alta".
# -----------------------------------------------------------------------------

def cq_ltv_tag_em_moedas(tag: str, log):
    """
    Pergunta natural: "Qual o gasto total dos clientes VIP em dólar e euro?"
    Cadeia de chamadas:
      1. listar_clientes_por_tag(tag)       → identifica os clientes
      2. consultar_cotacao_moedas()          → busca taxa de câmbio atual
      3. calcular_total_gasto_cliente × N    → LTV de cada cliente (CSV)
    Saída: tabela com BRL / USD / EUR + total consolidado
    """
    log.info("**Passo 1 / 2** — Buscando clientes `" + tag + "` e cotações de câmbio…")
    res = executar_multiplas_ferramentas([
        ("listar_clientes_por_tag", {"tag_procurada": tag}),
        ("consultar_cotacao_moedas", {}),
    ])
    clientes_raw, cotacao_raw = res[0], res[1]

    if "❌" in clientes_raw:
        return None, clientes_raw
    try:
        clientes = json.loads(clientes_raw)
        cotacao  = json.loads(cotacao_raw)
        usd = float(cotacao["USD"]["valor"])
        eur = float(cotacao["EUR"]["valor"])
    except Exception as e:
        return None, f"Erro ao interpretar resposta MCP: {e}"

    if not clientes:
        return None, f"Nenhum cliente encontrado com a tag '{tag}'."

    log.info(f"**Passo 2 / 2** — Calculando LTV de {len(clientes)} cliente(s) no Big Data (CSV)…")
    chamadas_ltv = [("calcular_total_gasto_cliente", {"id_cliente": c["id"]}) for c in clientes]
    gastos_raw = executar_multiplas_ferramentas(chamadas_ltv)

    linhas = []
    for cliente, gasto_raw in zip(clientes, gastos_raw):
        try:
            g = json.loads(gasto_raw)
            brl = g["total"]
            linhas.append({
                "ID":             cliente["id"],
                "Nome":           cliente["nome_anonimizado"],
                "Compras":        g["compras"],
                "Total (R$)":     brl,
                "Total (USD)":    round(brl / usd, 2),
                "Total (EUR)":    round(brl / eur, 2),
            })
        except Exception:
            pass

    df = pd.DataFrame(linhas).sort_values("Total (R$)", ascending=False).reset_index(drop=True)
    return df, None


def cq_ranking_ltv_tag(tag: str, log):
    """
    Pergunta natural: "Qual o ranking de gasto dos clientes B2B?"
    Cadeia de chamadas:
      1. listar_clientes_por_tag(tag)       → identifica os clientes
      2. calcular_total_gasto_cliente × N    → LTV individual no CSV
    Saída: ranking ordenado por gasto total
    """
    log.info("**Passo 1 / 2** — Buscando clientes `" + tag + "` na base NoSQL…")
    clientes_raw = executar_multiplas_ferramentas([
        ("listar_clientes_por_tag", {"tag_procurada": tag}),
    ])[0]

    if "❌" in clientes_raw:
        return None, clientes_raw
    try:
        clientes = json.loads(clientes_raw)
    except Exception as e:
        return None, f"Erro ao interpretar resposta MCP: {e}"

    if not clientes:
        return None, f"Nenhum cliente encontrado com a tag '{tag}'."

    log.info(f"**Passo 2 / 2** — Calculando LTV de {len(clientes)} cliente(s)…")
    chamadas = [("calcular_total_gasto_cliente", {"id_cliente": c["id"]}) for c in clientes]
    gastos_raw = executar_multiplas_ferramentas(chamadas)

    linhas = []
    for cliente, gasto_raw in zip(clientes, gastos_raw):
        try:
            g = json.loads(gasto_raw)
            linhas.append({
                "ID":          cliente["id"],
                "Nome":        cliente["nome_anonimizado"],
                "Compras":     g["compras"],
                "Total (R$)":  g["total"],
            })
        except Exception:
            pass

    df = pd.DataFrame(linhas).sort_values("Total (R$)", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))
    return df, None


def cq_catalogo_em_moedas(log):
    """
    Pergunta natural: "Qual o preço médio dos produtos em dólar e euro?"
    Cadeia de chamadas:
      1. obter_metricas_produtos(categoria)  → preços médios em BRL (SQLite)
      2. consultar_cotacao_moedas()           → taxa de câmbio USD e EUR
    Saída: catálogo de categorias com preço em 3 moedas
    """
    log.info("**Passo 1 / 1** — Buscando métricas de produtos e cotações em paralelo…")
    res = executar_multiplas_ferramentas([
        ("obter_metricas_produtos", {"dimensao": "categoria"}),
        ("consultar_cotacao_moedas", {}),
    ])
    produtos_raw, cotacao_raw = res[0], res[1]

    if "❌" in produtos_raw:
        return None, produtos_raw
    try:
        produtos = json.loads(produtos_raw)
        cotacao  = json.loads(cotacao_raw)
        usd = float(cotacao["USD"]["valor"])
        eur = float(cotacao["EUR"]["valor"])
    except Exception as e:
        return None, f"Erro ao interpretar resposta MCP: {e}"

    linhas = []
    for row in produtos["dados"]:
        categoria, preco_brl = row[0], round(row[1], 2)
        linhas.append({
            "Categoria":           categoria,
            "Preço Médio (R$)":    preco_brl,
            "Preço Médio (USD)":   round(preco_brl / usd, 2),
            "Preço Médio (EUR)":   round(preco_brl / eur, 2),
        })

    df = pd.DataFrame(linhas).sort_values("Preço Médio (R$)", ascending=False).reset_index(drop=True)
    return df, None


def cq_novos_acima_da_media(log):
    """
    Pergunta natural: "Quais clientes novos estão gastando acima da média do grupo?"
    Cadeia de chamadas:
      1. listar_clientes_por_tag(novo)       → identifica os clientes novos
      2. calcular_total_gasto_cliente × N    → LTV individual
    Saída: dois dataframes — acima e abaixo da média, com destaque
    """
    log.info("**Passo 1 / 2** — Buscando clientes `novo` na base NoSQL…")
    clientes_raw = executar_multiplas_ferramentas([
        ("listar_clientes_por_tag", {"tag_procurada": "novo"}),
    ])[0]

    if "❌" in clientes_raw:
        return None, None, clientes_raw
    try:
        clientes = json.loads(clientes_raw)
    except Exception as e:
        return None, None, f"Erro: {e}"

    if not clientes:
        return None, None, "Nenhum cliente novo encontrado."

    log.info(f"**Passo 2 / 2** — Calculando gasto de {len(clientes)} clientes novos no CSV…")
    chamadas = [("calcular_total_gasto_cliente", {"id_cliente": c["id"]}) for c in clientes]
    gastos_raw = executar_multiplas_ferramentas(chamadas)

    linhas = []
    for cliente, gasto_raw in zip(clientes, gastos_raw):
        try:
            g = json.loads(gasto_raw)
            linhas.append({
                "ID":         cliente["id"],
                "Nome":       cliente["nome_anonimizado"],
                "Compras":    g["compras"],
                "Total (R$)": g["total"],
            })
        except Exception:
            pass

    df = pd.DataFrame(linhas)
    media = df["Total (R$)"].mean()
    df_acima  = df[df["Total (R$)"] >  media].sort_values("Total (R$)", ascending=False).reset_index(drop=True)
    df_abaixo = df[df["Total (R$)"] <= media].sort_values("Total (R$)", ascending=False).reset_index(drop=True)
    return df_acima, df_abaixo, None


def exibir_resultado(resultado_texto: str):
    """Função utilitária para renderizar JSON como Tabela ou Texto."""
    # Verifica se é uma mensagem de erro/bloqueio vinda dos Guardrails
    if "❌" in resultado_texto or "⚠️" in resultado_texto:
        st.error(resultado_texto)
        return
        
    try:
        dados = json.loads(resultado_texto)
        if isinstance(dados, dict) and dados.get("tipo") == "grafico" and dados.get("dados"):
            df = pd.DataFrame(dados["dados"])
            x_coluna = dados.get("x_coluna")
            y_coluna = dados.get("y_coluna")
            tipo_grafico = dados.get("grafico", "bar")

            if x_coluna not in df.columns or y_coluna not in df.columns:
                st.error("Resposta de gráfico inválida: colunas esperadas não foram retornadas pelo servidor MCP.")
                return

            st.markdown(f"**{dados.get('titulo', 'Gráfico gerado pelo servidor MCP')}**")
            df_plot = df.set_index(x_coluna)[[y_coluna]]
            if tipo_grafico == "line":
                st.line_chart(df_plot, use_container_width=True)
            else:
                st.bar_chart(df_plot, use_container_width=True)
            st.dataframe(df, use_container_width=True)
            return
        # Se for uma lista ou um dicionário que contém "dados" (como o nosso SQLite)
        if isinstance(dados, dict) and "dados" in dados and "colunas" in dados:
            df = pd.DataFrame(dados["dados"], columns=dados["colunas"])
            st.dataframe(df, use_container_width=True)
        elif isinstance(dados, list):
            st.dataframe(pd.DataFrame(dados), use_container_width=True)
        else:
            st.json(dados)
    except json.JSONDecodeError:
        st.info(resultado_texto)


def _render_conversation_trace(trace: list):
    with st.expander("Raciocínio do Agente", expanded=False):
        for indice, step in enumerate(trace, start=1):
            if step["tipo"] == "ferramentas_descobertas":
                st.markdown(f"**Passo {indice} — Ferramentas disponíveis**")
                st.code(", ".join(step.get("ferramentas", [])), language=None)
            elif step["tipo"] == "chamada":
                st.markdown(f"**Passo {indice} — Chamada de ferramenta**")
                st.markdown(f"Ferramenta: `{step['ferramenta']}`")
                if step.get("argumentos"):
                    st.json(step["argumentos"])
                else:
                    st.caption("Sem parâmetros")
            elif step["tipo"] == "resultado":
                st.markdown(f"**Passo {indice} — Resultado da ferramenta**")
                st.caption(f"Retorno de `{step['ferramenta']}`")
                exibir_resultado(step["conteudo"])
            elif step["tipo"] == "resposta_final":
                st.markdown(f"**Passo {indice} — Resposta final**")
                st.markdown(step.get("conteudo", ""))


def _render_chart_from_conversation_trace(trace: list):
    for step in reversed(trace):
        if step.get("tipo") != "resultado":
            continue
        try:
            dados = json.loads(step["conteudo"])
        except Exception:
            continue
        if isinstance(dados, dict) and dados.get("tipo") == "grafico" and dados.get("dados"):
            exibir_resultado(step["conteudo"])
            break

# -----------------------------------------------------------------------------
# INTERFACE GRÁFICA (UI)
# -----------------------------------------------------------------------------
st.title("🤖 Painel do Agente de Dados (MCP Client)")
st.markdown("""
Este painel simula um **LLM** a interagir com os sistemas da empresa. 
Através do protocolo MCP, o modelo pede dados e recebe respostas estruturadas, sem conhecer a infraestrutura subjacente.
""")

# Criar abas para separar os ecossistemas
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "📊 SQL (Relacional)",
    "🗂️ NoSQL (Documentos)",
    "📈 CSV (Big Data)",
    "🌐 API Externa",
    "🤖 Agente Conversacional",
])

# --- ABA 1: SQLITE ---
with aba1:
    st.header("Análise de Produtos (SQLite)")
    st.write("O servidor expõe agregações. Tente aceder a dimensões de negócio.")
    st.caption("Também é possível pedir ao servidor MCP que transforme uma tabela em gráfico para o Streamlit renderizar.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        nivel_acesso_sql = st.selectbox(
            "Nível de acesso SQL:",
            options=["agente", "analista", "diretoria"],
            help="Dimensões estratégicas como margem, lucro, custo e fornecedor exigem acesso de diretoria, mas não estão materializadas neste dataset de laboratório.",
        )
        dimensao_sql = st.selectbox(
            "Dimensão para agrupar preço médio:", 
            options=["categoria", "margem", "lucro", "fornecedor"],
            help="Margem, lucro e fornecedor dependem do nível de acesso escolhido acima."
        )
        if st.button("Executar Query SQL", key="btn_sql"):
            resultado = executar_ferramenta(
                "obter_metricas_produtos",
                {"dimensao": dimensao_sql, "nivel_acesso": nivel_acesso_sql},
            )
            with col2:
                exibir_resultado(resultado)
        if st.button("Gerar gráfico das métricas", key="btn_sql_chart"):
            resultado = executar_ferramenta(
                "obter_metricas_produtos",
                {"dimensao": dimensao_sql, "nivel_acesso": nivel_acesso_sql},
            )
            with col2:
                if "❌" in resultado or "⚠️" in resultado:
                    exibir_resultado(resultado)
                else:
                    try:
                        dados = json.loads(resultado)
                        df = pd.DataFrame(dados["dados"], columns=dados["colunas"])
                        payload = executar_ferramenta(
                            "gerar_grafico_dataframe",
                            {
                                "dataframe_json": df.to_json(orient="records", force_ascii=False),
                                "x_coluna": dados["colunas"][0],
                                "y_coluna": dados["colunas"][1],
                                "tipo": "bar",
                                "titulo": f"Preço médio por {dados['colunas'][0]}",
                            },
                        )
                        exibir_resultado(payload)
                    except Exception as e:
                        st.error(f"Erro ao preparar gráfico no cliente: {e}")

# --- ABA 2: NOSQL JSON ---
with aba2:
    st.header("Busca de Clientes (JSON / MongoDB Simulado)")
    st.write("A IA pode procurar listas de clientes, mas regras de LGPD/GDPR são aplicadas no servidor.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        tag_nosql = st.selectbox(
            "Filtrar clientes pela tag:", 
            options=["vip", "novo", "b2b", "inadimplente", "fraude"],
            help="'inadimplente' e 'fraude' ativarão bloqueios de privacidade."
        )
        if st.button("Buscar no NoSQL", key="btn_nosql"):
            resultado = executar_ferramenta("listar_clientes_por_tag", {"tag_procurada": tag_nosql})
            with col2:
                exibir_resultado(resultado)

# --- ABA 3: CSV ---
with aba3:
    st.header("Delegação de Cálculo em Big Data (CSV)")
    st.write("Em vez de ler 20.000 linhas, o Agente delega o cálculo de LTV (Lifetime Value) para o servidor.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        id_cliente_csv = st.text_input("ID do Cliente:", value="C0015")
        if st.button("Calcular Gasto Total", key="btn_csv"):
            resultado = executar_ferramenta("calcular_total_gasto_cliente", {"id_cliente": id_cliente_csv})
            with col2:
                exibir_resultado(resultado)

# --- ABA 4: API ---
with aba4:
    st.header("Enriquecimento com Dados em Tempo Real (API REST)")
    st.write("O agente consulta as taxas de câmbio atuais sempre que precisa internacionalizar um valor.")
    
    if st.button("Consultar Cotação de Moedas (USD/EUR)", key="btn_api"):
        resultado = executar_ferramenta("consultar_cotacao_moedas", {})
        exibir_resultado(resultado)

# --- ABA 5: AGENTE CONVERSACIONAL ---
with aba5:
    st.header("🤖 Agente Conversacional")
    st.markdown("""
    O **LLM é o único orquestrador**: ele descobre as ferramentas MCP, decide quais invocar,
    interpreta os resultados e consolida a resposta final.
    """)

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    modelos_chat = [
        "openai/gpt-4o-mini",
        "deepseek/deepseek-v3.2",
        "x-ai/grok-4.1-fast",
        "google/gemini-3.1-flash-lite-preview",
        "nvidia/nemotron-3-super-120b-a12b",
        "google/gemma-4-31b-it",
    ]

    col_cfg1, col_cfg2 = st.columns([2, 1])
    with col_cfg1:
        modelo_chat = st.selectbox("Modelo do agente:", modelos_chat, key="chat_modelo_main")
    with col_cfg2:
        if st.button("🗑️ Limpar conversa", key="btn_clear_conv_main", use_container_width=True):
            st.session_state["chat_historico_main"] = []
            st.session_state["chat_display_main"] = []
            st.session_state.pop("chat_input_main", None)
            st.session_state.pop("chat_pending_main", None)
            st.rerun()

    if not openrouter_key:
        st.warning("Defina OPENROUTER_API_KEY no arquivo .env para usar o agente conversacional.")
    else:
        st.caption("A chave do OpenRouter é carregada automaticamente do .env.")

    st.subheader("📋 Exemplos de requisições")
    exemplos = [
        "Quais categorias de produto têm maior preço médio?",
        "Liste os clientes VIP e mostre quanto cada um gastou",
        "Gere um gráfico de barras com o preço médio por categoria",
        "Calcule o LTV dos clientes B2B e ordene do maior para o menor",
        "Quanto o cliente C0015 gastou? Converta o valor para euro",
        "Compare as cotações de dólar, euro e bitcoin agora",
        "Qual era a cotação do dólar em 01/01/2025?",
        "Tente acessar a margem de lucro dos produtos",
        "Liste os clientes inadimplentes",
    ]

    col_ex1, col_ex2, col_ex3 = st.columns(3)
    colunas_ex = [col_ex1, col_ex2, col_ex3]
    for i, exemplo in enumerate(exemplos):
        with colunas_ex[i % 3]:
            if st.button(exemplo, key=f"conv_ex_{i}", use_container_width=True):
                st.session_state["chat_pending_main"] = exemplo

    st.divider()

    if "chat_historico_main" not in st.session_state:
        st.session_state["chat_historico_main"] = []
    if "chat_display_main" not in st.session_state:
        st.session_state["chat_display_main"] = []

    for entrada in st.session_state["chat_display_main"]:
        with st.chat_message(entrada["role"]):
            if entrada["role"] == "user":
                st.markdown(entrada["content"])
            else:
                trace = entrada.get("trace", [])
                if trace:
                    _render_conversation_trace(trace)
                st.markdown(entrada["content"])
                if trace:
                    _render_chart_from_conversation_trace(trace)

    pergunta = st.text_area(
        "Sua pergunta para o agente:",
        value=st.session_state.get("chat_pending_main", ""),
        height=80,
        placeholder="Ex.: Gere um gráfico de barras com o preço médio por categoria.",
        key="chat_input_main",
    )

    executar_chat = st.button("🚀 Enviar ao agente", key="btn_conv_main", type="primary")
    if executar_chat:
        st.session_state["chat_pending_main"] = ""
        if not openrouter_key:
            st.warning("Defina OPENROUTER_API_KEY no .env antes de usar o agente conversacional.")
        elif not pergunta.strip():
            st.warning("Digite uma pergunta antes de executar.")
        else:
            pergunta = pergunta.strip()
            st.session_state["chat_display_main"].append({"role": "user", "content": pergunta})
            with st.chat_message("user"):
                st.markdown(pergunta)

            with st.chat_message("assistant"):
                with st.spinner(f"Agente `{modelo_chat}` a raciocinar…"):
                    try:
                        trace, resposta = agente_llm_loop(
                            st.session_state["chat_historico_main"],
                            pergunta,
                            openrouter_key,
                            modelo_chat,
                        )
                        _render_conversation_trace(trace)
                        st.markdown(resposta)
                        _render_chart_from_conversation_trace(trace)

                        st.session_state["chat_historico_main"].append(
                            {"role": "user", "content": pergunta}
                        )
                        st.session_state["chat_historico_main"].append(
                            {"role": "assistant", "content": resposta}
                        )
                        st.session_state["chat_display_main"].append(
                            {"role": "assistant", "content": resposta, "trace": trace}
                        )
                    except Exception as e:
                        st.error(f"Erro no Agente LLM: {e}")

st.divider()
st.caption("Minicurso: Arquiteturas de Dados e IA Generativa com Model Context Protocol (MCP).")