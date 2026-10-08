import json
import sqlite3
import pytest
from final_project.config import ProjectConfig
from final_project.storage.repository import SQLiteRepository, RepositoryError, Snapshot, SCHEMA_VERSION
from .service_support import initial


def test_empty_db_schema_and_roundtrip(tmp_path):
    repo = SQLiteRepository(ProjectConfig(project_root=tmp_path))
    try:
        assert repo.path == tmp_path/'runtime/final_project/auction.sqlite3'
        assert repo.load() is None
        assert repo._connection.execute('PRAGMA user_version').fetchone()[0] == SCHEMA_VERSION
        snap = Snapshot(initial())
        repo.commit(snap)
        assert repo.load() == snap
        assert repo._connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        repo.close()


def test_transaction_rollback(tmp_path):
    repo = SQLiteRepository(ProjectConfig(project_root=tmp_path))
    try:
        before = Snapshot(initial())
        repo.commit(before)
        repo._connection.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON snapshot BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        candidate = Snapshot(initial(), version=1)
        candidate.state.budgets['coach01'] = 900
        with pytest.raises(RepositoryError):
            repo.commit(candidate)
        assert repo.load() == before
        assert not repo._connection.in_transaction
        repo._connection.execute('DROP TRIGGER fail_update')
        repo.commit(candidate)
        assert repo.load() == candidate
    finally:
        repo.close()


def test_unknown_database_schema(tmp_path):
    cfg = ProjectConfig(project_root=tmp_path)
    repo = SQLiteRepository(cfg)
    repo._connection.execute('PRAGMA user_version=999')
    repo.close()
    with pytest.raises(RepositoryError, match='Unsupported database schema'):
        SQLiteRepository(cfg)


@pytest.mark.parametrize('mutation',[
    lambda r: r.update(schema_version=2),
    lambda r: r['state'].pop('minimum_bid'),
    lambda r: r['metadata'].update(settled_round_id='other'),
    lambda r: r['state']['budgets'].update(coach01=True),
    lambda r: r['state']['bids'].update(coach01='100'),
    lambda r: r['state'].update(status='bad'),
    lambda r: r['metadata'].update(version=-1),
    lambda r: r['metadata'].update(remaining=float('nan')),
    lambda r: r['state']['history'].append({'player':'Player01','coach_id':'unknown','amount':100,'time':None}),
    lambda r: r['metadata'].update(processed={'bad':{'fingerprint':'hash','result':{'ok':True}}}),
])
def test_corrupt_snapshot_rejected(tmp_path, mutation):
    repo = SQLiteRepository(ProjectConfig(project_root=tmp_path))
    try:
        repo.commit(Snapshot(initial()))
        raw = json.loads(repo._connection.execute('SELECT document FROM snapshot').fetchone()[0])
        mutation(raw)
        with repo._connection:
            repo._connection.execute('UPDATE snapshot SET document=?',(json.dumps(raw),))
        with pytest.raises(RepositoryError):
            repo.load()
    finally:
        repo.close()


def test_invalid_json_rejected(tmp_path):
    repo = SQLiteRepository(ProjectConfig(project_root=tmp_path))
    try:
        repo.commit(Snapshot(initial()))
        with repo._connection:
            repo._connection.execute("UPDATE snapshot SET document='not json'")
        with pytest.raises(RepositoryError): repo.load()
    finally:
        repo.close()


def test_invalid_config_cannot_target_data(tmp_path):
    with pytest.raises(ValueError): ProjectConfig(project_root=tmp_path, sqlite_file='data/state.sqlite3')


def test_config_default_root_unchanged():
    from final_project.config import PROJECT_ROOT
    cfg=ProjectConfig()
    assert cfg.project_root==PROJECT_ROOT and cfg.port==3001
    assert cfg.path(cfg.sqlite_file)==PROJECT_ROOT/'runtime/final_project/auction.sqlite3'


def test_root_override_not_loaded_from_json(tmp_path):
    from final_project.config import load_config
    path=tmp_path/'override.json'; path.write_text(json.dumps({'project_root':str(tmp_path)}))
    with pytest.raises(ValueError,match='test constructor'): load_config(path)
