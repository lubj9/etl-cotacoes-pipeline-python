"""
Transformação: limpa, valida e enriquece os dados.
"""
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def transformar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica regras de qualidade e enriquece o DataFrame.

    - Remove duplicatas
    - Valida tipos e ranges
    - Calcula spread (ask - bid)
    - Classifica tendência (alta/baixa/estável)
    """
    if df.empty:
        logger.warning("DataFrame vazio recebido em transformar().")
        return df

    df = df.copy()

    # Drop de eventuais duplicatas exatas
    antes = len(df)
    df = df.drop_duplicates(subset=["codigo", "timestamp_origem"])
    if antes != len(df):
        logger.info(f"Removidas {antes - len(df)} duplicatas.")

    # Validação de valores
    df = df[(df["bid"] > 0) & (df["ask"] > 0)]

    # Enriquecimento
    df["spread"] = (df["ask"] - df["bid"]).round(4)

    def classificar(pct: float) -> str:
        if pct > 0.5:
            return "alta"
        if pct < -0.5:
            return "baixa"
        return "estável"

    df["tendencia"] = df["pct_variacao"].apply(classificar)

    logger.info(f"Transformação concluída: {len(df)} registros válidos.")
    return df
