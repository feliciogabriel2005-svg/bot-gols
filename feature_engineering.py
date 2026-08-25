from models.signal import MatchState

class FeatureExtractor:
    @staticmethod
    def extract(match: MatchState, team: str, current_odd: float) -> dict:
        s_5 = match.recent_shots_home.get(5, 0) if team == "home" else match.recent_shots_away.get(5, 0)
        s_10 = match.recent_shots_home.get(10, 0) if team == "home" else match.recent_shots_away.get(10, 0)
        return {
            "minute": match.minute,
            "shots_last_5": s_5,
            "shots_last_10": s_10,
            "odd_current": current_odd
        }
