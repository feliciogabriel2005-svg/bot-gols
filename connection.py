import sqlite3

def get_db_connection(db_path="production_live.db"):
    conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    init_db(conn)
    return conn

def init_db(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS live_match_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            match_minute INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            home_shots INTEGER,
            away_shots INTEGER,
            home_shots_on_target INTEGER,
            away_shots_on_target INTEGER,
            home_attacks INTEGER,
            away_attacks INTEGER,
            home_dangerous_attacks INTEGER,
            away_dangerous_attacks INTEGER,
            home_possession INTEGER,
            away_possession INTEGER,
            home_corners INTEGER,
            away_corners INTEGER,
            home_xg REAL,
            away_xg REAL,
            raw_json TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_fixture ON live_match_snapshots(fixture_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_collected ON live_match_snapshots(collected_at)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_fixtures_snapshot (
            fixture_id TEXT PRIMARY KEY,
            league TEXT,
            teams TEXT,
            minute INTEGER,
            score TEXT,
            snapshot_json TEXT,
            collected_at TEXT,
            live_eligible INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS live_odds_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id TEXT,
            bookmaker TEXT,
            market TEXT,
            line TEXT,
            odd REAL,
            collected_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS engine_evaluations (
            id TEXT PRIMARY KEY,
            fixture_id TEXT,
            match_name TEXT,
            minute INTEGER,
            pressure_score REAL,
            estimated_prob REAL,
            odd REAL,
            implied_prob REAL,
            edge REAL,
            ev REAL,
            confidence_grade TEXT,
            reasons TEXT,
            collected_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT NOT NULL,
            fixture_id TEXT NOT NULL,
            match_name TEXT NOT NULL,
            market TEXT NOT NULL,
            line TEXT NOT NULL,
            minute_at_signal INTEGER NOT NULL,
            score_at_signal TEXT NOT NULL,
            odd REAL NOT NULL,
            estimated_prob REAL NOT NULL,
            implied_prob REAL NOT NULL,
            edge REAL NOT NULL,
            ev REAL NOT NULL,
            confidence_score REAL NOT NULL,
            confidence_grade TEXT NOT NULL,
            stake REAL NOT NULL,
            outcome TEXT NOT NULL DEFAULT 'PENDING',
            pnl REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            settled_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emitted_signals (
            dedup_key TEXT PRIMARY KEY,
            fixture_id TEXT NOT NULL,
            market TEXT NOT NULL,
            line TEXT NOT NULL,
            emitted_at TEXT NOT NULL
        )
    ''')
    conn.commit()
