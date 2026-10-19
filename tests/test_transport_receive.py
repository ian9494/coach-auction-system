import asyncio
from queue import Queue
from types import SimpleNamespace
import pytest
from final_project.client.transport import SnapshotReceived, CommandAckReceived
from .test_client_transport import receive


@pytest.mark.parametrize('snapshot_first', [True, False])
def test_receive_retains_snapshot_regardless_of_ack_order(snapshot_first):
    async def run():
        t = SimpleNamespace(events=Queue())
        snapshot = SnapshotReceived({'status':'ended', 'version':1})
        ack = CommandAckReceived({'ok':True, 'version':1})
        for event in ([snapshot, ack] if snapshot_first else [ack, snapshot]): t.events.put(event)
        assert await receive(t, CommandAckReceived) == ack
        assert await receive(t, SnapshotReceived) == snapshot
    asyncio.run(run())
