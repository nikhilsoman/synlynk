import asyncio
import threading
from types import SimpleNamespace

import pytest

from synlynk.relay_hub import NatsTransport, _local_work


@pytest.mark.parametrize('operation', ['local_work', 'consumer'])
@pytest.mark.parametrize('cancel_count', [1, 2])
def test_cancellation_survives_inflight_storage_failure(operation, cancel_count):
    if operation == 'consumer':
        pytest.importorskip('nats')
    async def scenario():
        entered, release = threading.Event(), threading.Event()

        def callback(*args):
            entered.set()
            assert release.wait(3)
            raise OSError('storage failed during shutdown')

        class Subscription:
            calls = 0

            async def fetch(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return [SimpleNamespace(subject='x', data=b'x',
                        metadata=SimpleNamespace(sequence=SimpleNamespace(stream=1)))]
                await asyncio.Future()

        class JetStream:
            async def stream_info(self, *args):
                return SimpleNamespace(state=SimpleNamespace(first_seq=1))

        sub = Subscription()
        owner = SimpleNamespace(_js=JetStream(), timeout=1, last_error=None)
        tracker = SimpleNamespace(last_delivered_seq=0, detect_sync_gap=lambda info: False)
        work = (_local_work(callback) if operation == 'local_work' else
                NatsTransport._consume(owner, sub, 'stream', tracker, callback, lambda *args: None))
        task = asyncio.create_task(work)
        try:
            for _ in range(200):
                if entered.is_set():
                    break
                await asyncio.sleep(.005)
            assert entered.is_set()
            for _ in range(cancel_count):
                task.cancel()
                await asyncio.sleep(.01)
            assert not task.done(), 'Cancellation abandoned an active storage worker'
            release.set()
            done, _ = await asyncio.wait({task}, timeout=1.5)
            assert task in done, 'Consumer resumed fetching after cancellation'
            with pytest.raises(asyncio.CancelledError):
                await task
            if operation == 'consumer':
                assert sub.calls == 1
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
