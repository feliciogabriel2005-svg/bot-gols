import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
from models.signal import MatchState
from database.connection import get_db_connection

ALLOWED_LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE"}

def is_valid_current_live_match(fixture_item: dict) -> bool:
    fixture_data = fixture_item.get("fixture", {})
    status_short = fixture_data.get("status", {}).get("short")
    
    if status_short not in ALLOWED_LIVE_STATUSES:
        return False
        
    date_str = fixture_data.get("date")
    if not date_str:
        return False
        
    try:
        match_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        time_diff_hours = (now - match_time).total_seconds() / 3600.0
        if time_diff_hours > 24.0 or time_diff_hours < -12.0:
            return False
    except Exception:
        return False
        
    return True

class APIFootballProvider:
    def __init__(self, api_key: str, api_host: str, db_path: str = "production_live.db"):
        self.api_key = api_key
        self.api_host = api_host
        self.db_path = db_path
        self.headers = {
            "x-apisports-key": self.api_key,
            "x-rapidapi-host": self.api_host
        }

    def fetch_live_matches(self) -> List[MatchState]:
        if not self.api_key:
            return []

        url = f"https://{self.api_host}/fixtures?live=all"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                logging.warning(f"[DATA_PROVIDER] API HTTP {response.status_code} na busca ao vivo")
                return []

            data = response.json().get("response", [])
            matches = []
            for item in data:
                if is_valid_current_live_match(item):
                    normalized = self._normalize_match(item)
                    if normalized:
                        matches.append(normalized)
            return matches
        except Exception as e:
            logging.error(f"[DATA_PROVIDER] Exceção na consulta de partidas ao vivo: {e}")
            return []

    def fetch_match_statistics(self, fixture_id: str) -> Dict[str, dict]:
        url = f"https://{self.api_host}/fixtures/statistics?fixture={fixture_id}"
        stats_dict = {"home": {}, "away": {}}
        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                teams_data = resp.json().get("response", [])
                if len(teams_data) >= 2:
                    for idx, side in [(0, "home"), (1, "away")]:
                        s_list = teams_data[idx].get("statistics", [])
                        for s in s_list:
                            s_type = s.get("type")
                            s_val = s.get("value")
                            stats_dict[side][s_type] = s_val
        except Exception as e:
            logging.error(f"[DATA_PROVIDER] Erro ao buscar estatísticas {fixture_id}: {e}")
        return stats_dict

    def get_snapshot_count(self, fixture_id: str) -> int:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM live_match_snapshots WHERE fixture_id = ?", (fixture_id,))
        row = cursor.fetchone()
        return row[0] if row else 0

    def _get_window_deltas(self, fixture_id: str, current_stats: dict) -> tuple:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        now_utc = datetime.now(timezone.utc)
        
        recent_shots_home = {5: 0, 10: 0, 15: 0}
        recent_shots_away = {5: 0, 10: 0, 15: 0}
        recent_sot_home = {5: 0, 10: 0, 15: 0}
        recent_sot_away = {5: 0, 10: 0, 15: 0}
        recent_xg_home = {5: 0.0, 10: 0.0, 15: 0.0}
        recent_xg_away = {5: 0.0, 10: 0.0, 15: 0.0}

        cur_h_shots = current_stats.get("home_shots") or 0
        cur_a_shots = current_stats.get("away_shots") or 0
        cur_h_sot = current_stats.get("home_sot") or 0
        cur_a_sot = current_stats.get("away_sot") or 0
        cur_h_xg = current_stats.get("home_xg") or 0.0
        cur_a_xg = current_stats.get("away_xg") or 0.0

        for minutes in [5, 10, 15]:
            time_threshold = (now_utc - timedelta(minutes=minutes)).isoformat()
            cursor.execute('''
                SELECT home_shots, away_shots, home_shots_on_target, away_shots_on_target, home_xg, away_xg
                FROM live_match_snapshots
                WHERE fixture_id = ? AND collected_at <= ?
                ORDER BY collected_at DESC LIMIT 1
            ''', (fixture_id, time_threshold))
            past_snap = cursor.fetchone()

            if past_snap:
                p_h_shots = past_snap["home_shots"] if past_snap["home_shots"] is not None else cur_h_shots
                p_a_shots = past_snap["away_shots"] if past_snap["away_shots"] is not None else cur_a_shots
                p_h_sot = past_snap["home_shots_on_target"] if past_snap["home_shots_on_target"] is not None else cur_h_sot
                p_a_sot = past_snap["away_shots_on_target"] if past_snap["away_shots_on_target"] is not None else cur_a_sot
                p_h_xg = past_snap["home_xg"] if past_snap["home_xg"] is not None else cur_h_xg
                p_a_xg = past_snap["away_xg"] if past_snap["away_xg"] is not None else cur_a_xg

                recent_shots_home[minutes] = max(0, cur_h_shots - p_h_shots)
                recent_shots_away[minutes] = max(0, cur_a_shots - p_a_shots)
                recent_sot_home[minutes] = max(0, cur_h_sot - p_h_sot)
                recent_sot_away[minutes] = max(0, cur_a_sot - p_a_sot)
                recent_xg_home[minutes] = max(0.0, round(cur_h_xg - p_h_xg, 2))
                recent_xg_away[minutes] = max(0.0, round(cur_a_xg - p_a_xg, 2))

        return (recent_shots_home, recent_shots_away,
                recent_sot_home, recent_sot_away,
                recent_xg_home, recent_xg_away)

    def _normalize_match(self, item: dict) -> Optional[MatchState]:
        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        fixture_id = str(fixture.get("id"))

        stats = self.fetch_match_statistics(fixture_id)
        
        def parse_stat(side, stat_name, is_float=False):
            val = stats.get(side, {}).get(stat_name)
            if val is None:
                return None
            try:
                if is_float:
                    return float(str(val).replace("%", "").strip())
                return int(val)
            except ValueError:
                return None

        h_shots = parse_stat("home", "Total Shots")
        a_shots = parse_stat("away", "Total Shots")
        h_sot = parse_stat("home", "Shots on Goal")
        a_sot = parse_stat("away", "Shots on Goal")
        h_att = parse_stat("home", "Attacks")
        a_att = parse_stat("away", "Attacks")
        h_dang = parse_stat("home", "Dangerous Attacks")
        a_dang = parse_stat("away", "Dangerous Attacks")
        h_pos = parse_stat("home", "Ball Possession", is_float=True)
        a_pos = parse_stat("away", "Ball Possession", is_float=True)
        h_corn = parse_stat("home", "Corner Kicks")
        a_corn = parse_stat("away", "Corner Kicks")
        h_xg = parse_stat("home", "expected_goals", is_float=True)
        a_xg = parse_stat("away", "expected_goals", is_float=True)

        current_stats_summary = {
            "home_shots": h_shots, "away_shots": a_shots,
            "home_sot": h_sot, "away_sot": a_sot,
            "home_xg": h_xg, "away_xg": a_xg
        }

        rec_sh_h, rec_sh_a, rec_sot_h, rec_sot_a, rec_xg_h, rec_xg_a = self._get_window_deltas(
            fixture_id, current_stats_summary
        )

        return MatchState(
            match_id=fixture_id,
            home_team=teams.get("home", {}).get("name", "Unknown Home"),
            away_team=teams.get("away", {}).get("name", "Unknown Away"),
            league=item.get("league", {}).get("name", "Unknown League"),
            minute=fixture.get("status", {}).get("elapsed") or 0,
            score_home=goals.get("home") if goals.get("home") is not None else 0,
            score_away=goals.get("away") if goals.get("away") is not None else 0,
            shots_home=h_shots,
            shots_away=a_shots,
            shots_on_target_home=h_sot,
            shots_on_target_away=a_sot,
            dangerous_attacks_home=h_dang,
            dangerous_attacks_away=a_dang,
            xg_home=h_xg,
            xg_away=a_xg,
            recent_shots_home=rec_sh_h,
            recent_shots_away=rec_sh_a,
            recent_on_target_home=rec_sot_h,
            recent_on_target_away=rec_sot_a,
            recent_xg_home=rec_xg_h,
            recent_xg_away=rec_xg_a,
            raw_data_snapshot={
                "match_id": fixture_id,
                "fixture": item,
                "statistics": stats,
                "parsed_summary": {
                    "home_attacks": h_att, "away_attacks": a_att,
                    "home_possession": h_pos, "away_possession": a_pos,
                    "home_corners": h_corn, "away_corners": a_corn
                }
            }
        )

    def _is_over_0_5_market(self, market_name: str, value_name: str) -> bool:
        if not market_name or not value_name:
            return False
        m_clean = str(market_name).strip().lower()
        v_clean = str(value_name).strip().lower()

        valid_markets = {"match goals", "goals over/under", "total goals", "alternative total goals", "asian total"}
        is_market_match = any(vm in m_clean for vm in valid_markets) or "goal" in m_clean
        is_selection_match = v_clean in ["over 0.5", "over 0.50", "over 0.5 goals", "mais de 0.5"]

        return is_market_match and is_selection_match

    def get_live_odds(self, match_id: str) -> Optional[Dict[str, any]]:
        if not match_id or not self.api_key:
            return None

        url = f"https://{self.api_host}/odds/live?fixture={match_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code != 200:
                return None

            data = resp.json().get("response", [])
            if not data or not isinstance(data, list):
                return None

            bookmakers = data[0].get("bookmakers", [])
            if not bookmakers:
                return None

            now_iso = datetime.now(timezone.utc).isoformat()

            for bm in bookmakers:
                bm_name = bm.get("name", "Unknown Bookmaker")
                bets = bm.get("bets", [])
                for bet in bets:
                    market_name = bet.get("name")
                    values = bet.get("values", [])
                    for val_item in values:
                        val_label = val_item.get("value")
                        odd_val = val_item.get("odd")

                        if self._is_over_0_5_market(market_name, val_label):
                            try:
                                odd_float = float(odd_val)
                                if odd_float > 1.00:
                                    return {
                                        "bookmaker": bm_name,
                                        "market": "Total Goals",
                                        "line": "Over 0.5",
                                        "odd": odd_float,
                                        "collected_at": now_iso,
                                        "fixture_id": match_id
                                    }
                            except (ValueError, TypeError):
                                continue
        except Exception as e:
            logging.error(f"[DATA_PROVIDER] Exceção ao consultar odds para {match_id}: {e}")

        return None
