import importlib.util
import types
import sys

import src.db as db


def load_base(monkeypatch, cursor):
    dummy_config = types.SimpleNamespace(RANDOM_ORG_API_KEY='')
    sys.modules['src.config'] = dummy_config
    spec = importlib.util.spec_from_file_location('base', 'src/handlers/game_management/base.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    monkeypatch.setattr(base, 'cursor', cursor)
    return base


def test_initialize_database_tables(memory_db):
    memory_db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {t[0] for t in memory_db.cursor.fetchall()}
    assert {'Users', 'Games', 'Roles', 'GameRoles'} <= tables


def test_get_player_count(memory_db, monkeypatch):
    base = load_base(monkeypatch, memory_db.cursor)
    game_id = 'g1'
    memory_db.cursor.execute("INSERT INTO Games (game_id, passcode, moderator_id) VALUES (?, ?, ?)", (game_id, 'p', 1))
    memory_db.cursor.execute("INSERT INTO Roles (game_id, user_id, role) VALUES (?, ?, ?)", (game_id, 1, 'A'))
    memory_db.cursor.execute("INSERT INTO Roles (game_id, user_id, role) VALUES (?, ?, ?)", (game_id, 2, 'B'))
    memory_db.conn.commit()
    assert base.get_player_count(game_id) == 2
