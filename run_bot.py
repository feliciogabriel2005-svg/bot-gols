import logging
from config import SystemConfig
from core.live_scanner import LiveScanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot_execution.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

if __name__ == "__main__":
    logging.info("=== INICIANDO BOT DE OPORTUNIDADES EM GOLS (AUDITADO) ===")
    config = SystemConfig()
    logging.info(f"📍 Modo: {config.ENV} | Operação: {config.MODE} | DB: {config.DB_PATH}")
    logging.info(f"🔑 Chave API: {config.get_masked_key()} | Host: {config.API_FOOTBALL_HOST}")
    
    scanner = LiveScanner()
    scanner.start()
