import uuid
import logging
from datetime import datetime, timezone
from config import SystemConfig
from models.signal import MatchState, Signal
from core.pressure_engine import PressureEngine
from core.probability_engine import ProbabilityEngine
from core.odds_engine import OddsEngine
from core.edge_engine import EdgeEngine

class OpportunityEngine:
    def __init__(self, data_provider):
        self.provider = data_provider
        self.config = SystemConfig()
        self.filters = self.config.FILTERS

    def evaluate_match(self, match: MatchState) -> Signal:
        m_name = f"{match.home_team.upper()} x {match.away_team.upper()}"

        if match.minute < self.filters.MIN_GAME_MINUTE or match.minute > self.filters.MAX_GAME_MINUTE:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: Minuto {match.minute}' fora de [{self.filters.MIN_GAME_MINUTE}'-{self.filters.MAX_GAME_MINUTE}']")
            return None

        snap_count = self.provider.get_snapshot_count(match.match_id)
        if snap_count < self.filters.MIN_DATA_POINTS:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: Apenas {snap_count} snapshots, mínimo: {self.filters.MIN_DATA_POINTS}")
            return None

        if match.shots_home is None and match.shots_away is None:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: Dados de finalização ausentes")
            return None

        home_pressure = PressureEngine.calculate_intensity(match, "home")
        away_pressure = PressureEngine.calculate_intensity(match, "away")
        active_team = "away" if away_pressure > home_pressure else "home"
        max_pressure = max(home_pressure, away_pressure)

        if max_pressure < self.filters.MIN_PRESSURE:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: Pressão {max_pressure:.1f} < mínimo {self.filters.MIN_PRESSURE}")
            return None

        odd_data = self.provider.get_live_odds(match.match_id)
        if not odd_data or "odd" not in odd_data:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: Nenhuma odd real para Over 0.5")
            return None

        real_odd = float(odd_data["odd"])
        if real_odd <= 1.00:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: Odd inválida ({real_odd})")
            return None

        prob_est_raw = ProbabilityEngine.estimate_goal_probability(match, 10, active_team)
        if prob_est_raw is None or prob_est_raw <= 0.0:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: Probabilidade estimada inválida")
            return None

        prob_imp_raw = OddsEngine.calculate_implied_probability(real_odd)

        edge_raw = EdgeEngine.calculate_edge(prob_est_raw, prob_imp_raw)
        ev_raw = EdgeEngine.calculate_ev(prob_est_raw, real_odd)

        if edge_raw < self.filters.MIN_EDGE:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: Edge +{edge_raw*100:.1f} pp < mínimo +{self.filters.MIN_EDGE*100:.1f} pp")
            return None

        if ev_raw <= self.filters.MIN_EV:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: EV {ev_raw*100:.1f}% <= 0.0%")
            return None

        s_press = max_pressure / 100.0
        s_ev = min(1.0, max(0.0, ev_raw / 0.30))
        s_edge = min(1.0, max(0.0, edge_raw / 0.20))
        s_prob = prob_est_raw
        s_snaps = min(1.0, snap_count / 10.0)

        confidence_score = (s_press * 0.25 + s_ev * 0.25 + s_edge * 0.20 + s_prob * 0.15 + s_snaps * 0.15) * 100.0
        confidence_score = round(confidence_score, 1)

        if confidence_score < self.filters.MIN_SCORE:
            logging.debug(f"[OPPORTUNITY] {m_name} REJEITADO: Score {confidence_score:.1f} < mínimo {self.filters.MIN_SCORE}")
            return None

        if confidence_score >= 85.0 and edge_raw >= 0.10 and ev_raw >= 0.15 and max_pressure >= 75.0:
            grade = "A+"
        elif confidence_score >= 72.0 and edge_raw >= 0.07 and ev_raw >= 0.08 and max_pressure >= 70.0:
            grade = "A"
        else:
            grade = "B"

        prob_est_pct = round(prob_est_raw * 100.0, 2)
        prob_imp_pct = round(prob_imp_raw * 100.0, 2)
        edge_pp = round(edge_raw * 100.0, 2)
        ev_pct = round(ev_raw * 100.0, 2)
        bookmaker = odd_data.get("bookmaker", "Unknown")

        reasons = [
            f"Pressão ofensiva: {max_pressure:.1f}/100",
            f"Snapshots válidos: {snap_count}",
            f"Probabilidade estimada: {prob_est_pct}%",
            f"Probabilidade implícita: {prob_imp_pct}% ({bookmaker}: {real_odd})",
            f"Edge: +{edge_pp} pp",
            f"EV: +{ev_pct}%",
            f"Score de confiança: {confidence_score}/100"
        ]

        return Signal(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).isoformat(),
            match_name=m_name,
            minute=match.minute,
            score=f"{match.score_home}x{match.score_away}",
            pressure_score=max_pressure,
            estimated_prob=prob_est_pct,
            market="Over 0.5 Gols",
            odd=real_odd,
            implied_prob=prob_imp_pct,
            edge=edge_pp,
            ev=ev_pct,
            confidence_score=confidence_score,
            confidence_grade=grade,
            reasons=reasons,
            raw_data_snapshot=match.__dict__,
            bookmaker=bookmaker,
            line=odd_data.get("line", "Over 0.5"),
            odd_collected_at=odd_data.get("collected_at")
        )
