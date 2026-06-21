# 🔄 Pipeline ETL — Cotações de Moedas (API → PostgreSQL)

Pipeline ETL em Python que consome cotações de moedas e criptomoedas em tempo real via API pública, aplica regras de qualidade e enriquecimento, e persiste em PostgreSQL. Agendado automaticamente via **GitHub Actions** a cada 6 horas.

## 🎯 O que o projeto demonstra

- **Extract**: consumo de API REST com tratamento de erros e timeout
- **Transform**: limpeza, validação, deduplicação e enriquecimento de dados
- **Load**: persistência idempotente em PostgreSQL com upsert via SQL nativo
- **Orquestração**: agendamento serverless com GitHub Actions
- **Boas práticas**: logging estruturado, secrets via variáveis de ambiente, schema versionado

## 🛠️ Stack

- **Python 3.11** · pandas · requests · SQLAlchemy
- **PostgreSQL** (produção) / **SQLite** (desenvolvimento local — fallback automático)
- **GitHub Actions** (agendador)
- **Render** ou **Supabase** (banco gerenciado free tier)

## 📁 Estrutura

```
.
├── etl/
│   ├── extract.py      # Coleta da API AwesomeAPI
│   ├── transform.py    # Limpeza, dedup, enriquecimento
│   └── load.py         # Schema + upsert no PostgreSQL
├── main.py             # Orquestrador (E → T → L)
├── analise.py          # Consultas SQL sobre os dados coletados
├── .github/workflows/
│   └── etl.yml         # Agendamento a cada 6h
├── requirements.txt
└── README.md
```

## 🚀 Como rodar

### Localmente (com SQLite — não precisa instalar Postgres)

```bash
pip install -r requirements.txt
python main.py        # roda o pipeline
python analise.py     # mostra consultas sobre o que foi coletado
```

### Com PostgreSQL real (Supabase / Render free tier)

```bash
cp .env.example .env
# edite .env com sua DATABASE_URL
export $(cat .env | xargs)
python main.py
```

### Em produção (GitHub Actions)

1. Criar banco no [Supabase](https://supabase.com) (free tier, 500MB)
2. Em **Settings → Secrets → Actions** do seu repositório, adicionar `DATABASE_URL`
3. O workflow roda automaticamente a cada 6 horas

## 📊 Schema da tabela

```sql
CREATE TABLE cotacoes (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) NOT NULL,   -- ex: USD-BRL
    nome            VARCHAR(100),
    alta            NUMERIC(18, 6),
    baixa           NUMERIC(18, 6),
    variacao        NUMERIC(18, 6),
    pct_variacao    NUMERIC(8, 4),
    bid             NUMERIC(18, 6),         -- preço de compra
    ask             NUMERIC(18, 6),         -- preço de venda
    spread          NUMERIC(18, 6),         -- enriquecido
    tendencia       VARCHAR(10),            -- alta / baixa / estável
    timestamp_origem TIMESTAMP,             -- momento da cotação
    data_coleta     TIMESTAMP,              -- momento da execução do ETL
    UNIQUE (codigo, timestamp_origem)       -- garante idempotência
);
```

## 🧠 Decisões de design

| Decisão | Por quê |
|---|---|
| ETL e não ELT | Volume baixo (5 registros/execução); transformações simples não justificam orquestrador como dbt |
| SQLAlchemy em vez de psycopg2 puro | Portabilidade — mesmo código roda em SQLite (dev) e Postgres (prod) |
| Upsert com `ON CONFLICT DO NOTHING` | Idempotência: executar o pipeline 2x não duplica dados |
| GitHub Actions em vez de Airflow | Custo zero, suficiente para o caso de uso, padrão da indústria para schedules simples |
| Fallback SQLite | Reviewer consegue rodar e testar em segundos, sem subir banco |

## 🔮 Próximos passos

- Adicionar testes unitários com pytest (mock da API)
- Métricas de qualidade dos dados (Great Expectations)
- Dashboard Streamlit consumindo o Postgres
- Alertas no Telegram quando variação > 3%

---

Desenvolvido por **Lucas Zeferino Baracat**
[LinkedIn](https://www.linkedin.com/in/lucasbaracat9/) · [GitHub](https://github.com/lubj9)
