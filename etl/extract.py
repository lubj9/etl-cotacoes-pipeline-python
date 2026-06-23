"""
Extração: busca cotações de moedas e criptomoedas via duas fontes complementares.

Decisão arquitetural:
- Forex (USD, EUR, GBP vs BRL): Frankfurter API
    Fonte: Banco Central Europeu. Sem chave, sem rate limit.
- Cripto (BTC, ETH vs BRL): Binance API pública
    Endpoints públicos sem chave, limit generoso (~1200/min por IP).

Por que trocamos da AwesomeAPI original:
    O IP do GitHub Actions é compartilhado entre milhares de workflows simultâneos.
    APIs com rate limit por IP veem todo esse tráfego coletivo como vindo da mesma
    origem, esgotando a cota mesmo quando o pipeline individual usa pouco.
    Frankfurter e Binance pública não sofrem desse problema.

Mantemos a estratégia de resiliência (retry, backoff, timeout) porque mesmo
APIs robustas têm instabilidades pontuais.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# Moedas a coletar
MOEDAS_FOREX = ["USD", "EUR", "GBP"]  # cotação contra BRL
CRIPTOS = ["BTC", "ETH"]              # contra BRL via Binance

NOMES = {
    "USD-BRL": "Dolar Americano/Real",
    "EUR-BRL": "Euro/Real",
    "GBP-BRL": "Libra Esterlina/Real",
    "BTC-BRL": "Bitcoin/Real",
    "ETH-BRL": "Ethereum/Real",
}

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1/latest"
BINANCE_BASE = "https://api.binance.com/api/v3/ticker/24hr"

# Configurações de resiliência
MAX_TENTATIVAS = 4
BACKOFF_INICIAL = 2
TIMEOUT = 15
USER_AGENT = "etl-cotacoes-pipeline/2.0 (github.com/lubj9)"


def _fazer_requisicao(url: str, params: Optional[dict] = None) -> dict:
    """Requisição HTTP com retry e backoff exponencial."""
    headers = {"User-Agent": USER_AGENT}
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
    Busca BTC e ETH contra BRL via Binance pública.
    """
    logger.info("Buscando cripto via Binance...")
    simbolos = ",".join(f'"{c}BRL"' for c in CRIPTOS)
    data = _fazer_requisicao(BINANCE_BASE, params={"symbols": f"[{simbolos}]"})

    registros = []
    for item in data:
        simbolo = item["symbol"]
        cripto = simbolo.replace("BRL", "")
        codigo = f"{cripto}-BRL"

        bid = float(item.get("bidPrice", item["lastPrice"]))
        ask = float(item.get("askPrice", item["lastPrice"]))
        if bid == 0:
            bid = float(item["lastPrice"])
        if ask == 0:
            ask = float(item["lastPrice"])

        registros.append({
            "codigo": codigo,
            "nome": NOMES.get(codigo, codigo),
            "bid": bid,
            "ask": ask,
            "alta": float(item["highPrice"]),
            "baixa": float(item["lowPrice"]),
            "variacao": float(item["priceChange"]),
            "pct_variacao": float(item["priceChangePercent"]),
            "timestamp_origem": datetime.fromtimestamp(
                int(item["closeTime"]) / 1000, tz=timezone.utc
            ),
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
