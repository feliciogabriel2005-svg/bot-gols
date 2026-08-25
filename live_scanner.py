import time
import json
import logging
from datetime import datetime, timezone
from config import SystemConfig
from core.data_provider import APIFootballProvider
from core.opportunity_engine import OpportunityEngine
from core.alert_system import TelegramNotifier
from core.paper_trading import PaperTradingEngine
from core.settlement import PaperSettlementService
from database.connection import get_db_connection, init_db

class PersistentAlertDeduplicator:
    def __init__(self, db_path: str):
        self.db_path = db_path
        conn = get_db_connection(self.db_path)
        init_db(conn)
        conn.close()

    def should_emit(self, signal) -> bool:
        fixture_id = str(signal.raw_data_snapshot.get('match_id'))
        market = signal.market
        line = signal.line or "Over 0.5"
        dedup_key = f"{fixture_id}_{market}_{line}"

        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM emitted_signals WHERE dedup_key = ?", (dedup_key,))
        exists = cursor.fetchone()

        if exists:
            return False

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            INSERT OR IGNORE INTO emitted_signals (dedup_key, fixture_id, market, line, emitted_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (dedup_key, fixture_id, market, line, now_iso))
        conn.commit()
        return True

class LiveScanner:
    def __init__(self):
        self.config = SystemConfig()
        self.provider = APIFootballProvider(self.config.API_FOOTBALL_KEY, self.config.API_FOOTBALL_HOST, self.config.DB_PATH)
        self.engine = OpportunityEngine(self.provider)
        self.notifier = TelegramNotifier()
        self.paper_engine = PaperTradingEngine()
        self.settlement_service = PaperSettlementService(self.provider, self.config.DB_PATH)
        self.deduplicator = PersistentAlertDeduplicator(self.config.DB_PATH)
        self.conn = get_db_connection(self.config.DB_PATH)

    def _save_match_snapshot(self, match):
        parsed = match.raw_data_snapshot.get("parsed_summary", {}) if match.raw_data_snapshot else {}
        now_iso = datetime.now(timezone.utc).isoformat()
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO live_match_snapshots (
                fixture_id, collected_at, match_minute, home_score, away_score,
                home_shots, away_shots, home_shots_on_target, away_shots_on_target,
                home_attacks, away_attacks, home_dangerous_attacks, away_dangerous_attacks,
                home_possession, away_possession, home_corners, away_corners,
                home_xg, away_xg, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            match.match_id, now_iso, match.minute, match.score_home, match.score_away,
            match.shots_home, match.shots_away, match.shots_on_target_home, match.shots_on_target_away,
            parsed.get("home_attacks"), parsed.get("away_attacks"),
            match.dangerous_attacks_home, match.dangerous_attacks_away,
            parsed.get("home_possession"), parsed.get("away_possession"),
            parsed.get("home_corners"), parsed.get("away_corners"),
            match.xg_home, match.xg_away,
            json.dumps(match.raw_data_snapshot)
        ))
        
        cursor.execute('''
            INSERT OR REPLACE INTO raw_fixtures_snapshot
            (fixture_id, league, teams, minute, score, snapshot_json, collected_at, live_eligible)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            match.match_id, match.league, f"{match.home_team} x {match.away_team}",
            match.minute, f"{match.score_home}x{match.score_away}",
            json.dumps(match.raw_data_snapshot), now_iso
        ))
        self.conn.commit()

    def run_cycle(self):
        try:
            logging.info("[SCANNER] Buscando partidas ao vivo na API-Football...")
            matches = self.provider.fetch_live_matches()
            logging.info(f"[SCANNER] Partidas LIVE encontradas: {len(matches)}")
        except Exception as e:
            logging.error(f"[SCANNER] Falha ao buscar partidas ao vivo: {e}")
            return

        for match in matches:
            try:
                self._save_match_snapshot(match)
                
                signal = self.engine.evaluate_match(match)
                if signal and self.deduplicator.should_emit(signal):
                    logging.info(f"[OPPORTUNITY] Oportunidade Detectada: {signal.match_name} [{signal.confidence_grade}] @ {signal.odd}")
                    
                    reasons_str = "; ".join(signal.reasons)
                    cursor = self.conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO engine_evaluations
                        (id, fixture_id, match_name, minute, pressure_score, estimated_prob, odd, implied_prob, edge, ev, confidence_grade, reasons, collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        signal.id, match.match_id, signal.match_name, signal.minute,
                        signal.pressure_score, signal.estimated_prob, signal.odd,
                        signal.implied_prob, signal.edge, signal.ev, signal.confidence_grade,
                        reasons_str, datetime.now(timezone.utc).isoformat()
                    ))
                    self.conn.commit()

                    self.notifier.send_opportunity_alert(signal)
                    self.paper_engine.record_paper_trade(signal)
            except Exception as e:
                logging.error(f"[SCANNER] Erro ao processar partida {match.match_id}: {e}")

        try:
            self.settlement_service.process_pending_trades()
        except Exception as e:
            logging.error(f"[PAPER_SETTLEMENT] Erro ao processar settlement: {e}")

    def start(self):
        logging.info("[SCANNER] Motor de Varredura Iniciado...")
        while True:
            try:
                self.run_cycle()
            except Exception as e:
                logging.error(f"[SCANNER] Exceção no ciclo de varredura: {e}")
            time.sleep(self.config.POLL_INTERVAL_SECONDS)
