import logging
from datetime import datetime, timezone
from database.connection import get_db_connection

TERMINAL_STATUSES = {"FT", "AET", "PEN"}
CANCELLED_STATUSES = {"POSTP", "CANC", "ABD", "INT"}
LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE"}

class PaperSettlementService:
    """
    Fonte oficial única de Settlement.
    Consulta diretamente o endpoint fixture_id na API-Football para cada trade PENDING.
    """
    def __init__(self, data_provider, db_path: str = "production_live.db"):
        self.provider = data_provider
        self.db_path = db_path

    def process_pending_trades(self):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM paper_trades WHERE outcome = 'PENDING'")
        pending_trades = cursor.fetchall()

        if not pending_trades:
            return

        now_iso = datetime.now(timezone.utc).isoformat()

        fixture_trades = {}
        for trade in pending_trades:
            f_id = str(trade["fixture_id"])
            if f_id not in fixture_trades:
                fixture_trades[f_id] = []
            fixture_trades[f_id].append(trade)

        for f_id, trades in fixture_trades.items():
            logging.info(f"[PAPER_SETTLEMENT] Consultando fixture {f_id} para {len(trades)} trade(s) PENDING")
            
            raw_fix = self.provider.fetch_fixture_by_id(f_id)
            if not raw_fix:
                logging.info(f"[PAPER_SETTLEMENT] Fixture {f_id} sem retorno da API. Continua PENDING.")
                continue

            fix_info = raw_fix.get("fixture", {})
            goals_info = raw_fix.get("goals", {})
            status_short = fix_info.get("status", {}).get("short", "")
            h_goals = goals_info.get("home") if goals_info.get("home") is not None else 0
            a_goals = goals_info.get("away") if goals_info.get("away") is not None else 0

            logging.info(f"[PAPER_SETTLEMENT] Fixture {f_id} status: {status_short}, placar atual: {h_goals}x{a_goals}")

            if status_short in LIVE_STATUSES or (status_short not in TERMINAL_STATUSES and status_short not in CANCELLED_STATUSES):
                logging.info(f"[PAPER_SETTLEMENT] Fixture {f_id} ainda LIVE/Andamento (status: {status_short}). Trade continua PENDING.")
                continue

            for trade in trades:
                try:
                    sig_h, sig_a = map(int, trade["score_at_signal"].lower().split("x"))
                except Exception:
                    sig_h, sig_a = 0, 0

                goals_before_signal = sig_h + sig_a
                goals_current = h_goals + a_goals
                new_goals_after_signal = goals_current - goals_before_signal

                stake = float(trade["stake"])
                odd = float(trade["odd"])

                if status_short in CANCELLED_STATUSES:
                    cursor.execute("UPDATE paper_trades SET outcome = 'VOID', pnl = 0.0, settled_at = ? WHERE id = ?", (now_iso, trade["id"]))
                    logging.info(f"[PAPER_SETTLEMENT] Trade #{trade['id']} → VOID (Partida cancelada/abandonada)")

                elif new_goals_after_signal >= 1:
                    pnl = round(stake * (odd - 1.0), 2)
                    cursor.execute("UPDATE paper_trades SET outcome = 'WIN', pnl = ?, settled_at = ? WHERE id = ?", (pnl, now_iso, trade["id"]))
                    logging.info(f"[PAPER_SETTLEMENT] Trade #{trade['id']} → WIN (+R$ {pnl})")

                elif status_short in TERMINAL_STATUSES:
                    pnl = -stake
                    cursor.execute("UPDATE paper_trades SET outcome = 'LOSS', pnl = ?, settled_at = ? WHERE id = ?", (pnl, now_iso, trade["id"]))
                    logging.info(f"[PAPER_SETTLEMENT] Trade #{trade['id']} → LOSS (-R$ {stake})")

        conn.commit()
