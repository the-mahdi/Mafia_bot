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


def test_final_confirm_vote_triggers_results(monkeypatch, memory_db):
    module = load_voting(monkeypatch, memory_db)
    gid = setup_game(memory_db)
    module.game_voting_data[gid] = {
        'votes': {1: [2]},
        'player_ids': [1, 2, 3],
        'player_names': {1: 'mod', 2: 'A', 3: 'B'},
        'summary_message_id': None,
        'anonymous': False,
        'voters': {1},
        'permissions': {1: {'can_vote': True, 'can_be_voted': True},
                        2: {'can_vote': True, 'can_be_voted': True},
                        3: {'can_vote': True, 'can_be_voted': True}},
    }

    called_summary = []
    async def fake_summary(ctx, gid_param):
        called_summary.append(gid_param)

    processed = []
    async def fake_process(update, ctx, gid_param):
        processed.append(gid_param)
        module.game_voting_data.pop(gid_param, None)

    monkeypatch.setattr(module, 'send_voting_summary', fake_summary)
    monkeypatch.setattr(module, 'process_voting_results', fake_process)

    query = types.SimpleNamespace(data=f"final_confirm_vote_{gid}",
                                  message=types.SimpleNamespace(chat_id=1, message_id=1))
    async def answer():
        pass
    async def edit_message_text(text):
        query.edited = text
    query.answer = answer
    query.edit_message_text = edit_message_text

    update = DummyUpdate(1)
    update.callback_query = query
    context = DummyContext()

    asyncio.run(module.final_confirm_vote(update, context))

    assert query.edited == "Your votes have been finally confirmed."
    assert called_summary == [gid]
    assert processed == [gid]
    assert gid not in module.game_voting_data

