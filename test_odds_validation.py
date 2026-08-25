import unittest
from unittest.mock import MagicMock
from core.opportunity_engine import OpportunityEngine
from core.data_provider import APIFootballProvider
from models.signal import MatchState

class TestOddsValidation(unittest.TestCase):

    def setUp(self):
        self.mock_provider = MagicMock(spec=APIFootballProvider)
        self.engine = OpportunityEngine(self.mock_provider)
        self.mock_match = MatchState(
            match_id="1001", home_team="Team A", away_team="Team B", league="League X",
            minute=70, score_home=0, score_away=0, shots_home=20, shots_away=2,
            shots_on_target_home=10, shots_on_target_away=1,
            xg_home=2.5, xg_away=0.1,
            recent_shots_home={5: 6, 10: 10, 15: 14}, recent_on_target_home={5: 4, 10: 7, 15: 9},
            recent_xg_home={5: 0.8, 10: 1.5, 15: 2.0}
        )

    def test_1_real_odd_available_returns_signal(self):
        self.mock_provider.get_snapshot_count.return_value = 5
        self.mock_provider.get_live_odds.return_value = {
            "bookmaker": "Bet365", "market": "Total Goals", "line": "Over 0.5",
            "odd": 3.00, "collected_at": "2026-08-25T10:00:00Z", "fixture_id": "1001"
        }
        signal = self.engine.evaluate_match(self.mock_match)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.odd, 3.00)

    def test_2_no_odds_returns_no_signal(self):
        self.mock_provider.get_snapshot_count.return_value = 5
        self.mock_provider.get_live_odds.return_value = None
        signal = self.engine.evaluate_match(self.mock_match)
        self.assertIsNone(signal)

if __name__ == "__main__":
    unittest.main()
