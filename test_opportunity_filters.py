import unittest
from unittest.mock import MagicMock
from core.opportunity_engine import OpportunityEngine
from core.data_provider import APIFootballProvider
from models.signal import MatchState

class TestOpportunityFilters(unittest.TestCase):

    def setUp(self):
        self.mock_provider = MagicMock(spec=APIFootballProvider)
        self.engine = OpportunityEngine(self.mock_provider)
        self.valid_match = MatchState(
            match_id="7001", home_team="Flamengo", away_team="Palmeiras", league="Brasileirão",
            minute=35, score_home=0, score_away=0, shots_home=12, shots_away=2,
            shots_on_target_home=6, shots_on_target_away=1,
            recent_shots_home={5: 4, 10: 6, 15: 8}, recent_on_target_home={5: 2, 10: 4, 15: 5}
        )
        self.mock_provider.get_snapshot_count.return_value = 5
        self.mock_provider.get_live_odds.return_value = {
            "bookmaker": "Bet365", "market": "Total Goals", "line": "Over 0.5",
            "odd": 2.00, "collected_at": "2026-08-25T10:00:00Z", "fixture_id": "7001"
        }

    def test_minuto_invalido_rejeitado(self):
        self.valid_match.minute = 10
        self.assertIsNone(self.engine.evaluate_match(self.valid_match))

if __name__ == "__main__":
    unittest.main()
