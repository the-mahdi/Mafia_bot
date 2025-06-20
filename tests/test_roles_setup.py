import asyncio
import types
import importlib
import sys

def load_roles_setup(monkeypatch):
    dummy_config = types.SimpleNamespace(RANDOM_ORG_API_KEY='', MAINTAINER_ID=1, TOKEN='t')
    sys.modules['src.config'] = dummy_config
    if 'src.handlers.game_management.roles_setup' in sys.modules:
        module = importlib.reload(sys.modules['src.handlers.game_management.roles_setup'])
    else:
        module = importlib.import_module('src.handlers.game_management.roles_setup')
    return module

class DummyBot:
    def __init__(self):
        self.sent = []
        self.edited = []
    async def send_message(self, *args, **kwargs):
        self.sent.append((args, kwargs))
        return types.SimpleNamespace(message_id=1, **kwargs)
    async def edit_message_text(self, *args, **kwargs):
        self.edited.append(kwargs)

class DummyUpdate:
    def __init__(self):
        self.effective_chat = types.SimpleNamespace(id=1)
        self.effective_user = types.SimpleNamespace(id=1)

class DummyContext:
    def __init__(self):
        self.bot = DummyBot()
        self.user_data = {}

async def run_confirm_and_set_roles(module, game_id):
    update = DummyUpdate()
    context = DummyContext()
    return await module.confirm_and_set_roles(update, context, game_id)


def setup_game(memory_db, roles, counts):
    game_id = 'g1'
    memory_db.cursor.execute(
        "INSERT INTO Games (game_id, passcode, moderator_id) VALUES (?, ?, ?)",
        (game_id, 'p', 1)
    )
    for user_id in [1, 2]:
        memory_db.cursor.execute(
            "INSERT INTO Roles (game_id, user_id, role) VALUES (?, ?, ?)",
            (game_id, user_id, None)
        )
    for role, count in zip(roles, counts):
        memory_db.cursor.execute(
            "INSERT INTO GameRoles (game_id, role, count) VALUES (?, ?, ?)",
            (game_id, role, count)
        )
    memory_db.conn.commit()
    return game_id


def test_confirm_and_set_roles_success(monkeypatch, memory_db):
    module = load_roles_setup(monkeypatch)
    game_id = setup_game(memory_db, ['A', 'B'], [1, 1])
    monkeypatch.setattr(module, 'RANDOM_ORG_API_KEY', '')
    monkeypatch.setattr(module, 'role_descriptions', {'A': 'descA', 'B': 'descB'})
    async def fake_shuffle(lst, api_key=None):
        return lst
    monkeypatch.setattr(module, 'get_random_shuffle', fake_shuffle)
    monkeypatch.setattr(module.random, 'shuffle', lambda x: None)
    result = asyncio.run(run_confirm_and_set_roles(module, game_id))
    assert result == (True, 'fallback (local random)')
    memory_db.cursor.execute("SELECT role FROM Roles WHERE game_id=? ORDER BY user_id", (game_id,))
    roles_assigned = [r[0] for r in memory_db.cursor.fetchall()]
    assert roles_assigned == ['A', 'B']
    memory_db.cursor.execute("SELECT randomness_method FROM Games WHERE game_id=?", (game_id,))
    assert memory_db.cursor.fetchone()[0] == 'fallback (local random)'


def test_confirm_and_set_roles_mismatch(monkeypatch, memory_db):
    module = load_roles_setup(monkeypatch)
    game_id = setup_game(memory_db, ['A'], [1])
    monkeypatch.setattr(module, 'RANDOM_ORG_API_KEY', '')
    monkeypatch.setattr(module, 'role_descriptions', {'A': 'descA'})
    monkeypatch.setattr(module, 'get_random_shuffle', lambda lst, api_key=None: lst)
    monkeypatch.setattr(module.random, 'shuffle', lambda x: None)
    # Add an extra player without corresponding role count
    memory_db.cursor.execute("INSERT INTO Roles (game_id, user_id, role) VALUES (?, ?, ?)", (game_id, 3, None))
    memory_db.conn.commit()
    result = asyncio.run(run_confirm_and_set_roles(module, game_id))
    assert result == (False, 'Mismatch in roles and players')

async def run_show_roles(module, context, page, message_id=None):
    update = DummyUpdate()
    context.user_data['current_page'] = page
    return await module.show_role_buttons(update, context, message_id=message_id)


def test_show_role_buttons_pagination(monkeypatch, memory_db):
    module = load_roles_setup(monkeypatch)
    # limit roles for predictability
    roles = [f'R{i}' for i in range(6)]
    monkeypatch.setattr(module, 'available_roles', roles)
    monkeypatch.setattr(module, 'ROLES_PER_PAGE', 5)
    game_id = setup_game(memory_db, roles[:2], [1, 1])

    context = DummyContext()
    context.user_data['game_id'] = game_id

    # first page sends message
    msg_id = asyncio.run(run_show_roles(module, context, 0))
    assert context.bot.sent  # message sent
    kb1 = context.bot.sent[0][1]['reply_markup'].inline_keyboard
    data1 = [b.callback_data for row in kb1 for b in row]
    assert 'next_page' in data1 and 'prev_page' not in data1

    # second page edits message
    asyncio.run(run_show_roles(module, context, 1, message_id=msg_id))
    assert context.bot.edited
    kb2 = context.bot.edited[0]['reply_markup'].inline_keyboard
    data2 = [b.callback_data for row in kb2 for b in row]
    assert 'prev_page' in data2 and 'next_page' not in data2

