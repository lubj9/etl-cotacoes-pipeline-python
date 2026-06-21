"""
Extração: busca cotações de moedas via API do AwesomeAPI (gratuita, sem chave).

Inclui estratégia de resiliência:
- Retry automático com backoff exponencial em falhas transitórias
- Tratamento específico de rate limit (HTTP 429)
- User-Agent identificável (evita bloqueio de bots genéricos)
- Timeout para não travar a execução em caso de instabilidade da API
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# Moedas que vamos rastrear (pares contra BRL)
MOEDAS = ["USD-BRL", "EUR-BRL", "GBP-BRL", "BTC-BRL", "ETH-BRL"]

API_BASE = "https://economia.awesomeapi.com.br/json/last"

# Configurações de retry
MAX_TENTATIVAS = 5
BACKOFF_INICIAL = 2  # segundos; dobra a cada tentativa (2, 4, 8, 16, 32)
TIMEOUT = 15  # segundos

# Identifica o cliente — APIs públicas tratam User-Agent identificável melhor
USER_AGENT = "etl-cotacoes-pipeline/1.0 (github.com/lubj9)"


def _fazer_requisicao(url: str) -> dict:
    """
    Faz a requisição com retry e backoff exponencial.
    Distingue entre erros transitórios (retry) e permanentes (falha imediata).
    """
    headers = {"User-Agent": USER_AGENT}
    espera = BACKOFF_INICIAL

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT)

            # Rate limit: respeita o Retry-After se a API informar
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", espera))
                logger.warning(
                    f"Tentativa {tentativa}/{MAX_TENTATIVAS}: rate limit. "
                    f"Aguardando {retry_after}s..."
                )
                time.sleep(retry_after)
                espera *= 2
                continue

            # Erros 5xx do servidor: vale tentar de novo
            if 500 <= resp.status_code < 600:
                logger.warning(
                    f"Tentativa {tentativa}/{MAX_TENTATIVAS}: erro {resp.status_code} do servidor. "
                    f"Aguardando {espera}s..."
                )
                time.sleep(espera)
                espera *= 2
                continue

            # Outros erros 4xx: problema da nossa request, não adianta tentar de novo
            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            logger.warning(
                f"Tentativa {tentativa}/{MAX_TENTATIVAS}: timeout. "
                f"Aguardando {espera}s..."
            )
            time.sleep(espera)
            espera *= 2

        except requests.exceptions.ConnectionError as e:
            logger.warning(
                f"Tentativa {tentativa}/{MAX_TENTATIVAS}: erro de conexão ({e}). "
                f"Aguardando {espera}s..."
            )
            time.sleep(espera)
            espera *= 2

    raise RuntimeError(
        f"Falha ao acessar API após {MAX_TENTATIVAS} tentativas."
    )


def buscar_cotacoes(moedas: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Busca cotações atuais para a lista de moedas.

    Returns:
        DataFrame com colunas: codigo, nome, alta, baixa, variacao, pct_variacao,
        bid, ask, timestamp_origem, data_coleta.
    """
    moedas = moedas or MOEDAS
    url = f"{API_BASE}/{','.join(moedas)}"

    logger.info(f"Chamando API: {url}")
    data = _fazer_requisicao(url)

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
