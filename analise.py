"""
Análises ad-hoc sobre os dados coletados no banco.
Demonstra o "T" no "ELT": transformações analíticas dentro do SGBD.
"""
import pandas as pd
from etl.load import obter_engine


def consultas_exemplo() -> None:
    engine = obter_engine()

    print("\n📊 ÚLTIMA COTAÇÃO POR MOEDA")
    q = """
        SELECT codigo, nome, bid, pct_variacao, tendencia, data_coleta
        FROM cotacoes
        WHERE (codigo, data_coleta) IN (
            SELECT codigo, MAX(data_coleta) FROM cotacoes GROUP BY codigo
        )
        ORDER BY codigo
    """
    print(pd.read_sql(q, engine).to_string(index=False))

    print("\n📈 VARIAÇÃO MÉDIA POR MOEDA (todas as coletas)")
    q = """
        SELECT codigo,
               COUNT(*) AS n_coletas,
               ROUND(AVG(bid), 4) AS media_bid,
               ROUND(MIN(bid), 4) AS min_bid,
               ROUND(MAX(bid), 4) AS max_bid,
               ROUND(AVG(pct_variacao), 4) AS media_variacao
        FROM cotacoes
        GROUP BY codigo
        ORDER BY codigo
    """
    print(pd.read_sql(q, engine).to_string(index=False))

    print("\n🔥 DISTRIBUIÇÃO DE TENDÊNCIA")
    q = "SELECT tendencia, COUNT(*) AS qtd FROM cotacoes GROUP BY tendencia"
    print(pd.read_sql(q, engine).to_string(index=False))


if __name__ == "__main__":
    consultas_exemplo()
