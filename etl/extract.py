"""
Extração: busca cotações de moedas e criptomoedas via duas fontes complementares.

Decisão arquitetural:
- Forex (USD, EUR, GBP vs BRL): Frankfurter API
    Fonte: Banco Central Europeu. Sem chave, sem rate limit.
- Cripto (BTC, ETH vs BRL): CoinGecko API
    Endpoint público sem chave. Sem geo-block.
    Rate limit ~10-30 req/min — trivial para 4 execuções/dia.

Histórico de decisões:
1. AwesomeAPI (original): rate limit por IP saturado no GitHub Actions
   (IP compartilhado com milhares de workflows).
2. Binance pública (tentativa): bloqueada por geo-restrição (HTTP 451) em IPs US;
   runners do GitHub Actions estão em Azure US.
3. CoinGecko (atual): sem chave, sem geo-block, padrão da indústria
   para projetos cripto open-source.

Mantemos a estratégia de resiliência (retry, backoff, timeout) porque
mesmo APIs robustas têm instabilidades pontuais.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# Moedas a coletar
MOEDAS_FOREX = ["USD", "EUR", "GBP"]  # contra BRL via Frankfurter
# CoinGecko usa identificadores próprios (ids), não tickers
CRIPTOS = {"bitcoin": "BTC", "ethereum": "ETH"}

NOMES = {
    "USD-BRL": "Dolar Americano/Real",
    "EUR-BRL": "Euro/Real",
    "GBP-BRL": "Libra Esterlina/Real",
    "BTC-BRL": "Bitcoin/Real",
    "ETH-BRL": "Ethereum/Real",
}

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1/latest"
COINGECKO_BASE = "https://api.coingecko.com/api/v3/coins/markets"

# Configurações de resiliência
MAX_TENTATIVAS = 4
BACKOFF_INICIAL = 2
TIMEOUT = 15
USER_AGENT = "etl-cotacoes-pipeline/2.1 (github.com/lubj9)"


def _fazer_requisicao(url: str, params: Optional[dict] = None):
    """Requisição HTTP com retry e backoff exponencial."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    espera = BACKOFF_INICIAL

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", espera))
                logger.warning(
                    f"Tentativa {tentativa}/{MAX_TENTATIVAS}: rate limit em {url}. "
                    f"Aguardando {retry_after}s..."
                )
                time.sleep(retry_after)
                espera *= 2
                continue

            if 500 <= resp.status_code < 600:
                logger.warning(
                    f"Tentativa {tentativa}/{MAX_TENTATIVAS}: erro {resp.status_code}. "
                    f"Aguardando {espera}s..."
                )
                time.sleep(espera)
                espera *= 2
                continue

            resp.raise_for_status()
            return resp.json()

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            logger.warning(
                f"Tentativa {tentativa}/{MAX_TENTATIVAS}: erro de rede ({e}). "
                f"Aguardando {espera}s..."
            )
            time.sleep(espera)
            espera *= 2

    raise RuntimeError(f"Falha em {url} após {MAX_TENTATIVAS} tentativas.")


def _buscar_forex(data_coleta: datetime) -> list[dict]:
    """
    Busca USD, EUR, GBP contra BRL via Frankfurter.

    A API retorna 1 BRL = X moedaEstrangeira. Invertemos para obter a cotação
    no formato padrão do mercado brasileiro: 1 USD = R$ Y.
    """
    logger.info("Buscando forex via Frankfurter...")
    data = _fazer_requisicao(
        FRANKFURTER_BASE,
        params={"base": "BRL", "symbols": ",".join(MOEDAS_FOREX)},
    )

    registros = []
    timestamp_origem = datetime.fromisoformat(data["date"])
    for moeda in MOEDAS_FOREX:
        taxa_inversa = float(data["rates"][moeda])
        if taxa_inversa <= 0:
            continue
        bid = 1.0 / taxa_inversa
        codigo = f"{moeda}-BRL"
        registros.append({
            "codigo": codigo,
            "nome": NOMES[codigo],
            "bid": round(bid, 4),
            "ask": round(bid, 4),
            "alta": round(bid, 4),
            "baixa": round(bid, 4),
            "variacao": 0.0,
            "pct_variacao": 0.0,
            "timestamp_origem": datetime.combine(timestamp_origem, datetime.min.time()),
            "data_coleta": data_coleta,
        })
    return registros


def _buscar_cripto(data_coleta: datetime) -> list[dict]:
    """
    Busca BTC e ETH contra BRL via CoinGecko.

    O endpoint /coins/markets fornece em uma única requisição: preço atual,
    máxima e mínima das últimas 24h, variação absoluta e percentual.
    """
    logger.info("Buscando cripto via CoinGecko...")
    data = _fazer_requisicao(
        COINGECKO_BASE,
        params={
            "vs_currency": "brl",
            "ids": ",".join(CRIPTOS.keys()),
            "price_change_percentage": "24h",
        },
    )

    registros = []
    for item in data:
        ticker = CRIPTOS.get(item["id"])
        if not ticker:
            continue
        codigo = f"{ticker}-BRL"
        preco = float(item["current_price"])

        # CoinGecko não fornece bid/ask separados (não é exchange única);
        # usamos o preço médio agregado, consistente em ambos os campos.
        registros.append({
            "codigo": codigo,
            "nome": NOMES.get(codigo, codigo),
            "bid": preco,
            "ask": preco,
            "alta": float(item.get("high_24h") or preco),
            "baixa": float(item.get("low_24h") or preco),
            "variacao": float(item.get("price_change_24h") or 0.0),
            "pct_variacao": float(item.get("price_change_percentage_24h") or 0.0),
            "timestamp_origem": datetime.now(timezone.utc),
            "data_coleta": data_coleta,
        })
    return registros


def buscar_cotacoes() -> pd.DataFrame:
    """Orquestra a coleta nas duas fontes e retorna um DataFrame único."""
    data_coleta = datetime.now(timezone.utc)
    registros = []
    registros.extend(_buscar_forex(data_coleta))
    registros.extend(_buscar_cripto(data_coleta))

    df = pd.DataFrame(registros)
    logger.info(f"Extraídos {len(df)} registros de 2 fontes.")
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    df = buscar_cotacoes()
    print(df.to_string())
