"""Analytics and feedback logging using SQLite."""
import sqlite3
import threading
from contextlib import closing
from typing import Optional

from . import config

_local = threading.local()

def _get_db():
    if not hasattr(_local, "conn"):
        # Make sure directory exists
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(config.ANALYTICS_DB, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn

def init_db():
    """Create tables if they don't exist."""
    db = _get_db()
    with closing(db.cursor()) as cur:
        # Table for query logs
        cur.execute('''
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                message TEXT,
                domain TEXT,
                subtype TEXT,
                field TEXT,
                decision TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Table for user feedback
        cur.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                query_id INTEGER,
                is_positive BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (query_id) REFERENCES queries(id)
            )
        ''')
    db.commit()

def log_query(session_id: str, message: str, domain: Optional[str], subtype: Optional[str], field: Optional[str], decision: str) -> int:
    """Log a user query and return its row ID."""
    db = _get_db()
    with closing(db.cursor()) as cur:
        cur.execute('''
            INSERT INTO queries (session_id, message, domain, subtype, field, decision)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, message, domain, subtype, field, decision))
        db.commit()
        return cur.lastrowid

def log_feedback(session_id: str, query_id: int, is_positive: bool) -> None:
    """Record user thumbs up/down for a specific query."""
    db = _get_db()
    with closing(db.cursor()) as cur:
        cur.execute('''
            INSERT INTO feedback (session_id, query_id, is_positive)
            VALUES (?, ?, ?)
        ''', (session_id, query_id, is_positive))
        db.commit()

def get_stats() -> dict:
    """Retrieve top solved problems and general stats."""
    db = _get_db()
    with closing(db.cursor()) as cur:
        cur.execute("SELECT COUNT(*) FROM queries")
        total_queries = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM feedback WHERE is_positive = 1")
        positive_fb = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM feedback WHERE is_positive = 0")
        negative_fb = cur.fetchone()[0]

        # Most solved problems (domain, subtype combinations with highest frequency where decision is answer)
        cur.execute('''
            SELECT domain, subtype, COUNT(*) as count 
            FROM queries 
            WHERE decision = 'answer' AND domain IS NOT NULL 
            GROUP BY domain, subtype 
            ORDER BY count DESC 
            LIMIT 5
        ''')
        top_problems = [{"domain": row["domain"], "subtype": row["subtype"], "count": row["count"]} for row in cur.fetchall()]

    return {
        "total_queries": total_queries,
        "positive_feedback": positive_fb,
        "negative_feedback": negative_fb,
        "top_problems": top_problems
    }

# Initialize database on import
init_db()
