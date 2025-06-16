import asyncio
import types
import importlib
import sys

class DummyBot:
    def __init__(self):
        self.sent = []
    async def send_message(self, *args, **kwargs):
        self.sent.append((args, kwargs))

class DummyUpdate:
    def __init__(self, uid=1):
        self.effective_user = types.SimpleNamespace(id=uid)
        self.effective_chat = types.SimpleNamespace(id=uid)

class DummyContext:
    def __init__(self):
        self.bot = DummyBot()
        self.user_data = {}


def load_module(monkeypatch, memory_db, name):
    dummy_cfg = types.SimpleNamespace(MAINTAINER_ID=1, TOKEN='t', RANDOM_ORG_API_KEY='key')
    sys.modules['src.config'] = dummy_cfg
    module = importlib.import_module(f'src.handlers.game_management.{name}')
    importlib.reload(module)
    if hasattr(module, 'conn'):
        monkeypatch.setattr(module, 'conn', memory_db.conn)
    if hasattr(module, 'cursor'):
        monkeypatch.setattr(module, 'cursor', memory_db.cursor)
    return module

def test_create_game(monkeypatch, memory_db):
    module = load_module(monkeypatch, memory_db, 'create_game')
    monkeypatch.setattr(module, 'available_roles', ['A', 'B'])
    seq = iter(['pass', 'gid'])
    monkeypatch.setattr(module.uuid, 'uuid4', lambda: next(seq))
    update = DummyUpdate(10)
    context = DummyContext()
    asyncio.run(module.create_game(update, context))
    memory_db.cursor.execute("SELECT game_id, moderator_id FROM Games")
    row = memory_db.cursor.fetchone()
    assert row == ('gid', 10)
    memory_db.cursor.execute("SELECT COUNT(*) FROM GameRoles WHERE game_id=?", ('gid',))
    assert memory_db.cursor.fetchone()[0] == 2
    assert context.user_data['game_id'] == 'gid'
    assert len(context.bot.sent) == 2


def test_join_game(monkeypatch, memory_db):
    # prepare DB
    memory_db.cursor.execute("INSERT INTO Games (game_id, passcode, moderator_id) VALUES ('gid','code',1)")
    memory_db.conn.commit()
    module = load_module(monkeypatch, memory_db, 'join_game')
    update = DummyUpdate(2)
    context = DummyContext()
    context.user_data['username'] = 'alice'
    asyncio.run(module.join_game(update, context, 'code'))
    memory_db.cursor.execute("SELECT username FROM Users WHERE user_id=2")
    assert memory_db.cursor.fetchone()[0] == 'alice'
    memory_db.cursor.execute("SELECT role FROM Roles WHERE game_id='gid' AND user_id=2")
    assert memory_db.cursor.fetchone()[0] is None
    assert context.user_data['game_id'] == 'gid'
    # two messages: to player and moderator
    assert len(context.bot.sent) == 2


def test_start_game(monkeypatch, memory_db):
    module = load_module(monkeypatch, memory_db, 'start_game')
    monkeypatch.setattr(module, 'role_descriptions', {'A':'descA','B':'descB'})
    monkeypatch.setattr(module, 'role_factions', {'A':'Mafia','B':'Town'})
    # prepare game and roles
    memory_db.cursor.execute("INSERT INTO Games (game_id, passcode, moderator_id, randomness_method) VALUES ('g1','p',1,'Random.org')")
    for uid,name,role in [(1,'mod','A'), (2,'p2','B')]:
        memory_db.cursor.execute("INSERT INTO Users (user_id, username) VALUES (?,?)", (uid,name))
        memory_db.cursor.execute("INSERT INTO Roles (game_id, user_id, role) VALUES ('g1', ?, ?)", (uid,role))
    memory_db.conn.commit()
    update = DummyUpdate(1)
    context = DummyContext()
    context.user_data['game_id'] = 'g1'
    asyncio.run(module.start_game(update, context))
    memory_db.cursor.execute("SELECT started FROM Games WHERE game_id='g1'")
    assert memory_db.cursor.fetchone()[0] == 1
    # two players -> 4 messages total (role to two players + summary + final)
    assert len(context.bot.sent) == 4


def setup_inquiry_game(memory_db):
    memory_db.cursor.execute("INSERT INTO Games (game_id, passcode, moderator_id) VALUES ('inq','p',1)")
    for uid,name,role,elim in [
        (1,'mod','A',0),
        (2,'p1','B',0),
        (3,'p2','B',1)
    ]:
        memory_db.cursor.execute("INSERT INTO Users (user_id, username) VALUES (?,?)", (uid,name))
        memory_db.cursor.execute("INSERT INTO Roles (game_id, user_id, role, eliminated) VALUES ('inq',?,?,?)", (uid,role,elim))
    memory_db.conn.commit()


def test_inquiry_summary(monkeypatch, memory_db):
    module = load_module(monkeypatch, memory_db, 'inquiry')
    monkeypatch.setattr(module, 'role_factions', {'A':'Mafia','B':'Town'})
    monkeypatch.setattr(module, 'escape_markdown', lambda s, version=2: s)
    setup_inquiry_game(memory_db)
    update = DummyUpdate(1)
    context = DummyContext()
    asyncio.run(module.send_inquiry_summary(update, context, 'inq'))
    # 3 players + moderator = 4 messages
    assert len(context.bot.sent) == 4


def test_inquiry_detailed_summary(monkeypatch, memory_db):
    module = load_module(monkeypatch, memory_db, 'inquiry')
    monkeypatch.setattr(module, 'role_factions', {'A':'Mafia','B':'Town'})
    monkeypatch.setattr(module, 'escape_markdown', lambda s, version=2: s)
    setup_inquiry_game(memory_db)
    update = DummyUpdate(1)
    context = DummyContext()
    asyncio.run(module.send_detailed_inquiry_summary(update, context, 'inq'))
    assert len(context.bot.sent) == 4
