# 🔄 Pipeline ETL — Cotações de Moedas

Pipeline ETL em Python que coleta cotações de moedas e criptomoedas em tempo real via API pública, aplica regras de qualidade e enriquecimento, e persiste em **PostgreSQL** hospedado no Supabase. Executado automaticamente a cada 6 horas via **GitHub Actions**.

[![ETL Cotações](https://github.com/lubj9/etl-cotacoes-pipeline/actions/workflows/etl.yml/badge.svg)](https://github.com/lubj9/etl-cotacoes-pipeline/actions/workflows/etl.yml)

---

## 🟢 Status atual

Pipeline rodando em produção, agendado a cada 6 horas. Dados sendo persistidos em PostgreSQL gerenciado.

> <img width="633" height="335" alt="{1DC39839-F334-43D4-B832-42D157AA2C5F}" src="https://github.com/user-attachments/assets/eee08cfa-cdc5-4ad3-81b7-0876978ec343" />


---

## 🎯 O que o projeto demonstra

- **ETL end-to-end** com separação clara das fases (Extract, Transform, Load)
- **Resiliência de rede**: retry com backoff exponencial e tratamento específico de HTTP 429 (rate limit)
- **Idempotência**: pipeline pode ser reexecutado sem gerar duplicatas
- **Orquestração serverless** via GitHub Actions (zero infraestrutura para manter)
- **Portabilidade**: mesmo código roda em SQLite (desenvolvimento local) e PostgreSQL (produção)
- **Segurança**: credenciais via secrets, nunca no código
- **Observabilidade**: logging estruturado e artefatos de log armazenados a cada execução

---

## 🛠️ Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11 |
| HTTP | requests |
| Manipulação de dados | pandas |
| Persistência | SQLAlchemy + psycopg2 |
| Banco (produção) | PostgreSQL (Supabase free tier) |
| Banco (local) | SQLite (fallback automático) |
| Orquestração | GitHub Actions |
| Fonte de dados | [AwesomeAPI](https://docs.awesomeapi.com.br/) |

---

## 🧭 Arquitetura

```
                 ┌──────────────────────┐
                 │   GitHub Actions     │
                 │   cron: */6h         │
                 └──────────┬───────────┘
                            │
                            ▼
    ┌─────────────────────────────────────────────────┐
    │                  main.py                        │
    │  ┌──────────┐   ┌────────────┐   ┌──────────┐   │
    │  │ extract  │ → │ transform  │ → │   load   │   │
    │  └────┬─────┘   └────────────┘   └─────┬────┘   │
    └───────┼──────────────────────────────────┼──────┘
            │                                  │
            ▼                                  ▼
   ┌──────────────────┐              ┌──────────────────┐
   │   AwesomeAPI     │              │   PostgreSQL     │
   │ (cotações reais) │              │   (Supabase)     │
   └──────────────────┘              └──────────────────┘
```

---

## 📁 Estrutura

```
.
├── etl/
│   ├── extract.py        # Coleta da API, com retry e backoff exponencial
│   ├── transform.py      # Validação, deduplicação, enriquecimento
│   ├── load.py           # Schema + upsert idempotente
│   └── __init__.py
├── main.py               # Orquestrador (E → T → L)
├── analise.py            # Consultas SQL sobre os dados coletados
├── .github/
│   └── workflows/
│       └── etl.yml       # Agendamento e execução no GitHub Actions
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Como rodar localmente

### Pré-requisitos
- Python 3.10 ou superior
- Git

### Setup

```bash
# 1. Clonar o repositório
git clone https://github.com/lubj9/etl-cotacoes-pipeline.git
cd etl-cotacoes-pipeline

# 2. Criar e ativar ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# Linux/Mac:
source .venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Rodar o pipeline (usa SQLite local automaticamente)
python main.py

# 5. Ver análises sobre os dados coletados
python analise.py
```

Sem `DATABASE_URL` configurada, o pipeline detecta automaticamente e usa SQLite local em `data/cotacoes.db` — útil para desenvolvimento e revisão de código sem precisar provisionar banco.

### Rodar com PostgreSQL real

```bash
cp .env.example .env
# editar .env com sua DATABASE_URL
export $(cat .env | xargs)  # Linux/Mac
# Windows: defina a variável manualmente no PowerShell
python main.py
```

---

## ☁️ Deploy em produção

### 1. Provisionar PostgreSQL no Supabase

1. Criar conta em [supabase.com](https://supabase.com) (gratuito, sem cartão)
2. **New project** → escolher região South America
3. Salvar a senha do banco em local seguro
4. Em **Project Settings → Database → Connection string (URI)**, copiar a string e substituir `[YOUR-PASSWORD]` pela senha real

### 2. Configurar secret no GitHub

No repositório: **Settings → Secrets and variables → Actions → New repository secret**
- Name: `DATABASE_URL`
- Value: a connection string completa do Supabase

### 3. Ativar workflows

No repositório: aba **Actions → I understand my workflows, go ahead and enable them**.

O workflow `ETL Cotações` rodará automaticamente a cada 6 horas. Para testar imediatamente, clique em **Run workflow**.

---

## 🗄️ Schema da tabela

```sql
CREATE TABLE cotacoes (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) NOT NULL,    -- ex: USD-BRL
    nome            VARCHAR(100),
    alta            NUMERIC(18, 6),
    baixa           NUMERIC(18, 6),
    variacao        NUMERIC(18, 6),
    pct_variacao    NUMERIC(8, 4),
    bid             NUMERIC(18, 6),          -- preço de compra
    ask             NUMERIC(18, 6),          -- preço de venda
    spread          NUMERIC(18, 6),          -- enriquecido: ask - bid
    tendencia       VARCHAR(10),             -- alta / baixa / estável
    timestamp_origem TIMESTAMP,              -- momento da cotação
    data_coleta     TIMESTAMP,               -- momento da execução do ETL
    UNIQUE (codigo, timestamp_origem)        -- garante idempotência
);

CREATE INDEX idx_cotacoes_codigo ON cotacoes(codigo);
CREATE INDEX idx_cotacoes_data ON cotacoes(data_coleta);
```

---

## 🧠 Decisões de design

| Decisão | Por quê |
|---|---|
| ETL e não ELT | Volume baixo (~5 registros/execução); transformações simples não justificam um orquestrador como dbt. |
| SQLAlchemy em vez de psycopg2 puro | Portabilidade: o mesmo código roda em SQLite (desenvolvimento) e PostgreSQL (produção). |
| Upsert com `ON CONFLICT DO NOTHING` | Idempotência: executar o pipeline duas vezes em sequência não duplica dados. |
| GitHub Actions em vez de Airflow | Custo zero, suficiente para o caso de uso. Airflow só faria sentido com dezenas de DAGs e dependências entre elas. |
| Fallback automático para SQLite | Permite que qualquer pessoa clone o repo e rode em segundos, sem provisionar banco. |
| Retry com backoff exponencial | APIs públicas têm rate limit e instabilidade. Pipeline em produção precisa absorver isso sem falhar. |
| Distinção entre erros transitórios e permanentes | Só faz retry em 429, 5xx, timeout e ConnectionError. Erros 4xx são problemas da própria requisição e falham imediatamente. |
| `User-Agent` identificável | Boa prática de cliente HTTP: APIs públicas frequentemente penalizam bots genéricos. |

---

## 📊 Consultas analíticas (`analise.py`)

```sql
-- Última cotação por moeda
SELECT codigo, nome, bid, pct_variacao, tendencia, data_coleta
FROM cotacoes
WHERE (codigo, data_coleta) IN (
    SELECT codigo, MAX(data_coleta) FROM cotacoes GROUP BY codigo
);

-- Estatísticas históricas por moeda
SELECT codigo,
       COUNT(*) AS n_coletas,
       AVG(bid) AS media_bid,
       MIN(bid) AS min_bid,
       MAX(bid) AS max_bid
FROM cotacoes
GROUP BY codigo;
```

---

## ⚠️ Limitações conhecidas

- **Supabase free tier** pausa projetos após 7 dias sem atividade. Como o workflow roda a cada 6 horas, o banco mantém-se ativo continuamente.
- **GitHub Actions** desativa workflows agendados em repositórios sem atividade por 60 dias. Commits esporádicos no repositório mantêm o agendamento vivo.
- A **AwesomeAPI** não exige autenticação, mas aplica rate limit por IP. Como o IP do GitHub Actions é compartilhado, ocasionalmente pode haver bloqueio temporário — daí a importância do retry implementado.

---

## 🔮 Próximos passos

- [ ] Testes unitários com pytest (mocks da API)
- [ ] Métricas de qualidade dos dados com Great Expectations
- [ ] Dashboard Streamlit consumindo o PostgreSQL
- [ ] Notificações no Telegram em variações superiores a 3%
- [ ] Containerização com Docker para portabilidade adicional
- [ ] Migração para data warehouse (BigQuery) caso o volume cresça

---

## 👤 Autor

**Lucas Zeferino Baracat**
Estudante de Sistemas de Informação na Universidade Presbiteriana Mackenzie
[LinkedIn](https://www.linkedin.com/in/lucasbaracat9/) · [GitHub](https://github.com/lubj9)
