import os
from mcp.server.fastmcp import FastMCP
import sqlite3
import csv
import json
import requests
from typing import List, Dict, Any
import pandas as pd

mcp = FastMCP("DataIntegrationServer_Seguro")

# Resolve o diretório data/ relativo à raiz do projeto (um nível acima de mcp/)
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, 'data')

# =====================================================================
# FERRAMENTAS RELACIONAIS (SQLITE) - COM LÓGICA NO SERVIDOR
# =====================================================================

@mcp.tool()
def obter_metricas_produtos(dimensao: str) -> str:
    """
    Obtém o preço médio dos produtos agrupados por uma dimensão de negócio.
    Parâmetros aceites para 'dimensao': 'categoria'.
    
    Tentar aceder a dimensões financeiras restritas resultará num bloqueio.
    """
    dimensao = dimensao.lower().strip()
    
    # 🛡️ EXEMPLO DE BLOQUEIO 1: Governança Corporativa e RBAC (Role-Based Access Control)
    # Bloqueamos o acesso da IA a colunas/dados estratégicos que não lhe competem.
    dimensoes_proibidas = ['custo', 'margem', 'fornecedor', 'lucro']
    if dimensao in dimensoes_proibidas:
        return f"❌ BLOQUEIO DE GOVERNANÇA: O acesso à dimensão '{dimensao}' é estritamente reservado à diretoria (C-Level). O perfil deste Agente não possui autorização."
    
    # Validação rigorosa de parâmetros (evita SQL Injection, pois não concatenamos input cego)
    if dimensao != 'categoria':
        return f"⚠️ Erro: A dimensão '{dimensao}' não é suportada por esta ferramenta."

    # A LÓGICA DE DADOS FICA NO SERVIDOR:
    # A IA não sabe se isto é SQLite, Postgres ou Oracle. Ela apenas pede a métrica.
    query = f"SELECT {dimensao}, AVG(preco) as preco_medio FROM produtos GROUP BY {dimensao};"
    
    try:
        conn = sqlite3.connect(os.path.join(DATA_DIR, 'produtos.db'))
        cursor = conn.cursor()
        cursor.execute(query)
        resultados = cursor.fetchall()
        colunas = [description[0] for description in cursor.description]
        conn.close()
        
        return json.dumps({"colunas": colunas, "dados": resultados}, ensure_ascii=False)
    except Exception as e:
        return f"Erro interno do banco de dados: {str(e)}"

# =====================================================================
# FERRAMENTAS NOSQL (JSON) - COM PROTEÇÃO DE PRIVACIDADE
# =====================================================================

@mcp.tool()
def listar_clientes_por_tag(tag_procurada: str) -> str:
    """
    Pesquisa na base de dados de clientes (NoSQL) todos os clientes que possuam
    uma tag específica de marketing ou perfil (ex: 'vip', 'novo').
    """
    tag_procurada = tag_procurada.lower().strip()
    
    # 🛡️ EXEMPLO DE BLOQUEIO 2: Compliance e LGPD / GDPR
    # Bloqueamos a IA de vasculhar listas de clientes em situações sensíveis.
    tags_sensiveis = ['inadimplente', 'fraude', 'investigacao', 'processo_juridico']
    if tag_procurada in tags_sensiveis:
        return f"❌ BLOQUEIO DE COMPLIANCE (LGPD/GDPR): A listagem de clientes com a tag '{tag_procurada}' viola as políticas de privacidade de dados sensíveis. Pedido registado e negado."

    try:
        with open(os.path.join(DATA_DIR, 'clientes.json'), 'r', encoding='utf-8') as f:
            clientes = json.load(f)
        
        resultados = []
        for id_cliente, dados in clientes.items():
            if tag_procurada in dados.get("tags", []):
                # Aplicamos máscara/anonimização nos dados retornados (outro padrão de segurança)
                nome_mascarado = dados.get("nome")[:3] + "***" + dados.get("nome")[-2:]
                resultados.append({"id": id_cliente, "nome_anonimizado": nome_mascarado})
                
        return json.dumps(resultados[:10], ensure_ascii=False)
    except Exception as e:
        return f"Erro ao pesquisar JSON: {str(e)}"

# =====================================================================
# FERRAMENTAS DE BIG DATA (CSV) E API (Mantidas com lógica encapsulada)
# =====================================================================

@mcp.tool()
def calcular_total_gasto_cliente(id_cliente: str) -> str:
    """
    Analisa o Big Data de vendas e calcula o valor total gasto por um cliente.
    Recebe apenas o ID do cliente.
    """
    total_gasto = 0.0
    quantidade_compras = 0
    try:
        with open(os.path.join(DATA_DIR, 'vendas.csv'), 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for linha in reader:
                if linha['id_cliente'] == id_cliente:
                    total_gasto += float(linha['valor_total'])
                    quantidade_compras += 1
                    
        return json.dumps({"id_cliente": id_cliente, "compras": quantidade_compras, "total": round(total_gasto, 2)}, ensure_ascii=False)
    except Exception as e:
        return f"Erro ao processar ficheiro CSV: {str(e)}"

@mcp.tool()
def consultar_cotacao_moedas(moeda: str = "USD,EUR", data: str = "") -> str:
    """
    Consulta a cotação de uma ou mais moedas em relação ao BRL.
    - moeda: sigla(s) separadas por vírgula (ex: 'USD', 'EUR', 'USD,EUR,GBP').
             Moedas suportadas: USD, EUR, GBP, JPY, BTC, ETH, CAD, ARS, CHF, AUD.
    - data: data no formato YYYY-MM-DD para consulta histórica (vazio = cotação atual).
    """
    MOEDAS_VALIDAS = {"USD", "EUR", "GBP", "JPY", "BTC", "ETH", "CAD", "ARS", "CHF", "AUD"}
    moedas = [m.strip().upper() for m in moeda.split(",") if m.strip()]
    moedas_invalidas = [m for m in moedas if m not in MOEDAS_VALIDAS]
    if moedas_invalidas:
        return f"⚠️ Moeda(s) não suportada(s): {', '.join(moedas_invalidas)}. Válidas: {', '.join(sorted(MOEDAS_VALIDAS))}"

    try:
        resultado = {}
        if not data:
            # Cotação atual — endpoint /last/ suporta múltiplos pares
            pares = ",".join(f"{m}-BRL" for m in moedas)
            response = requests.get(f"https://economia.awesomeapi.com.br/last/{pares}", timeout=5)
            response.raise_for_status()
            dados = response.json()
            for m in moedas:
                chave = f"{m}BRL"
                if chave in dados:
                    resultado[m] = {
                        "valor": dados[chave]["ask"],
                        "data":  dados[chave]["create_date"][:10],
                    }
        else:
            # Cotação histórica — endpoint /json/daily/ com start_date e end_date
            data_fmt = data.replace("-", "")  # YYYYMMDD
            for m in moedas:
                response = requests.get(
                    f"https://economia.awesomeapi.com.br/json/daily/{m}-BRL/1",
                    params={"start_date": data_fmt, "end_date": data_fmt},
                    timeout=5,
                )
                response.raise_for_status()
                dados = response.json()
                resultado[m] = {
                    "valor": dados[0]["ask"] if dados else "N/D",
                    "data":  data,
                }
        return json.dumps(resultado, ensure_ascii=False)
    except Exception as e:
        return f"Falha na API financeira: {str(e)}"


@mcp.tool()
def gerar_grafico_dataframe(
    dataframe_json: str,
    x_coluna: str,
    y_coluna: str,
    tipo: str = "bar",
    titulo: str = "Gráfico gerado pelo MCP",
) -> str:
    """
    Recebe um DataFrame serializado em JSON e devolve uma especificação de gráfico
    com os dados necessários para o cliente Streamlit renderizar nativamente.

    Parâmetros:
    - dataframe_json: JSON serializado no formato 'records'.
    - x_coluna: nome da coluna para o eixo X.
    - y_coluna: nome da coluna numérica para o eixo Y.
    - tipo: 'bar' ou 'line'.
    - titulo: título do gráfico.
    """
    tipos_suportados = {"bar", "line"}
    if tipo not in tipos_suportados:
        return f"⚠️ Tipo de gráfico não suportado: {tipo}. Use um de: {', '.join(sorted(tipos_suportados))}"

    try:
        registros = json.loads(dataframe_json)
        df = pd.DataFrame(registros)
    except Exception as e:
        return f"⚠️ Erro ao desserializar o DataFrame: {str(e)}"

    if df.empty:
        return "⚠️ O DataFrame recebido está vazio."

    colunas_faltantes = [col for col in [x_coluna, y_coluna] if col not in df.columns]
    if colunas_faltantes:
        return f"⚠️ Coluna(s) não encontrada(s) no DataFrame: {', '.join(colunas_faltantes)}"

    try:
        df[y_coluna] = pd.to_numeric(df[y_coluna], errors="raise")
        return json.dumps(
            {
                "tipo": "grafico",
                "titulo": titulo,
                "x_coluna": x_coluna,
                "y_coluna": y_coluna,
                "grafico": tipo,
                "dados": df[[x_coluna, y_coluna]].to_dict(orient="records"),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return f"Erro ao gerar gráfico: {str(e)}"

if __name__ == "__main__":
    print("A iniciar o Servidor MCP de Dados Heterogéneos (Modo Seguro)...")
    mcp.run()