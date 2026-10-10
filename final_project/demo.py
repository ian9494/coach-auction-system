"""Explicit demo preparation: new directory, demo CSVs and generated local credentials."""
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


def main():
    parser = argparse.ArgumentParser(description='Prepare a NEW isolated DEMO / TEST ONLY session')
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    try:
        prepare_demo(args.root)
    except FileExistsError:
        parser.error('Demo root already exists; choose a new directory. No files were replaced.')
    print('New demo prepared. Credentials remain in runtime/final_project/demo_tokens.json; no database was created.')


if __name__ == '__main__': main()
