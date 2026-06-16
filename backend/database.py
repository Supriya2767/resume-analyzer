# database.py - SQLite Database Module
# SQLite is a file-based database — no server needed.
# Python has sqlite3 built-in, so no extra install required.

import sqlite3
from datetime import datetime

# The database will be saved as this file in the backend folder
DB_FILE = "resume_analyzer.db"


def get_connection():
    """
    Opens a connection to the SQLite database file.
    row_factory lets us access columns by name: row["filename"]
    instead of by index: row[0]
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    """
    Creates the 'analyses' table if it doesn't already exist.
    Safe to run every time the app starts.
    
    Column types:
    - INTEGER PRIMARY KEY AUTOINCREMENT = auto-numbered ID
    - TEXT = string
    - REAL = decimal number
    - DATETIME = date/time string
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            ats_score REAL DEFAULT 0,
            match_percentage REAL DEFAULT 0,
            analysis_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database ready.")


def save_analysis(filename: str, ats_score: float, match_percentage: float):
    """
    Inserts a new analysis record into the database.
    
    IMPORTANT: We use ? placeholders instead of f-strings.
    This prevents SQL injection attacks.
    Never do: f"INSERT INTO ... VALUES ('{filename}')"
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO analyses (filename, ats_score, match_percentage, analysis_date)
        VALUES (?, ?, ?, ?)
    """, (filename, ats_score, match_percentage, now))

    conn.commit()
    conn.close()


def get_all_analyses():
    """
    Fetches all rows from the analyses table.
    Returns a list of dicts sorted by most recent first.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, filename, ats_score, match_percentage, analysis_date
        FROM analyses
        ORDER BY analysis_date DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    # Convert sqlite3.Row objects → plain Python dicts
    # FastAPI needs plain dicts to serialize to JSON
    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "ats_score": row["ats_score"],
            "match_percentage": row["match_percentage"],
            "analysis_date": row["analysis_date"],
        }
        for row in rows
    ]


# Auto-create tables when this module is imported
create_tables()