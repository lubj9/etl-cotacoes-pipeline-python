"""
Load: persiste os dados no PostgreSQL.
Usa SQLAlchemy para portabilidade entre SGBDs.
"""
import logging
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def obter_engine():
    """Cria engine do SQLAlchemy a partir de variáveis de ambiente."""
    url = os.getenv("DATABASE_URL")
    if not url:
        # Fallback para SQLite local em desenvolvimento
        Path("data").mkdir(exist_ok=True)
        url = "sqlite:///data/cotacoes.db"
        logger.warning(f"DATABASE_URL não definida — usando SQLite local: {url}")
    return create_engine(url)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cotacoes (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) NOT NULL,
    nome            VARCHAR(100),
    alta            NUMERIC(18, 6),
    baixa           NUMERIC(18, 6),
    variacao        NUMERIC(18, 6),
    pct_variacao    NUMERIC(8, 4),
    bid             NUMERIC(18, 6),
    ask             NUMERIC(18, 6),
    spread          NUMERIC(18, 6),
    tendencia       VARCHAR(10),
    timestamp_origem TIMESTAMP,
    data_coleta     TIMESTAMP,
    UNIQUE (codigo, timestamp_origem)
);

CREATE INDEX IF NOT EXISTS idx_cotacoes_codigo ON cotacoes(codigo);
CREATE INDEX IF NOT EXISTS idx_cotacoes_data ON cotacoes(data_coleta);
"""

SCHEMA_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS cotacoes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT NOT NULL,
    nome            TEXT,
    alta            REAL,
    baixa           REAL,
    variacao        REAL,
    pct_variacao    REAL,
    bid             REAL,
    ask             REAL,
    spread          REAL,
    tendencia       TEXT,
    timestamp_origem TIMESTAMP,
    data_coleta     TIMESTAMP,
    UNIQUE (codigo, timestamp_origem)
);
"""


def criar_schema(engine) -> None:
    """Cria a tabela se ainda não existir."""
    dialect = engine.dialect.name
    sql = SCHEMA_SQL_SQLITE if dialect == "sqlite" else SCHEMA_SQL
    with engine.begin() as conn:
        for stmt in sql.strip().split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    logger.info(f"Schema verificado/criado ({dialect}).")


def carregar(df: pd.DataFrame, engine) -> int:
    """
    Insere registros na tabela `cotacoes`.
    Usa INSERT OR IGNORE / ON CONFLICT para idempotência.
    """
    if df.empty:
        logger.warning("Nada a carregar.")
        return 0

    # Append direto via pandas; em produção usaríamos UPSERT explícito
    df.to_sql("cotacoes_staging", engine, if_exists="replace", index=False)

    dialect = engine.dialect.name
    cols = list(df.columns)
    cols_str = ", ".join(cols)

    if dialect == "sqlite":
        upsert = f"""
            INSERT OR IGNORE INTO cotacoes ({cols_str})
            SELECT {cols_str} FROM cotacoes_staging
        """
    else:  # postgres
        upsert = f"""
            INSERT INTO cotacoes ({cols_str})
            SELECT {cols_str} FROM cotacoes_staging
            ON CONFLICT (codigo, timestamp_origem) DO NOTHING
        """

    with engine.begin() as conn:
        result = conn.execute(text(upsert))
        conn.execute(text("DROP TABLE cotacoes_staging"))

    inseridos = result.rowcount if result.rowcount is not None else len(df)
    logger.info(f"Inseridos {inseridos} registros novos.")
    return inseridos
