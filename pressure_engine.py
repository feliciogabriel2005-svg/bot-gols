from models.signal import MatchState

class PressureEngine:
    @staticmethod
    def calculate_intensity(state: MatchState, team: str) -> float:
        shots_tot = state.shots_home if team == "home" else state.shots_away
        if shots_tot is None:
            return 0.0

        if team == "home":
            rec_shots = state.recent_shots_home or {}
            rec_target = state.recent_on_target_home or {}
            rec_xg = state.recent_xg_home or {}
            total_min = max(state.minute, 1)
            avg_shots_per_min = shots_tot / total_min
        else:
            rec_shots = state.recent_shots_away or {}
            rec_target = state.recent_on_target_away or {}
            rec_xg = state.recent_xg_away or {}
            total_min = max(state.minute, 1)
            avg_shots_per_min = shots_tot / total_min

        xg_5 = rec_xg.get(5) or 0.0
        xg_10 = rec_xg.get(10) or 0.0
        xg_15 = rec_xg.get(15) or 0.0

        w_5min = (rec_shots.get(5, 0) * 12.0) + (rec_target.get(5, 0) * 18.0) + (xg_5 * 40.0)
        w_10min = (rec_shots.get(10, 0) * 6.0) + (rec_target.get(10, 0) * 10.0) + (xg_10 * 25.0)
        w_15min = (rec_shots.get(15, 0) * 3.0) + (rec_target.get(15, 0) * 5.0)  + (xg_15 * 15.0)

        raw_score = (w_5min * 0.5) + (w_10min * 0.3) + (w_15min * 0.2)

        recent_rate = rec_shots.get(10, 0) / 10.0
        acceleration = (recent_rate / avg_shots_per_min) if avg_shots_per_min > 0 else 1.0
        
        final_score = min(100.0, raw_score * min(acceleration, 2.0))
        return round(final_score, 1)
