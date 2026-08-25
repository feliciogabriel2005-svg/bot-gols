import logging
from datetime import datetime, timezone
import pandas as pd
from config import SystemConfig
from database.connection import get_db_connection
from models.signal import Signal
from core.settlement import PaperSettlementService
from core.data_provider import APIFootballProvider

class PaperTradingEngine:
    def __init__(self):
        self.config = SystemConfig()
        self.db_path = self.config.DB_PATH
        self.stake = float(self.config.PAPER_STAKE)
        self.initial_bankroll = float(self.config.PAPER_BANKROLL)

    def record_paper_trade(self, signal: Signal):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()

        cursor.execute('''
            INSERT INTO paper_trades (
                signal_id, fixture_id, match_name, market, line,
                minute_at_signal, score_at_signal, odd, estimated_prob,
                implied_prob, edge, ev, confidence_score, confidence_grade,
                stake, outcome, pnl, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0.0, ?)
        ''', (
            signal.id, signal.raw_data_snapshot.get("match_id", ""), signal.match_name,
            signal.market, signal.line or "Over 0.5", signal.minute, signal.score,
            signal.odd, signal.estimated_prob, signal.implied_prob, signal.edge,
            signal.ev, signal.confidence_score, signal.confidence_grade,
            self.stake, now_iso
        ))
        conn.commit()
        logging.info(f"[PAPER_TRADING] Trade PENDING aberto: {signal.match_name} ({signal.confidence_grade}) @ {signal.odd}")

    def settle_pending_trades(self, live_matches_map: dict):
        """
        Compatibilidade com testes legados que chamavam settle_pending_trades(live_map).
        Delega para o PaperSettlementService injetando um provider mock/compatível se necessário.
        """
        logging.info("[PAPER_TRADING] settle_pending_trades chamado (legado). Delegando para PaperSettlementService.")
        class MockLegacyProvider:
            def __init__(self, l_map):
                self.l_map = l_map
            def fetch_fixture_by_id(self, f_id):
                f_id_str = str(f_id)
                if f_id_str in self.l_map:
                    m = self.l_map[f_id_str]
                    return {
                        "fixture": {"status": {"short": m.get("status_short", "FT")}},
                        "goals": {"home": m.get("score_home", 0), "away": m.get("score_away", 0)}
                    }
                return None

        provider = MockLegacyProvider(live_matches_map)
        service = PaperSettlementService(provider, self.db_path)
        service.process_pending_trades()

    def get_performance_summary(self) -> dict:
        conn = get_db_connection(self.db_path)
        df = pd.read_sql_query("SELECT * FROM paper_trades", conn)

        if df.empty:
            return {
                "total_signals": 0, "resolved_trades": 0, "pending_trades": 0,
                "wins": 0, "losses": 0, "voids": 0, "win_rate": 0.0,
                "net_profit": 0.0, "roi": 0.0, "current_bankroll": self.initial_bankroll,
                "max_drawdown": 0.0, "by_grade": {}, "by_odd_range": {}
            }

        resolved = df[df["outcome"].isin(["WIN", "LOSS", "VOID"])]
        pending_count = len(df[df["outcome"] == "PENDING"])
        wins = len(df[df["outcome"] == "WIN"])
        losses = len(df[df["outcome"] == "LOSS"])
        voids = len(df[df["outcome"] == "VOID"])
        total_decided = wins + losses

        win_rate = round((wins / total_decided * 100.0), 2) if total_decided > 0 else 0.0
        net_profit = round(float(resolved["pnl"].sum()), 2)
        total_staked = float(resolved[resolved["outcome"].isin(["WIN", "LOSS"])]["stake"].sum())
        roi = round((net_profit / total_staked * 100.0), 2) if total_staked > 0 else 0.0

        current_bankroll = round(self.initial_bankroll + net_profit, 2)

        resolved_sorted = resolved.sort_values("id")
        cum_pnl = resolved_sorted["pnl"].cumsum()
        bank_history = self.initial_bankroll + cum_pnl
        peak = bank_history.cummax()
        drawdowns = (peak - bank_history) / peak * 100.0
        max_dd = round(float(drawdowns.max()), 2) if not drawdowns.empty else 0.0

        by_grade = {}
        for grade in ["A+", "A", "B"]:
            gdf = resolved[resolved["confidence_grade"] == grade]
            g_wins = len(gdf[gdf["outcome"] == "WIN"])
            g_losses = len(gdf[gdf["outcome"] == "LOSS"])
            g_voids = len(gdf[gdf["outcome"] == "VOID"])
            g_total_decided = g_wins + g_losses
            g_wr = round((g_wins / g_total_decided * 100.0), 2) if g_total_decided > 0 else 0.0
            g_pnl = round(float(gdf["pnl"].sum()), 2)
            g_staked = float(gdf[gdf["outcome"].isin(["WIN", "LOSS"])]["stake"].sum())
            g_roi = round((g_pnl / g_staked * 100.0), 2) if g_staked > 0 else 0.0

            by_grade[grade] = {
                "signals": len(df[df["confidence_grade"] == grade]),
                "wins": g_wins, "losses": g_losses, "voids": g_voids,
                "win_rate": g_wr, "profit": g_pnl, "roi": g_roi,
                "avg_odd": round(float(gdf["odd"].mean()), 2) if not gdf.empty else 0.0,
                "avg_edge": round(float(gdf["edge"].mean()), 2) if not gdf.empty else 0.0,
                "avg_ev": round(float(gdf["ev"].mean()), 2) if not gdf.empty else 0.0
            }

        odd_ranges = [
            ("1.50–1.69", 1.50, 1.699),
            ("1.70–1.89", 1.70, 1.899),
            ("1.90–2.09", 1.90, 2.099),
            ("2.10–2.49", 2.10, 2.499),
            ("2.50+", 2.50, 999.0)
        ]
        by_odd_range = {}
        for label, low, high in odd_ranges:
            odf = resolved[(resolved["odd"] >= low) & (resolved["odd"] <= high)]
            o_wins = len(odf[odf["outcome"] == "WIN"])
            o_losses = len(odf[odf["outcome"] == "LOSS"])
            o_voids = len(odf[odf["outcome"] == "VOID"])
            o_total_decided = o_wins + o_losses
            o_wr = round((o_wins / o_total_decided * 100.0), 2) if o_total_decided > 0 else 0.0
            o_pnl = round(float(odf["pnl"].sum()), 2)
            o_staked = float(odf[odf["outcome"].isin(["WIN", "LOSS"])]["stake"].sum())
            o_roi = round((o_pnl / o_staked * 100.0), 2) if o_staked > 0 else 0.0

            by_odd_range[label] = {
                "signals": len(df[(df["odd"] >= low) & (df["odd"] <= high)]),
                "wins": o_wins, "losses": o_losses, "voids": o_voids,
                "win_rate": o_wr, "profit": o_pnl, "roi": o_roi
            }

        return {
            "total_signals": len(df), "resolved_trades": len(resolved),
            "pending_trades": pending_count, "wins": wins, "losses": losses,
            "voids": voids, "win_rate": win_rate, "net_profit": net_profit,
            "roi": roi, "current_bankroll": current_bankroll,
            "max_drawdown": max_dd, "by_grade": by_grade, "by_odd_range": by_odd_range
        }
