import unittest
import os
import sqlite3
from unittest.mock import MagicMock, patch
from core.paper_trading import PaperTradingEngine
from core.settlement import PaperSettlementService
from core.live_scanner import PersistentAlertDeduplicator
from database.connection import init_db
from models.signal import Signal

class TestPrompt7Corrections(unittest.TestCase):

    def setUp(self):
        self.test_db = "test_prompt7.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

        conn = sqlite3.connect(self.test_db)
        init_db(conn)
        conn.close()

        os.environ["DB_PATH"] = self.test_db
        os.environ["PAPER_STAKE"] = "100"
        os.environ["PAPER_BANKROLL"] = "1000"

        self.engine = PaperTradingEngine()
        self.engine.db_path = self.test_db

        self.mock_provider = MagicMock()
        self.settlement_service = PaperSettlementService(self.mock_provider, self.test_db)

        self.sample_signal = Signal(
            id="sig100", timestamp="2026-08-25T10:00:00Z", match_name="FLAMENGO x PALMEIRAS",
            minute=65, score="0x0", pressure_score=80.0, estimated_prob=65.0,
            market="Over 0.5 Gols", odd=2.00, implied_prob=50.0, edge=15.0, ev=30.0,
            confidence_score=85.0, confidence_grade="A+", reasons=["Teste"],
            raw_data_snapshot={"match_id": "123"}, line="Over 0.5"
        )

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_settle_win_100_pnl(self):
        self.engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "FT"}},
            "goals": {"home": 1, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig100'").fetchone()

        self.assertEqual(trade["outcome"], "WIN")
        self.assertEqual(trade["pnl"], 100.0)

    def test_settle_loss_minus_100_pnl(self):
        self.engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "FT"}},
            "goals": {"home": 0, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig100'").fetchone()

        self.assertEqual(trade["outcome"], "LOSS")
        self.assertEqual(trade["pnl"], -100.0)

    def test_settle_pending_status(self):
        self.engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "2H"}},
            "goals": {"home": 2, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig100'").fetchone()

        self.assertEqual(trade["outcome"], "PENDING")

    def test_settle_void_status(self):
        self.engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "CANC"}},
            "goals": {"home": 0, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig100'").fetchone()

        self.assertEqual(trade["outcome"], "VOID")
        self.assertEqual(trade["pnl"], 0.0)

    def test_persistent_deduplication(self):
        dedup = PersistentAlertDeduplicator(self.test_db)
        self.assertTrue(dedup.should_emit(self.sample_signal))
        self.assertFalse(dedup.should_emit(self.sample_signal))

    def test_multiple_distinct_signals_allowed(self):
        dedup = PersistentAlertDeduplicator(self.test_db)
        self.assertTrue(dedup.should_emit(self.sample_signal))
        
        signal_2 = Signal(
            id="sig101", timestamp="2026-08-25T10:05:00Z", match_name="FLAMENGO x PALMEIRAS",
            minute=75, score="0x0", pressure_score=85.0, estimated_prob=70.0,
            market="Over 0.5 Gols", odd=2.20, implied_prob=45.0, edge=25.0, ev=54.0,
            confidence_score=90.0, confidence_grade="A+", reasons=["Teste 2"],
            raw_data_snapshot={"match_id": "123"}, line="Over 1.5"
        )
        self.assertTrue(dedup.should_emit(signal_2))

    def test_settled_after_disappearing_from_live(self):
        self.engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "FT"}},
            "goals": {"home": 1, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig100'").fetchone()

        self.assertEqual(trade["outcome"], "WIN")
        self.assertEqual(trade["pnl"], 100.0)

if __name__ == "__main__":
    unittest.main()
