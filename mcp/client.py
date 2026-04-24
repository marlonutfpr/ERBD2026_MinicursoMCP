import os
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json

# Caminho absoluto para server.py (mesmo diretório de client.py)
_SERVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server.py')

async def rodar_agente_simulado():
    print("="*70)
    print("🤖 INICIALIZANDO AGENTE DE DADOS (Cenários de Sucesso e Bloqueio)")
    print("="*70)
    
    server_params = StdioServerParameters(command="python", args=[_SERVER_PATH])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[✓] Conexão MCP estabelecida via STDIO.\n")

            # --- CÁLCULO RELACIONAL (SQLITE) - SUCESSO ---
            print("📊 FASE 1: ACESSO PERMITIDO (SQL)")
            print("  [Agente Executa]: obter_metricas_produtos(dimensao='categoria')")
            res_permitida = await session.call_tool("obter_metricas_produtos", arguments={"dimensao": "categoria"})
            print(f"    -> Resposta: {res_permitida.content[0].text[:150]}...\n")

            # --- CÁLCULO RELACIONAL (SQLITE) - BLOQUEIO ---
            print("🛡️ FASE 2: TENTATIVA DE ACESSO RESTRITO (SQL - Margem de Lucro)")
            print("  [O utilizador pediu à IA para analisar os lucros e ela tenta invocar a ferramenta]")
            print("  [Agente Executa]: obter_metricas_produtos(dimensao='margem')")
            res_bloqueada1 = await session.call_tool("obter_metricas_produtos", arguments={"dimensao": "margem"})
            # Exibindo o aviso de segurança gerado pelo servidor:
            print(f"    -> Resposta do Servidor: \033[91m{res_bloqueada1.content[0].text}\033[0m\n")

            # --- NOSQL (JSON) - SUCESSO COM ANONIMIZAÇÃO ---
            print("🗂️ FASE 3: ACESSO PERMITIDO (NoSQL - Clientes VIP)")
            print("  [Agente Executa]: listar_clientes_por_tag(tag_procurada='vip')")
            res_vip = await session.call_tool("listar_clientes_por_tag", arguments={"tag_procurada": "vip"})
            print(f"    -> Resposta: {res_vip.content[0].text[:150]}...\n")

            # --- NOSQL (JSON) - BLOQUEIO LGPD ---
            print("🛡️ FASE 4: TENTATIVA DE ACESSO SENSÍVEL (NoSQL - Inadimplentes)")
            print("  [A IA tenta compilar uma lista de devedores para enviar por email]")
            print("  [Agente Executa]: listar_clientes_por_tag(tag_procurada='inadimplente')")
            res_bloqueada2 = await session.call_tool("listar_clientes_por_tag", arguments={"tag_procurada": "inadimplente"})
            print(f"    -> Resposta do Servidor: \033[91m{res_bloqueada2.content[0].text}\033[0m\n")

            # --- DELEGAÇÃO DE BIG DATA (CSV) ---
            print("📈 FASE 5: DELEGAÇÃO DE BIG DATA (CSV)")
            print("  [A IA delega o cálculo em vez de ler milhares de linhas]")
            print("  [Agente Executa]: calcular_total_gasto_cliente(id_cliente='C0012')")
            res_csv = await session.call_tool("calcular_total_gasto_cliente", arguments={"id_cliente": "C0012"})
            print(f"    -> Resposta: {res_csv.content[0].text}\n")
            
            print("🎯 CONCLUSÃO: O protocolo MCP garante que o poder cognitivo fica na IA (LLM), mas o poder de GOVERNANÇA e SEGURANÇA de dados continua do lado da Engenharia de Dados!")

if __name__ == "__main__":
    asyncio.run(rodar_agente_simulado())