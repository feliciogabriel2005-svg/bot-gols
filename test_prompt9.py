import unittest
import os
import sqlite3
from unittest.mock import MagicMock
from core.settlement import PaperSettlementService
from core.live_scanner import PersistentAlertDeduplicator
from core.paper_trading import PaperTradingEngine
from database.connection import init_db
from models.signal import Signal

class TestPrompt9PromptCorrections(unittest.TestCase):

    def setUp(self):
        self.test_db = "test_prompt9.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

        conn = sqlite3.connect(self.test_db)
        init_db(conn)
        conn.close()

        os.environ["DB_PATH"] = self.test_db
        os.environ["PAPER_STAKE"] = "100"
        os.environ["PAPER_BANKROLL"] = "1000"

        self.paper_engine = PaperTradingEngine()
        self.paper_engine.db_path = self.test_db

        self.mock_provider = MagicMock()
        self.settlement_service = PaperSettlementService(self.mock_provider, self.test_db)

        self.sample_signal = Signal(
            id="sig888", timestamp="2026-08-25T10:00:00Z", match_name="FLAMENGO x VASCO",
            minute=70, score="2x0", pressure_score=80.0, estimated_prob=65.0,
            market="Over 0.5 Gols", odd=2.00, implied_prob=50.0, edge=15.0, ev=30.0,
            confidence_score=85.0, confidence_grade="A+", reasons=["Teste"],
            raw_data_snapshot={"match_id": "555"}, line="Over 0.5"
        )

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_live_2x0_remains_pending(self):
        """Partida LIVE com 2x0 permanece PENDING enquanto em andamento."""
        self.paper_engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "2H"}},
            "goals": {"home": 2, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig888'").fetchone()
        self.assertEqual(trade["outcome"], "PENDING")

    def test_persistent_deduplication_survives_destruction(self):
        """PersistentAlertDeduplicator sobrevive a destruição e recriação do objeto."""
        dedup1 = PersistentAlertDeduplicator(self.test_db)
        self.assertTrue(dedup1.should_emit(self.sample_signal))

        del dedup1
        dedup2 = PersistentAlertDeduplicator(self.test_db)
        self.assertFalse(dedup2.should_emit(self.sample_signal))

if __name__ == "__main__":
    unittest.main()
