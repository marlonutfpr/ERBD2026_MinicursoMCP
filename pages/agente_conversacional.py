"""
pages/agente_conversacional.py
Página dedicada ao Agente Conversacional MCP orquestrado por LLM.

Separada de app.py para que st.chat_input() funcione no nível
raiz da página (não dentro de st.tabs, onde é proibido).
"""
import sys
import os

# Garante que mcp_core.py (em mcp/) seja encontrado
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, 'mcp'))

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))

import streamlit as st
import json
from mcp_core import agente_llm_loop

st.set_page_config(
    page_title="Agente Conversacional MCP",
    page_icon="🤖",
    layout="wide",
)

# -----------------------------------------------------------------------------
# SIDEBAR — configuração do LLM
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuração do Agente")
    _env_key = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_key = _env_key.strip()
    _MODELOS = [
        "openai/gpt-4o-mini",
        "deepseek/deepseek-v3.2",
        "x-ai/grok-4.1-fast",
        "google/gemini-3.1-flash-lite-preview",
        "nvidia/nemotron-3-super-120b-a12b",
        "google/gemma-4-31b-it",
    ]
    modelo = st.selectbox("Modelo", _MODELOS)
    st.caption("[Ver todos os modelos disponíveis](https://openrouter.ai/models)")

    if openrouter_key:
        st.success(f"Modelo ativo: `{modelo}`")
        st.caption("OPENROUTER_API_KEY carregada automaticamente do arquivo .env.")
    else:
        st.warning("OPENROUTER_API_KEY não encontrada no arquivo .env.")

    st.divider()
    if st.button("🗑️ Limpar conversa", use_container_width=True):
        st.session_state["chat_historico"] = []
        st.session_state["chat_display"] = []
        st.rerun()


# -----------------------------------------------------------------------------
# HELPER — renderiza o raciocínio do agente (trace)
# -----------------------------------------------------------------------------
def _render_trace(trace: list):
    for step in trace:
        if step["tipo"] == "ferramentas_descobertas":
            st.markdown("**🗂️ Ferramentas descobertas no servidor MCP:**")
            st.code(", ".join(step["ferramentas"]), language=None)

        elif step["tipo"] == "chamada":
            st.markdown(f"**🔧 Chamando `{step['ferramenta']}`**")
            if step["argumentos"]:
                st.json(step["argumentos"])
            else:
                st.caption("*(sem parâmetros)*")

        elif step["tipo"] == "resultado":
            st.markdown(f"**📥 Resposta de `{step['ferramenta']}`:**")
            try:
                st.json(json.loads(step["conteudo"]))
            except Exception:
                st.code(step["conteudo"], language=None)


# -----------------------------------------------------------------------------
# CABEÇALHO
# -----------------------------------------------------------------------------
st.title("🤖 Agente Conversacional MCP")
st.markdown("""
O **LLM é o único orquestrador**: descobre dinamicamente as ferramentas do servidor MCP,  
decide quais invocar, interpreta os resultados e mantém contexto ao longo de toda a conversa.  
Nenhuma lógica de roteamento foi codificada na aplicação.
""")

if not openrouter_key:
    st.info("🔑 Defina **OPENROUTER_API_KEY** no arquivo `.env` para começar.")
    st.stop()

# -----------------------------------------------------------------------------
# SUGESTÕES DE PERGUNTAS
# -----------------------------------------------------------------------------
with st.expander("💡 Sugestões de perguntas", expanded=True):
    sugestoes = [
        "Quais categorias de produto têm maior preço médio?",
        "Liste os clientes VIP e mostre quanto cada um gastou",
        "Qual o preço médio dos produtos em dólar e euro hoje?",
        "Calcule o LTV dos clientes B2B e ordene do maior para o menor",
        "Quais clientes novos estão acima da média de gastos do grupo?",
        "Quanto o cliente C0015 gastou? Converta o valor para euro",
        "Compare as cotações de dólar, euro e bitcoin agora",
        "Qual era a cotação do dólar em 01/01/2025?",
        "Tente acessar a margem de lucro dos produtos",
        "Liste os clientes inadimplentes",
    ]
    cols = st.columns(2)
    for i, sug in enumerate(sugestoes):
        if cols[i % 2].button(sug, key=f"sug_{i}", use_container_width=True):
            st.session_state["_mensagem_pendente"] = sug

# -----------------------------------------------------------------------------
# ESTADO DA CONVERSA
# -----------------------------------------------------------------------------
if "chat_historico" not in st.session_state:
    st.session_state["chat_historico"] = []   # somente user/assistant para o LLM

if "chat_display" not in st.session_state:
    st.session_state["chat_display"] = []     # inclui trace para exibição

# -----------------------------------------------------------------------------
# EXIBE HISTÓRICO DA CONVERSA
# -----------------------------------------------------------------------------
for entrada in st.session_state["chat_display"]:
    with st.chat_message(entrada["role"]):
        if entrada["role"] == "user":
            st.markdown(entrada["content"])
        else:
            trace = entrada.get("trace", [])
            if trace:
                with st.expander("🔍 Raciocínio do Agente", expanded=False):
                    _render_trace(trace)
            st.markdown(entrada["content"])

# -----------------------------------------------------------------------------
# INPUT — chat_input nativo (funciona porque estamos no nível raiz da página)
# -----------------------------------------------------------------------------
mensagem_pendente = st.session_state.pop("_mensagem_pendente", None)
pergunta = st.chat_input(f"Pergunte ao Agente ({modelo})…") or mensagem_pendente

if pergunta:
    pergunta = pergunta.strip()

    # Exibe a mensagem do usuário imediatamente
    st.session_state["chat_display"].append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    # Chama o agente e exibe a resposta
    with st.chat_message("assistant"):
        with st.spinner(f"Agente `{modelo}` a raciocinar…"):
            try:
                trace, resposta = agente_llm_loop(
                    st.session_state["chat_historico"],
                    pergunta,
                    openrouter_key,
                    modelo,
                )

                with st.expander("🔍 Raciocínio do Agente", expanded=True):
                    _render_trace(trace)

                st.markdown(resposta)

                # Atualiza histórico para o próximo turno (apenas user/assistant)
                st.session_state["chat_historico"].append(
                    {"role": "user", "content": pergunta}
                )
                st.session_state["chat_historico"].append(
                    {"role": "assistant", "content": resposta}
                )
                st.session_state["chat_display"].append({
                    "role": "assistant",
                    "content": resposta,
                    "trace": trace,
                })

            except Exception as e:
                st.error(f"Erro no Agente LLM: {e}")
