import os
import sqlite3
import csv
import json
import random
from datetime import datetime, timedelta

# Diretório onde os dados gerados serão armazenados (data/ na raiz do projeto)
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, 'data')


def setup_environment():
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Dados serão gerados em: {DATA_DIR}")
    print("Iniciando geração de dados em massa para o laboratório...")
    random.seed(42) # Semente fixa para garantir reprodutibilidade no minicurso

    # ---------------------------------------------------------
    # 1. Banco Relacional (SQLite) - 1.000 Produtos
    # ---------------------------------------------------------
    print("Gerando banco de produtos (SQLite)...")
    conn = sqlite3.connect(os.path.join(DATA_DIR, 'produtos.db'))
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS produtos (id INTEGER PRIMARY KEY, nome TEXT, categoria TEXT, preco REAL)''')
    cursor.execute("DELETE FROM produtos") # Limpa execuções anteriores
    
    categorias = ['Eletrônicos', 'Informática', 'Móveis', 'Escritório', 'Acessórios']
    adjetivos = ['Pro', 'Master', 'Lite', 'Gamer', 'Premium', 'Essencial']
    tipos = ['Notebook', 'Monitor', 'Teclado', 'Cadeira', 'Mesa', 'Headset', 'Mouse']
    
    produtos = []
    for i in range(1, 1001):
        nome = f"{random.choice(tipos)} {random.choice(adjetivos)} {random.randint(100, 999)}"
        categoria = random.choice(categorias)
        preco = round(random.uniform(50.0, 8500.0), 2)
        produtos.append((i, nome, categoria, preco))
        
    cursor.executemany("INSERT INTO produtos VALUES (?, ?, ?, ?)", produtos)
    conn.commit()
    conn.close()
    print(f"✅ {len(produtos)} produtos inseridos no SQLite.")

    # ---------------------------------------------------------
    # 2. Banco Não-Relacional (JSON) - 1.000 Clientes
    # ---------------------------------------------------------
    print("Gerando banco documental de clientes (JSON)...")
    segmentos = ['Tecnologia', 'Varejo', 'Educação', 'Saúde', 'Finanças', 'Indústria']
    tags_base = ['b2b', 'b2c', 'premium', 'novo', 'vip', 'risco_churn', 'inativo']
    
    clientes = {}
    for i in range(1, 1001):
        id_cliente = f"C{i:04d}"
        qtd_tags = random.randint(1, 4)
        
        clientes[id_cliente] = {
            "nome": f"Empresa Fictícia {i} S.A." if random.random() > 0.3 else f"Cliente Final {i}",
            "segmento": random.choice(segmentos),
            "ltv_historico": round(random.uniform(500.0, 50000.0), 2), # Lifetime Value
            "tags": random.sample(tags_base, qtd_tags),
            "status": "ativo" if random.random() > 0.1 else "inativo"
        }
        
    with open(os.path.join(DATA_DIR, 'clientes.json'), 'w', encoding='utf-8') as f:
        json.dump(clientes, f, indent=4, ensure_ascii=False)
    print(f"✅ {len(clientes)} clientes salvos no JSON.")

    # ---------------------------------------------------------
    # 3. Planilha/Arquivo Plano (CSV) - 20.000 Vendas
    # ---------------------------------------------------------
    print("Gerando histórico massivo de vendas (CSV)...")
    data_inicio = datetime.now() - timedelta(days=730) # 2 anos atrás
    
    vendas = []
    # Cabeçalho
    vendas.append(['id_venda', 'id_produto', 'id_cliente', 'quantidade', 'valor_total', 'data_venda'])
    
    for i in range(1, 20001):
        id_produto = random.randint(1, 1000)
        id_cliente = f"C{random.randint(1, 1000):04d}"
        quantidade = random.randint(1, 15)
        # Aproximação de valor para não precisarmos fazer um JOIN em Python gerando os dados
        valor_total = round(quantidade * random.uniform(50.0, 8500.0), 2) 
        
        dias_aleatorios = random.randint(0, 730)
        data_venda = data_inicio + timedelta(days=dias_aleatorios)
        
        vendas.append([
            f"V{i:06d}", 
            str(id_produto), 
            id_cliente, 
            str(quantidade), 
            str(valor_total), 
            data_venda.strftime('%Y-%m-%d')
        ])

    with open(os.path.join(DATA_DIR, 'vendas.csv'), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(vendas)
    print(f"✅ {len(vendas) - 1} registros de venda inseridos no CSV.")
    print("🚀 Ambiente de dados complexo criado com sucesso!")

if __name__ == "__main__":
    setup_environment()