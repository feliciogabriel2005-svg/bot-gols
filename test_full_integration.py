import unittest
import os
import sqlite3
from unittest.mock import MagicMock, patch
from core.live_scanner import LiveScanner
from core.alert_system import TelegramNotifier
from database.connection import init_db

class TestFullSystemIntegration(unittest.TestCase):

    def setUp(self):
        self.test_db = "test_integration.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        conn = sqlite3.connect(self.test_db)
        init_db(conn)
        conn.close()

        os.environ["DB_PATH"] = self.test_db
        os.environ["API_FOOTBALL_KEY"] = "test_key_123456"

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_api_indisponivel_nao_derruba_scanner(self):
        scanner = LiveScanner()
        with patch.object(scanner.provider, 'fetch_live_matches', side_effect=Exception("API Down")):
            try:
                scanner.run_cycle()
            except Exception as e:
                self.fail(f"O scanner travou inesperadamente: {e}")

if __name__ == "__main__":
    unittest.main()
