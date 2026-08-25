from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class MatchState:
    match_id: str
    home_team: str
    away_team: str
    league: str
    minute: int
    score_home: int
    score_away: int
    shots_home: Optional[int] = None
    shots_away: Optional[int] = None
    shots_on_target_home: Optional[int] = None
    shots_on_target_away: Optional[int] = None
    dangerous_attacks_home: Optional[int] = None
    dangerous_attacks_away: Optional[int] = None
    xg_home: Optional[float] = None
    xg_away: Optional[float] = None
    recent_shots_home: Dict[int, int] = None
    recent_shots_away: Dict[int, int] = None
    recent_on_target_home: Dict[int, int] = None
    recent_on_target_away: Dict[int, int] = None
    recent_xg_home: Dict[int, float] = None
    recent_xg_away: Dict[int, float] = None
    raw_data_snapshot: Dict = None

    def __post_init__(self):
        if self.recent_shots_home is None: self.recent_shots_home = {}
        if self.recent_shots_away is None: self.recent_shots_away = {}
        if self.recent_on_target_home is None: self.recent_on_target_home = {}
        if self.recent_on_target_away is None: self.recent_on_target_away = {}
        if self.recent_xg_home is None: self.recent_xg_home = {}
        if self.recent_xg_away is None: self.recent_xg_away = {}

@dataclass
class Signal:
    id: str
    timestamp: str
    match_name: str
    minute: int
    score: str
    pressure_score: float
    estimated_prob: float
    market: str
    odd: float
    implied_prob: float
    edge: float
    ev: float
    confidence_score: float
    confidence_grade: str
    reasons: List[str]
    raw_data_snapshot: Dict
    bookmaker: Optional[str] = None
    line: Optional[str] = None
    odd_collected_at: Optional[str] = None
