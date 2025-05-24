import time
from cachetronomy.core.store.utils.batch_logger import SyncBatchLogger

def test_sync_batch_flush_by_size():
    flushed = []
    logger = SyncBatchLogger(flushed.extend, batch_size=3, flush_interval=10)
    for i in range(3):
        logger.log(i)
    assert flushed == [0, 1, 2]

def test_sync_batch_flush_by_time(monkeypatch):
    flushed = []
    logger = SyncBatchLogger(flushed.extend, batch_size=99, flush_interval=0.01)
    logger.log('x')
    time.sleep(0.05)      # tiny, keeps test fast
    assert flushed == ['x']
    logger.stop()