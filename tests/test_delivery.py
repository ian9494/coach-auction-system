"""Demo isolation and launch overrides without binding a configured port."""
import pytest
from final_project.config import load_launch_config
from final_project.demo import prepare_demo, demo_auth
from final_project.server.app import load_roster


def test_new_demo_sessions_are_independent_and_existing_root_is_protected(tmp_path):
    roots = [tmp_path / 'first', tmp_path / 'second']
    for root in roots:
        tokens = prepare_demo(root)
        config = load_launch_config(root / 'config.json', project_root=root, environ={})
        roster = load_roster(config)
        assert len(roster.coaches) == 8 and len(roster.roster) == 40
        assert [p.name for p in roster.roster] == [f'Player{i:02d}' for i in range(1, 41)]
        assert set(roster.budgets.values()) == {1000}
        assert not config.path(config.sqlite_file).exists()
        assert 'admin_token' not in repr(demo_auth(root))
        before = tokens.read_bytes()
        with pytest.raises(FileExistsError): prepare_demo(root)
        assert tokens.read_bytes() == before
    assert demo_auth(roots[0]).admin_token != demo_auth(roots[1]).admin_token
    assert set(demo_auth(roots[0]).coach_tokens.values()).isdisjoint(demo_auth(roots[1]).coach_tokens.values())


def test_launch_overrides_are_explicit_and_isolated(tmp_path):
    config = load_launch_config(environ={'FINAL_PROJECT_ROOT': str(tmp_path),
        'FINAL_PROJECT_HOST': '0.0.0.0', 'FINAL_PROJECT_PORT': '3011'})
    assert config.host == '0.0.0.0' and config.port == 3011
    assert config.path(config.sqlite_file).is_relative_to(tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('port', ['3000', '0', '65536', '1.2', 'abc', '-1', '３００１'])
def test_invalid_launch_port_is_rejected(port):
    with pytest.raises(ValueError): load_launch_config(environ={'FINAL_PROJECT_PORT': port})
