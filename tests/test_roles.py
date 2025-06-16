import json
import importlib
import pytest


def reload_roles(monkeypatch, tmp_path, roles_content, templates_content):
    roles_json = tmp_path / 'roles.json'
    roles_json.write_text(json.dumps(roles_content))
    templates_json = tmp_path / 'role_templates.json'
    templates_json.write_text(json.dumps(templates_content))
    import src.roles as roles
    monkeypatch.setattr('src.utils.resource_path', lambda p: roles_json if 'roles.json' in p else templates_json)
    importlib.reload(roles)
    return roles


def test_load_roles(monkeypatch, tmp_path):
    roles_content = {"roles": [{"name": "A", "description": "desc", "faction": "F"}]}
    templates_content = {"templates": {"1": [{"name": "t1", "roles": {"A": 1}}]}, "pending_templates": {}}
    roles = reload_roles(monkeypatch, tmp_path, roles_content, templates_content)
    assert roles.available_roles == ['A']
    assert roles.role_descriptions['A'] == 'desc'
    assert roles.role_templates == {"1": [{"name": "t1", "roles": {"A": 1}}]}
    assert roles.pending_templates == {}

    roles.save_role_templates({'x': [1]}, {'y': []})
    saved = json.loads((tmp_path / 'role_templates.json').read_text())
    assert saved['templates'] == {'x': [1]}
    assert saved['pending_templates'] == {'y': []}


def test_load_role_factions(monkeypatch, tmp_path):
    roles_content = {"roles": [
        {"name": "A", "description": "desc", "faction": "F1"},
        {"name": "B", "description": "desc2", "faction": "F2"}
    ]}
    templates_content = {"templates": {}, "pending_templates": {}}
    roles = reload_roles(monkeypatch, tmp_path, roles_content, templates_content)
    assert roles.role_factions == {"A": "F1", "B": "F2"}
