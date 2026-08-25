import unittest
import os
import sqlite3
from unittest.mock import MagicMock
from core.paper_trading import PaperTradingEngine
from core.settlement import PaperSettlementService
from database.connection import init_db
from models.signal import Signal

class TestPaperTradingEngine(unittest.TestCase):

    def setUp(self):
        self.test_db = "test_paper_trading.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

        conn = sqlite3.connect(self.test_db)
        init_db(conn)
        conn.close()

        os.environ["DB_PATH"] = self.test_db
        self.engine = PaperTradingEngine()
        self.engine.db_path = self.test_db

        self.sample_signal = Signal(
            id="sig100", timestamp="2026-08-25T10:00:00Z", match_name="FLAMENGO x PALMEIRAS",
            minute=65, score="0x0", pressure_score=80.0, estimated_prob=65.0,
            market="Over 0.5 Gols", odd=2.00, implied_prob=50.0, edge=15.0, ev=30.0,
            confidence_score=85.0, confidence_grade="A+", reasons=["Teste"],
            raw_data_snapshot={"match_id": "9999"}
        )

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_win_resolution(self):
        self.engine.record_paper_trade(self.sample_signal)
        mock_provider = MagicMock()
        mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "FT"}},
            "goals": {"home": 1, "away": 0}
        }
        settlement = PaperSettlementService(mock_provider, self.test_db)
        settlement.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig100'").fetchone()

        self.assertEqual(trade["outcome"], "WIN")
        self.assertEqual(trade["pnl"], 100.0)

if __name__ == "__main__":
    unittest.main()
