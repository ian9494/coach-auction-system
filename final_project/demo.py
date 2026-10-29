"""One-command isolated demo launcher and legacy explicit session preparation."""
import argparse
import json
from pathlib import Path
import secrets
import shutil

from .config import ProjectConfig
from .resources import resource_root
from .server.auth import AuthConfig


def prepare_demo(root: Path) -> Path:
    root = Path(root).resolve()
    ProjectConfig(project_root=root)  # Validate path containment before writing files.
    resources = resource_root()
    # Never replace an existing session, DB, roster or user-provided credentials.
    root.mkdir(parents=True, exist_ok=False)
    target = root / 'examples/final_project'
    shutil.copytree(resources / 'examples/final_project', target)
    credentials = {'admin_token': secrets.token_hex(24), 'coach_tokens': {
        f'coach{i:02d}': secrets.token_hex(24) for i in range(1, 9)}}
    AuthConfig(**credentials)
    runtime = root / 'runtime/final_project'
    runtime.mkdir(parents=True)
    token_path = runtime / 'demo_tokens.json'
    token_path.write_text(json.dumps(credentials, indent=2) + '\n', encoding='utf-8')
    # Best effort owner-only mode on POSIX; Windows uses the demo root's ACL.
    token_path.chmod(0o600)
    shutil.copyfile(resources / 'config/final_project.demo.example.json', root / 'config.json')
    return token_path


def demo_auth(root: Path) -> AuthConfig:
    config = ProjectConfig(project_root=Path(root))
    path = config.path('runtime/final_project/demo_tokens.json')
    return AuthConfig(**json.loads(path.read_text(encoding='utf-8')))


# Launcher credentials live only in the inherited child environment.
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

SERVER_URL = 'http://127.0.0.1:3001'


def demo_environment(environ=None):
    env = dict(os.environ if environ is None else environ)
    names = ['FINAL_PROJECT_ADMIN_TOKEN'] + [
        f'FINAL_PROJECT_COACH_TOKEN_COACH{i:02d}' for i in range(1, 9)]
    for index, name in enumerate(names):
        env[name] = f'DEMO-ONLY-{index}-' + secrets.token_hex(24)
    env.update(FINAL_PROJECT_HOST='127.0.0.1', FINAL_PROJECT_PORT='3001')
    AuthConfig.from_env([f'coach{i:02d}' for i in range(1, 9)], env)
    return env


def viewer_url(viewer='normal'):
    pages = {'normal': 'viewer.html', 'transparent': 'viewer-transparent.html',
             'colored': 'viewer-colored.html'}
    return SERVER_URL + '/final-project/' + pages[viewer]


def component_commands(coaches=2):
    if not 1 <= coaches <= 8:
        raise ValueError('coaches must be between 1 and 8')
    return [[sys.executable, '-m', 'final_project.server.app'],
            [sys.executable, '-m', 'final_project.client.admin_app', '--server', SERVER_URL],
            *[[sys.executable, '-m', 'final_project.client.coach_app', '--server',
               SERVER_URL, '--coach-id', f'coach{i:02d}'] for i in range(1, coaches + 1)]]


def wait_for_health(server, timeout=20, interval=0.1):
    deadline = time.monotonic() + timeout
    # Local readiness must not go through a configured HTTP proxy.
    opener = build_opener(ProxyHandler({}))
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError('Demo Server exited before becoming ready')
        try:
            with opener.open(SERVER_URL + '/health',
                             timeout=max(0.001, min(1, deadline-time.monotonic()))) as response:
                if response.status == 200 and json.load(response).get('ready') is True:
                    return
        except (URLError, OSError, ValueError):
            pass
        time.sleep(max(0, min(interval, deadline-time.monotonic())))
    raise TimeoutError('Demo Server /health readiness timed out')


def cleanup_processes(processes, timeout=5):
    # Signal every live child before waiting, so shutdown happens concurrently.
    for process in reversed(processes):
        if process.poll() is None:
            try:
                if os.name == 'nt':
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
            except OSError:
                pass
    for process in reversed(processes):
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass
            process.wait()


def launch(coaches=2, *, browser=True, viewer='normal'):
    commands = component_commands(coaches)
    processes = []
    # Fail before launching if another application already owns the demo port.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 3001))
    with tempfile.TemporaryDirectory(prefix='auction-demo-') as temporary:
        root = Path(temporary)
        shutil.copytree(resource_root() / 'examples/final_project', root / 'examples/final_project')
        env = demo_environment()
        env['FINAL_PROJECT_ROOT'] = str(root)
        options = {'env': env}
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            processes.append(subprocess.Popen(commands[0], **options))
            wait_for_health(processes[0])
            for command in commands[1:]:
                processes.append(subprocess.Popen(command, **options))
            if browser:
                webbrowser.open(viewer_url(viewer))
            print('DEMO ONLY: Server ready at ' + SERVER_URL + '; Ctrl+C to stop all components.', flush=True)
            # A manually closed GUI is expected; Server exit or all GUIs closed ends demo.
            while processes[0].poll() is None and any(p.poll() is None for p in processes[1:]):
                time.sleep(0.2)
            return 0 if processes[0].poll() in (None, 0) else 1
        finally:
            cleanup_processes(processes)


def main(argv=None):
    parser = argparse.ArgumentParser(description='DEMO ONLY one-command local auction launcher')
    parser.add_argument('--root', type=Path, help='Legacy: prepare a new session only')
    parser.add_argument('--coaches', type=int, choices=range(1, 9), default=2)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--viewer', choices=('normal', 'transparent', 'colored'), default='normal')
    args = parser.parse_args(argv)
    try:
        if args.root is not None:
            prepare_demo(args.root)
            print('New demo prepared; credentials remain in its isolated runtime directory.')
            return 0
        return launch(args.coaches, browser=not args.no_browser, viewer=args.viewer)
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError, TimeoutError):
        print('Demo launch failed. Check dependencies, local port 3001 and GUI availability.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
