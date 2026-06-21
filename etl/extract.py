"""
Extração: busca cotações de moedas via API do AwesomeAPI (gratuita, sem chave).
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# Moedas que vamos rastrear (pares contra BRL)
MOEDAS = ["USD-BRL", "EUR-BRL", "GBP-BRL", "BTC-BRL", "ETH-BRL"]

API_BASE = "https://economia.awesomeapi.com.br/json/last"


def buscar_cotacoes(moedas: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Busca cotações atuais para a lista de moedas.

    Returns:
        DataFrame com colunas: codigo, nome, alta, baixa, varBid, pctChange,
        bid, ask, timestamp, data_coleta.
    """
    moedas = moedas or MOEDAS
    url = f"{API_BASE}/{','.join(moedas)}"

    logger.info(f"Chamando API: {url}")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    registros = []
    data_coleta = datetime.now(timezone.utc)
    for chave, valores in data.items():
        registros.append({
            "codigo": f"{valores['code']}-{valores['codein']}",
            "nome": valores["name"],
            "alta": float(valores["high"]),
            "baixa": float(valores["low"]),
            "variacao": float(valores["varBid"]),
            "pct_variacao": float(valores["pctChange"]),
            "bid": float(valores["bid"]),
            "ask": float(valores["ask"]),
            "timestamp_origem": datetime.fromtimestamp(int(valores["timestamp"])),
            "data_coleta": data_coleta,
        })

    df = pd.DataFrame(registros)
    logger.info(f"Extraídos {len(df)} registros.")
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = buscar_cotacoes()
    print(df.to_string())
