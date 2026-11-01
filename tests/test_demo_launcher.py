import subprocess
from unittest.mock import Mock, patch

import pytest
from final_project import demo
from final_project.server.auth import AuthConfig


def test_demo_environment():
    original = {'OTHER': 'keep', 'FINAL_PROJECT_ADMIN_TOKEN': 'real-unused'}
    env = demo.demo_environment(original)
    auth = AuthConfig.from_env([f'coach{i:02d}' for i in range(1, 9)], env)
    tokens = [auth.admin_token, *auth.coach_tokens.values()]
    assert len(set(tokens)) == 9
    assert all(16 <= len(token) <= 1024 and token.startswith('DEMO-ONLY-') for token in tokens)
    assert demo.demo_environment(original)['FINAL_PROJECT_ADMIN_TOKEN'] != auth.admin_token
    assert original['FINAL_PROJECT_ADMIN_TOKEN'] == 'real-unused'
    assert env['OTHER'] == 'keep'
    assert env['FINAL_PROJECT_HOST'] == '127.0.0.1'
    assert env['FINAL_PROJECT_PORT'] == '3001'


@pytest.mark.parametrize('count', [2, 8])
def test_commands(count):
    commands = demo.component_commands(count)
    assert len(commands) == count + 2
    assert commands[0] == [demo.sys.executable, '-m', 'final_project.server.app']
    assert commands[-1][-2:] == ['--coach-id', f'coach{count:02d}']
    assert all(command[0] == demo.sys.executable for command in commands)
    assert all('TOKEN' not in ' '.join(command) for command in commands)


@pytest.mark.parametrize('kind,suffix', [('normal','viewer.html'), ('colored','viewer-colored.html'), ('transparent','viewer-transparent.html')])
def test_viewer(kind, suffix):
    assert demo.viewer_url(kind) == demo.SERVER_URL + '/final-project/' + suffix


def test_health_timeout():
    server = Mock()
    server.poll.return_value = None
    with patch.object(demo, 'build_opener') as opener:
        opener.return_value.open.side_effect = OSError('not ready')
        with pytest.raises(TimeoutError):
            demo.wait_for_health(server, timeout=0.01, interval=0.001)
        assert opener.return_value.open.call_count >= 1


def test_health_success_and_exit():
    server = Mock()
    server.poll.return_value = None
    with patch.object(demo, 'build_opener') as opener:
        opener.return_value.open.return_value.__enter__.return_value.status = 200
        opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"ready": true}'
        demo.wait_for_health(server)
    server.poll.return_value = 1
    with pytest.raises(RuntimeError):
        demo.wait_for_health(server)


def test_cleanup_escalates_and_reaps_closed_gui():
    running, closed = Mock(), Mock()
    running.poll.return_value = None
    closed.poll.return_value = 0
    running.wait.side_effect = [subprocess.TimeoutExpired('demo', 5), 0]
    demo.cleanup_processes([running, closed])
    running.kill.assert_called_once()
    assert running.wait.call_count == 2
    closed.kill.assert_not_called()
    closed.terminate.assert_not_called()
    closed.wait.assert_called_once()


def test_launch_readiness_failure_cleans_server():
    server = Mock()
    with patch.object(demo.subprocess, 'Popen', return_value=server) as popen, \
         patch.object(demo, 'wait_for_health', side_effect=TimeoutError), \
         patch.object(demo, 'cleanup_processes') as cleanup, \
         patch.object(demo.socket, 'socket'), \
         patch.object(demo.webbrowser, 'open') as browser:
        with pytest.raises(TimeoutError):
            demo.launch()
        assert popen.call_count == 1
        cleanup.assert_called_once_with([server])
        browser.assert_not_called()


def test_launch_environment_order_and_closed_gui():
    server, admin, coach1, coach2 = [Mock() for _ in range(4)]
    server.poll.return_value = None
    for gui in (admin, coach1, coach2):
        gui.poll.return_value = 0
    events = []
    from pathlib import Path
    children = iter([server, admin, coach1, coach2])
    def spawn(command, **kwargs):
        events.append(command[2])
        assert kwargs['env']['FINAL_PROJECT_ADMIN_TOKEN'].startswith('DEMO-ONLY-')
        assert Path(kwargs['env']['FINAL_PROJECT_ROOT']).is_dir()
        return next(children)
    with patch.object(demo.subprocess, 'Popen', side_effect=spawn), \
         patch.object(demo, 'wait_for_health', side_effect=lambda _: events.append('health')), \
         patch.object(demo, 'cleanup_processes') as cleanup, \
         patch.object(demo.socket, 'socket'), \
         patch.object(demo.webbrowser, 'open') as browser:
        assert demo.launch(viewer='colored') == 0
        assert events[:3] == ['final_project.server.app', 'health', 'final_project.client.admin_app']
        browser.assert_called_once_with(demo.viewer_url('colored'))
        cleanup.assert_called_once_with([server, admin, coach1, coach2])

@pytest.mark.parametrize('module_name,flag,variable', [
    ('admin_app', '--admin-token', 'token'),
    ('coach_app', '--token', 'token'),
])
def test_gui_cli_prefill(module_name, flag, variable):
    from importlib import import_module
    module = import_module('final_project.client.' + module_name)
    cls = 'AdminApp' if module_name == 'admin_app' else 'CoachApp'
    with patch.object(module.tk, 'Tk'), patch.object(module, cls) as app:
        module.main(['--server', demo.SERVER_URL, flag, 'DEMO-ONLY-prefilled-token'])
        app.return_value.url.set.assert_called_once_with(demo.SERVER_URL)
        getattr(app.return_value, variable).set.assert_called_once_with('DEMO-ONLY-prefilled-token')


def test_health_not_ready_is_retried():
    server = Mock()
    server.poll.return_value = None
    with patch.object(demo, 'build_opener') as opener:
        response = opener.return_value.open.return_value.__enter__.return_value
        response.status = 200
        response.read.side_effect = [b'{"ready": false}', b'{"ready": true}']
        demo.wait_for_health(server, interval=0)
        assert response.read.call_count == 2


def test_cli_defaults_and_options():
    with patch.object(demo, 'launch', return_value=0) as launch:
        assert demo.main([]) == 0
        launch.assert_called_once_with(2, browser=True, viewer='normal')
        launch.reset_mock()
        demo.main(['--coaches', '8', '--no-browser', '--viewer', 'transparent'])
        launch.assert_called_once_with(8, browser=False, viewer='transparent')
