import json
import shutil
import subprocess
import pytest
from .fixture_adapter import FIXTURE, ROOT, run_case, assert_partial

@pytest.fixture(scope='module')
def legacy():
    node=shutil.which('node')
    assert node, 'Node is required for parity verification'
    output=subprocess.run([node,str(ROOT/'scripts/legacy_parity.cjs')],capture_output=True,text=True,encoding='utf-8',check=True,timeout=15)
    return {r['id']:r['result'] for r in json.loads(output.stdout)}

@pytest.mark.parametrize('case',FIXTURE['cases'],ids=lambda c:c['id'])
def test_shared_cases(case,legacy):
    python=run_case(case)
    node=legacy[case['id']]
    assert_partial(python,case['expected'])
    assert_partial(node,case['expected'])
    assert python==node
