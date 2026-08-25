import math
from typing import Optional
from models.signal import MatchState
from core.pressure_engine import PressureEngine

class ProbabilityEngine:
    BASE_GOAL_RATE_PER_MINUTE = 0.03  # ~2.7 gols por 90 min (0.03 gols/min)

    @classmethod
    def estimate_goal_probability(cls, match: MatchState, window_minutes: int, team: str) -> Optional[float]:
        if match.shots_home is None and match.shots_away is None:
            return None

        p_score = PressureEngine.calculate_intensity(match, team)
        
        if p_score <= 0.0:
            return 0.0

        intensity_factor = p_score / 50.0
        lambda_param = (cls.BASE_GOAL_RATE_PER_MINUTE * window_minutes) * intensity_factor
        prob_raw = 1.0 - math.exp(-lambda_param)

        return max(0.0, min(1.0, prob_raw))
