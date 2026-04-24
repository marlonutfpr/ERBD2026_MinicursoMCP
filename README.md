# Minicurso MCP — Agente de Dados com Model Context Protocol

> Material didático apresentado no **ERBD 2026** (Escola Regional de Banco de Dados 2026).

**Autor:** Prof. Dr. Marlon Marcon  
**Instituição:** Universidade Tecnológica Federal do Paraná — UTFPR

Apresentação do minicurso: [minicurso_erbd_2026_mcp.pdf](minicurso_erbd_2026_mcp.pdf)

---

## Sobre o Projeto

Este repositório contém o código-fonte completo do minicurso prático sobre o **Model Context Protocol (MCP)**, demonstrando como construir agentes de IA seguros e governados que interagem com fontes de dados heterogêneas — bancos relacionais, documentos NoSQL, arquivos de Big Data e APIs externas.

O projeto ilustra, de forma didática, os seguintes conceitos:

- Arquitetura cliente-servidor do MCP via transporte STDIO
- Controle de acesso baseado em papéis (**RBAC**) implementado no servidor MCP
- Conformidade com privacidade de dados (**LGPD/GDPR**) — bloqueio de consultas sensíveis
- Anonimização de dados em respostas do servidor
- Prevenção de **SQL Injection** por validação estrita de parâmetros
- Loop agêntico orquestrado por LLM via **OpenRouter**
- Interface interativa com **Streamlit**

---

## Estrutura do Projeto

```
ERBD2026_MinicursoMCP/
├── app.py                       # Aplicação web principal (Streamlit)
├── requirements.txt             # Dependências Python
├── README.md
├── LICENSE
├── mcp/                         # Camada MCP (servidor, cliente e motor)
│   ├── server.py                  # Servidor MCP com as ferramentas de dados
│   ├── client.py                  # Cliente de demonstração via terminal (CLI)
│   └── mcp_core.py                # Motor MCP e loop agêntico compartilhado
├── scripts/                     # Scripts utilitários
│   └── setup_data.py              # Geração dos dados de laboratório
├── data/                        # Dados gerados automaticamente pelo setup
│   ├── produtos.db                # Banco relacional SQLite (1.000 produtos)
│   ├── clientes.json              # Banco documental NoSQL (1.000 clientes)
│   └── vendas.csv                 # Histórico de Big Data de vendas (20.000 registros)
```

---

## Pré-requisitos

- Python 3.10 ou superior
- Conta no [OpenRouter](https://openrouter.ai) para obter uma API Key (gratuita)

---

## Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/marlonutfpr/ERBD2026_MinicursoMCP.git
cd ERBD2026_MinicursoMCP

# 2. Crie e ative um ambiente virtual
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

---

## Configuração da API Key

A chave do OpenRouter é carregada automaticamente a partir de um arquivo `.env` na raiz do projeto.

```bash
# Copie o arquivo de exemplo
cp .env.example .env   # Linux/macOS
copy .env.example .env  # Windows
```

Abra o `.env` e substitua o valor pelo sua chave real:

```env
OPENROUTER_API_KEY=sk-or-v1-SUA_CHAVE_AQUI
```

> O arquivo `.env` está no `.gitignore` e **nunca deve ser versionado**. Use `.env.example` como referência pública.

---

## Configuração dos Dados

Execute o script de setup para gerar o banco SQLite, o JSON de clientes e o CSV de vendas:

```bash
python scripts/setup_data.py
```

---

## Execução

### Demonstração via Terminal (CLI)

Executa um roteiro automático que demonstra os cenários de sucesso e bloqueio de segurança:

```bash
python mcp/client.py
```

### Interface Web Interativa (Streamlit)

```bash
streamlit run app.py
```

Acesse `http://localhost:8501` no navegador. A aplicação concentra os fluxos no arquivo `app.py`, incluindo a aba **Agente Conversacional**, que usa a chave do OpenRouter carregada automaticamente do `.env`.

---

## Ferramentas MCP Disponíveis

| Ferramenta | Fonte | Descrição |
|---|---|---|
| `obter_metricas_produtos` | SQLite | Preço médio de produtos por categoria (com RBAC) |
| `listar_clientes_por_tag` | JSON (NoSQL) | Clientes por tag de perfil (com filtro LGPD) |
| `calcular_total_gasto_cliente` | CSV (Big Data) | Total gasto por cliente nas vendas |
| `consultar_cotacao_moedas` | API externa | Cotação de moedas em relação ao BRL (atual ou histórica) |
| `gerar_grafico_dataframe` | DataFrame serializado | Gera um gráfico PNG em base64 para exibição no Streamlit |

---

## Cenários de Segurança Demonstrados

| Fase | Tipo | Resultado Esperado |
|------|------|--------------------|
| 1 | Acesso SQL permitido | Métricas por categoria retornadas com sucesso |
| 2 | Acesso SQL restrito (RBAC) | Bloqueio — dimensão reservada à diretoria |
| 3 | NoSQL com anonimização | Nomes mascarados nos resultados |
| 4 | NoSQL sensível (LGPD) | Bloqueio — tag de compliance negada |
| 5 | Big Data delegado | Cálculo server-side sem expor dados brutos ao LLM |

---

## Licença

Este projeto está licenciado sob a **Creative Commons Atribuição 4.0 Internacional (CC BY 4.0)**.

Você tem liberdade para copiar, distribuir, adaptar e criar obras derivadas — inclusive para fins comerciais — **desde que atribua a devida crédito aos autores originais**, indique se realizou alterações e mantenha o vínculo com a licença.

Consulte o arquivo [LICENSE](LICENSE) ou acesse [creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/deed.pt_BR) para os termos completos.

---

## Como Citar

Se você utilizar este material em trabalhos acadêmicos, apresentações ou adaptações, por favor cite:

```
MARCON, Marlon. Desenvolvimento de Agentes de IA e Integração com Bases de Dados Heterogêneas.
ERBD 2026 — Escola Regional de Banco de Dados, 2026.
Universidade Tecnológica Federal do Paraná — UTFPR.
Disponível em: https://github.com/marlonutfpr/ERBD2026_MinicursoMCP
```

---

*Desenvolvido com fins didáticos para o ERBD 2026 — Prof. Dr. Marlon Marcon, UTFPR.*
