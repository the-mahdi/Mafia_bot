import importlib.util
import types
import sys
import asyncio


def load_base(monkeypatch, cursor, api_key='dummy'):
    dummy_config = types.SimpleNamespace(RANDOM_ORG_API_KEY=api_key)
    sys.modules['src.config'] = dummy_config
    spec = importlib.util.spec_from_file_location('base', 'src/handlers/game_management/base.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    if cursor is not None:
        monkeypatch.setattr(base, 'cursor', cursor)
    return base


def test_get_random_shuffle_fallback(monkeypatch):
    base = load_base(monkeypatch, cursor=None, api_key='key')

    class FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        def post(self, *a, **kw):
            class Resp:
                async def __aenter__(self_inner):
                    raise Exception('fail')
                async def __aexit__(self_inner, exc_type, exc, tb):
                    pass
            return Resp()

    monkeypatch.setattr(base.aiohttp, 'ClientSession', lambda: FakeSession())
    monkeypatch.setattr(base.random, 'sample', lambda lst, n: list(reversed(lst)))
    result = asyncio.run(base.get_random_shuffle([1,2,3], 'key'))
    assert result == [3,2,1]


def test_get_templates_for_player_count(monkeypatch, memory_db):
    base = load_base(monkeypatch, memory_db.cursor)
    monkeypatch.setattr(base, 'role_templates', {'5': ['tpl']})
    assert base.get_templates_for_player_count(5) == ['tpl']



def test_get_random_shuffle_success(monkeypatch):
    base = load_base(monkeypatch, cursor=None, api_key='key')

    class FakeResponse:
        def __init__(self):
            self.status = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        async def json(self):
            return {"result": {"random": {"data": [[3, 1, 2]]}}}

    class FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        def post(self, *a, **kw):
            return FakeResponse()

    monkeypatch.setattr(base.aiohttp, 'ClientSession', lambda: FakeSession())
    result = asyncio.run(base.get_random_shuffle([1, 2, 3], 'key'))
    assert result == [3, 1, 2]


def test_get_random_shuffle_empty_no_call(monkeypatch):
    base = load_base(monkeypatch, cursor=None, api_key='key')

    class ShouldNotBeCalled:
        def __init__(self, *a, **kw):
            raise AssertionError("ClientSession should not be called")

    monkeypatch.setattr(base.aiohttp, 'ClientSession', ShouldNotBeCalled)
    monkeypatch.setattr(base.random, 'sample', lambda *a, **k: (_ for _ in ()).throw(AssertionError("sample called")))

    result = asyncio.run(base.get_random_shuffle([], 'key'))
    assert result == []
