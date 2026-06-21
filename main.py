"""
Pipeline ETL — orquestrador principal.

Executa: Extract → Transform → Load
Roda manualmente via `python main.py` ou agendado por cron / GitHub Actions.
"""
import logging
import sys
from datetime import datetime, timezone

from etl.extract import buscar_cotacoes
from etl.transform import transformar
from etl.load import obter_engine, criar_schema, carregar


def configurar_logs() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("pipeline.log"),
        ],
    )


def main() -> int:
    configurar_logs()
    log = logging.getLogger("pipeline")
    log.info("=" * 60)
    log.info(f"Pipeline iniciado em {datetime.now(timezone.utc).isoformat()}")

    try:
        # 1. EXTRACT
        log.info("[1/3] Extraindo dados da API...")
        df = buscar_cotacoes()

        # 2. TRANSFORM
        log.info("[2/3] Transformando dados...")
        df = transformar(df)

        # 3. LOAD
        log.info("[3/3] Carregando no banco...")
        engine = obter_engine()
        criar_schema(engine)
        n = carregar(df, engine)

        log.info(f"✅ Pipeline concluído — {n} registros novos.")
        return 0

    except Exception as e:
        log.exception(f"❌ Pipeline falhou: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
