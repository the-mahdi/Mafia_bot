import os
import sys
import sqlite3
import pytest

# Ensure repo root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import src.db as db

@pytest.fixture
def memory_db(monkeypatch):
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    cursor = conn.cursor()
    monkeypatch.setattr(db, 'conn', conn)
    monkeypatch.setattr(db, 'cursor', cursor)
    db.initialize_database()
    yield db
    conn.close()
