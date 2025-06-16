import ast


def get_is_valid_passcode():
    with open('src/handlers/passcode_handler.py', 'r') as f:
        source = f.read()
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'is_valid_passcode':
            code = ast.get_source_segment(source, node)
            namespace = {}
            exec(code, namespace)
            return namespace['is_valid_passcode']
    raise RuntimeError('Function not found')


def test_is_valid_passcode():
    func = get_is_valid_passcode()
    assert func('123e4567-e89b-42d3-a456-426614174000')
    assert not func('not-a-uuid')
