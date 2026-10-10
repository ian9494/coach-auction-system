"""Optional actual browser/network smoke; core pytest remains browser-independent."""
import asyncio
import json
import os
from pathlib import Path
import shutil

import pytest
from .live_support import live
from .transport_support import config_and_auth


def test_playwright_viewer_network_and_obs(tmp_path):
    node=shutil.which('node')
    if not node or not os.environ.get('FINAL_PROJECT_PLAYWRIGHT_MODULE'):
        pytest.skip('Set FINAL_PROJECT_PLAYWRIGHT_MODULE for optional actual browser smoke')
    async def run():
        config,auth=config_and_auth(tmp_path)
        async with live(config,auth) as r:
            process=await asyncio.create_subprocess_exec(node,'scripts/smoke_final_viewer.cjs',
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            payload={'url':r.url,'auth':{'admin':auth.admin_token,'coach01':auth.coach_tokens['coach01'],
                     'coach02':auth.coach_tokens['coach02']},'screenshot':str(tmp_path/'transparent.png')}
            try:
                stdout,stderr=await asyncio.wait_for(process.communicate(json.dumps(payload).encode()),60)
            finally:
                if process.returncode is None:
                    process.kill(); await process.wait()
            assert process.returncode==0,stderr.decode(errors='replace')
            report=json.loads(stdout)
            assert report['ok'] and report['viewer_frames']>=5 and report['running_payload_private_fields']==0
            assert report['external_requests']==report['page_errors']==0
            assert report['layout']['rows']==2 and report['layout']['columns']==4
            assert (tmp_path/'transparent.png').exists()
    asyncio.run(run())
