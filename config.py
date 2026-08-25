import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    def load_dotenv():
        pass
    load_dotenv()

@dataclass(frozen=True)
class QualityFiltersConfig:
    MIN_GAME_MINUTE: int = 15
    MAX_GAME_MINUTE: int = 85
    MIN_DATA_POINTS: int = 3
    MIN_EDGE: float = 0.05
    MIN_SCORE: float = 60.0
    MIN_PRESSURE: float = 65.0
    MIN_EV: float = 0.0

@dataclass
class SystemConfig:
    ENV: str = os.getenv("APP_ENV", "PRODUCTION")
    MODE: str = os.getenv("MODE", "PAPER_TRADING")
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
    API_FOOTBALL_KEY: str = os.getenv("API_FOOTBALL_KEY", "")
    API_FOOTBALL_HOST: str = os.getenv("API_FOOTBALL_HOST", "v3.football.api-sports.io")
    DB_PATH: str = os.getenv("DB_PATH", "production_live.db")
    
    PAPER_STAKE: float = float(os.getenv("PAPER_STAKE", "100.0"))
    PAPER_BANKROLL: float = float(os.getenv("PAPER_BANKROLL", "1000.0"))

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    BASE_GOAL_RATE_PER_MINUTE: float = float(os.getenv("BASE_GOAL_RATE_PER_MINUTE", "0.03"))

    ENABLE_REAL_BETTING: bool = False
    FILTERS: QualityFiltersConfig = QualityFiltersConfig()

    def is_production(self) -> bool:
        return self.ENV.upper() == "PRODUCTION"

    def get_masked_key(self) -> str:
        if not self.API_FOOTBALL_KEY:
            return "AUSENTE"
        return f"{self.API_FOOTBALL_KEY[:4]}...{self.API_FOOTBALL_KEY[-4:]}"
