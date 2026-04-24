"""
mcp_core.py — Motor de comunicação MCP e loop agêntico LLM.
Módulo compartilhado entre app.py e pages/agente_conversacional.py.
"""
import os
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

# Caminho absoluto para server.py (mesmo diretório de mcp_core.py)
_SERVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server.py')


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(command="python", args=[_SERVER_PATH])


# -----------------------------------------------------------------------------
# PRIMITIVAS MCP
# -----------------------------------------------------------------------------

async def mcp_call_tool_async(tool_name: str, arguments: dict) -> str:
    """Abre uma sessão MCP, executa uma ferramenta e retorna o resultado."""
    try:
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                return result.content[0].text
    except Exception as e:
        return f"Erro de comunicação MCP: {str(e)}"


async def mcp_multi_call_async(chamadas: list) -> list:
    """Executa múltiplas ferramentas em sequência numa única sessão MCP."""
    resultados = []
    try:
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for tool_name, arguments in chamadas:
                    result = await session.call_tool(tool_name, arguments=arguments)
                    resultados.append(result.content[0].text)
    except Exception as e:
        return [f"Erro de comunicação MCP: {str(e)}"]
    return resultados


# -----------------------------------------------------------------------------
# LOOP AGÊNTICO — orquestrado pelo LLM via OpenRouter
# -----------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "Você é um agente de análise de dados corporativos experiente. "
    "Use as ferramentas disponíveis para responder ao usuário em português. "
    "Quando os dados vierem de múltiplas ferramentas, combine-os numa resposta "
    "clara, estruturada e objetiva. Mantenha o contexto da conversa anterior. "
    "Nunca invente dados — use sempre as ferramentas para obtê-los. "
    "Quando o usuário pedir gráfico, visualização, plot, barras, linhas, evolução ou comparação visual, "
    "obtenha primeiro os dados tabulares necessários e depois chame a ferramenta gerar_grafico_dataframe. "
    "Ao usar essa ferramenta, envie dataframe_json no formato records com colunas adequadas para x_coluna e y_coluna."
)


async def agente_llm_loop_async(
    historico: list,       # [{"role": "user"|"assistant", "content": str}, ...]
    nova_pergunta: str,
    api_key: str,
    model: str,
) -> tuple:
    """
    Loop agêntico multi-turn genuíno:
      1. Descobre as ferramentas do servidor MCP via list_tools().
      2. Converte os schemas MCP para o formato function-calling OpenAI.
      3. Envia histórico + nova pergunta ao LLM.
      4. Executa no servidor MCP cada tool_call decidida pelo LLM.
      5. Repete até o LLM gerar uma resposta final sem tool_calls.

    Retorna (trace, resposta_final):
      - trace: lista de passos para exibição transparente na UI
      - resposta_final: texto final do agente
    """
    llm = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    trace = []

    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Descobre ferramentas dinamicamente — o LLM não conhece o servidor
            mcp_tools_resp = await session.list_tools()
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.inputSchema,
                    },
                }
                for t in mcp_tools_resp.tools
            ]
            trace.append({
                "tipo": "ferramentas_descobertas",
                "ferramentas": [t.name for t in mcp_tools_resp.tools],
            })

            # Constrói o contexto: sistema + histórico + nova pergunta
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                *historico,
                {"role": "user", "content": nova_pergunta},
            ]

            resposta_final = ""

            for _ in range(10):  # limite de segurança: 10 iterações
                response = await llm.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )
                msg = response.choices[0].message

                # Constrói a mensagem do assistente para histórico interno
                assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                messages.append(assistant_msg)

                # Sem tool_calls → resposta final
                if not msg.tool_calls:
                    resposta_final = msg.content or ""
                    trace.append({"tipo": "resposta_final", "conteudo": resposta_final})
                    break

                # Executa cada chamada de ferramenta no servidor MCP
                for tc in msg.tool_calls:
                    nome = tc.function.name
                    args = json.loads(tc.function.arguments)
                    trace.append({"tipo": "chamada", "ferramenta": nome, "argumentos": args})

                    result = await session.call_tool(nome, arguments=args)
                    conteudo = result.content[0].text
                    trace.append({"tipo": "resultado", "ferramenta": nome, "conteudo": conteudo})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": conteudo,
                    })

    return trace, resposta_final


def agente_llm_loop(
    historico: list,
    nova_pergunta: str,
    api_key: str,
    model: str,
) -> tuple:
    """Wrapper síncrono do loop agêntico (para uso no Streamlit)."""
    return asyncio.run(agente_llm_loop_async(historico, nova_pergunta, api_key, model))
