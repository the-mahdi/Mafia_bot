import os
from src.utils import resource_path, generate_voting_summary

def test_resource_path():
    path = resource_path(os.path.join('data', 'roles.json'))
    assert os.path.isabs(path)
    assert path.endswith(os.path.join('data', 'roles.json'))

def test_generate_voting_summary():
    summary = generate_voting_summary(['Alice'], ['Bob'])
    assert 'Alice' in summary
    assert 'Bob' in summary
    assert 'Players Who Have Voted' in summary


def test_generate_voting_summary_empty():
    summary = generate_voting_summary([], [])
    assert 'None' in summary
