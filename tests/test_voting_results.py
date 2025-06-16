import asyncio
import types
import importlib
import sys


def load_voting(monkeypatch, memory_db):
    dummy_config = types.SimpleNamespace(RANDOM_ORG_API_KEY='', MAINTAINER_ID=1)
    sys.modules['src.config'] = dummy_config
    module = importlib.import_module('src.handlers.game_management.voting')
    importlib.reload(module)
    monkeypatch.setattr(module, 'cursor', memory_db.cursor)
    monkeypatch.setattr(module, 'conn', memory_db.conn)
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
    gid = 'g1'
    memory_db.cursor.execute("INSERT INTO Games (game_id, passcode, moderator_id) VALUES (?, ?, ?)", (gid, 'p', 1))
    for uid, name in [(1, 'mod'), (2, 'A'), (3, 'B')]:
        memory_db.cursor.execute("INSERT INTO Users (user_id, username) VALUES (?, ?)", (uid, name))
        memory_db.cursor.execute("INSERT INTO Roles (game_id, user_id, role, eliminated) VALUES (?, ?, ?, 0)", (gid, uid, 'R'))
    memory_db.conn.commit()
    return gid


def test_process_voting_results(monkeypatch, memory_db):
    module = load_voting(monkeypatch, memory_db)
    gid = setup_game(memory_db)
    module.game_voting_data[gid] = {
        'votes': {1: [2], 2: [1], 3: []},
        'player_ids': [1, 2, 3],
        'player_names': {1: 'mod', 2: 'A', 3: 'B'},
        'summary_message_id': None,
        'anonymous': False,
    }
    update = DummyUpdate(1)
    context = DummyContext()
    asyncio.run(module.process_voting_results(update, context, gid))
    assert gid not in module.game_voting_data
    # expect 8 messages: summary+detail to 3 players and moderator
    assert len(context.bot.sent) == 8

