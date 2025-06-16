import asyncio
import types
import importlib
import sys


def load_player_management(monkeypatch, memory_db):
    dummy_config = types.SimpleNamespace(MAINTAINER_ID=1, RANDOM_ORG_API_KEY='', TOKEN='t')
    sys.modules['src.config'] = dummy_config
    module = importlib.import_module('src.handlers.game_management.player_management')
    importlib.reload(module)
    monkeypatch.setattr(module, 'cursor', memory_db.cursor)
    monkeypatch.setattr(module, 'conn', memory_db.conn)
    # isolate from real voting module
    monkeypatch.setattr(module, 'game_voting_data', {})
    async def dummy_process(*a, **k):
        pass
    monkeypatch.setattr(module, 'process_voting_results', dummy_process)
    return module


class DummyBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, *args, **kwargs):
        self.sent.append((args, kwargs))


class DummyUpdate:
    def __init__(self, chat_id=1):
        self.effective_chat = types.SimpleNamespace(id=chat_id)
        self.effective_user = types.SimpleNamespace(id=chat_id)


class DummyContext:
    def __init__(self):
        self.bot = DummyBot()
        self.user_data = {}


def setup_game(memory_db):
    game_id = 'g1'
    memory_db.cursor.execute("INSERT INTO Games (game_id, passcode, moderator_id) VALUES (?, ?, ?)", (game_id, 'p', 1))
    for uid, name in [(1, 'mod'), (2, 'player')]:
        memory_db.cursor.execute("INSERT INTO Users (user_id, username) VALUES (?, ?)", (uid, name))
        memory_db.cursor.execute("INSERT INTO Roles (game_id, user_id, role) VALUES (?, ?, ?)", (game_id, uid, 'R'))
    memory_db.conn.commit()
    return game_id


def test_confirm_elimination(monkeypatch, memory_db):
    module = load_player_management(monkeypatch, memory_db)
    game_id = setup_game(memory_db)
    update = DummyUpdate(1)
    context = DummyContext()
    asyncio.run(module.confirm_elimination(update, context, game_id, 2))
    memory_db.cursor.execute("SELECT eliminated FROM Roles WHERE game_id=? AND user_id=?", (game_id, 2))
    assert memory_db.cursor.fetchone()[0] == 1
    chat_ids = [kwargs['chat_id'] for args, kwargs in context.bot.sent]
    assert {1, 2} <= set(chat_ids)


def test_confirm_revive(monkeypatch, memory_db):
    module = load_player_management(monkeypatch, memory_db)
    game_id = setup_game(memory_db)
    memory_db.cursor.execute("UPDATE Roles SET eliminated=1 WHERE game_id=? AND user_id=?", (game_id, 2))
    memory_db.conn.commit()
    update = DummyUpdate(1)
    context = DummyContext()
    asyncio.run(module.confirm_revive(update, context, game_id, 2))
    memory_db.cursor.execute("SELECT eliminated FROM Roles WHERE game_id=? AND user_id=?", (game_id, 2))
    assert memory_db.cursor.fetchone()[0] == 0

