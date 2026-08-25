import unittest
import os
import sqlite3
from unittest.mock import MagicMock
from core.settlement import PaperSettlementService
from core.live_scanner import PersistentAlertDeduplicator
from core.paper_trading import PaperTradingEngine
from database.connection import init_db
from models.signal import Signal

class TestPrompt7V2Corrections(unittest.TestCase):

    def setUp(self):
        self.test_db = "test_v2.db"
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
            id="sig900", timestamp="2026-08-25T10:00:00Z", match_name="GREMIO x INTER",
            minute=65, score="0x0", pressure_score=80.0, estimated_prob=65.0,
            market="Over 0.5 Gols", odd=2.00, implied_prob=50.0, edge=15.0, ev=30.0,
            confidence_score=85.0, confidence_grade="A+", reasons=["Teste"],
            raw_data_snapshot={"match_id": "777"}, line="Over 0.5"
        )

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_A_live_pending(self):
        """Partida LIVE -> PENDING."""
        self.paper_engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "2H"}},
            "goals": {"home": 0, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig900'").fetchone()
        self.assertEqual(trade["outcome"], "PENDING")

    def test_B_ft_win(self):
        """Partida finalizada FT com gol após sinal -> WIN."""
        self.paper_engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "FT"}},
            "goals": {"home": 1, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig900'").fetchone()
        self.assertEqual(trade["outcome"], "WIN")
        self.assertEqual(trade["pnl"], 100.0)

    def test_C_ft_loss(self):
        """Partida finalizada FT sem gol após sinal -> LOSS."""
        self.paper_engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "FT"}},
            "goals": {"home": 0, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig900'").fetchone()
        self.assertEqual(trade["outcome"], "LOSS")
        self.assertEqual(trade["pnl"], -100.0)

    def test_D_cancelled_void(self):
        """Partida cancelada -> VOID."""
        self.paper_engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "CANC"}},
            "goals": {"home": 0, "away": 0}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig900'").fetchone()
        self.assertEqual(trade["outcome"], "VOID")
        self.assertEqual(trade["pnl"], 0.0)

    def test_E_disappear_from_live_resolved_via_fixture_id(self):
        """Partida desaparece do live=all -> settlement resolve via fixture_id."""
        self.paper_engine.record_paper_trade(self.sample_signal)
        self.mock_provider.fetch_fixture_by_id.return_value = {
            "fixture": {"status": {"short": "FT"}},
            "goals": {"home": 0, "away": 1}
        }
        self.settlement_service.process_pending_trades()

        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        trade = conn.cursor().execute("SELECT * FROM paper_trades WHERE signal_id='sig900'").fetchone()
        self.assertEqual(trade["outcome"], "WIN")

    def test_F_restart_deduplication(self):
        """Reinício do scanner -> deduplicação persistente no SQLite."""
        dedup_1 = PersistentAlertDeduplicator(self.test_db)
        self.assertTrue(dedup_1.should_emit(self.sample_signal))

        dedup_2 = PersistentAlertDeduplicator(self.test_db)
        self.assertFalse(dedup_2.should_emit(self.sample_signal))

    def test_G_multiple_distinct_signals_allowed(self):
        """Dois sinais legítimos diferentes são permitidos."""
        dedup = PersistentAlertDeduplicator(self.test_db)
        self.assertTrue(dedup.should_emit(self.sample_signal))

        signal_diff = Signal(
            id="sig901", timestamp="2026-08-25T10:05:00Z", match_name="GREMIO x INTER",
            minute=75, score="0x0", pressure_score=85.0, estimated_prob=70.0,
            market="Over 0.5 Gols", odd=2.20, implied_prob=45.0, edge=25.0, ev=54.0,
            confidence_score=90.0, confidence_grade="A+", reasons=["Teste 2"],
            raw_data_snapshot={"match_id": "777"}, line="Over 1.5"
        )
        self.assertTrue(dedup.should_emit(signal_diff))

if __name__ == "__main__":
    unittest.main()
